#!/usr/bin/env python3
"""
COV-103: Kern-Unit-Tests für FeatureSpec
Substanzielle Basisabdeckung mit echten Imports und Tests.
"""

import pytest
import json
import yaml
import hashlib
from pathlib import Path
import tempfile
import os

# Import FeatureSpec - robuste Fallback-Strategie
FeatureSpec = None
TestConfig = None

try:
    # Versuche direkten Import
    from feature_spec import FeatureSpec, TestConfig
    print("✓ Imported from feature_spec")
except ImportError:
    try:
        # Versuche codepipeline.feature_spec
        from codepipeline.feature_spec import FeatureSpec, TestConfig
        print("✓ Imported from codepipeline.feature_spec")
    except ImportError:
        try:
            # Versuche production_feature_spec
            from production_feature_spec import ProductionFeatureSpec as FeatureSpec, TestConfig
            print("✓ Imported from production_feature_spec")
        except ImportError:
            # Skip alle Tests wenn FeatureSpec nicht verfügbar
            pytest.skip("FeatureSpec not available", allow_module_level=True)


class TestFeatureSpecConstruction:
    """Tests für FeatureSpec Konstruktion mit minimalen Feldern"""
    
    def test_minimal_construction(self):
        """Test Konstruktion mit minimalen erforderlichen Feldern"""
        spec = FeatureSpec(
            id="TEST-001",
            title="Minimal Test Feature",
            version=1,
            goal="Test minimal construction with required fields only",
            target_paths=["codepipeline"]
        )
        
        # Basis-Attribute prüfen
        assert spec.id == "TEST-001"
        assert spec.title == "Minimal Test Feature"
        assert spec.version == 1
        assert spec.goal == "Test minimal construction with required fields only"
        assert spec.target_paths == ["codepipeline"]
        
        # Default-Werte prüfen
        assert spec.risk_level in ["low", "medium", "high"]
        assert isinstance(spec.constraints, list)
        assert isinstance(spec.reviewers, list)
    
    def test_construction_with_all_fields(self):
        """Test Konstruktion mit allen optionalen Feldern"""
        spec = FeatureSpec(
            id="FULL-TEST-001",
            title="Full Feature Test",
            version=2,
            goal="Test construction with all optional fields included",
            description="Detailed description of the feature",
            target_paths=["codepipeline", "tests"],
            constraints=["constraint1", "constraint2"],
            risk_level="high",
            reviewers=["reviewer1", "reviewer2"],
            model="gpt-4o",
            token_budget=5000,
            hard_musts=["security", "performance"]
        )
        
        assert spec.id == "FULL-TEST-001"
        assert spec.title == "Full Feature Test"
        assert spec.version == 2
        assert spec.description == "Detailed description of the feature"
        assert spec.constraints == ["constraint1", "constraint2"]
        assert spec.risk_level == "high"
        assert spec.reviewers == ["reviewer1", "reviewer2"]
        assert spec.model == "gpt-4o"
        assert spec.token_budget == 5000
        assert spec.hard_musts == ["security", "performance"]
    
    def test_id_validation(self):
        """Test ID-Validierung (nur Großbuchstaben, Ziffern, Bindestrich, Punkt, Unterstrich)"""
        valid_ids = [
            "TEST-001",
            "FEATURE_001",
            "MODULE.TEST.001",
            "ABC123",
            "TEST-FEATURE_001.V2"
        ]
        
        for valid_id in valid_ids:
            spec = FeatureSpec(
                id=valid_id,
                title="ID Test",
                version=1,
                goal="Test valid ID patterns",
                target_paths=["codepipeline"]
            )
            assert spec.id == valid_id
    
    def test_invalid_id_rejection(self):
        """Test dass ungültige IDs abgelehnt werden"""
        invalid_ids = [
            "test-001",  # Kleinbuchstaben
            "TEST 001",  # Leerzeichen
            "TEST@001",  # Ungültiges Zeichen
            "",          # Leer
            "test",      # Nur Kleinbuchstaben
        ]
        
        for invalid_id in invalid_ids:
            with pytest.raises(Exception):  # ValidationError oder ValueError
                FeatureSpec(
                    id=invalid_id,
                    title="Invalid ID Test",
                    version=1,
                    goal="Test invalid ID rejection",
                    target_paths=["codepipeline"]
                )


class TestFeatureSpecSHA256:
    """Tests für SHA256-Hash-Funktionalität"""
    
    def test_sha256_returns_64_hex_chars(self):
        """Test dass sha256() immer 64 Hex-Zeichen zurückgibt"""
        spec = FeatureSpec(
            id="HASH-TEST-001",
            title="SHA256 Test Feature",
            version=1,
            goal="Test SHA256 hash generation functionality",
            target_paths=["codepipeline"]
        )
        
        hash_value = spec.sha256()
        
        # 64 Zeichen lang
        assert len(hash_value) == 64
        
        # Nur Hex-Zeichen (0-9, a-f)
        assert all(c in '0123456789abcdef' for c in hash_value)
        
        # Nicht leer
        assert hash_value != ""
        assert hash_value != "0" * 64
    
    def test_sha256_deterministic(self):
        """Test dass SHA256-Hash deterministisch ist"""
        spec1 = FeatureSpec(
            id="DETERMINISTIC-001",
            title="Deterministic Test",
            version=1,
            goal="Test deterministic hash generation",
            target_paths=["codepipeline"]
        )
        
        spec2 = FeatureSpec(
            id="DETERMINISTIC-001",
            title="Deterministic Test",
            version=1,
            goal="Test deterministic hash generation",
            target_paths=["codepipeline"]
        )
        
        hash1 = spec1.sha256()
        hash2 = spec2.sha256()
        
        assert hash1 == hash2
        assert len(hash1) == 64
    
    def test_sha256_different_for_different_specs(self):
        """Test dass verschiedene Specs verschiedene Hashes haben"""
        spec1 = FeatureSpec(
            id="DIFFERENT-001",
            title="First Spec",
            version=1,
            goal="Test different hash generation",
            target_paths=["codepipeline"]
        )
        
        spec2 = FeatureSpec(
            id="DIFFERENT-002",
            title="Second Spec",
            version=1,
            goal="Test different hash generation",
            target_paths=["codepipeline"]
        )
        
        hash1 = spec1.sha256()
        hash2 = spec2.sha256()
        
        assert hash1 != hash2
        assert len(hash1) == len(hash2) == 64


class TestFeatureSpecTargetPaths:
    """Tests für target_paths Validierung und Normalisierung"""
    
    def test_allowed_target_paths_accepted(self):
        """Test dass erlaubte Zielpfade akzeptiert werden"""
        allowed_paths = [
            ["codepipeline"],
            ["tests"],
            ["codepipeline", "tests"],
            ["qa"],
            ["core"],
            ["utils"],
            ["metrics"],
            ["release"],
            ["modules"],
            ["codepipeline", "tests", "qa"],
        ]
        
        for paths in allowed_paths:
            spec = FeatureSpec(
                id="PATH-TEST-001",
                title="Path Test",
                version=1,
                goal="Test allowed target paths acceptance",
                target_paths=paths
            )
            assert spec.target_paths == paths
    
    def test_path_normalization(self):
        """Test dass Pfade normalisiert werden"""
        spec = FeatureSpec(
            id="NORMALIZE-001",
            title="Path Normalization Test",
            version=1,
            goal="Test path normalization functionality",
            target_paths=["codepipeline/", "tests//", "./qa"]
        )
        
        # Paths sollten normalisiert werden (ohne trailing slashes, etc.)
        for path in spec.target_paths:
            assert not path.endswith('/')
            assert '//' not in path
            assert not path.startswith('./')
    
    def test_empty_target_paths_rejected(self):
        """Test dass leere target_paths abgelehnt werden"""
        with pytest.raises(Exception):  # ValidationError
            FeatureSpec(
                id="EMPTY-PATHS-001",
                title="Empty Paths Test",
                version=1,
                goal="Test empty target paths rejection",
                target_paths=[]
            )
    
    def test_invalid_paths_rejected(self):
        """Test dass aufwärtsgerichtete/gefährliche Pfade abgelehnt werden"""
        invalid_paths = [
            [".."],
            ["../parent"],
            ["codepipeline/../escape"],
            ["/absolute/path"],
            ["codepipeline", ".."],
            ["path/with/../traversal"],
        ]
        
        for paths in invalid_paths:
            with pytest.raises(Exception):  # ValidationError
                FeatureSpec(
                    id="INVALID-PATHS-001",
                    title="Invalid Paths Test",
                    version=1,
                    goal="Test invalid target paths rejection",
                    target_paths=paths
                )
    
    def test_empty_string_path_rejected(self):
        """Test dass leere String-Pfade abgelehnt werden"""
        with pytest.raises(Exception):
            FeatureSpec(
                id="EMPTY-STRING-001",
                title="Empty String Path Test",
                version=1,
                goal="Test empty string path rejection",
                target_paths=[""]
            )


class TestFeatureSpecValidation:
    """Tests für weitere Validierungsregeln"""
    
    def test_version_must_be_positive(self):
        """Test dass Version >= 1 sein muss"""
        # Gültige Versionen
        for version in [1, 2, 10, 100]:
            spec = FeatureSpec(
                id="VERSION-TEST-001",
                title="Version Test",
                version=version,
                goal="Test version validation",
                target_paths=["codepipeline"]
            )
            assert spec.version == version
        
        # Ungültige Versionen
        for invalid_version in [0, -1, -10]:
            with pytest.raises(Exception):
                FeatureSpec(
                    id="VERSION-TEST-001",
                    title="Version Test",
                    version=invalid_version,
                    goal="Test version validation",
                    target_paths=["codepipeline"]
                )
    
    def test_goal_minimum_length(self):
        """Test dass goal mindestens 10 Zeichen haben muss"""
        # Gültiges goal
        spec = FeatureSpec(
            id="GOAL-TEST-001",
            title="Goal Test",
            version=1,
            goal="Valid goal with sufficient length for testing",
            target_paths=["codepipeline"]
        )
        assert len(spec.goal) >= 10
        
        # Ungültiges goal (zu kurz)
        with pytest.raises(Exception):
            FeatureSpec(
                id="GOAL-TEST-001",
                title="Goal Test",
                version=1,
                goal="Short",  # Nur 5 Zeichen
                target_paths=["codepipeline"]
            )
    
    def test_title_length_validation(self):
        """Test dass title zwischen 1 und 200 Zeichen haben muss"""
        # Gültiger title
        spec = FeatureSpec(
            id="TITLE-TEST-001",
            title="Valid Title",
            version=1,
            goal="Test title length validation",
            target_paths=["codepipeline"]
        )
        assert 1 <= len(spec.title) <= 200
        
        # Leerer title
        with pytest.raises(Exception):
            FeatureSpec(
                id="TITLE-TEST-001",
                title="",
                version=1,
                goal="Test empty title rejection",
                target_paths=["codepipeline"]
            )
        
        # Zu langer title
        long_title = "x" * 201
        with pytest.raises(Exception):
            FeatureSpec(
                id="TITLE-TEST-001",
                title=long_title,
                version=1,
                goal="Test long title rejection",
                target_paths=["codepipeline"]
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
