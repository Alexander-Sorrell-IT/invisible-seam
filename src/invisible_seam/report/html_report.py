from __future__ import annotations

from pathlib import Path

from invisible_seam.models import Seam

_CSS = """
body { font-family: 'Segoe UI', monospace; background: #0d1117; color: #c9d1d9; margin: 2rem; }
h1 { color: #58a6ff; }
.summary { background: #161b22; border: 1px solid #30363d; padding: 1rem; border-radius: 6px; margin-bottom: 2rem; }
.seam { border: 1px solid #30363d; border-radius: 6px; margin-bottom: 1.5rem; padding: 1.2rem; background: #161b22; }
.seam.fixable { border-left: 4px solid #d29922; }
.seam.paradox { border-left: 4px solid #bc8cff; }
.seam-header { font-size: 1.1rem; font-weight: bold; margin-bottom: 0.8rem; }
.fixable .seam-header { color: #d29922; }
.paradox .seam-header { color: #bc8cff; }
.verdict-resolved { color: #3fb950; font-weight: bold; }
.verdict-unsolved { color: #f85149; font-weight: bold; }
.label { font-weight: bold; min-width: 110px; display: inline-block; }
.assert-a { color: #79c0ff; }
.assert-b { color: #f85149; }
.check { color: #8b949e; font-family: monospace; font-size: 0.9rem; }
.question { color: #bc8cff; }
.source { color: #8b949e; font-size: 0.85rem; margin-left: 0.5rem; }
.row { margin: 0.3rem 0; }
"""


def _verdict_class(verdict: str) -> str:
    """Returns CSS class for verdict badge. Returns string."""
    if verdict in ("RESOLVED", "CLOSED"):
        return "verdict-resolved"
    return "verdict-unsolved"


def render_html(seams: list[Seam], output_path: Path) -> None:
    """Writes a self-contained HTML report to output_path. Returns None."""
    fixable = [s for s in seams if s.classification == "FIXABLE"]
    paradoxes = [s for s in seams if s.classification == "PARADOX"]
    resolved = [s for s in fixable if s.verdict in ("RESOLVED", "CLOSED")]
    unsolved = [s for s in fixable if s.verdict == "UNSOLVED"]

    cards: list[str] = []
    for i, seam in enumerate(seams, start=1):
        css_class = seam.classification.lower()
        verdict_html = ""
        if seam.classification == "FIXABLE":
            vcls = _verdict_class(seam.verdict)
            verdict_html = f'<div class="row"><span class="label">Verdict:</span> <span class="{vcls}">{seam.verdict}</span></div>'

        check_or_question = ""
        if seam.classification == "PARADOX" and seam.question:
            check_or_question = f'<div class="row"><span class="label">Question:</span> <span class="question">{seam.question}</span></div>'
        elif seam.check:
            check_or_question = f'<div class="row"><span class="label">Check:</span> <span class="check">{seam.check}</span></div>'

        card = f"""
<div class="seam {css_class}">
  <div class="seam-header">SEAM #{i} &nbsp; [{seam.classification}]</div>
  <div class="row">
    <span class="label assert-a">Assertion A:</span>
    <span class="assert-a">{seam.assertion_a}</span>
    <span class="source">({seam.source_a.name}:{seam.line_a})</span>
  </div>
  <div class="row">
    <span class="label assert-b">Assertion B:</span>
    <span class="assert-b">{seam.assertion_b}</span>
    <span class="source">({seam.source_b.name}:{seam.line_b})</span>
  </div>
  {check_or_question}
  {verdict_html}
</div>"""
        cards.append(card)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>INVISIBLE SEAM Report</title>
<style>{_CSS}</style>
</head>
<body>
<h1>&#x1F50D; INVISIBLE SEAM Report</h1>
<div class="summary">
  <strong>{len(seams)} seam(s) found:</strong>
  &nbsp;
  <span style="color:#d29922">{len(fixable)} FIXABLE</span>
  ({len(resolved)} RESOLVED, {len(unsolved)} UNSOLVED)
  &nbsp;·&nbsp;
  <span style="color:#bc8cff">{len(paradoxes)} PARADOX</span>
</div>
{"".join(cards)}
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
