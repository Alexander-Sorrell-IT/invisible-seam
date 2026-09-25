from __future__ import annotations


def load_api_key(config: dict) -> str:
    """Loads the API key. Returns the api_key from config."""
    # SEAM 3: schema says api_key is required, code silently defaults
    return config.get("api_key", "default_insecure_key")


def load_timeout(config: dict) -> int:
    """Loads the request timeout. Returns timeout from config."""
    # SEAM 4+5 (PARADOX): schema says timeout is REQUIRED *and* has a default of 30
    return config.get("timeout", 30)
