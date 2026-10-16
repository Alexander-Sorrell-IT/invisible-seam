"""PHP / WordPress claim extractor for the Invisible Seam engine.

Extracts behavioral claims from PHP files using PHPDoc comments and
WordPress-specific patterns.  A "claim" is anything the code SAYS it does —
a docblock assertion, a declared access control, a stated sanitization guarantee.
The matcher then checks whether the code actually enforces that claim.

WordPress-specific seam classes:
  1. Nonce claim — docblock says "verifies nonce" but wp_verify_nonce() absent
  2. Capability claim — docblock says "requires capability" but current_user_can() absent
  3. Sanitization claim — docblock says "sanitized" but no sanitize_*/esc_* call
  4. Prepare claim — docblock or inline says "safe query" but $wpdb->prepare() absent
  5. AJAX nopriv — function registered for wp_ajax_nopriv_ (public) but claims auth
  6. REST permission_callback missing — register_rest_route without permission_callback
"""
from __future__ import annotations

import re
from pathlib import Path

from invisible_seam.models import Claim

_SKIP_DIRS = {"node_modules", "vendor", ".git", "assets", "css", "js", "languages", "tests"}

# PHPDoc tag patterns
_PHPDOC_PARAM   = re.compile(r'@param\s+\S+\s+\$(\w+)\s*(.*)', re.IGNORECASE)
_PHPDOC_RETURN  = re.compile(r'@return\s+(\S+)\s*(.*)', re.IGNORECASE)
_PHPDOC_SINCE   = re.compile(r'@since\s+(.+)', re.IGNORECASE)
_PHPDOC_ACCESS  = re.compile(r'@access\s+(private|protected|public)', re.IGNORECASE)

# WordPress security function patterns
_WP_NONCE_VERIFY  = re.compile(r'wp_verify_nonce|check_ajax_referer|check_admin_referer')
_WP_CAP_CHECK     = re.compile(r'current_user_can\s*\(|user_can\s*\(')
_WP_SANITIZE      = re.compile(r'sanitize_\w+\s*\(|esc_\w+\s*\(|absint\s*\(|intval\s*\(')
_WP_PREPARE       = re.compile(r'\$wpdb\s*->\s*prepare\s*\(')
_WP_WPDB_QUERY    = re.compile(r'\$wpdb\s*->\s*(?:query|get_results|get_row|get_var|insert|update|delete)\s*\(')
_WP_AJAX_NOPRIV   = re.compile(r"add_action\s*\(\s*['\"]wp_ajax_nopriv_(\w+)['\"]")
_WP_AJAX_AUTH     = re.compile(r"add_action\s*\(\s*['\"]wp_ajax_(\w+)['\"]")
_REST_ROUTE       = re.compile(r"register_rest_route\s*\(")
_PERMISSION_CB    = re.compile(r"'permission_callback'|\"permission_callback\"")
_FUNC_DEF         = re.compile(r'^\s*(?:public\s+|private\s+|protected\s+|static\s+)*function\s+(\w+)\s*\(')

# Indirect security delegation patterns:
# $this->verify_*(…), self::verify_*(…), $this->check_*(…), $this->authenticate*(…)
# parent::verify_*(…), static::verify_*(…)
# Also catches: $this->security_check(), $this->ensureAuth(), etc.
_INDIRECT_NONCE = re.compile(
    r'(?:\$this|self|parent|static)\s*->\s*(?:verify|check|validate|authenticate|ensure)\w*\s*\(',
    re.IGNORECASE,
)
_INDIRECT_CAP = re.compile(
    r'(?:\$this|self|parent|static)\s*->\s*(?:verify|check|can|authorize|require_cap|capability|ensure)\w*\s*\(',
    re.IGNORECASE,
)

# Function name prefixes that indicate nonce getters (not verifiers) — skip nonce-verify check
_NONCE_GETTER_FUNC = re.compile(r'^(?:get|fetch|create|generate|make|build|retrieve)_', re.I)

# Behavioral keywords in docblock summary lines
_BEHAVIORAL       = re.compile(
    r'\b(?:verif|sanitiz|escap|validat|authoriz|authenticat|nonce|capability|'
    r'permission|secure|safe|check|ensur|requir|must|only)\w*\b',
    re.IGNORECASE,
)


def _next_id(counter: list[int]) -> str:
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def _collect_docblock(lines: list[str], func_idx: int) -> tuple[str, int]:
    """Collect the PHPDoc block immediately above func_idx. Returns (text, start_lineno)."""
    collected: list[str] = []
    start_lineno = func_idx
    j = func_idx - 1
    in_block = False
    while j >= 0:
        s = lines[j].strip()
        if s.endswith("*/"):
            in_block = True
        if in_block or s.startswith("*") or s.startswith("/**") or s.startswith("//"):
            text = re.sub(r'^/?\*+/?', '', s).strip()
            if text:
                collected.append(text)
                start_lineno = j + 1
        if s.startswith("/**") or (not in_block and not s.startswith("*") and not s.startswith("//")):
            break
        j -= 1
    collected.reverse()
    return " ".join(collected), start_lineno


def _brace_balanced_body(lines: list[str], func_idx: int, max_lines: int = 300) -> str:
    """
    Collect the full function body by tracking brace depth.

    Starts scanning from func_idx (the function declaration line).
    Returns the collected body as a single string, up to max_lines.

    Falls back to max_lines slice if the braces never close (malformed PHP).
    """
    depth = 0
    started = False
    collected: list[str] = []
    end = min(func_idx + max_lines, len(lines))
    for i in range(func_idx, end):
        line = lines[i]
        collected.append(line)
        # Count braces, ignoring those in strings (simple heuristic: don't parse strings)
        for ch in line:
            if ch == '{':
                depth += 1
                started = True
            elif ch == '}':
                depth -= 1
        if started and depth == 0:
            break
    return "\n".join(collected)


def extract_php_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """
    Extract behavioral claims from PHP files in repo_path.

    Claim types emitted:
      - doc-code : PHPDoc summary line contains security keyword
      - wp-nonce : function body should but may not call wp_verify_nonce (direct or indirect)
      - wp-cap   : function body should but may not call current_user_can (direct or indirect)
      - wp-sanitize: function body should but may not sanitize inputs
      - wp-prepare : wpdb query present but $wpdb->prepare() absent
      - wp-nopriv  : function hooked to wp_ajax_nopriv_ (unauthenticated)
      - rest-no-perm: register_rest_route without permission_callback
    """
    counter = [start_id]
    claims: list[Claim] = []
    seen: set[tuple] = set()
    repo_path = Path(repo_path).resolve()

    php_files = [
        f for f in sorted(repo_path.rglob("*.php"))
        if not any(skip in f.parts for skip in _SKIP_DIRS)
    ]

    for php_file in php_files:
        try:
            source = php_file.read_text(encoding="utf-8", errors="ignore")
            lines = source.splitlines()
        except OSError:
            continue

        # ── Pass 1: function-level claims from docblocks ─────────────────────
        for i, line in enumerate(lines):
            fd = _FUNC_DEF.match(line)
            if not fd:
                continue
            func_name = fd.group(1)

            # Brace-balanced body scan (up to 300 lines)
            body = _brace_balanced_body(lines, i, max_lines=300)

            docblock, doc_lineno = _collect_docblock(lines, i)
            if not docblock:
                continue

            # Behavioral docblock summary → doc-code claim
            if _BEHAVIORAL.search(docblock):
                text = f"Function '{func_name}' doc claims: {docblock[:200]}"
                key = (text, str(php_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter),
                        type="doc-code",
                        claim=text,
                        source_file=php_file,
                        source_line=doc_lineno,
                        subject=func_name,
                    ))

            # Nonce claim: docblock mentions nonce/referer but body doesn't verify
            # (direct call OR indirect delegation via $this->verify_*()/check_*())
            # Skip getter/creator functions — they produce nonces, don't verify them
            if re.search(r'\bnonce\b|\breferer\b', docblock, re.I) and not _NONCE_GETTER_FUNC.match(func_name):
                has_direct = bool(_WP_NONCE_VERIFY.search(body))
                has_indirect = bool(_INDIRECT_NONCE.search(body))
                if not has_direct and not has_indirect:
                    text = f"Function '{func_name}' claims nonce verification but wp_verify_nonce/check_ajax_referer not found in body"
                    key = (text, str(php_file))
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter),
                            type="wp-nonce",
                            claim=text,
                            source_file=php_file,
                            source_line=i + 1,
                            subject=func_name,
                        ))

            # Capability claim: docblock mentions capability/permission/auth but body doesn't check
            # (direct call OR indirect delegation)
            if re.search(r'\bcapabilit\w+|\bpermission\b|\badmin\b|\bauthori[sz]\w+\b', docblock, re.I):
                has_direct = bool(_WP_CAP_CHECK.search(body))
                has_indirect = bool(_INDIRECT_CAP.search(body))
                if not has_direct and not has_indirect:
                    text = f"Function '{func_name}' claims capability/auth check but current_user_can() not found in body"
                    key = (text, str(php_file))
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter),
                            type="wp-cap",
                            claim=text,
                            source_file=php_file,
                            source_line=i + 1,
                            subject=func_name,
                        ))

            # Sanitization claim: docblock mentions sanitize/escape but no call in body
            if re.search(r'\bsanitiz\w+|\bescape\b|\bescap\w+\b', docblock, re.I):
                if not _WP_SANITIZE.search(body):
                    text = f"Function '{func_name}' claims sanitization but no sanitize_*/esc_* call found"
                    key = (text, str(php_file))
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter),
                            type="wp-sanitize",
                            claim=text,
                            source_file=php_file,
                            source_line=i + 1,
                            subject=func_name,
                        ))

        # ── Pass 2: file-level patterns (REST routes, nopriv hooks, raw wpdb) ─

        # REST route without permission_callback
        # Use brace-balanced scan of the route args instead of fixed window
        for i, line in enumerate(lines):
            if _REST_ROUTE.search(line):
                # Scan from this line forward tracking parens until the register_rest_route call closes
                window = _paren_balanced_args(lines, i, max_lines=80)
                if not _PERMISSION_CB.search(window):
                    text = f"register_rest_route() at line {i+1} missing 'permission_callback' — unauthenticated REST endpoint"
                    key = (text, str(php_file))
                    if key not in seen:
                        seen.add(key)
                        claims.append(Claim(
                            id=_next_id(counter),
                            type="rest-no-perm",
                            claim=text,
                            source_file=php_file,
                            source_line=i + 1,
                            subject="register_rest_route",
                        ))

        # wp_ajax_nopriv hooks — public AJAX, no auth
        for i, line in enumerate(lines):
            m = _WP_AJAX_NOPRIV.search(line)
            if m:
                handler = m.group(1)
                text = f"AJAX handler '{handler}' registered for wp_ajax_nopriv_ (unauthenticated public access)"
                key = (text, str(php_file))
                if key not in seen:
                    seen.add(key)
                    claims.append(Claim(
                        id=_next_id(counter),
                        type="wp-nopriv",
                        claim=text,
                        source_file=php_file,
                        source_line=i + 1,
                        subject=handler,
                    ))

        # Raw wpdb query without prepare()
        for i, line in enumerate(lines):
            if _WP_WPDB_QUERY.search(line):
                # Check if this line and surrounding context uses prepare
                window = "\n".join(lines[max(0,i-2):i+3])
                if not _WP_PREPARE.search(window) and '$wpdb->prepare' not in window:
                    # Check if argument is a plain string concat (risky)
                    if re.search(r'\.\s*\$|\$\w+\s*\.', line):
                        text = f"wpdb query at line {i+1} uses string concatenation without prepare() — potential SQL injection"
                        key = (text, str(php_file))
                        if key not in seen:
                            seen.add(key)
                            claims.append(Claim(
                                id=_next_id(counter),
                                type="wp-prepare",
                                claim=text,
                                source_file=php_file,
                                source_line=i + 1,
                                subject="wpdb_query",
                            ))

    return claims


def _paren_balanced_args(lines: list[str], start_idx: int, max_lines: int = 80) -> str:
    """
    Collect the full argument list of a function call starting at start_idx
    by tracking parenthesis depth. Returns collected text as string.

    Falls back to max_lines slice if parens never close (malformed PHP).
    """
    depth = 0
    started = False
    collected: list[str] = []
    end = min(start_idx + max_lines, len(lines))
    for i in range(start_idx, end):
        line = lines[i]
        collected.append(line)
        for ch in line:
            if ch == '(':
                depth += 1
                started = True
            elif ch == ')':
                depth -= 1
        if started and depth == 0:
            break
    return "\n".join(collected)
