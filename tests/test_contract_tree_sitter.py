import importlib


def test_import_tree_sitter():
    module = importlib.import_module('codepipeline.tree_sitter')
    assert module is not None

# Add more contract tests for tree_sitter here
