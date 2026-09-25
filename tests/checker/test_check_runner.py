from __future__ import annotations

from pathlib import Path

from invisible_seam.models import Claim, SeamCandidate, Seam
from invisible_seam.checker.check_runner import write_check, run_check


def _make_seam(tmp_path: Path) -> Seam:
    return Seam(
        id="S001",
        classification="FIXABLE",
        assertion_a="Function 'broken' return annotation: list[str]",
        source_a=tmp_path / "src" / "broken.py",
        line_a=1,
        assertion_b="Function 'broken' returns: None",
        source_b=tmp_path / "src" / "broken.py",
        line_b=3,
        check=None,
        verdict="CERTAIN",
        question=None,
    )


def test_write_check_sets_check_field(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "broken.py").write_text(
        "def broken(db: dict) -> list[str]:\n"
        "    if not db:\n"
        "        return None\n"
        "    return list(db.keys())\n"
    )
    seam = _make_seam(tmp_path)
    updated = write_check(seam, tmp_path)
    assert updated.check is not None
    assert "pytest" in updated.check


def test_check_file_is_created(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "broken.py").write_text(
        "def broken() -> list[str]:\n"
        "    return None\n"
    )
    seam = _make_seam(tmp_path)
    updated = write_check(seam, tmp_path)
    check_path = tmp_path / "tests" / "_seam_checks" / "seam_S001.py"
    assert check_path.exists()


def test_run_check_nonexistent_command_returns_unsolved(tmp_path: Path) -> None:
    seam = Seam(
        id="S999",
        classification="FIXABLE",
        assertion_a="test",
        source_a=tmp_path,
        line_a=1,
        assertion_b="test",
        source_b=tmp_path,
        line_b=1,
        check="nonexistent_command_xyz --flag",
        verdict="CERTAIN",
        question=None,
    )
    result = run_check(seam, tmp_path)
    assert result.verdict == "UNSOLVED"


def test_run_check_returns_resolved_on_valid_command(tmp_path: Path) -> None:
    seam = Seam(
        id="S998",
        classification="FIXABLE",
        assertion_a="test",
        source_a=tmp_path,
        line_a=1,
        assertion_b="test",
        source_b=tmp_path,
        line_b=1,
        check="python3 -c 'print(1)'",
        verdict="CERTAIN",
        question=None,
    )
    result = run_check(seam, tmp_path)
    assert result.verdict == "RESOLVED"
