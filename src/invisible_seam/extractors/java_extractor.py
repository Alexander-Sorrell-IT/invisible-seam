"""Java claim extractor for the Invisible Seam engine.

Extracts behavioral claims from Java source files using Javadoc comments
and structural patterns. A "claim" is anything the code SAYS it does.

Java-specific seam classes:
  1. java-spring-noauth — Spring @RequestMapping/@GetMapping/@PostMapping without
                          @PreAuthorize / @Secured / SecurityConfig reference
  2. java-sql-concat    — JDBC query built by string concatenation (SQLi)
  3. java-hardcoded     — hardcoded credential/secret literal
  4. java-javadoc       — Javadoc behavioral claim (@param, @throws, prose)
  5. java-secret-log    — System.out.println / logger.* of a secret/token value
  6. java-deserialize   — ObjectInputStream.readObject() without auth guard nearby
  7. java-xxe           — XML parser without disabling external entity processing
"""
from __future__ import annotations

import re
from pathlib import Path

from invisible_seam.models import Claim

_SKIP_DIRS = {"target", ".git", "test", "tests", "generated", "build"}

# ── Patterns ──────────────────────────────────────────────────────────────────

# Spring MVC route annotations
_SPRING_MAPPING = re.compile(
    r'@(?:Request|Get|Post|Put|Delete|Patch)Mapping\s*'
    r'(?:\(\s*["\']?([^"\'\)]+)["\']?\s*\))?',
    re.IGNORECASE,
)
# Spring security annotations
_SPRING_SECURE  = re.compile(
    r'@(?:PreAuthorize|PostAuthorize|Secured|RolesAllowed|'
    r'WithMockUser|EnableGlobalMethodSecurity)',
    re.IGNORECASE,
)
# Also SecurityContextHolder usage = manual auth check
_SECURITY_CTX   = re.compile(
    r'SecurityContextHolder|Authentication\s+auth|'
    r'\.isAuthenticated\(\)|\.hasRole\(|\.hasAuthority\(',
    re.IGNORECASE,
)
# JDBC string concatenation
_JDBC_CONCAT    = re.compile(
    r'(?:createStatement|prepareStatement|executeQuery|executeUpdate)\s*\('
    r'[^;]*(?:\+\s*\w|\w\s*\+)',
)
_SQL_CONCAT     = re.compile(
    r'(?:String\s+\w+\s*=\s*["\'][^"\']*(?:SELECT|INSERT|UPDATE|DELETE|WHERE)[^"\']*["\']'
    r'\s*\+|(?:SELECT|INSERT|UPDATE|DELETE)\s*["\'][^"\']*["\']\s*\+)',
    re.IGNORECASE,
)
# Hardcoded credentials
_HARDCODED_CRED = re.compile(
    r'(?:password|passwd|secret|apiKey|api_key|token|credential|privateKey)\s*=\s*["\']([^"\']{4,})["\']',
    re.IGNORECASE,
)
# System.out.println / logger of secrets
_SECRET_LOG     = re.compile(
    r'(?:System\.out\.print(?:ln)?|log(?:ger)?\.(?:info|debug|warn|error|trace))\s*\('
    r'[^;]*(?:password|secret|token|key|credential|auth)',
    re.IGNORECASE,
)
# ObjectInputStream.readObject
_DESERIALIZE    = re.compile(r'\.readObject\s*\(\s*\)')
# XML factory without security flags
_XML_PARSER     = re.compile(
    r'(?:DocumentBuilderFactory|SAXParserFactory|XMLInputFactory)\s*\.\s*newInstance\s*\(\s*\)',
)
_XML_SECURE     = re.compile(
    r'setFeature\s*\(\s*["\']http://(?:xml\.org|apache\.org)[^"\']*["\']|'
    r'setExpandEntityReferences\s*\(\s*false\s*\)|'
    r'DISALLOW_DOCTYPE_DECL',
)
# Method / class declaration
_METHOD_DEF     = re.compile(
    r'^\s*(?:public|protected|private|static|final|synchronized|native|abstract|\s)+'
    r'[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{'
)
# Javadoc behavioral comment
_JAVADOC_LINE   = re.compile(r'^\s*\*?\s*(?:@(?:param|throws|return|exception)\s+\S*\s*)?(.+)')
_BEHAVIORAL     = re.compile(
    r'\b(?:must|require|return|never|always|guarantee|ensure|only|'
    r'verif|authenticat|authoriz|sanitiz|validat|check|throw|raise|'
    r'secure|safe|not null|non-?null)\w*\b',
    re.IGNORECASE,
)


def _next_id(counter: list[int]) -> str:
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def _collect_javadoc(lines: list[str], method_idx: int) -> tuple[str, int]:
    """Collect Javadoc block immediately above method_idx. Returns (text, start_lineno)."""
    collected: list[str] = []
    start = method_idx
    j = method_idx - 1
    in_block = False
    while j >= 0:
        s = lines[j].strip()
        if s.endswith("*/"):
            in_block = True
        if in_block or s.startswith("*") or s.startswith("/**"):
            text = re.sub(r'^/?\*+/?', '', s).strip()
            if text:
                collected.append(text)
                start = j + 1
        if s.startswith("/**") or (not in_block and not s.startswith("*")):
            break
        j -= 1
    collected.reverse()
    return " ".join(collected), start


def extract_java_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """
    Extract behavioral claims from Java (.java) files in repo_path.

    Claim types emitted:
      - java-spring-noauth : Spring mapping without auth annotation/check
      - java-sql-concat    : JDBC query built by string concatenation
      - java-hardcoded     : hardcoded credential literal
      - java-javadoc       : Javadoc behavioral claim
      - java-secret-log    : logging of credential/secret value
      - java-deserialize   : ObjectInputStream.readObject without nearby auth guard
      - java-xxe           : XML parser without external entity protection
    """
    counter = [start_id]
    claims: list[Claim] = []
    seen: set[tuple] = set()
    repo_path = Path(repo_path).resolve()

    java_files = [
        f for f in sorted(repo_path.rglob("*.java"))
        if not any(skip in f.parts for skip in _SKIP_DIRS)
    ]

    for java_file in java_files:
        try:
            lines = java_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        # ── Hardcoded credentials ─────────────────────────────────────────────
        for i, line in enumerate(lines):
            m = _HARDCODED_CRED.search(line)
            if m and len(m.group(1)) > 4:
                if re.match(r'^(your|example|placeholder|xxx|todo|changeme|test)',
                            m.group(1), re.I):
                    continue
                text = f"Hardcoded credential at line {i+1}: {line.strip()[:120]}"
                key = (text, str(java_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="java-hardcoded",
                        claim=text, source_file=java_file, source_line=i + 1,
                        subject="hardcoded_credential",
                    ))

        # ── Secret logging ────────────────────────────────────────────────────
        for i, line in enumerate(lines):
            if _SECRET_LOG.search(line):
                text = f"Credential/secret value logged at line {i+1}: {line.strip()[:120]}"
                key = (text, str(java_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="java-secret-log",
                        claim=text, source_file=java_file, source_line=i + 1,
                        subject="secret_log",
                    ))

        # ── SQL string concatenation ──────────────────────────────────────────
        for i, line in enumerate(lines):
            if _JDBC_CONCAT.search(line) or _SQL_CONCAT.search(line):
                text = f"JDBC query built by string concatenation at line {i+1}: {line.strip()[:120]}"
                key = (text, str(java_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="java-sql-concat",
                        claim=text, source_file=java_file, source_line=i + 1,
                        subject="sql_query",
                    ))

        # ── Deserialization without auth ──────────────────────────────────────
        for i, line in enumerate(lines):
            if _DESERIALIZE.search(line):
                window = "\n".join(lines[max(0, i-15):i+5])
                if not _SECURITY_CTX.search(window) and not _SPRING_SECURE.search(window):
                    text = f"ObjectInputStream.readObject() at line {i+1} without detectable auth guard"
                    key = (text, str(java_file))
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter), type="java-deserialize",
                            claim=text, source_file=java_file, source_line=i + 1,
                            subject="readObject",
                        ))

        # ── XML parser without XXE protection ────────────────────────────────
        for i, line in enumerate(lines):
            if _XML_PARSER.search(line):
                window = "\n".join(lines[i:min(len(lines), i+20)])
                if not _XML_SECURE.search(window):
                    text = f"XML parser created at line {i+1} without XXE protection (no setFeature/DISALLOW_DOCTYPE)"
                    key = (text, str(java_file))
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter), type="java-xxe",
                            claim=text, source_file=java_file, source_line=i + 1,
                            subject="XMLParser",
                        ))

        # ── Spring route annotations without auth ─────────────────────────────
        for i, line in enumerate(lines):
            if not _SPRING_MAPPING.search(line):
                continue
            route_match = _SPRING_MAPPING.search(line)
            route = route_match.group(1) if route_match and route_match.lastindex else line.strip()[:60]
            # Check ±20 lines for security annotation or SecurityContextHolder usage
            window_start = max(0, i - 5)
            window_end   = min(len(lines), i + 20)
            window = "\n".join(lines[window_start:window_end])
            if not _SPRING_SECURE.search(window) and not _SECURITY_CTX.search(window):
                text = (f"Spring route '{route}' at line {i+1} has no "
                        f"@PreAuthorize/@Secured or SecurityContext check in method scope")
                key = (text, str(java_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="java-spring-noauth",
                        claim=text, source_file=java_file, source_line=i + 1,
                        subject=route,
                    ))

        # ── Javadoc behavioral claims on methods ──────────────────────────────
        for i, line in enumerate(lines):
            md = _METHOD_DEF.match(line)
            if not md:
                continue
            method_name = md.group(1)
            doc_text, doc_line = _collect_javadoc(lines, i)
            if not doc_text:
                continue
            if _BEHAVIORAL.search(doc_text):
                text = f"Method '{method_name}' Javadoc claims: {doc_text[:200]}"
                key = (text, str(java_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="java-javadoc",
                        claim=text, source_file=java_file, source_line=doc_line,
                        subject=method_name,
                    ))

    return claims
