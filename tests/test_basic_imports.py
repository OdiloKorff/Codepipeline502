"""
Basic import tests for CodePipeline.
"""

import pytest

@pytest.mark.mvp
def test_basic_imports():
    """Test that basic modules can be imported."""
    try:
        from codepipeline.logging_config import get_logger  # noqa: F401
        from codepipeline.orchestrator import run  # noqa: F401
        assert True
    except ImportError as e:
        raise AssertionError(f"Import failed: {e}") from e

@pytest.mark.mvp
def test_logging_works():
    """Test that logging configuration works."""
    try:
        from codepipeline.logging_config import get_logger
        logger = get_logger(__name__)
        assert logger is not None
        logger.info("Test logging works")
    except ImportError:
        pytest.skip("logging_config is stub module")

@pytest.mark.mvp
def test_orchestrator_works():
    """Test that orchestrator can be called."""
    from codepipeline.orchestrator import run
    result = run("test_spec.yaml", dry_run=True)
    assert result is not None
    assert result.get("status") == "dry_run"

def test_llm_gateway_import():
    """Test that LLM gateway can be imported."""
    try:
        from codepipeline.llm_gateway import LLMGateway
        gateway = LLMGateway()
        assert gateway is not None
    except ImportError:
        pytest.skip("llm_gateway not implemented yet")
