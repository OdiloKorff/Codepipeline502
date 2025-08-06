"""
Standalone tests that don't import the main package.
"""

def test_basic():
    """Basic test that always passes."""
    assert True

def test_math():
    """Simple math test."""
    assert 2 + 2 == 4

def test_string():
    """Simple string test."""
    assert "hello" + " world" == "hello world"

def test_list():
    """Simple list test."""
    assert [1, 2, 3] == [1, 2, 3]

def test_dict():
    """Simple dict test."""
    assert {"a": 1, "b": 2} == {"a": 1, "b": 2}
