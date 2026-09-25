# INVISIBLE SEAM — Project Context for Bob

## What this project is
A CLI tool that finds every place where a project's **claims** contradict its **behavior**.
Doctrine: "Never force an auditor or model to read the whole document.
Isolate the two irreconcilable assertions and present ONLY the conflict." — The iPhone Problem.

The model proposes. The deterministic runner owns the verdict.

## Output format (non-negotiable)
Every finding is a SEAM:
```
SEAM #n  [FIXABLE | PARADOX]
Assertion A: <what the doc/docstring/config/spec claims>  (source: file:line)
Assertion B: <what the code actually does>               (source: file:line)
Check:       <one shell command or pytest invocation that decides it>
Verdict:     RESOLVED | UNSOLVED
```
No summaries. No log dumps. No "this might be an issue." RESOLVED or UNSOLVED, nothing else.

## Seam types (v1 scope)
1. **doc-code**: README/docs say X, code does Y
2. **type-hint**: docstring/type hint promises X, runtime does Y
3. **config-fallback**: config schema marks field required, code silently uses a default
4. **auth**: API spec says auth required, endpoint responds without it (future)

## Seam classification
- **FIXABLE**: the impossibility is outside — one side is wrong. Patch the code or patch the doc.
- **PARADOX**: the impossibility is inside — the spec contradicts itself. No code change fixes it.
  Output: one precise question for the human. No verdict, no patch.

## Verdict states
- **KNOWN**: matches a seam pattern seen before
- **CERTAIN**: seam exists, check is pending execution
- **RESOLVED**: check ran and decided it
- **UNSOLVED**: honest failure — tool says it cannot decide

## Project layout
```
invisible-seam/
├── AGENTS.md                    ← this file
├── README.md
├── pyproject.toml
├── src/invisible_seam/
│   ├── __init__.py
│   ├── cli.py                   ← entry point: `seam scan <path>`
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── doc_extractor.py     ← reads README, docstrings, type hints → list[Claim]
│   │   ├── config_extractor.py  ← reads JSON/YAML schemas → list[Claim]
│   │   └── openapi_extractor.py ← reads OpenAPI specs → list[Claim]
│   ├── matchers/
│   │   ├── __init__.py
│   │   └── code_matcher.py      ← pairs Claim with actual code behavior → list[SeamCandidate]
│   ├── classifier/
│   │   ├── __init__.py
│   │   └── seam_classifier.py   ← classifies FIXABLE vs PARADOX
│   ├── checker/
│   │   ├── __init__.py
│   │   └── check_runner.py      ← generates + executes one deterministic check per seam
│   ├── fixer/
│   │   ├── __init__.py
│   │   └── seam_fixer.py        ← patches FIXABLE seams, re-runs check to prove closed
│   └── report/
│       ├── __init__.py
│       ├── terminal_report.py   ← colored terminal output
│       └── html_report.py       ← static HTML report for Application URL
├── tasks/                       ← Bob task specs (one file = one Bob session)
├── demo_repo/                   ← seeded sample repo with planted seams for the demo
├── bob_sessions/                ← PNG screenshots of each Bob task session summary
├── .bob/rules/
│   ├── coding.md
│   └── seam_rules.md
└── .bobignore
```

## Commands
```bash
# install
pip install -e ".[dev]"

# scan a repo
seam scan ./demo_repo

# scan with HTML report
seam scan ./demo_repo --report html --output report.html

# fix all FIXABLE seams
seam fix ./demo_repo

# run tests
pytest tests/ -v

# lint
ruff check src/ && mypy src/
```

## Conventions Bob must follow
- All source files: Python 3.11+, type hints on every function signature
- No silent fallbacks. If a value is missing, raise — never use `dict.get(k, default)` silently
- Every public function has a one-line docstring stating what it does and what it returns
- Fail loud: exceptions must propagate with context, never swallowed
- No hardcoded paths. Use pathlib.Path throughout
- Tests go in `tests/` mirroring `src/invisible_seam/`
- Each test file tests exactly one module

## What Bob must NOT do
- Never read the whole demo_repo to understand it — use @file context mentions on exact files
- Never summarize findings — output only the seam format above
- Never hedge ("this might be") — RESOLVED or UNSOLVED, nothing else
- Never add features not in the current task spec
