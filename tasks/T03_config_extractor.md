# T03 — Config Claim Extractor (config-fallback seam type)

## Context files (use @file — do not explore)
- @AGENTS.md
- @.bob/rules/coding.md
- @.bob/rules/seam_rules.md
- @src/invisible_seam/models.py
- @src/invisible_seam/extractors/doc_extractor.py

## What to build
`src/invisible_seam/extractors/config_extractor.py`

### Public API
```python
def extract_config_claims(repo_path: Path) -> list[Claim]:
    """Scans repo_path for config schema claims. Returns list of Claim."""
```

### Rules
1. **Find config schemas** — look for these files under `repo_path` (recursive):
   - `*.schema.json` — JSON Schema files
   - `config.yaml`, `config.yml`, `settings.yaml`, `settings.yml`
   - `pyproject.toml` sections with `[tool.*]` that have typed fields

2. **JSON Schema extraction** — for any `*.schema.json`:
   - Find all properties under `required: [...]` — each required property name becomes a Claim:
     `"Config schema requires field '{name}' to be present"` with type `"config-fallback"`
   - Find all properties with `"default"` key — each becomes a Claim:
     `"Config field '{name}' has default value '{default}'"` with type `"config-fallback"`

3. **YAML config extraction** — for YAML files:
   - Any key whose comment (line above, starting with `#`) contains "required" becomes a Claim
   - Any key with a `null` value and a comment with "optional" stays — not a claim

4. **IDs** — continue from where `doc_extractor` left off — accept an optional `start_id: int = 1` parameter to `extract_config_claims`

### What NOT to do
- Do not load arbitrary Python code to check config
- Do not use `exec` or `eval`

## Tests
`tests/extractors/test_config_extractor.py`

Use `tmp_path`. Plant:
1. A `config.schema.json`:
   ```json
   {
     "required": ["api_key", "timeout"],
     "properties": {
       "api_key": {"type": "string"},
       "timeout": {"type": "integer", "default": 30},
       "retries": {"type": "integer", "default": 3}
     }
   }
   ```
2. Assert: 4 claims — 2 from `required` + 2 from `default` fields

## Done when
- `pytest tests/extractors/test_config_extractor.py -v` passes
- `ruff check src/invisible_seam/extractors/config_extractor.py` clean
- `mypy src/invisible_seam/extractors/config_extractor.py` clean
