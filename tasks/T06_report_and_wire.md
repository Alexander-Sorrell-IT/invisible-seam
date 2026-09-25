# T06 — Report Generator + Wire up CLI

## Context files (use @file — do not explore)
- @AGENTS.md
- @.bob/rules/coding.md
- @.bob/rules/seam_rules.md
- @src/invisible_seam/models.py
- @src/invisible_seam/cli.py

## What to build

### 1. `src/invisible_seam/report/terminal_report.py`

```python
def render_terminal(seams: list[Seam]) -> None:
    """Prints all seams to terminal using rich. Returns None."""
```

Use `rich` for colored output. Format per seam (sacred — do not change):
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEAM #1  [FIXABLE]                    RESOLVED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Assertion A: Returns a list of users   (docs/README.md:14)
Assertion B: Returns None on empty DB  (src/app/users.py:42)
Check:       pytest tests/_seam_checks/seam_C001.py -v
Verdict:     RESOLVED — check failed (seam confirmed)
```

For PARADOX seams:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEAM #2  [PARADOX]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Assertion A: Config field 'timeout' has default 30s  (config.schema.json:8)
Assertion B: Schema marks 'timeout' as required      (config.schema.json:3)
Question:    Is 'timeout' required or does it default to 30s?
```

Color rules:
- FIXABLE header: yellow
- PARADOX header: magenta
- RESOLVED: green
- UNSOLVED: red
- Assertion A: cyan
- Assertion B: red
- Check: dim white
- Question: magenta

Summary line at end:
```
Scanned 47 claims → 5 seams found: 3 FIXABLE (2 RESOLVED, 1 UNSOLVED) · 2 PARADOX
```

### 2. `src/invisible_seam/report/html_report.py`

```python
def render_html(seams: list[Seam], output_path: Path) -> None:
    """Writes a self-contained HTML report to output_path. Returns None."""
```

- Single HTML file, no external dependencies (inline CSS only)
- Same content as terminal but in a table layout
- Include the summary at the top
- Each seam is a card with colored border (yellow=FIXABLE, magenta=PARADOX)
- Must open and render in a browser with no server

### 3. Wire up `src/invisible_seam/cli.py`

Replace the "NOT IMPLEMENTED YET" stubs with the full pipeline:

```python
@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--report", type=click.Choice(["terminal", "html"]), default="terminal")
@click.option("--output", type=click.Path(path_type=Path), default=None)
def scan(path, report, output):
    # 1. extract_claims(path) + extract_config_claims(path)
    # 2. match_claims(claims, path)
    # 3. classify each candidate
    # 4. write_check + run_check for FIXABLE seams
    # 5. render_terminal or render_html
```

## Tests
`tests/report/test_terminal_report.py`
- Build 2 fake Seams (1 FIXABLE RESOLVED, 1 PARADOX)
- Call `render_terminal` — assert no exception raised
- Capture output with `rich.console.Console(file=io.StringIO())`, assert "SEAM #1" in output

`tests/test_cli_integration.py`
- Use `CliRunner`, run `seam scan demo_repo/` against the demo repo
- Assert exit code 0
- Assert "SEAM" appears in output

## Done when
- `pytest tests/report/ tests/test_cli_integration.py -v` all pass
- `seam scan demo_repo/` runs end to end and prints seams
- `seam scan demo_repo/ --report html --output /tmp/test_report.html` creates the file
- `ruff check src/` clean
- `mypy src/` clean
