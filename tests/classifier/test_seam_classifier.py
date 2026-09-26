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


def _schema_pair(tmp_path: Path, schema: dict, behavior: str) -> tuple[SeamCandidate, Claim]:
    import dataclasses
    import json

    schema_file = tmp_path / "config.schema.json"
    schema_file.write_text(json.dumps(schema))
    candidate, claim = _make_pair(
        tmp_path, "config-fallback", "Config schema requires field 'api_key' to be present", behavior
    )
    return candidate, dataclasses.replace(claim, source_file=schema_file)


def test_required_field_with_code_default_is_fixable(tmp_path: Path) -> None:
    """Schema is unambiguous (required, no default): the code is simply wrong."""
    candidate, claim = _schema_pair(
        tmp_path,
        {"required": ["api_key"], "properties": {"api_key": {"type": "string"}}},
        "Code calls .get('api_key', 'default') — silently uses default when field is absent",
    )
    seam = classify(candidate, claim)
    assert seam.classification == "FIXABLE"
    assert seam.question is None


def test_required_field_with_schema_default_is_paradox(tmp_path: Path) -> None:
    """The schema contradicts itself: no code change can settle it."""
    candidate, claim = _schema_pair(
        tmp_path,
        {"required": ["api_key"], "properties": {"api_key": {"type": "string", "default": "x"}}},
        "The same schema gives 'api_key' a default of 'x'",
    )
    seam = classify(candidate, claim)
    assert seam.classification == "PARADOX"
    assert seam.question is not None and "required AND gives it a default" in seam.question


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
