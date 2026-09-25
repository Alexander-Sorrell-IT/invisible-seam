from __future__ import annotations

import ast
import re
from pathlib import Path

from invisible_seam.models import Claim

_BEHAVIORAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\breturns?\s+\w+", re.IGNORECASE),
    re.compile(r"\braises?\s+\w+", re.IGNORECASE),
    re.compile(r"\bdefaults?\s+to\b", re.IGNORECASE),
    re.compile(r"\brequires?\s+\w+", re.IGNORECASE),
    re.compile(r"\bmust\s+\w+", re.IGNORECASE),
]


def _is_behavioral(text: str) -> bool:
    """Returns True if text contains a behavioral promise."""
    return any(p.search(text) for p in _BEHAVIORAL_PATTERNS)


def _next_id(counter: list[int]) -> str:
    """Returns the next claim ID and increments the counter. Returns string like 'C001'."""
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def _extract_readme_claims(repo_path: Path, counter: list[int]) -> list[Claim]:
    """Extracts behavioral claims from README.md or README.rst. Returns list of Claim."""
    claims: list[Claim] = []
    for name in ("README.md", "README.rst", "readme.md"):
        readme = repo_path / name
        if readme.exists():
            for lineno, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), start=1):
                line = line.strip()
                if line and _is_behavioral(line):
                    claims.append(
                        Claim(
                            id=_next_id(counter),
                            type="doc-code",
                            claim=line,
                            source_file=readme,
                            source_line=lineno,
                        )
                    )
            break
    return claims


def _extract_python_claims(repo_path: Path, counter: list[int]) -> list[Claim]:
    """Extracts type-hint and docstring claims from all .py files. Returns list of Claim."""
    claims: list[Claim] = []
    seen: set[tuple[str, Path]] = set()

    for py_file in sorted(repo_path.rglob("*.py")):
        # skip auto-generated seam check files
        if "_seam_checks" in py_file.parts:
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # type-hint: return annotation
            if node.returns is not None:
                ann = ast.unparse(node.returns)
                if ann not in ("None", "Any"):
                    text = f"Function '{node.name}' return annotation: {ann}"
                    key = (text, py_file)
                    if key not in seen:
                        seen.add(key)
                        claims.append(
                            Claim(
                                id=_next_id(counter),
                                type="type-hint",
                                claim=text,
                                source_file=py_file,
                                source_line=node.lineno,
                            )
                        )

            # type-hint: parameter annotations
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                if arg.annotation is not None:
                    ann = ast.unparse(arg.annotation)
                    if ann not in ("None", "Any"):
                        text = f"Parameter '{arg.arg}' in '{node.name}' annotated as: {ann}"
                        key = (text, py_file)
                        if key not in seen:
                            seen.add(key)
                            claims.append(
                                Claim(
                                    id=_next_id(counter),
                                    type="type-hint",
                                    claim=text,
                                    source_file=py_file,
                                    source_line=arg.col_offset and node.lineno or node.lineno,
                                )
                            )

            # docstring behavioral claims
            docstring = ast.get_docstring(node)
            if docstring:
                for sentence in re.split(r"(?<=[.!?])\s+", docstring):
                    sentence = sentence.strip()
                    if sentence and _is_behavioral(sentence):
                        key = (sentence, py_file)
                        if key not in seen:
                            seen.add(key)
                            claims.append(
                                Claim(
                                    id=_next_id(counter),
                                    type="doc-code",
                                    claim=sentence,
                                    source_file=py_file,
                                    source_line=node.lineno,
                                )
                            )

    return claims


def extract_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """Scans repo_path for doc-code and type-hint claims. Returns list of Claim."""
    counter = [start_id]
    claims = _extract_readme_claims(repo_path, counter)
    claims += _extract_python_claims(repo_path, counter)
    return claims
