"""JavaScript / TypeScript claim extractor for the Invisible Seam engine.

Extracts behavioral claims from JS/TS source files using JSDoc comments and
framework-specific patterns.  A "claim" is anything the code SAYS it does —
a JSDoc assertion about auth, a declared middleware chain, a stated validation.
The matcher then checks whether the code actually enforces that claim.

JS/TS seam classes:
  1. jsdoc-auth    — JSDoc says "requires auth/role/permission" but no auth middleware/guard found
  2. express-noauth — Express route handler (app.get/post/put/delete/patch) with no auth middleware
  3. jwt-nochecks  — jwt.sign/verify called but options.algorithms missing or expiry unchecked
  4. eval-sink     — eval() / new Function() / innerHTML / document.write with non-literal arg
  5. hardcoded-secret — string literal that looks like a key/password/token assigned to a secret var
  6. missing-input-validation — route handler reads req.body/req.query but no validation/sanitize call
  7. cors-wildcard — CORS configured with origin: '*' or allow-all
  8. prototype-pollution — recursive merge/assign without hasOwnProperty guard
"""
from __future__ import annotations

import re
from pathlib import Path

from invisible_seam.models import Claim

_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "coverage",
    ".next", ".nuxt", "vendor", "__pycache__", "assets",
}

# ── JSDoc patterns ─────────────────────────────────────────────────────────────
_JSDOC_BLOCK   = re.compile(r'/\*\*(.*?)\*/', re.DOTALL)
_JSDOC_AUTH    = re.compile(
    r'@(?:auth|security|requires?|permission|role|access|protected|guard)\b.*',
    re.IGNORECASE,
)
_JSDOC_BEHAVIOR = re.compile(
    r'\b(?:verif|sanitiz|validat|authoriz|authenticat|permission|secure|safe|'
    r'check|ensur|require|must|only|protect|restrict|guard)\w*\b',
    re.IGNORECASE,
)

# ── Express route patterns ─────────────────────────────────────────────────────
# Matches: router.get('/path', handler) or app.post('/path', mw, handler)
_EXPRESS_ROUTE = re.compile(
    r'(?:router|app|server)\s*\.\s*(?:get|post|put|patch|delete|use)\s*\(',
    re.IGNORECASE,
)
# Auth middleware names — if any of these appear in the route's arg list it's protected
_AUTH_MIDDLEWARE = re.compile(
    r'\b(?:auth|authenticate|isAuth|requireAuth|verifyToken|passport|ensureLoggedIn|'
    r'checkAuth|authorize|isLoggedIn|requireLogin|jwtMiddleware|bearerAuth|'
    r'withAuth|protect|verifyJWT|checkJWT|authenticated|isAuthenticated)\b',
    re.IGNORECASE,
)

# ── JWT patterns ───────────────────────────────────────────────────────────────
_JWT_SIGN    = re.compile(r'jwt\s*\.\s*sign\s*\(')
_JWT_VERIFY  = re.compile(r'jwt\s*\.\s*verify\s*\(')
_JWT_ALGO    = re.compile(r'algorithms?\s*[=:]\s*\[')
_JWT_EXPIRY  = re.compile(r'expiresIn\s*[=:]')

# ── Dangerous sinks ────────────────────────────────────────────────────────────
_EVAL_SINK   = re.compile(r'\beval\s*\(|new\s+Function\s*\(')
_DOM_SINK    = re.compile(r'\.innerHTML\s*[+]?=|\.outerHTML\s*[+]?=|document\.write\s*\(')
_NON_LITERAL = re.compile(r'[+`$]')   # string concat, template literal, variable

# ── Hardcoded secrets ──────────────────────────────────────────────────────────
_SECRET_VAR  = re.compile(
    r'(?:secret|password|passwd|api_key|apikey|private_key|token|jwt_secret|'
    r'auth_token|access_key|signing_key)\s*[=:]\s*["\']([^"\']{8,})["\']',
    re.IGNORECASE,
)
_SECRET_EXEMPT = re.compile(
    r'process\.env\.|config\.|require\(|import\s+|placeholder|example|changeme|'
    r'your[_-]?(?:secret|key|token)|<[A-Z_]+>',
    re.IGNORECASE,
)

# ── Input validation ───────────────────────────────────────────────────────────
_REQ_INPUT   = re.compile(r'req\.(?:body|query|params|headers)\b')
_VALIDATION  = re.compile(
    r'\bvalidate\b|\bsanitize\b|\bescape\b|\bJoi\b|\byup\b|\bzod\b|'
    r'\.trim\(\)|parseInt\(|parseFloat\(|Number\(|Boolean\(|isNaN\(|'
    r'encodeURIComponent\(|DOMPurify\b|xss\b',
    re.IGNORECASE,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
_CORS_WILDCARD = re.compile(
    r"origin\s*[=:]\s*['\"]?\*['\"]?|"
    r"Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]?\*",
    re.IGNORECASE,
)

# ── Prototype pollution ────────────────────────────────────────────────────────
_RECURSIVE_MERGE = re.compile(r'function\s+\w*(?:merge|assign|extend|deep)\w*\s*\(', re.IGNORECASE)
_HAS_OWN_PROP    = re.compile(r'hasOwnProperty|Object\.prototype\.hasOwnProperty|hasOwn\b')

# ── Function/method definition ─────────────────────────────────────────────────
_FUNC_DEF    = re.compile(
    r'(?:^|\s)(?:async\s+)?function\s+(\w+)\s*\('         # function foo(
    r'|(?:^|\s)(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\('  # const foo = (
    r'|^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{',          # method shorthand
    re.MULTILINE,
)


def _next_id(counter: list[int]) -> str:
    val = counter[0]
    counter[0] += 1
    return f"C{val:03d}"


def _collect_jsdoc(lines: list[str], func_idx: int) -> str:
    """Collect the JSDoc block immediately above func_idx."""
    j = func_idx - 1
    # skip blank lines
    while j >= 0 and not lines[j].strip():
        j -= 1
    if j < 0 or not lines[j].strip().startswith('*') and not lines[j].strip() == '*/':
        return ""
    # scan up to find /**
    collected = []
    while j >= 0:
        s = lines[j].strip()
        collected.append(s)
        if s.startswith('/**'):
            break
        j -= 1
    return " ".join(reversed(collected))


def _line_window(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[max(0, start):min(len(lines), end)])


def extract_js_claims(repo_path: Path, start_id: int = 1) -> list[Claim]:
    """
    Extract behavioral claims from JS/TS files in repo_path.

    Claim types emitted:
      - jsdoc-auth        : JSDoc claims auth/permission but no auth middleware in route
      - express-noauth    : Express route with no auth middleware visible
      - jwt-nochecks      : jwt.sign missing algorithm or jwt.verify missing algorithm check
      - eval-sink         : eval/new Function/innerHTML with dynamic argument
      - hardcoded-secret  : string literal assigned to secret/key/password/token variable
      - missing-validation: route handler reads req.body/query but no validation call
      - cors-wildcard     : CORS configured with origin: '*'
      - proto-pollution   : merge/assign/extend function without hasOwnProperty guard
    """
    counter = [start_id]
    claims: list[Claim] = []
    seen: set[tuple] = set()
    repo_path = Path(repo_path).resolve()

    js_files = [
        f for f in sorted(repo_path.rglob("*"))
        if f.suffix in (".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx")
        and not any(skip in f.parts for skip in _SKIP_DIRS)
    ]

    for js_file in js_files:
        try:
            source = js_file.read_text(encoding="utf-8", errors="ignore")
            lines = source.splitlines()
        except OSError:
            continue

        # ── Pass 1: line-by-line patterns ────────────────────────────────────

        for i, line in enumerate(lines):

            # 1. JSDoc @auth / @requires on a function → check if route is guarded
            if _JSDOC_AUTH.search(line):
                # look ahead up to 10 lines for a route or function definition
                ahead = _line_window(lines, i, i + 10)
                if _EXPRESS_ROUTE.search(ahead) and not _AUTH_MIDDLEWARE.search(ahead):
                    text = f"JSDoc at line {i+1} claims auth/permission but Express route has no auth middleware"
                    _emit(claims, seen, counter, "jsdoc-auth", text, js_file, i + 1, "express_route")

            # 2. Express route with no auth middleware
            if _EXPRESS_ROUTE.search(line):
                window = _line_window(lines, i, i + 5)
                if not _AUTH_MIDDLEWARE.search(window):
                    # Only flag if the route handler is non-trivial (not just a static file serve)
                    if re.search(r'req\.|res\.(?:json|send|render)\s*\(', window):
                        text = f"Express route at line {i+1} has no auth middleware — unauthenticated endpoint"
                        _emit(claims, seen, counter, "express-noauth", text, js_file, i + 1, "express_route")

            # 3. JWT sign without algorithm
            if _JWT_SIGN.search(line):
                window = _line_window(lines, i, i + 8)
                if not _JWT_ALGO.search(window):
                    text = f"jwt.sign() at line {i+1} missing explicit 'algorithms' option — algorithm confusion attack"
                    _emit(claims, seen, counter, "jwt-nochecks", text, js_file, i + 1, "jwt_sign")

            # 4. JWT verify without algorithm
            if _JWT_VERIFY.search(line):
                window = _line_window(lines, i, i + 8)
                if not _JWT_ALGO.search(window):
                    text = f"jwt.verify() at line {i+1} missing explicit 'algorithms' option — algorithm confusion attack"
                    _emit(claims, seen, counter, "jwt-nochecks", text, js_file, i + 1, "jwt_verify")

            # 5. eval / new Function with dynamic argument
            if _EVAL_SINK.search(line):
                if _NON_LITERAL.search(re.sub(r'["\'].*?["\']', '', line)):
                    text = f"eval()/new Function() at line {i+1} with dynamic argument — potential code injection"
                    _emit(claims, seen, counter, "eval-sink", text, js_file, i + 1, "eval")

            # 6. innerHTML / outerHTML / document.write with dynamic value
            if _DOM_SINK.search(line):
                if _NON_LITERAL.search(re.sub(r'["\'].*?["\']', '', line)):
                    text = f"DOM sink (innerHTML/document.write) at line {i+1} with dynamic value — potential XSS"
                    _emit(claims, seen, counter, "eval-sink", text, js_file, i + 1, "dom_sink")

            # 7. Hardcoded secret
            m = _SECRET_VAR.search(line)
            if m and not _SECRET_EXEMPT.search(line):
                text = f"Hardcoded secret/key at line {i+1}: variable name matches secret pattern with literal value"
                _emit(claims, seen, counter, "hardcoded-secret", text, js_file, i + 1, "secret")

            # 8. CORS wildcard
            if _CORS_WILDCARD.search(line):
                text = f"CORS wildcard (origin: '*') at line {i+1} — any origin allowed"
                _emit(claims, seen, counter, "cors-wildcard", text, js_file, i + 1, "cors")

        # ── Pass 2: function-scope patterns ──────────────────────────────────

        for i, line in enumerate(lines):

            # 9. Route handler reads req.body/query but no validation in function body
            if _EXPRESS_ROUTE.search(line):
                window = _line_window(lines, i, i + 40)
                if _REQ_INPUT.search(window) and not _VALIDATION.search(window):
                    text = f"Route at line {i+1} reads req.body/query without input validation/sanitization"
                    _emit(claims, seen, counter, "missing-validation", text, js_file, i + 1, "route_handler")

            # 10. Recursive merge/assign without hasOwnProperty guard
            if _RECURSIVE_MERGE.search(line):
                window = _line_window(lines, i, i + 30)
                if not _HAS_OWN_PROP.search(window):
                    text = f"Merge/assign/extend function at line {i+1} lacks hasOwnProperty guard — prototype pollution"
                    _emit(claims, seen, counter, "proto-pollution", text, js_file, i + 1, "merge_func")

    return claims


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
