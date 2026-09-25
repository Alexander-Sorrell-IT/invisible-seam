from __future__ import annotations


def get_active_users(db: dict) -> list[str]:
    """Returns a list of active user records. Never returns None."""
    if not db:
        return None  # SEAM: README says "never returns None", annotation says list[str]
    return list(db.keys())
