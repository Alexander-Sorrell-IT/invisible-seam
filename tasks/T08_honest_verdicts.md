# T08 — Honest verdicts (the check must own the verdict)

## Why
Right now every RESOLVED is fake:
- `check_runner.py:199-208` returns RESOLVED whenever the command *runs*, ignoring the result.
- All generated checks are SKIPPED: they `import config_loader`, but pytest runs from the repo root
  without `src/` on the path, so every import fails and the test skips.
- `seam fix` re-uses `run_check`, so any patch is marked CLOSED.
- `tests/checker/test_check_runner.py:71-86` asserts that `python3 -c 'print(1)'` is RESOLVED, which
  locks in the bug.

This breaks the core doctrine: "The model proposes; deterministic executed checks own the verdict."

## Files in scope (touch ONLY these)
- `src/invisible_seam/checker/check_runner.py`
- `src/invisible_seam/fixer/seam_fixer.py` (only the re-run block, lines 25-30)
- `src/invisible_seam/cli.py` (only the `scan` and `fix` loops)
- `src/invisible_seam/matchers/code_matcher.py` (only the two false positives below)
- `tests/checker/test_check_runner.py`
- `tests/fixer/test_seam_fixer.py`
- `tests/matchers/test_code_matcher.py`

Do not touch the report, extractor, classifier or demo files. Do not refactor anything else.

## 1. Checks become standalone scripts with an exit-code contract
Each generated check is a plain Python script, not a pytest test:
`tests/_seam_checks/seam_<ID>.py`, run as `python tests/_seam_checks/seam_<ID>.py`.

| Exit | Meaning |
|---|---|
| 0 | Claim A holds -> no seam |
| 1 | Claim A broken -> seam CONFIRMED |
| 2 | Inconclusive (import failed, couldn't build args, unexpected exception) |

- The script inserts `<repo>/src` (if it exists) and `<repo>` at the front of `sys.path` itself, so
  imports work no matter where it runs from.
- It prints exactly one line to stdout starting with `CONFIRMED:`, `HOLDS:` or `INCONCLUSIVE:`,
  followed by the reason.
- **It re-reads the current state at run time.** It uses `inspect.getdoc()` and
  `typing.get_type_hints()` on the live function and does not hardcode the claim text from scan time,
  so a fix to either side can close the seam.
- Arguments are built from annotations: `dict -> {}`, `str -> ""`, `list -> []`, anything else ->
  `None`. The current raises-check calls `func("")` on a `dict` parameter, which raises AttributeError
  for the wrong reason. That must not happen.
- Per check type:
  - **type-hint:** if the live return annotation allows None (or is `object` / missing) -> 0. Else call
    the function; if it returns None -> 1, otherwise -> 0.
  - **raises (doc-code):** if the live docstring no longer claims `raises <Exc>` -> 0. Else call; if
    it raises `<Exc>` -> 0; if it returns normally -> 1; any other exception -> 2.
  - **config-fallback:** call the loader with `{}`; if it raises KeyError/ValueError -> 0; if it
    returns -> 1; anything else -> 2.

## 2. `run_check` maps exit codes to verdicts
- 1 -> `RESOLVED` (seam confirmed by execution)
- 0 -> the candidate was a false alarm. Return the seam with verdict `CLOSED` and let the caller
  decide (see 3).
- 2, any other code, timeout, or FileNotFoundError -> `UNSOLVED`
- Run with `subprocess.run([sys.executable, path], cwd=repo_path, timeout=30, capture_output=True)`.
  Do not use `.split()` on a string command. Store the printed one-line reason in the seam's
  `question` field only if the verdict is UNSOLVED (so the report shows why).

## 3. CLI behavior
- `scan`: seams whose check exits 0 are dropped from the list. Print one line at the end:
  `N candidate(s) dismissed by their own check.` (only when N > 0).
- `fix`: only acts on RESOLVED seams. After patching it re-runs the **same** check. CLOSED only if
  the re-run exits 0. Exit 1 -> `STILL OPEN`, exit 2 -> `UNSOLVED`.

## 4. Two false positives in `code_matcher.py`
- **Parameter annotations** (currently produces "Parameter 'db' annotated as: dict" vs the function's
  *return* behavior): a parameter annotation claim must never be compared against return behavior.
  Skip parameter-annotation claims in `_match_type_hint_claim` (line 61).
- **Matching defaults** (currently flags schema `default: 30` vs code `.get('timeout', 30)`): in
  `_match_config_fallback_claim` (line 131), a claim that the field *has default X* is NOT a conflict
  when the code's default equals X. Compare values with `ast.literal_eval`. (The "required + has a
  default" paradox stays. That is a real seam.)

## Tests (must fail before the change, pass after)
- `test_check_runner.py`: replace the `print(1)` test with:
  - a script exiting 1 -> RESOLVED
  - a script exiting 0 -> CLOSED
  - a script exiting 2 -> UNSOLVED
  - a generated check against a tmp repo with `src/mod.py` whose loader silently defaults -> exits 1
    (proves the `sys.path` fix: the import succeeds)
- `test_seam_fixer.py`: a fix whose re-run still exits 1 -> STILL OPEN (not CLOSED); a real fix
  (`.get` -> `[...]`) -> CLOSED.
- `test_code_matcher.py`: parameter annotation -> no candidate; schema default 30 == code default
  30 -> no conflict.

## Done when
1. `python -m pytest -q` is all green.
2. On a fresh copy of `demo_repo/` (delete `tests/_seam_checks/` first), running each generated
   check by hand with `python tests/_seam_checks/seam_<ID>.py` prints CONFIRMED and exits 1 for every
   RESOLVED seam. None print INCONCLUSIVE.
3. `seam scan` on that copy shows no parameter-annotation seam and no "default 30 vs 30" seam; the
   two PARADOX seams remain.
4. `seam fix` on that copy then `seam scan` again: every seam `fix` reported CLOSED is gone.

## How to run this in Bob (coin rules)
- Open **`~/invisible-seam`** as the workspace in Bob IDE, not the home folder.
- Start a **new task**. Paste only: "Do tasks/T08_honest_verdicts.md", and attach this file plus the
  7 in-scope files with `@`.
- Code mode. No exploration of other files.
- When it's done: screenshot the task summary -> `bob_sessions/invisibleseam_task08_honest_verdicts_summary.png`.
