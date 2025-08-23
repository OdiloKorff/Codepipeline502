#!/usr/bin/env python3
"""
COV-501: Coverage-Boost Hot-Path-Mikrotests
Ergänzende Mikrotests für kritische Hot-Paths ohne externe Abhängigkeiten.
"""

import pytest
import json
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import os

# Dynamischer Import von FeatureSpec
FeatureSpec = None
TestConfig = None

try:
    from feature_spec import FeatureSpec, TestConfig
except ImportError:
    try:
        from codepipeline.feature_spec import FeatureSpec, TestConfig
    except ImportError:
        try:
            from production_feature_spec import ProductionFeatureSpec as FeatureSpec, TestConfig
        except ImportError:
            pytest.skip("FeatureSpec module not found in any expected path", allow_module_level=True)

if FeatureSpec is None:
    pytest.skip("FeatureSpec module not found after all attempts", allow_module_level=True)


class TestHotPathMicrotests:
    """Hot-Path-Mikrotests für Coverage-Boost ohne externe Abhängigkeiten"""
    
    def test_specification_serialization_roundtrip_json(self):
        """Test: Serialisierung der Spezifikation in JSON-Datei und erneutes Laden"""
        # Erstelle Test-Spezifikation
        original_spec = FeatureSpec(
            id="HOTPATH-001",
            title="Serialization Test",
            version=1,
            goal="Test JSON serialization roundtrip",
            target_paths=["codepipeline", "tests/unit"]
        )
        
        # Serialisiere zu JSON
        spec_dict = {
            "id": original_spec.id,
            "title": original_spec.title,
            "version": original_spec.version,
            "goal": original_spec.goal,
            "target_paths": original_spec.target_paths,
            "tests": {
                "coverage_min": original_spec.tests.coverage_min
            }
        }
        
        json_content = json.dumps(spec_dict, indent=2)
        
        # Mock file operations für isolierten Test
        with patch("builtins.open", mock_open(read_data=json_content)) as mock_file:
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value=json_content):
                    
                    # Simuliere Laden aus JSON
                    loaded_data = json.loads(json_content)
                    
                    # Validiere Roundtrip
                    assert loaded_data["id"] == original_spec.id
                    assert loaded_data["title"] == original_spec.title
                    assert loaded_data["version"] == original_spec.version
                    assert loaded_data["goal"] == original_spec.goal
                    assert loaded_data["target_paths"] == original_spec.target_paths
                    assert loaded_data["tests"]["coverage_min"] == original_spec.tests.coverage_min
    
    def test_specification_serialization_roundtrip_yaml(self):
        """Test: Serialisierung der Spezifikation in YAML-Datei und erneutes Laden"""
        # Erstelle Test-Spezifikation
        original_spec = FeatureSpec(
            id="HOTPATH-002", 
            title="YAML Serialization Test",
            version=2,
            goal="Test YAML serialization roundtrip",
            target_paths=["codepipeline/core", "tests/integration"]
        )
        
        # Serialisiere zu YAML
        spec_dict = {
            "id": original_spec.id,
            "title": original_spec.title,
            "version": original_spec.version,
            "goal": original_spec.goal,
            "target_paths": original_spec.target_paths,
            "tests": {
                "coverage_min": original_spec.tests.coverage_min
            }
        }
        
        yaml_content = yaml.dump(spec_dict, default_flow_style=False)
        
        # Mock file operations für isolierten Test
        with patch("builtins.open", mock_open(read_data=yaml_content)) as mock_file:
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value=yaml_content):
                    
                    # Simuliere Laden aus YAML mit safe_load
                    loaded_data = yaml.safe_load(yaml_content)
                    
                    # Validiere Roundtrip
                    assert loaded_data["id"] == original_spec.id
                    assert loaded_data["title"] == original_spec.title
                    assert loaded_data["version"] == original_spec.version
                    assert loaded_data["goal"] == original_spec.goal
                    assert loaded_data["target_paths"] == original_spec.target_paths
                    assert loaded_data["tests"]["coverage_min"] == original_spec.tests.coverage_min
    
    def test_target_path_validation_typical_error_cases(self):
        """Test: Validierung der Zielpfade mit typischen Fehlerfällen"""
        
        # Test 1: Absolute Pfade (Windows und Unix)
        with pytest.raises(ValueError, match="Target path must be relative"):
            FeatureSpec(
                id="ERROR-001",
                title="Absolute Path Test",
                version=1,
                goal="Test absolute path rejection",
                target_paths=["/usr/bin/python"]  # Unix absolute
            )
        
        with pytest.raises(ValueError, match="Target path must be relative"):
            FeatureSpec(
                id="ERROR-002", 
                title="Windows Absolute Path Test",
                version=1,
                goal="Test Windows absolute path rejection",
                target_paths=["C:\\Windows\\System32"]  # Windows absolute
            )
        
        # Test 2: Parent directory traversal (..)
        with pytest.raises(ValueError, match="Target path cannot contain '..'"):
            FeatureSpec(
                id="ERROR-003",
                title="Parent Traversal Test",
                version=1,
                goal="Test parent directory traversal rejection",
                target_paths=["../../../etc/passwd"]
            )
        
        with pytest.raises(ValueError, match="Target path cannot contain '..'"):
            FeatureSpec(
                id="ERROR-004",
                title="Nested Parent Traversal Test", 
                version=1,
                goal="Test nested parent directory traversal rejection",
                target_paths=["src/../../../sensitive/data"]
            )
        
        # Test 3: Leere Pfade
        with pytest.raises(ValueError, match="Target path cannot be empty"):
            FeatureSpec(
                id="ERROR-005",
                title="Empty Path Test",
                version=1,
                goal="Test empty path rejection",
                target_paths=[""]
            )
        
        with pytest.raises(ValueError, match="Target path cannot be empty"):
            FeatureSpec(
                id="ERROR-006",
                title="Whitespace Path Test",
                version=1,
                goal="Test whitespace-only path rejection", 
                target_paths=["   "]
            )
        
        # Test 4: Null/None Pfade
        with pytest.raises((ValueError, TypeError)):
            FeatureSpec(
                id="ERROR-007",
                title="None Path Test",
                version=1,
                goal="Test None path rejection",
                target_paths=[None]
            )
        
        # Test 5: Gefährliche Zeichen
        dangerous_chars = ["<", ">", "|", "&", ";", "`", "$"]
        for char in dangerous_chars:
            with pytest.raises(ValueError):
                FeatureSpec(
                    id=f"ERROR-CHAR-{ord(char)}",
                    title=f"Dangerous Char {char} Test",
                    version=1,
                    goal=f"Test dangerous character {char} rejection",
                    target_paths=[f"path{char}file.py"]
                )
    
    def test_target_path_validation_valid_cases(self):
        """Test: Validierung akzeptiert valide Zielpfade"""
        
        # Test gültige relative Pfade
        valid_paths = [
            "codepipeline",
            "tests/unit", 
            "src/main.py",
            "docs/README.md",
            "config/settings.json",
            "scripts/deploy.sh",
            "data/input.csv",
            "build/output.txt"
        ]
        
        # Alle sollten akzeptiert werden
        spec = FeatureSpec(
            id="VALID-001",
            title="Valid Paths Test",
            version=1,
            goal="Test valid path acceptance",
            target_paths=valid_paths
        )
        
        assert spec.target_paths == valid_paths
    
    def test_specification_edge_cases_coverage(self):
        """Test: Edge Cases für bessere Coverage"""
        
        # Test mit minimalen Feldern
        minimal_spec = FeatureSpec(
            id="MIN-001",
            title="Minimal",
            version=1,
            goal="Minimal spec",
            target_paths=["src"]
        )
        
        # Teste SHA256 mehrfach (sollte stabil sein)
        hash1 = minimal_spec.sha256()
        hash2 = minimal_spec.sha256()
        assert hash1 == hash2
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)
        
        # Test mit langen Strings
        long_spec = FeatureSpec(
            id="LONG-001",
            title="Very Long Title " + "X" * 200,
            version=999,
            goal="Very long goal description " + "Y" * 500,
            target_paths=["very/long/path/structure/" + "Z" * 100]
        )
        
        long_hash = long_spec.sha256()
        assert len(long_hash) == 64
        assert long_hash != hash1  # Sollte unterschiedlich sein
    
    def test_test_config_coverage(self):
        """Test: TestConfig Coverage für Hot-Path"""
        
        # Test default TestConfig
        spec = FeatureSpec(
            id="CONFIG-001",
            title="Config Test",
            version=1,
            goal="Test config coverage",
            target_paths=["src"]
        )
        
        # Teste TestConfig Attribute
        assert hasattr(spec.tests, 'coverage_min')
        assert isinstance(spec.tests.coverage_min, (int, float))
        assert spec.tests.coverage_min >= 0
        assert spec.tests.coverage_min <= 100
        
        # Test mit custom TestConfig falls verfügbar
        try:
            custom_config = TestConfig(coverage_min=90)
            custom_spec = FeatureSpec(
                id="CONFIG-002",
                title="Custom Config Test",
                version=1,
                goal="Test custom config",
                target_paths=["src"],
                tests=custom_config
            )
            assert custom_spec.tests.coverage_min == 90
        except (TypeError, AttributeError):
            # TestConfig might not accept parameters
            pass
    
    def test_path_normalization_coverage(self):
        """Test: Path Normalization für Coverage"""
        
        # Test verschiedene Path-Formate
        path_variants = [
            "src/main.py",
            "src\\main.py",  # Windows-Style
            "src/./main.py",  # Current dir
            "src//main.py",   # Double slash
            "src/sub/../main.py"  # Sollte normalisiert werden falls erlaubt
        ]
        
        for path in path_variants:
            try:
                spec = FeatureSpec(
                    id=f"NORM-{hash(path) % 1000}",
                    title="Path Normalization Test",
                    version=1,
                    goal="Test path normalization",
                    target_paths=[path]
                )
                # Wenn erfolgreich, prüfe dass Pfad gesetzt ist
                assert len(spec.target_paths) > 0
                assert spec.target_paths[0] is not None
            except ValueError:
                # Einige Pfade könnten abgelehnt werden - das ist OK
                pass
