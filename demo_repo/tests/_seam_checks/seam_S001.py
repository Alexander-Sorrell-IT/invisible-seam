"""Auto-generated seam check for S001."""
import pytest

def test_S001_raises_claim():
    """Seam S001: docstring claims raises ValueError but code may not."""
    try:
        from auth import authenticate
    except ImportError:
        pytest.skip("Cannot import auth.authenticate")
    # Call with empty/falsy input to trigger the condition
    with pytest.raises(ValueError):
        authenticate("")
