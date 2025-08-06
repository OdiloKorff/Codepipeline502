import os

from codepipeline.prompt_planner import token_aware_plan


def test_token_aware_plan_budget_disabled(monkeypatch):
    os.environ['ENABLE_TOKEN_BUDGET'] = 'false'
    prompts = ['a', 'b', 'c']
    assert token_aware_plan(prompts) == prompts

def test_token_aware_plan_budget_enabled(monkeypatch):
    os.environ['ENABLE_TOKEN_BUDGET'] = 'true'
    os.environ['TOKEN_BUDGET_LIMIT'] = '1'
    # Mock count_tokens
    import codepipeline.prompt_planner as pp
    pp.count_tokens = lambda x: len(x)
    prompts = ['aa', 'b', 'c']
    assert token_aware_plan(prompts) == ['aa']
