import importlib


def test_import_prompt_planner():
    module = importlib.import_module('codepipeline.prompt_planner')
    assert module is not None

# Add more contract tests for prompt_planner here
