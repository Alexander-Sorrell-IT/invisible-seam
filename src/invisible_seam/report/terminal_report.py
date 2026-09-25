from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.text import Text
from rich.rule import Rule

from invisible_seam.models import Seam

_console = Console()


def render_terminal(seams: list[Seam], console: Console | None = None) -> None:
    """Prints all seams to terminal using rich. Returns None."""
    con = console or _console

    for i, seam in enumerate(seams, start=1):
        # header color
        if seam.classification == "FIXABLE":
            header_style = "bold yellow"
        else:
            header_style = "bold magenta"

        verdict_str = ""
        if seam.classification == "FIXABLE":
            if seam.verdict == "RESOLVED":
                verdict_style = "bold green"
            elif seam.verdict == "CLOSED":
                verdict_style = "bold green"
            else:
                verdict_style = "bold red"
            verdict_str = seam.verdict

        con.print(Rule(style="dim white"))

        header = Text()
        header.append(f"SEAM #{i}  ", style=header_style)
        header.append(f"[{seam.classification}]", style=header_style)
        if verdict_str:
            header.append(f"  {' ' * max(0, 40 - len(f'SEAM #{i}  [{seam.classification}]'))}", style="")
            header.append(verdict_str, style=verdict_style)
        con.print(header)

        con.print(
            Text.assemble(
                ("Assertion A: ", "bold cyan"),
                (seam.assertion_a, "cyan"),
                ("  ", ""),
                (f"({seam.source_a.name}:{seam.line_a})", "dim cyan"),
            )
        )
        con.print(
            Text.assemble(
                ("Assertion B: ", "bold red"),
                (seam.assertion_b, "red"),
                ("  ", ""),
                (f"({seam.source_b.name}:{seam.line_b})", "dim red"),
            )
        )

        if seam.classification == "PARADOX" and seam.question:
            con.print(
                Text.assemble(
                    ("Question:    ", "bold magenta"),
                    (seam.question, "magenta"),
                )
            )
        elif seam.check:
            con.print(
                Text.assemble(
                    ("Check:       ", "dim white"),
                    (seam.check, "dim white"),
                )
            )
            con.print(
                Text.assemble(
                    ("Verdict:     ", "bold"),
                    (seam.verdict, verdict_style if verdict_str else "white"),
                )
            )

        con.print()

    # summary line
    fixable = [s for s in seams if s.classification == "FIXABLE"]
    paradoxes = [s for s in seams if s.classification == "PARADOX"]
    resolved = [s for s in fixable if s.verdict in ("RESOLVED", "CLOSED")]
    unsolved = [s for s in fixable if s.verdict == "UNSOLVED"]

    con.print(Rule(style="dim white"))
    con.print(
        Text.assemble(
            (f"Found {len(seams)} seam(s): ", "bold white"),
            (f"{len(fixable)} FIXABLE ", "yellow"),
            (f"({len(resolved)} RESOLVED, {len(unsolved)} UNSOLVED)", "dim yellow"),
            (" · ", "dim white"),
            (f"{len(paradoxes)} PARADOX", "magenta"),
        )
    )
