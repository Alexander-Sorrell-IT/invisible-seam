from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console

from invisible_seam.models import Seam
from invisible_seam.report.terminal_report import render_terminal


def _make_fixable_seam(tmp_path: Path) -> Seam:
    return Seam(
        id="S001",
        classification="FIXABLE",
        assertion_a="Function 'foo' return annotation: list[str]",
        source_a=tmp_path / "src.py",
        line_a=1,
        assertion_b="Function 'foo' returns: None",
        source_b=tmp_path / "src.py",
        line_b=5,
        check="pytest tests/",
        verdict="RESOLVED",
        question=None,
    )


def _make_paradox_seam(tmp_path: Path) -> Seam:
    return Seam(
        id="S002",
        classification="PARADOX",
        assertion_a="Config field 'timeout' has default value '30'",
        source_a=tmp_path / "config.schema.json",
        line_a=8,
        assertion_b="Schema marks 'timeout' as required",
        source_b=tmp_path / "config.schema.json",
        line_b=3,
        check=None,
        verdict="CERTAIN",
        question="Is 'timeout' required or does it default to 30?",
    )


def test_render_terminal_no_exception(tmp_path: Path) -> None:
    seams = [_make_fixable_seam(tmp_path), _make_paradox_seam(tmp_path)]
    buf = io.StringIO()
    con = Console(file=buf, highlight=False, markup=False)
    render_terminal(seams, console=con)
    output = buf.getvalue()
    assert "SEAM #1" in output
    assert "SEAM #2" in output


def test_render_terminal_shows_verdict(tmp_path: Path) -> None:
    seams = [_make_fixable_seam(tmp_path)]
    buf = io.StringIO()
    con = Console(file=buf, highlight=False, markup=False)
    render_terminal(seams, console=con)
    assert "RESOLVED" in buf.getvalue()


def test_render_terminal_shows_question(tmp_path: Path) -> None:
    seams = [_make_paradox_seam(tmp_path)]
    buf = io.StringIO()
    con = Console(file=buf, highlight=False, markup=False)
    render_terminal(seams, console=con)
    assert "timeout" in buf.getvalue()
