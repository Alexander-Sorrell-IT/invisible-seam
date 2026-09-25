# T04 — Code Matcher + Seam Classifier

## Context files (use @file — do not explore)
- @AGENTS.md
- @.bob/rules/coding.md
- @.bob/rules/seam_rules.md
- @src/invisible_seam/models.py
- @src/invisible_seam/extractors/doc_extractor.py

## What to build

### 1. `src/invisible_seam/matchers/code_matcher.py`

```python
def match_claims(claims: list[Claim], repo_path: Path) -> list[SeamCandidate]:
    """Pairs each Claim with actual code behavior. Returns SeamCandidate list."""
```

**Matching strategy (deterministic, no LLM):**

For each `Claim` of type `"type-hint"`:
- The `source_file` is already the Python file. Use `ast.parse()` on it.
- Find the function at `source_line`.
- Compare the annotated return type to what the function *actually returns*:
  - If the annotation says `-> int` but all `return` statements return `str` literals or `len()` calls that are `str` — conflict.
  - If the annotation says `-> list[X]` but the function returns `None` in any branch — conflict.
  - Use AST node type inspection: `ast.Constant`, `ast.Call`, `ast.Name`, `ast.Attribute`
- Simple rule: if ANY `return` statement in the function body returns a type-incompatible literal or
  `None` when the annotation is non-optional — `conflict: True`.

For each `Claim` of type `"doc-code"` from README:
- Locate the function name mentioned in the claim text (simple word match).
- If a function is found: check whether its implementation contains a `raise` for claims that say
  "raises X" — if no `raise` of that exception exists in the body, `conflict: True`.
- If no function found: `conflict: False` (can't match — skip).

For each `Claim` of type `"config-fallback"`:
- Search all `*.py` files for `dict.get`, `.get(`, or `os.environ.get` calls where the key matches
  the required field name and a non-None default is passed as second arg — `conflict: True`.
- Search for `or` expressions like `config.get("api_key") or "default_key"` — `conflict: True`.

### 2. `src/invisible_seam/classifier/seam_classifier.py`

```python
def classify(candidate: SeamCandidate, claim: Claim) -> Seam:
    """Classifies a conflict as FIXABLE or PARADOX. Returns a Seam."""
```

**Classification rules:**
- `"type-hint"` conflicts → always `FIXABLE` (one side is objectively wrong)
- `"doc-code"` conflicts → `FIXABLE` if the code is wrong, `PARADOX` if docs are ambiguous
  (detect ambiguity: if the claim uses "might", "may", "optionally" → `PARADOX`)
- `"config-fallback"` conflicts → always `FIXABLE` (the fallback is the behavior, schema is the claim)

**Seam construction:**
- `assertion_a` = the claim text + "(source: {file}:{line})"
- `assertion_b` = the behavior text + "(source: {file}:{line})"  
- `check` = `None` (filled in T05)
- `verdict` = `"CERTAIN"` (seam exists, check pending)
- `question` = `None` for FIXABLE; for PARADOX = one sentence ending in `?`

## Tests
`tests/matchers/test_code_matcher.py`
`tests/classifier/test_seam_classifier.py`

Plant a `tmp_path` Python file with:
1. A function annotated `-> int` that returns a string literal — assert `conflict: True`
2. A function annotated `-> list[str]` that returns `None` — assert `conflict: True`
3. A function annotated `-> str` that always returns a string — assert `conflict: False`
4. A `dict.get("api_key", "default")` call — assert `conflict: True` for a config-fallback claim

## Done when
- `pytest tests/matchers/ tests/classifier/ -v` all pass
- `ruff check src/invisible_seam/matchers/ src/invisible_seam/classifier/` clean
- `mypy src/invisible_seam/matchers/ src/invisible_seam/classifier/` clean
