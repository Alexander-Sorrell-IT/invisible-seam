"""Go claim extractor for the Invisible Seam engine.

Extracts behavioral claims from Go source files using godoc comments and
structural patterns. A "claim" is anything the code SAYS it does — a godoc
assertion, a declared access control guarantee, a stated auth requirement.

Go-specific seam classes:
  1. go-noauth      — HTTP handler registered without auth middleware (ServeHTTP / HandleFunc)
  2. go-hardcoded   — hardcoded credential/secret literal in source
  3. go-defer-err   — defer with error-returning call where error is ignored
  4. go-unhandled   — _ = err pattern discarding an error on a security-relevant call
  5. go-tls-skip    — InsecureSkipVerify: true in TLS config
  6. go-godoc       — godoc comment behavioral claim (must/requires/returns non-zero)
  7. go-sql-concat  — fmt.Sprintf/+ used to build SQL query string (injection risk)
"""
from __future__ import annotations

import re
from pathlib import Path

from invisible_seam.models import Claim

_SKIP_DIRS = {"vendor", "testdata", ".git", "node_modules", "_test"}

# ── Patterns ──────────────────────────────────────────────────────────────────

# HTTP handler registration — net/http style
_HTTP_HANDLE    = re.compile(r'http\.Handle(?:Func)?\s*\(\s*["\']([^"\']+)["\']')
# ServeMux.HandleFunc
_MUX_HANDLE     = re.compile(r'\.\s*Handle(?:Func)?\s*\(\s*["\']([^"\']+)["\']')
# Common auth middleware names — if present near a handler, it's protected
_AUTH_MIDDLEWARE = re.compile(
    r'\b(?:Auth(?:enticate|orize|Middleware|Required|Handler)?|'
    r'RequireAuth|JWTMiddleware|BearerToken|ValidateToken|'
    r'IsAuthenticated|CheckAuth|WithAuth|AuthGuard)\b',
    re.IGNORECASE,
)
# Hardcoded credential patterns
_HARDCODED_CRED = re.compile(
    r'(?:password|passwd|secret|api_?key|token|credential|private_?key|auth_?key)\s*[:=]\s*["\']([^"\']{4,})["\']',
    re.IGNORECASE,
)
# defer with a call that returns error, but result discarded
_DEFER_CALL     = re.compile(r'^\s*defer\s+(\w[\w.()]+)\s*$')
# Error discard — _ = someSecurityCall(...)
_ERR_DISCARD    = re.compile(
    r'_\s*[,=]\s*(?:.*\.)?(?:Close|Write|Flush|Exec|Query|Remove|Delete|'
    r'Chmod|Chown|Rename|Connect|Login|Authenticate|Verify|Validate)\s*\(',
    re.IGNORECASE,
)
# TLS skip verify
_TLS_SKIP       = re.compile(r'InsecureSkipVerify\s*:\s*true')
# SQL concatenation via fmt.Sprintf or string + with SQL keywords
_SQL_SPRINTF    = re.compile(
    r'fmt\.Sprintf\s*\(\s*["\'][^"\']*(?:SELECT|INSERT|UPDATE|DELETE|WHERE|FROM)[^"\']*["\']',
    re.IGNORECASE,
)
_SQL_CONCAT     = re.compile(
    r'(?:query|sql|stmt)\s*(?:\+?=\s*|\s*:=\s*)["\'][^"\']*\s*\+\s*',
    re.IGNORECASE,
)
# Godoc behavioral comment — line immediately above func/method declaration
_FUNC_DEF       = re.compile(r'^func\s+(?:\(\s*\w+\s+[\*\w]+\s*\)\s+)?(\w+)\s*\(')
_GODOC_BEHAVIORAL = re.compile(
    r'\b(?:must|require|return|never|always|guarantee|ensure|only|verif|authenticat|'
    r'authoriz|sanitiz|validat|check|secure|safe)\w*\b',
    re.IGNORECASE,
)


def _next_id(counter: list[int]) -> str:
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def extract_go_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """
    Extract behavioral claims from Go (.go) files in repo_path.

    Claim types emitted:
      - go-noauth     : HTTP handler with no auth middleware nearby
      - go-hardcoded  : hardcoded credential literal
      - go-defer-err  : deferred call whose error is silently dropped
      - go-unhandled  : _ = securityCall(...) discarding error
      - go-tls-skip   : InsecureSkipVerify: true
      - go-godoc      : godoc behavioral claim
      - go-sql-concat : SQL query built by string concatenation
    """
    counter = [start_id]
    claims: list[Claim] = []
    seen: set[tuple] = set()
    repo_path = Path(repo_path).resolve()

    go_files = [
        f for f in sorted(repo_path.rglob("*.go"))
        if not any(skip in f.parts for skip in _SKIP_DIRS)
        and not f.name.endswith("_test.go")
    ]

    for go_file in go_files:
        try:
            lines = go_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        # Collect file text for multi-line patterns
        source = "\n".join(lines)

        # ── TLS skip verify ───────────────────────────────────────────────────
        for i, line in enumerate(lines):
            if _TLS_SKIP.search(line):
                text = f"InsecureSkipVerify: true at line {i+1} — TLS certificate verification disabled"
                key = (text, str(go_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="go-tls-skip",
                        claim=text, source_file=go_file, source_line=i + 1,
                        subject="TLSConfig",
                    ))

        # ── Hardcoded credentials ─────────────────────────────────────────────
        for i, line in enumerate(lines):
            m = _HARDCODED_CRED.search(line)
            if m and len(m.group(1)) > 4:
                # Skip obvious placeholders
                if re.match(r'^(your|example|placeholder|xxx|todo|changeme|test)',
                            m.group(1), re.I):
                    continue
                text = f"Hardcoded credential at line {i+1}: {line.strip()[:120]}"
                key = (text, str(go_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="go-hardcoded",
                        claim=text, source_file=go_file, source_line=i + 1,
                        subject="hardcoded_credential",
                    ))

        # ── SQL concatenation ─────────────────────────────────────────────────
        for i, line in enumerate(lines):
            if _SQL_SPRINTF.search(line) or _SQL_CONCAT.search(line):
                text = f"SQL query built by string concatenation at line {i+1} — injection risk: {line.strip()[:120]}"
                key = (text, str(go_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="go-sql-concat",
                        claim=text, source_file=go_file, source_line=i + 1,
                        subject="sql_query",
                    ))

        # ── Error discard on security calls ──────────────────────────────────
        for i, line in enumerate(lines):
            if _ERR_DISCARD.search(line):
                text = f"Security-relevant error discarded (_ =) at line {i+1}: {line.strip()[:120]}"
                key = (text, str(go_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="go-unhandled",
                        claim=text, source_file=go_file, source_line=i + 1,
                        subject="error_discard",
                    ))

        # ── HTTP handlers without auth middleware ────────────────────────────
        # Scan a window of ±10 lines around each handler registration for auth middleware
        for i, line in enumerate(lines):
            m = _HTTP_HANDLE.search(line) or _MUX_HANDLE.search(line)
            if not m:
                continue
            route = m.group(1) if m.lastindex else line.strip()[:60]
            window_start = max(0, i - 10)
            window_end   = min(len(lines), i + 10)
            window = "\n".join(lines[window_start:window_end])
            if not _AUTH_MIDDLEWARE.search(window):
                text = (f"HTTP handler '{route}' at line {i+1} registered without "
                        f"detectable auth middleware in surrounding context")
                key = (text, str(go_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="go-noauth",
                        claim=text, source_file=go_file, source_line=i + 1,
                        subject=route,
                    ))

        # ── Godoc behavioral claims ───────────────────────────────────────────
        for i, line in enumerate(lines):
            fd = _FUNC_DEF.match(line)
            if not fd:
                continue
            func_name = fd.group(1)
            # Collect godoc comment block immediately above
            doc_lines: list[str] = []
            j = i - 1
            while j >= 0:
                stripped = lines[j].strip()
                if stripped.startswith("//"):
                    doc_lines.append(stripped.lstrip("/").strip())
                    j -= 1
                else:
                    break
            if not doc_lines:
                continue
            doc_text = " ".join(reversed(doc_lines))
            if _GODOC_BEHAVIORAL.search(doc_text):
                text = f"func '{func_name}' godoc claims: {doc_text[:200]}"
                key = (text, str(go_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="go-godoc",
                        claim=text, source_file=go_file, source_line=i + 1,
                        subject=func_name,
                    ))

    return claims
