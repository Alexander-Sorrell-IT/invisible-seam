from __future__ import annotations


def authenticate(token: str) -> bool:
    """Authenticates a token. Raises ValueError if token is empty."""
    if not token:
        return False  # SEAM 2: docstring says raises ValueError, code returns False
    return token.startswith("valid_")
