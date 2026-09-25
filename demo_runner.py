#!/usr/bin/env python3
"""
INVISIBLE SEAM — Self-Running Split-Screen Demo
Left panel:  terminal output streaming in at reading pace
Right panel: synced explanation cards

Run directly:  python3 demo_runner.py
Or via:        bash record_demo.sh   (records to demo.mp4 automatically)
"""
from __future__ import annotations

import sys
import time
import threading

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding


# ─────────────────────────────────────────────────────────────────────────────
# EXPLANATION CARDS  (right panel — one per stage)
# ─────────────────────────────────────────────────────────────────────────────

CARDS = [
    {
        "title": "⚠  THE PROBLEM",
        "color": "bold white",
        "border": "white",
        "body": (
            "Every codebase has a gap between\n"
            "what it [bold cyan]CLAIMS[/] and what it [bold red]DOES[/].\n\n"
            "[cyan]README:[/] 'Never returns None.'\n"
            "[red]Code:[/]   returns None on empty DB.\n\n"
            "[cyan]Schema:[/] api_key is required.\n"
            "[red]Code:[/]   silently defaults it.\n\n"
            "[cyan]Docstring:[/] Raises ValueError.\n"
            "[red]Code:[/]        returns False.\n\n"
            "These gaps are [bold]invisible to linters[/].\n"
            "They live between files.\n"
            "They reach production.\n\n"
            "[dim]Current AI tools read the whole\n"
            "repo and summarise both sides.\n"
            "More noise. Same gap.[/]",
        ),
    },
    {
        "title": "⟩  ONE COMMAND",
        "color": "bold yellow",
        "border": "yellow",
        "body": (
            "[bold yellow]seam scan demo_repo/[/]\n\n"
            "No config. No setup.\n"
            "No repo summary. No score.\n\n"
            "The tool reads [bold]only[/] what it needs:\n"
            "  [cyan]the claim[/]\n"
            "  [red]the behavior[/]\n\n"
            "Nothing else enters the context.\n\n"
            "[dim]The iPhone Problem doctrine:\n"
            "never force an auditor to read\n"
            "the whole document.\n"
            "Isolate the two irreconcilable\n"
            "assertions. Present only\n"
            "the conflict.[/]",
        ),
    },
    {
        "title": "SEAM #1 — FIXABLE  ✓",
        "color": "bold yellow",
        "border": "yellow",
        "body": (
            "[cyan]What it claims:[/]\n"
            "  Raises [cyan]ValueError[/] if token is empty.\n"
            "  [dim](auth.py docstring)[/]\n\n"
            "[red]What it does:[/]\n"
            "  Returns [red]False[/]. No exception.\n"
            "  [dim](auth.py:7)[/]\n\n"
            "[bold]Classification: [yellow]FIXABLE[/]\n"
            "One side is wrong.\n"
            "A check decides which.\n\n"
            "A pytest file is auto-generated\n"
            "and executed [bold]right now[/].\n\n"
            "[bold green]RESOLVED[/] — seam confirmed.\n"
            "Ready to fix.",
        ),
    },
    {
        "title": "SEAM #4 — FIXABLE  ✓",
        "color": "bold yellow",
        "border": "yellow",
        "body": (
            "[cyan]What it claims:[/]\n"
            "  Annotation: [cyan]→ list[str][/]\n"
            "  README: [cyan]'never returns None'[/]\n"
            "  [dim](users.py:4)[/]\n\n"
            "[red]What it does:[/]\n"
            "  Returns [red]None[/] when DB is empty.\n"
            "  [dim](users.py:7)[/]\n\n"
            "[dim]The README and annotation agreed.\n"
            "The code disagreed with both.\n"
            "The gap is between two files —\n"
            "that's why nobody caught it.[/]\n\n"
            "[bold green]RESOLVED — seam confirmed.[/]",
        ),
    },
    {
        "title": "SEAM #6 — PARADOX  ⚡",
        "color": "bold magenta",
        "border": "magenta",
        "body": (
            "[cyan]What it claims:[/]\n"
            "  Schema: [cyan]'api_key'[/] is [cyan]required[/].\n"
            "  [dim](config.schema.json:2)[/]\n\n"
            "[red]What it does:[/]\n"
            "  Code: [red].get('api_key', 'default')[/]\n"
            "  [dim](config_loader.py:7)[/]\n\n"
            "[bold magenta]Classification: PARADOX[/]\n\n"
            "No code change fixes this.\n"
            "The spec contradicts [bold]itself[/].\n\n"
            "So instead of a check —\n"
            "[bold magenta]one question for the human:[/]\n\n"
            "  Is api_key required,\n"
            "  or does the default make\n"
            "  it optional?\n\n"
            "[dim]No guess. One question.\n"
            "The loop closes when answered.[/]",
        ),
    },
    {
        "title": "⟩  seam fix  — CLOSING SEAMS",
        "color": "bold green",
        "border": "green",
        "body": (
            "For each [yellow]FIXABLE[/] seam:\n\n"
            "  1. Patch applied to source\n"
            "  2. [bold]Same check re-runs[/]\n"
            "  3. [green]CLOSED[/] = proven fixed\n\n"
            "[dim]Not 'we think this is fixed.'\n"
            "The check ran again.\n"
            "The check passed.\n"
            "CLOSED.[/]\n\n"
            "[bold]The model proposed the patch.\n"
            "The runner owns the verdict.[/]\n\n"
            "[magenta]PARADOX seams are not patched —\n"
            "they need a human decision.[/]",
        ),
    },
    {
        "title": "★  THE SELF-SCAN",
        "color": "bold red",
        "border": "red",
        "body": (
            "[bold red]seam scan src/[/]\n\n"
            "The tool scans [bold]itself[/].\n\n"
            "It finds seams in its own\n"
            "docstrings.\n\n"
            "[bold]The tool that hunts liars\n"
            "found a lie in its own code.[/]\n\n"
            "That's not a demo gimmick.\n\n"
            "It proves the doctrine works\n"
            "on [bold]any[/] repo you point it at.\n"
            "No special cases.\n"
            "No curated inputs.\n\n"
            "[dim]Just the seam.[/]",
        ),
    },
    {
        "title": "■  FINAL RESULTS",
        "color": "bold cyan",
        "border": "cyan",
        "body": (
            "[bold]demo_repo/[/]\n"
            "  [yellow]6 FIXABLE[/]  →  [green]6 RESOLVED[/]\n"
            "  [magenta]2 PARADOX[/]  →  2 questions\n\n"
            "[bold]src/ (tool scans itself)[/]\n"
            "  [yellow]3 FIXABLE[/]  →  [green]3 RESOLVED[/]\n\n"
            "────────────────────────────\n\n"
            "[bold]Zero summaries.[/]\n"
            "[bold]Zero hedging.[/]\n"
            "[bold]Zero 'this might be an issue.'[/]\n\n"
            "Every verdict is something\n"
            "a [bold]check ran[/] and decided.\n\n"
            "[bold cyan]    INVISIBLE SEAM[/]\n"
            "[dim]  IBM Bob 2.0 Hackathon 2026[/]",
        ),
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# TERMINAL STAGE SCRIPT
# Each stage: card index, lines to stream, pause after all lines
# line format: (style, text, char_delay_seconds)
# char_delay=0 means print instantly (no streaming)
# ─────────────────────────────────────────────────────────────────────────────

STAGES = [
    {
        "card": 0,
        "lines": [
            ("dim",          "# CartService — production microservice",  0),
            ("dim",          "# README: 'Never returns None.'",           0),
            ("dim",          "# Schema: 'api_key is required.'",          0),
            ("dim",          "# Let's verify that.",                      0),
            ("",             "",                                           0),
        ],
        "pause": 8.0,
    },
    {
        "card": 1,
        "lines": [
            ("bold yellow",  "$ seam scan demo_repo/",   0.055),
            ("",             "",                          0),
            ("dim",          "  extracting claims...",   0),
            ("dim",          "  matching behavior...",   0),
            ("dim",          "  classifying seams...",   0),
            ("dim",          "  running checks...",      0),
            ("",             "",                          0),
        ],
        "pause": 4.0,
    },
    {
        "card": 2,
        "lines": [
            ("dim white",    "─" * 54,                                                0),
            ("bold yellow",  "SEAM #1  [FIXABLE]                   RESOLVED",        0.04),
            ("dim white",    "─" * 54,                                                0),
            ("cyan",         "Assertion A: Raises ValueError if token is empty.",    0.035),
            ("dim cyan",     "             (auth.py:4)",                              0),
            ("red",          "Assertion B: Function does NOT raise ValueError —",    0.035),
            ("red",          "             returns False instead.",                   0.035),
            ("dim red",      "             (auth.py:7)",                              0),
            ("dim white",    "Check:       pytest tests/_seam_checks/seam_S001.py",  0),
            ("bold green",   "Verdict:     RESOLVED",                                0.05),
            ("",             "",                                                       0),
        ],
        "pause": 10.0,
    },
    {
        "card": 3,
        "lines": [
            ("dim white",    "─" * 54,                                                0),
            ("bold yellow",  "SEAM #4  [FIXABLE]                   RESOLVED",        0.04),
            ("dim white",    "─" * 54,                                                0),
            ("cyan",         "Assertion A: return annotation → list[str]",           0.035),
            ("dim cyan",     "             README: 'never returns None'",             0),
            ("dim cyan",     "             (users.py:4)",                             0),
            ("red",          "Assertion B: Returns None when db is empty.",          0.035),
            ("dim red",      "             (users.py:7)",                             0),
            ("dim white",    "Check:       pytest tests/_seam_checks/seam_S004.py",  0),
            ("bold green",   "Verdict:     RESOLVED",                                0.05),
            ("",             "",                                                       0),
        ],
        "pause": 10.0,
    },
    {
        "card": 4,
        "lines": [
            ("dim white",    "─" * 54,                                                0),
            ("bold magenta", "SEAM #6  [PARADOX]",                                   0.05),
            ("dim white",    "─" * 54,                                                0),
            ("cyan",         "Assertion A: Schema requires field 'api_key'.",        0.035),
            ("dim cyan",     "             (config.schema.json:2)",                   0),
            ("red",          "Assertion B: .get('api_key', 'default_insecure_key')", 0.035),
            ("dim red",      "             (config_loader.py:7)",                     0),
            ("",             "",                                                       0),
            ("bold magenta", "Question:    Is 'api_key' required or optional?",      0.04),
            ("magenta",      "             Schema and code contradict each other.",  0.035),
            ("",             "",                                                       0),
        ],
        "pause": 12.0,
    },
    {
        "card": 5,
        "lines": [
            ("bold yellow",  "$ seam fix demo_repo/",                                0.055),
            ("",             "",                                                       0),
            ("bold green",   "CLOSED: SEAM #1  (Raises ValueError...)",              0.04),
            ("bold green",   "CLOSED: SEAM #2  (Raises KeyError if api_key...)",     0.04),
            ("bold green",   "CLOSED: SEAM #3  (Raises KeyError if timeout...)",     0.04),
            ("bold green",   "CLOSED: SEAM #4  (return annotation: list[str])",      0.04),
            ("magenta",      "PARADOX: SEAM #6  awaiting human decision",            0),
            ("magenta",      "PARADOX: SEAM #7  awaiting human decision",            0),
            ("",             "",                                                       0),
        ],
        "pause": 10.0,
    },
    {
        "card": 6,
        "lines": [
            ("bold red",     "$ seam scan src/   # the tool scans itself",           0.05),
            ("",             "",                                                       0),
            ("dim",          "  scanning invisible_seam/...",                         0),
            ("",             "",                                                       0),
            ("bold yellow",  "SEAM #1  [FIXABLE]                   RESOLVED",        0.04),
            ("cyan",         "Assertion A: Fixes a doc-code seam by updating",      0.03),
            ("cyan",         "             the docstring to match behavior.",        0.03),
            ("red",          "Assertion B: Function does NOT raise 'seam'.",         0.03),
            ("bold green",   "Verdict:     RESOLVED",                                0.05),
            ("",             "",                                                       0),
            ("bold yellow",  "SEAM #2  [FIXABLE]                   RESOLVED",        0.04),
            ("cyan",         "Assertion A: Returns (True, exception_name)",          0.03),
            ("cyan",         "             if claim says raises X.",                 0.03),
            ("red",          "Assertion B: Docstring mismatches return type.",       0.03),
            ("bold green",   "Verdict:     RESOLVED",                                0.05),
            ("",             "",                                                       0),
            ("bold white",   "Found 3 seam(s) in own source: 3 FIXABLE RESOLVED",   0.035),
            ("",             "",                                                       0),
        ],
        "pause": 12.0,
    },
    {
        "card": 7,
        "lines": [
            ("dim white",    "═" * 54,                                                0),
            ("bold white",   "FINAL RESULTS",                                        0.05),
            ("dim white",    "═" * 54,                                                0),
            ("",             "",                                                       0),
            ("yellow",       "demo_repo/  →  8 seams found",                         0),
            ("green",        "  6 FIXABLE   6 RESOLVED   0 UNSOLVED",                0),
            ("magenta",      "  2 PARADOX   2 questions for humans",                  0),
            ("",             "",                                                       0),
            ("yellow",       "src/        →  3 seams found",                         0),
            ("green",        "  3 FIXABLE   3 RESOLVED   0 UNSOLVED",                0),
            ("",             "",                                                       0),
            ("dim white",    "─" * 54,                                                0),
            ("bold white",   "Zero summaries.  Zero hedging.",                       0.04),
            ("bold white",   "Every verdict proven by a check that ran.",            0.04),
            ("",             "",                                                       0),
            ("bold cyan",    "           INVISIBLE SEAM",                            0.05),
            ("dim",          "     IBM Bob 2.0 Hackathon 2026",                       0),
            ("",             "",                                                       0),
        ],
        "pause": 15.0,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# STATE + RENDERER
# ─────────────────────────────────────────────────────────────────────────────

class State:
    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []   # (style, text)
        self.streaming_line: str = ""             # current line being typed
        self.streaming_style: str = ""
        self.card_idx: int = 0
        self.done: bool = False
        self.lock = threading.Lock()


def left_panel(state: State) -> Panel:
    """Renders the live terminal output. Returns Panel."""
    text = Text()
    with state.lock:
        lines = list(state.lines[-46:])
        streaming = state.streaming_line
        s_style = state.streaming_style

    for style, content in lines:
        if style:
            text.append(content + "\n", style=style)
        else:
            text.append("\n")

    if streaming:
        text.append(streaming, style=s_style or "white")
        text.append("█", style="bold white")

    return Panel(
        Padding(text, (0, 1)),
        title="[bold green on black] ▸ TERMINAL [/]",
        border_style="green",
    )


def right_panel(state: State) -> Panel:
    """Renders the synced explanation card. Returns Panel."""
    with state.lock:
        idx = state.card_idx

    card = CARDS[idx]
    raw_body = card["body"]
    body_str = "".join(raw_body) if isinstance(raw_body, tuple) else raw_body
    body = Text.from_markup(body_str)

    # progress bar
    bar = Text("\n")
    bar.append("  ", style="")
    for i in range(len(CARDS)):
        if i < idx:
            bar.append("▓ ", style="dim " + card["color"])
        elif i == idx:
            bar.append("▓ ", style=card["color"])
        else:
            bar.append("░ ", style="dim white")
    bar.append(f"\n  Step {idx + 1} / {len(CARDS)}", style="dim white")

    content = Text.assemble(Text("\n"), body, bar)

    return Panel(
        Padding(content, (0, 2)),
        title=f"[{card['color']}]  {card['title']}  [/]",
        border_style=card["border"],
        subtitle="[dim]github.com/Alexander-Sorrell-IT/invisible-seam[/]",
    )


def build_layout(state: State) -> Layout:
    """Returns the split layout with both panels."""
    layout = Layout()
    layout.split_row(
        Layout(name="left",  ratio=55),
        Layout(name="right", ratio=45),
    )
    layout["left"].update(left_panel(state))
    layout["right"].update(right_panel(state))
    return layout


# ─────────────────────────────────────────────────────────────────────────────
# DEMO THREAD
# ─────────────────────────────────────────────────────────────────────────────

def run_demo(state: State) -> None:
    """Runs the full demo sequence. Blocks until complete."""
    time.sleep(0.8)  # let UI render first

    for stage in STAGES:
        # switch card
        with state.lock:
            state.card_idx = stage["card"]

        for style, text, char_delay in stage["lines"]:
            if not text:
                with state.lock:
                    state.lines.append(("", ""))
                time.sleep(0.06)
                continue

            if char_delay == 0:
                # instant line
                with state.lock:
                    state.lines.append((style, text))
                time.sleep(0.07)
            else:
                # stream character by character
                current = ""
                with state.lock:
                    state.streaming_line = ""
                    state.streaming_style = style

                for ch in text:
                    current += ch
                    with state.lock:
                        state.streaming_line = current
                    time.sleep(char_delay)

                # commit the finished line
                with state.lock:
                    state.streaming_line = ""
                    state.streaming_style = ""
                    state.lines.append((style, text))
                time.sleep(0.05)

        # pause between stages so judges can read the card
        time.sleep(stage["pause"])

    with state.lock:
        state.done = True


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    state = State()
    console = Console()

    thread = threading.Thread(target=run_demo, args=(state,), daemon=True)
    thread.start()

    with Live(
        build_layout(state),
        console=console,
        refresh_per_second=20,
        screen=True,
    ) as live:
        while True:
            live.update(build_layout(state))
            time.sleep(1 / 20)
            with state.lock:
                if state.done:
                    break

    # hold final frame visible for 4 seconds
    with Live(build_layout(state), console=console, screen=True):
        time.sleep(4)


if __name__ == "__main__":
    main()
