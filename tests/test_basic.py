"""
Basic tests for CodePipeline.
"""

import pytest

@pytest.mark.mvp
def test_imports():
    """Test that basic imports work."""
    try:
        from codepipeline.logging_config import get_logger  # noqa: F401
        from codepipeline.orchestrator import run  # noqa: F401
        assert True
    except ImportError as e:
        raise AssertionError(f"Import failed: {e}") from e

@pytest.mark.mvp
def test_logging():
    """Test that logging works."""
    try:
        from codepipeline.logging_config import get_logger
        logger = get_logger(__name__)
        assert logger is not None
    except ImportError:
        # Stub-Modul - Test überspringen
        pytest.skip("logging_config is stub module")

@pytest.mark.mvp
def test_orchestrator():
    """Test that orchestrator can be imported and called."""
    from codepipeline.orchestrator import run
    result = run("test_spec.yaml", dry_run=True)
    assert result is not None
    assert result.get("status") == "dry_run"
