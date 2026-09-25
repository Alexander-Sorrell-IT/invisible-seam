from __future__ import annotations

import json
from pathlib import Path

import yaml

from invisible_seam.models import Claim


def _next_id(counter: list[int]) -> str:
    """Returns the next claim ID and increments the counter. Returns string like 'C001'."""
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def _extract_json_schema_claims(schema_file: Path, counter: list[int]) -> list[Claim]:
    """Extracts required-field and default-value claims from a JSON Schema file. Returns list of Claim."""
    claims: list[Claim] = []
    try:
        data = json.loads(schema_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return claims

    required: list[str] = data.get("required", [])
    properties: dict[str, object] = data.get("properties", {})

    # find line numbers by scanning the raw text
    raw_lines = schema_file.read_text(encoding="utf-8").splitlines()

    def _find_line(keyword: str) -> int:
        """Returns 1-based line number of first line containing keyword. Returns 1 if not found."""
        for i, line in enumerate(raw_lines, start=1):
            if keyword in line:
                return i
        return 1

    for field in required:
        claims.append(
            Claim(
                id=_next_id(counter),
                type="config-fallback",
                claim=f"Config schema requires field '{field}' to be present",
                source_file=schema_file,
                source_line=_find_line(f'"{field}"'),
            )
        )

    for field, props in properties.items():
        if isinstance(props, dict) and "default" in props:
            default_val = props["default"]
            claims.append(
                Claim(
                    id=_next_id(counter),
                    type="config-fallback",
                    claim=f"Config field '{field}' has default value '{default_val}'",
                    source_file=schema_file,
                    source_line=_find_line(f'"default"'),
                )
            )

    return claims


def _extract_yaml_claims(yaml_file: Path, counter: list[int]) -> list[Claim]:
    """Extracts required-field claims from YAML config files. Returns list of Claim."""
    claims: list[Claim] = []
    try:
        raw_lines = yaml_file.read_text(encoding="utf-8").splitlines()
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return claims

    if not isinstance(data, dict):
        return claims

    for i, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped.startswith("#") and ":" in stripped:
            prev_comment = raw_lines[i - 2].strip() if i >= 2 else ""
            if "required" in prev_comment.lower():
                key = stripped.split(":")[0].strip()
                claims.append(
                    Claim(
                        id=_next_id(counter),
                        type="config-fallback",
                        claim=f"Config field '{key}' is marked required (comment)",
                        source_file=yaml_file,
                        source_line=i,
                    )
                )

    return claims


def extract_config_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """Scans repo_path for config schema claims. Returns list of Claim."""
    counter = [start_id]
    claims: list[Claim] = []

    for schema_file in sorted(repo_path.rglob("*.schema.json")):
        claims += _extract_json_schema_claims(schema_file, counter)

    for yaml_name in ("config.yaml", "config.yml", "settings.yaml", "settings.yml"):
        for yaml_file in sorted(repo_path.rglob(yaml_name)):
            claims += _extract_yaml_claims(yaml_file, counter)

    return claims
