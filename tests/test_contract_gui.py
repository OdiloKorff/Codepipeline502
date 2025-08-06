import importlib


def test_import_gui():
    module = importlib.import_module('codepipeline.gui')
    assert module is not None

# Add more contract tests for gui here
