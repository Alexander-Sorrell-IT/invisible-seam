from __future__ import annotations

from pathlib import Path

from invisible_seam.cli import main
from click.testing import CliRunner


def test_cli_scan_exits_zero(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("This function returns a list of items.\n")
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 0


def test_cli_fix_exits_zero(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["fix", str(tmp_path)])
    assert result.exit_code == 0


def test_cli_scan_no_claims(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "No claims found" in result.output
