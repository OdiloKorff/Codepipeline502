import importlib


def test_import_cli():
    module = importlib.import_module('codepipeline.cli')
    assert module is not None

# Add more contract tests for cli here
