"""Python security-fact extractor for the Invisible Seam engine.

Unlike doc/code claims, these findings start from a security invariant
rather than documentation: SQL text must not be built by interpolating
dynamic values; values must travel as bound parameters. The extractor is
AST-based and deliberately narrow for its first slice:

  - py-sql-format — a SQL string built with %, .format(), f-strings, or
    concatenation reaches an execute/executemany/executescript sink.

Parameterized calls (``execute(sql, params)`` with constant SQL) and
constant-only string assembly are clean. A dynamic value counts as a
source when it is a function parameter or propagates from request /
input / argv / environment access through simple assignments.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from invisible_seam.models import Claim

_SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "tests", "test",
    "_seam_checks", "node_modules", ".mypy_cache",
}
_SQL_RE = re.compile(
    r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO)\b",
    re.IGNORECASE,
)
_SINK_ATTRS = {"execute", "executemany", "executescript"}
_INVARIANT = (
    "SQL must be parameterized: values must be bound as parameters, "
    "never interpolated into SQL text"
)


@dataclass
class _ExprInfo:
    text: str = ""
    formatted: bool = False
    roots: set[str] = field(default_factory=set)
    constant: bool = True


def _next_id(counter: list[int]) -> str:
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_source_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "input"
    root = _root_name(func)
    called = func.attr if isinstance(func, ast.Attribute) else ""
    return root in {"request", "os", "sys"} or called in {"getenv", "get_data"}


def _expr_info(node: ast.AST, env: dict[str, _ExprInfo]) -> _ExprInfo:
    if isinstance(node, ast.Constant):
        return _ExprInfo(text=node.value if isinstance(node.value, str) else "")
    if isinstance(node, ast.Name):
        known = env.get(node.id)
        if known is not None:
            return _ExprInfo(known.text, known.formatted, set(known.roots), known.constant)
        return _ExprInfo(roots={node.id}, constant=False)
    if isinstance(node, ast.JoinedStr):
        text, roots, formatted = "", set(), False
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                formatted = True
                sub = _expr_info(value.value, env)
                text += sub.text
                roots |= sub.roots
            else:
                sub = _expr_info(value, env)
                text += sub.text
                roots |= sub.roots
        return _ExprInfo(text, formatted, roots, not formatted)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        left, right = _expr_info(node.left, env), _expr_info(node.right, env)
        formatted = left.formatted or right.formatted or (
            isinstance(node.op, ast.Mod) and not right.constant
        ) or (
            isinstance(node.op, ast.Add)
            and (not left.constant or not right.constant)
            and bool(left.text or right.text)
        )
        return _ExprInfo(
            left.text + right.text,
            formatted,
            left.roots | right.roots,
            left.constant and right.constant,
        )
    if isinstance(node, ast.Call):
        roots = set()
        if _is_source_call(node):
            roots.add("__source__")
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"format", "format_map"}:
            base = _expr_info(func.value, env)
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                sub = _expr_info(arg, env)
                roots |= sub.roots
                if not sub.constant:
                    formatted = True
                else:
                    formatted = base.formatted
            has_dynamic = any(not _expr_info(a, env).constant for a in node.args)
            return _ExprInfo(base.text, base.formatted or has_dynamic, base.roots | roots, False)
        root = _root_name(func)
        if root:
            roots.add(root)
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            roots |= _expr_info(arg, env).roots
        return _ExprInfo(roots=roots, constant=False)
    roots = set()
    constant = True
    for child in ast.iter_child_nodes(node):
        sub = _expr_info(child, env)
        roots |= sub.roots
        constant = constant and sub.constant
    return _ExprInfo(roots=roots, constant=constant)


def _call_attr(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _own_nodes(func: ast.AST) -> list[ast.AST]:
    """Nodes belonging to func, without descending into nested functions."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = [func]
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    while stack:
        node = stack.pop()
        out.append(node)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, nested) and child is not func:
                continue
            stack.append(child)
    return out


def _tainted_roots(info: _ExprInfo, tainted: set[str]) -> set[str]:
    return {r for r in info.roots if r in tainted or r == "__source__"}


def _scan_scope(
    scope: ast.AST,
    params: set[str],
    subject: str,
    py_file: Path,
    counter: list[int],
    claims: list[Claim],
    seen: set[tuple[str, int]],
) -> None:
    env: dict[str, _ExprInfo] = {}
    tainted = set(params)
    relevant = [
        n for n in _own_nodes(scope)
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Call))
    ]
    relevant.sort(key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
    for node in relevant:
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if node.value is None:
                continue
            info = _expr_info(node.value, env)
            for target in targets:
                if isinstance(target, ast.Name):
                    env[target.id] = info
                    if _tainted_roots(info, tainted):
                        tainted.add(target.id)
            continue
        if _call_attr(node) not in _SINK_ATTRS or not node.args:
            continue
        info = _expr_info(node.args[0], env)
        hits = _tainted_roots(info, tainted)
        if not info.formatted or not hits or not _SQL_RE.search(info.text):
            continue
        key = (str(py_file), node.lineno)
        if key in seen:
            continue
        seen.add(key)
        dynamic = ", ".join(sorted(h for h in hits if h != "__source__") or ["external input"])
        claims.append(
            Claim(
                id=_next_id(counter),
                type=cast("object", "py-sql-format"),  # type: ignore[arg-type]
                claim=(
                    f"{_INVARIANT}; function '{subject}' interpolates "
                    f"dynamic value(s) {dynamic} into SQL text passed to "
                    f"{_call_attr(node)}() at line {node.lineno}"
                ),
                source_file=py_file,
                source_line=node.lineno,
                subject=subject,
            )
        )


def extract_python_security_claims(
    repo_path: Path, start_id: int = 1
) -> list[Claim]:
    """Extract high-confidence Python SQL-interpolation findings as claims."""
    counter = [start_id]
    claims: list[Claim] = []
    seen: set[tuple[str, int]] = set()
    repo_path = Path(repo_path)
    py_files = [
        f for f in sorted(repo_path.rglob("*.py"))
        if not any(skip in f.parts for skip in _SKIP_DIRS)
    ]
    for py_file in py_files:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, OSError):
            continue
        scopes: list[tuple[ast.AST, set[str], str]] = [(tree, set(), "<module>")]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = {
                    a.arg
                    for a in (
                        node.args.posonlyargs
                        + node.args.args
                        + node.args.kwonlyargs
                    )
                }
                if node.args.vararg:
                    params.add(node.args.vararg.arg)
                if node.args.kwarg:
                    params.add(node.args.kwarg.arg)
                scopes.append((node, params, node.name))
        for scope, params, subject in scopes:
            _scan_scope(scope, params, subject, py_file, counter, claims, seen)
    return claims
