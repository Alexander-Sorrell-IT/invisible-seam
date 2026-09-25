"""Auto-generated seam check for S003."""
import pytest

def test_S003_raises_claim():
    """Seam S003: docstring claims raises ValueError but code may not."""
    try:
        from auth import authenticate
    except ImportError:
        pytest.skip("Cannot import auth.authenticate")
    # Call with empty/falsy input to trigger the condition
    with pytest.raises(ValueError):
        authenticate("")
