# INVISIBLE SEAM

> *"Never force an auditor or model to read the whole document. Isolate the two irreconcilable assertions and present ONLY the conflict."*

A CLI tool that finds every place where a project's **claims** contradict its **behavior** — shows only the binary conflict — and proves each verdict by running something deterministic.

---

## The problem

In any real codebase, docs, docstrings, type hints, and config schemas slowly stop matching the code. A README says a function returns a list. The function returns `None`. A config schema marks a field required. The code silently uses a default. A docstring says it raises `ValueError`. It returns `False`.

Current AI tools make this worse: they read the whole repo, dump a summary, and sound confident about both sides. The result is cognitive paralysis — the noise hides the seam.

## The fix

INVISIBLE SEAM doesn't read the whole repo. It finds the seam — the exact point where what the project *claims* contradicts what it *does* — and presents only the binary conflict:

```
SEAM #1  [FIXABLE]                              RESOLVED
─────────────────────────────────────────────────────────
Assertion A: Returns a list of active users     (README.md:14)
Assertion B: Returns None when DB is empty      (src/users.py:42)
Check:       pytest tests/_seam_checks/seam_C001.py -v
Verdict:     RESOLVED — check failed (seam confirmed)
```

No summaries. No "this might be an issue." Every seam ends `RESOLVED` or explicitly `UNSOLVED`.

## Seam types
- **doc-code**: README/docs say X, code does Y
- **type-hint**: annotation promises X, function returns Y
- **config-fallback**: schema says required, code uses a silent default
- **paradox**: spec contradicts itself — outputs one precise question for the human

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# scan a repo — prints seam report to terminal
seam scan ./my_project

# generate HTML report
seam scan ./my_project --report html --output report.html

# auto-fix all provably FIXABLE seams and re-prove them
seam fix ./my_project
```

## Demo

```bash
seam scan demo_repo/
```

The `demo_repo/` is seeded with 5 planted seams. Watch them surface, get classified, get checked, and get fixed.

---

MIT License · Built with IBM Bob 2.0 · IBM Bob 2.0 Hackathon 2026
