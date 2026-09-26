from __future__ import annotations

from pathlib import Path

from invisible_seam.models import Seam
from invisible_seam.checker.check_runner import write_check
from invisible_seam.fixer.seam_fixer import fix_seam


def test_fix_config_fallback_replaces_get(tmp_path: Path) -> None:
    loader = tmp_path / "loader.py"
    loader.write_text(
        "def load(config: dict) -> str:\n"
        "    return config.get('api_key', 'default_key')\n"
    )
    seam = Seam(
        id="S001",
        classification="FIXABLE",
        assertion_a="Config schema requires field 'api_key' to be present",
        source_a=tmp_path / "config.schema.json",
        line_a=2,
        assertion_b="Code calls .get('api_key', 'default_key') — silently uses default",
        source_b=loader,
        line_b=2,
        check="python3 -c 'print(1)'",
        verdict="RESOLVED",
        question=None,
    )
    result = fix_seam(seam, tmp_path)
    content = loader.read_text()
    assert ".get('api_key'" not in content or "['api_key']" in content


def test_fix_skips_paradox_seam(tmp_path: Path) -> None:
    seam = Seam(
        id="S002",
        classification="PARADOX",
        assertion_a="claim",
        source_a=tmp_path,
        line_a=1,
        assertion_b="behavior",
        source_b=tmp_path,
        line_b=1,
        check=None,
        verdict="CERTAIN",
        question="Is timeout required or optional?",
    )
    result = fix_seam(seam, tmp_path)
    assert result.classification == "PARADOX"
    assert result.verdict == "CERTAIN"


def _required_seam(mod: Path) -> Seam:
    return Seam(
        id="S020",
        classification="FIXABLE",
        assertion_a="Config field 'api_key' is marked required (comment)",
        source_a=mod,
        line_a=1,
        assertion_b="Code calls .get('api_key', 'x') — silently uses default when field is absent",
        source_b=mod,
        line_b=2,
        check=None,
        verdict="RESOLVED",
        question=None,
    )


def test_real_fix_is_closed_by_rerun(tmp_path: Path) -> None:
    mod = tmp_path / "loader.py"
    mod.write_text("def load(config: dict) -> str:\n    return config.get('api_key', 'x')\n")
    seam = write_check(_required_seam(mod), tmp_path)
    result = fix_seam(seam, tmp_path)
    assert "config['api_key']" in mod.read_text()
    assert result.verdict == "CLOSED"


def test_fix_that_does_not_help_stays_open(tmp_path: Path) -> None:
    """The fixer can't patch this line (default via `or`), so the re-run must still confirm it."""
    mod = tmp_path / "loader.py"
    mod.write_text("def load(config: dict) -> str:\n    return config.get('api_key') or 'x'\n")
    seam = write_check(_required_seam(mod), tmp_path)
    result = fix_seam(seam, tmp_path)
    assert result.verdict == "RESOLVED"  # still open: the check still confirms the seam


def test_doc_fix_edits_the_claimed_function_only(tmp_path: Path) -> None:
    mod = tmp_path / "loader.py"
    mod.write_text(
        "def a(config: dict) -> str:\n"
        '    """Raises KeyError if a is missing."""\n'
        "    return config['a']\n"
        "\n"
        "def b(config: dict) -> str:\n"
        '    """Raises KeyError if b is missing."""\n'
        "    return config.get('b', 'x')\n"
    )
    seam = Seam(
        id="S021",
        classification="FIXABLE",
        assertion_a="Raises KeyError if b is missing.",
        source_a=mod,
        line_a=5,
        assertion_b="Function 'b' does NOT raise KeyError — returns instead",
        source_b=mod,
        line_b=5,
        check=None,
        verdict="RESOLVED",
        question=None,
    )
    result = fix_seam(write_check(seam, tmp_path), tmp_path)
    text = mod.read_text()
    assert "Raises KeyError if a is missing." in text  # function a untouched
    assert "Raises KeyError if b is missing." not in text
    assert result.verdict == "CLOSED"


def test_type_hint_fix_keeps_file_valid_and_closes(tmp_path: Path) -> None:
    import ast

    src = tmp_path / "src"
    src.mkdir()
    mod = src / "users.py"
    mod.write_text(
        "def get_users(db: dict) -> list[str]:\n"
        "    if not db:\n"
        "        return None\n"
        "    return list(db.keys())\n"
    )
    seam = Seam(
        id="S030",
        classification="FIXABLE",
        assertion_a="Function 'get_users' return annotation: list[str]",
        source_a=mod,
        line_a=1,
        assertion_b="Function 'get_users' returns: list(db.keys()), None",
        source_b=mod,
        line_b=1,
        check=None,
        verdict="RESOLVED",
        question=None,
    )
    result = fix_seam(write_check(seam, tmp_path), tmp_path)
    text = mod.read_text()
    ast.parse(text)  # regression: the old fixer dropped the colon
    assert "-> list[str]:" in text  # contract kept; the code was fixed instead
    assert "return []" in text and "return None" not in text
    assert result.verdict == "CLOSED"


def test_default_mismatch_fix_sets_schema_default_and_closes(tmp_path: Path) -> None:
    mod = tmp_path / "loader.py"
    mod.write_text("def load(config: dict) -> int:\n    return config.get('timeout', 60)\n")
    seam = Seam(
        id="S040",
        classification="FIXABLE",
        assertion_a="Config field 'timeout' has default value '30'",
        source_a=tmp_path / "config.schema.json",
        line_a=1,
        assertion_b="Code calls .get('timeout', 60) — silently uses default when field is absent",
        source_b=mod,
        line_b=2,
        check=None,
        verdict="RESOLVED",
        question=None,
    )
    seam = write_check(seam, tmp_path)
    from invisible_seam.checker.check_runner import run_check
    assert run_check(seam, tmp_path).verdict == "RESOLVED"  # 60 != 30 confirmed by execution
    result = fix_seam(seam, tmp_path)
    assert "config.get('timeout', 30)" in mod.read_text()
    assert result.verdict == "CLOSED"


def test_type_hint_fix_widens_non_container_annotation(tmp_path: Path) -> None:
    import ast

    src = tmp_path / "src"
    src.mkdir()
    mod = src / "calc.py"
    mod.write_text(
        "def ratio(db: dict) -> int:\n"
        "    if not db:\n"
        "        return None\n"
        "    return len(db)\n"
    )
    seam = Seam(
        id="S031",
        classification="FIXABLE",
        assertion_a="Function 'ratio' return annotation: int",
        source_a=mod,
        line_a=1,
        assertion_b="Function 'ratio' returns: len(db), None",
        source_b=mod,
        line_b=1,
        check=None,
        verdict="RESOLVED",
        question=None,
    )
    result = fix_seam(write_check(seam, tmp_path), tmp_path)
    text = mod.read_text()
    ast.parse(text)
    assert "-> int | None:" in text  # no empty value for int, so widen honestly
    assert result.verdict == "CLOSED"


def test_readme_never_none_fixed_in_code_and_closed(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    mod = src / "users.py"
    mod.write_text(
        "def get_users(db: dict) -> list[str]:\n"
        "    if not db:\n"
        "        return None\n"
        "    return list(db)\n"
    )
    readme = tmp_path / "README.md"
    readme.write_text("### `get_users(db)`\n\nNever returns None.\n")
    seam = Seam(
        id="S032",
        classification="FIXABLE",
        assertion_a="Never returns None.",
        source_a=readme,
        line_a=3,
        assertion_b="Function 'get_users' returns None on at least one path",
        source_b=mod,
        line_b=1,
        check=None,
        verdict="CERTAIN",
        question=None,
    )
    from invisible_seam.checker.check_runner import run_check
    seam = run_check(write_check(seam, tmp_path), tmp_path)
    assert seam.verdict == "RESOLVED"  # the real function returned None
    result = fix_seam(seam, tmp_path)
    assert "return []" in mod.read_text()
    assert readme.read_text().count("Never returns None.") == 1  # docs untouched
    assert result.verdict == "CLOSED"


def test_type_hint_fix_after_code_fix_does_not_widen(tmp_path: Path) -> None:
    """Regression: once the code no longer returns None, the annotation stays list[str]."""
    src = tmp_path / "src"
    src.mkdir()
    mod = src / "users.py"
    mod.write_text(
        "def get_users(db: dict) -> list[str]:\n"
        "    if not db:\n"
        "        return []\n"
        "    return list(db)\n"
    )
    seam = Seam(
        id="S033",
        classification="FIXABLE",
        assertion_a="Function 'get_users' return annotation: list[str]",
        source_a=mod,
        line_a=1,
        assertion_b="Function 'get_users' returns: list(db), None",
        source_b=mod,
        line_b=1,
        check=None,
        verdict="RESOLVED",
        question=None,
    )
    result = fix_seam(write_check(seam, tmp_path), tmp_path)
    assert "-> list[str]:" in mod.read_text()
    assert result.verdict == "CLOSED"


def test_readme_raises_claim_with_backticks_is_fixed(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    mod = src / "loader.py"
    mod.write_text("def load(config: dict) -> str:\n    return config.get('k', 'x')\n")
    readme = tmp_path / "README.md"
    readme.write_text("### `load(config)`\n\nRaises `KeyError` if the key is missing.\n")
    seam = Seam(
        id="S034",
        classification="FIXABLE",
        assertion_a="Raises `KeyError` if the key is missing.",
        source_a=readme,
        line_a=3,
        assertion_b="Function 'load' does NOT raise KeyError — returns instead",
        source_b=mod,
        line_b=1,
        check=None,
        verdict="RESOLVED",
        question=None,
    )
    result = fix_seam(write_check(seam, tmp_path), tmp_path)
    assert "Raises `KeyError`" not in readme.read_text()
    assert result.verdict == "CLOSED"
