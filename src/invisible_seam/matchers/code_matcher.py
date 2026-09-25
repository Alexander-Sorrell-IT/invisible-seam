from __future__ import annotations

import ast
import re
from pathlib import Path

from invisible_seam.models import Claim, SeamCandidate


def _returns_incompatible(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Returns True if any return statement is incompatible with the return annotation."""
    if func_node.returns is None:
        return False
    ann = ast.unparse(func_node.returns)
    if ann in ("None", "Any", "object"):
        return False

    for node in ast.walk(func_node):
        if not isinstance(node, ast.Return):
            continue
        if node.value is None:
            # bare return → incompatible with non-None annotation
            if "None" not in ann and "Optional" not in ann:
                return True
        elif isinstance(node.value, ast.Constant) and node.value.value is None:
            if "None" not in ann and "Optional" not in ann:
                return True

    return False


def _has_raises_claim(claim_text: str) -> tuple[bool, str]:
    """Returns (True, exception_name) if claim says raises X. Returns (False, '') otherwise."""
    m = re.search(r"\braises?\s+(\w+)", claim_text, re.IGNORECASE)
    if m:
        return True, m.group(1)
    return False, ""


def _function_raises(func_node: ast.FunctionDef | ast.AsyncFunctionDef, exc_name: str) -> bool:
    """Returns True if the function body contains a raise of exc_name."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Raise) and node.exc is not None:
            raised = ast.unparse(node.exc)
            if exc_name.lower() in raised.lower():
                return True
    return False


def _find_function(tree: ast.Module, lineno: int) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Returns the function node at or nearest to lineno. Returns None if not found."""
    best: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno:
                if best is None or node.lineno > best.lineno:
                    best = node
    return best


def _match_type_hint_claim(claim: Claim, repo_path: Path) -> SeamCandidate | None:
    """Matches a type-hint claim against actual code. Returns SeamCandidate or None."""
    try:
        source = claim.source_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return None

    func = _find_function(tree, claim.source_line)
    if func is None:
        return None

    conflict = _returns_incompatible(func)
    ann = ast.unparse(func.returns) if func.returns else "unknown"

    # find actual return types
    return_types: list[str] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            return_types.append(ast.unparse(node.value))

    behavior = (
        f"Function '{func.name}' returns: {', '.join(return_types) or 'None'} "
        f"(annotated as {ann})"
    )

    return SeamCandidate(
        claim_id=claim.id,
        behavior=behavior,
        behavior_file=claim.source_file,
        behavior_line=func.lineno,
        conflict=conflict,
    )


def _match_doc_code_claim(claim: Claim, repo_path: Path) -> SeamCandidate | None:
    """Matches a doc-code claim against actual code. Returns SeamCandidate or None."""
    is_raises, exc_name = _has_raises_claim(claim.claim)
    if not is_raises:
        return None  # only match raises-type doc claims for now

    # find the function the claim is about
    try:
        source = claim.source_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return None

    func = _find_function(tree, claim.source_line)
    if func is None:
        return None

    actually_raises = _function_raises(func, exc_name)
    conflict = not actually_raises

    behavior = (
        f"Function '{func.name}' does NOT raise {exc_name} — returns instead"
        if conflict
        else f"Function '{func.name}' raises {exc_name} as claimed"
    )

    return SeamCandidate(
        claim_id=claim.id,
        behavior=behavior,
        behavior_file=claim.source_file,
        behavior_line=func.lineno,
        conflict=conflict,
    )


def _match_config_fallback_claim(claim: Claim, repo_path: Path) -> SeamCandidate | None:
    """Matches a config-fallback claim against code that silently defaults. Returns SeamCandidate or None."""
    # extract the field name from the claim
    m = re.search(r"'(\w+)'", claim.claim)
    if not m:
        return None
    field = m.group(1)

    for py_file in sorted(repo_path.rglob("*.py")):
        if "_seam_checks" in py_file.parts:
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            # dict.get("field", default) — silent default
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Constant)
                and str(node.args[0].value) == field
            ):
                behavior = (
                    f"Code calls .get('{field}', {ast.unparse(node.args[1])}) "
                    f"— silently uses default when field is absent"
                )
                return SeamCandidate(
                    claim_id=claim.id,
                    behavior=behavior,
                    behavior_file=py_file,
                    behavior_line=node.lineno,
                    conflict=True,
                )

            # config["field"] or "default" — silent fallback via or
            if (
                isinstance(node, ast.BoolOp)
                and isinstance(node.op, ast.Or)
                and len(node.values) >= 2
            ):
                first = node.values[0]
                if (
                    isinstance(first, ast.Subscript)
                    and isinstance(first.slice, ast.Constant)
                    and str(first.slice.value) == field
                ):
                    behavior = (
                        f"Code uses config['{field}'] or <default> "
                        f"— silently falls back when field is absent"
                    )
                    return SeamCandidate(
                        claim_id=claim.id,
                        behavior=behavior,
                        behavior_file=py_file,
                        behavior_line=node.lineno,
                        conflict=True,
                    )

    return SeamCandidate(
        claim_id=claim.id,
        behavior=f"No silent fallback found for field '{field}'",
        behavior_file=claim.source_file,
        behavior_line=claim.source_line,
        conflict=False,
    )


def match_claims(claims: list[Claim], repo_path: Path) -> list[SeamCandidate]:
    """Pairs each Claim with actual code behavior. Returns SeamCandidate list."""
    results: list[SeamCandidate] = []
    for claim in claims:
        candidate: SeamCandidate | None = None
        if claim.type == "type-hint":
            candidate = _match_type_hint_claim(claim, repo_path)
        elif claim.type == "doc-code":
            candidate = _match_doc_code_claim(claim, repo_path)
        elif claim.type == "config-fallback":
            candidate = _match_config_fallback_claim(claim, repo_path)
        if candidate is not None:
            results.append(candidate)
    return results
