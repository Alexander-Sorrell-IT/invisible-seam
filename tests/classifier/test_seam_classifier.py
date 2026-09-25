from __future__ import annotations

from pathlib import Path

from invisible_seam.models import Claim, SeamCandidate
from invisible_seam.classifier.seam_classifier import classify


def _make_pair(
    tmp_path: Path,
    claim_type: str,
    claim_text: str,
    behavior: str,
) -> tuple[SeamCandidate, Claim]:
    claim = Claim(
        id="C001",
        type=claim_type,  # type: ignore[arg-type]
        claim=claim_text,
        source_file=tmp_path / "src.py",
        source_line=1,
    )
    candidate = SeamCandidate(
        claim_id="C001",
        behavior=behavior,
        behavior_file=tmp_path / "src.py",
        behavior_line=5,
        conflict=True,
    )
    return candidate, claim


def test_type_hint_classifies_as_fixable(tmp_path: Path) -> None:
    candidate, claim = _make_pair(
        tmp_path,
        "type-hint",
        "Function 'foo' return annotation: list[str]",
        "Function 'foo' returns: None",
    )
    seam = classify(candidate, claim)
    assert seam.classification == "FIXABLE"
    assert seam.question is None


def test_config_fallback_required_with_default_is_paradox(tmp_path: Path) -> None:
    candidate, claim = _make_pair(
        tmp_path,
        "config-fallback",
        "Config schema requires field 'api_key' to be present",
        "Code calls .get('api_key', 'default') — silently uses default when field is absent",
    )
    seam = classify(candidate, claim)
    # required + code has a default = PARADOX (schema and code contradict each other)
    assert seam.classification == "PARADOX"
    assert seam.question is not None


def test_config_fallback_default_only_is_fixable(tmp_path: Path) -> None:
    candidate, claim = _make_pair(
        tmp_path,
        "config-fallback",
        "Config field 'retries' has default value '3'",
        "Code calls .get('retries', 3) — silently uses default when field is absent",
    )
    seam = classify(candidate, claim)
    assert seam.classification == "FIXABLE"


def test_ambiguous_doc_classifies_as_paradox(tmp_path: Path) -> None:
    candidate, claim = _make_pair(
        tmp_path,
        "doc-code",
        "Function may raise ValueError if input is empty",
        "Function 'foo' does NOT raise ValueError",
    )
    seam = classify(candidate, claim)
    assert seam.classification == "PARADOX"
    assert seam.question is not None


def test_seam_has_both_assertions(tmp_path: Path) -> None:
    candidate, claim = _make_pair(
        tmp_path,
        "type-hint",
        "Function 'bar' return annotation: int",
        "Function 'bar' returns: 'hello'",
    )
    seam = classify(candidate, claim)
    assert seam.assertion_a
    assert seam.assertion_b
