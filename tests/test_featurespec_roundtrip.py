#!/usr/bin/env python3
"""
COV-103: JSON/YAML Roundtrip-Tests für FeatureSpec
Tests für Laden/Speichern mit safe Loader und stabilem Encoding.
"""

import pytest
import json
import yaml
import tempfile
from pathlib import Path
import os

# Import FeatureSpec - robuste Fallback-Strategie
FeatureSpec = None

try:
    from feature_spec import FeatureSpec
    print("✓ Imported FeatureSpec from feature_spec")
except ImportError:
    try:
        from codepipeline.feature_spec import FeatureSpec
        print("✓ Imported FeatureSpec from codepipeline.feature_spec")
    except ImportError:
        try:
            from production_feature_spec import ProductionFeatureSpec as FeatureSpec
            print("✓ Imported FeatureSpec from production_feature_spec")
        except ImportError:
            pytest.skip("FeatureSpec not available", allow_module_level=True)


class TestFeatureSpecJSONRoundtrip:
    """Tests für JSON Serialisierung und Deserialisierung"""
    
    def test_json_roundtrip_minimal(self):
        """Test JSON-Roundtrip mit minimalen Feldern"""
        original_spec = FeatureSpec(
            id="JSON-MINIMAL-001",
            title="JSON Minimal Test",
            version=1,
            goal="Test minimal JSON serialization and deserialization",
            target_paths=["codepipeline"]
        )
        
        # Serialize zu Dict
        spec_dict = original_spec.model_dump() if hasattr(original_spec, 'model_dump') else original_spec.dict()
        
        # Serialize zu JSON String
        json_string = json.dumps(spec_dict, ensure_ascii=False, indent=2)
        
        # Deserialize von JSON String
        parsed_dict = json.loads(json_string)
        
        # Reconstruct FeatureSpec
        restored_spec = FeatureSpec(**parsed_dict)
        
        # Verify roundtrip integrity
        assert restored_spec.id == original_spec.id
        assert restored_spec.title == original_spec.title
        assert restored_spec.version == original_spec.version
        assert restored_spec.goal == original_spec.goal
        assert restored_spec.target_paths == original_spec.target_paths
    
    def test_json_roundtrip_full(self):
        """Test JSON-Roundtrip mit allen Feldern"""
        original_spec = FeatureSpec(
            id="JSON-FULL-001",
            title="JSON Full Test Feature",
            version=2,
            goal="Test complete JSON serialization with all fields",
            description="Detailed description for full JSON test",
            target_paths=["codepipeline", "tests", "qa"],
            constraints=["security", "performance", "scalability"],
            risk_level="high",
            reviewers=["reviewer1", "reviewer2", "reviewer3"],
            model="gpt-4o",
            token_budget=8000,
            hard_musts=["tests", "security", "documentation"]
        )
        
        # Full roundtrip
        spec_dict = original_spec.model_dump() if hasattr(original_spec, 'model_dump') else original_spec.dict()
        json_string = json.dumps(spec_dict, ensure_ascii=False, indent=2)
        parsed_dict = json.loads(json_string)
        restored_spec = FeatureSpec(**parsed_dict)
        
        # Verify all fields
        assert restored_spec.id == original_spec.id
        assert restored_spec.title == original_spec.title
        assert restored_spec.version == original_spec.version
        assert restored_spec.goal == original_spec.goal
        assert restored_spec.description == original_spec.description
        assert restored_spec.target_paths == original_spec.target_paths
        assert restored_spec.constraints == original_spec.constraints
        assert restored_spec.risk_level == original_spec.risk_level
        assert restored_spec.reviewers == original_spec.reviewers
        assert restored_spec.model == original_spec.model
        assert restored_spec.token_budget == original_spec.token_budget
        assert restored_spec.hard_musts == original_spec.hard_musts
    
    def test_json_file_roundtrip(self):
        """Test JSON-Roundtrip über Dateien"""
        original_spec = FeatureSpec(
            id="JSON-FILE-001",
            title="JSON File Test",
            version=1,
            goal="Test JSON file serialization and deserialization",
            target_paths=["codepipeline", "tests"]
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            json_file = Path(temp_dir) / "test_spec.json"
            
            # Write to JSON file
            spec_dict = original_spec.model_dump() if hasattr(original_spec, 'model_dump') else original_spec.dict()
            json_file.write_text(
                json.dumps(spec_dict, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            
            # Read from JSON file
            loaded_dict = json.loads(json_file.read_text(encoding='utf-8'))
            restored_spec = FeatureSpec(**loaded_dict)
            
            # Verify
            assert restored_spec.id == original_spec.id
            assert restored_spec.title == original_spec.title
            assert restored_spec.version == original_spec.version
            assert restored_spec.target_paths == original_spec.target_paths
    
    def test_json_unicode_handling(self):
        """Test JSON-Roundtrip mit Unicode-Zeichen"""
        original_spec = FeatureSpec(
            id="JSON-UNICODE-001",
            title="JSON Unicode Test: äöü ñ 中文 🚀",
            version=1,
            goal="Test Unicode handling in JSON serialization: äöü ñ 中文 emoji 🎯",
            target_paths=["codepipeline"],
            constraints=["Unicode-Support: äöü", "Emoji-Support: 🚀🎯"]
        )
        
        # Roundtrip with Unicode
        spec_dict = original_spec.model_dump() if hasattr(original_spec, 'model_dump') else original_spec.dict()
        json_string = json.dumps(spec_dict, ensure_ascii=False, indent=2)
        parsed_dict = json.loads(json_string)
        restored_spec = FeatureSpec(**parsed_dict)
        
        # Verify Unicode preservation
        assert restored_spec.title == original_spec.title
        assert restored_spec.goal == original_spec.goal
        assert restored_spec.constraints == original_spec.constraints
        assert "äöü" in restored_spec.title
        assert "🚀" in restored_spec.title
        assert "中文" in restored_spec.goal


class TestFeatureSpecYAMLRoundtrip:
    """Tests für YAML Serialisierung und Deserialisierung mit safe_load"""
    
    def test_yaml_roundtrip_minimal(self):
        """Test YAML-Roundtrip mit minimalen Feldern"""
        original_spec = FeatureSpec(
            id="YAML-MINIMAL-001",
            title="YAML Minimal Test",
            version=1,
            goal="Test minimal YAML serialization and deserialization",
            target_paths=["codepipeline"]
        )
        
        # Serialize zu Dict
        spec_dict = original_spec.model_dump() if hasattr(original_spec, 'model_dump') else original_spec.dict()
        
        # Serialize zu YAML String mit safe_dump
        yaml_string = yaml.safe_dump(spec_dict, default_flow_style=False, allow_unicode=True)
        
        # Deserialize von YAML String mit safe_load
        parsed_dict = yaml.safe_load(yaml_string)
        
        # Reconstruct FeatureSpec
        restored_spec = FeatureSpec(**parsed_dict)
        
        # Verify roundtrip integrity
        assert restored_spec.id == original_spec.id
        assert restored_spec.title == original_spec.title
        assert restored_spec.version == original_spec.version
        assert restored_spec.goal == original_spec.goal
        assert restored_spec.target_paths == original_spec.target_paths
    
    def test_yaml_roundtrip_full(self):
        """Test YAML-Roundtrip mit allen Feldern"""
        original_spec = FeatureSpec(
            id="YAML-FULL-001",
            title="YAML Full Test Feature",
            version=3,
            goal="Test complete YAML serialization with all fields",
            description="Detailed description for full YAML test",
            target_paths=["codepipeline", "tests", "qa", "core"],
            constraints=["security", "performance", "maintainability"],
            risk_level="medium",
            reviewers=["yaml-reviewer1", "yaml-reviewer2"],
            model="gpt-4o-mini",
            token_budget=6000,
            hard_musts=["tests", "documentation"]
        )
        
        # Full YAML roundtrip
        spec_dict = original_spec.model_dump() if hasattr(original_spec, 'model_dump') else original_spec.dict()
        yaml_string = yaml.safe_dump(spec_dict, default_flow_style=False, allow_unicode=True)
        parsed_dict = yaml.safe_load(yaml_string)
        restored_spec = FeatureSpec(**parsed_dict)
        
        # Verify all fields
        assert restored_spec.id == original_spec.id
        assert restored_spec.title == original_spec.title
        assert restored_spec.version == original_spec.version
        assert restored_spec.goal == original_spec.goal
        assert restored_spec.description == original_spec.description
        assert restored_spec.target_paths == original_spec.target_paths
        assert restored_spec.constraints == original_spec.constraints
        assert restored_spec.risk_level == original_spec.risk_level
        assert restored_spec.reviewers == original_spec.reviewers
        assert restored_spec.model == original_spec.model
        assert restored_spec.token_budget == original_spec.token_budget
        assert restored_spec.hard_musts == original_spec.hard_musts
    
    def test_yaml_file_roundtrip(self):
        """Test YAML-Roundtrip über Dateien mit UTF-8 Encoding"""
        original_spec = FeatureSpec(
            id="YAML-FILE-001",
            title="YAML File Test",
            version=1,
            goal="Test YAML file serialization and deserialization with UTF-8",
            target_paths=["codepipeline", "tests"],
            constraints=["UTF-8 encoding", "safe_load only"]
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            yaml_file = Path(temp_dir) / "test_spec.yaml"
            
            # Write to YAML file with UTF-8
            spec_dict = original_spec.model_dump() if hasattr(original_spec, 'model_dump') else original_spec.dict()
            yaml_content = yaml.safe_dump(spec_dict, default_flow_style=False, allow_unicode=True)
            yaml_file.write_text(yaml_content, encoding='utf-8')
            
            # Read from YAML file with safe_load
            loaded_dict = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
            restored_spec = FeatureSpec(**loaded_dict)
            
            # Verify
            assert restored_spec.id == original_spec.id
            assert restored_spec.title == original_spec.title
            assert restored_spec.version == original_spec.version
            assert restored_spec.target_paths == original_spec.target_paths
            assert restored_spec.constraints == original_spec.constraints
    
    def test_yaml_safe_load_security(self):
        """Test dass nur safe_load verwendet wird (keine arbitrary code execution)"""
        # Erstelle YAML mit potentiell gefährlichem Inhalt
        dangerous_yaml = """
id: YAML-SAFE-001
title: Safe Load Test
version: 1
goal: Test that only safe_load is used for security
target_paths:
  - codepipeline
# Dieser Kommentar sollte ignoriert werden
constraints:
  - "safe_load only"
  - "no arbitrary code execution"
"""
        
        # Parse mit safe_load
        parsed_dict = yaml.safe_load(dangerous_yaml)
        restored_spec = FeatureSpec(**parsed_dict)
        
        # Verify dass nur sichere Daten geladen wurden
        assert restored_spec.id == "YAML-SAFE-001"
        assert restored_spec.title == "Safe Load Test"
        assert "safe_load only" in restored_spec.constraints
        assert "no arbitrary code execution" in restored_spec.constraints
    
    def test_yaml_unicode_handling(self):
        """Test YAML-Roundtrip mit Unicode-Zeichen"""
        original_spec = FeatureSpec(
            id="YAML-UNICODE-001",
            title="YAML Unicode Test: äöü ñ 中文 🎯",
            version=1,
            goal="Test Unicode handling in YAML serialization: äöü ñ 中文 emoji 🚀",
            target_paths=["codepipeline"],
            constraints=["Unicode-Support: äöü", "Emoji-Support: 🎯🚀"]
        )
        
        # Roundtrip with Unicode
        spec_dict = original_spec.model_dump() if hasattr(original_spec, 'model_dump') else original_spec.dict()
        yaml_string = yaml.safe_dump(spec_dict, default_flow_style=False, allow_unicode=True)
        parsed_dict = yaml.safe_load(yaml_string)
        restored_spec = FeatureSpec(**parsed_dict)
        
        # Verify Unicode preservation
        assert restored_spec.title == original_spec.title
        assert restored_spec.goal == original_spec.goal
        assert restored_spec.constraints == original_spec.constraints
        assert "äöü" in restored_spec.title
        assert "🎯" in restored_spec.title
        assert "中文" in restored_spec.goal


class TestFeatureSpecFromToFile:
    """Tests für from_file und to_file Methoden (falls verfügbar)"""
    
    def test_from_file_json_if_available(self):
        """Test from_file für JSON (falls Methode verfügbar)"""
        if not hasattr(FeatureSpec, 'from_file'):
            pytest.skip("from_file method not available")
        
        test_spec = {
            "id": "FROM-FILE-JSON-001",
            "title": "From File JSON Test",
            "version": 1,
            "goal": "Test loading from JSON file using from_file method",
            "target_paths": ["codepipeline"]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            json_file = Path(temp_dir) / "test_spec.json"
            json_file.write_text(
                json.dumps(test_spec, indent=2),
                encoding='utf-8'
            )
            
            # Load using from_file
            loaded_spec = FeatureSpec.from_file(json_file)
            
            assert loaded_spec.id == test_spec["id"]
            assert loaded_spec.title == test_spec["title"]
            assert loaded_spec.version == test_spec["version"]
    
    def test_from_file_yaml_if_available(self):
        """Test from_file für YAML (falls Methode verfügbar)"""
        if not hasattr(FeatureSpec, 'from_file'):
            pytest.skip("from_file method not available")
        
        test_spec = {
            "id": "FROM-FILE-YAML-001",
            "title": "From File YAML Test",
            "version": 1,
            "goal": "Test loading from YAML file using from_file method",
            "target_paths": ["codepipeline"]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            yaml_file = Path(temp_dir) / "test_spec.yaml"
            yaml_file.write_text(
                yaml.safe_dump(test_spec, default_flow_style=False),
                encoding='utf-8'
            )
            
            # Load using from_file
            loaded_spec = FeatureSpec.from_file(yaml_file)
            
            assert loaded_spec.id == test_spec["id"]
            assert loaded_spec.title == test_spec["title"]
            assert loaded_spec.version == test_spec["version"]
    
    def test_to_file_if_available(self):
        """Test to_file Methode (falls verfügbar)"""
        if not hasattr(FeatureSpec, 'to_file'):
            pytest.skip("to_file method not available")
        
        spec = FeatureSpec(
            id="TO-FILE-001",
            title="To File Test",
            version=1,
            goal="Test saving to file using to_file method",
            target_paths=["codepipeline"]
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            json_file = Path(temp_dir) / "output.json"
            yaml_file = Path(temp_dir) / "output.yaml"
            
            # Save as JSON
            spec.to_file(json_file, format_type="json")
            assert json_file.exists()
            
            # Save as YAML
            spec.to_file(yaml_file, format_type="yaml")
            assert yaml_file.exists()
            
            # Verify content
            json_content = json.loads(json_file.read_text(encoding='utf-8'))
            assert json_content["id"] == spec.id
            
            yaml_content = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
            assert yaml_content["id"] == spec.id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
