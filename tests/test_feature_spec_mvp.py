#!/usr/bin/env python3
"""
MVP-004: Unit-Tests für FeatureSpec Validierung + SHA256
Tests für Roundtrip JSON/YAML und Hash-Länge 64.
"""

import pytest
import json
import yaml
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from codepipeline.feature_spec_mvp import FeatureSpecMVP, FeatureSpecValidationError, TestConfig


class TestFeatureSpecMVP:
    """Unit-Tests für MVP FeatureSpec"""
    
    @pytest.mark.mvp
    def test_valid_featurespec_creation(self):
        """Test: Gültige FeatureSpec wird korrekt erstellt"""
        
        spec = FeatureSpecMVP(
            id="MVP-004",
            title="Test Feature",
            version=1,
            goal="Test the FeatureSpec validation system",
            target_paths=["codepipeline/module.py", "tests/test_module.py"]
        )
        
        assert spec.id == "MVP-004"
        assert spec.title == "Test Feature"
        assert spec.version == 1
        assert spec.goal == "Test the FeatureSpec validation system"
        assert spec.target_paths == ["codepipeline/module.py", "tests/test_module.py"]
        assert isinstance(spec.tests, TestConfig)
        assert spec.tests.coverage_min == 80.0
    
    @pytest.mark.mvp
    def test_sha256_hash_length_64(self):
        """Test: SHA256-Hash hat Länge 64"""
        
        spec = FeatureSpecMVP(
            id="HASH-001",
            title="Hash Test",
            version=1,
            goal="Test SHA256 hash generation",
            target_paths=["test.py"]
        )
        
        hash_value = spec.sha256()
        assert len(hash_value) == 64
        assert isinstance(hash_value, str)
        # Prüfe dass es hexadezimal ist
        assert all(c in '0123456789abcdef' for c in hash_value)
    
    @pytest.mark.mvp
    def test_hash_stability(self):
        """Test: Hash ist stabil bei identischen Specs"""
        
        spec1 = FeatureSpecMVP(
            id="STABLE-001",
            title="Stability Test",
            version=1,
            goal="Test hash stability",
            target_paths=["module.py"]
        )
        
        spec2 = FeatureSpecMVP(
            id="STABLE-001",
            title="Stability Test", 
            version=1,
            goal="Test hash stability",
            target_paths=["module.py"]
        )
        
        hash1 = spec1.sha256()
        hash2 = spec2.sha256()
        
        assert hash1 == hash2
        assert len(hash1) == 64
    
    @pytest.mark.mvp
    def test_json_roundtrip(self):
        """Test: JSON Serialization/Deserialization Roundtrip"""
        
        original = FeatureSpecMVP(
            id="JSON-001",
            title="JSON Roundtrip Test",
            version=2,
            goal="Test JSON serialization and deserialization",
            target_paths=["src/main.py", "src/utils.py"],
            description="Test description",
            author="Test Author"
        )
        
        # Serialisiere zu JSON
        json_str = original.to_json()
        assert isinstance(json_str, str)
        
        # Deserialisiere von JSON
        loaded = FeatureSpecMVP.from_json(json_str)
        
        # Prüfe alle Felder
        assert loaded.id == original.id
        assert loaded.title == original.title
        assert loaded.version == original.version
        assert loaded.goal == original.goal
        assert loaded.target_paths == original.target_paths
        assert loaded.description == original.description
        assert loaded.author == original.author
        
        # Prüfe Hash-Konsistenz
        assert loaded.sha256() == original.sha256()
    
    @pytest.mark.mvp
    def test_yaml_roundtrip(self):
        """Test: YAML Serialization/Deserialization Roundtrip"""
        
        original = FeatureSpecMVP(
            id="YAML-001",
            title="YAML Roundtrip Test",
            version=3,
            goal="Test YAML serialization and deserialization",
            target_paths=["config/settings.py"]
        )
        
        # Serialisiere zu YAML
        yaml_str = original.to_yaml()
        assert isinstance(yaml_str, str)
        
        # Deserialisiere von YAML
        loaded = FeatureSpecMVP.from_yaml(yaml_str)
        
        # Prüfe kritische Felder
        assert loaded.id == original.id
        assert loaded.title == original.title
        assert loaded.version == original.version
        assert loaded.goal == original.goal
        assert loaded.target_paths == original.target_paths
        
        # Prüfe Hash-Konsistenz
        assert loaded.sha256() == original.sha256()
    
    @pytest.mark.mvp
    def test_cross_format_hash_consistency(self):
        """Test: Hash ist konsistent zwischen JSON und YAML"""
        
        spec = FeatureSpecMVP(
            id="CROSS-001",
            title="Cross Format Test",
            version=1,
            goal="Test hash consistency across formats",
            target_paths=["cross.py"]
        )
        
        # Original Hash
        original_hash = spec.sha256()
        
        # JSON Roundtrip
        json_loaded = FeatureSpecMVP.from_json(spec.to_json())
        json_hash = json_loaded.sha256()
        
        # YAML Roundtrip
        yaml_loaded = FeatureSpecMVP.from_yaml(spec.to_yaml())
        yaml_hash = yaml_loaded.sha256()
        
        assert original_hash == json_hash == yaml_hash
    
    @pytest.mark.mvp
    def test_invalid_id_formats(self):
        """Test: Ungültige ID-Formate werden abgewiesen"""
        
        invalid_ids = [
            "",  # Leer
            "invalid",  # Kein Bindestrich
            "invalid-",  # Kein Nummer-Teil
            "123-ABC",  # Zahlen vor Buchstaben
            "abc-123",  # Kleinbuchstaben
            "ABC_123",  # Unterstrich statt Bindestrich
            "ABC-123-",  # Trailing Bindestrich
            "ABC--123",  # Doppelter Bindestrich
        ]
        
        for invalid_id in invalid_ids:
            with pytest.raises(FeatureSpecValidationError, match="Feature ID"):
                FeatureSpecMVP(
                    id=invalid_id,
                    title="Test",
                    version=1,
                    goal="Test invalid ID",
                    target_paths=["test.py"]
                )
    
    @pytest.mark.mvp
    def test_invalid_target_paths(self):
        """Test: Ungültige Zielpfade werden abgewiesen"""
        
        invalid_path_cases = [
            {
                "paths": ["/absolute/path"],
                "error": "Target path must be relative"
            },
            {
                "paths": ["C:\\windows\\path"],
                "error": "Target path must be relative"
            },
            {
                "paths": ["../parent/dir"],
                "error": "Target path cannot contain '..'"
            },
            {
                "paths": ["src/../parent"],
                "error": "Target path cannot contain '..'"
            },
            {
                "paths": ["file;rm -rf /"],
                "error": "dangerous character"
            },
            {
                "paths": ["file|pipe"],
                "error": "dangerous character"
            },
            {
                "paths": ["file<redirect"],
                "error": "dangerous character"
            },
            {
                "paths": [""],
                "error": "cannot be empty"
            },
            {
                "paths": ["   "],
                "error": "cannot be empty"
            },
            {
                "paths": [".hidden/file"],
                "error": "cannot contain hidden"
            },
            {
                "paths": ["etc/passwd"],
                "error": "system directory"
            }
        ]
        
        for case in invalid_path_cases:
            with pytest.raises(FeatureSpecValidationError):
                FeatureSpecMVP(
                    id="PATH-001",
                    title="Path Test",
                    version=1,
                    goal="Test invalid paths",
                    target_paths=case["paths"]
                )
    
    @pytest.mark.mvp
    def test_target_path_normalization(self):
        """Test: Zielpfade werden korrekt normalisiert"""
        
        spec = FeatureSpecMVP(
            id="NORM-001",
            title="Normalization Test",
            version=1,
            goal="Test path normalization",
            target_paths=[
                "src/main.py",
                "src\\windows\\path.py",  # Windows-Style
                "src//double//slash.py",  # Doppelte Slashes
                "src/main.py",  # Duplikat
                "tests/test.py"
            ]
        )
        
        # Erwarte normalisierte und deduplizierte Pfade
        expected = ["src/main.py", "src/windows/path.py", "src/double/slash.py", "tests/test.py"]
        assert spec.target_paths == sorted(expected)
    
    @pytest.mark.mvp
    def test_field_validation_edge_cases(self):
        """Test: Edge Cases für Feld-Validierung"""
        
        # Titel zu kurz
        with pytest.raises(FeatureSpecValidationError, match="at least 3 characters"):
            FeatureSpecMVP(
                id="EDGE-001",
                title="AB",  # Zu kurz
                version=1,
                goal="Test edge cases",
                target_paths=["test.py"]
            )
        
        # Titel zu lang
        with pytest.raises(FeatureSpecValidationError, match="at most 100 characters"):
            FeatureSpecMVP(
                id="EDGE-002",
                title="X" * 101,  # Zu lang
                version=1,
                goal="Test edge cases",
                target_paths=["test.py"]
            )
        
        # Goal zu kurz
        with pytest.raises(FeatureSpecValidationError, match="at least 10 characters"):
            FeatureSpecMVP(
                id="EDGE-003",
                title="Edge Test",
                version=1,
                goal="Short",  # Zu kurz
                target_paths=["test.py"]
            )
        
        # Version null oder negativ
        with pytest.raises(FeatureSpecValidationError, match="must be positive"):
            FeatureSpecMVP(
                id="EDGE-004",
                title="Edge Test",
                version=0,  # Null
                goal="Test zero version",
                target_paths=["test.py"]
            )
    
    @pytest.mark.mvp
    def test_file_operations(self):
        """Test: Laden und Speichern von Dateien"""
        import tempfile
        
        spec = FeatureSpecMVP(
            id="FILE-001",
            title="File Operations Test",
            version=1,
            goal="Test file loading and saving operations",
            target_paths=["file_ops.py"]
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test JSON speichern/laden
            json_file = temp_path / "test.json"
            spec.save_to_file(json_file, format='json')
            
            loaded_json = FeatureSpecMVP.from_file(json_file)
            assert loaded_json.sha256() == spec.sha256()
            
            # Test YAML speichern/laden
            yaml_file = temp_path / "test.yaml"
            spec.save_to_file(yaml_file, format='yaml')
            
            loaded_yaml = FeatureSpecMVP.from_file(yaml_file)
            assert loaded_yaml.sha256() == spec.sha256()
            
            # Test Auto-Format-Erkennung
            auto_json = temp_path / "auto.json"
            spec.save_to_file(auto_json)  # Auto-format
            
            loaded_auto = FeatureSpecMVP.from_file(auto_json)
            assert loaded_auto.sha256() == spec.sha256()
    
    @pytest.mark.mvp
    def test_canonical_representation(self):
        """Test: Kanonische Repräsentation ist deterministisch"""
        
        spec1 = FeatureSpecMVP(
            id="CANON-001",
            title="Canonical Test",
            version=1,
            goal="Test canonical representation",
            target_paths=["b.py", "a.py"],  # Unsortiert
            description="Description",
            author="Author"
        )
        
        spec2 = FeatureSpecMVP(
            id="CANON-001",
            title="Canonical Test",
            version=1,
            goal="Test canonical representation",
            target_paths=["a.py", "b.py"],  # Sortiert
            description="Description",
            author="Author"
        )
        
        # Canonical JSON sollte identisch sein
        canonical1 = spec1.to_canonical_json()
        canonical2 = spec2.to_canonical_json()
        
        assert canonical1 == canonical2
        assert spec1.sha256() == spec2.sha256()
    
    @pytest.mark.mvp
    def test_mvp_004_acceptance_criteria(self):
        """Test: MVP-004 Akzeptanzkriterien"""
        
        # 1. Valid Specs laden
        valid_spec = FeatureSpecMVP(
            id="ACCEPT-001",
            title="Acceptance Test",
            version=1,
            goal="Test acceptance criteria",
            target_paths=["accept.py"]
        )
        assert valid_spec.id == "ACCEPT-001"
        
        # 2. Invalid Specs werden abgewiesen
        with pytest.raises(FeatureSpecValidationError):
            FeatureSpecMVP(
                id="invalid",
                title="Should Fail",
                version=1,
                goal="Should be rejected",
                target_paths=["/absolute/path"]
            )
        
        # 3. Hash ist stabil
        hash1 = valid_spec.sha256()
        hash2 = valid_spec.sha256()
        assert hash1 == hash2
        assert len(hash1) == 64
        
        # 4. JSON/YAML Roundtrip
        json_loaded = FeatureSpecMVP.from_json(valid_spec.to_json())
        yaml_loaded = FeatureSpecMVP.from_yaml(valid_spec.to_yaml())
        
        assert json_loaded.sha256() == valid_spec.sha256()
        assert yaml_loaded.sha256() == valid_spec.sha256()
        
        print("✅ MVP-004 Akzeptanzkriterien erfüllt:")
        print("   - Valid Specs laden ✅")
        print("   - Invalid Specs abgewiesen ✅")
        print("   - Hash-Länge 64 ✅")
        print("   - Hash stabil ✅")
        print("   - JSON/YAML Roundtrip ✅")
