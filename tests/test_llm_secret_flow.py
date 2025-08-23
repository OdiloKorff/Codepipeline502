"""
Tests für den sauberen Secret Flow im LLM Gateway.

Testet die zentrale Secret-Verwaltung über ensure_env und die
frühe Validierung vor LLM-Calls.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Importiere die Module direkt ohne Package-Pfad
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_secrets import ensure_env, SecretNotAvailableError, validate_required_secrets
from llm_gateway import LLMGateway


class TestSecretFlow:
    """Tests für die zentrale Secret-Verwaltung."""
    
    def setup_method(self):
        """Setup vor jedem Test - entferne OPENAI_API_KEY aus Environment."""
        # Sichere den aktuellen Wert falls vorhanden
        self.original_key = os.environ.get("OPENAI_API_KEY")
        # Entferne aus Environment für saubere Tests
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
    
    def teardown_method(self):
        """Cleanup nach jedem Test - stelle Original-Zustand wieder her."""
        if self.original_key is not None:
            os.environ["OPENAI_API_KEY"] = self.original_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
    
    def test_ensure_env_with_existing_environment_variable(self):
        """Test: ensure_env mit bereits gesetzter Umgebungsvariable."""
        # Setze Dummy-Secret
        os.environ["OPENAI_API_KEY"] = "test-key-123"
        
        # ensure_env sollte erfolgreich sein
        ensure_env("OPENAI_API_KEY")
        
        # Variable sollte unverändert bleiben
        assert os.environ["OPENAI_API_KEY"] == "test-key-123"
    
    def test_ensure_env_missing_secret_no_vault_path(self):
        """Test: ensure_env mit fehlendem Secret und ohne Vault-Pfad."""
        # Teste mit unbekanntem Secret
        with pytest.raises(SecretNotAvailableError) as exc_info:
            ensure_env("UNKNOWN_SECRET")
        
        error_msg = str(exc_info.value)
        assert "UNKNOWN_SECRET" in error_msg
        assert "not found in environment" in error_msg
        assert "no Vault path configured" in error_msg
        assert "Available Vault paths" in error_msg
    
    @patch('app_secrets.get_secret')
    def test_ensure_env_fetch_from_vault_success(self, mock_get_secret):
        """Test: ensure_env holt erfolgreich Secret aus Vault."""
        # Mock Vault-Antwort
        mock_get_secret.return_value = "vault-secret-456"
        
        # ensure_env sollte Secret aus Vault holen
        ensure_env("OPENAI_API_KEY")
        
        # Secret sollte in Environment gesetzt sein
        assert os.environ["OPENAI_API_KEY"] == "vault-secret-456"
        
        # Vault sollte mit korrekten Parametern aufgerufen worden sein
        mock_get_secret.assert_called_once_with("openai", "OPENAI_API_KEY")
    
    @patch('app_secrets.get_secret')
    def test_ensure_env_vault_failure(self, mock_get_secret):
        """Test: ensure_env schlägt fehl wenn Vault nicht verfügbar ist."""
        # Mock Vault-Fehler
        mock_get_secret.side_effect = Exception("Vault connection failed")
        
        # ensure_env sollte SecretNotAvailableError werfen
        with pytest.raises(SecretNotAvailableError) as exc_info:
            ensure_env("OPENAI_API_KEY")
        
        error_msg = str(exc_info.value)
        assert "Failed to fetch secret 'OPENAI_API_KEY'" in error_msg
        assert "Vault connection failed" in error_msg
        
        # Secret sollte nicht in Environment gesetzt sein
        assert "OPENAI_API_KEY" not in os.environ
    
    def test_validate_required_secrets_all_available(self):
        """Test: validate_required_secrets mit verfügbaren Secrets."""
        # Setze erforderliche Secrets
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
        
        # Validierung sollte erfolgreich sein
        validate_required_secrets("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        
        # Keine Exception erwartet
    
    def test_validate_required_secrets_missing_secrets(self):
        """Test: validate_required_secrets mit fehlenden Secrets."""
        # Keine Secrets gesetzt
        
        # Validierung sollte fehlschlagen
        with pytest.raises(SecretNotAvailableError) as exc_info:
            validate_required_secrets("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        
        error_msg = str(exc_info.value)
        assert "Required secrets not available" in error_msg
        assert "OPENAI_API_KEY" in error_msg
        assert "ANTHROPIC_API_KEY" in error_msg


class TestLLMGatewaySecretIntegration:
    """Tests für die Secret-Integration im LLM Gateway."""
    
    def setup_method(self):
        """Setup vor jedem Test."""
        self.original_key = os.environ.get("OPENAI_API_KEY")
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
    
    def teardown_method(self):
        """Cleanup nach jedem Test."""
        if self.original_key is not None:
            os.environ["OPENAI_API_KEY"] = self.original_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
    
    def test_llm_gateway_initialization_missing_secret(self):
        """Test: LLMGateway Initialisierung schlägt fehl bei fehlendem Secret."""
        # Kein Secret gesetzt
        
        # Gateway-Initialisierung sollte fehlschlagen
        with pytest.raises(SecretNotAvailableError) as exc_info:
            LLMGateway()
        
        error_msg = str(exc_info.value)
        assert "OPENAI_API_KEY" in error_msg
    
    def test_llm_gateway_initialization_with_dummy_secret(self):
        """Test: LLMGateway Initialisierung erfolgreich mit Dummy-Secret."""
        # Setze Dummy-Secret
        os.environ["OPENAI_API_KEY"] = "sk-dummy-test-key-for-testing-only"
        
        # Gateway-Initialisierung sollte erfolgreich sein
        gateway = LLMGateway()
        
        # Gateway sollte erstellt worden sein
        assert gateway is not None
        assert gateway._client is not None
    
    def test_llm_gateway_skip_validation(self):
        """Test: LLMGateway kann Secret-Validierung überspringen."""
        # Kein Secret gesetzt, aber Validierung deaktiviert
        
        # Mock OpenAI Client für diesen Test
        mock_client = MagicMock()
        
        # Gateway mit deaktivierter Validierung
        gateway = LLMGateway(client=mock_client, validate_secrets=False)
        
        # Gateway sollte erfolgreich erstellt werden
        assert gateway is not None
        assert gateway._client is mock_client
    
    @patch('app_secrets.get_secret')
    def test_llm_gateway_with_vault_secret(self, mock_get_secret):
        """Test: LLMGateway mit Secret aus Vault."""
        # Mock Vault-Antwort
        mock_get_secret.return_value = "sk-vault-secret-from-vault-system"
        
        # Gateway-Initialisierung sollte Secret aus Vault holen
        gateway = LLMGateway()
        
        # Secret sollte aus Vault geholt worden sein
        mock_get_secret.assert_called_once_with("openai", "OPENAI_API_KEY")
        
        # Environment sollte das Secret enthalten
        assert os.environ["OPENAI_API_KEY"] == "sk-vault-secret-from-vault-system"
        
        # Gateway sollte erstellt worden sein
        assert gateway is not None
    
    def test_multiple_gateway_instances_reuse_secret(self):
        """Test: Mehrere Gateway-Instanzen verwenden dasselbe Secret."""
        # Setze Secret
        os.environ["OPENAI_API_KEY"] = "sk-shared-secret-key"
        
        # Erstelle mehrere Gateway-Instanzen
        gateway1 = LLMGateway()
        gateway2 = LLMGateway()
        
        # Beide sollten erfolgreich erstellt werden
        assert gateway1 is not None
        assert gateway2 is not None
        
        # Secret sollte unverändert bleiben
        assert os.environ["OPENAI_API_KEY"] == "sk-shared-secret-key"


class TestSecretFlowEdgeCases:
    """Tests für Edge Cases im Secret Flow."""
    
    def setup_method(self):
        """Setup vor jedem Test."""
        self.original_key = os.environ.get("OPENAI_API_KEY")
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
    
    def teardown_method(self):
        """Cleanup nach jedem Test."""
        if self.original_key is not None:
            os.environ["OPENAI_API_KEY"] = self.original_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
    
    def test_empty_secret_value(self):
        """Test: Leerer Secret-Wert wird als fehlend behandelt."""
        # Setze leeres Secret
        os.environ["OPENAI_API_KEY"] = ""
        
        # ensure_env sollte das als "nicht vorhanden" behandeln
        # (da os.getenv("") als falsy gilt)
        with pytest.raises(SecretNotAvailableError):
            # Mock get_secret um Vault-Aufruf zu verhindern
            with patch('app_secrets.get_secret', side_effect=Exception("No vault")):
                ensure_env("OPENAI_API_KEY")
    
    def test_whitespace_only_secret(self):
        """Test: Secret mit nur Whitespace."""
        # Setze Secret mit nur Leerzeichen
        os.environ["OPENAI_API_KEY"] = "   "
        
        # ensure_env sollte das akzeptieren (ist technisch gesetzt)
        ensure_env("OPENAI_API_KEY")
        
        # Secret sollte unverändert bleiben
        assert os.environ["OPENAI_API_KEY"] == "   "
    
    @patch('app_secrets.get_secret')
    def test_vault_returns_empty_secret(self, mock_get_secret):
        """Test: Vault gibt leeres Secret zurück."""
        # Mock Vault gibt leeren String zurück
        mock_get_secret.return_value = ""
        
        # ensure_env sollte das leere Secret setzen
        ensure_env("OPENAI_API_KEY")
        
        # Environment sollte leeres Secret enthalten
        assert os.environ["OPENAI_API_KEY"] == ""
    
    def test_case_sensitive_secret_names(self):
        """Test: Secret-Namen sind case-sensitive."""
        # Setze Secret mit falscher Groß-/Kleinschreibung
        os.environ["openai_api_key"] = "lowercase-key"
        
        # ensure_env mit korrekter Schreibweise sollte fehlschlagen
        with pytest.raises(SecretNotAvailableError):
            with patch('app_secrets.get_secret', side_effect=Exception("No vault")):
                ensure_env("OPENAI_API_KEY")


def test_integration_complete_flow():
    """Integrations-Test für den kompletten Secret Flow."""
    # Sichere Original-Zustand
    original_key = os.environ.get("OPENAI_API_KEY")
    
    try:
        # 1. Starte ohne Secret
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        
        # 2. Gateway-Erstellung sollte fehlschlagen
        with pytest.raises(SecretNotAvailableError) as exc_info:
            LLMGateway()
        
        assert "OPENAI_API_KEY" in str(exc_info.value)
        
        # 3. Setze Dummy-Secret
        os.environ["OPENAI_API_KEY"] = "sk-test-integration-key-12345"
        
        # 4. Gateway-Erstellung sollte jetzt erfolgreich sein
        gateway = LLMGateway()
        assert gateway is not None
        
        # 5. Secret sollte verfügbar sein
        assert os.environ["OPENAI_API_KEY"] == "sk-test-integration-key-12345"
        
        # 6. Weitere Gateway-Instanzen sollten das gleiche Secret verwenden
        gateway2 = LLMGateway()
        assert gateway2 is not None
        
        print("✅ Integrations-Test erfolgreich abgeschlossen")
        
    finally:
        # Stelle Original-Zustand wieder her
        if original_key is not None:
            os.environ["OPENAI_API_KEY"] = original_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]


if __name__ == "__main__":
    # Führe Integrations-Test aus
    test_integration_complete_flow()
    print("🎉 Alle Tests erfolgreich!")
