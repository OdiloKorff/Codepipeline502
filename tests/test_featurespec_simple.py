#!/usr/bin/env python3
"""
Einfache FeatureSpec Tests die garantiert funktionieren.
COV-103: Substanzielle Basisabdeckung.
"""

import pytest
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct import
from feature_spec import FeatureSpec


def test_featurespec_construction():
    """Test FeatureSpec Konstruktion mit minimalen Feldern"""
    spec = FeatureSpec(
        id="SIMPLE-001",
        title="Simple Test Feature",
        version=1,
        goal="Test simple construction with required fields",
        target_paths=["codepipeline"]
    )
    
    assert spec.id == "SIMPLE-001"
    assert spec.title == "Simple Test Feature"
    assert spec.version == 1
    assert spec.goal == "Test simple construction with required fields"
    assert spec.target_paths == ["codepipeline"]


def test_featurespec_sha256():
    """Test dass sha256() 64 Hex-Zeichen zurückgibt"""
    spec = FeatureSpec(
        id="SHA256-001",
        title="SHA256 Test",
        version=1,
        goal="Test SHA256 hash generation",
        target_paths=["codepipeline"]
    )
    
    hash_value = spec.sha256()
    assert len(hash_value) == 64
    assert all(c in '0123456789abcdef' for c in hash_value)


def test_featurespec_target_paths():
    """Test erlaubte Zielpfade werden akzeptiert"""
    allowed_paths = [
        ["codepipeline"],
        ["tests"],
        ["codepipeline", "tests"],
        ["qa"],
        ["core"]
    ]
    
    for paths in allowed_paths:
        spec = FeatureSpec(
            id="PATHS-001",
            title="Path Test",
            version=1,
            goal="Test allowed target paths",
            target_paths=paths
        )
        assert spec.target_paths == paths


def test_featurespec_invalid_paths():
    """Test dass gefährliche Pfade abgelehnt werden"""
    invalid_paths = [
        [".."],
        ["../parent"],
        ["/absolute"]
    ]
    
    for paths in invalid_paths:
        with pytest.raises(Exception):
            FeatureSpec(
                id="INVALID-001",
                title="Invalid Path Test",
                version=1,
                goal="Test invalid path rejection",
                target_paths=paths
            )


def test_featurespec_json_roundtrip():
    """Test JSON-Serialisierung und Deserialisierung"""
    import json
    
    original = FeatureSpec(
        id="JSON-001",
        title="JSON Test",
        version=1,
        goal="Test JSON serialization",
        target_paths=["codepipeline", "tests"]
    )
    
    # Serialize
    data = original.model_dump() if hasattr(original, 'model_dump') else original.dict()
    json_str = json.dumps(data)
    
    # Deserialize
    parsed = json.loads(json_str)
    restored = FeatureSpec(**parsed)
    
    assert restored.id == original.id
    assert restored.title == original.title
    assert restored.version == original.version


def test_featurespec_yaml_roundtrip():
    """Test YAML-Serialisierung mit safe_load"""
    import yaml
    
    original = FeatureSpec(
        id="YAML-001",
        title="YAML Test",
        version=1,
        goal="Test YAML serialization with safe_load",
        target_paths=["codepipeline"]
    )
    
    # Serialize
    data = original.model_dump() if hasattr(original, 'model_dump') else original.dict()
    yaml_str = yaml.safe_dump(data, default_flow_style=False)
    
    # Deserialize with safe_load
    parsed = yaml.safe_load(yaml_str)
    restored = FeatureSpec(**parsed)
    
    assert restored.id == original.id
    assert restored.title == original.title
    assert restored.version == original.version


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
