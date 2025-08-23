#!/usr/bin/env python3
"""
Standalone Test für den sauberen Secret Flow.

Testet die Secret-Verwaltung ohne hvac-Abhängigkeiten durch Mocking.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Füge Projekt-Root zum Python-Path hinzu
sys.path.insert(0, str(Path(__file__).parent))


def test_secret_flow():
    """Haupttest für den sauberen Secret Flow."""
    print("🧪 Teste sauberen Secret Flow...")
    
    # Sichere Original-Zustand
    original_key = os.environ.get("OPENAI_API_KEY")
    
    try:
        # Entferne OPENAI_API_KEY für sauberen Test
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        
        # Mock hvac um Import-Probleme zu vermeiden
        with patch.dict('sys.modules', {'hvac': MagicMock()}):
            from app_secrets import SecretNotAvailableError, ensure_env, validate_required_secrets
            from llm_gateway import LLMGateway
            
            test_results = []
            
            # Test 1: Fehlende Secret-Variable wirft Exception
            print("\n1️⃣ Test: Fehlende Secret-Variable")
            try:
                LLMGateway()
                print("   ❌ Exception erwartet, aber keine geworfen")
                test_results.append(("missing_secret_exception", False))
            except SecretNotAvailableError as e:
                if "OPENAI_API_KEY" in str(e):
                    print("   ✅ Korrekte SecretNotAvailableError geworfen")
                    test_results.append(("missing_secret_exception", True))
                else:
                    print(f"   ❌ Falsche Exception-Message: {e}")
                    test_results.append(("missing_secret_exception", False))
            except Exception as e:
                print(f"   ❌ Unerwartete Exception: {type(e).__name__}: {e}")
                test_results.append(("missing_secret_exception", False))
            
            # Test 2: Dummy-Secret führt nicht zum Crash
            print("\n2️⃣ Test: Dummy-Secret verhindert Crash")
            try:
                os.environ["OPENAI_API_KEY"] = "sk-dummy-test-key-12345"
                gateway = LLMGateway()
                
                if gateway is not None and hasattr(gateway, '_client'):
                    print("   ✅ LLMGateway erfolgreich mit Dummy-Secret erstellt")
                    test_results.append(("dummy_secret_success", True))
                else:
                    print("   ❌ LLMGateway nicht korrekt initialisiert")
                    test_results.append(("dummy_secret_success", False))
            except Exception as e:
                print(f"   ❌ Unerwartete Exception mit Dummy-Secret: {type(e).__name__}: {e}")
                test_results.append(("dummy_secret_success", False))
            
            # Test 3: ensure_env mit gesetzter Variable
            print("\n3️⃣ Test: ensure_env mit bereits gesetzter Variable")
            try:
                os.environ["OPENAI_API_KEY"] = "existing-key-789"
                ensure_env("OPENAI_API_KEY")
                
                if os.environ.get("OPENAI_API_KEY") == "existing-key-789":
                    print("   ✅ ensure_env respektiert bestehende Variable")
                    test_results.append(("ensure_env_existing", True))
                else:
                    print("   ❌ ensure_env hat bestehende Variable verändert")
                    test_results.append(("ensure_env_existing", False))
            except Exception as e:
                print(f"   ❌ Exception bei ensure_env mit bestehender Variable: {e}")
                test_results.append(("ensure_env_existing", False))
            
            # Test 4: ensure_env mit unbekanntem Secret
            print("\n4️⃣ Test: ensure_env mit unbekanntem Secret")
            try:
                ensure_env("UNKNOWN_SECRET_XYZ")
                print("   ❌ Exception erwartet für unbekanntes Secret")
                test_results.append(("unknown_secret", False))
            except SecretNotAvailableError as e:
                if "UNKNOWN_SECRET_XYZ" in str(e) and "no Vault path configured" in str(e):
                    print("   ✅ Korrekte Exception für unbekanntes Secret")
                    test_results.append(("unknown_secret", True))
                else:
                    print(f"   ❌ Falsche Exception-Message: {e}")
                    test_results.append(("unknown_secret", False))
            except Exception as e:
                print(f"   ❌ Unerwartete Exception: {type(e).__name__}: {e}")
                test_results.append(("unknown_secret", False))
            
            # Test 5: validate_required_secrets mit verfügbaren Secrets
            print("\n5️⃣ Test: validate_required_secrets mit verfügbaren Secrets")
            try:
                os.environ["OPENAI_API_KEY"] = "test-key-123"
                os.environ["ANTHROPIC_API_KEY"] = "test-key-456"
                
                validate_required_secrets("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
                print("   ✅ validate_required_secrets erfolgreich mit verfügbaren Secrets")
                test_results.append(("validate_available_secrets", True))
            except Exception as e:
                print(f"   ❌ Unerwartete Exception: {type(e).__name__}: {e}")
                test_results.append(("validate_available_secrets", False))
            
            # Test 6: validate_required_secrets mit fehlenden Secrets
            print("\n6️⃣ Test: validate_required_secrets mit fehlenden Secrets")
            try:
                # Entferne Secrets
                if "OPENAI_API_KEY" in os.environ:
                    del os.environ["OPENAI_API_KEY"]
                if "ANTHROPIC_API_KEY" in os.environ:
                    del os.environ["ANTHROPIC_API_KEY"]
                
                validate_required_secrets("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
                print("   ❌ Exception erwartet für fehlende Secrets")
                test_results.append(("validate_missing_secrets", False))
            except SecretNotAvailableError as e:
                if "Required secrets not available" in str(e):
                    print("   ✅ Korrekte Exception für fehlende Secrets")
                    test_results.append(("validate_missing_secrets", True))
                else:
                    print(f"   ❌ Falsche Exception-Message: {e}")
                    test_results.append(("validate_missing_secrets", False))
            except Exception as e:
                print(f"   ❌ Unerwartete Exception: {type(e).__name__}: {e}")
                test_results.append(("validate_missing_secrets", False))
            
            # Test 7: LLMGateway mit deaktivierter Validierung
            print("\n7️⃣ Test: LLMGateway mit deaktivierter Secret-Validierung")
            try:
                # Entferne Secret
                if "OPENAI_API_KEY" in os.environ:
                    del os.environ["OPENAI_API_KEY"]
                
                # Mock Client für diesen Test
                mock_client = MagicMock()
                gateway = LLMGateway(client=mock_client, validate_secrets=False)
                
                if gateway._client is mock_client:
                    print("   ✅ LLMGateway mit deaktivierter Validierung erfolgreich")
                    test_results.append(("skip_validation", True))
                else:
                    print("   ❌ Mock-Client nicht korrekt gesetzt")
                    test_results.append(("skip_validation", False))
            except Exception as e:
                print(f"   ❌ Exception bei deaktivierter Validierung: {type(e).__name__}: {e}")
                test_results.append(("skip_validation", False))
            
            # Zusammenfassung
            print("\n" + "="*60)
            print("📊 TEST ZUSAMMENFASSUNG - SECRET FLOW")
            print("="*60)
            
            passed = sum(1 for _, result in test_results if result)
            total = len(test_results)
            
            for test_name, result in test_results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} {test_name}")
            
            print(f"\n🎯 Ergebnis: {passed}/{total} Tests bestanden")
            
            if passed == total:
                print("🎉 Alle Secret Flow Tests erfolgreich!")
                return True
            else:
                print("💥 Einige Secret Flow Tests fehlgeschlagen!")
                return False
    
    finally:
        # Stelle Original-Zustand wieder her
        if original_key is not None:
            os.environ["OPENAI_API_KEY"] = original_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]


def test_specific_requirements():
    """Test der spezifischen Anforderungen aus dem Prompt."""
    print("\n" + "="*60)
    print("🎯 SPEZIFISCHE ANFORDERUNGEN TESTS")
    print("="*60)
    
    # Sichere Original-Zustand
    original_key = os.environ.get("OPENAI_API_KEY")
    
    try:
        # Mock hvac
        with patch.dict('sys.modules', {'hvac': MagicMock()}):
            from app_secrets import SecretNotAvailableError
            from llm_gateway import LLMGateway
            
            # Anforderung 1: Fehlt ein Secret, wird vor dem ersten LLM-Call mit klarer Exception abgebrochen
            print("\n📋 Anforderung 1: Klare Exception bei fehlendem Secret")
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            
            try:
                LLMGateway()
                print("   ❌ FAIL: Keine Exception geworfen")
                req1_passed = False
            except SecretNotAvailableError as e:
                print(f"   ✅ PASS: SecretNotAvailableError geworfen: {str(e)[:100]}...")
                req1_passed = True
            except Exception as e:
                print(f"   ❌ FAIL: Falsche Exception: {type(e).__name__}: {e}")
                req1_passed = False
            
            # Anforderung 2: Gesetztes Dummy-Secret führt nicht zum Crash
            print("\n📋 Anforderung 2: Dummy-Secret verhindert Crash")
            os.environ["OPENAI_API_KEY"] = "sk-dummy-secret-for-testing"
            
            try:
                LLMGateway()
                print("   ✅ PASS: LLMGateway erfolgreich mit Dummy-Secret erstellt")
                req2_passed = True
            except Exception as e:
                print(f"   ❌ FAIL: Exception mit Dummy-Secret: {type(e).__name__}: {e}")
                req2_passed = False
            
            # Gesamtergebnis
            print(f"\n🏁 ANFORDERUNGEN ERFÜLLT: {req1_passed and req2_passed}")
            print(f"   Anforderung 1 (Exception bei fehlendem Secret): {'✅' if req1_passed else '❌'}")
            print(f"   Anforderung 2 (Dummy-Secret funktioniert): {'✅' if req2_passed else '❌'}")
            
            return req1_passed and req2_passed
    
    finally:
        # Stelle Original-Zustand wieder her
        if original_key is not None:
            os.environ["OPENAI_API_KEY"] = original_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]


if __name__ == "__main__":
    print("🚀 Starte Secret Flow Tests...")
    
    # Haupttests
    main_success = test_secret_flow()
    
    # Spezifische Anforderungen
    req_success = test_specific_requirements()
    
    # Gesamtergebnis
    overall_success = main_success and req_success
    
    print("\n" + "="*60)
    print("🏆 GESAMTERGEBNIS")
    print("="*60)
    print(f"Haupttests: {'✅ PASS' if main_success else '❌ FAIL'}")
    print(f"Anforderungen: {'✅ PASS' if req_success else '❌ FAIL'}")
    print(f"Gesamt: {'🎉 ALLE TESTS ERFOLGREICH!' if overall_success else '💥 TESTS FEHLGESCHLAGEN!'}")
    
    sys.exit(0 if overall_success else 1)
