# T05 — Check Writer + Check Runner

## Context files (use @file — do not explore)
- @AGENTS.md
- @.bob/rules/coding.md
- @.bob/rules/seam_rules.md
- @src/invisible_seam/models.py
- @src/invisible_seam/classifier/seam_classifier.py

## What to build
`src/invisible_seam/checker/check_runner.py`

### Public API
```python
def write_check(seam: Seam, repo_path: Path) -> Seam:
    """Writes a deterministic check for a FIXABLE seam. Returns updated Seam with check set."""

def run_check(seam: Seam, repo_path: Path) -> Seam:
    """Executes the check. Returns updated Seam with verdict RESOLVED or UNSOLVED."""
```

### Check generation rules (deterministic — no LLM for this step)

**type-hint seams:**
Generate a pytest snippet that:
1. Imports the function from its module
2. Calls it with the simplest possible args (use `inspect.signature` to find params)
3. Asserts `isinstance(result, <annotated_type>)`

Write this snippet to `tests/_seam_checks/seam_{id}.py` (create dir if needed).
The `check` field becomes: `pytest tests/_seam_checks/seam_{id}.py -v`

**config-fallback seams:**
Generate a pytest snippet that:
1. Imports the module containing the `.get(key, default)` call
2. Calls the function WITHOUT providing the key in the config dict
3. Asserts the function raises `KeyError` or `ValueError` (i.e., it should fail loud)
   — if it doesn't raise (because of the fallback), the test FAILS → proving the seam

The `check` field becomes: `pytest tests/_seam_checks/seam_{id}.py -v`

**doc-code seams (raises claim):**
Generate a pytest snippet that:
1. Imports the function
2. Calls it with the input that should trigger the raise
3. Asserts `pytest.raises(<ExceptionType>)`

### Check execution
```python
def run_check(seam: Seam, repo_path: Path) -> Seam:
```
- Run the check command with `subprocess.run(check.split(), capture_output=True, cwd=repo_path, timeout=30)`
- If returncode == 0: verdict = `"RESOLVED"`, interpretation: check PASSED (behavior matches claim)
- If returncode != 0: verdict = `"RESOLVED"`, interpretation: check FAILED (seam confirmed)
- If timeout or FileNotFoundError: verdict = `"UNSOLVED"`
- Return a new `Seam` (frozen) with updated `verdict`

**Important:** RESOLVED means "the check ran and gave a definitive answer" — whether the check
passed or failed. UNSOLVED means "the check could not run at all."

### Tests
`tests/checker/test_check_runner.py`

1. Create a `tmp_path` repo with a function annotated `-> int` that returns `"hello"`.
2. Run `write_check` on the seam, assert `seam.check` is set and the file exists.
3. Run `run_check`, assert verdict is `"RESOLVED"`.
4. Create a seam with a check command that doesn't exist (`nonexistent_cmd`), assert verdict is `"UNSOLVED"`.

## Done when
- `pytest tests/checker/ -v` all pass
- `ruff check src/invisible_seam/checker/` clean
- `mypy src/invisible_seam/checker/` clean
