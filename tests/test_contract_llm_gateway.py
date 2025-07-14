import pytest
import importlib

def test_import_llm_gateway():
    module = importlib.import_module('codepipeline.llm_gateway')
    assert module is not None

# Add more contract tests for llm_gateway here