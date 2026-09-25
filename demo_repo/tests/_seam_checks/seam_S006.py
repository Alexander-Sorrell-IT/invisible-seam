"""Auto-generated seam check for S006."""
import pytest

def test_S006_raises_claim():
    """Seam S006: docstring claims raises KeyError but code may not."""
    try:
        from config_loader import load_api_key
    except ImportError:
        pytest.skip("Cannot import config_loader.load_api_key")
    # Call with empty/falsy input to trigger the condition
    with pytest.raises(KeyError):
        load_api_key("")
