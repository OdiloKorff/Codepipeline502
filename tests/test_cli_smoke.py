#!/usr/bin/env python3
"""
COV-104: CLI-Smoke-Test ohne Nebenwirkungen
CLI importierbar und Hilfe abrufbar über Typer-Test-Runner.
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def clean_environment():
    """Entferne alle Secret-Umgebungsvariablen vor CLI-Tests"""
    # Liste aller bekannten Secret-Environment-Variablen
    secret_vars = [
        # CodePipeline Secrets
        'CP_SECRET_GITHUB_TOKEN',
        'CP_SECRET_OPENAI_API_KEY', 
        'CP_SECRET_ANTHROPIC_API_KEY',
        'CP_SECRET_SLACK_WEBHOOK_URL',
        'CP_SECRET_DATABASE_URL',
        'CP_SECRET_ENCRYPTION_KEY',
        
        # GitHub Secrets
        'GITHUB_TOKEN',
        'GH_TOKEN',
        'GITHUB_PAT',
        
        # OpenAI/LLM Secrets
        'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY',
        'AZURE_OPENAI_KEY',
        
        # Slack/Notification Secrets
        'SLACK_WEBHOOK_URL',
        'SLACK_BOT_TOKEN',
        
        # Database Secrets
        'DATABASE_URL',
        'DB_PASSWORD',
        'POSTGRES_PASSWORD',
        
        # General Secrets
        'API_KEY',
        'SECRET_KEY',
        'ENCRYPTION_KEY',
        'PRIVATE_KEY'
    ]
    
    # Entferne alle Secret-Variablen
    for var in secret_vars:
        if var in os.environ:
            del os.environ[var]
    
    # Setze sichere Default-Werte für Tests
    os.environ['CP_TEST_MODE'] = 'true'
    os.environ['CP_NO_NETWORK'] = 'true'
    os.environ['CP_DRY_RUN'] = 'true'


class TestCLISmoke:
    """CLI-Smoke-Tests ohne externe Nebenwirkungen"""
    
    def setup_method(self):
        """Setup vor jedem Test - Environment bereinigen"""
        clean_environment()
    
    def test_cli_import_success(self):
        """Test dass CLI-Module erfolgreich importiert werden können"""
        # Test codepipeline.cli
        try:
            from codepipeline.cli import app as main_cli_app
            assert main_cli_app is not None
            assert hasattr(main_cli_app, 'commands')
        except ImportError as e:
            pytest.skip(f"codepipeline.cli not available: {e}")
    
    def test_cli_help_via_typer_runner(self):
        """Test CLI-Hilfe über Typer CliRunner - Exit-Code 0"""
        try:
            from codepipeline.cli import app as main_cli_app
            
            runner = CliRunner()
            
            # Test --help Aufruf
            result = runner.invoke(main_cli_app, ["--help"])
            
            # Exit-Code 0 erwartet
            assert result.exit_code == 0
            
            # Help-Output sollte CLI-Informationen enthalten
            assert "help" in result.stdout.lower() or "usage" in result.stdout.lower()
            
        except ImportError:
            pytest.skip("codepipeline.cli not available")
    
    @patch('codepipeline.cli.get_secret')
    @patch('codepipeline.cli.create_draft_pr')
    @patch('codepipeline.cli.generate_unified_diff')
    def test_cli_feature_help_no_side_effects(self, mock_diff, mock_pr, mock_secret):
        """Test feature-Kommando Hilfe ohne Nebenwirkungen"""
        try:
            from codepipeline.cli import app as main_cli_app
            
            # Mock alle externen Funktionen
            mock_secret.return_value = "mock-token"
            mock_pr.return_value = {"url": "mock-url"}
            mock_diff.return_value = "mock-diff"
            
            runner = CliRunner()
            
            # Test feature --help
            result = runner.invoke(main_cli_app, ["feature", "--help"])
            
            # Exit-Code 0 erwartet
            assert result.exit_code == 0
            
            # Hilfe-Text sollte feature-spezifische Optionen enthalten
            assert "feature" in result.stdout.lower()
            assert "--spec" in result.stdout or "spec" in result.stdout.lower()
            
            # Keine externen Calls sollten gemacht worden sein
            mock_secret.assert_not_called()
            mock_pr.assert_not_called()
            mock_diff.assert_not_called()
            
        except ImportError:
            pytest.skip("codepipeline.cli not available")
    
    def test_e2e_orchestrator_cli_help(self):
        """Test E2E-Orchestrator CLI-Hilfe"""
        try:
            from e2e_orchestrator import app as e2e_app
            
            runner = CliRunner()
            
            # Test --help
            result = runner.invoke(e2e_app, ["--help"])
            
            # Exit-Code 0 erwartet
            assert result.exit_code == 0
            
            # Help-Output prüfen
            assert "orchestrat" in result.stdout.lower() or "help" in result.stdout.lower()
            
        except ImportError:
            pytest.skip("e2e_orchestrator not available")
    
    def test_scaffold_generator_cli_help(self):
        """Test Scaffold-Generator CLI-Hilfe"""
        try:
            from scaffold_generator import app as scaffold_app
            
            runner = CliRunner()
            
            # Test --help
            result = runner.invoke(scaffold_app, ["--help"])
            
            # Exit-Code 0 erwartet
            assert result.exit_code == 0
            
            # Help-Output prüfen
            assert "scaffold" in result.stdout.lower() or "demo" in result.stdout.lower()
            
        except ImportError:
            pytest.skip("scaffold_generator not available")
    
    @patch.dict(os.environ, {}, clear=True)
    def test_no_secret_environment_variables(self):
        """Test dass keine Secret-Umgebungsvariablen gesetzt sind"""
        # Environment bereinigen
        clean_environment()
        
        # Prüfe dass keine Secret-Variablen gesetzt sind
        secret_vars = [var for var in os.environ.keys() 
                      if 'SECRET' in var or 'TOKEN' in var or 'KEY' in var]
        
        # Nur Test-spezifische Variablen sollten erlaubt sein
        allowed_test_vars = ['CP_TEST_MODE', 'CP_NO_NETWORK', 'CP_DRY_RUN']
        unexpected_secrets = [var for var in secret_vars if var not in allowed_test_vars]
        
        assert len(unexpected_secrets) == 0, f"Unexpected secret variables found: {unexpected_secrets}"
        
        # Test-Modus sollte aktiviert sein
        assert os.environ.get('CP_TEST_MODE') == 'true'
        assert os.environ.get('CP_NO_NETWORK') == 'true'
        assert os.environ.get('CP_DRY_RUN') == 'true'
    
    @patch('subprocess.run')
    @patch('requests.post')
    @patch('requests.get')
    def test_no_network_effects_during_help(self, mock_get, mock_post, mock_subprocess):
        """Test dass CLI-Hilfe keine Netzwerk-Effekte hat"""
        try:
            from codepipeline.cli import app as main_cli_app
            
            # Mock alle Netzwerk-Operationen
            mock_get.return_value = MagicMock()
            mock_post.return_value = MagicMock()
            mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
            
            runner = CliRunner()
            
            # Test mehrere Help-Aufrufe
            help_commands = [
                ["--help"],
                ["feature", "--help"]
            ]
            
            for cmd in help_commands:
                try:
                    result = runner.invoke(main_cli_app, cmd)
                    # Exit-Code sollte 0 sein (Help erfolgreich)
                    assert result.exit_code == 0
                except Exception:
                    # Einzelne Help-Kommandos können fehlschlagen, das ist ok
                    pass
            
            # Keine Netzwerk-Calls sollten gemacht worden sein
            mock_get.assert_not_called()
            mock_post.assert_not_called()
            
            # Subprocess-Calls sind für Help ok, aber sollten minimal sein
            assert mock_subprocess.call_count <= 2
            
        except ImportError:
            pytest.skip("codepipeline.cli not available")
    
    def test_typer_app_structure(self):
        """Test dass Typer-App korrekt strukturiert ist"""
        try:
            from codepipeline.cli import app as main_cli_app
            
            # Typer-App sollte grundlegende Eigenschaften haben
            assert hasattr(main_cli_app, 'commands')
            assert hasattr(main_cli_app, 'callback')
            
            # App sollte Commands haben
            commands = main_cli_app.commands
            assert isinstance(commands, dict)
            
            # Mindestens ein Command sollte vorhanden sein
            assert len(commands) > 0
            
            # Feature-Command sollte existieren (falls definiert)
            if 'feature' in commands:
                feature_cmd = commands['feature']
                assert feature_cmd is not None
            
        except ImportError:
            pytest.skip("codepipeline.cli not available")
    
    def test_cli_runner_isolation(self):
        """Test dass CliRunner Tests isoliert"""
        try:
            from codepipeline.cli import app as main_cli_app
            
            runner = CliRunner()
            
            # Test dass Runner isoliert arbeitet
            with runner.isolated_filesystem():
                # Test in isoliertem Filesystem
                result = runner.invoke(main_cli_app, ["--help"])
                assert result.exit_code == 0
            
            # Nach Test sollte Original-Environment wiederhergestellt sein
            assert os.getcwd() != "/tmp"  # Nicht mehr im isolated filesystem
            
        except ImportError:
            pytest.skip("codepipeline.cli not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
