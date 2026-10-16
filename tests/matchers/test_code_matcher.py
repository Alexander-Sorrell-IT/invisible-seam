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


def test_parameter_annotation_is_never_a_candidate(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        "def get_users(db: dict) -> list[str]:\n"
        "    if not db:\n"
        "        return None\n"
        "    return list(db.keys())\n"
    )
    claims = [c for c in extract_claims(tmp_path) if c.claim.startswith("Parameter ")]
    assert claims
    assert match_claims(claims, tmp_path) == []


def test_matching_schema_and_code_default_is_not_a_conflict(tmp_path: Path) -> None:
    import json
    from invisible_seam.extractors.config_extractor import extract_config_claims
    schema = {"properties": {"timeout": {"type": "integer", "default": 30}}}
    (tmp_path / "config.schema.json").write_text(json.dumps(schema))
    (tmp_path / "loader.py").write_text(
        "def load(config: dict) -> int:\n    return config.get('timeout', 30)\n"
    )
    candidates = match_claims(extract_config_claims(tmp_path), tmp_path)
    assert candidates and not any(c.conflict for c in candidates)


def test_different_schema_and_code_default_is_a_conflict(tmp_path: Path) -> None:
    import json
    from invisible_seam.extractors.config_extractor import extract_config_claims
    schema = {"properties": {"timeout": {"type": "integer", "default": 30}}}
    (tmp_path / "config.schema.json").write_text(json.dumps(schema))
    (tmp_path / "loader.py").write_text(
        "def load(config: dict) -> int:\n    return config.get('timeout', 60)\n"
    )
    candidates = match_claims(extract_config_claims(tmp_path), tmp_path)
    assert any(c.conflict for c in candidates)


def test_readme_claim_is_matched_against_the_named_function(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Svc\n\n### `load(config)`\n\nRaises `KeyError` if the key is missing.\n"
        "\n## Notes\n\nEverything raises KeyError loudly.\n"
    )
    (tmp_path / "loader.py").write_text(
        "def load(config: dict) -> str:\n    return config.get('k', 'x')\n"
    )
    claims = [c for c in extract_claims(tmp_path) if c.source_file.name == "README.md"]
    assert [c.subject for c in claims] == ["load", None]  # section ends at next heading
    candidates = match_claims(claims, tmp_path)
    assert len(candidates) == 1  # the claim with no function section is not guessed at
    assert candidates[0].conflict
    assert candidates[0].behavior_file.name == "loader.py"
