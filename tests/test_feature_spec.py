"""
Tests für das FeatureSpec Datenmodell.

Testet Validierung, Serialisierung, Hashing und Datei-I/O
mit umfassenden Positiv- und Negativfällen.
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from feature_spec import FeatureSpec, TestConfig, QualityOverrides, load_feature_spec, create_feature_spec


class TestFeatureSpecValidation:
    """Tests für Basis-Validierung des FeatureSpec-Modells."""
    
    def test_valid_feature_spec_creation(self):
        """Test: Gültige FeatureSpec kann erstellt werden."""
        spec = FeatureSpec(
            id="TEST-001",
            title="Test Feature",
            version=1,
            goal="Implementiere Test-Funktionalität für bessere Code-Qualität",
            target_paths=["src/test.py", "tests/test_new.py"]
        )
        
        assert spec.id == "TEST-001"
        assert spec.title == "Test Feature"
        assert spec.version == 1
        assert spec.risk_level == "medium"  # Default
        assert spec.model == "gpt-4o"  # Default
        assert spec.token_budget == 8000  # Default
        assert len(spec.target_paths) == 2
    
    def test_id_pattern_validation(self):
        """Test: ID-Pattern wird korrekt validiert."""
        # Gültige IDs
        valid_ids = ["TEST-001", "FEATURE_123", "API.V2", "USER-AUTH_V1.2"]
        for valid_id in valid_ids:
            spec = FeatureSpec(
                id=valid_id,
                title="Test",
                version=1,
                goal="Test goal with sufficient length",
                target_paths=["src/test.py"]
            )
            assert spec.id == valid_id
        
        # Ungültige IDs
        invalid_ids = ["test-001", "TEST 001", "TEST@001", "TEST/001", ""]
        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError) as exc_info:
                FeatureSpec(
                    id=invalid_id,
                    title="Test",
                    version=1,
                    goal="Test goal with sufficient length",
                    target_paths=["src/test.py"]
                )
            assert "String should match pattern" in str(exc_info.value)
    
    def test_version_validation(self):
        """Test: Version muss >= 1 sein."""
        # Gültige Versionen
        for version in [1, 2, 100]:
            spec = FeatureSpec(
                id="TEST-001",
                title="Test",
                version=version,
                goal="Test goal with sufficient length",
                target_paths=["src/test.py"]
            )
            assert spec.version == version
        
        # Ungültige Versionen
        for invalid_version in [0, -1]:
            with pytest.raises(ValidationError) as exc_info:
                FeatureSpec(
                    id="TEST-001",
                    title="Test",
                    version=invalid_version,
                    goal="Test goal with sufficient length",
                    target_paths=["src/test.py"]
                )
            assert "greater than or equal to 1" in str(exc_info.value)
    
    def test_goal_length_validation(self):
        """Test: Goal muss mindestens 10 Zeichen haben."""
        # Zu kurz
        with pytest.raises(ValidationError) as exc_info:
            FeatureSpec(
                id="TEST-001",
                title="Test",
                version=1,
                goal="Short",
                target_paths=["src/test.py"]
            )
        assert "at least 10 characters" in str(exc_info.value)
        
        # Gültig
        spec = FeatureSpec(
            id="TEST-001",
            title="Test",
            version=1,
            goal="This is a sufficiently long goal description",
            target_paths=["src/test.py"]
        )
        assert len(spec.goal) >= 10


class TestTargetPathsValidation:
    """Tests für target_paths Validierung."""
    
    def test_valid_relative_paths(self):
        """Test: Gültige relative Pfade werden akzeptiert."""
        valid_paths = [
            ["src/main.py"],
            ["src/api/routes.py", "tests/test_api.py"],
            ["docs/readme.md", "config/settings.json"],
            ["app/models/user.py", "app/views/auth.py", "static/css/style.css"]
        ]
        
        for paths in valid_paths:
            spec = FeatureSpec(
                id="TEST-001",
                title="Test",
                version=1,
                goal="Test goal with sufficient length",
                target_paths=paths
            )
            assert spec.target_paths == [p.replace('\\', '/') for p in paths]
    
    @pytest.mark.mvp
    def test_empty_target_paths_rejected(self):
        """Test: Leere target_paths werden abgelehnt."""
        with pytest.raises(ValidationError) as exc_info:
            FeatureSpec(
                id="TEST-001",
                title="Test",
                version=1,
                goal="Test goal with sufficient length",
                target_paths=[]
            )
        # Pydantic v2 hat andere Fehlermeldungen
        error_msg = str(exc_info.value)
        assert ("target_paths darf nicht leer sein" in error_msg or 
                "List should have at least 1 item" in error_msg)
    
    def test_absolute_paths_rejected(self):
        """Test: Absolute Pfade werden abgelehnt."""
        absolute_paths = [
            ["/etc/passwd"],
            ["C:\\Windows\\System32\\config"],
            ["/home/user/secret.txt"],
            ["\\\\server\\share\\file.txt"]
        ]
        
        for paths in absolute_paths:
            with pytest.raises(ValidationError) as exc_info:
                FeatureSpec(
                    id="TEST-001",
                    title="Test",
                    version=1,
                    goal="Test goal with sufficient length",
                    target_paths=paths
                )
            # Pydantic v2 hat andere Fehlermeldungen
            error_msg = str(exc_info.value)
            assert ("Absolute Pfade nicht erlaubt" in error_msg or 
                    "Value error" in error_msg or "validation error" in error_msg)
    
    def test_parent_traversal_rejected(self):
        """Test: Parent-Traversal wird abgelehnt."""
        traversal_paths = [
            ["../etc/passwd"],
            ["src/../../../secret.txt"],
            ["app/../../config/database.yml"],
            ["../../../../../../../etc/shadow"]
        ]
        
        for paths in traversal_paths:
            with pytest.raises(ValidationError) as exc_info:
                FeatureSpec(
                    id="TEST-001",
                    title="Test",
                    version=1,
                    goal="Test goal with sufficient length",
                    target_paths=paths
                )
            # Pydantic v2 hat andere Fehlermeldungen
            error_msg = str(exc_info.value)
            assert ("Parent-Traversal nicht erlaubt" in error_msg or 
                    "Value error" in error_msg or "validation error" in error_msg)
    
    def test_empty_path_strings_rejected(self):
        """Test: Leere Pfad-Strings werden abgelehnt."""
        with pytest.raises(ValidationError) as exc_info:
            FeatureSpec(
                id="TEST-001",
                title="Test",
                version=1,
                goal="Test goal with sufficient length",
                target_paths=["src/main.py", "", "tests/test.py"]
            )
        # Pydantic v2 hat andere Fehlermeldungen
        error_msg = str(exc_info.value)
        assert ("Leere Pfade sind nicht erlaubt" in error_msg or 
                "Value error" in error_msg or "validation error" in error_msg)


class TestModelValidation:
    """Tests für Model-weite Validierungen."""
    
    def test_token_budget_validation(self):
        """Test: Token-Budget wird gegen Model-Limits validiert."""
        # GPT-4 mit zu hohem Budget
        with pytest.raises(ValidationError) as exc_info:
            FeatureSpec(
                id="TEST-001",
                title="Test",
                version=1,
                goal="Test goal with sufficient length",
                target_paths=["src/test.py"],
                model="gpt-4o",
                token_budget=200000  # Über 128k Limit
            )
        assert "GPT-4 Token-Budget überschreitet Maximum" in str(exc_info.value)
        
        # GPT-3.5 mit zu hohem Budget
        with pytest.raises(ValidationError) as exc_info:
            FeatureSpec(
                id="TEST-001",
                title="Test",
                version=1,
                goal="Test goal with sufficient length",
                target_paths=["src/test.py"],
                model="gpt-3.5-turbo",
                token_budget=20000  # Über 16k Limit
            )
        assert "GPT-3.5 Token-Budget überschreitet Maximum" in str(exc_info.value)
    
    def test_high_risk_reviewer_requirement(self):
        """Test: High-Risk Features benötigen mindestens 2 Reviewer."""
        # Zu wenig Reviewer für High-Risk
        with pytest.raises(ValidationError) as exc_info:
            FeatureSpec(
                id="TEST-001",
                title="Test",
                version=1,
                goal="Test goal with sufficient length",
                target_paths=["src/test.py"],
                risk_level="high",
                reviewers=["alice"]  # Nur 1 Reviewer
            )
        assert "High-Risk Features benötigen mindestens 2 Reviewer" in str(exc_info.value)
        
        # Genug Reviewer für High-Risk
        spec = FeatureSpec(
            id="TEST-001",
            title="Test",
            version=1,
            goal="Test goal with sufficient length",
            target_paths=["src/test.py"],
            risk_level="high",
            reviewers=["alice", "bob"]
        )
        assert len(spec.reviewers) == 2


class TestSerializationAndHashing:
    """Tests für Serialisierung und Hash-Funktionen."""
    
    def test_canonical_json_deterministic(self):
        """Test: canonical_json erzeugt deterministische Ausgabe."""
        spec1 = FeatureSpec(
            id="TEST-001",
            title="Test Feature",
            version=1,
            goal="Test goal with sufficient length",
            target_paths=["src/test.py", "tests/test.py"],
            reviewers=["alice", "bob"]
        )
        
        spec2 = FeatureSpec(
            id="TEST-001",
            title="Test Feature", 
            version=1,
            goal="Test goal with sufficient length",
            target_paths=["src/test.py", "tests/test.py"],
            reviewers=["alice", "bob"]
        )
        
        # Identische Specs sollten identisches JSON erzeugen
        json1 = spec1.canonical_json()
        json2 = spec2.canonical_json()
        assert json1 == json2
        
        # JSON sollte sortiert und ohne Whitespace sein
        assert '"id":"TEST-001"' in json1
        assert '\n' not in json1
        assert '  ' not in json1
    
    @pytest.mark.mvp
    def test_sha256_hash_length_and_consistency(self):
        """Test: SHA256-Hash hat korrekte Länge und ist konsistent."""
        spec = FeatureSpec(
            id="TEST-001",
            title="Test Feature",
            version=1,
            goal="Test goal with sufficient length",
            target_paths=["src/test.py"]
        )
        
        hash1 = spec.sha256()
        hash2 = spec.sha256()
        
        # Hash sollte 64 Zeichen haben (SHA256 in Hex)
        assert len(hash1) == 64
        assert len(hash2) == 64
        
        # Hash sollte konsistent sein
        assert hash1 == hash2
        
        # Hash sollte nur Hex-Zeichen enthalten
        assert all(c in '0123456789abcdef' for c in hash1)
    
    def test_different_specs_different_hashes(self):
        """Test: Verschiedene Specs erzeugen verschiedene Hashes."""
        spec1 = FeatureSpec(
            id="TEST-001",
            title="Test Feature",
            version=1,
            goal="Test goal with sufficient length",
            target_paths=["src/test.py"]
        )
        
        spec2 = FeatureSpec(
            id="TEST-002",  # Unterschiedliche ID
            title="Test Feature",
            version=1,
            goal="Test goal with sufficient length",
            target_paths=["src/test.py"]
        )
        
        assert spec1.sha256() != spec2.sha256()


class TestFileIO:
    """Tests für Datei-I/O Funktionen."""
    
    def test_json_roundtrip(self):
        """Test: JSON Speichern und Laden funktioniert korrekt."""
        original = FeatureSpec(
            id="TEST-001",
            title="Test Feature",
            version=2,
            goal="Test goal with sufficient length",
            target_paths=["src/api.py", "tests/test_api.py"],
            description="Detailed description",
            risk_level="high",
            reviewers=["alice", "bob"],
            model="gpt-4o",
            token_budget=4000,
            constraints=["No breaking changes", "Backward compatible"],
            hard_musts=["All tests pass", "Security review"]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Speichern
            original.to_file(temp_path)
            
            # Laden
            loaded = FeatureSpec.from_file(temp_path)
            
            # Vergleichen
            assert loaded.id == original.id
            assert loaded.title == original.title
            assert loaded.version == original.version
            assert loaded.goal == original.goal
            assert loaded.target_paths == original.target_paths
            assert loaded.description == original.description
            assert loaded.risk_level == original.risk_level
            assert loaded.reviewers == original.reviewers
            assert loaded.model == original.model
            assert loaded.token_budget == original.token_budget
            assert loaded.constraints == original.constraints
            assert loaded.hard_musts == original.hard_musts
            
            # Hash sollte identisch sein
            assert loaded.sha256() == original.sha256()
            
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_yaml_roundtrip(self):
        """Test: YAML Speichern und Laden funktioniert korrekt."""
        original = FeatureSpec(
            id="TEST-002",
            title="YAML Test Feature",
            version=1,
            goal="Test YAML serialization with sufficient length",
            target_paths=["config/app.yml", "docs/config.md"],
            quality=QualityOverrides(score_threshold=85, coverage_min=90)
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Speichern
            original.to_file(temp_path)
            
            # Laden
            loaded = FeatureSpec.from_file(temp_path)
            
            # Vergleichen
            assert loaded.sha256() == original.sha256()
            assert loaded.quality.score_threshold == 85
            assert loaded.quality.coverage_min == 90
            
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_file_not_found_error(self):
        """Test: FileNotFoundError wird korrekt geworfen."""
        with pytest.raises(FileNotFoundError) as exc_info:
            FeatureSpec.from_file("nonexistent.json")
        assert "Spec-Datei nicht gefunden" in str(exc_info.value)
    
    def test_invalid_json_error(self):
        """Test: Ungültiges JSON wird korrekt behandelt."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{ invalid json }')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError) as exc_info:
                FeatureSpec.from_file(temp_path)
            assert "Ungültiges JSON" in str(exc_info.value)
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_invalid_yaml_error(self):
        """Test: Ungültiges YAML wird korrekt behandelt."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('invalid: yaml: content: [')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError) as exc_info:
                FeatureSpec.from_file(temp_path)
            assert "Ungültiges YAML" in str(exc_info.value)
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_unsupported_format_error(self):
        """Test: Nicht unterstützte Dateiformate werden abgelehnt."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('invalid content')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError) as exc_info:
                FeatureSpec.from_file(temp_path)
            assert "Unsupported file format" in str(exc_info.value)
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_explicit_format_override(self):
        """Test: Explizite Format-Angabe funktioniert."""
        spec = FeatureSpec(
            id="TEST-003",
            title="Format Test",
            version=1,
            goal="Test explicit format with sufficient length",
            target_paths=["src/test.py"]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Als JSON speichern trotz .txt Endung
            spec.to_file(temp_path, format_type="json")
            
            # Datei sollte gültiges JSON enthalten
            content = temp_path.read_text()
            data = json.loads(content)
            assert data['id'] == "TEST-003"
            
        finally:
            temp_path.unlink(missing_ok=True)


class TestConvenienceFunctions:
    """Tests für Convenience-Funktionen."""
    
    def test_load_feature_spec_alias(self):
        """Test: load_feature_spec Alias funktioniert."""
        spec = FeatureSpec(
            id="TEST-004",
            title="Convenience Test",
            version=1,
            goal="Test convenience functions with sufficient length",
            target_paths=["src/convenience.py"]
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            spec.to_file(temp_path)
            loaded = load_feature_spec(temp_path)
            assert loaded.sha256() == spec.sha256()
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_create_feature_spec_convenience(self):
        """Test: create_feature_spec Convenience-Funktion."""
        spec = create_feature_spec(
            id="TEST-005",
            title="Created via convenience",
            goal="Test convenience creation with sufficient length",
            target_paths=["src/created.py"],
            version=3,
            risk_level="low"
        )
        
        assert spec.id == "TEST-005"
        assert spec.version == 3
        assert spec.risk_level == "low"
        assert spec.model == "gpt-4o"  # Default
        assert len(spec.sha256()) == 64


class TestComplexScenarios:
    """Tests für komplexere Anwendungsszenarien."""
    
    def test_full_feature_spec_with_all_options(self):
        """Test: Vollständige FeatureSpec mit allen Optionen."""
        spec = FeatureSpec(
            id="COMPLEX-001",
            title="Complex Feature with All Options",
            version=5,
            goal="Comprehensive test of all FeatureSpec capabilities with sufficient detail",
            description="This is a complex feature spec that tests all available options and configurations",
            target_paths=[
                "src/api/auth.py",
                "src/models/user.py", 
                "tests/test_auth.py",
                "tests/test_user_model.py",
                "docs/api/auth.md"
            ],
            constraints=[
                "Must maintain backward compatibility",
                "No breaking API changes",
                "Performance impact < 10ms",
                "Memory usage increase < 50MB"
            ],
            risk_level="high",
            reviewers=["senior-dev-alice", "security-expert-bob", "architect-charlie"],
            model="gpt-4o",
            token_budget=12000,
            tests=TestConfig(coverage_min=95, pytest_args=["--strict-markers", "--verbose"]),
            quality=QualityOverrides(
                score_threshold=98,
                coverage_min=95,
                sast_high=0,
                secret_findings=0,
                budget_max=25.0
            ),
            hard_musts=[
                "All existing tests must pass",
                "Security review completed",
                "Performance benchmarks met",
                "Documentation updated",
                "Migration script provided"
            ]
        )
        
        # Validierung
        assert len(spec.target_paths) == 5
        assert len(spec.constraints) == 4
        assert len(spec.reviewers) == 3
        assert len(spec.hard_musts) == 5
        assert spec.tests.coverage_min == 95
        assert spec.quality.score_threshold == 98
        
        # Hash-Konsistenz
        hash1 = spec.sha256()
        assert len(hash1) == 64
        
        # Serialisierung
        json_str = spec.canonical_json()
        assert "COMPLEX-001" in json_str
        
        # Roundtrip-Test
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            spec.to_file(temp_path)
            loaded = FeatureSpec.from_file(temp_path)
            assert loaded.sha256() == spec.sha256()
        finally:
            temp_path.unlink(missing_ok=True)
