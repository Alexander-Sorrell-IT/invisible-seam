"""Auto-generated seam check for S011."""
import pytest

def test_S011_type_hint_conflict():
    """Seam S011: annotation says object but behavior differs."""
    try:
        from config.schema import unknown_function
    except ImportError:
        pytest.skip("Cannot import config.schema.unknown_function")
    import inspect
    sig = inspect.signature(unknown_function)
    params = {
        name: None
        for name, param in sig.parameters.items()
        if param.default is inspect.Parameter.empty
    }
    try:
        result = unknown_function(**params)
    except Exception:
        pytest.skip("Function raised during check call")
    # If the annotation is correct, this assertion should pass.
    # If the seam is real, it will fail (e.g. None returned for list[str]).
    assert result is not None, (
        f"SEAM CONFIRMED: 'unknown_function' returned None but annotation says 'object'"
    )
