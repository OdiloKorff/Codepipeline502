import pytest
import importlib

def test_import_metrics():
    module = importlib.import_module('codepipeline.metrics')
    assert module is not None

# Add more contract tests for metrics here