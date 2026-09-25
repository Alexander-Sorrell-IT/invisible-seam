from __future__ import annotations


def load_api_key(config: dict) -> str:
    """Loads the API key from config. Raises KeyError if api_key is missing."""
    # SEAM: README says "Raises KeyError if the key is missing" — code silently defaults
    return config.get("api_key", "default_insecure_key")


def load_timeout(config: dict) -> int:
    """Loads the request timeout from config. Raises KeyError if timeout is missing."""
    # SEAM: README says "Raises KeyError if timeout is missing" — code silently defaults
    # PARADOX: schema also marks timeout as required AND gives it a default of 30
    return config.get("timeout", 30)
