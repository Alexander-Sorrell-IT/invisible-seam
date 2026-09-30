from __future__ import annotations

import ast
import re
from pathlib import Path

from invisible_seam.models import Claim

# ── Solidity / Cairo behavioral patterns ─────────────────────────────────────
# NatSpec tags that carry behavioral promises worth checking
_SOL_BEHAVIORAL_TAGS = re.compile(
    r'@(?:notice|dev|param|return)\s+(.+)',
    re.IGNORECASE,
)
# Inline require/revert statements — ground truth of what the code enforces
_SOL_REQUIRE = re.compile(
    r'\b(?:require|revert)\s*\(([^;]{5,120})',
)
# Modifiers applied to a function — claimed access control
_SOL_MODIFIER = re.compile(
    r'function\s+(\w+)\s*\([^)]*\)[^{]*\b(onlyOwner|onlyRole|whenNotPaused|nonReentrant|onlyAdmin|authorized|protected)\b',
    re.IGNORECASE,
)
# Cairo #[doc] and /// doc comments
_CAIRO_DOC = re.compile(r'(?://[/!]\s*|#\[doc\s*=\s*")(.+?)(?:")?$', re.MULTILINE)

_BEHAVIORAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\breturns?\s+\w+", re.IGNORECASE),
    re.compile(r"\braises?\s+`?\w+", re.IGNORECASE),
    re.compile(r"\bdefaults?\s+to\b", re.IGNORECASE),
    re.compile(r"\brequires?\s+\w+", re.IGNORECASE),
    re.compile(r"\bmust\s+\w+", re.IGNORECASE),
]


_HEADING_FUNC = re.compile(r"`(\w+)\(")


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
            subject: str | None = None
            for lineno, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), start=1):
                line = line.strip()
                if line.startswith("#"):
                    # a heading like "### `load_api_key(config)`" names the function
                    # the following lines describe; any other heading ends that section
                    m = _HEADING_FUNC.search(line)
                    subject = m.group(1) if m else None
                    continue
                if line and _is_behavioral(line):
                    claims.append(
                        Claim(
                            id=_next_id(counter),
                            type="doc-code",
                            claim=line,
                            source_file=readme,
                            source_line=lineno,
                            subject=subject,
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


# Solidity function declaration — used to track current function context
_SOL_FUNC_DEF = re.compile(
    r'^\s*function\s+(\w+)\s*\(',
)


def _extract_solidity_claims(repo_path: Path, counter: list[int]) -> list[Claim]:
    """
    Extract behavioral claims from Solidity (.sol) files via NatSpec and require() statements.

    - NatSpec @notice / @dev lines = what the contract CLAIMS (subject = nearest function)
    - require() / revert() = what the code ACTUALLY enforces (subject = enclosing function)
    - Modifier on function signature = claimed access control (subject = function name)

    subject is set on every claim so the solidity_matcher can find the function body.
    """
    claims: list[Claim] = []
    seen: set[tuple] = set()

    for sol_file in sorted(repo_path.rglob("*.sol")):
        try:
            lines = sol_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        current_func: str | None = None   # tracks nearest enclosing function name
        pending_natspec: list[tuple[str, int]] = []  # (text, lineno) waiting for func

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Track current function context
            fd = _SOL_FUNC_DEF.match(line)
            if fd:
                current_func = fd.group(1)
                # Flush pending NatSpec claims — now we know the function name
                for (text, nlineno) in pending_natspec:
                    key = (text, sol_file)
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter),
                            type="doc-code",
                            claim=text,
                            source_file=sol_file,
                            source_line=nlineno,
                            subject=current_func,
                        ))
                pending_natspec = []
                continue

            # NatSpec behavioral comment — queue until we see the function name
            m = _SOL_BEHAVIORAL_TAGS.search(stripped)
            if m:
                text = m.group(1).strip()
                if text and len(text) > 8:
                    if current_func:
                        key = (text, sol_file)
                        if key not in seen:
                            seen.add(key)
                            claims.append(Claim(
                                id=_next_id(counter),
                                type="doc-code",
                                claim=text,
                                source_file=sol_file,
                                source_line=lineno,
                                subject=current_func,
                            ))
                    else:
                        pending_natspec.append((text, lineno))

            # require() / revert() — ground truth enforcement, subject = enclosing function
            r = _SOL_REQUIRE.search(stripped)
            if r:
                text = f"Contract enforces: {r.group(1).strip()[:120]}"
                key = (text, sol_file)
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter),
                        type="doc-code",
                        claim=text,
                        source_file=sol_file,
                        source_line=lineno,
                        subject=current_func,
                    ))

            # Function modifier on the signature line — subject = function name from modifier regex
            mod_m = _SOL_MODIFIER.search(stripped)
            if mod_m:
                fname = mod_m.group(1)
                text = (
                    f"Function '{fname}' claims access control "
                    f"via modifier '{mod_m.group(2)}'"
                )
                key = (text, sol_file)
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter),
                        type="doc-code",
                        claim=text,
                        source_file=sol_file,
                        source_line=lineno,
                        subject=fname,
                    ))

    return claims


def _extract_cairo_claims(repo_path: Path, counter: list[int]) -> list[Claim]:
    """
    Extract behavioral claims from Cairo (.cairo) files via doc comments.
    Captures /// and #[doc] annotation lines that carry behavioral promises.
    """
    claims: list[Claim] = []
    seen: set[tuple] = set()

    for cairo_file in sorted(repo_path.rglob("*.cairo")):
        try:
            source = cairo_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for lineno, line in enumerate(source.splitlines(), start=1):
            m = _CAIRO_DOC.search(line)
            if m:
                text = m.group(1).strip()
                if text and len(text) > 8 and _is_behavioral(text):
                    key = (text, cairo_file)
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter),
                            type="doc-code",
                            claim=text,
                            source_file=cairo_file,
                            source_line=lineno,
                        ))

    return claims


def extract_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """Scans repo_path for claims from Python, Solidity, Cairo, PHP, JS/TS, and config files."""
    counter = [start_id]
    claims = _extract_readme_claims(repo_path, counter)
    claims += _extract_python_claims(repo_path, counter)
    claims += _extract_solidity_claims(repo_path, counter)
    claims += _extract_cairo_claims(repo_path, counter)
    # PHP / WordPress support
    try:
        from invisible_seam.extractors.php_extractor import extract_php_claims
        claims += extract_php_claims(repo_path, start_id=counter[0])
    except ImportError:
        pass
    # JavaScript / TypeScript support
    try:
        from invisible_seam.extractors.js_extractor import extract_js_claims
        claims += extract_js_claims(repo_path, start_id=counter[0])
    except ImportError:
        pass
    # Config file security checks (YAML / JSON / TOML / env)
    try:
        from invisible_seam.extractors.config_extractor_security import extract_config_claims
        claims += extract_config_claims(repo_path, start_id=counter[0])
    except ImportError:
        pass
    return claims
