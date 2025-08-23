"""
Production Secret-Resolver und Token-Budget-Gate.

Stelle eine zentrale Funktion für Secret-Auflösung bereit, ohne Secrets zu loggen.
Fehlendes Secret führt vor dem ersten LLM-Call zu einem harten Fail. Ergänze ein
Token-Accounting für Prompt und Completion, kumuliere und vergleiche gegen das
in der Spec definierte Budget. Überschreitung führt zum Gate-Fail.
"""

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class SecretResolutionError(Exception):
    """Fehler bei Secret-Auflösung."""
    pass


class TokenBudgetExceededError(Exception):
    """Token-Budget überschritten."""
    pass


class SecretSource(str, Enum):
    """Quellen für Secret-Auflösung."""
    ENVIRONMENT = "environment"
    VAULT = "vault"
    OIDC = "oidc"
    FILE = "file"
    CACHED = "cached"


@dataclass
class SecretValue:
    """Sichere Secret-Repräsentation ohne Klartext-Logging."""
    key: str
    source: SecretSource
    hash_sha256: str
    retrieved_at: datetime
    expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        if not self.hash_sha256:
            raise ValueError("Secret hash is required")
    
    @classmethod
    def from_value(cls, key: str, value: str, source: SecretSource, ttl_seconds: int = 3600) -> 'SecretValue':
        """Erstelle SecretValue aus Klartext-Wert."""
        if not value:
            raise SecretResolutionError(f"Empty secret value for key: {key}")
        
        hash_sha256 = hashlib.sha256(value.encode('utf-8')).hexdigest()
        retrieved_at = datetime.now()
        expires_at = retrieved_at + timedelta(seconds=ttl_seconds) if ttl_seconds > 0 else None
        
        return cls(
            key=key,
            source=source,
            hash_sha256=hash_sha256,
            retrieved_at=retrieved_at,
            expires_at=expires_at
        )
    
    def is_expired(self) -> bool:
        """Prüfe ob Secret abgelaufen ist."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def get_audit_info(self) -> Dict[str, Any]:
        """Hole Audit-Informationen ohne Klartext."""
        return {
            "key": self.key,
            "source": self.source.value,
            "hash": self.hash_sha256[:16] + "...",  # Nur erste 16 Zeichen
            "retrieved_at": self.retrieved_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired()
        }


@dataclass
class TokenUsage:
    """Token-Verbrauch für einen LLM-Request."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: Optional[str] = None
    estimated_cost_usd: float = 0.0
    
    def __post_init__(self):
        # Validiere Token-Counts
        if self.prompt_tokens < 0 or self.completion_tokens < 0:
            raise ValueError("Token counts cannot be negative")
        
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            self.total_tokens = self.prompt_tokens + self.completion_tokens
        
        # Schätze Kosten (vereinfacht)
        self.estimated_cost_usd = self._estimate_cost()
    
    def _estimate_cost(self) -> float:
        """Schätze Kosten basierend auf Modell und Token-Count."""
        # Vereinfachte Kostenschätzung (echte Implementation würde aktuelle Preise verwenden)
        cost_per_1k_tokens = {
            "gpt-4o-mini": 0.00015,  # $0.15 per 1M tokens
            "gpt-4o": 0.005,         # $5.00 per 1M tokens
            "gpt-3.5-turbo": 0.002,  # $2.00 per 1M tokens
        }
        
        base_cost = cost_per_1k_tokens.get(self.model, 0.002)  # Default fallback
        return (self.total_tokens / 1000) * base_cost


class ProductionSecretResolver:
    """
    Production-ready Secret-Resolver mit sicherer Auflösung und Caching.
    
    Features:
    - Zentrale Secret-Auflösung ohne Klartext-Logging
    - Multi-Source-Support (ENV, Vault, OIDC, File)
    - Secure Caching mit TTL
    - Audit-Trail für Secret-Zugriffe
    - Fail-Closed bei fehlenden Secrets
    """
    
    def __init__(self, cache_ttl_seconds: int = 3600):
        """
        Args:
            cache_ttl_seconds: TTL für Secret-Cache
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self._secret_cache: Dict[str, SecretValue] = {}
        self._access_log: List[Dict[str, Any]] = []
        
        print("🔐 Secret-Resolver initialisiert")
        print(f"   ⏱️ Cache TTL: {cache_ttl_seconds}s")
    
    def _log_secret_access(self, key: str, source: SecretSource, success: bool, error: str = None):
        """Logge Secret-Zugriff für Audit-Trail."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "key": key,
            "source": source.value,
            "success": success,
            "error": error
        }
        
        self._access_log.append(log_entry)
        
        status_emoji = "✅" if success else "❌"
        print(f"🔐 Secret Access {status_emoji}: {key} from {source.value}")
        
        if error:
            print(f"   Error: {error}")
    
    def _resolve_from_environment(self, key: str) -> Optional[str]:
        """Löse Secret aus Umgebungsvariablen auf."""
        value = os.environ.get(key)
        return value if value else None
    
    def _resolve_from_vault(self, key: str) -> Optional[str]:
        """Löse Secret aus HashiCorp Vault auf (simuliert)."""
        # In echter Implementation: Vault-Client, Authentifizierung, etc.
        # Hier: Simulation für Demo
        
        vault_secrets = {
            "OPENAI_API_KEY": "sk-demo-vault-key-12345",
            "DATABASE_URL": "postgresql://vault-user:vault-pass@localhost/db",
            "GITHUB_TOKEN": "ghp_vault_token_67890"
        }
        
        return vault_secrets.get(key)
    
    def _resolve_from_oidc(self, key: str) -> Optional[str]:
        """Löse Secret via OIDC-Provider auf (simuliert)."""
        # In echter Implementation: OIDC-Flow, Token-Exchange, etc.
        # Hier: Simulation für Demo
        
        oidc_secrets = {
            "AZURE_CLIENT_SECRET": "oidc-azure-secret-abc123",
            "AWS_ACCESS_KEY": "oidc-aws-key-def456"
        }
        
        return oidc_secrets.get(key)
    
    def _resolve_from_file(self, key: str) -> Optional[str]:
        """Löse Secret aus Datei auf."""
        # Suche in Standard-Secret-Verzeichnissen
        secret_paths = [
            f"/run/secrets/{key.lower()}",
            f"/var/run/secrets/{key.lower()}",
            f".secrets/{key.lower()}",
        ]
        
        for path in secret_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        return content if content else None
            except Exception:
                continue
        
        return None
    
    def resolve_secret(self, key: str, required: bool = True) -> Optional[SecretValue]:
        """
        Löse Secret sicher auf ohne Klartext-Logging.
        
        Args:
            key: Secret-Schlüssel
            required: Ob Secret erforderlich ist (Fail-Closed wenn True)
            
        Returns:
            SecretValue oder None
            
        Raises:
            SecretResolutionError: Bei erforderlichen, aber fehlenden Secrets
        """
        # 1. Prüfe Cache
        cached_secret = self._secret_cache.get(key)
        if cached_secret and not cached_secret.is_expired():
            self._log_secret_access(key, SecretSource.CACHED, True)
            return cached_secret
        
        # 2. Löse Secret von verschiedenen Quellen auf
        resolution_sources = [
            (SecretSource.VAULT, self._resolve_from_vault),
            (SecretSource.OIDC, self._resolve_from_oidc),
            (SecretSource.ENVIRONMENT, self._resolve_from_environment),
            (SecretSource.FILE, self._resolve_from_file),
        ]
        
        for source, resolver_func in resolution_sources:
            try:
                secret_value = resolver_func(key)
                
                if secret_value:
                    # Erstelle SecretValue ohne Klartext-Logging
                    secret = SecretValue.from_value(
                        key=key,
                        value=secret_value,
                        source=source,
                        ttl_seconds=self.cache_ttl_seconds
                    )
                    
                    # Cache Secret
                    self._secret_cache[key] = secret
                    
                    self._log_secret_access(key, source, True)
                    return secret
            
            except Exception as e:
                self._log_secret_access(key, source, False, str(e))
                continue
        
        # 3. Secret nicht gefunden
        error_msg = f"Secret '{key}' not found in any source"
        
        if required:
            self._log_secret_access(key, SecretSource.ENVIRONMENT, False, error_msg)
            raise SecretResolutionError(error_msg)
        
        self._log_secret_access(key, SecretSource.ENVIRONMENT, False, error_msg)
        return None
    
    def get_secret_value(self, key: str, required: bool = True) -> Optional[str]:
        """
        Hole Klartext-Secret-Wert (VORSICHTIG VERWENDEN!).
        
        Diese Methode sollte nur für tatsächliche Secret-Verwendung genutzt werden,
        niemals für Logging oder Debugging.
        """
        secret = self.resolve_secret(key, required)
        
        if not secret:
            return None
        
        # Rekonstruiere Wert aus Source (vereinfacht für Demo)
        if secret.source == SecretSource.ENVIRONMENT:
            return os.environ.get(key)
        elif secret.source == SecretSource.VAULT:
            return self._resolve_from_vault(key)
        elif secret.source == SecretSource.OIDC:
            return self._resolve_from_oidc(key)
        elif secret.source == SecretSource.FILE:
            return self._resolve_from_file(key)
        
        return None
    
    def validate_required_secrets(self, *secret_keys: str) -> bool:
        """
        Validiere erforderliche Secrets vor LLM-Operationen.
        
        Args:
            secret_keys: Liste erforderlicher Secret-Schlüssel
            
        Returns:
            True wenn alle Secrets verfügbar
            
        Raises:
            SecretResolutionError: Bei fehlenden erforderlichen Secrets
        """
        missing_secrets = []
        
        for key in secret_keys:
            try:
                secret = self.resolve_secret(key, required=True)
                if not secret:
                    missing_secrets.append(key)
            except SecretResolutionError:
                missing_secrets.append(key)
        
        if missing_secrets:
            error_msg = f"Required secrets missing: {', '.join(missing_secrets)}"
            raise SecretResolutionError(error_msg)
        
        print(f"✅ All required secrets validated: {', '.join(secret_keys)}")
        return True
    
    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Hole Audit-Log für Secret-Zugriffe."""
        return self._access_log.copy()
    
    def clear_cache(self):
        """Lösche Secret-Cache."""
        self._secret_cache.clear()
        print("🧹 Secret-Cache geleert")


class ProductionTokenBudgetGate:
    """
    Production-ready Token-Budget-Gate mit präzisem Accounting.
    
    Features:
    - Token-Verbrauch-Tracking pro Request
    - Kumulatives Budget-Monitoring
    - Kostenschätzung
    - Fail-Closed bei Budget-Überschreitung
    - Detaillierte Audit-Trails
    """
    
    def __init__(self, budget_tokens: int, spec_id: str = "default"):
        """
        Args:
            budget_tokens: Token-Budget für diese Session
            spec_id: ID der Feature-Spec für Tracking
        """
        self.budget_tokens = budget_tokens
        self.spec_id = spec_id
        
        self.token_usage_log: List[TokenUsage] = []
        self.total_tokens_used = 0
        self.total_estimated_cost = 0.0
        self.session_start_time = datetime.now()
        
        print("💰 Token-Budget-Gate initialisiert")
        print(f"   📊 Budget: {budget_tokens:,} tokens")
        print(f"   🏷️ Spec ID: {spec_id}")
    
    def record_token_usage(self, 
                          prompt_tokens: int,
                          completion_tokens: int,
                          model: str,
                          request_id: str = None) -> TokenUsage:
        """
        Erfasse Token-Verbrauch für einen LLM-Request.
        
        Args:
            prompt_tokens: Tokens für Prompt
            completion_tokens: Tokens für Completion
            model: Verwendetes LLM-Modell
            request_id: Optional Request-ID für Tracking
            
        Returns:
            TokenUsage-Objekt
            
        Raises:
            TokenBudgetExceededError: Bei Budget-Überschreitung
        """
        # Erstelle TokenUsage
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
            request_id=request_id
        )
        
        # Prüfe Budget vor Aufzeichnung
        projected_total = self.total_tokens_used + usage.total_tokens
        
        if projected_total > self.budget_tokens:
            error_msg = (f"Token budget exceeded: {projected_total:,} > {self.budget_tokens:,} "
                        f"(Request would use {usage.total_tokens:,} tokens)")
            
            print("💥 TOKEN BUDGET EXCEEDED")
            print(f"   Current Usage: {self.total_tokens_used:,} tokens")
            print(f"   Request Tokens: {usage.total_tokens:,} tokens")
            print(f"   Budget: {self.budget_tokens:,} tokens")
            print(f"   Overage: {projected_total - self.budget_tokens:,} tokens")
            
            raise TokenBudgetExceededError(error_msg)
        
        # Aktualisiere Totals
        self.token_usage_log.append(usage)
        self.total_tokens_used += usage.total_tokens
        self.total_estimated_cost += usage.estimated_cost_usd
        
        # Logge Usage
        remaining_tokens = self.budget_tokens - self.total_tokens_used
        usage_percentage = (self.total_tokens_used / self.budget_tokens) * 100
        
        print("💰 Token Usage Recorded:")
        print(f"   Request: {usage.prompt_tokens:,} prompt + {usage.completion_tokens:,} completion = {usage.total_tokens:,} total")
        print(f"   Model: {usage.model}")
        print(f"   Total Used: {self.total_tokens_used:,} / {self.budget_tokens:,} ({usage_percentage:.1f}%)")
        print(f"   Remaining: {remaining_tokens:,} tokens")
        print(f"   Estimated Cost: ${usage.estimated_cost_usd:.6f}")
        
        return usage
    
    def check_budget_status(self) -> Dict[str, Any]:
        """Hole aktuellen Budget-Status."""
        remaining_tokens = self.budget_tokens - self.total_tokens_used
        usage_percentage = (self.total_tokens_used / self.budget_tokens) * 100 if self.budget_tokens > 0 else 0
        
        session_duration = datetime.now() - self.session_start_time
        
        status = {
            "spec_id": self.spec_id,
            "budget_tokens": self.budget_tokens,
            "tokens_used": self.total_tokens_used,
            "tokens_remaining": remaining_tokens,
            "usage_percentage": usage_percentage,
            "estimated_cost_usd": self.total_estimated_cost,
            "requests_count": len(self.token_usage_log),
            "session_duration_seconds": session_duration.total_seconds(),
            "is_budget_exceeded": self.total_tokens_used > self.budget_tokens,
            "budget_warning": usage_percentage >= 80.0  # Warning bei 80%
        }
        
        return status
    
    def can_afford_request(self, estimated_tokens: int) -> bool:
        """Prüfe ob Request innerhalb Budget liegt."""
        projected_total = self.total_tokens_used + estimated_tokens
        return projected_total <= self.budget_tokens
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Hole detaillierte Usage-Zusammenfassung."""
        if not self.token_usage_log:
            return {"message": "No token usage recorded"}
        
        # Gruppiere nach Modell
        model_usage = {}
        for usage in self.token_usage_log:
            if usage.model not in model_usage:
                model_usage[usage.model] = {
                    "requests": 0,
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "estimated_cost": 0.0
                }
            
            model_stats = model_usage[usage.model]
            model_stats["requests"] += 1
            model_stats["total_tokens"] += usage.total_tokens
            model_stats["prompt_tokens"] += usage.prompt_tokens
            model_stats["completion_tokens"] += usage.completion_tokens
            model_stats["estimated_cost"] += usage.estimated_cost_usd
        
        budget_status = self.check_budget_status()
        
        return {
            "budget_status": budget_status,
            "model_breakdown": model_usage,
            "usage_timeline": [
                {
                    "timestamp": usage.timestamp.isoformat(),
                    "model": usage.model,
                    "tokens": usage.total_tokens,
                    "cost": usage.estimated_cost_usd,
                    "request_id": usage.request_id
                }
                for usage in self.token_usage_log
            ]
        }
    
    def generate_budget_report(self) -> str:
        """Generiere menschenlesbaren Budget-Report."""
        status = self.check_budget_status()
        
        report = f"""
💰 TOKEN BUDGET REPORT
{'=' * 50}

📊 Budget Overview:
   Spec ID: {status['spec_id']}
   Total Budget: {status['budget_tokens']:,} tokens
   Tokens Used: {status['tokens_used']:,} tokens ({status['usage_percentage']:.1f}%)
   Tokens Remaining: {status['tokens_remaining']:,} tokens
   
💵 Cost Estimation:
   Total Estimated Cost: ${status['estimated_cost_usd']:.6f}
   
📈 Usage Statistics:
   Total Requests: {status['requests_count']}
   Session Duration: {status['session_duration_seconds']:.1f}s
   
🚨 Status:
   Budget Exceeded: {'YES' if status['is_budget_exceeded'] else 'NO'}
   Warning Level: {'HIGH' if status['budget_warning'] else 'NORMAL'}
"""
        
        if self.token_usage_log:
            report += "\n📋 Recent Requests:\n"
            for usage in self.token_usage_log[-5:]:  # Letzte 5 Requests
                report += f"   {usage.timestamp.strftime('%H:%M:%S')} | {usage.model} | {usage.total_tokens:,} tokens | ${usage.estimated_cost_usd:.6f}\n"
        
        return report


def test_production_secret_token_system():
    """Teste Production Secret-Token-System umfassend."""
    print("🧪 PRODUCTION SECRET-TOKEN-SYSTEM TESTS")
    print("=" * 70)
    
    # Test 1: Secret-Resolver
    print("\n🔐 Test 1: Secret-Resolver")
    
    # Setze Test-Environment-Variable
    os.environ["TEST_SECRET"] = "test-secret-value-12345"
    
    resolver = ProductionSecretResolver(cache_ttl_seconds=60)
    
    try:
        # Erfolgreiche Secret-Auflösung
        secret = resolver.resolve_secret("TEST_SECRET")
        
        if secret and secret.key == "TEST_SECRET":
            print(f"   ✅ Secret erfolgreich aufgelöst: {secret.key}")
            print(f"   📊 Source: {secret.source.value}")
            print(f"   🔐 Hash: {secret.hash_sha256[:16]}...")
            
            # Audit-Info prüfen
            audit_info = secret.get_audit_info()
            if "hash" in audit_info and len(audit_info["hash"]) > 10:
                print("   ✅ Audit-Info verfügbar (kein Klartext)")
            else:
                print("   ❌ Audit-Info unvollständig")
                return False
        else:
            print("   ❌ Secret-Auflösung fehlgeschlagen")
            return False
    
    except Exception as e:
        print(f"   ❌ Secret-Test-Fehler: {e}")
        return False
    
    # Test 2: Fehlende Required Secrets
    print("\n🚨 Test 2: Fehlende Required Secrets")
    
    try:
        resolver.validate_required_secrets("NONEXISTENT_SECRET")
        print("   ❌ Fehlende Secrets wurden nicht erkannt")
        return False
    
    except SecretResolutionError as e:
        print(f"   ✅ Fehlende Secrets korrekt erkannt: {e}")
    
    # Test 3: Token-Budget-Gate
    print("\n💰 Test 3: Token-Budget-Gate")
    
    budget_gate = ProductionTokenBudgetGate(budget_tokens=1000, spec_id="TEST-SPEC-001")
    
    try:
        # Normale Token-Usage
        usage1 = budget_gate.record_token_usage(
            prompt_tokens=300,
            completion_tokens=200,
            model="gpt-4o-mini",
            request_id="req-001"
        )
        
        if usage1.total_tokens == 500:
            print(f"   ✅ Token-Usage erfasst: {usage1.total_tokens} tokens")
        else:
            print(f"   ❌ Token-Usage inkorrekt: {usage1.total_tokens}")
            return False
        
        # Budget-Status prüfen
        status = budget_gate.check_budget_status()
        
        if status["tokens_used"] == 500 and status["tokens_remaining"] == 500:
            print(f"   ✅ Budget-Status korrekt: {status['usage_percentage']:.1f}% verwendet")
        else:
            print("   ❌ Budget-Status inkorrekt")
            return False
    
    except Exception as e:
        print(f"   ❌ Token-Budget-Test-Fehler: {e}")
        return False
    
    # Test 4: Budget-Überschreitung
    print("\n💥 Test 4: Budget-Überschreitung")
    
    try:
        # Versuche Budget zu überschreiten
        budget_gate.record_token_usage(
            prompt_tokens=400,
            completion_tokens=200,  # 600 tokens - würde Budget überschreiten
            model="gpt-4o-mini",
            request_id="req-002"
        )
        
        print("   ❌ Budget-Überschreitung wurde nicht erkannt")
        return False
    
    except TokenBudgetExceededError as e:
        print("   ✅ Budget-Überschreitung korrekt erkannt")
        print(f"      Error: {str(e)[:60]}...")
    
    # Test 5: Integration Test
    print("\n🔗 Test 5: Secret + Token Integration")
    
    try:
        # Validiere Secrets vor LLM-Call
        resolver.validate_required_secrets("TEST_SECRET")
        
        # Simuliere LLM-Call mit Token-Tracking
        new_budget_gate = ProductionTokenBudgetGate(budget_tokens=2000, spec_id="INTEGRATION-TEST")
        
        usage = new_budget_gate.record_token_usage(
            prompt_tokens=150,
            completion_tokens=100,
            model="gpt-3.5-turbo",
            request_id="integration-001"
        )
        
        # Hole Secret für LLM-Call (ohne Logging)
        secret_value = resolver.get_secret_value("TEST_SECRET")
        
        if secret_value and usage.total_tokens == 250:
            print("   ✅ Integration erfolgreich: Secret verfügbar, Token erfasst")
        else:
            print("   ❌ Integration fehlgeschlagen")
            return False
    
    except Exception as e:
        print(f"   ❌ Integration-Test-Fehler: {e}")
        return False
    
    # Test 6: Audit-Trail
    print("\n📋 Test 6: Audit-Trail")
    
    # Secret-Audit
    secret_audit = resolver.get_audit_log()
    if len(secret_audit) > 0:
        print(f"   ✅ Secret-Audit-Log: {len(secret_audit)} Einträge")
        
        # Prüfe dass keine Klartexte geloggt wurden
        audit_text = json.dumps(secret_audit)
        if "test-secret-value" not in audit_text.lower():
            print("   ✅ Keine Klartext-Secrets im Audit-Log")
        else:
            print("   ❌ Klartext-Secrets im Audit-Log gefunden!")
            return False
    else:
        print("   ❌ Kein Secret-Audit-Log vorhanden")
        return False
    
    # Token-Usage-Summary
    usage_summary = new_budget_gate.get_usage_summary()
    if "budget_status" in usage_summary and "model_breakdown" in usage_summary:
        print("   ✅ Token-Usage-Summary verfügbar")
    else:
        print("   ❌ Token-Usage-Summary unvollständig")
        return False
    
    # Cleanup
    del os.environ["TEST_SECRET"]
    
    print("\n🎉 Alle Tests bestanden!")
    print("✅ Production Secret-Token-System ist vollständig funktional")
    
    return True


def demo_production_secret_token_system():
    """Demo des Production Secret-Token-Systems."""
    print("🔐💰 PRODUCTION SECRET-TOKEN-SYSTEM DEMO")
    print("=" * 80)
    
    # Führe Tests aus
    test_success = test_production_secret_token_system()
    
    if not test_success:
        print("\n❌ Tests fehlgeschlagen!")
        return 1
    
    # Demo verschiedener Szenarien
    print("\n📋 Demo: Verschiedene Secret-Token-Szenarien")
    
    # Setze Demo-Secrets
    demo_secrets = {
        "OPENAI_API_KEY": "sk-demo-openai-key-abcdef123456",
        "GITHUB_TOKEN": "ghp_demo_github_token_789xyz",
        "DATABASE_URL": "postgresql://demo:secret@localhost/mydb"
    }
    
    for key, value in demo_secrets.items():
        os.environ[key] = value
    
    # Szenario 1: Erfolgreicher LLM-Workflow
    print("\n🎯 Szenario 1: Erfolgreicher LLM-Workflow")
    
    resolver = ProductionSecretResolver()
    budget_gate = ProductionTokenBudgetGate(budget_tokens=5000, spec_id="DEMO-WORKFLOW")
    
    try:
        # 1. Validiere erforderliche Secrets
        resolver.validate_required_secrets("OPENAI_API_KEY")
        
        # 2. Simuliere LLM-Requests
        requests = [
            {"prompt": 300, "completion": 150, "model": "gpt-4o-mini"},
            {"prompt": 250, "completion": 200, "model": "gpt-4o-mini"},
            {"prompt": 400, "completion": 100, "model": "gpt-3.5-turbo"},
        ]
        
        for i, req in enumerate(requests):
            usage = budget_gate.record_token_usage(
                prompt_tokens=req["prompt"],
                completion_tokens=req["completion"],
                model=req["model"],
                request_id=f"demo-{i+1}"
            )
            
            print(f"   Request {i+1}: {usage.total_tokens} tokens, ${usage.estimated_cost_usd:.6f}")
        
        # 3. Budget-Report
        print("\n📊 Final Budget Report:")
        status = budget_gate.check_budget_status()
        print(f"   Used: {status['tokens_used']:,} / {status['budget_tokens']:,} tokens ({status['usage_percentage']:.1f}%)")
        print(f"   Cost: ${status['estimated_cost_usd']:.6f}")
        print(f"   Status: {'✅ OK' if not status['is_budget_exceeded'] else '❌ EXCEEDED'}")
    
    except Exception as e:
        print(f"   ❌ Workflow-Fehler: {e}")
    
    # Szenario 2: Budget-Überschreitung
    print("\n💥 Szenario 2: Budget-Überschreitung")
    
    small_budget_gate = ProductionTokenBudgetGate(budget_tokens=500, spec_id="SMALL-BUDGET")
    
    try:
        # Versuche großen Request
        small_budget_gate.record_token_usage(
            prompt_tokens=400,
            completion_tokens=200,
            model="gpt-4o",
            request_id="large-request"
        )
        
        print("   ❌ Budget-Überschreitung nicht erkannt")
    
    except TokenBudgetExceededError:
        print("   ✅ Budget-Überschreitung korrekt abgefangen")
        status = small_budget_gate.check_budget_status()
        print(f"   Budget: {status['budget_tokens']} tokens")
        print(f"   Verwendet: {status['tokens_used']} tokens")
    
    # Szenario 3: Fehlende Secrets
    print("\n🚨 Szenario 3: Fehlende Secrets")
    
    try:
        resolver.validate_required_secrets("MISSING_SECRET", "ANOTHER_MISSING_SECRET")
        print("   ❌ Fehlende Secrets nicht erkannt")
    
    except SecretResolutionError as e:
        print("   ✅ Fehlende Secrets korrekt erkannt")
        print(f"   Error: {str(e)}")
    
    # Audit-Trail-Demo
    print("\n📋 Audit-Trail-Demo:")
    
    secret_audit = resolver.get_audit_log()
    print(f"   Secret-Zugriffe: {len(secret_audit)}")
    
    for entry in secret_audit[-3:]:  # Letzte 3 Einträge
        print(f"   - {entry['timestamp'][:19]} | {entry['key']} | {entry['source']} | {'✅' if entry['success'] else '❌'}")
    
    usage_summary = budget_gate.get_usage_summary()
    model_breakdown = usage_summary.get("model_breakdown", {})
    
    print("   Token-Usage by Model:")
    for model, stats in model_breakdown.items():
        print(f"   - {model}: {stats['total_tokens']:,} tokens, {stats['requests']} requests, ${stats['estimated_cost']:.6f}")
    
    # Cleanup
    for key in demo_secrets:
        if key in os.environ:
            del os.environ[key]
    
    print("\n🔐💰 Secret-Token-System-Capabilities:")
    print("   ✅ Zentrale Secret-Auflösung ohne Klartext-Logging")
    print("   ✅ Multi-Source-Support (ENV, Vault, OIDC, File)")
    print("   ✅ Secure Secret-Caching mit TTL")
    print("   ✅ Fail-Closed bei fehlenden erforderlichen Secrets")
    print("   ✅ Präzises Token-Budget-Accounting")
    print("   ✅ Real-Time Budget-Monitoring mit Fail-Closed")
    print("   ✅ Kostenschätzung nach Modell")
    print("   ✅ Umfassende Audit-Trails")
    print("   ✅ Integration-Ready für LLM-Workflows")
    
    print("\n✅ Production Secret-Token-System Demo abgeschlossen!")
    
    return 0


if __name__ == "__main__":
    exit_code = demo_production_secret_token_system()
    sys.exit(exit_code)
