# Submission Statements

## Problem & Solution Statement (≤500 words)

Every codebase has a growing gap between what it claims and what it does. A README says a function returns a list of users. The code returns None when the database is empty. A config schema marks a field as required. The loader silently uses a hardcoded default. A docstring promises a ValueError on bad input. The function returns False.

These are not style issues. They are bugs waiting for a new developer to trust the wrong side of the gap. And they are nearly invisible because the docs and the code live in different files, are read at different times, and no existing tool treats them as a binary contradiction.

Current AI tools make the problem worse. They read the entire repository, produce a summary, and sound confident about both sides. The result is cognitive overload — a wall of text that buries the two sentences that actually disagree.

INVISIBLE SEAM starts from a different axiom: **never force an auditor to read the whole document. Isolate the two irreconcilable assertions and present only the conflict.**

The tool scans a Python project and finds every place where a claim — in a README, docstring, type annotation, or config schema — contradicts the actual code behavior. It presents each finding as a binary seam:

```
SEAM #1  [FIXABLE]                              RESOLVED
Assertion A: Returns a list of active users     (README.md:14)
Assertion B: Returns None when DB is empty      (src/users.py:42)
Check:       pytest tests/_seam_checks/seam_C001.py -v
Verdict:     RESOLVED — seam confirmed
```

No summaries. No hedging. Every seam ends RESOLVED or explicitly UNSOLVED.

The tool classifies each seam as **FIXABLE** (one side is wrong — patch the code or the doc) or **PARADOX** (the spec contradicts itself — no code change resolves it, so the tool outputs the one precise question that closes the loop). It then auto-fixes provably FIXABLE seams and re-runs the same check to prove they are closed.

The impact is measurable: a new developer following a wrong README wastes hours. A silent config fallback reaches production unnoticed. INVISIBLE SEAM surfaces both in seconds, proves them with a deterministic test, and closes them before review.

---

## IBM Bob Usage Statement (≤500 words)

IBM Bob 2.0 is not a code assistant in this project — it is the engine that applies the iPhone Problem doctrine to its own workflow.

**Architecture (Agent mode + subagents + parallel tasks):**
Bob was used with a custom "Seam Auditor" mode — a specialized persona that refuses to read whole files and refuses to hedge. Every Bob call received exactly two inputs: the claim source and the behavior source. Nothing else. This kept each session coin-efficient and hallucination-free because there was no ambient noise to misread.

The scan pipeline uses subagents: a claim-extractor subagent reads only the README, docstrings, and schemas. Parallel per-claim subagents pair each claim with its corresponding code in isolation. The Seam Auditor mode classifies each conflict and writes the check. A deterministic runner — not Bob — executes the check and owns the verdict.

**Document understanding:** The claim-extractor subagent is a direct application of Bob's document understanding capability — extracting structured behavioral promises from unstructured text (README sentences, docstrings) and typed metadata (annotations, JSON Schema).

**Custom skill:** A reusable `seam-scan` skill packages the full five-step pipeline so it can be dropped into any Python project and run identically, without re-explaining the procedure in a new context.

**Custom rules:** Project-level rules in `.bob/rules/` enforced fail-loud coding (no silent fallbacks, no swallowed exceptions, no hedging output) across every Bob task. Bob never added a `dict.get(k, default)` because the rules explicitly forbid it — the tool that hunts silent fallbacks cannot itself contain one.

**Task discipline:** Each Bob task received a pre-written spec file with exact file names, function signatures, acceptance criteria, and "done when" tests. Bob never explored the repo. Every coin went to building, not discovering.

The result is a project where the doctrine that inspired the tool also governed how the tool was built.
