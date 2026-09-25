from __future__ import annotations


def get_active_users(db: dict) -> list[str]:
    """Returns a list of active user records from the database."""
    if not db:
        return None  # SEAM 1: annotation says list[str], returns None when empty
    return list(db.keys())
