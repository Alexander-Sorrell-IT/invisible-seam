# T01 — Scaffold + pyproject.toml + CLI skeleton

## Context files (use @file — do not explore)
- @AGENTS.md
- @.bob/rules/coding.md

## What to build
1. `pyproject.toml` with:
   - `[project]` name=invisible-seam, version=0.1.0, requires-python=">=3.11"
   - dependencies: `click>=8.1`, `pyyaml>=6.0`, `rich>=13.0`
   - `[project.optional-dependencies]` dev: `pytest>=8.0`, `ruff>=0.4`, `mypy>=1.9`
   - `[project.scripts]` entry: `seam = "invisible_seam.cli:main"`

2. `src/invisible_seam/__init__.py` — empty, just `__version__ = "0.1.0"`

3. `src/invisible_seam/cli.py`:
   - `main()` is a `click.group()`
   - subcommand `scan`: takes `path: Path` argument, `--report` option (choices: terminal, html, default: terminal), `--output` option (Path, default: None)
   - subcommand `fix`: takes `path: Path` argument
   - Both subcommands print "NOT IMPLEMENTED YET" and exit 0 for now
   - No logic — just the CLI skeleton

4. `src/invisible_seam/models.py`:
   - Dataclasses (use `@dataclass(frozen=True)`):
     - `Claim(id: str, type: str, claim: str, source_file: Path, source_line: int)`
     - `SeamCandidate(claim_id: str, behavior: str, behavior_file: Path, behavior_line: int, conflict: bool)`
     - `Seam(id: str, classification: str, assertion_a: str, source_a: Path, line_a: int, assertion_b: str, source_b: Path, line_b: int, check: str | None, verdict: str, question: str | None)`
   - `SeamType` string literal: `"doc-code" | "type-hint" | "config-fallback" | "auth"`
   - `Classification` string literal: `"FIXABLE" | "PARADOX"`
   - `Verdict` string literal: `"RESOLVED" | "UNSOLVED" | "CERTAIN" | "KNOWN"`

5. `tests/__init__.py` — empty
6. `tests/test_cli.py` — test that `seam scan .` runs and exits 0 (use `click.testing.CliRunner`)
7. `tests/test_models.py` — test that all dataclasses are constructable and frozen

## Done when
- `pip install -e ".[dev]"` succeeds
- `seam scan .` runs and exits 0
- `seam fix .` runs and exits 0
- `pytest tests/ -v` passes all tests (zero failures)
- `ruff check src/` clean
- `mypy src/` clean
