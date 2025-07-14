import pytest
import importlib

def test_import_gui_bridge():
    module = importlib.import_module('codepipeline.gui_bridge')
    assert module is not None

# Add more contract tests for gui_bridge here