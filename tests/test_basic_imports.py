"""
Basic import tests for CodePipeline.
"""

def test_basic_imports():
    """Test that basic modules can be imported."""
    try:
        from codepipeline.logging_config import get_logger
        from codepipeline.orchestrator import run
        from codepipeline.llm_gateway import LLMGateway
        assert True
    except ImportError as e:
        assert False, f"Import failed: {e}"

def test_logging_works():
    """Test that logging configuration works."""
    from codepipeline.logging_config import get_logger
    logger = get_logger(__name__)
    assert logger is not None
    logger.info("Test logging works")

def test_orchestrator_works():
    """Test that orchestrator can be called."""
    from codepipeline.orchestrator import run
    result = run()
    assert result is True

def test_llm_gateway_import():
    """Test that LLM gateway can be imported."""
    from codepipeline.llm_gateway import LLMGateway
    gateway = LLMGateway()
    assert gateway is not None 