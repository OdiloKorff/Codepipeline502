import importlib


def test_import_deployer():
    module = importlib.import_module('codepipeline.deployer')
    assert module is not None

# Add more contract tests for deployer here
