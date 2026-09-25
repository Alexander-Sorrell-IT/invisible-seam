# T07 — Seam Fixer + Demo Repo

## Context files (use @file — do not explore)
- @AGENTS.md
- @.bob/rules/coding.md
- @.bob/rules/seam_rules.md
- @src/invisible_seam/models.py
- @src/invisible_seam/checker/check_runner.py
- @src/invisible_seam/cli.py

## Part A — Seam Fixer

### `src/invisible_seam/fixer/seam_fixer.py`

```python
def fix_seam(seam: Seam, repo_path: Path) -> Seam:
    """Patches a RESOLVED FIXABLE seam. Re-runs the check. Returns updated Seam."""
```

**Rules:**
- Only fix seams with `classification == "FIXABLE"` and `verdict == "RESOLVED"`
- For `type-hint` seams: fix the TYPE ANNOTATION (not the code logic) — the annotation is wrong
  because the behavior is the truth. Update the annotation in the source file using `ast` + `astor`
  or direct string replacement at the known line.
- For `config-fallback` seams: remove the default from the `.get()` call — replace
  `config.get("key", default)` with `config["key"]` at the known line.
- For `doc-code` seams: update the README/docstring to match what the code actually does.
  Find the claim sentence in the file at `source_line` and replace it with the correct behavior.
- After patching: re-run `run_check(seam, repo_path)`
- If the re-run now exits 0 (test passes = behavior matches annotation): mark `verdict = "CLOSED"`
- If the re-run still fails: revert the patch (restore original line), set `verdict = "UNSOLVED"`
- Return the updated Seam

**Important:** Use `pathlib.Path.read_text()` and `Path.write_text()` for file edits.
Never use `subprocess` to edit files. Never use LLM for the actual text replacement.
The replacement is mechanical: find the exact line number, replace the exact text.

## Part B — Demo Repo

Build `demo_repo/` — a small fake Python project seeded with exactly 5 planted seams.
This is what runs in the demo video.

### Structure
```
demo_repo/
├── README.md              ← planted seam 1: doc-code
├── config.schema.json     ← planted seam 2: config-fallback (schema says required)
├── src/
│   ├── __init__.py
│   ├── users.py           ← planted seam 3: type-hint (annotated -> list[str], returns None)
│   ├── auth.py            ← planted seam 4: doc-code (docstring says raises ValueError, doesn't)
│   └── config_loader.py   ← planted seam 5: config-fallback (uses .get with silent default)
└── tests/
    └── test_users.py      ← a real passing test (shows the tool doesn't break existing tests)
```

### Planted seams (exact content)

**Seam 1 — doc-code (README)**
In `README.md` write: "The `get_active_users()` function returns a list of active user records."
In `src/users.py`, `get_active_users()` actually returns `None` when the DB is empty.

**Seam 2 — config-fallback (schema vs code)**
In `config.schema.json`:
```json
{"required": ["api_key"], "properties": {"api_key": {"type": "string"}}}
```
In `src/config_loader.py`:
```python
def load_api_key(config: dict) -> str:
    return config.get("api_key", "default_insecure_key")
```

**Seam 3 — type-hint**
In `src/users.py`:
```python
def get_active_users(db: dict) -> list[str]:
    if not db:
        return None  # seam: annotation says list[str], code returns None
    return list(db.keys())
```

**Seam 4 — doc-code (raises)**
In `src/auth.py`:
```python
def authenticate(token: str) -> bool:
    """Authenticates a token. Raises ValueError if token is empty."""
    if not token:
        return False  # seam: docstring says raises, code returns False
    return token.startswith("valid_")
```

**Seam 5 — config-fallback (paradox)**
In `config.schema.json` add:
```json
"timeout": {"type": "integer", "default": 30}
```
AND in required: `["api_key", "timeout"]`
This creates a PARADOX: schema says timeout is required AND has a default. One question decides it.

### `demo_repo/tests/test_users.py`
A real, passing test:
```python
def test_get_active_users_with_data():
    db = {"alice": 1, "bob": 2}
    result = get_active_users(db)
    assert result == ["alice", "bob"] or set(result) == {"alice", "bob"}
```

## Wire up `seam fix` CLI command
In `cli.py`, implement the `fix` subcommand:
```python
@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def fix(path):
    # 1. run full scan pipeline
    # 2. for each RESOLVED FIXABLE seam: call fix_seam
    # 3. print "CLOSED: SEAM #n" or "STILL OPEN: SEAM #n"
```

## Tests
`tests/fixer/test_seam_fixer.py`
- Use `tmp_path`, plant a config_loader.py with `.get("api_key", "default")`
- Run fix_seam on the matching seam
- Assert the file now contains `config["api_key"]` not `.get`

## Done when
- `seam scan demo_repo/` finds exactly 5 seams (3 FIXABLE, 2 PARADOX or 4/1 depending on classification)
- `seam fix demo_repo/` closes at least 2 FIXABLE seams and re-proves them
- `pytest demo_repo/tests/ -v` still passes after fixes
- `pytest tests/ -v` all pass
- `ruff check src/` clean
- `mypy src/` clean
