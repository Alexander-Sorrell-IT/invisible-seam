from __future__ import annotations

import json
from pathlib import Path

from invisible_seam.extractors.config_extractor import extract_config_claims


def test_json_schema_required_and_defaults(tmp_path: Path) -> None:
    schema = {
        "required": ["api_key", "timeout"],
        "properties": {
            "api_key": {"type": "string"},
            "timeout": {"type": "integer", "default": 30},
            "retries": {"type": "integer", "default": 3},
        },
    }
    schema_file = tmp_path / "config.schema.json"
    schema_file.write_text(json.dumps(schema, indent=2))

    claims = extract_config_claims(tmp_path)
    assert len(claims) == 4  # 2 required + 2 defaults

    claim_texts = [c.claim for c in claims]
    assert any("api_key" in t and "requires" in t for t in claim_texts)
    assert any("timeout" in t and "requires" in t for t in claim_texts)
    assert any("timeout" in t and "default" in t for t in claim_texts)
    assert any("retries" in t and "default" in t for t in claim_texts)


def test_no_schema_no_claims(tmp_path: Path) -> None:
    claims = extract_config_claims(tmp_path)
    assert claims == []


def test_claims_have_source_file(tmp_path: Path) -> None:
    schema = {"required": ["key"], "properties": {"key": {"type": "string"}}}
    (tmp_path / "config.schema.json").write_text(json.dumps(schema))
    claims = extract_config_claims(tmp_path)
    assert all(c.source_file.exists() for c in claims)
