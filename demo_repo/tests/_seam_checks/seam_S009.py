"""Auto-generated seam check for S009."""
import pytest

def test_S009_raises_claim():
    """Seam S009: docstring claims raises KeyError but code may not."""
    try:
        from config_loader import load_timeout
    except ImportError:
        pytest.skip("Cannot import config_loader.load_timeout")
    # Call with empty/falsy input to trigger the condition
    with pytest.raises(KeyError):
        load_timeout("")
