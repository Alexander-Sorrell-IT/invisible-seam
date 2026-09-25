"""Auto-generated seam check for S072."""
import pytest

def test_S072_raises_claim():
    """Seam S072: docstring claims raises of but code may not."""
    try:
        from invisible_seam.matchers.code_matcher import _function_raises
    except ImportError:
        pytest.skip("Cannot import invisible_seam.matchers.code_matcher._function_raises")
    # Call with empty/falsy input to trigger the condition
    with pytest.raises(of):
        _function_raises("")
