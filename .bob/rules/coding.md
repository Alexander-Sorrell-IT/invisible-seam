# Coding Rules — INVISIBLE SEAM

## Python version
Python 3.11+. Use `match` statements where appropriate. Use `tomllib` (stdlib).

## Type hints
Every function signature must have full type hints. No `Any` unless unavoidable and commented.

## Docstrings
Every public function: one-line docstring. Format: "Does X. Returns Y."
No multi-paragraph docstrings on simple functions.

## Error handling
FAIL LOUD. Never swallow exceptions.
- Never: `except Exception: pass`
- Never: `except Exception: return None`
- Never: `dict.get(key, silent_default)` without the caller knowing the default is possible
- Always: raise with context — `raise ValueError(f"Missing required field '{key}' in {source}") from e`

## Imports
- stdlib first, third-party second, local third — separated by blank lines
- No wildcard imports (`from x import *`)

## Paths
Use `pathlib.Path` everywhere. No `os.path`. No hardcoded strings for paths.

## Constants
No magic strings or numbers inline. Define at module top or in a `constants.py`.

## Tests
- One test file per source module, mirroring the src layout
- Test names: `test_<what>_<condition>_<expected>`
- No mocking of the filesystem — use `tmp_path` fixture
- Every test must be able to run with `pytest tests/ -v` from the project root

## Output
The tool output format is sacred. Never change the seam output format without updating AGENTS.md.
No print statements in library code — use the report module only.
CLI may use `click.echo`. Library modules raise or return; they never print.
