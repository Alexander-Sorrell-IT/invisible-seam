from __future__ import annotations

from pathlib import Path

from invisible_seam.extractors.doc_extractor import extract_claims
from invisible_seam.matchers.code_matcher import match_claims


def test_type_hint_conflict_detected(tmp_path: Path) -> None:
    py = tmp_path / "broken.py"
    py.write_text(
        "def get_users(db: dict) -> list[str]:\n"
        "    if not db:\n"
        "        return None\n"
        "    return list(db.keys())\n"
    )
    claims = extract_claims(tmp_path)
    type_hints = [c for c in claims if c.type == "type-hint"]
    candidates = match_claims(type_hints, tmp_path)
    conflicts = [c for c in candidates if c.conflict]
    assert len(conflicts) >= 1


def test_no_conflict_on_correct_annotation(tmp_path: Path) -> None:
    py = tmp_path / "good.py"
    py.write_text(
        "def get_name() -> str:\n"
        '    return "hello"\n'
    )
    claims = extract_claims(tmp_path)
    type_hints = [c for c in claims if c.type == "type-hint"]
    candidates = match_claims(type_hints, tmp_path)
    conflicts = [c for c in candidates if c.conflict]
    assert len(conflicts) == 0


def test_config_fallback_conflict_detected(tmp_path: Path) -> None:
    import json
    schema = {"required": ["api_key"], "properties": {"api_key": {"type": "string"}}}
    (tmp_path / "config.schema.json").write_text(json.dumps(schema))

    py = tmp_path / "loader.py"
    py.write_text(
        "def load(config: dict) -> str:\n"
        "    return config.get('api_key', 'default_key')\n"
    )
    from invisible_seam.extractors.config_extractor import extract_config_claims
    claims = extract_config_claims(tmp_path)
    candidates = match_claims(claims, tmp_path)
    conflicts = [c for c in candidates if c.conflict]
    assert len(conflicts) >= 1
