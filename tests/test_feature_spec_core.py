"""
Gezielte Unit-Tests für FeatureSpec-Kernpfade.
Erhöht Coverage für FeatureSpec-Validierung und -Serialisierung.
"""

import pytest
import tempfile
import json
from pathlib import Path

from codepipeline.feature_spec import FeatureSpec


@pytest.mark.mvp
def test_feature_spec_creation():
    """Test FeatureSpec-Erstellung mit minimalen Daten."""
    spec = FeatureSpec(
        id="TEST-001",
        title="Test Feature",
        version=1,
        goal="Test goal with sufficient length to meet validation requirements",
        target_paths=["codepipeline", "tests"],
        risk_level="low",
        model="gpt-4o-mini",
        token_budget=1000
    )
    
    assert spec.id == "TEST-001"
    assert spec.title == "Test Feature"
    assert spec.version == 1
    assert len(spec.goal) >= 10  # Mindestlänge
    assert spec.target_paths == ["codepipeline", "tests"]


@pytest.mark.mvp
def test_feature_spec_validation():
    """Test FeatureSpec-Validierung."""
    # Gültige Spec
    spec = FeatureSpec(
        id="VALID-001",
        title="Valid Feature",
        version=1,
        goal="Valid goal with sufficient length for validation",
        target_paths=["codepipeline"],
        risk_level="medium",
        model="gpt-4o-mini",
        token_budget=2000
    )
    
    # Validierung sollte erfolgreich sein
    assert spec.id is not None
    assert spec.title is not None
    assert spec.version >= 1


@pytest.mark.mvp
def test_feature_spec_serialization():
    """Test FeatureSpec-Serialisierung."""
    spec = FeatureSpec(
        id="SERIAL-001",
        title="Serialization Test",
        version=1,
        goal="Test serialization with sufficient goal length",
        target_paths=["codepipeline", "qa"],
        risk_level="high",
        model="gpt-4o-mini",
        token_budget=5000,
        reviewers=["reviewer1", "reviewer2"]
    )
    
    # JSON-Serialisierung
    json_data = spec.model_dump_json()
    assert json_data is not None
    assert "SERIAL-001" in json_data
    
    # Dict-Serialisierung
    dict_data = spec.model_dump()
    assert dict_data["id"] == "SERIAL-001"
    assert dict_data["title"] == "Serialization Test"


@pytest.mark.mvp
def test_feature_spec_file_operations():
    """Test FeatureSpec-Datei-Operationen."""
    spec = FeatureSpec(
        id="FILE-001",
        title="File Operations Test",
        version=1,
        goal="Test file operations with sufficient goal length",
        target_paths=["codepipeline"],
        risk_level="low",
        model="gpt-4o-mini",
        token_budget=1000,
        reviewers=["reviewer1"]
    )
    
    # Temporäre Datei erstellen
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(spec.model_dump_json())
        temp_path = f.name
    
    try:
        # Spec aus Datei laden
        loaded_spec = FeatureSpec.from_file(temp_path)
        assert loaded_spec.id == "FILE-001"
        assert loaded_spec.title == "File Operations Test"
    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.mvp
def test_feature_spec_hash_consistency():
    """Test FeatureSpec-Hash-Konsistenz."""
    spec1 = FeatureSpec(
        id="HASH-001",
        title="Hash Test",
        version=1,
        goal="Test hash consistency with sufficient goal length",
        target_paths=["codepipeline"],
        risk_level="low",
        model="gpt-4o-mini",
        token_budget=1000,
        reviewers=["reviewer1"]
    )
    
    spec2 = FeatureSpec(
        id="HASH-001",
        title="Hash Test",
        version=1,
        goal="Test hash consistency with sufficient goal length",
        target_paths=["codepipeline"],
        risk_level="low",
        model="gpt-4o-mini",
        token_budget=1000,
        reviewers=["reviewer1"]
    )
    
    # Hashes sollten identisch sein
    assert spec1.sha256() == spec2.sha256()
    assert len(spec1.sha256()) == 64  # SHA256-Länge


@pytest.mark.mvp
def test_feature_spec_target_paths_validation():
    """Test Target-Paths-Validierung."""
    # Gültige Pfade
    valid_spec = FeatureSpec(
        id="PATHS-001",
        title="Valid Paths",
        version=1,
        goal="Test valid target paths with sufficient goal length",
        target_paths=["codepipeline", "tests", "qa"],
        risk_level="low",
        model="gpt-4o-mini",
        token_budget=1000,
        reviewers=["reviewer1"]
    )
    
    assert len(valid_spec.target_paths) >= 1
    assert all(isinstance(p, str) for p in valid_spec.target_paths)
    assert all("/" not in p for p in valid_spec.target_paths)  # Keine absoluten Pfade
