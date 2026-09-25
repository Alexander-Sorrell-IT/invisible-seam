# Seam Rules — The iPhone Problem Doctrine

## The law
Never force an auditor or model to read the whole document.
Isolate the two irreconcilable assertions and present ONLY the conflict.
The model proposes. The deterministic runner owns the verdict.

## Seam output format (sacred — never change)
```
SEAM #n  [FIXABLE | PARADOX]
Assertion A: <claim>   (source: file:line)
Assertion B: <behavior> (source: file:line)
Check:       <one command>
Verdict:     RESOLVED | UNSOLVED
```

## Classification rules
- FIXABLE: one side is provably wrong. Code or doc can be patched. Check decides which.
- PARADOX: the spec contradicts itself. No code change resolves it.
  A PARADOX seam outputs ONE precise question for the human instead of a check.

## Verdict rules
- RESOLVED: check executed and returned a definitive result
- UNSOLVED: check could not execute, or result was ambiguous — say so honestly
- NEVER output: "this might be", "possibly", "could indicate", "appears to"
- The tool either knows or it doesn't. If it doesn't: UNSOLVED.

## Context discipline (the coin rule)
Each Bob call gets ONLY the two files involved in one seam.
Never pass the whole repo. Never pass more than: the claim source + the behavior source.

## The paradox-to-question rule
A PARADOX seam is not a failure. It is unfinished logic waiting to be completed.
Output the one question that, if answered, closes the loop.
Example: "The schema marks `timeout` as required, but the docstring says it defaults to 30s.
Which is the contract: the schema or the docstring?"
