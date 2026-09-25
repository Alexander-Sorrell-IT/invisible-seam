from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SeamType = Literal["doc-code", "type-hint", "config-fallback", "auth"]
Classification = Literal["FIXABLE", "PARADOX"]
Verdict = Literal["RESOLVED", "UNSOLVED", "CERTAIN", "KNOWN", "CLOSED"]


@dataclass(frozen=True)
class Claim:
    """A behavioral promise extracted from docs, annotations, or config schemas."""

    id: str
    type: SeamType
    claim: str
    source_file: Path
    source_line: int


@dataclass(frozen=True)
class SeamCandidate:
    """A claim paired with observed code behavior, flagged if they conflict."""

    claim_id: str
    behavior: str
    behavior_file: Path
    behavior_line: int
    conflict: bool


@dataclass(frozen=True)
class Seam:
    """A confirmed contradiction between a claim and behavior."""

    id: str
    classification: Classification
    assertion_a: str
    source_a: Path
    line_a: int
    assertion_b: str
    source_b: Path
    line_b: int
    check: str | None
    verdict: Verdict
    question: str | None
