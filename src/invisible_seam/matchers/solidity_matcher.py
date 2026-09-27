"""Solidity code matcher for the Invisible Seam engine.

The core code_matcher is Python-`ast` only, so on Solidity repos it matches
nothing. This module handles the highest-value, lowest-false-positive Solidity
case: a documentation claim asserts a function *reverts* or is *access-controlled*
(only-owner / role-gated), but the `.sol` function body carries no such guard —
i.e. missing validation or missing access control, a real bug class.

Conservative by design: it fires ONLY when the claim explicitly asserts a guard.
A claim with no revert/access wording is never matched, so it cannot invent a seam.
"""
from __future__ import annotations

import re
from pathlib import Path

from invisible_seam.models import Claim, SeamCandidate

_SKIP_DIRS = {"node_modules", "lib", "out", "cache", ".git"}

# Claim wording that asserts a guard, and which kind.
_ACCESS_WORDS = re.compile(
    r"\b(only\s+(?:the\s+)?owner|onlyowner|only\s+admin|only\s+the\s+admin|"
    r"access\s*control|authori[sz]ed|role[- ]?gated|permissioned)\b",
    re.IGNORECASE,
)
_REVERT_WORDS = re.compile(
    r"\b(reverts?|requires?|must\s+(?:be|not|have)|fails?\s+if|throws?|reverting)\b",
    re.IGNORECASE,
)


def _asserted_guard(claim_text: str) -> str | None:
    """Return the guard kind a claim asserts: 'access', 'revert', or None."""
    if _ACCESS_WORDS.search(claim_text):
        return "access"
    if _REVERT_WORDS.search(claim_text):
        return "revert"
    return None


def find_solidity_function(name: str, repo_path: Path) -> tuple[Path, int, str] | None:
    """Return (file, 1-based line, block) for the first Solidity function `name`.
    `block` spans `function name(...) ... { ... }` (signature + brace-matched body).
    Dependency/build dirs are skipped."""
    pat = re.compile(r"function\s+" + re.escape(name) + r"\s*\(")
    for sol in sorted(Path(repo_path).rglob("*.sol")):
        try:
            rel_parts = set(sol.relative_to(repo_path).parts)
        except ValueError:
            rel_parts = set()
        if rel_parts & _SKIP_DIRS:
            continue
        try:
            src = sol.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = pat.search(src)
        if not m:
            continue
        brace = src.find("{", m.end())
        if brace == -1:
            continue
        depth, i = 0, brace
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        block = src[m.start():i + 1]
        line = src[:m.start()].count("\n") + 1
        return sol, line, block
    return None


def _body_has_guard(block: str, kind: str) -> bool:
    """True if the function block carries the asserted guard. A function-level
    modifier (`only...`) counts for both kinds (modifiers usually revert)."""
    sig = block.split("{", 1)[0]
    body = block[len(sig):]
    has_modifier = bool(re.search(r"\bonly[A-Za-z0-9_]+", sig))
    if kind == "revert":
        return has_modifier or bool(
            re.search(r"\brequire\s*\(", body) or re.search(r"\brevert\b", body)
        )
    if kind == "access":
        return has_modifier or bool(
            re.search(r"require\s*\(\s*msg\.sender", body)
            or re.search(r"\bmsg\.sender\s*==", body)
            or re.search(r"\b(hasRole|_checkOwner|_checkRole|onlyRole)\b", block)
        )
    return False


def match_solidity_doc_claim(claim: Claim, repo_path: Path) -> SeamCandidate | None:
    """Match a doc claim naming a Solidity function against that function's guards.
    Returns a SeamCandidate (conflict=True when the asserted guard is absent), or
    None when the claim asserts no guard or the function is not found."""
    if not claim.subject:
        return None
    kind = _asserted_guard(claim.claim)
    if kind is None:
        return None
    found = find_solidity_function(claim.subject, repo_path)
    if found is None:
        return None
    path, line, block = found
    has = _body_has_guard(block, kind)
    behavior = (
        f"Solidity function '{claim.subject}' has NO {kind} guard "
        f"despite the claim"
        if not has
        else f"Solidity function '{claim.subject}' has a {kind} guard as claimed"
    )
    return SeamCandidate(
        claim_id=claim.id,
        behavior=behavior,
        behavior_file=path,
        behavior_line=line,
        conflict=not has,
    )
