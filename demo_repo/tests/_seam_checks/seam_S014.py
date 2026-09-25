"""Auto-generated seam check for S014."""
import pytest

def test_S014_config_fallback():
    """Seam S014: config field 'timeout' should be required but has a silent default."""
    import importlib
    try:
        mod = importlib.import_module("config_loader")
    except ImportError:
        pytest.skip("Cannot import config_loader")

    # Find a callable that takes a config dict
    import inspect
    loader = None
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        sig = inspect.signature(obj)
        params = list(sig.parameters.keys())
        if params and ("config" in params[0] or "cfg" in params[0] or "settings" in params[0]):
            loader = obj
            break

    if loader is None:
        pytest.skip("No config loader function found in config_loader")

    # Call with empty dict — should raise, but will silently default if seam is real
    with pytest.raises((KeyError, ValueError)):
        loader({})
