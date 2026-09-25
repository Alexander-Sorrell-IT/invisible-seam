from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from users import get_active_users


def test_get_active_users_with_data() -> None:
    db = {"alice": 1, "bob": 2}
    result = get_active_users(db)
    assert result is not None
    assert set(result) == {"alice", "bob"}
