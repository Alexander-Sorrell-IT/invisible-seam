from __future__ import annotations

from pathlib import Path

import click

from invisible_seam import __version__


@click.group()
@click.version_option(__version__)
def main() -> None:
    """INVISIBLE SEAM — find where claims contradict behavior."""


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--report",
    type=click.Choice(["terminal", "html"]),
    default="terminal",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (required for --report html).",
)
def scan(path: Path, report: str, output: Path | None) -> None:
    """Scan PATH for seams where claims contradict behavior."""
    from invisible_seam.extractors.doc_extractor import extract_claims
    from invisible_seam.extractors.config_extractor import extract_config_claims
    from invisible_seam.matchers.code_matcher import match_claims
    from invisible_seam.classifier.seam_classifier import classify
    from invisible_seam.checker.check_runner import write_check, run_check
    from invisible_seam.report.terminal_report import render_terminal
    from invisible_seam.report.html_report import render_html

    claims = extract_claims(path) + extract_config_claims(path)
    if not claims:
        click.echo("No claims found.")
        return

    candidates = match_claims(claims, path)
    claim_map = {c.id: c for c in claims}

    seams = []
    for i, candidate in enumerate(candidates, start=1):
        if not candidate.conflict:
            continue
        claim = claim_map[candidate.claim_id]
        seam = classify(candidate, claim)
        # reassign canonical id
        seam = type(seam)(
            **{**seam.__dict__, "id": f"S{i:03d}"}  # type: ignore[arg-type]
        )
        if seam.classification == "FIXABLE":
            seam = write_check(seam, path)
            seam = run_check(seam, path)
        seams.append(seam)

    if not seams:
        click.echo("No seams found. All claims match behavior.")
        return

    if report == "terminal":
        render_terminal(seams)
    else:
        if output is None:
            raise click.UsageError("--output is required when --report html")
        render_html(seams, output)
        click.echo(f"Report written to {output}")


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def fix(path: Path) -> None:
    """Fix all RESOLVED FIXABLE seams in PATH and re-prove them."""
    from invisible_seam.extractors.doc_extractor import extract_claims
    from invisible_seam.extractors.config_extractor import extract_config_claims
    from invisible_seam.matchers.code_matcher import match_claims
    from invisible_seam.classifier.seam_classifier import classify
    from invisible_seam.checker.check_runner import write_check, run_check
    from invisible_seam.fixer.seam_fixer import fix_seam

    claims = extract_claims(path) + extract_config_claims(path)
    candidates = match_claims(claims, path)
    claim_map = {c.id: c for c in claims}

    for i, candidate in enumerate(candidates, start=1):
        if not candidate.conflict:
            continue
        claim = claim_map[candidate.claim_id]
        seam = classify(candidate, claim)
        if seam.classification != "FIXABLE":
            continue
        seam = write_check(seam, path)
        seam = run_check(seam, path)
        if seam.verdict != "RESOLVED":
            click.echo(f"SKIPPED SEAM #{i} — could not resolve check")
            continue
        seam = fix_seam(seam, path)
        if seam.verdict == "CLOSED":
            click.echo(f"CLOSED: SEAM #{i}  ({seam.assertion_a[:60]})")
        else:
            click.echo(f"STILL OPEN: SEAM #{i}  ({seam.assertion_a[:60]})")
