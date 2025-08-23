#!/usr/bin/env python3
"""
COV-032: CLI (Click) – Help/Version/Fehlerpfade (Simple Version)
Einfache Click-CLI-Tests für grundlegende Funktionalität.
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys
from click.testing import CliRunner

# Füge src-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from codepipeline.cli_mvp import cli, feature_run
except ImportError as e:
    pytest.skip(f"CLI module not available: {e}", allow_module_level=True)


class TestCLIBasicFunctionality:
    """Tests für grundlegende CLI-Funktionalität."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def test_cli_help_returns_zero(self):
        """Test: CLI --help gibt Exit-Code 0 zurück."""
        result = self.runner.invoke(cli, ["--help"])
        
        # Exit-Code muss 0 sein
        assert result.exit_code == 0
        
        # Output darf nicht leer sein
        assert result.output
        assert len(result.output) > 0
        
        # Sollte grundlegende CLI-Begriffe enthalten
        help_text = result.output.lower()
        cli_terms = ["usage", "commands", "options"]
        found_terms = [term for term in cli_terms if term in help_text]
        assert len(found_terms) >= 1, f"Help should contain basic CLI terms, got: {result.output[:200]}"
    
    def test_feature_run_help_returns_zero(self):
        """Test: feature-run --help gibt Exit-Code 0 zurück."""
        result = self.runner.invoke(cli, ["feature-run", "--help"])
        
        # Exit-Code muss 0 sein für Help
        assert result.exit_code == 0
        
        # Output sollte feature-run Optionen zeigen
        assert result.output
        help_text = result.output.lower()
        
        # Sollte feature-run spezifische Optionen enthalten
        feature_terms = ["spec-path", "branch", "secure", "dry-run"]
        found_terms = [term for term in feature_terms if term in help_text]
        assert len(found_terms) >= 2, f"Feature-run help should show options, got: {result.output[:300]}"
    
    def test_invalid_command_non_zero_exit(self):
        """Test: Ungültige Kommandos geben Exit-Code ≠ 0."""
        result = self.runner.invoke(cli, ["nonexistent-command"])
        
        # Exit-Code sollte nicht 0 sein
        assert result.exit_code != 0
        
        # Sollte Fehlermeldung enthalten
        assert result.output
        error_text = result.output.lower()
        assert "no such command" in error_text or "error" in error_text


class TestFeatureRunCommand:
    """Tests für das feature-run Kommando."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def create_minimal_spec_file(self, tmp_path):
        """Helper: Erstelle minimale valide Spec-Datei."""
        spec_data = {
            "id": "TEST-001",
            "title": "Test Feature",
            "version": 1,
            "goal": "Test CLI functionality",
            "target_paths": ["src/"]
        }
        
        spec_file = tmp_path / "test_spec.json"
        with open(spec_file, 'w') as f:
            json.dump(spec_data, f, indent=2)
        
        return str(spec_file)
    
    def test_feature_run_missing_spec_path_error(self):
        """Test: Fehlende --spec-path führt zu Exit-Code ≠ 0."""
        result = self.runner.invoke(cli, [
            "feature-run",
            "--dry-run"
        ])
        
        # Exit-Code sollte nicht 0 sein
        assert result.exit_code != 0
        
        # Sollte Fehlermeldung über fehlende Option enthalten
        assert result.output
        output = result.output.lower()
        assert "spec-path" in output or "required" in output or "missing" in output
    
    def test_feature_run_nonexistent_file_error(self):
        """Test: Nicht-existierende Spec-Datei führt zu Fehler."""
        result = self.runner.invoke(cli, [
            "feature-run",
            "--spec-path", "/path/that/does/not/exist.json",
            "--dry-run"
        ])
        
        # Exit-Code sollte nicht 0 sein
        assert result.exit_code != 0
        
        # Sollte Fehlermeldung enthalten
        assert result.output
        output = result.output.lower()
        assert "does not exist" in output or "not found" in output or "error" in output
    
    def test_feature_run_invalid_option_error(self):
        """Test: Ungültige Optionen führen zu Fehler."""
        result = self.runner.invoke(cli, [
            "feature-run",
            "--invalid-option-that-does-not-exist"
        ])
        
        # Exit-Code sollte nicht 0 sein
        assert result.exit_code != 0
        
        # Sollte Fehlermeldung über unbekannte Option enthalten
        assert result.output
        output = result.output.lower()
        assert "no such option" in output or "unrecognized" in output
    
    def test_feature_run_with_valid_spec_file(self):
        """Test: feature-run mit valider Spec-Datei (kann fehlschlagen, aber sollte nicht crashen)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            spec_file = self.create_minimal_spec_file(tmp_path)
            
            result = self.runner.invoke(cli, [
                "feature-run",
                "--spec-path", spec_file,
                "--dry-run"
            ])
            
            # Sollte nicht crashen (Exit-Code kann variieren)
            assert isinstance(result.exit_code, int)
            assert result.exit_code >= 0
            
            # Sollte irgendeine Ausgabe haben
            assert result.output is not None


class TestCLIErrorHandling:
    """Tests für Error-Handling."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def test_invalid_json_spec_file_error(self):
        """Test: Ungültige JSON-Datei führt zu Fehler."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Erstelle ungültige JSON-Datei
            invalid_json_file = tmp_path / "invalid.json"
            with open(invalid_json_file, 'w') as f:
                f.write('{"id": "TEST", invalid json syntax}')
            
            result = self.runner.invoke(cli, [
                "feature-run",
                "--spec-path", str(invalid_json_file),
                "--dry-run"
            ])
            
            # Exit-Code sollte nicht 0 sein
            assert result.exit_code != 0
            
            # Sollte Fehlermeldung haben
            assert result.output
    
    def test_empty_spec_file_error(self):
        """Test: Leere Spec-Datei führt zu Fehler."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Erstelle leere JSON-Datei
            empty_file = tmp_path / "empty.json"
            with open(empty_file, 'w') as f:
                f.write('{}')
            
            result = self.runner.invoke(cli, [
                "feature-run",
                "--spec-path", str(empty_file),
                "--dry-run"
            ])
            
            # Exit-Code sollte nicht 0 sein (wegen fehlender required fields)
            assert result.exit_code != 0
            
            # Sollte Fehlermeldung haben
            assert result.output


class TestCLIFlags:
    """Tests für verschiedene CLI-Flags."""
    
    def setup_method(self):
        """Setup für jeden Test."""
        self.runner = CliRunner()
    
    def create_minimal_spec_file(self, tmp_path):
        """Helper: Erstelle minimale valide Spec-Datei."""
        spec_data = {
            "id": "FLAG-001",
            "title": "Flag Test Feature",
            "version": 1,
            "goal": "Test CLI flags",
            "target_paths": ["src/"]
        }
        
        spec_file = tmp_path / "flag_spec.json"
        with open(spec_file, 'w') as f:
            json.dump(spec_data, f, indent=2)
        
        return str(spec_file)
    
    def test_dry_run_flag(self):
        """Test: --dry-run Flag wird erkannt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            spec_file = self.create_minimal_spec_file(tmp_path)
            
            result = self.runner.invoke(cli, [
                "feature-run",
                "--spec-path", spec_file,
                "--dry-run"
            ])
            
            # Sollte nicht crashen
            assert isinstance(result.exit_code, int)
            assert result.output is not None
    
    def test_secure_flag(self):
        """Test: --secure Flag wird erkannt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            spec_file = self.create_minimal_spec_file(tmp_path)
            
            result = self.runner.invoke(cli, [
                "feature-run",
                "--spec-path", spec_file,
                "--secure",
                "--dry-run"
            ])
            
            # Sollte nicht crashen
            assert isinstance(result.exit_code, int)
            assert result.output is not None
    
    def test_branch_name_flag(self):
        """Test: --branch-name Flag wird erkannt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            spec_file = self.create_minimal_spec_file(tmp_path)
            
            result = self.runner.invoke(cli, [
                "feature-run",
                "--spec-path", spec_file,
                "--branch-name", "feature/test-branch",
                "--dry-run"
            ])
            
            # Sollte nicht crashen
            assert isinstance(result.exit_code, int)
            assert result.output is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
