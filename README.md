# INVISIBLE SEAM

> *"Never force an auditor to read the whole document. Isolate the two irreconcilable assertions and present only the conflict."*

**A tool that finds every place where a project's claims contradict its behavior — and proves each verdict by running something.**

No summaries. No scores. No "this might be an issue."  
Every finding is a binary conflict. Every verdict is proven by a check that ran.

---

## What it looks like

```
────────────────────────────────────────────────────────────
SEAM #1  [FIXABLE]                              RESOLVED
────────────────────────────────────────────────────────────
Assertion A: Never returns None — always returns a list.  (README.md:13)
Assertion B: Function returns None when db is empty.      (users.py:7)
Check:       pytest tests/_seam_checks/seam_S001.py -v
Verdict:     RESOLVED — seam confirmed

────────────────────────────────────────────────────────────
SEAM #2  [PARADOX]
────────────────────────────────────────────────────────────
Assertion A: Config schema requires field 'timeout'.      (config.schema.json:2)
Assertion B: Code calls .get('timeout', 30) — silent default.  (config_loader.py:14)
Question:    Is 'timeout' required or does it default to 30?
             The schema and the code contradict each other.
```

That is the entire output. Not a report. Not a summary. Just the seam.

---

## The problem

Every codebase has a gap between what it **claims** and what it **does**.

A README says a function never returns `None`. The function returns `None` when the database is empty. A config schema marks a field as required. The loader silently uses a hardcoded default. A docstring promises a `ValueError` on bad input. The code returns `False`.

These gaps are invisible to linters. They're invisible to static analysis. They live in the space between files — between what the doc says and what the code does.

A new developer reads the README. They trust it. They build on it. Three days later something breaks in production and nobody can explain why, because the bug was in the gap — the seam — between the documentation and the reality.

**Current AI tools make this worse.** They read the entire repo, produce a summary, and sound confident about both sides. The result is more noise in a system already drowning in noise.

---

## The solution

INVISIBLE SEAM applies one rule: **never read more than the conflict.**

For every contradiction it finds, it shows you exactly two things — the claim and the behavior — with their precise file and line numbers. Then it writes one deterministic check and runs it. The check decides the verdict. Not the model. The check.

**The model proposes. The runner owns the verdict.**

---

## Seam types

| Type | What it catches |
|---|---|
| `doc-code` | README or docstring says X, code does Y |
| `type-hint` | Annotation promises `list[str]`, function returns `None` |
| `config-fallback` | Schema marks field required, code silently uses a default |
| `paradox` | The spec contradicts **itself** — outputs one precise question for a human |

## Verdict states

| Verdict | Meaning |
|---|---|
| `RESOLVED` | Check ran. Seam confirmed or cleared. |
| `UNSOLVED` | Check could not run. Tool says so honestly. |
| `CLOSED` | Was RESOLVED, then fixed and re-proven clean. |
| `PARADOX` | No code change can fix it. Needs a human decision. |

---

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# find all seams in a project
seam scan ./my_project

# generate an HTML report
seam scan ./my_project --report html --output report.html

# auto-fix all provably FIXABLE seams and re-prove them
seam fix ./my_project
```

## Try it on the demo repo

```bash
# 8 planted seams — 6 FIXABLE, 2 PARADOX
seam scan demo_repo/

# fix the fixable ones and watch them close
seam fix demo_repo/

# the tool scans itself — finds seams in its own docstrings
seam scan src/
```

That last one is the point. **The tool that hunts seams has seams.** It finds them. It proves them. It closes them.

---

## Built from a doctrine

Every design decision in this tool comes from a single doctrine: **The iPhone Problem**.

> When the machine breaks, do not show the whole world.  
> Surface only the binary contradiction.  
> The model proposes. Deterministic executed checks own the verdict.

The classification system (FIXABLE vs PARADOX) comes from the distinction between problems where the impossibility is **outside** the spec (one side is wrong — fixable) versus problems where the impossibility is **inside** the spec (it contradicts itself — paradox, requires human resolution).

The verdict states (RESOLVED / UNSOLVED / CERTAIN / KNOWN) map to four observed cognitive modes for how problems actually get solved.

The no-hedging rule (RESOLVED or UNSOLVED, never "this might be") comes from the axiom that the only way to avoid judgment is to stop moving — and a tool that hedges is a tool that stopped moving.

---

## Architecture

```
invisible-seam/
├── src/invisible_seam/
│   ├── cli.py                   ← entry point: seam scan / seam fix
│   ├── models.py                ← Claim, SeamCandidate, Seam (frozen dataclasses)
│   ├── extractors/
│   │   ├── doc_extractor.py     ← README + docstring + type-hint claims
│   │   └── config_extractor.py  ← JSON Schema + YAML config claims
│   ├── matchers/
│   │   └── code_matcher.py      ← pairs each claim with actual code behavior
│   ├── classifier/
│   │   └── seam_classifier.py   ← FIXABLE vs PARADOX
│   ├── checker/
│   │   └── check_runner.py      ← writes + runs one deterministic check per seam
│   ├── fixer/
│   │   └── seam_fixer.py        ← patches FIXABLE seams, re-proves them
│   └── report/
│       ├── terminal_report.py   ← rich colored terminal output
│       └── html_report.py       ← self-contained HTML report
├── demo_repo/                   ← sample repo with 8 planted seams
├── tests/                       ← 30 passing tests
└── .bob/
    ├── rules/                   ← coding.md + seam_rules.md
    ├── seam_auditor_mode.yaml   ← custom Bob mode
    └── skills/seam-scan.md      ← reusable Bob skill
```

---

MIT License · Built with IBM Bob 2.0 · [Live Report](https://alexander-sorrell-it.github.io/invisible-seam/) · IBM Bob 2.0 Hackathon 2026
