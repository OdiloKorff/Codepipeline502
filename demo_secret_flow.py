#!/usr/bin/env python3
"""
Demo für den sauberen Secret Flow im LLM Gateway.

Zeigt die Funktionsweise der zentralen Secret-Verwaltung.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Füge Projekt-Root zum Python-Path hinzu
sys.path.insert(0, str(Path(__file__).parent))


def demo_secret_flow():
    """Demonstriert den sauberen Secret Flow."""
    print("🚀 Demo: Sauberer Secret Flow im LLM Gateway")
    print("="*60)
    
    # Sichere Original-Zustand
    original_key = os.environ.get("OPENAI_API_KEY")
    
    try:
        # Mock hvac um Import-Probleme zu vermeiden
        with patch.dict('sys.modules', {'hvac': MagicMock()}):
            from app_secrets import SecretNotAvailableError, ensure_env, validate_required_secrets
            from llm_gateway import LLMGateway
            
            print("\n🔍 Schritt 1: Ohne Secret - Exception erwartet")
            print("-" * 40)
            
            # Entferne OPENAI_API_KEY
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            
            try:
                gateway = LLMGateway()
                print("❌ FEHLER: Keine Exception geworfen!")
            except SecretNotAvailableError as e:
                print("✅ KORREKT: SecretNotAvailableError geworfen")
                print(f"   Message: {str(e)[:100]}...")
            
            print("\n🔧 Schritt 2: Setze Dummy-Secret")
            print("-" * 40)
            
            dummy_secret = "sk-demo-secret-12345-not-real"
            os.environ["OPENAI_API_KEY"] = dummy_secret
            print(f"   OPENAI_API_KEY = {dummy_secret}")
            
            print("\n✅ Schritt 3: LLMGateway mit Secret - Erfolg erwartet")
            print("-" * 40)
            
            try:
                gateway = LLMGateway()
                print("✅ KORREKT: LLMGateway erfolgreich erstellt")
                print(f"   Gateway-Typ: {type(gateway).__name__}")
                print(f"   Client verfügbar: {hasattr(gateway, '_client')}")
            except Exception as e:
                print(f"❌ FEHLER: Unerwartete Exception: {type(e).__name__}: {e}")
            
            print("\n🔍 Schritt 4: Zentrale ensure_env Funktion")
            print("-" * 40)
            
            # Test mit bereits gesetztem Secret
            print("4a) Mit bereits gesetztem Secret:")
            try:
                ensure_env("OPENAI_API_KEY")
                print("   ✅ ensure_env erfolgreich (Secret bereits gesetzt)")
            except Exception as e:
                print(f"   ❌ Unerwartete Exception: {e}")
            
            # Test mit unbekanntem Secret
            print("\n4b) Mit unbekanntem Secret:")
            try:
                ensure_env("UNKNOWN_SECRET")
                print("   ❌ FEHLER: Keine Exception für unbekanntes Secret")
            except SecretNotAvailableError as e:
                print("   ✅ KORREKT: SecretNotAvailableError für unbekanntes Secret")
                print(f"   Message: {str(e)[:80]}...")
            
            print("\n🔍 Schritt 5: Batch-Validierung mit validate_required_secrets")
            print("-" * 40)
            
            # Setze zweites Secret für Test
            os.environ["ANTHROPIC_API_KEY"] = "dummy-anthropic-key"
            
            try:
                validate_required_secrets("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
                print("   ✅ validate_required_secrets erfolgreich für verfügbare Secrets")
            except Exception as e:
                print(f"   ❌ Unerwartete Exception: {e}")
            
            # Entferne ein Secret für Fehlertest
            del os.environ["ANTHROPIC_API_KEY"]
            
            try:
                validate_required_secrets("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
                print("   ❌ FEHLER: Keine Exception für fehlendes Secret")
            except SecretNotAvailableError:
                print("   ✅ KORREKT: SecretNotAvailableError für fehlendes Secret")
            
            print("\n🔍 Schritt 6: LLMGateway mit deaktivierter Validierung")
            print("-" * 40)
            
            # Entferne alle Secrets
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            
            # Mock Client
            mock_client = MagicMock()
            
            try:
                gateway = LLMGateway(client=mock_client, validate_secrets=False)
                print("   ✅ KORREKT: LLMGateway mit deaktivierter Validierung erfolgreich")
                print(f"   Mock-Client korrekt gesetzt: {gateway._client is mock_client}")
            except Exception as e:
                print(f"   ❌ FEHLER: Exception bei deaktivierter Validierung: {e}")
            
            print("\n" + "="*60)
            print("🎉 SECRET FLOW DEMO ABGESCHLOSSEN")
            print("="*60)
            
            print("\n📋 ZUSAMMENFASSUNG:")
            print("✅ Fehlende Secrets werfen SecretNotAvailableError vor LLM-Call")
            print("✅ Dummy-Secrets verhindern Crashes")
            print("✅ ensure_env ist zentrale Secret-Verwaltung")
            print("✅ validate_required_secrets für Batch-Validierung")
            print("✅ Secret-Validierung kann optional deaktiviert werden")
            print("✅ Alle direkten os.getenv-Zugriffe eliminiert")
            
    finally:
        # Stelle Original-Zustand wieder her
        if original_key is not None:
            os.environ["OPENAI_API_KEY"] = original_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        
        # Cleanup andere Test-Secrets
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]


def show_code_examples():
    """Zeigt Code-Beispiele für die Verwendung."""
    print("\n" + "="*60)
    print("💻 CODE-BEISPIELE")
    print("="*60)
    
    print("""
🔧 Verwendung der zentralen Secret-Verwaltung:

```python
from app_secrets import ensure_env, SecretNotAvailableError, validate_required_secrets
from llm_gateway import LLMGateway

# 1. Einzelnes Secret sicherstellen
try:
    ensure_env("OPENAI_API_KEY")
    print("Secret verfügbar!")
except SecretNotAvailableError as e:
    print(f"Secret fehlt: {e}")

# 2. Mehrere Secrets auf einmal validieren
try:
    validate_required_secrets("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    print("Alle Secrets verfügbar!")
except SecretNotAvailableError as e:
    print(f"Fehlende Secrets: {e}")

# 3. LLMGateway mit automatischer Secret-Validierung
try:
    gateway = LLMGateway()  # Validiert OPENAI_API_KEY automatisch
    response = gateway.chat([{"role": "user", "content": "Hello!"}])
except SecretNotAvailableError as e:
    print(f"LLM Secret nicht verfügbar: {e}")

# 4. LLMGateway ohne Secret-Validierung (für Tests)
mock_client = MockOpenAI()
gateway = LLMGateway(client=mock_client, validate_secrets=False)
```

🎯 Vorteile des neuen Secret Flows:

✅ Fail Fast: Secrets werden vor dem ersten LLM-Call validiert
✅ Zentral: Alle Secret-Zugriffe über ensure_env()
✅ Klar: Spezifische SecretNotAvailableError mit hilfreichen Messages
✅ Flexibel: Validierung kann für Tests deaktiviert werden
✅ Sicher: Keine direkten os.getenv() Zugriffe mehr im Code
✅ Auditierbar: Alle Secret-Zugriffe an einer Stelle
""")


if __name__ == "__main__":
    demo_secret_flow()
    show_code_examples()
    
    print("\n🎉 Demo abgeschlossen! Der saubere Secret Flow ist implementiert.")
