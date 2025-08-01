"""
Basic tests for CodePipeline.
"""

def test_imports():
    """Test that basic imports work."""
    try:
        from codepipeline.logging_config import get_logger
        from codepipeline.orchestrator import run
        assert True
    except ImportError as e:
        assert False, f"Import failed: {e}"

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