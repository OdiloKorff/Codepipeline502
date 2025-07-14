import os
import pytest

from codepipeline.context_window_manager import token_aware_window

def test_window_disabled():
    os.environ['ENABLE_CONTEXT_WINDOW'] = 'false'
    context = ['foo', 'bar']
    assert token_aware_window(context) == context

def test_window_enabled(monkeypatch):
    os.environ['ENABLE_CONTEXT_WINDOW'] = 'true'
    os.environ['CONTEXT_WINDOW_SIZE'] = '3'
    import codepipeline.context_window_manager as cwm
    cwm.count_tokens = lambda x: len(x)
    context = ['ab', 'cd', 'efg']
    assert token_aware_window(context) == ['ab', 'cd']