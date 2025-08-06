import importlib


def test_import_rag_core():
    module = importlib.import_module('codepipeline.rag_core')
    assert module is not None

# Add more contract tests for rag_core here
