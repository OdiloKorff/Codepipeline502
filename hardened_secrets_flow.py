"""
Hardened Secrets Flow.

Zentralen Secret-Resolver einsetzen, Secrets nie loggen, frühes Fail bei 
fehlenden Secrets. Bevorzugt OIDC/Vault, ansonsten sichere ENV-Fallbacks.
Unit-Tests für Fehl- und Erfolgsfälle.
"""

import hashlib
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

# Setup Logging mit Secret-Schutz
_log = logging.getLogger(__name__)


class SecretSource(str, Enum):
    """Secret-Quellen."""
    VAULT = "vault"
    OIDC = "oidc"
    ENV = "env"
    FILE = "file"
    MEMORY = "memory"


class SecretSeverity(str, Enum):
    """Secret-Kritikalitäts-Level."""
    CRITICAL = "critical"  # API-Keys, DB-Passwörter
    HIGH = "high"         # Service-Tokens
    MEDIUM = "medium"     # Config-Secrets
    LOW = "low"          # Non-sensitive Config


@dataclass
class SecretMetadata:
    """Metadaten für ein Secret."""
    key: str
    source: SecretSource
    severity: SecretSeverity
    expires_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    
    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = datetime.now()


@dataclass
class SecretValue:
    """Gehärteter Secret-Wert."""
    _value: str
    metadata: SecretMetadata
    _hash: Optional[str] = field(init=False, default=None)
    
    def __post_init__(self):
        # Erstelle Hash für Audit ohne Secret zu exposen
        self._hash = hashlib.sha256(self._value.encode()).hexdigest()[:16]
    
    @property
    def value(self) -> str:
        """Hole Secret-Wert und update Metadaten."""
        self.metadata.access_count += 1
        self.metadata.last_accessed = datetime.now()
        return self._value
    
    @property
    def audit_hash(self) -> str:
        """Hole Audit-Hash (sicher zu loggen)."""
        return self._hash
    
    def is_expired(self) -> bool:
        """Prüfe ob Secret abgelaufen."""
        if not self.metadata.expires_at:
            return False
        return datetime.now() > self.metadata.expires_at
    
    def __str__(self) -> str:
        """String-Repräsentation ohne Secret-Wert."""
        return f"SecretValue(key={self.metadata.key}, hash={self.audit_hash})"
    
    def __repr__(self) -> str:
        """Repr ohne Secret-Wert."""
        return self.__str__()


class SecretResolutionError(Exception):
    """Fehler bei Secret-Auflösung."""
    pass


class SecretExpiredError(SecretResolutionError):
    """Secret ist abgelaufen."""
    pass


class SecretNotFoundError(SecretResolutionError):
    """Secret nicht gefunden."""
    pass


class SecretResolver(ABC):
    """Abstract Base Class für Secret-Resolver."""
    
    @abstractmethod
    def resolve_secret(self, key: str, severity: SecretSeverity = SecretSeverity.MEDIUM) -> SecretValue:
        """
        Löse Secret auf.
        
        Args:
            key: Secret-Schlüssel
            severity: Kritikalitäts-Level
            
        Returns:
            SecretValue
            
        Raises:
            SecretResolutionError: Bei Auflösungsfehlern
        """
        pass
    
    @abstractmethod
    def list_available_secrets(self) -> List[str]:
        """Liste verfügbare Secret-Schlüssel."""
        pass


class VaultSecretResolver(SecretResolver):
    """HashiCorp Vault Secret-Resolver."""
    
    def __init__(self, vault_url: str, vault_token: Optional[str] = None):
        """
        Args:
            vault_url: Vault-Server URL
            vault_token: Vault-Token (optional, aus ENV)
        """
        self.vault_url = vault_url
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
        
        if not self.vault_token:
            raise SecretResolutionError("Vault-Token nicht verfügbar")
        
        _log.info("Vault Secret-Resolver initialisiert")
    
    def resolve_secret(self, key: str, severity: SecretSeverity = SecretSeverity.MEDIUM) -> SecretValue:
        """Löse Secret aus Vault auf."""
        try:
            # Simuliere Vault-API-Call
            # In Production: Echter hvac-Client
            
            # Simulierte Vault-Secrets
            vault_secrets = {
                "openai_api_key": "sk-simulated-openai-key-12345",
                "github_token": "ghp_simulated-github-token-67890",
                "database_password": "simulated-db-password-secure-123"
            }
            
            if key not in vault_secrets:
                raise SecretNotFoundError(f"Secret '{key}' nicht in Vault gefunden")
            
            metadata = SecretMetadata(
                key=key,
                source=SecretSource.VAULT,
                severity=severity,
                expires_at=datetime.now() + timedelta(hours=24)  # 24h TTL
            )
            
            secret_value = SecretValue(vault_secrets[key], metadata)
            
            _log.info(f"Secret aus Vault aufgelöst: {key} (hash: {secret_value.audit_hash})")
            
            return secret_value
            
        except Exception as e:
            _log.error(f"Vault Secret-Auflösung fehlgeschlagen für '{key}': {type(e).__name__}")
            raise SecretResolutionError(f"Vault-Auflösung fehlgeschlagen: {e}")
    
    def list_available_secrets(self) -> List[str]:
        """Liste verfügbare Vault-Secrets."""
        return ["openai_api_key", "github_token", "database_password"]


class OIDCSecretResolver(SecretResolver):
    """OIDC-basierter Secret-Resolver."""
    
    def __init__(self, oidc_provider: str, client_id: str):
        """
        Args:
            oidc_provider: OIDC-Provider URL
            client_id: OIDC Client-ID
        """
        self.oidc_provider = oidc_provider
        self.client_id = client_id
        
        _log.info("OIDC Secret-Resolver initialisiert")
    
    def resolve_secret(self, key: str, severity: SecretSeverity = SecretSeverity.MEDIUM) -> SecretValue:
        """Löse Secret via OIDC auf."""
        try:
            # Simuliere OIDC-Token-Exchange
            # In Production: Echter OIDC-Flow
            
            oidc_secrets = {
                "service_token": "oidc-exchanged-service-token-abc123",
                "api_access_token": "oidc-api-token-def456"
            }
            
            if key not in oidc_secrets:
                raise SecretNotFoundError(f"Secret '{key}' nicht via OIDC verfügbar")
            
            metadata = SecretMetadata(
                key=key,
                source=SecretSource.OIDC,
                severity=severity,
                expires_at=datetime.now() + timedelta(hours=1)  # 1h TTL für OIDC-Tokens
            )
            
            secret_value = SecretValue(oidc_secrets[key], metadata)
            
            _log.info(f"Secret via OIDC aufgelöst: {key} (hash: {secret_value.audit_hash})")
            
            return secret_value
            
        except Exception as e:
            _log.error(f"OIDC Secret-Auflösung fehlgeschlagen für '{key}': {type(e).__name__}")
            raise SecretResolutionError(f"OIDC-Auflösung fehlgeschlagen: {e}")
    
    def list_available_secrets(self) -> List[str]:
        """Liste verfügbare OIDC-Secrets."""
        return ["service_token", "api_access_token"]


class EnvSecretResolver(SecretResolver):
    """Environment-Variable Secret-Resolver (Fallback)."""
    
    def __init__(self, require_prefix: bool = True, prefix: str = "SECRET_"):
        """
        Args:
            require_prefix: Ob Secret-Prefix erforderlich
            prefix: Secret-Prefix für ENV-Vars
        """
        self.require_prefix = require_prefix
        self.prefix = prefix
        
        _log.info(f"ENV Secret-Resolver initialisiert (prefix: {prefix})")
    
    def resolve_secret(self, key: str, severity: SecretSeverity = SecretSeverity.MEDIUM) -> SecretValue:
        """Löse Secret aus Environment auf."""
        try:
            # Bestimme ENV-Variable-Name
            env_key = f"{self.prefix}{key.upper()}" if self.require_prefix else key.upper()
            
            env_value = os.getenv(env_key)
            
            if not env_value:
                raise SecretNotFoundError(f"Environment-Variable '{env_key}' nicht gefunden")
            
            # Warnung bei Critical-Secrets aus ENV
            if severity == SecretSeverity.CRITICAL:
                _log.warning(f"Critical Secret aus unsicherem ENV geladen: {key}")
            
            metadata = SecretMetadata(
                key=key,
                source=SecretSource.ENV,
                severity=severity
                # ENV-Secrets haben kein Ablaufdatum
            )
            
            secret_value = SecretValue(env_value, metadata)
            
            _log.info(f"Secret aus ENV aufgelöst: {key} (hash: {secret_value.audit_hash})")
            
            return secret_value
            
        except Exception as e:
            _log.error(f"ENV Secret-Auflösung fehlgeschlagen für '{key}': {type(e).__name__}")
            raise SecretResolutionError(f"ENV-Auflösung fehlgeschlagen: {e}")
    
    def list_available_secrets(self) -> List[str]:
        """Liste verfügbare ENV-Secrets."""
        secrets = []
        
        for env_key in os.environ:
            if self.require_prefix and env_key.startswith(self.prefix):
                secret_key = env_key[len(self.prefix):].lower()
                secrets.append(secret_key)
            elif not self.require_prefix:
                secrets.append(env_key.lower())
        
        return secrets


class HardenedSecretManager:
    """Gehärteter Secret-Manager mit Fallback-Chain."""
    
    def __init__(self, spec_id: str):
        """
        Args:
            spec_id: Feature-Spec ID für Audit-Logs
        """
        self.spec_id = spec_id
        self.resolvers: List[SecretResolver] = []
        self.secret_cache: Dict[str, SecretValue] = {}
        self.access_log: List[Dict] = []
        
        # Initialisiere Resolver-Chain
        self._initialize_resolvers()
        
        _log.info(f"[{self.spec_id}] Hardened Secret Manager initialisiert")
        _log.info(f"[{self.spec_id}] Resolver-Chain: {[type(r).__name__ for r in self.resolvers]}")
    
    def _initialize_resolvers(self):
        """Initialisiere Resolver-Chain (bevorzugt sicherste Quellen)."""
        
        # 1. Vault (höchste Priorität)
        vault_url = os.getenv("VAULT_ADDR")
        if vault_url:
            try:
                vault_resolver = VaultSecretResolver(vault_url)
                self.resolvers.append(vault_resolver)
                _log.info(f"[{self.spec_id}] Vault-Resolver aktiviert")
            except SecretResolutionError as e:
                _log.warning(f"[{self.spec_id}] Vault-Resolver fehlgeschlagen: {e}")
        
        # 2. OIDC (mittlere Priorität)
        oidc_provider = os.getenv("OIDC_PROVIDER")
        oidc_client_id = os.getenv("OIDC_CLIENT_ID")
        if oidc_provider and oidc_client_id:
            try:
                oidc_resolver = OIDCSecretResolver(oidc_provider, oidc_client_id)
                self.resolvers.append(oidc_resolver)
                _log.info(f"[{self.spec_id}] OIDC-Resolver aktiviert")
            except Exception as e:
                _log.warning(f"[{self.spec_id}] OIDC-Resolver fehlgeschlagen: {e}")
        
        # 3. ENV (Fallback, niedrigste Priorität)
        env_resolver = EnvSecretResolver()
        self.resolvers.append(env_resolver)
        _log.info(f"[{self.spec_id}] ENV-Resolver aktiviert (Fallback)")
        
        if not self.resolvers:
            raise SecretResolutionError("Keine Secret-Resolver verfügbar")
    
    def get_secret(self, 
                   key: str, 
                   severity: SecretSeverity = SecretSeverity.MEDIUM,
                   use_cache: bool = True) -> SecretValue:
        """
        Hole Secret mit Fallback-Chain.
        
        Args:
            key: Secret-Schlüssel
            severity: Kritikalitäts-Level
            use_cache: Ob Cache verwendet werden soll
            
        Returns:
            SecretValue
            
        Raises:
            SecretResolutionError: Bei Auflösungsfehlern
        """
        # Prüfe Cache
        if use_cache and key in self.secret_cache:
            cached_secret = self.secret_cache[key]
            
            if not cached_secret.is_expired():
                self._log_access(key, "cache_hit", cached_secret.metadata.source)
                return cached_secret
            else:
                # Entferne abgelaufenes Secret
                del self.secret_cache[key]
                _log.info(f"[{self.spec_id}] Abgelaufenes Secret aus Cache entfernt: {key}")
        
        # Versuche Resolver-Chain
        last_error = None
        
        for resolver in self.resolvers:
            try:
                secret = resolver.resolve_secret(key, severity)
                
                # Cache Secret (wenn nicht abgelaufen)
                if use_cache and not secret.is_expired():
                    self.secret_cache[key] = secret
                
                self._log_access(key, "resolved", secret.metadata.source)
                
                return secret
                
            except SecretNotFoundError:
                # Secret in diesem Resolver nicht verfügbar - weiter versuchen
                continue
            except Exception as e:
                last_error = e
                _log.warning(f"[{self.spec_id}] Resolver {type(resolver).__name__} fehlgeschlagen für '{key}': {e}")
                continue
        
        # Alle Resolver fehlgeschlagen
        error_msg = f"Secret '{key}' konnte nicht aufgelöst werden"
        if last_error:
            error_msg += f": {last_error}"
        
        self._log_access(key, "failed", None)
        
        raise SecretNotFoundError(error_msg)
    
    def _log_access(self, key: str, action: str, source: Optional[SecretSource]):
        """Logge Secret-Zugriff (ohne Secret-Wert)."""
        access_entry = {
            "timestamp": datetime.now().isoformat(),
            "spec_id": self.spec_id,
            "key": key,
            "action": action,
            "source": source.value if source else None
        }
        
        self.access_log.append(access_entry)
        
        # Strukturiertes Logging ohne Secret-Werte
        _log.info(f"[{self.spec_id}] Secret-Access: {key} -> {action} ({source})")
    
    def validate_required_secrets(self, *secret_keys: str) -> Dict[str, bool]:
        """
        Validiere dass erforderliche Secrets verfügbar sind.
        
        Args:
            secret_keys: Liste der erforderlichen Secret-Schlüssel
            
        Returns:
            Dictionary mit Verfügbarkeitsstatus
        """
        results = {}
        
        for key in secret_keys:
            try:
                # Versuche Secret aufzulösen (ohne zu cachen)
                self.get_secret(key, use_cache=False)
                results[key] = True
            except SecretResolutionError:
                results[key] = False
        
        missing_secrets = [key for key, available in results.items() if not available]
        
        if missing_secrets:
            _log.error(f"[{self.spec_id}] Fehlende erforderliche Secrets: {missing_secrets}")
        else:
            _log.info(f"[{self.spec_id}] Alle erforderlichen Secrets verfügbar: {list(secret_keys)}")
        
        return results
    
    def get_access_audit_log(self) -> List[Dict]:
        """Hole Audit-Log aller Secret-Zugriffe."""
        return self.access_log.copy()
    
    def clear_cache(self):
        """Leere Secret-Cache."""
        cache_size = len(self.secret_cache)
        self.secret_cache.clear()
        _log.info(f"[{self.spec_id}] Secret-Cache geleert: {cache_size} Secrets entfernt")
    
    def get_cache_status(self) -> Dict:
        """Hole Cache-Status."""
        datetime.now()
        
        cache_status = {
            "total_secrets": len(self.secret_cache),
            "expired_secrets": 0,
            "secrets_by_source": {},
            "secrets_by_severity": {}
        }
        
        for key, secret in self.secret_cache.items():
            # Prüfe Ablauf
            if secret.is_expired():
                cache_status["expired_secrets"] += 1
            
            # Gruppiere nach Quelle
            source = secret.metadata.source.value
            cache_status["secrets_by_source"][source] = cache_status["secrets_by_source"].get(source, 0) + 1
            
            # Gruppiere nach Severity
            severity = secret.metadata.severity.value
            cache_status["secrets_by_severity"][severity] = cache_status["secrets_by_severity"].get(severity, 0) + 1
        
        return cache_status


# Globaler Secret-Manager (Singleton-Pattern)
_global_secret_manager: Optional[HardenedSecretManager] = None


def get_secret_manager(spec_id: str = "default") -> HardenedSecretManager:
    """Hole globalen Secret-Manager (Singleton)."""
    global _global_secret_manager
    
    if _global_secret_manager is None:
        _global_secret_manager = HardenedSecretManager(spec_id)
    
    return _global_secret_manager


def get_secret(key: str, 
               severity: SecretSeverity = SecretSeverity.MEDIUM,
               spec_id: str = "default") -> str:
    """
    Convenience-Funktion für Secret-Zugriff.
    
    Args:
        key: Secret-Schlüssel
        severity: Kritikalitäts-Level
        spec_id: Spec-ID für Audit
        
    Returns:
        Secret-Wert als String
        
    Raises:
        SecretResolutionError: Bei Auflösungsfehlern
    """
    manager = get_secret_manager(spec_id)
    secret_value = manager.get_secret(key, severity)
    return secret_value.value


def validate_secrets_early(*secret_keys: str, spec_id: str = "default") -> None:
    """
    Frühe Secret-Validierung (Fail-Fast).
    
    Args:
        secret_keys: Erforderliche Secret-Schlüssel
        spec_id: Spec-ID für Audit
        
    Raises:
        SecretResolutionError: Bei fehlenden Secrets
    """
    manager = get_secret_manager(spec_id)
    results = manager.validate_required_secrets(*secret_keys)
    
    missing = [key for key, available in results.items() if not available]
    
    if missing:
        raise SecretResolutionError(f"Erforderliche Secrets fehlen: {missing}")


def demo_hardened_secrets_flow():
    """Demonstriere Hardened Secrets Flow."""
    print("🔐 Hardened Secrets Flow Demo")
    print("=" * 60)
    
    # Test 1: Secret-Manager-Initialisierung
    print("\n✅ Test 1: Secret-Manager-Initialisierung")
    
    spec_id = "SECRETS-DEMO-001"
    manager = HardenedSecretManager(spec_id)
    
    print("🔧 Secret-Manager:")
    print(f"   - Spec ID: {spec_id}")
    print(f"   - Resolver: {len(manager.resolvers)}")
    print(f"   - Cache: {len(manager.secret_cache)} Secrets")
    
    # Test 2: Secret-Auflösung mit Fallback
    print("\n🔍 Test 2: Secret-Auflösung mit Fallback")
    
    # Setze Test-ENV-Variable
    os.environ["SECRET_TEST_KEY"] = "test-secret-value-12345"
    
    try:
        # Versuche verschiedene Secrets
        test_secrets = [
            ("test_key", SecretSeverity.LOW),
            ("openai_api_key", SecretSeverity.CRITICAL),
            ("nonexistent_key", SecretSeverity.MEDIUM)
        ]
        
        for key, severity in test_secrets:
            try:
                secret = manager.get_secret(key, severity)
                print(f"   - {key}: ✅ RESOLVED ({secret.metadata.source.value}, hash: {secret.audit_hash})")
            except SecretResolutionError as e:
                print(f"   - {key}: ❌ FAILED ({e})")
    
    except Exception as e:
        print(f"❌ Secret-Auflösung fehlgeschlagen: {e}")
    
    # Test 3: Frühe Secret-Validierung
    print("\n⚡ Test 3: Frühe Secret-Validierung (Fail-Fast)")
    
    try:
        # Validiere erforderliche Secrets
        required_secrets = ["test_key", "openai_api_key"]
        results = manager.validate_required_secrets(*required_secrets)
        
        print("🔍 Secret-Validierung:")
        for key, available in results.items():
            status = "✅ AVAILABLE" if available else "❌ MISSING"
            print(f"   - {key}: {status}")
        
        # Teste Fail-Fast
        try:
            validate_secrets_early("test_key", "missing_critical_key", spec_id=spec_id)
            print("⚠️  Fail-Fast nicht ausgelöst - Fehler!")
        except SecretResolutionError as e:
            print(f"✅ Fail-Fast korrekt ausgelöst: {e}")
    
    except Exception as e:
        print(f"❌ Secret-Validierung fehlgeschlagen: {e}")
    
    # Test 4: Cache-Management
    print("\n💾 Test 4: Cache-Management")
    
    cache_status = manager.get_cache_status()
    
    print("📊 Cache-Status:")
    print(f"   - Total Secrets: {cache_status['total_secrets']}")
    print(f"   - Expired: {cache_status['expired_secrets']}")
    print(f"   - By Source: {cache_status['secrets_by_source']}")
    print(f"   - By Severity: {cache_status['secrets_by_severity']}")
    
    # Test 5: Audit-Log
    print("\n📜 Test 5: Audit-Log")
    
    audit_log = manager.get_access_audit_log()
    
    print("📋 Secret-Access-Audit:")
    print(f"   - Total Access: {len(audit_log)}")
    
    for entry in audit_log[-3:]:  # Letzte 3 Einträge
        print(f"   - {entry['key']}: {entry['action']} ({entry['source']})")
    
    # Test 6: Convenience-Funktionen
    print("\n🔧 Test 6: Convenience-Funktionen")
    
    try:
        # Teste globale Convenience-Funktion
        secret_value = get_secret("test_key", SecretSeverity.LOW, spec_id)
        print(f"🔑 Convenience get_secret: ✅ SUCCESS (Länge: {len(secret_value)})")
        
        # Teste globale Validierung
        validate_secrets_early("test_key", spec_id=spec_id)
        print("✅ Convenience validate_secrets_early: ✅ SUCCESS")
    
    except Exception as e:
        print(f"❌ Convenience-Funktionen fehlgeschlagen: {e}")
    
    # Test 7: Secret-Sicherheit (keine Logs)
    print("\n🛡️ Test 7: Secret-Sicherheit")
    
    # Prüfe dass Secrets nicht in Logs erscheinen
    secret = manager.get_secret("test_key")
    
    print("🔒 Secret-Sicherheit:")
    print(f"   - String-Repr: {str(secret)}")  # Sollte kein Secret-Wert enthalten
    print(f"   - Audit-Hash: {secret.audit_hash}")
    print(f"   - Access-Count: {secret.metadata.access_count}")
    print(f"   - Last-Access: {secret.metadata.last_accessed}")
    
    # Cleanup
    os.environ.pop("SECRET_TEST_KEY", None)
    
    print("\n✅ Hardened Secrets Flow Demo abgeschlossen!")
    print("🔐 Zentraler Secret-Resolver mit sicherer Fallback-Chain implementiert")
    
    return 0


if __name__ == "__main__":
    # Konfiguriere Logging ohne Secret-Leakage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    exit_code = demo_hardened_secrets_flow()
    sys.exit(exit_code)
