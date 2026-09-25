from __future__ import annotations

import ast
import dataclasses
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from invisible_seam.models import Seam

# Exit-code contract for every generated check script.
EXIT_HOLDS = 0  # claim A holds -> no seam
EXIT_CONFIRMED = 1  # claim A broken -> seam confirmed by execution
EXIT_INCONCLUSIVE = 2  # the check could not decide

_CHECK_PREFIX = "python "

# One template for all check kinds. Parameters are injected with repr() so the
# generated script is plain, auditable Python. It re-imports the target in a
# fresh process and re-reads docstrings/annotations at run time, so a fix to
# either side of the seam changes the outcome.
_TEMPLATE = '''\
"""Auto-generated seam check for {seam_id}.

Exit 0 = claim holds (no seam), 1 = seam confirmed, 2 = inconclusive.
"""
import importlib
import inspect
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO, REPO / "src"):
    if _p.is_dir():
        sys.path.insert(0, str(_p))

KIND = {kind!r}
MODULE = {module!r}
FUNC = {func!r}
EXC = {exc!r}
EXPECTED = {expected!r}


def _done(code, label, reason):
    print(f"{{label}}: {{reason}}")
    sys.exit(code)


def _ann_name(ann):
    if ann is inspect.Parameter.empty or ann is inspect.Signature.empty:
        return ""
    return ann if isinstance(ann, str) else getattr(ann, "__name__", repr(ann))


def _arg_for(ann):
    name = _ann_name(ann).replace(" ", "")
    if name.startswith("dict"):
        return {{}}
    if name == "str":
        return ""
    if name.startswith("list"):
        return []
    return None


def main():
    try:
        fn = getattr(importlib.import_module(MODULE), FUNC)
    except Exception as e:
        _done(2, "INCONCLUSIVE", f"cannot import {{MODULE}}.{{FUNC}}: {{e}}")

    sig = inspect.signature(fn)
    args = [
        _arg_for(p.annotation)
        for p in sig.parameters.values()
        if p.default is inspect.Parameter.empty
        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]

    if KIND == "type-hint":
        ann = _ann_name(sig.return_annotation).replace(" ", "")
        if ann in ("", "object", "Any") or "None" in ann or "Optional" in ann:
            _done(0, "HOLDS", f"{{FUNC}} return annotation {{ann or 'missing'}} allows None")
        try:
            result = fn(*args)
        except Exception as e:
            _done(2, "INCONCLUSIVE", f"{{FUNC}}{{tuple(args)}} raised {{type(e).__name__}}: {{e}}")
        if result is None:
            _done(1, "CONFIRMED", f"{{FUNC}}{{tuple(args)}} returned None, annotation says {{ann}}")
        _done(0, "HOLDS", f"{{FUNC}}{{tuple(args)}} returned {{type(result).__name__}}")

    if KIND == "raises":
        doc = inspect.getdoc(fn) or ""
        if not re.search(rf"\\braises?\\s+`?{{EXC}}\\b", doc, re.IGNORECASE):
            _done(0, "HOLDS", f"docstring of {{FUNC}} no longer claims it raises {{EXC}}")
        try:
            fn(*args)
        except Exception as e:
            if type(e).__name__ == EXC:
                _done(0, "HOLDS", f"{{FUNC}}{{tuple(args)}} raised {{EXC}} as documented")
            _done(2, "INCONCLUSIVE", f"{{FUNC}}{{tuple(args)}} raised {{type(e).__name__}}, not {{EXC}}")
        _done(1, "CONFIRMED", f"{{FUNC}}{{tuple(args)}} returned normally; docs say it raises {{EXC}}")

    if KIND == "config-required":
        try:
            value = fn({{}})
        except (KeyError, ValueError) as e:
            _done(0, "HOLDS", f"{{FUNC}}({{{{}}}}) raised {{type(e).__name__}}: field is enforced")
        except Exception as e:
            _done(2, "INCONCLUSIVE", f"{{FUNC}}({{{{}}}}) raised {{type(e).__name__}}: {{e}}")
        _done(1, "CONFIRMED", f"{{FUNC}}({{{{}}}}) returned {{value!r}} instead of failing")

    if KIND == "config-default":
        try:
            value = fn({{}})
        except Exception as e:
            _done(2, "INCONCLUSIVE", f"{{FUNC}}({{{{}}}}) raised {{type(e).__name__}}: {{e}}")
        if value == EXPECTED:
            _done(0, "HOLDS", f"{{FUNC}}({{{{}}}}) returned schema default {{EXPECTED!r}}")
        _done(1, "CONFIRMED", f"{{FUNC}}({{{{}}}}) returned {{value!r}}, schema default is {{EXPECTED!r}}")

    _done(2, "INCONCLUSIVE", f"unknown check kind {{KIND}}")


# Any crash is inconclusive. It must never fall through to exit 1 (= confirmed).
try:
    main()
except SystemExit:
    raise
except BaseException as e:
    _done(2, "INCONCLUSIVE", f"check crashed: {{type(e).__name__}}: {{e}}")
'''


def _checks_dir(repo_path: Path) -> Path:
    """Returns the directory for generated seam check files. Creates it if needed."""
    d = repo_path / "tests" / "_seam_checks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _module_for(source: Path, repo_path: Path) -> str:
    """Returns the dotted import path for source, relative to repo/src or the repo root."""
    for root in (repo_path / "src", repo_path):
        try:
            rel = source.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        return ".".join(rel.with_suffix("").parts)
    return source.stem


def _enclosing_function(source: Path, lineno: int) -> str | None:
    """Returns the name of the function whose body spans lineno in source."""
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno if node.end_lineno is not None else node.lineno
            if node.lineno <= lineno <= end:
                return node.name
    return None


def _check_params(seam: Seam, repo_path: Path) -> dict[str, object] | None:
    """Derives the template parameters for seam. Returns None if no check can be built."""
    a = seam.assertion_a
    m = re.search(r"Function '(\w+)' return annotation:", a)
    if m:
        return {
            "kind": "type-hint",
            "module": _module_for(seam.source_a, repo_path),
            "func": m.group(1),
            "exc": None,
            "expected": None,
        }

    m_cfg = re.search(r"Config (?:schema requires field|field) '(\w+)'", a)
    if m_cfg:
        func = _enclosing_function(seam.source_b, seam.line_b)
        if func is None:
            return None
        m_default = re.search(r"has default value '(.*)'$", a)
        if m_default:
            try:
                expected = ast.literal_eval(m_default.group(1))
            except (ValueError, SyntaxError):
                expected = m_default.group(1)
            kind = "config-default"
        else:
            expected = None
            kind = "config-required"
        return {
            "kind": kind,
            "module": _module_for(seam.source_b, repo_path),
            "func": func,
            "exc": None,
            "expected": expected,
        }

    m_exc = re.search(r"\braises?\s+`?(\w+)", a, re.IGNORECASE)
    m_func = re.search(r"Function '(\w+)'", seam.assertion_b)
    if m_exc and m_func:
        return {
            "kind": "raises",
            "module": _module_for(seam.source_b, repo_path),
            "func": m_func.group(1),
            "exc": m_exc.group(1),
            "expected": None,
        }
    return None


def write_check(seam: Seam, repo_path: Path) -> Seam:
    """Writes a deterministic check script for a FIXABLE seam. Returns updated Seam."""
    if seam.classification != "FIXABLE":
        return seam
    params = _check_params(seam, repo_path)
    if params is None:
        return dataclasses.replace(seam, check=None)
    check_file = _checks_dir(repo_path) / f"seam_{seam.id}.py"
    check_file.write_text(_TEMPLATE.format(seam_id=seam.id, **params), encoding="utf-8")
    return dataclasses.replace(
        seam, check=f"{_CHECK_PREFIX}{check_file.relative_to(repo_path).as_posix()}"
    )


def run_check(seam: Seam, repo_path: Path) -> Seam:
    """Executes the check. Exit 1 -> RESOLVED, 0 -> CLOSED, anything else -> UNSOLVED."""
    if seam.check is None or not seam.check.startswith(_CHECK_PREFIX):
        return dataclasses.replace(seam, verdict="UNSOLVED", question="no runnable check")

    script = repo_path / seam.check[len(_CHECK_PREFIX):]
    if not script.is_file():
        return dataclasses.replace(seam, verdict="UNSOLVED", question=f"missing check {script}")

    # Fresh bytecode cache per run: a fix that keeps the file size and mtime second
    # identical must not be masked by a stale __pycache__ entry.
    with tempfile.TemporaryDirectory(prefix="seam_pyc_") as pyc_dir:
        env = {**os.environ, "PYTHONPYCACHEPREFIX": pyc_dir, "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                cwd=repo_path,
                env=env,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return dataclasses.replace(seam, verdict="UNSOLVED", question="check timed out")

    reason = (result.stdout.strip().splitlines() or [result.stderr.strip()[-200:]])[-1]
    if result.returncode == EXIT_CONFIRMED:
        return dataclasses.replace(seam, verdict="RESOLVED")
    if result.returncode == EXIT_HOLDS:
        return dataclasses.replace(seam, verdict="CLOSED")
    return dataclasses.replace(seam, verdict="UNSOLVED", question=reason)
