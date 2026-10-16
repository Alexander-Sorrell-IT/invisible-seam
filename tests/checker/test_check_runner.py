from __future__ import annotations

import dataclasses
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
    assert updated.check == "python tests/_seam_checks/seam_S001.py"


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


def _script_seam(tmp_path: Path, exit_code: int) -> Seam:
    script = tmp_path / "check.py"
    script.write_text(f"import sys\nprint('reason')\nsys.exit({exit_code})\n")
    return Seam(
        id="S997",
        classification="FIXABLE",
        assertion_a="test",
        source_a=tmp_path,
        line_a=1,
        assertion_b="test",
        source_b=tmp_path,
        line_b=1,
        check="python check.py",
        verdict="CERTAIN",
        question=None,
    )


def test_exit_1_is_resolved(tmp_path: Path) -> None:
    assert run_check(_script_seam(tmp_path, 1), tmp_path).verdict == "RESOLVED"


def test_exit_0_is_closed(tmp_path: Path) -> None:
    assert run_check(_script_seam(tmp_path, 0), tmp_path).verdict == "CLOSED"


def test_exit_2_is_unsolved_with_reason(tmp_path: Path) -> None:
    result = run_check(_script_seam(tmp_path, 2), tmp_path)
    assert result.verdict == "UNSOLVED"
    assert result.question == "reason"


def test_command_that_merely_runs_is_not_resolved(tmp_path: Path) -> None:
    """Regression: a check that runs without confirming anything must never be RESOLVED."""
    seam = dataclasses.replace(_script_seam(tmp_path, 0), check="python3 -c 'print(1)'")
    assert run_check(seam, tmp_path).verdict == "UNSOLVED"


def _src_repo(tmp_path: Path, body: str) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    mod = src / "loader.py"
    mod.write_text(body)
    return mod


def test_generated_check_imports_from_src_and_confirms(tmp_path: Path) -> None:
    """The generated check must import from src/ (the old checks all skipped on import)."""
    mod = _src_repo(
        tmp_path,
        "def load(config: dict) -> str:\n"
        '    """Raises KeyError if api_key is missing."""\n'
        "    return config.get('api_key', 'x')\n",
    )
    seam = Seam(
        id="S010",
        classification="FIXABLE",
        assertion_a="Raises KeyError if api_key is missing.",
        source_a=mod,
        line_a=1,
        assertion_b="Function 'load' does NOT raise KeyError — returns instead",
        source_b=mod,
        line_b=1,
        check=None,
        verdict="CERTAIN",
        question=None,
    )
    result = run_check(write_check(seam, tmp_path), tmp_path)
    assert result.verdict == "RESOLVED"


def test_generated_check_holds_when_claim_is_true(tmp_path: Path) -> None:
    mod = _src_repo(
        tmp_path,
        "def load(config: dict) -> str:\n"
        '    """Raises KeyError if api_key is missing."""\n'
        "    return config['api_key']\n",
    )
    seam = Seam(
        id="S011",
        classification="FIXABLE",
        assertion_a="Raises KeyError if api_key is missing.",
        source_a=mod,
        line_a=1,
        assertion_b="Function 'load' does NOT raise KeyError — returns instead",
        source_b=mod,
        line_b=1,
        check=None,
        verdict="CERTAIN",
        question=None,
    )
    assert run_check(write_check(seam, tmp_path), tmp_path).verdict == "CLOSED"


def test_generated_check_for_missing_function_is_unsolved(tmp_path: Path) -> None:
    mod = _src_repo(tmp_path, "def other() -> int:\n    return 1\n")
    seam = dataclasses.replace(
        _make_seam(tmp_path), assertion_a="Function 'gone' return annotation: list[str]",
        source_a=mod,
    )
    result = run_check(write_check(seam, tmp_path), tmp_path)
    assert result.verdict == "UNSOLVED"
    assert result.question is not None and "cannot import" in result.question


def test_check_on_unparseable_module_is_unsolved_not_confirmed(tmp_path: Path) -> None:
    """Regression: a crash inside a check must not exit 1 (which means CONFIRMED)."""
    mod = _src_repo(tmp_path, "def broken(db: dict) -> list[str]\n    return None\n")
    seam = dataclasses.replace(
        _make_seam(tmp_path), assertion_a="Function 'broken' return annotation: list[str]",
        source_a=mod,
    )
    result = run_check(write_check(seam, tmp_path), tmp_path)
    assert result.verdict == "UNSOLVED"
