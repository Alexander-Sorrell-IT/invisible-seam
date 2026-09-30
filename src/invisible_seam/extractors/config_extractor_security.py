"""Config file (YAML / JSON) claim extractor for the Invisible Seam engine.

Extracts security misconfigurations from config files that make claims about
access control, authentication, or data protection — then checks if those
claims are actually enforced.

Config seam classes:
  1. iam-wildcard      — IAM policy with Action: '*' or Resource: '*' (AWS/GCP style)
  2. oauth-no-pkce     — OAuth2 config that doesn't require PKCE (response_type=code without PKCE)
  3. csp-unsafe        — Content-Security-Policy with unsafe-inline or unsafe-eval
  4. cors-wildcard     — CORS config with allow_origins: ['*'] or similar
  5. auth-disabled     — auth: false / authentication: disabled / require_auth: false
  6. debug-enabled     — debug: true in a non-dev config file
  7. tls-disabled      — SSL/TLS verification disabled (verify: false, ssl: false)
  8. secrets-in-config — literal secret/password/token value (not env-var reference)
  9. weak-jwt-algo     — JWT algorithm set to 'none' or symmetric HS256 in a multi-party config
 10. open-redirect     — redirect_uri / callback_url set to wildcard or open pattern
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from invisible_seam.models import Claim

_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "coverage",
    "__pycache__", "vendor", ".next",
}

# File extensions we care about
_CONFIG_EXTS = {".yaml", ".yml", ".json", ".toml", ".env", ".ini", ".conf"}

# Files we explicitly skip (test fixtures, lock files, package manifests)
_SKIP_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "composer.json",
    "composer.lock", "Pipfile.lock", "poetry.lock", "Cargo.lock",
    "tsconfig.json", "jsconfig.json", ".eslintrc.json", ".prettierrc",
    "babel.config.json", "jest.config.json", "webpack.config.js",
}

# ── Regex patterns (applied to raw file text line-by-line) ────────────────────

# IAM wildcard action or resource
_IAM_WILDCARD = re.compile(
    r'["\']?(?:Action|Resource|actions|resources)["\']?\s*[=:]\s*["\']?\*["\']?',
    re.IGNORECASE,
)
# IAM Effect: Allow with wildcard (the dangerous combo)
_IAM_ALLOW = re.compile(r'["\']?Effect["\']?\s*[=:]\s*["\']?Allow["\']?', re.IGNORECASE)

# OAuth/OIDC — no PKCE (code flow without code_challenge)
_OAUTH_CODE_FLOW  = re.compile(r'response_type\s*[=:]\s*["\']?code["\']?', re.IGNORECASE)
_OAUTH_PKCE       = re.compile(r'code_challenge|pkce|require_pkce|code_verifier', re.IGNORECASE)
_OAUTH_GRANT      = re.compile(r'grant_type\s*[=:]\s*["\']?authorization_code["\']?', re.IGNORECASE)

# CSP unsafe directives
_CSP_UNSAFE       = re.compile(r"'unsafe-inline'|'unsafe-eval'|'unsafe-hashes'", re.IGNORECASE)
_CSP_KEY          = re.compile(r'content.security.policy|csp\b', re.IGNORECASE)

# CORS wildcard
_CORS_WILDCARD    = re.compile(
    r'allow[_-]?origins?\s*[=:]\s*["\']?\*["\']?|'
    r'cors[_-]?origins?\s*[=:]\s*["\']?\*["\']?|'
    r'"Access-Control-Allow-Origin"\s*[=:]\s*["\']?\*["\']?',
    re.IGNORECASE,
)

# Auth disabled
_AUTH_DISABLED    = re.compile(
    r'(?:auth(?:entication)?|require[_-]?auth|enable[_-]?auth|auth[_-]?enabled)\s*[=:]\s*(?:false|no|disabled|0)\b',
    re.IGNORECASE,
)

# Debug enabled in non-dev context
_DEBUG_ON         = re.compile(r'\bdebug\s*[=:]\s*(?:true|yes|1|on)\b', re.IGNORECASE)
_DEV_INDICATOR    = re.compile(r'dev|development|local|test', re.IGNORECASE)

# TLS/SSL disabled
_TLS_DISABLED     = re.compile(
    r'(?:ssl[_-]?verify|verify[_-]?ssl|tls[_-]?verify|verify[_-]?tls|'
    r'insecure[_-]?skip[_-]?verify|rejectUnauthorized|ssl)\s*[=:]\s*(?:false|no|0|disabled)\b',
    re.IGNORECASE,
)

# Secrets / hardcoded values in config
_SECRET_KEY       = re.compile(
    r'(?:secret|password|passwd|api[_-]?key|private[_-]?key|signing[_-]?key|'
    r'jwt[_-]?secret|auth[_-]?token|access[_-]?key|encryption[_-]?key|'
    r'hmac[_-]?secret)\s*[=:]\s*["\']([^"\'$\{]{8,})["\']',
    re.IGNORECASE,
)
_SECRET_EXEMPT    = re.compile(
    r'\$\{|\$\(|env\.|ENV\.|process\.env|%\w+%|<[A-Z_]+>|'
    r'changeme|placeholder|example|your[_-]?|REPLACE|REDACTED',
    re.IGNORECASE,
)

# Weak JWT algorithm
_JWT_ALGO_WEAK    = re.compile(
    r'algorithm\s*[=:]\s*["\']?(?:none|HS256|HS384|HS512)["\']?',
    re.IGNORECASE,
)
_JWT_MULTI_PARTY  = re.compile(r'public[_-]?key|audience|issuer\s*[=:]', re.IGNORECASE)

# Open redirect in OAuth config
_REDIRECT_URI     = re.compile(r'redirect[_-]?uri[s]?\s*[=:]', re.IGNORECASE)
_OPEN_REDIRECT    = re.compile(r'["\']?\*["\']?|\*\.|localhost\b|http://', re.IGNORECASE)


def _next_id(counter: list[int]) -> str:
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def _emit(
    claims: list[Claim],
    seen: set[tuple],
    counter: list[int],
    claim_type: str,
    text: str,
    source_file: Path,
    source_line: int,
    subject: str,
) -> None:
    key = (text, str(source_file))
    if key not in seen:
        seen.add(key)
        claims.append(Claim(
            id=_next_id(counter),
            type=claim_type,
            claim=text,
            source_file=source_file,
            source_line=source_line,
            subject=subject,
        ))


def extract_config_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """
    Extract security misconfigurations from YAML/JSON/TOML/env config files.

    Claim types emitted:
      - iam-wildcard       : IAM Allow with Action/Resource '*'
      - oauth-no-pkce      : OAuth2 authorization_code flow without PKCE enforcement
      - csp-unsafe         : CSP header with unsafe-inline or unsafe-eval
      - cors-wildcard      : CORS allow-all origin
      - auth-disabled      : authentication explicitly disabled
      - debug-enabled      : debug mode on in a production-looking config
      - tls-disabled       : TLS/SSL verification disabled
      - secrets-in-config  : literal secret value (not env-var reference)
      - weak-jwt-algo      : JWT using 'none' or symmetric algo in multi-party context
      - open-redirect      : OAuth redirect_uri with wildcard or open pattern
    """
    counter = [start_id]
    claims: list[Claim] = []
    seen: set[tuple] = set()
    repo_path = Path(repo_path).resolve()

    config_files = [
        f for f in sorted(repo_path.rglob("*"))
        if f.suffix in _CONFIG_EXTS
        and f.name not in _SKIP_FILES
        and not any(skip in f.parts for skip in _SKIP_DIRS)
    ]

    for cfg_file in config_files:
        try:
            source = cfg_file.read_text(encoding="utf-8", errors="ignore")
            lines = source.splitlines()
        except OSError:
            continue

        is_dev = bool(_DEV_INDICATOR.search(cfg_file.name)) or bool(
            _DEV_INDICATOR.search(str(cfg_file.parent))
        )
        # Track context for multi-line patterns
        in_iam_allow_block = False
        in_oauth_block = False
        oauth_block_has_pkce = False
        oauth_block_start = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # ── IAM wildcard ─────────────────────────────────────────────────
            if _IAM_ALLOW.search(line):
                in_iam_allow_block = True
            if in_iam_allow_block and _IAM_WILDCARD.search(line):
                _emit(claims, seen, counter, "iam-wildcard",
                      f"IAM Allow policy with wildcard Action/Resource at line {i+1} — overpermissioned",
                      cfg_file, i + 1, "iam_policy")
                in_iam_allow_block = False  # only flag once per Allow block

            # ── OAuth PKCE ────────────────────────────────────────────────────
            if _OAUTH_CODE_FLOW.search(line) or _OAUTH_GRANT.search(line):
                in_oauth_block = True
                oauth_block_start = i
                oauth_block_has_pkce = False
            if in_oauth_block and _OAUTH_PKCE.search(line):
                oauth_block_has_pkce = True
            # Close the OAuth block check after 15 lines
            if in_oauth_block and (i - oauth_block_start) > 15:
                if not oauth_block_has_pkce:
                    _emit(claims, seen, counter, "oauth-no-pkce",
                          f"OAuth2 authorization_code flow at line {oauth_block_start+1} has no PKCE requirement",
                          cfg_file, oauth_block_start + 1, "oauth_config")
                in_oauth_block = False

            # ── CSP unsafe ───────────────────────────────────────────────────
            if _CSP_KEY.search(line) and _CSP_UNSAFE.search(line):
                _emit(claims, seen, counter, "csp-unsafe",
                      f"Content-Security-Policy at line {i+1} contains 'unsafe-inline' or 'unsafe-eval'",
                      cfg_file, i + 1, "csp")
            elif _CSP_UNSAFE.search(line):
                _emit(claims, seen, counter, "csp-unsafe",
                      f"CSP directive at line {i+1} uses unsafe-inline/unsafe-eval — XSS protection bypassed",
                      cfg_file, i + 1, "csp")

            # ── CORS wildcard ─────────────────────────────────────────────────
            if _CORS_WILDCARD.search(line):
                _emit(claims, seen, counter, "cors-wildcard",
                      f"CORS wildcard (allow all origins) at line {i+1}",
                      cfg_file, i + 1, "cors")

            # ── Auth disabled ─────────────────────────────────────────────────
            if _AUTH_DISABLED.search(line):
                _emit(claims, seen, counter, "auth-disabled",
                      f"Authentication explicitly disabled at line {i+1}",
                      cfg_file, i + 1, "auth_config")

            # ── Debug enabled (non-dev) ───────────────────────────────────────
            if _DEBUG_ON.search(line) and not is_dev:
                _emit(claims, seen, counter, "debug-enabled",
                      f"debug: true in non-dev config at line {i+1} — may expose stack traces / internals",
                      cfg_file, i + 1, "debug")

            # ── TLS disabled ──────────────────────────────────────────────────
            if _TLS_DISABLED.search(line):
                _emit(claims, seen, counter, "tls-disabled",
                      f"TLS/SSL verification disabled at line {i+1} — MITM attacks possible",
                      cfg_file, i + 1, "tls")

            # ── Hardcoded secrets ─────────────────────────────────────────────
            m = _SECRET_KEY.search(line)
            if m and not _SECRET_EXEMPT.search(line):
                _emit(claims, seen, counter, "secrets-in-config",
                      f"Hardcoded secret/key in config at line {i+1} — should be env-var reference",
                      cfg_file, i + 1, "secret")

            # ── Weak JWT algorithm ────────────────────────────────────────────
            if _JWT_ALGO_WEAK.search(line):
                # Only flag HS* as weak in multi-party context (where asymmetric is needed)
                window_around = "\n".join(lines[max(0, i-5):min(len(lines), i+5)])
                if re.search(r'none', line, re.I) or _JWT_MULTI_PARTY.search(window_around):
                    _emit(claims, seen, counter, "weak-jwt-algo",
                          f"JWT using weak/symmetric algorithm at line {i+1} — consider RS256/ES256 for multi-party",
                          cfg_file, i + 1, "jwt_config")

            # ── Open redirect URI ─────────────────────────────────────────────
            if _REDIRECT_URI.search(line) and _OPEN_REDIRECT.search(line):
                _emit(claims, seen, counter, "open-redirect",
                      f"OAuth redirect_uri at line {i+1} contains wildcard or insecure pattern",
                      cfg_file, i + 1, "oauth_redirect")

    return claims
