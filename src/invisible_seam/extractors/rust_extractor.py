"""Rust claim extractor for the Invisible Seam engine.

Extracts behavioral claims from Rust source files using doc comments (///)
and structural patterns. A "claim" is anything the code SAYS it does.

Rust-specific seam classes:
  1. rust-unsafe      — unsafe block claimed safe in doc comment (paradox)
  2. rust-unwrap       — .unwrap()/.expect() on user-controlled / security-relevant value
  3. rust-hardcoded    — hardcoded credential/secret literal
  4. rust-rustdoc      — /// doc comment behavioral claim
  5. rust-tls-skip     — danger_accept_invalid_certs / accept_invalid_hostnames
  6. rust-sql-concat   — format! used to build SQL query string
  7. rust-no-bounds    — indexing operation without bounds check on user-controlled index
"""
from __future__ import annotations

import re
from pathlib import Path

from invisible_seam.models import Claim

_SKIP_DIRS = {"target", ".git", "tests", "benches", "examples"}

# ── Patterns ──────────────────────────────────────────────────────────────────

# unsafe block
_UNSAFE_BLOCK   = re.compile(r'\bunsafe\s*\{')
# .unwrap() / .expect("...") on lines involving user input, auth, crypto, network
_UNWRAP         = re.compile(r'\.(unwrap|expect)\s*\(')
_SECURITY_CTX   = re.compile(
    r'\b(?:password|secret|token|key|auth|credential|request|user|input|'
    r'parse|from_str|decrypt|verify|sign|hash)\b',
    re.IGNORECASE,
)
# Hardcoded secrets
_HARDCODED_CRED = re.compile(
    r'(?:password|secret|api_?key|token|credential|private_?key)\s*[:=]\s*["\']([^"\']{4,})["\']',
    re.IGNORECASE,
)
# TLS danger flags
_TLS_DANGER     = re.compile(
    r'danger_accept_invalid_certs\s*\(\s*true\s*\)|'
    r'accept_invalid_hostnames\s*\(\s*true\s*\)|'
    r'disable_certificate_verification',
    re.IGNORECASE,
)
# SQL concatenation via format!
_SQL_FORMAT     = re.compile(
    r'format!\s*\(\s*["\'][^"\']*(?:SELECT|INSERT|UPDATE|DELETE|WHERE|FROM)[^"\']*["\']',
    re.IGNORECASE,
)
# fn definition line
_FN_DEF         = re.compile(r'^\s*(?:pub(?:\(.*?\))?\s+)?(?:async\s+)?fn\s+(\w+)\s*[(<]')
# /// doc comment
_RUSTDOC        = re.compile(r'^\s*//[!/]\s*(.*)')
# Behavioral keywords in rustdoc
_BEHAVIORAL     = re.compile(
    r'\b(?:must|require|return|never|always|guarantee|ensure|only|safe|unsafe|'
    r'verif|authenticat|authoriz|sanitiz|validat|check|panic|unwrap|infallible)\w*\b',
    re.IGNORECASE,
)
# unsafe in doc comment = claims it's safe
_UNSAFE_CLAIM   = re.compile(r'\b(?:safe|sound|no[- ]?ub|well[- ]?defined)\b', re.IGNORECASE)


def _next_id(counter: list[int]) -> str:
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def extract_rust_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """
    Extract behavioral claims from Rust (.rs) files in repo_path.

    Claim types emitted:
      - rust-unsafe    : unsafe block in a fn whose doc claims it is safe
      - rust-unwrap    : .unwrap()/.expect() in security-relevant context
      - rust-hardcoded : hardcoded credential literal
      - rust-rustdoc   : /// behavioral doc claim
      - rust-tls-skip  : TLS certificate validation disabled
      - rust-sql-concat: SQL built via format!()
    """
    counter = [start_id]
    claims: list[Claim] = []
    seen: set[tuple] = set()
    repo_path = Path(repo_path).resolve()

    rs_files = [
        f for f in sorted(repo_path.rglob("*.rs"))
        if not any(skip in f.parts for skip in _SKIP_DIRS)
    ]

    for rs_file in rs_files:
        try:
            lines = rs_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        # ── TLS danger flags ──────────────────────────────────────────────────
        for i, line in enumerate(lines):
            if _TLS_DANGER.search(line):
                text = f"TLS certificate validation disabled at line {i+1}: {line.strip()[:120]}"
                key = (text, str(rs_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="rust-tls-skip",
                        claim=text, source_file=rs_file, source_line=i + 1,
                        subject="TLSConfig",
                    ))

        # ── Hardcoded credentials ─────────────────────────────────────────────
        for i, line in enumerate(lines):
            m = _HARDCODED_CRED.search(line)
            if m and len(m.group(1)) > 4:
                if re.match(r'^(your|example|placeholder|xxx|todo|changeme|test)',
                            m.group(1), re.I):
                    continue
                text = f"Hardcoded credential at line {i+1}: {line.strip()[:120]}"
                key = (text, str(rs_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="rust-hardcoded",
                        claim=text, source_file=rs_file, source_line=i + 1,
                        subject="hardcoded_credential",
                    ))

        # ── SQL via format! ───────────────────────────────────────────────────
        for i, line in enumerate(lines):
            if _SQL_FORMAT.search(line):
                text = f"SQL query built via format!() at line {i+1} — injection risk: {line.strip()[:120]}"
                key = (text, str(rs_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="rust-sql-concat",
                        claim=text, source_file=rs_file, source_line=i + 1,
                        subject="sql_query",
                    ))

        # ── Function-level: doc claims + unsafe + unwrap ──────────────────────
        for i, line in enumerate(lines):
            fd = _FN_DEF.match(line)
            if not fd:
                continue
            fn_name = fd.group(1)

            # Collect /// doc block immediately above
            doc_lines: list[str] = []
            j = i - 1
            while j >= 0:
                m = _RUSTDOC.match(lines[j])
                if m:
                    doc_lines.append(m.group(1).strip())
                    j -= 1
                elif lines[j].strip() == "" or lines[j].strip().startswith("#["):
                    j -= 1  # skip blank lines and attributes
                else:
                    break
            doc_text = " ".join(reversed(doc_lines)).strip()

            # Collect function body (brace-balanced, up to 200 lines)
            body_lines: list[str] = []
            depth = 0
            started = False
            for k in range(i, min(i + 200, len(lines))):
                body_lines.append(lines[k])
                for ch in lines[k]:
                    if ch == '{':
                        depth += 1
                        started = True
                    elif ch == '}':
                        depth -= 1
                if started and depth == 0:
                    break
            body = "\n".join(body_lines)

            # rust-unsafe: fn doc says "safe" but body has unsafe{}
            if doc_text and _UNSAFE_CLAIM.search(doc_text) and _UNSAFE_BLOCK.search(body):
                text = (f"fn '{fn_name}' doc claims safety ({doc_text[:100]}) "
                        f"but body contains unsafe block")
                key = (text, str(rs_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="rust-unsafe",
                        claim=text, source_file=rs_file, source_line=i + 1,
                        subject=fn_name,
                    ))

            # rust-unwrap: .unwrap()/.expect() in security-relevant fn body
            for k_off, bl in enumerate(body_lines):
                if _UNWRAP.search(bl) and _SECURITY_CTX.search(bl):
                    text = (f"fn '{fn_name}': .unwrap()/.expect() on security-relevant "
                            f"value at line {i+1+k_off}: {bl.strip()[:120]}")
                    key = (text, str(rs_file))
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter), type="rust-unwrap",
                            claim=text, source_file=rs_file,
                            source_line=i + 1 + k_off,
                            subject=fn_name,
                        ))

            # rust-rustdoc: behavioral doc claim
            if doc_text and _BEHAVIORAL.search(doc_text):
                text = f"fn '{fn_name}' rustdoc claims: {doc_text[:200]}"
                key = (text, str(rs_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter), type="rust-rustdoc",
                        claim=text, source_file=rs_file, source_line=i + 1,
                        subject=fn_name,
                    ))

    return claims
