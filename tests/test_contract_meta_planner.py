import importlib


def test_import_meta_planner():
    module = importlib.import_module('codepipeline.meta_planner')
    assert module is not None

# Add more contract tests for meta_planner here
