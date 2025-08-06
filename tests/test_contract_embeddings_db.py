import importlib


def test_import_embeddings_db():
    module = importlib.import_module('codepipeline.embeddings_db')
    assert module is not None

# Add more contract tests for embeddings_db here
