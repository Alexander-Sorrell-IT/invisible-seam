# T02 — Claim Extractor (doc-code + type-hint seam types)

## Context files (use @file — do not explore)
- @AGENTS.md
- @.bob/rules/coding.md
- @.bob/rules/seam_rules.md
- @src/invisible_seam/models.py

## What to build
`src/invisible_seam/extractors/doc_extractor.py`

### Public API
```python
def extract_claims(repo_path: Path) -> list[Claim]:
    """Scans repo_path for doc-code and type-hint claims. Returns list of Claim."""
```

### Rules
1. **README scanning** — find `README.md` or `README.rst` at `repo_path` root.
   Extract sentences that contain an explicit behavioral promise. A sentence is a claim if it
   matches any of these patterns (case-insensitive regex):
   - `returns?\s+\w+`  (e.g. "returns a list of users")
   - `raises?\s+\w+`   (e.g. "raises ValueError if empty")
   - `defaults?\s+to`  (e.g. "defaults to 30 seconds")
   - `requires?\s+\w+` (e.g. "requires an API key")
   - `must\s+\w+`      (e.g. "must be non-empty")
   Each matching sentence becomes a `Claim` with type `"doc-code"`.

2. **Docstring + type-hint scanning** — walk all `*.py` files under `repo_path`.
   Use `ast.parse()` only. For every `FunctionDef` and `AsyncFunctionDef`:
   - Extract the docstring (first string literal in body) if present
   - Extract return type annotation as a string if present
   - Extract each parameter's type annotation as a string if present
   Each annotation that is not `None` and not `Any` becomes a `Claim` with type `"type-hint"`.
   Docstrings that contain a behavioral promise (same patterns as README) become `Claim` with type `"doc-code"`.

3. **Deduplication** — if two claims have identical `claim` text and `source_file`, keep only one.

4. **IDs** — sequential: `"C001"`, `"C002"`, etc.

### What NOT to do
- Do not read whole files as strings and pass to an LLM for extraction
- Do not use regex on raw source — use `ast` for Python files
- Do not explore directories outside `repo_path`

## Tests
`tests/extractors/test_doc_extractor.py`

Use `tmp_path` fixture. Plant:
1. A `README.md` with "Returns a list of active users" and "Raises ValueError if the input is empty"
2. A `sample.py` with a function that has a docstring saying "Returns the user count" and a `-> int` return annotation
3. A `sample.py` function with no docstring and `-> None` return (should produce NO claim)

Assert:
- 3 claims extracted total (2 from README, 1 from docstring, 1 from annotation = 4 actually — count carefully)
- All have correct `source_file` and `source_line`
- Claims are frozen (can't mutate)

## Done when
- `pytest tests/extractors/test_doc_extractor.py -v` passes
- `ruff check src/invisible_seam/extractors/doc_extractor.py` clean
- `mypy src/invisible_seam/extractors/doc_extractor.py` clean
