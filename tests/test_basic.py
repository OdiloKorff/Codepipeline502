"""
Basic tests for CodePipeline.
"""

def test_imports():
    """Test that basic imports work."""
    try:
        from codepipeline.logging_config import get_logger  # noqa: F401
        from codepipeline.orchestrator import run  # noqa: F401
        assert True
    except ImportError as e:
        raise AssertionError(f"Import failed: {e}") from e

def test_logging():
    """Test that logging works."""
    from codepipeline.logging_config import get_logger
    logger = get_logger(__name__)
    assert logger is not None

def test_orchestrator():
    """Test that orchestrator can be imported and called."""
    from codepipeline.orchestrator import run
    result = run()
    assert result is True
