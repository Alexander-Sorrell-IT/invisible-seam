from __future__ import annotations

from pathlib import Path

from invisible_seam.models import Seam
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
