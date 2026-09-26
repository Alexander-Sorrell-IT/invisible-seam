from __future__ import annotations

import ast
import dataclasses
import re
from pathlib import Path

from invisible_seam.checker.check_runner import run_check
from invisible_seam.models import Seam


def fix_seam(seam: Seam, repo_path: Path) -> Seam:
    """Patches a RESOLVED FIXABLE seam. Re-runs the check. Returns updated Seam."""
    if seam.classification != "FIXABLE" or seam.verdict != "RESOLVED":
        return seam

    if re.search(r"annotation:", seam.assertion_a):
        seam = _fix_type_hint(seam, repo_path)
    elif _NEVER_NONE.search(seam.assertion_a):
        seam = _fix_never_none(seam, repo_path)
    elif re.search(r"raises?", seam.assertion_a, re.IGNORECASE):
        seam = _fix_doc_raises(seam, repo_path)
    elif "has default value" in seam.assertion_a:
        seam = _fix_config_default(seam, repo_path)
    elif "config" in seam.assertion_a.lower():
        seam = _fix_config_fallback(seam, repo_path)
    else:
        return seam

    # re-run the SAME check: CLOSED only if it now exits 0 (claim holds)
    if seam.check is None:
        return dataclasses.replace(seam, verdict="UNSOLVED", question="no check to re-prove fix")
    return run_check(seam, repo_path)


_NEVER_NONE = re.compile(r"\bnever\s+returns?\s+`?None\b", re.IGNORECASE)
_EMPTY_FOR = {"list": "[]", "dict": "{}", "set": "set()", "tuple": "()", "str": '""'}


def _has_container_return(target: Path, func_name: str) -> bool:
    """Returns True if func_name's return annotation is a type with an empty value."""
    func = next(
        (
            n
            for n in ast.walk(ast.parse(target.read_text(encoding="utf-8")))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name
        ),
        None,
    )
    if func is None or func.returns is None:
        return False
    return ast.unparse(func.returns).split("[")[0].split("|")[0].strip() in _EMPTY_FOR


def _return_nones_to_empty(target: Path, func_name: str) -> bool:
    """Rewrites `return None` / bare `return` in func_name to the empty value of its
    container return type (e.g. list[str] -> []). Returns True if the file changed."""
    if not target.exists():
        return False
    text = target.read_text(encoding="utf-8")
    func = next(
        (
            n
            for n in ast.walk(ast.parse(text))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func_name
        ),
        None,
    )
    if func is None or func.returns is None:
        return False
    base = ast.unparse(func.returns).split("[")[0].split("|")[0].strip()
    empty = _EMPTY_FOR.get(base)
    if empty is None:
        return False

    lines = text.splitlines(keepends=True)
    changed = False
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and (
            node.value is None
            or (isinstance(node.value, ast.Constant) and node.value.value is None)
        ):
            i = node.lineno - 1
            new = re.sub(r"\breturn(\s+None)?\b", f"return {empty}", lines[i], count=1)
            if new != lines[i]:
                lines[i] = new
                changed = True
    if changed:
        target.write_text("".join(lines), encoding="utf-8")
    return changed


def _fix_never_none(seam: Seam, repo_path: Path) -> Seam:
    """Fixes a never-returns-None seam in the code: None returns become the empty value."""
    m = re.search(r"Function '(\w+)'", seam.assertion_b)
    if m:
        _return_nones_to_empty(seam.source_b, m.group(1))
    return seam


def _fix_type_hint(seam: Seam, repo_path: Path) -> Seam:
    """Fixes a type-hint seam. Container return types: make the code honor the annotation
    (None returns become the empty value). Otherwise widen the annotation to admit None."""
    target = seam.source_a
    if not target.exists():
        return seam
    m = re.search(r"Function '(\w+)'", seam.assertion_a)
    if m and _has_container_return(target, m.group(1)):
        # the annotation is a real contract: fix the code, never weaken the type
        _return_nones_to_empty(target, m.group(1))
        return seam

    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    lineno = seam.line_a - 1  # 0-indexed

    if lineno < 0 or lineno >= len(lines):
        return seam

    original = lines[lineno]
    # widen the return annotation to admit the None the code actually returns:
    # "-> list[str]:" becomes "-> list[str] | None:" (keeps the colon and the type)
    fixed = re.sub(r"->\s*([^:]+?)\s*:", r"-> \1 | None:", original, count=1)
    if fixed == original:
        return seam

    lines[lineno] = fixed
    target.write_text("".join(lines), encoding="utf-8")
    return seam


def _fix_doc_raises(seam: Seam, repo_path: Path) -> Seam:
    """Fixes a doc-code raises seam by updating the docstring to match behavior. Returns updated Seam."""
    target = seam.source_a
    if not target.exists():
        return seam

    m = re.search(r"raises?\s+`?(\w+)", seam.assertion_a, re.IGNORECASE)
    if not m:
        return seam
    exc_name = m.group(1)

    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    start = max(seam.line_a - 1, 0)
    for i in range(start, len(lines)):
        line = lines[i]
        if re.search(rf"raises?\s+`?{exc_name}", line, re.IGNORECASE):
            lines[i] = re.sub(
                rf"[Rr]aises?\s+`?{exc_name}`?[^.]*",
                f"returns a value instead of raising {exc_name}",
                line,
            )
            break

    target.write_text("".join(lines), encoding="utf-8")
    return seam


def _fix_config_fallback(seam: Seam, repo_path: Path) -> Seam:
    """Fixes a config-fallback seam by replacing .get(key, default) with [key]. Returns updated Seam."""
    target = seam.source_b
    if not target.exists():
        return seam

    m = re.search(r"\.get\('(\w+)'", seam.assertion_b)
    if not m:
        return seam
    field = m.group(1)

    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    lineno = seam.line_b - 1

    if lineno < 0 or lineno >= len(lines):
        return seam

    original = lines[lineno]
    # replace .get('field', anything) with ['field']
    fixed = re.sub(
        rf"\.get\(['\"]({re.escape(field)})['\"],\s*[^)]+\)",
        rf"['\1']",
        original,
    )
    if fixed == original:
        return seam

    lines[lineno] = fixed
    target.write_text("".join(lines), encoding="utf-8")
    return seam


def _fix_config_default(seam: Seam, repo_path: Path) -> Seam:
    """Fixes a default mismatch by setting the code's .get default to the schema default."""
    target = seam.source_b
    m_field = re.search(r"'(\w+)'", seam.assertion_a)
    m_default = re.search(r"has default value '(.*)'$", seam.assertion_a)
    if not target.exists() or not m_field or not m_default:
        return seam
    field = re.escape(m_field.group(1))

    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    lineno = seam.line_b - 1
    if lineno < 0 or lineno >= len(lines):
        return seam
    new_default = m_default.group(1)

    def _repl(mm: re.Match[str]) -> str:
        return f"{mm.group(1)}{new_default})"

    lines[lineno] = re.sub(rf"(\.get\(['\"]{field}['\"],\s*)[^)]+\)", _repl, lines[lineno])
    target.write_text("".join(lines), encoding="utf-8")
    return seam
