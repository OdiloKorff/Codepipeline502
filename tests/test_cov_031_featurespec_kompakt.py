#!/usr/bin/env python3
"""
COV-031: FeatureSpec – Vollabdeckung Kernpfade (Kompakte Version)
Fokussierte Unit-Tests für die wichtigsten FeatureSpec-Pfade.
"""

import pytest
import json
import tempfile
import hashlib
from pathlib import Path
import sys

# Füge src-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from codepipeline.feature_spec_mvp import FeatureSpecMVP, FeatureSpecValidationError
except ImportError as e:
    pytest.skip(f"FeatureSpec module not available: {e}", allow_module_level=True)


class TestFeatureSpecCoreAPI:
    """Tests für die Core-API der FeatureSpec."""
    
    def create_valid_spec_data(self, spec_id="TEST-001"):
        """Helper: Erstelle valide Spec-Daten."""
        return {
            "id": spec_id,
            "title": "Test Feature",
            "version": 1,
            "goal": "Test goal for validation",
            "target_paths": ["src/"],
            "description": "Test specification"
        }
    
    def test_json_roundtrip_basic(self, tmp_path):
        """Test: Basic JSON Load/Save Roundtrip."""
        spec_file = tmp_path / "test.json"
        original_data = self.create_valid_spec_data()
        
        # Save → Load → Verify
        with open(spec_file, 'w') as f:
            json.dump(original_data, f)
        
        spec = FeatureSpecMVP.from_file(str(spec_file))
        assert spec.id == "TEST-001"
        assert spec.title == "Test Feature"
        assert spec.target_paths == ["src"]  # Normalisiert: trailing slash entfernt
    
    def test_canonical_json_stability(self, tmp_path):
        """Test: canonical_json ist deterministisch."""
        spec_file = tmp_path / "test.json"
        data = self.create_valid_spec_data("CANON-001")
        
        with open(spec_file, 'w') as f:
            json.dump(data, f)
        
        spec = FeatureSpecMVP.from_file(str(spec_file))
        
        # Mehrfache Calls müssen identisch sein
        canon1 = spec.to_canonical_json()
        canon2 = spec.to_canonical_json()
        canon3 = spec.to_canonical_json()
        
        assert canon1 == canon2 == canon3
        
        # Muss valides JSON sein
        parsed = json.loads(canon1)
        assert parsed["id"] == "CANON-001"
    
    def test_sha256_deterministic(self, tmp_path):
        """Test: SHA256 ist deterministisch und korrekte Länge."""
        spec_file = tmp_path / "test.json"
        data = self.create_valid_spec_data("SHA-001")
        
        with open(spec_file, 'w') as f:
            json.dump(data, f)
        
        spec = FeatureSpecMVP.from_file(str(spec_file))
        
        # Mehrfache Calls müssen identisch sein
        hash1 = spec.sha256()
        hash2 = spec.sha256()
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 = 64 Hex-Zeichen
        assert all(c in '0123456789abcdef' for c in hash1.lower())
        
        # Manual verification
        canonical = spec.to_canonical_json()
        expected = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        assert hash1.lower() == expected.lower()
    
    def test_sha256_content_sensitivity(self, tmp_path):
        """Test: SHA256 ändert sich bei Content-Änderung."""
        spec_file1 = tmp_path / "spec1.json"
        spec_file2 = tmp_path / "spec2.json"
        
        data1 = self.create_valid_spec_data("SENS-001")
        data2 = self.create_valid_spec_data("SENS-001")
        data2["title"] = "Different Title"  # Unterschied
        
        with open(spec_file1, 'w') as f:
            json.dump(data1, f)
        with open(spec_file2, 'w') as f:
            json.dump(data2, f)
        
        spec1 = FeatureSpecMVP.from_file(str(spec_file1))
        spec2 = FeatureSpecMVP.from_file(str(spec_file2))
        
        # Hashes müssen unterschiedlich sein
        assert spec1.sha256() != spec2.sha256()


class TestTargetPathsValidation:
    """Tests für target_paths Validierung."""
    
    def create_spec_with_paths(self, paths, tmp_path):
        """Helper: Erstelle Spec mit spezifischen Pfaden."""
        data = {
            "id": "PATH-001",
            "title": "Path Test",
            "version": 1,
            "goal": "Test paths validation",
            "target_paths": paths
        }
        spec_file = tmp_path / "paths.json"
        with open(spec_file, 'w') as f:
            json.dump(data, f)
        return str(spec_file)
    
    def test_valid_paths_accepted(self, tmp_path):
        """Test: Valide Pfade werden akzeptiert."""
        valid_paths_and_expected = [
            (["src/"], ["src"]),  # Trailing slash entfernt
            (["src/", "lib/"], ["lib", "src"]),  # Sortiert und normalisiert
            (["app/main.py"], ["app/main.py"]),  # File bleibt unverändert
            (["deep/nested/path/"], ["deep/nested/path"])  # Trailing slash entfernt
        ]
        
        for paths, expected in valid_paths_and_expected:
            spec_file = self.create_spec_with_paths(paths, tmp_path)
            spec = FeatureSpecMVP.from_file(spec_file)
            assert spec.target_paths == expected
    
    def test_invalid_paths_rejected(self, tmp_path):
        """Test: Ungültige Pfade werden abgelehnt."""
        invalid_paths = [
            [],  # Leer
            ["/absolute/path"],  # Absolut
            ["../parent/traversal"],  # Parent-Traversal
            [""],  # Leerer String
        ]
        
        for paths in invalid_paths:
            spec_file = self.create_spec_with_paths(paths, tmp_path)
            with pytest.raises((FeatureSpecValidationError, ValueError, Exception)):
                FeatureSpecMVP.from_file(spec_file)


class TestFeatureSpecErrorHandling:
    """Tests für Error-Handling und Edge Cases."""
    
    def test_missing_required_fields(self, tmp_path):
        """Test: Fehlende Required Fields werfen Exceptions."""
        incomplete_specs = [
            {"title": "No ID", "version": 1, "goal": "test", "target_paths": ["src/"]},
            {"id": "NO-TITLE-001", "version": 1, "goal": "test", "target_paths": ["src/"]},
            {"id": "NO-VERSION-001", "title": "Test", "goal": "test", "target_paths": ["src/"]},
            {"id": "NO-GOAL-001", "title": "Test", "version": 1, "target_paths": ["src/"]},
            {"id": "NO-PATHS-001", "title": "Test", "version": 1, "goal": "test"},
        ]
        
        for i, data in enumerate(incomplete_specs):
            spec_file = tmp_path / f"incomplete_{i}.json"
            with open(spec_file, 'w') as f:
                json.dump(data, f)
            
            with pytest.raises((FeatureSpecValidationError, KeyError, Exception)):
                FeatureSpecMVP.from_file(str(spec_file))
    
    def test_invalid_id_format(self, tmp_path):
        """Test: Ungültige ID-Formate werden abgelehnt."""
        invalid_ids = [
            "invalid-id-lowercase",  # Lowercase
            "123-INVALID",  # Starts with number
            "INVALID_ID_001",  # Underscore
            "INVALID ID 001",  # Spaces
            "",  # Empty
        ]
        
        for invalid_id in invalid_ids:
            data = {
                "id": invalid_id,
                "title": "Test",
                "version": 1,
                "goal": "Test goal",
                "target_paths": ["src/"]
            }
            spec_file = tmp_path / f"invalid_id.json"
            with open(spec_file, 'w') as f:
                json.dump(data, f)
            
            with pytest.raises((FeatureSpecValidationError, Exception)):
                FeatureSpecMVP.from_file(str(spec_file))
    
    def test_file_not_found(self, tmp_path):
        """Test: Nicht-existierende Datei wirft Exception."""
        non_existent = tmp_path / "does_not_exist.json"
        
        with pytest.raises((FileNotFoundError, Exception)):
            FeatureSpecMVP.from_file(str(non_existent))
    
    def test_invalid_json(self, tmp_path):
        """Test: Ungültiges JSON wirft Exception."""
        invalid_file = tmp_path / "invalid.json"
        
        with open(invalid_file, 'w') as f:
            f.write('{"id": "TEST", invalid json}')  # Syntaxfehler
        
        with pytest.raises((json.JSONDecodeError, Exception)):
            FeatureSpecMVP.from_file(str(invalid_file))


class TestFeatureSpecDefaults:
    """Tests für Default-Werte und optionale Felder."""
    
    def test_optional_fields_handling(self, tmp_path):
        """Test: Optionale Felder werden korrekt behandelt."""
        # Minimale Spec ohne optionale Felder
        minimal_data = {
            "id": "MINIMAL-001",
            "title": "Minimal Feature",
            "version": 1,
            "goal": "Minimal test goal",
            "target_paths": ["src/"]
        }
        
        spec_file = tmp_path / "minimal.json"
        with open(spec_file, 'w') as f:
            json.dump(minimal_data, f)
        
        spec = FeatureSpecMVP.from_file(str(spec_file))
        
        # Required fields müssen vorhanden sein
        assert spec.id == "MINIMAL-001"
        assert spec.title == "Minimal Feature"
        assert spec.version == 1
        assert spec.goal == "Minimal test goal"
        assert spec.target_paths == ["src"]  # Normalisiert: trailing slash entfernt
        
        # Optionale fields haben Defaults oder None
        assert spec.description is None
        assert spec.author is None
        assert spec.created_at is not None  # Auto-generated
        assert spec.tests is not None  # Default TestConfig
    
    def test_custom_optional_fields(self, tmp_path):
        """Test: Custom optionale Felder werden übernommen."""
        custom_data = {
            "id": "CUSTOM-001",
            "title": "Custom Feature",
            "version": 2,
            "goal": "Custom test goal",
            "target_paths": ["src/", "lib/"],
            "description": "Custom description",
            "author": "Test Author"
        }
        
        spec_file = tmp_path / "custom.json"
        with open(spec_file, 'w') as f:
            json.dump(custom_data, f)
        
        spec = FeatureSpecMVP.from_file(str(spec_file))
        
        assert spec.description == "Custom description"
        assert spec.author == "Test Author"


class TestFeatureSpecIntegration:
    """Integrationstests für komplette Workflows."""
    
    def test_complete_roundtrip_workflow(self, tmp_path):
        """Test: Kompletter Load → Modify → Save → Load Workflow."""
        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        
        original_data = {
            "id": "WORKFLOW-001",
            "title": "Workflow Test",
            "version": 1,
            "goal": "Test complete workflow",
            "target_paths": ["src/", "tests/"],
            "description": "Integration test"
        }
        
        # 1. Save original
        with open(input_file, 'w') as f:
            json.dump(original_data, f, indent=2)
        
        # 2. Load with FeatureSpec
        spec = FeatureSpecMVP.from_file(str(input_file))
        
        # 3. Verify loaded data
        assert spec.id == "WORKFLOW-001"
        assert spec.title == "Workflow Test"
        assert "src" in spec.target_paths  # Normalisiert
        assert "tests" in spec.target_paths  # Normalisiert
        
        # 4. Generate hash (should be stable)
        hash1 = spec.sha256()
        
        # 5. Save as JSON
        spec.save_json(str(output_file))
        
        # 6. Load output and compare
        with open(output_file, 'r') as f:
            output_data = json.load(f)
        
        assert output_data["id"] == original_data["id"]
        assert output_data["title"] == original_data["title"]
        assert output_data["target_paths"] == original_data["target_paths"]
        
        # 7. Hash should remain stable
        spec2 = FeatureSpecMVP.from_file(str(output_file))
        hash2 = spec2.sha256()
        assert hash1 == hash2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
