"""Auto-generated seam check for S008."""
import pytest

def test_S008_type_hint_conflict():
    """Seam S008: annotation says list[str] but behavior differs."""
    try:
        from users import get_active_users
    except ImportError:
        pytest.skip("Cannot import users.get_active_users")
    import inspect
    sig = inspect.signature(get_active_users)
    params = {
        name: None
        for name, param in sig.parameters.items()
        if param.default is inspect.Parameter.empty
    }
    try:
        result = get_active_users(**params)
    except Exception:
        pytest.skip("Function raised during check call")
    # If the annotation is correct, this assertion should pass.
    # If the seam is real, it will fail (e.g. None returned for list[str]).
    assert result is not None, (
        f"SEAM CONFIRMED: 'get_active_users' returned None but annotation says 'list[str]'"
    )
