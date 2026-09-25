from __future__ import annotations

from pathlib import Path

from invisible_seam.models import Claim, Seam, SeamCandidate


def test_claim_is_frozen(tmp_path: Path) -> None:
    c = Claim(id="C001", type="doc-code", claim="Returns a list", source_file=tmp_path, source_line=1)
    try:
        c.id = "C002"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        pass


def test_seam_candidate_conflict_flag(tmp_path: Path) -> None:
    sc = SeamCandidate(
        claim_id="C001",
        behavior="returns None",
        behavior_file=tmp_path,
        behavior_line=5,
        conflict=True,
    )
    assert sc.conflict is True


def test_seam_construction(tmp_path: Path) -> None:
    seam = Seam(
        id="S001",
        classification="FIXABLE",
        assertion_a="Returns list[str]",
        source_a=tmp_path,
        line_a=1,
        assertion_b="Returns None",
        source_b=tmp_path,
        line_b=5,
        check="pytest tests/",
        verdict="RESOLVED",
        question=None,
    )
    assert seam.classification == "FIXABLE"
    assert seam.verdict == "RESOLVED"
    assert seam.question is None
