#!/usr/bin/env python3
"""
Tests for generated cli-app.
"""

def test_main():
    """Test main function."""
    from main import main
    result = main()
    assert result == 0

def test_import():
    """Test import."""
    import main
    assert hasattr(main, 'main')
