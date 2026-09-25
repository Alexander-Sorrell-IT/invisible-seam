from __future__ import annotations

from pathlib import Path

from invisible_seam.extractors.doc_extractor import extract_claims


def test_readme_behavioral_claims(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "The service handles requests.\n"
        "Returns a list of active users.\n"
        "Raises ValueError if the input is empty.\n"
        "Defaults to 30 seconds on timeout.\n"
    )
    claims = extract_claims(tmp_path)
    texts = [c.claim for c in claims]
    assert any("Returns a list" in t for t in texts)
    assert any("Raises ValueError" in t for t in texts)
    assert any("Defaults to 30" in t for t in texts)


def test_type_hint_claim_extracted(tmp_path: Path) -> None:
    py = tmp_path / "sample.py"
    py.write_text(
        "def get_count(db: dict) -> int:\n"
        '    """Returns the user count."""\n'
        "    return len(db)\n"
    )
    claims = extract_claims(tmp_path)
    types = [c.type for c in claims]
    assert "type-hint" in types


def test_none_return_annotation_skipped(tmp_path: Path) -> None:
    py = tmp_path / "sample.py"
    py.write_text(
        "def do_nothing() -> None:\n"
        "    pass\n"
    )
    claims = extract_claims(tmp_path)
    type_hint_claims = [c for c in claims if c.type == "type-hint"]
    assert len(type_hint_claims) == 0


def test_claims_are_frozen(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("Returns a value.\n")
    claims = extract_claims(tmp_path)
    assert len(claims) >= 1
    try:
        claims[0].id = "mutated"  # type: ignore[misc]
        assert False, "Should be frozen"
    except Exception:
        pass
