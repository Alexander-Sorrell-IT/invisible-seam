from __future__ import annotations

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


def _fix_type_hint(seam: Seam, repo_path: Path) -> Seam:
    """Fixes a type-hint seam by correcting the annotation to match behavior. Returns updated Seam."""
    target = seam.source_a
    if not target.exists():
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

    m = re.search(r"raises?\s+(\w+)", seam.assertion_a, re.IGNORECASE)
    if not m:
        return seam
    exc_name = m.group(1)

    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    start = max(seam.line_a - 1, 0)
    for i in range(start, len(lines)):
        line = lines[i]
        if re.search(rf"raises?\s+{exc_name}", line, re.IGNORECASE):
            lines[i] = re.sub(
                rf"[Rr]aises?\s+{exc_name}[^.]*",
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
