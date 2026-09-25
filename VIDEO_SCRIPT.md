# Demo Video Script — INVISIBLE SEAM
# 3:00 exactly. Every second planned.

---

## [0:00–0:30] THE PAIN (no code yet — just the story)

**Narration (calm, direct):**

> "A new developer joins a team. They read the README.
> It says: 'This function never returns None. Always returns a list.'
> They build their feature on that contract.
> Three days later — production crash. NoneType has no attribute 'len'.
> The function has always returned None on an empty database.
> The README has always been wrong.
> Nobody knew. Because nobody had a tool that compared what the docs claim
> to what the code actually does."

**On screen:** Show README.md open. Highlight the line:
`"Never returns None — always returns a list."`
Then show `users.py`. Highlight: `return None`

---

## [0:30–0:45] THE TOOL — one command

**Narration:**

> "This is INVISIBLE SEAM. One command."

**On screen — type and run:**
```bash
seam scan demo_repo/
```

**Let the output roll. Don't skip it. Let the judges READ it.**

---

## [0:45–1:30] THE SEAMS APPEAR — walk through each one

**Narration as seams appear:**

> "SEAM 1 — FIXABLE. Docstring says raises ValueError. Code returns False.
> Binary. Proven. Check is written and run."

*(pause — let RESOLVED appear)*

> "SEAM 4 — FIXABLE. Annotation says list of strings.
> Function returns None on empty input.
> The README said it never does this. The annotation agreed. The code disagreed.
> One check. RESOLVED."

*(pause)*

> "SEAM 6 — PARADOX."

**Slow down here. This is the jaw-drop moment.**

> "The config schema marks 'api_key' as required.
> The code silently defaults to 'default_insecure_key' when it's missing.
> That's not a bug you fix by changing the code.
> That's a spec that contradicts itself.
> So instead of a check — the tool outputs one precise question for the human:
> Is api_key required, or is the default the contract?
> No guess. No summary. One question."

---

## [1:30–1:50] THE FIX — live

**Narration:**

> "Now fix the fixable ones."

**On screen — type and run:**
```bash
seam fix demo_repo/
```

> "Each FIXABLE seam gets patched. Then the same check runs again.
> CLOSED means: fixed, re-proven, done."

**Let CLOSED lines appear one by one.**

---

## [1:50–2:15] THE SELF-SCAN — the moment that breaks the brain

**Narration:**

> "Here's the part that matters most."

**On screen — type:**
```bash
seam scan src/
```

> "We just ran the tool on itself.
> It found seams in its own docstrings.
> The tool that hunts liars found a lie in its own code.
> That's not a demo gimmick. That's proof the doctrine works."

---

## [2:15–2:45] THE BOB USAGE — show the custom mode and skill

**Narration:**

> "Every part of this was built with IBM Bob 2.0.
> Not just code generation — architecture."

**On screen — show Bob IDE, open `.bob/seam_auditor_mode.yaml`**

> "A custom Seam Auditor mode. Bob operates under one law:
> never read more than the two files involved in one seam.
> That's the coin rule. That's also why the output is clean."

**Show `.bob/skills/seam-scan.md` briefly**

> "A reusable skill packages the full five-step pipeline.
> Drop it into any Python project and it runs the same way every time."

---

## [2:45–3:00] THE NUMBER + CLOSE

**On screen — show the final summary line from the demo scan:**
```
Found 8 seam(s): 6 FIXABLE (6 RESOLVED, 0 UNSOLVED) · 2 PARADOX
```

**Narration:**

> "8 seams. 6 proven. 2 turned into precise human questions.
> Zero summaries. Zero hedging. Zero 'this might be an issue.'
> Every verdict is something a check ran and decided.
> INVISIBLE SEAM."

**Fade.**

---

## Recording notes

- Terminal font: large. At least 18pt. Judges watch on small screens.
- Use a dark terminal. The rich colors (yellow FIXABLE, magenta PARADOX, green RESOLVED) need contrast.
- Do NOT speed up the scan output. Let it roll. The seams appearing one by one IS the demo.
- The self-scan moment at 1:50 — pause after you type the command. Let there be one second of silence before the output appears. That silence is the setup.
- No music. Voice only. Calm and direct.
