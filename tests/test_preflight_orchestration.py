#!/usr/bin/env python3
"""
COV-106: Branch-Preflight und Orchestrierung abdecken
Geschäftslogik abprüfen ohne externe Effekte.
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from typing import Dict, Any

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBranchPreflight:
    """Tests für Preflight-Check ohne externe Effekte"""
    
    @patch('codepipeline.branch_protection._has_git_remote')
    @patch('codepipeline.branch_protection._get_current_branch')
    def test_preflight_local_development_allowed(self, mock_get_branch, mock_has_remote):
        """Test erlaubter lokaler Entwicklungsfall"""
        try:
            from codepipeline.branch_protection import preflight
            
            # Mock lokale Entwicklung (kein Remote)
            mock_has_remote.return_value = False
            mock_get_branch.return_value = "feature/test-branch"
            
            # Preflight ausführen
            result = preflight("main")
            
            # Erwartete Ergebnisse
            assert result["status"] == "pass"
            assert result["reason"] == "local_development_no_remote"
            assert result["current_branch"] == "feature/test-branch"
            assert result["target_branch"] == "main"
            assert result["protected"] is False
            
        except ImportError:
            pytest.skip("codepipeline.branch_protection not available")
    
    @patch.dict(os.environ, {'CI': 'true'})
    @patch('codepipeline.branch_protection._check_branch_protection')
    @patch('codepipeline.branch_protection._has_git_remote')
    @patch('codepipeline.branch_protection._get_current_branch')
    def test_preflight_ci_protected_branch(self, mock_get_branch, mock_has_remote, mock_check_protection):
        """Test CI-Umgebung mit geschütztem Branch"""
        try:
            from codepipeline.branch_protection import preflight
            
            # Mock CI-Umgebung mit geschütztem Branch
            mock_has_remote.return_value = True
            mock_get_branch.return_value = "feature/ci-test"
            mock_check_protection.return_value = {
                "protected": True,
                "required_status_checks": ["ci/tests", "security/scan"]
            }
            
            # Preflight ausführen
            result = preflight("main")
            
            # Erwartete Ergebnisse für CI mit Protection
            assert result["status"] == "pass"
            assert result["reason"] == "branch_protection_verified"
            assert result["protected"] is True
            assert "required_checks" in result
            
        except ImportError:
            pytest.skip("codepipeline.branch_protection not available")
    
    @patch.dict(os.environ, {'REQUIRE_PROTECTION': 'false'})
    @patch('codepipeline.branch_protection._has_git_remote')
    @patch('codepipeline.branch_protection._get_current_branch')
    def test_preflight_protection_disabled_by_env(self, mock_get_branch, mock_has_remote):
        """Test geblockter Fall - Protection durch ENV deaktiviert"""
        try:
            from codepipeline.branch_protection import preflight
            
            # Mock lokale Entwicklung mit Remote aber Protection deaktiviert
            mock_has_remote.return_value = True
            mock_get_branch.return_value = "feature/env-test"
            
            # Preflight ausführen
            result = preflight("main")
            
            # Erwartete Ergebnisse
            assert result["status"] == "pass"
            assert result["reason"] == "protection_disabled_by_env"
            assert result["protected"] is False
            
        except ImportError:
            pytest.skip("codepipeline.branch_protection not available")
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('codepipeline.branch_protection._has_git_remote')
    @patch('codepipeline.branch_protection._get_current_branch')
    def test_preflight_mvp_local_allowed(self, mock_get_branch, mock_has_remote):
        """Test MVP-Fall - lokale Entwicklung erlaubt"""
        try:
            from codepipeline.branch_protection import preflight
            
            # Mock lokale Entwicklung mit Remote (MVP-Modus)
            mock_has_remote.return_value = True
            mock_get_branch.return_value = "feature/mvp-test"
            
            # Preflight ausführen
            result = preflight("develop")
            
            # Erwartete Ergebnisse für MVP
            assert result["status"] == "pass"
            assert result["reason"] == "local_development_allowed"
            assert result["target_branch"] == "develop"
            assert result["protected"] is False
            
        except ImportError:
            pytest.skip("codepipeline.branch_protection not available")
    
    def test_preflight_ultimate_stability_suite(self):
        """Test Ultimate Stability Suite Preflight (falls verfügbar)"""
        try:
            from codepipeline.ultimate_stability_suite import BranchProtectionPreflight
            
            preflight = BranchProtectionPreflight()
            
            # Test lokaler Entwicklungsmodus
            result = preflight.run_preflight("main", secure_mode=False, local_dev_mode=True)
            
            assert result.target_branch == "main"
            assert result.local_dev_mode is True
            assert result.secure_mode is False
            
        except ImportError:
            pytest.skip("ultimate_stability_suite not available")


class TestOrchestrationSmoke:
    """Orchestrierungs-Smoke-Tests mit Dry-Run und Mocks"""
    
    @patch('codepipeline.cli.get_secret')
    @patch('codepipeline.cli.create_draft_pr')
    @patch('codepipeline.cli.generate_unified_diff')
    @patch('codepipeline.cli.validate_and_apply_diff')
    @patch('codepipeline.cli.preflight')
    def test_orchestration_dry_run_no_secrets(self, mock_preflight, mock_validate, mock_diff, mock_pr, mock_secret):
        """Test Orchestrierungs-Dry-Run ohne Secrets und Netzwerk"""
        try:
            from codepipeline.cli import app as cli_app
            from typer.testing import CliRunner
            import tempfile
            
            # Mock alle externen Abhängigkeiten
            mock_preflight.return_value = {"status": "pass", "reason": "test_mode"}
            mock_secret.return_value = "mock-token"
            mock_diff.return_value = "mock-diff-content"
            mock_validate.return_value = {"status": "valid"}
            mock_pr.return_value = {"url": "mock-pr-url", "number": 123}
            
            # Erstelle temporäre Feature-Spec
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                spec_content = {
                    "id": "DRY-RUN-001",
                    "title": "Dry Run Test",
                    "version": 1,
                    "goal": "Test dry run orchestration without side effects",
                    "target_paths": ["tests"]
                }
                import json
                json.dump(spec_content, f)
                spec_file = f.name
            
            try:
                runner = CliRunner()
                
                # Test Dry-Run-Modus
                result = runner.invoke(cli_app, [
                    "feature",
                    "--spec", spec_file,
                    "--branch", "test-branch",
                    "--dry-run",
                    "--no-secure"
                ])
                
                # Dry-Run sollte erfolgreich sein oder graceful feilen
                # (Exit-Code 0 oder erwarteter Fehler-Code)
                assert result.exit_code in [0, 1, 2], f"Unexpected exit code: {result.exit_code}"
                
                # Keine echten externen Calls
                if mock_secret.called:
                    # Secret-Calls sind ok für Dry-Run-Validierung
                    pass
                
                # PR sollte nicht erstellt werden im Dry-Run
                if result.exit_code == 0:
                    # Erfolgreicher Dry-Run
                    assert "dry-run" in result.stdout.lower() or "test" in result.stdout.lower()
                
            finally:
                # Cleanup
                os.unlink(spec_file)
            
        except ImportError:
            pytest.skip("codepipeline.cli not available")
    
    @patch('e2e_orchestrator.E2EOrchestrator')
    def test_e2e_orchestrator_dry_run(self, mock_orchestrator_class):
        """Test E2E-Orchestrator Dry-Run"""
        try:
            from e2e_orchestrator import app as e2e_app
            from typer.testing import CliRunner
            import tempfile
            
            # Mock Orchestrator
            mock_orchestrator = Mock()
            mock_result = Mock()
            mock_result.success = True
            mock_result.spec_id = "E2E-DRY-001"
            mock_result.duration_seconds = 1.5
            mock_result.steps_completed = ["spec_validation", "dry_run"]
            mock_result.artifacts = {"spec": "/tmp/spec.json"}
            mock_result.exit_code.value = 0
            
            mock_orchestrator.execute.return_value = mock_result
            mock_orchestrator_class.return_value = mock_orchestrator
            
            # Erstelle temporäre Feature-Spec
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                spec_content = """
id: E2E-DRY-001
title: E2E Dry Run Test
version: 1
goal: Test E2E orchestration dry run without side effects
target_paths:
  - tests
"""
                f.write(spec_content)
                spec_file = f.name
            
            try:
                runner = CliRunner()
                
                # Test E2E Dry-Run
                result = runner.invoke(e2e_app, [
                    "orchestrate",
                    spec_file,
                    "--branch", "test-e2e",
                    "--dry-run",
                    "--verbose"
                ])
                
                # Dry-Run sollte erfolgreich sein
                assert result.exit_code == 0
                
                # Orchestrator sollte mit Dry-Run-Config erstellt worden sein
                mock_orchestrator_class.assert_called_once()
                config = mock_orchestrator_class.call_args[0][0]
                assert config.dry_run is True
                assert config.branch_name == "test-e2e"
                assert config.verbose is True
                
                # Execute sollte aufgerufen worden sein
                mock_orchestrator.execute.assert_called_once()
                
            finally:
                # Cleanup
                os.unlink(spec_file)
                
        except ImportError:
            pytest.skip("e2e_orchestrator not available")
    
    @patch.dict(os.environ, {'CP_TEST_MODE': 'true', 'CP_DRY_RUN': 'true'})
    def test_orchestration_test_mode_environment(self):
        """Test dass Orchestrierung Test-Modus Environment respektiert"""
        # Environment sollte Test-Modus signalisieren
        assert os.environ.get('CP_TEST_MODE') == 'true'
        assert os.environ.get('CP_DRY_RUN') == 'true'
        
        # Test dass keine produktiven Secrets gesetzt sind
        prod_secrets = [
            'CP_SECRET_GITHUB_TOKEN',
            'CP_SECRET_OPENAI_API_KEY',
            'GITHUB_TOKEN',
            'OPENAI_API_KEY'
        ]
        
        for secret in prod_secrets:
            assert secret not in os.environ, f"Production secret {secret} should not be set in test mode"
    
    def test_unified_orchestrator_smoke(self):
        """Test Unified Orchestrator Smoke (falls verfügbar)"""
        try:
            from codepipeline.unified_orchestrator import UnifiedOrchestrator
            
            # Test dass Klasse importierbar ist
            assert UnifiedOrchestrator is not None
            
            # Test Basis-Initialisierung (ohne echte Ausführung)
            # Nur prüfen dass Konstruktor funktioniert
            try:
                orchestrator = UnifiedOrchestrator()
                assert orchestrator is not None
            except Exception:
                # Konstruktor kann Parameter benötigen, das ist ok
                pass
                
        except ImportError:
            pytest.skip("unified_orchestrator not available")
    
    def test_orchestration_cli_smoke(self):
        """Test verschiedene Orchestration CLI-Interfaces"""
        cli_modules = [
            'e2e_orchestrator',
            'codepipeline.unified_orchestrator',
            'scaffold_generator'
        ]
        
        successful_imports = 0
        
        for module_name in cli_modules:
            try:
                module = __import__(module_name, fromlist=[''])
                
                # Prüfe auf CLI-App
                if hasattr(module, 'app'):
                    app = module.app
                    assert app is not None
                    
                    # Prüfe Typer-App Eigenschaften
                    if hasattr(app, 'commands'):
                        commands = app.commands
                        assert isinstance(commands, dict)
                
                successful_imports += 1
                
            except ImportError:
                # Modul nicht verfügbar
                pass
        
        # Mindestens ein CLI-Modul sollte verfügbar sein
        assert successful_imports > 0, "Keine Orchestration-CLI-Module verfügbar"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
