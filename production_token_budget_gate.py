"""
Production Token Budget Gate.

Token-Accounting pro Request/Response erfassen, kumulieren und gegen 
das in der Spec/Policy definierte Budget prüfen. Überschreitung führt 
zum Gate-Fail. Verbrauch in der QA-Zusammenfassung ausweisen.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

# Setup Logging
_log = logging.getLogger(__name__)


class TokenType(str, Enum):
    """Token-Typen für detailliertes Accounting."""
    PROMPT = "prompt"
    COMPLETION = "completion"
    TOTAL = "total"


class ModelTier(str, Enum):
    """Modell-Tiers für Kostenberechnung."""
    GPT4O_MINI = "gpt-4o-mini"
    GPT4O = "gpt-4o"
    GPT4_TURBO = "gpt-4-turbo"
    GPT35_TURBO = "gpt-3.5-turbo"


@dataclass
class TokenUsageEntry:
    """Einzelner Token-Verbrauchseintrag."""
    timestamp: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    request_id: Optional[str] = None
    operation: Optional[str] = None  # z.B. "diff_generation", "code_review"
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class TokenBudgetPolicy:
    """Token-Budget-Policy mit Limits und Regeln."""
    total_budget: int
    prompt_token_limit: int = 4000  # Pro Request
    completion_token_limit: int = 2000  # Pro Response
    cost_limit_usd: float = 10.0  # Maximale Kosten
    warning_threshold: float = 0.8  # Warnung bei 80%
    
    # Modell-spezifische Limits
    model_limits: Dict[str, int] = field(default_factory=lambda: {
        ModelTier.GPT4O_MINI.value: 50000,
        ModelTier.GPT4O.value: 10000,
        ModelTier.GPT4_TURBO.value: 15000,
        ModelTier.GPT35_TURBO.value: 100000
    })
    
    # Kosten pro 1K Token (Stand 2024)
    token_costs: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        ModelTier.GPT4O_MINI.value: {"prompt": 0.000150, "completion": 0.000600},
        ModelTier.GPT4O.value: {"prompt": 0.0050, "completion": 0.0150},
        ModelTier.GPT4_TURBO.value: {"prompt": 0.0100, "completion": 0.0300},
        ModelTier.GPT35_TURBO.value: {"prompt": 0.0015, "completion": 0.0020}
    })


@dataclass
class TokenBudgetStatus:
    """Aktueller Status des Token-Budgets."""
    total_tokens_used: int
    total_cost_usd: float
    budget_utilization: float  # 0.0 - 1.0
    cost_utilization: float    # 0.0 - 1.0
    requests_count: int
    average_tokens_per_request: float
    is_over_budget: bool
    is_over_cost_limit: bool
    warning_triggered: bool
    
    @property
    def status_emoji(self) -> str:
        """Status-Emoji basierend auf Nutzung."""
        if self.is_over_budget or self.is_over_cost_limit:
            return "💀"
        elif self.budget_utilization > 0.9:
            return "🔴"
        elif self.budget_utilization > 0.8:
            return "🟡"
        else:
            return "🟢"


class ProductionTokenBudgetGate:
    """Production-Ready Token Budget Gate mit detailliertem Accounting."""
    
    def __init__(self, 
                 budget_policy: TokenBudgetPolicy,
                 spec_id: Optional[str] = None,
                 strict_mode: bool = True):
        """
        Args:
            budget_policy: Token-Budget-Policy
            spec_id: ID der Feature-Spec für Logging
            strict_mode: Strenger Modus mit harten Abbrüchen
        """
        self.budget_policy = budget_policy
        self.spec_id = spec_id or "unknown"
        self.strict_mode = strict_mode
        
        # Token-Accounting
        self.usage_entries: List[TokenUsageEntry] = []
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        
        # Warnings und Failures
        self.warnings_issued: List[str] = []
        self.gate_failed = False
        self.failure_reason: Optional[str] = None
        
        _log.info(f"[{self.spec_id}] Production Token Budget Gate initialisiert")
        _log.info(f"[{self.spec_id}] Budget: {budget_policy.total_budget} Tokens, ${budget_policy.cost_limit_usd}")
    
    def record_token_usage(self, 
                          model: str,
                          prompt_tokens: int,
                          completion_tokens: int,
                          operation: str = None,
                          request_id: str = None) -> TokenUsageEntry:
        """
        Erfasse Token-Verbrauch für Request/Response.
        
        Args:
            model: Verwendetes Modell
            prompt_tokens: Verbrauchte Prompt-Tokens
            completion_tokens: Verbrauchte Completion-Tokens
            operation: Art der Operation (optional)
            request_id: Request-ID für Tracking (optional)
            
        Returns:
            TokenUsageEntry mit Details
            
        Raises:
            RuntimeError: Bei Budget-Überschreitung im strict_mode
        """
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        
        # Erstelle Usage-Entry
        entry = TokenUsageEntry(
            timestamp=datetime.now().isoformat(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            request_id=request_id,
            operation=operation
        )
        
        # Validiere Request-Limits
        self._validate_request_limits(entry)
        
        # Füge zu Accounting hinzu
        self.usage_entries.append(entry)
        self.total_tokens_used += total_tokens
        self.total_cost_usd += estimated_cost
        
        _log.info(f"[{self.spec_id}] Token-Verbrauch erfasst: {total_tokens} Tokens "
                 f"(Model: {model}, Cost: ${estimated_cost:.4f}, Gesamt: {self.total_tokens_used}/{self.budget_policy.total_budget})")
        
        # Prüfe Budget-Status
        self._check_budget_status()
        
        return entry
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Berechne Kosten für Token-Verbrauch."""
        if model not in self.budget_policy.token_costs:
            _log.warning(f"[{self.spec_id}] Unbekanntes Modell für Kostenberechnung: {model}")
            model = ModelTier.GPT4O_MINI.value  # Fallback
        
        costs = self.budget_policy.token_costs[model]
        
        prompt_cost = (prompt_tokens / 1000) * costs["prompt"]
        completion_cost = (completion_tokens / 1000) * costs["completion"]
        
        return prompt_cost + completion_cost
    
    def _validate_request_limits(self, entry: TokenUsageEntry):
        """Validiere Request-spezifische Limits."""
        # Prompt-Token-Limit
        if entry.prompt_tokens > self.budget_policy.prompt_token_limit:
            error_msg = (f"Prompt-Token-Limit überschritten: {entry.prompt_tokens} > "
                        f"{self.budget_policy.prompt_token_limit}")
            self._handle_violation(error_msg, critical=True)
        
        # Completion-Token-Limit
        if entry.completion_tokens > self.budget_policy.completion_token_limit:
            error_msg = (f"Completion-Token-Limit überschritten: {entry.completion_tokens} > "
                        f"{self.budget_policy.completion_token_limit}")
            self._handle_violation(error_msg, critical=True)
        
        # Modell-spezifisches Limit
        if entry.model in self.budget_policy.model_limits:
            model_used = sum(e.total_tokens for e in self.usage_entries if e.model == entry.model)
            model_limit = self.budget_policy.model_limits[entry.model]
            
            if model_used + entry.total_tokens > model_limit:
                error_msg = (f"Modell-spezifisches Limit überschritten für {entry.model}: "
                           f"{model_used + entry.total_tokens} > {model_limit}")
                self._handle_violation(error_msg, critical=True)
    
    def _check_budget_status(self):
        """Prüfe aktuellen Budget-Status und handle Violations."""
        budget_utilization = self.total_tokens_used / self.budget_policy.total_budget
        self.total_cost_usd / self.budget_policy.cost_limit_usd
        
        # Warning-Threshold
        if (budget_utilization >= self.budget_policy.warning_threshold and 
            not any("warning_threshold" in w for w in self.warnings_issued)):
            warning_msg = (f"Budget-Warning: {budget_utilization:.1%} des Budgets verbraucht "
                          f"({self.total_tokens_used}/{self.budget_policy.total_budget} Tokens)")
            self.warnings_issued.append(f"warning_threshold: {warning_msg}")
            _log.warning(f"[{self.spec_id}] {warning_msg}")
        
        # Budget-Überschreitung
        if self.total_tokens_used > self.budget_policy.total_budget:
            error_msg = (f"Token-Budget überschritten: {self.total_tokens_used} > "
                        f"{self.budget_policy.total_budget}")
            self._handle_violation(error_msg, critical=True)
        
        # Kosten-Überschreitung
        if self.total_cost_usd > self.budget_policy.cost_limit_usd:
            error_msg = (f"Kosten-Limit überschritten: ${self.total_cost_usd:.4f} > "
                        f"${self.budget_policy.cost_limit_usd}")
            self._handle_violation(error_msg, critical=True)
    
    def _handle_violation(self, message: str, critical: bool = False):
        """Handle Budget-Verletzung."""
        if critical:
            self.gate_failed = True
            self.failure_reason = message
            _log.error(f"[{self.spec_id}] CRITICAL: {message}")
            
            if self.strict_mode:
                raise RuntimeError(f"Token Budget Gate Failure: {message}")
        else:
            self.warnings_issued.append(message)
            _log.warning(f"[{self.spec_id}] WARNING: {message}")
    
    def get_budget_status(self) -> TokenBudgetStatus:
        """Hole aktuellen Budget-Status."""
        budget_utilization = self.total_tokens_used / self.budget_policy.total_budget
        cost_utilization = self.total_cost_usd / self.budget_policy.cost_limit_usd
        requests_count = len(self.usage_entries)
        avg_tokens = self.total_tokens_used / max(1, requests_count)
        
        return TokenBudgetStatus(
            total_tokens_used=self.total_tokens_used,
            total_cost_usd=self.total_cost_usd,
            budget_utilization=budget_utilization,
            cost_utilization=cost_utilization,
            requests_count=requests_count,
            average_tokens_per_request=avg_tokens,
            is_over_budget=self.total_tokens_used > self.budget_policy.total_budget,
            is_over_cost_limit=self.total_cost_usd > self.budget_policy.cost_limit_usd,
            warning_triggered=len(self.warnings_issued) > 0
        )
    
    def check_gate(self) -> bool:
        """
        Prüfe Token Budget Gate.
        
        Returns:
            True wenn Gate bestanden, False bei Failure
        """
        if self.gate_failed:
            _log.error(f"[{self.spec_id}] Token Budget Gate FAILED: {self.failure_reason}")
            return False
        
        status = self.get_budget_status()
        
        if status.is_over_budget or status.is_over_cost_limit:
            _log.error(f"[{self.spec_id}] Token Budget Gate FAILED: Budget oder Kosten überschritten")
            return False
        
        _log.info(f"[{self.spec_id}] Token Budget Gate PASSED "
                 f"({status.budget_utilization:.1%} Budget, ${status.total_cost_usd:.4f} Kosten)")
        return True
    
    def generate_qa_summary_section(self) -> Dict:
        """Generiere QA-Summary-Sektion für Token Budget."""
        status = self.get_budget_status()
        
        # Score basierend auf Budget-Effizienz
        if status.is_over_budget or status.is_over_cost_limit:
            score = 0
        elif status.budget_utilization > 0.9:
            score = 50
        elif status.budget_utilization > 0.8:
            score = 75
        else:
            score = 100
        
        return {
            "name": "Token Budget",
            "passed": not (status.is_over_budget or status.is_over_cost_limit),
            "score": score,
            "details": {
                "budget_limit": self.budget_policy.total_budget,
                "tokens_used": status.total_tokens_used,
                "budget_utilization_percent": round(status.budget_utilization * 100, 1),
                "cost_limit_usd": self.budget_policy.cost_limit_usd,
                "total_cost_usd": round(status.total_cost_usd, 4),
                "cost_utilization_percent": round(status.cost_utilization * 100, 1),
                "requests_count": status.requests_count,
                "average_tokens_per_request": round(status.average_tokens_per_request, 1),
                "warnings_count": len(self.warnings_issued),
                "models_used": list(set(entry.model for entry in self.usage_entries))
            },
            "error_message": self.failure_reason if self.gate_failed else None,
            "status_emoji": status.status_emoji
        }
    
    def generate_detailed_report(self) -> Dict:
        """Generiere detaillierten Token-Verbrauchsreport."""
        status = self.get_budget_status()
        
        # Gruppiere nach Modellen
        model_usage = {}
        for entry in self.usage_entries:
            if entry.model not in model_usage:
                model_usage[entry.model] = {
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "request_count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0
                }
            
            model_usage[entry.model]["total_tokens"] += entry.total_tokens
            model_usage[entry.model]["total_cost"] += entry.estimated_cost_usd
            model_usage[entry.model]["request_count"] += 1
            model_usage[entry.model]["prompt_tokens"] += entry.prompt_tokens
            model_usage[entry.model]["completion_tokens"] += entry.completion_tokens
        
        # Gruppiere nach Operationen
        operation_usage = {}
        for entry in self.usage_entries:
            op = entry.operation or "unknown"
            if op not in operation_usage:
                operation_usage[op] = {"total_tokens": 0, "total_cost": 0.0, "request_count": 0}
            
            operation_usage[op]["total_tokens"] += entry.total_tokens
            operation_usage[op]["total_cost"] += entry.estimated_cost_usd
            operation_usage[op]["request_count"] += 1
        
        return {
            "spec_id": self.spec_id,
            "timestamp": datetime.now().isoformat(),
            "budget_policy": {
                "total_budget": self.budget_policy.total_budget,
                "cost_limit_usd": self.budget_policy.cost_limit_usd,
                "prompt_token_limit": self.budget_policy.prompt_token_limit,
                "completion_token_limit": self.budget_policy.completion_token_limit
            },
            "status": {
                "total_tokens_used": status.total_tokens_used,
                "total_cost_usd": round(status.total_cost_usd, 4),
                "budget_utilization": round(status.budget_utilization, 3),
                "cost_utilization": round(status.cost_utilization, 3),
                "requests_count": status.requests_count,
                "gate_passed": not self.gate_failed
            },
            "model_breakdown": model_usage,
            "operation_breakdown": operation_usage,
            "warnings": self.warnings_issued,
            "failure_reason": self.failure_reason,
            "usage_entries": [
                {
                    "timestamp": entry.timestamp,
                    "model": entry.model,
                    "operation": entry.operation,
                    "prompt_tokens": entry.prompt_tokens,
                    "completion_tokens": entry.completion_tokens,
                    "total_tokens": entry.total_tokens,
                    "estimated_cost_usd": round(entry.estimated_cost_usd, 4)
                }
                for entry in self.usage_entries
            ]
        }
    
    def save_detailed_report(self, filepath: str):
        """Speichere detaillierten Report als JSON."""
        report = self.generate_detailed_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        _log.info(f"[{self.spec_id}] Token Budget Report gespeichert: {filepath}")


def demo_production_token_budget_gate():
    """Demonstriere Production Token Budget Gate."""
    print("💰 Production Token Budget Gate Demo")
    print("=" * 60)
    
    # Test 1: Normaler Betrieb innerhalb Budget
    print("\n✅ Test 1: Normaler Betrieb innerhalb Budget")
    
    policy = TokenBudgetPolicy(
        total_budget=10000,
        cost_limit_usd=5.0,
        warning_threshold=0.8
    )
    
    gate = ProductionTokenBudgetGate(policy, spec_id="BUDGET-001", strict_mode=True)
    
    # Simuliere verschiedene LLM-Calls
    llm_calls = [
        ("gpt-4o-mini", 500, 300, "code_generation"),
        ("gpt-4o-mini", 800, 400, "code_review"),
        ("gpt-4o-mini", 600, 250, "test_generation"),
        ("gpt-4o", 300, 150, "final_review"),
    ]
    
    for model, prompt_tokens, completion_tokens, operation in llm_calls:
        entry = gate.record_token_usage(model, prompt_tokens, completion_tokens, operation)
        print(f"📞 {operation}: {entry.total_tokens} Tokens, ${entry.estimated_cost_usd:.4f} ({model})")
    
    status = gate.get_budget_status()
    gate_passed = gate.check_gate()
    
    print("\n📊 Budget-Status:")
    print(f"   - Status: {status.status_emoji} {'PASSED' if gate_passed else 'FAILED'}")
    print(f"   - Token-Verbrauch: {status.total_tokens_used}/{policy.total_budget} ({status.budget_utilization:.1%})")
    print(f"   - Kosten: ${status.total_cost_usd:.4f}/${policy.cost_limit_usd} ({status.cost_utilization:.1%})")
    print(f"   - Requests: {status.requests_count}")
    print(f"   - Ø Tokens/Request: {status.average_tokens_per_request:.1f}")
    print(f"   - Warnungen: {len(gate.warnings_issued)}")
    
    # Test 2: Budget-Überschreitung
    print("\n❌ Test 2: Budget-Überschreitung")
    
    small_policy = TokenBudgetPolicy(
        total_budget=1000,  # Sehr kleines Budget
        cost_limit_usd=0.10
    )
    
    gate2 = ProductionTokenBudgetGate(small_policy, spec_id="BUDGET-002", strict_mode=True)
    
    try:
        # Versuche großen Call
        gate2.record_token_usage("gpt-4o", 800, 500, "large_generation")
        print("⚠️  Budget-Überschreitung nicht erkannt - Fehler!")
    except RuntimeError as e:
        print(f"✅ Budget-Überschreitung korrekt erkannt: {e}")
    
    # Test 3: Detaillierter Report
    print("\n📄 Test 3: Detaillierter Report")
    
    report = gate.generate_detailed_report()
    
    print("📋 Report-Details:")
    print(f"   - Spec ID: {report['spec_id']}")
    print(f"   - Budget-Nutzung: {report['status']['budget_utilization']:.1%}")
    print(f"   - Modelle verwendet: {len(report['model_breakdown'])}")
    print(f"   - Operationen: {len(report['operation_breakdown'])}")
    
    print("\n📊 Modell-Breakdown:")
    for model, usage in report['model_breakdown'].items():
        print(f"   - {model}: {usage['total_tokens']} Tokens, ${usage['total_cost']:.4f}, {usage['request_count']} Requests")
    
    print("\n🔧 Operation-Breakdown:")
    for operation, usage in report['operation_breakdown'].items():
        print(f"   - {operation}: {usage['total_tokens']} Tokens, ${usage['total_cost']:.4f}")
    
    # Test 4: QA-Integration
    print("\n📊 Test 4: QA-Integration")
    
    qa_section = gate.generate_qa_summary_section()
    
    print("🎯 QA-Summary:")
    print(f"   - Name: {qa_section['name']}")
    print(f"   - Passed: {'✅ YES' if qa_section['passed'] else '❌ NO'}")
    print(f"   - Score: {qa_section['score']}/100")
    print(f"   - Status: {qa_section['status_emoji']}")
    
    if qa_section.get('error_message'):
        print(f"   - Error: {qa_section['error_message']}")
    
    # Test 5: Report-Export
    print("\n💾 Test 5: Report-Export")
    
    report_file = "token_budget_report_demo.json"
    gate.save_detailed_report(report_file)
    
    print(f"📄 Report exportiert: {report_file}")
    
    # Lade und validiere Report
    with open(report_file, 'r', encoding='utf-8') as f:
        loaded_report = json.load(f)
    
    print("✅ Report-Validierung:")
    print(f"   - Entries: {len(loaded_report['usage_entries'])}")
    print(f"   - Total Cost: ${loaded_report['status']['total_cost_usd']}")
    print(f"   - Gate Status: {'PASSED' if loaded_report['status']['gate_passed'] else 'FAILED'}")
    
    print("\n✅ Production Token Budget Gate Demo abgeschlossen!")
    print("💰 Vollständiges Token-Accounting und Budget-Management aktiv")


if __name__ == "__main__":
    demo_production_token_budget_gate()
