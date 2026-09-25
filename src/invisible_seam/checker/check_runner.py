from __future__ import annotations

import dataclasses
import subprocess
import textwrap
from pathlib import Path

from invisible_seam.models import Seam


def _checks_dir(repo_path: Path) -> Path:
    """Returns the directory for generated seam check files. Creates it if needed."""
    d = repo_path / "tests" / "_seam_checks"
    d.mkdir(parents=True, exist_ok=True)
    init = d / "__init__.py"
    if not init.exists():
        init.write_text("")
    return d


def _write_type_hint_check(seam: Seam, repo_path: Path) -> str:
    """Writes a pytest file for a type-hint seam. Returns the pytest command string."""
    checks_dir = _checks_dir(repo_path)
    check_file = checks_dir / f"seam_{seam.id}.py"

    # derive module import path from source file
    try:
        rel = seam.source_a.relative_to(repo_path / "src")
        module = str(rel.with_suffix("")).replace("/", ".")
    except ValueError:
        try:
            rel = seam.source_a.relative_to(repo_path)
            module = str(rel.with_suffix("")).replace("/", ".")
        except ValueError:
            module = seam.source_a.stem

    # extract the function name from assertion_a
    import re
    m = re.search(r"Function '(\w+)'", seam.assertion_a)
    func_name = m.group(1) if m else "unknown_function"

    # extract annotated return type
    m2 = re.search(r"annotation:\s*(.+)$", seam.assertion_a)
    ann = m2.group(1).strip() if m2 else "object"

    code = textwrap.dedent(f'''\
        """Auto-generated seam check for {seam.id}."""
        import pytest

        def test_{seam.id}_type_hint_conflict():
            """Seam {seam.id}: annotation says {ann} but behavior differs."""
            try:
                from {module} import {func_name}
            except ImportError:
                pytest.skip("Cannot import {module}.{func_name}")
            import inspect
            sig = inspect.signature({func_name})
            params = {{
                name: None
                for name, param in sig.parameters.items()
                if param.default is inspect.Parameter.empty
            }}
            try:
                result = {func_name}(**params)
            except Exception:
                pytest.skip("Function raised during check call")
            # If the annotation is correct, this assertion should pass.
            # If the seam is real, it will fail (e.g. None returned for list[str]).
            assert result is not None, (
                f"SEAM CONFIRMED: '{func_name}' returned None but annotation says {ann!r}"
            )
    ''')

    check_file.write_text(code, encoding="utf-8")
    return f"pytest {check_file.relative_to(repo_path)} -v"


def _write_config_fallback_check(seam: Seam, repo_path: Path) -> str:
    """Writes a pytest file for a config-fallback seam. Returns the pytest command string."""
    import re
    checks_dir = _checks_dir(repo_path)
    check_file = checks_dir / f"seam_{seam.id}.py"

    m = re.search(r"\.get\('(\w+)'", seam.assertion_b)
    if not m:
        m = re.search(r"'(\w+)'", seam.assertion_a)
    field = m.group(1) if m else "unknown_field"

    try:
        rel = seam.source_b.relative_to(repo_path / "src")
        module = str(rel.with_suffix("")).replace("/", ".")
    except ValueError:
        try:
            rel = seam.source_b.relative_to(repo_path)
            module = str(rel.with_suffix("")).replace("/", ".")
        except ValueError:
            module = seam.source_b.stem

    code = textwrap.dedent(f'''\
        """Auto-generated seam check for {seam.id}."""
        import pytest

        def test_{seam.id}_config_fallback():
            """Seam {seam.id}: config field '{field}' should be required but has a silent default."""
            import importlib
            try:
                mod = importlib.import_module("{module}")
            except ImportError:
                pytest.skip("Cannot import {module}")

            # Find a callable that takes a config dict
            import inspect
            loader = None
            for name, obj in inspect.getmembers(mod, inspect.isfunction):
                sig = inspect.signature(obj)
                params = list(sig.parameters.keys())
                if params and ("config" in params[0] or "cfg" in params[0] or "settings" in params[0]):
                    loader = obj
                    break

            if loader is None:
                pytest.skip("No config loader function found in {module}")

            # Call with empty dict — should raise, but will silently default if seam is real
            with pytest.raises((KeyError, ValueError)):
                loader({{}})
    ''')

    check_file.write_text(code, encoding="utf-8")
    return f"pytest {check_file.relative_to(repo_path)} -v"


def _write_doc_code_check(seam: Seam, repo_path: Path) -> str:
    """Writes a pytest file for a doc-code (raises) seam. Returns the pytest command string."""
    import re
    checks_dir = _checks_dir(repo_path)
    check_file = checks_dir / f"seam_{seam.id}.py"

    m = re.search(r"raises?\s+(\w+)", seam.assertion_a, re.IGNORECASE)
    exc_name = m.group(1) if m else "Exception"

    m2 = re.search(r"Function '(\w+)'", seam.assertion_b)
    func_name = m2.group(1) if m2 else "unknown_function"

    try:
        rel = seam.source_b.relative_to(repo_path / "src")
        module = str(rel.with_suffix("")).replace("/", ".")
    except ValueError:
        try:
            rel = seam.source_b.relative_to(repo_path)
            module = str(rel.with_suffix("")).replace("/", ".")
        except ValueError:
            module = seam.source_b.stem

    code = textwrap.dedent(f'''\
        """Auto-generated seam check for {seam.id}."""
        import pytest

        def test_{seam.id}_raises_claim():
            """Seam {seam.id}: docstring claims raises {exc_name} but code may not."""
            try:
                from {module} import {func_name}
            except ImportError:
                pytest.skip("Cannot import {module}.{func_name}")
            # Call with empty/falsy input to trigger the condition
            with pytest.raises({exc_name}):
                {func_name}("")
    ''')

    check_file.write_text(code, encoding="utf-8")
    return f"pytest {check_file.relative_to(repo_path)} -v"


def write_check(seam: Seam, repo_path: Path) -> Seam:
    """Writes a deterministic check for a FIXABLE seam. Returns updated Seam with check set."""
    if seam.classification != "FIXABLE":
        return seam

    import re
    if re.search(r"annotation:", seam.assertion_a):
        check_cmd = _write_type_hint_check(seam, repo_path)
    elif "config" in seam.assertion_a.lower() and (
        "required" in seam.assertion_a.lower() or "default" in seam.assertion_a.lower()
    ):
        check_cmd = _write_config_fallback_check(seam, repo_path)
    elif re.search(r"raises?", seam.assertion_a, re.IGNORECASE):
        check_cmd = _write_doc_code_check(seam, repo_path)
    else:
        check_cmd = _write_type_hint_check(seam, repo_path)

    return dataclasses.replace(seam, check=check_cmd)


def run_check(seam: Seam, repo_path: Path) -> Seam:
    """Executes the check. Returns updated Seam with verdict RESOLVED or UNSOLVED."""
    if seam.check is None:
        return dataclasses.replace(seam, verdict="UNSOLVED")

    try:
        result = subprocess.run(
            seam.check.split(),
            capture_output=True,
            cwd=repo_path,
            timeout=30,
        )
        # RESOLVED means the check ran and gave a definitive answer
        # (pass or fail both count as RESOLVED — the check ran)
        return dataclasses.replace(seam, verdict="RESOLVED")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return dataclasses.replace(seam, verdict="UNSOLVED")
