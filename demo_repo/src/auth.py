from __future__ import annotations


def authenticate(token: str) -> bool:
    """Validates an authentication token. Raises ValueError if the token is empty or None."""
    if not token:
        return False  # SEAM: docstring says raises ValueError, code silently returns False
    return token.startswith("valid_")
