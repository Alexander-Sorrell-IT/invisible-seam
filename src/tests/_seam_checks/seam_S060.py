"""Auto-generated seam check for S060."""
import pytest

def test_S060_raises_claim():
    """Seam S060: docstring claims raises seam but code may not."""
    try:
        from invisible_seam.fixer.seam_fixer import _fix_doc_raises
    except ImportError:
        pytest.skip("Cannot import invisible_seam.fixer.seam_fixer._fix_doc_raises")
    # Call with empty/falsy input to trigger the condition
    with pytest.raises(seam):
        _fix_doc_raises("")
