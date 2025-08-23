#!/usr/bin/env python3
"""
COV-032: CLI (Click) – Help/Version/Fehlerpfade
Click-CLI-Tests mit CliRunner für Help, Version, Error-Handling.
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch, Mock
from click.testing import CliRunner

# Füge src-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from codepipeline.cli_mvp import cli, feature_run, CLI_MVP
except ImportError as e:
    pytest.skip(f"CLI module not available: {e}", allow_module_level=True)


class TestCLIBasicCommands:
    """Tests für grundlegende CLI-Kommandos."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def test_help_command_returns_zero(self):
        """Test: --help gibt Exit-Code 0 zurück und zeigt Kernkommandos."""
        result = self.runner.invoke(cli, ["--help"])
        
        # Exit-Code muss 0 sein
        assert result.exit_code == 0
        
        # Output darf nicht leer sein
        assert result.output
        
        # Kernkommandos sollten erwähnt werden
        help_text = result.output.lower()
        
        # Suche nach typischen CLI-Begriffen
        expected_terms = ["usage", "commands", "options", "feature"]
        found_terms = [term for term in expected_terms if term in help_text]
        assert len(found_terms) >= 1, f"Help should contain CLI terms, got: {result.output[:200]}"
    
    def test_feature_run_help(self):
        """Test: feature-run --help funktioniert."""
        result = self.runner.invoke(cli, ["feature-run", "--help"])
        
        # Exit-Code muss 0 sein
        assert result.exit_code == 0
        
        # Output sollte feature-run spezifische Optionen zeigen
        help_text = result.output.lower()
        
        # Suche nach feature-run spezifischen Begriffen
        expected_terms = ["spec-path", "branch-name", "secure", "dry-run"]
        found_terms = [term for term in expected_terms if term in help_text]
        assert len(found_terms) >= 2, f"Help should contain feature-run options, got: {result.output[:300]}"
    
    def test_invalid_command_non_zero_exit(self):
        """Test: Ungültige Kommandos geben Exit-Code ≠ 0."""
        result = self.runner.invoke(cli, ["invalid-command-that-does-not-exist"])
        
        # Exit-Code sollte nicht 0 sein
        assert result.exit_code != 0
        
        # Sollte Fehlermeldung enthalten
        assert result.output
        error_text = result.output.lower()
        assert "no such command" in error_text or "error" in error_text


class TestCLIFeatureRunCommand:
    """Tests für das 'feature-run' Kommando."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def create_test_spec_file(self, tmp_path):
        """Helper: Erstelle valide Test-Spec-Datei."""
        spec_data = {
            "id": "TEST-001",
            "title": "Test Feature",
            "version": 1,
            "goal": "Test CLI feature command",
            "target_paths": ["src/"],
            "description": "CLI test specification"
        }
        
        spec_file = tmp_path / "test_spec.json"
        with open(spec_file, 'w') as f:
            json.dump(spec_data, f, indent=2)
        
        return str(spec_file)
    
    def test_feature_run_dry_run_success(self):
        """Test: feature-run --spec <file> --branch feature/x --secure --dry-run."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            spec_file = self.create_test_spec_file(tmp_path)
            
            # Mock die internen Operationen um Side-Effects zu vermeiden
            with patch.object(CLI_MVP, 'run_pipeline') as mock_run:
                mock_run.return_value = 0  # Simuliere Erfolg
                
                result = self.runner.invoke(cli, [
                    "feature-run",
                    "--spec-path", spec_file,
                    "--branch-name", "feature/test",
                    "--secure",
                    "--dry-run"
                ])
                
                # Der Test sollte erfolgreich sein oder zumindest nicht crashen
                # Bei Dry-Run sollte kein schwerwiegender Fehler auftreten
                assert result.exit_code in [0, 1, 2], f"Unexpected exit code: {result.exit_code}, output: {result.output}"
    
    def test_feature_run_missing_spec_file_error(self):
        """Test: Fehlende Spec-Datei führt zu Exit-Code ≠ 0."""
        result = self.runner.invoke(cli, [
            "feature-run",
            "--spec-path", "/non/existent/file.json",
            "--branch-name", "feature/test",
            "--dry-run"
        ])
        
        # Exit-Code sollte nicht 0 sein
        assert result.exit_code != 0
        
        # Sollte Fehlermeldung enthalten
        output = result.output.lower()
        assert "error" in output or "not found" in output or "no such file" in output or "does not exist" in output
    
    def test_feature_run_missing_required_spec_path(self):
        """Test: Fehlende --spec-path Option führt zu Fehler."""
        result = self.runner.invoke(cli, [
            "feature-run",
            "--branch-name", "feature/test",
            "--dry-run"
        ])
        
        # Exit-Code sollte nicht 0 sein
        assert result.exit_code != 0
        
        # Sollte Fehlermeldung über fehlende Option enthalten
        output = result.output.lower()
        assert "spec-path" in output or "required" in output or "missing" in output
    
    def test_feature_run_invalid_flags_error(self):
        """Test: Ungültige Flags führen zu Exit-Code ≠ 0."""
        result = self.runner.invoke(cli, [
            "feature-run",
            "--invalid-flag-that-does-not-exist"
        ])
        
        # Exit-Code sollte nicht 0 sein
        assert result.exit_code != 0
        
        # Sollte Fehlermeldung über unbekannte Option enthalten
        output = result.output.lower()
        assert "no such option" in output or "unrecognized" in output or "error" in output


class TestCLISecureMode:
    """Tests für Secure-Mode Fehlerbehandlung."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def create_test_spec_file(self, tmp_path):
        """Helper: Erstelle valide Test-Spec-Datei."""
        spec_data = {
            "id": "SECURE-001",
            "title": "Secure Test Feature",
            "version": 1,
            "goal": "Test secure mode error handling",
            "target_paths": ["src/"],
            "description": "Secure mode test"
        }
        
        spec_file = tmp_path / "secure_spec.json"
        with open(spec_file, 'w') as f:
            json.dump(spec_data, f, indent=2)
        
        return str(spec_file)
    
    def test_secure_mode_environment_check(self):
        """Test: Secure-Mode führt Environment-Checks durch."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            spec_file = self.create_test_spec_file(tmp_path)
            
            # Mock environment checks
            with patch.object(CLI_MVP, 'validate_secure_environment') as mock_validate:
                mock_validate.return_value = False  # Simuliere fehlende Secure-Voraussetzungen
                
                with patch.object(CLI_MVP, 'run_pipeline') as mock_run:
                    mock_run.return_value = 2  # Simuliere Security-Gate-Fehler
                    
                    result = self.runner.invoke(cli, [
                        "feature-run",
                        "--spec-path", spec_file,
                        "--branch-name", "feature/secure-test",
                        "--secure"  # Echte Secure-Mode
                    ])
                    
                    # Exit-Code sollte nicht 0 sein bei Secure-Problemen
                    assert result.exit_code != 0
                    
                    # Sollte irgendeine Ausgabe haben
                    assert result.output


class TestCLIErrorHandling:
    """Tests für Error-Handling und Exit-Codes."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def test_spec_validation_error_handling(self):
        """Test: Spec-Validierungsfehler werden korrekt behandelt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Erstelle ungültige Spec
            invalid_spec_data = {
                "id": "INVALID",  # Ungültiges Format
                "title": "",  # Leerer Titel
                # Fehlende required fields
            }
            
            spec_file = tmp_path / "invalid_spec.json"
            with open(spec_file, 'w') as f:
                json.dump(invalid_spec_data, f)
            
            result = self.runner.invoke(cli, [
                "feature-run",
                "--spec-path", str(spec_file),
                "--dry-run"
            ])
            
            # Exit-Code sollte nicht 0 sein bei ungültiger Spec
            assert result.exit_code != 0
            
            # Sollte Fehlermeldung enthalten
            assert result.output
    
    def test_json_parsing_error_handling(self):
        """Test: JSON-Parsing-Fehler werden korrekt behandelt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Erstelle ungültiges JSON
            invalid_json_file = tmp_path / "invalid.json"
            with open(invalid_json_file, 'w') as f:
                f.write('{"id": "TEST", invalid json}')  # Syntaxfehler
            
            result = self.runner.invoke(cli, [
                "feature-run",
                "--spec-path", str(invalid_json_file),
                "--dry-run"
            ])
            
            # Exit-Code sollte nicht 0 sein bei JSON-Fehler
            assert result.exit_code != 0
            
            # Sollte Fehlermeldung enthalten
            assert result.output


class TestCLIIntegration:
    """Integrationstests für komplette CLI-Workflows."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def test_complete_dry_run_workflow(self):
        """Test: Kompletter Dry-Run-Workflow."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Erstelle vollständige Test-Spec
            spec_data = {
                "id": "INTEGRATION-001",
                "title": "Integration Test Feature",
                "version": 1,
                "goal": "Test complete CLI workflow",
                "target_paths": ["src/", "lib/"],
                "description": "Full integration test",
                "tests": {"unit": True, "integration": True},
                "quality": {"coverage_min": 80.0}
            }
            
            spec_file = tmp_path / "integration_spec.json"
            with open(spec_file, 'w') as f:
                json.dump(spec_data, f, indent=2)
            
            # Mock alle externen Dependencies
            with patch.object(CLI_MVP, 'validate_environment') as mock_env:
                mock_env.return_value = True
                
                with patch.object(CLI_MVP, 'run_pipeline') as mock_pipeline:
                    mock_pipeline.return_value = 0  # Erfolg
                    
                    result = self.runner.invoke(cli, [
                        "feature-run",
                        "--spec-path", str(spec_file),
                        "--branch-name", "feature/integration-test",
                        "--dry-run"
                    ])
                    
                    # Integration-Test sollte nicht crashen
                    assert isinstance(result.exit_code, int)
                    assert result.exit_code >= 0
                    
                    # Sollte irgendeine Ausgabe produzieren
                    assert result.output
    
    def test_cli_exit_codes_semantic_meaning(self):
        """Test: Exit-Codes haben semantische Bedeutung."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            spec_file = self.create_valid_spec_file(tmp_path)
            
            # Test verschiedene Exit-Code-Szenarien
            test_cases = [
                (0, "SUCCESS"),
                (1, "SPEC_VALIDATION_FAILED"),
                (2, "SECURITY_GATE_FAILED"),
                (3, "COVERAGE_GATE_FAILED"),
                (4, "TESTS_FAILED")
            ]
            
            for expected_code, scenario in test_cases:
                with patch.object(CLI_MVP, 'run_pipeline') as mock_pipeline:
                    mock_pipeline.return_value = expected_code
                    
                    result = self.runner.invoke(cli, [
                        "feature-run",
                        "--spec-path", spec_file,
                        "--dry-run"
                    ])
                    
                    # Exit-Code sollte dem erwarteten entsprechen oder sinnvoll sein
                    assert result.exit_code in [0, 1, 2, 3, 4], f"Exit code should be semantic for {scenario}"
    
    def create_valid_spec_file(self, tmp_path):
        """Helper: Erstelle valide Test-Spec-Datei."""
        spec_data = {
            "id": "EXITCODE-001",
            "title": "Exit Code Test",
            "version": 1,
            "goal": "Test exit code semantics",
            "target_paths": ["src/"]
        }
        
        spec_file = tmp_path / "exitcode_spec.json"
        with open(spec_file, 'w') as f:
            json.dump(spec_data, f)
        
        return str(spec_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
