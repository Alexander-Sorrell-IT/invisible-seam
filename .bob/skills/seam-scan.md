---
name: seam-scan
description: >
  Runs a full INVISIBLE SEAM scan on a target repository. Extracts all claims from docs,
  docstrings, type hints, and config schemas. Pairs each claim with actual code behavior.
  Classifies each conflict as FIXABLE or PARADOX. Writes one check per FIXABLE seam and
  runs it. Outputs the seam report. No summaries. No dumps. Binary verdicts only.
---

# INVISIBLE SEAM Scan Procedure

## Step 1 — Claim Extraction (subagent: claim-extractor)

Spawn a subagent with ONLY the following files:
- README.md (if present)
- All docstrings from the target module (extract with `ast`, not by reading whole files)
- Config schema files (*.schema.json, *.yaml with a `required:` key)
- OpenAPI spec (openapi.yaml / swagger.json if present)

The subagent outputs a `claims.json` file:
```json
[
  {
    "id": "C001",
    "type": "doc-code | type-hint | config-fallback | auth",
    "claim": "<exact text of the claim>",
    "source_file": "path/to/file",
    "source_line": 42
  }
]
```

## Step 2 — Behavior Matching (parallel subagents, one per claim)

For each claim in `claims.json`, spawn a subagent with ONLY:
- The claim object
- The specific source file + function the claim references

The subagent outputs a `candidates.json` entry:
```json
{
  "claim_id": "C001",
  "behavior": "<what the code actually does>",
  "behavior_file": "path/to/impl.py",
  "behavior_line": 88,
  "conflict": true | false
}
```

Discard candidates where `conflict: false`. Only contradictions proceed.

## Step 3 — Seam Classification (Seam Auditor mode)

For each conflict, invoke the Seam Auditor with ONLY the claim + behavior pair.
The auditor outputs the seam in standard format and classifies FIXABLE or PARADOX.

## Step 4 — Check Generation and Execution

For FIXABLE seams:
- Bob writes one deterministic check (pytest call or shell command)
- The check runner executes it
- Verdict is set: RESOLVED or UNSOLVED

For PARADOX seams:
- Output the one question for the human
- No check is written. No verdict is set.

## Step 5 — Report

Output the full seam list in terminal format.
Optionally generate HTML report with `--report html`.

## Step 6 — Fix (optional, `seam fix` command)

For each RESOLVED FIXABLE seam:
- Bob patches the wrong side (code or doc, whichever the check proved wrong)
- Re-runs the same check
- Marks the seam CLOSED if the re-run passes

## Coin discipline
Each subagent call gets ONLY what it needs for its one claim.
Never pass the whole repo to any single call.
