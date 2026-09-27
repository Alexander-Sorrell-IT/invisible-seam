"""Solidity NatSpec claim extractor for the Invisible Seam engine.

The README/docstring extractor is Python-shaped and produces no function-linked
claims from Solidity repos. Solidity's behavioral contracts live in NatSpec
comments (``/// @notice``, ``/// @dev``, ``/** */``) directly above each function.

This extractor reads the NatSpec block above each ``function`` and, when it
asserts a guard (reverts / requires / only-owner / access control), emits a
``doc-code`` Claim whose ``subject`` is the function name. The Solidity matcher
then checks whether the function body actually carries that guard — a missing
one is a real access-control / validation seam.

Conservative: only NatSpec that asserts a guard becomes a claim, so ordinary
descriptive NatSpec never manufactures a seam.
"""
from __future__ import annotations

import re
from pathlib import Path

from invisible_seam.matchers.solidity_matcher import _asserted_guard
from invisible_seam.models import Claim

_SKIP_DIRS = {"node_modules", "lib", "out", "cache", ".git"}
_FUNC = re.compile(r"^\s*function\s+(\w+)\s*\(")


def _next_id(n: int) -> str:
    return f"C{n:03d}"


def _natspec_above(lines: list[str], func_idx: int) -> str:
    """Collect the contiguous NatSpec comment block immediately above func_idx.
    Handles `///` line comments and `/** ... */` block comments. Stops at the
    first non-comment (or blank) line."""
    collected: list[str] = []
    j = func_idx - 1
    while j >= 0:
        s = lines[j].strip()
        if s.startswith("///"):
            collected.append(s.lstrip("/").strip())
        elif s.startswith("/**") or s.startswith("*") or s.endswith("*/"):
            collected.append(s.strip("/*").strip())
        else:
            break
        j -= 1
    collected.reverse()
    return " ".join(x for x in collected if x)


def extract_solidity_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """Extract guard-asserting NatSpec claims from every .sol function in the repo."""
    claims: list[Claim] = []
    counter = start_id
    repo_path = Path(repo_path)
    for sol in sorted(repo_path.rglob("*.sol")):
        try:
            rel = set(sol.relative_to(repo_path).parts)
        except ValueError:
            rel = set()
        if rel & _SKIP_DIRS:
            continue
        try:
            lines = sol.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            m = _FUNC.match(line)
            if not m:
                continue
            natspec = _natspec_above(lines, i)
            if not natspec or _asserted_guard(natspec) is None:
                continue
            claims.append(Claim(
                id=_next_id(counter),
                type="doc-code",
                claim=natspec,
                source_file=sol,
                source_line=i + 1,
                subject=m.group(1),
            ))
            counter += 1
    return claims
