"""
Token Budget Gate - Überwachung und Kontrolle des LLM-Token-Verbrauchs.

Erfasst beim LLM-Lauf die verbrauchten Tokens, vergleicht sie mit dem 
in der Spec angegebenen Budget und schlägt beim Überschreiten mit 
einem klaren Gate-Fail an.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

# Setup Logging
_log = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token-Verbrauchsinformationen für einen LLM-Call."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    timestamp: str
    
    @property
    def cost_estimate_usd(self) -> float:
        """Schätze Kosten basierend auf OpenAI-Preisen (Stand 2024)."""
        # Grobe Kostenschätzung für gpt-4o-mini
        if "gpt-4o-mini" in self.model.lower():
            # $0.000150 per 1K prompt tokens, $0.000600 per 1K completion tokens
            prompt_cost = (self.prompt_tokens / 1000) * 0.000150
            completion_cost = (self.completion_tokens / 1000) * 0.000600
            return prompt_cost + completion_cost
        elif "gpt-4" in self.model.lower():
            # $0.03 per 1K prompt tokens, $0.06 per 1K completion tokens
            prompt_cost = (self.prompt_tokens / 1000) * 0.03
            completion_cost = (self.completion_tokens / 1000) * 0.06
            return prompt_cost + completion_cost
        else:
            # Fallback für unbekannte Modelle
            return (self.total_tokens / 1000) * 0.001


class TokenBudgetGate:
    """Gate zur Überwachung und Kontrolle des Token-Budgets."""
    
    def __init__(self, budget_limit: int, spec_id: Optional[str] = None):
        """
        Args:
            budget_limit: Maximales Token-Budget
            spec_id: ID der Feature-Spec (für Logging)
        """
        self.budget_limit = budget_limit
        self.spec_id = spec_id or "unknown"
        self.token_usage_history: List[TokenUsage] = []
        self.total_tokens_used = 0
        self.gate_failed = False
        self.failure_reason: Optional[str] = None
        
        _log.info(f"[{self.spec_id}] Token Budget Gate initialisiert: {budget_limit} Tokens")
    
    def record_usage(self, usage: TokenUsage) -> None:
        """
        Erfasse Token-Verbrauch für einen LLM-Call.
        
        Args:
            usage: Token-Verbrauchsinformationen
        """
        self.token_usage_history.append(usage)
        self.total_tokens_used += usage.total_tokens
        
        _log.info(f"[{self.spec_id}] Token-Verbrauch erfasst: {usage.total_tokens} Tokens "
                 f"(Model: {usage.model}, Gesamt: {self.total_tokens_used}/{self.budget_limit})")
        
        # Prüfe Budget-Überschreitung
        if self.total_tokens_used > self.budget_limit:
            self.gate_failed = True
            self.failure_reason = (f"Token-Budget überschritten: {self.total_tokens_used} > {self.budget_limit}")
            _log.error(f"[{self.spec_id}] {self.failure_reason}")
    
    def check_gate(self) -> bool:
        """
        Prüfe ob das Token-Budget eingehalten wurde.
        
        Returns:
            True wenn Budget eingehalten, False bei Überschreitung
        """
        if self.gate_failed:
            return False
        return self.total_tokens_used <= self.budget_limit
    
    def get_usage_summary(self) -> Dict:
        """
        Hole zusammenfassende Token-Verbrauchsstatistiken.
        
        Returns:
            Dictionary mit Verbrauchsstatistiken
        """
        if not self.token_usage_history:
            return {
                "spec_id": self.spec_id,
                "budget_limit": self.budget_limit,
                "total_tokens_used": 0,
                "budget_remaining": self.budget_limit,
                "budget_utilization_percent": 0.0,
                "gate_passed": True,
                "calls_count": 0,
                "estimated_cost_usd": 0.0,
                "failure_reason": None
            }
        
        total_cost = sum(usage.cost_estimate_usd for usage in self.token_usage_history)
        utilization_percent = (self.total_tokens_used / self.budget_limit) * 100
        
        return {
            "spec_id": self.spec_id,
            "budget_limit": self.budget_limit,
            "total_tokens_used": self.total_tokens_used,
            "budget_remaining": max(0, self.budget_limit - self.total_tokens_used),
            "budget_utilization_percent": round(utilization_percent, 2),
            "gate_passed": not self.gate_failed,
            "calls_count": len(self.token_usage_history),
            "estimated_cost_usd": round(total_cost, 4),
            "failure_reason": self.failure_reason,
            "usage_breakdown": [
                {
                    "model": usage.model,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost_usd": round(usage.cost_estimate_usd, 4),
                    "timestamp": usage.timestamp
                }
                for usage in self.token_usage_history
            ]
        }
    
    def generate_qa_summary_section(self) -> Dict:
        """
        Generiere Token-Budget-Sektion für QA-Zusammenfassung.
        
        Returns:
            Dictionary für QA-Scorecard-Integration
        """
        summary = self.get_usage_summary()
        
        return {
            "name": "Token Budget",
            "passed": summary["gate_passed"],
            "score": 100 if summary["gate_passed"] else 0,
            "details": {
                "budget_limit": summary["budget_limit"],
                "tokens_used": summary["total_tokens_used"],
                "utilization_percent": summary["budget_utilization_percent"],
                "calls_count": summary["calls_count"],
                "estimated_cost_usd": summary["estimated_cost_usd"]
            },
            "error_message": summary["failure_reason"] if not summary["gate_passed"] else None
        }


def create_token_budget_gate_from_spec(feature_spec) -> TokenBudgetGate:
    """
    Erstelle Token Budget Gate aus Feature-Spec.
    
    Args:
        feature_spec: FeatureSpec-Objekt mit token_budget Feld
        
    Returns:
        Konfiguriertes TokenBudgetGate
    """
    return TokenBudgetGate(
        budget_limit=feature_spec.token_budget,
        spec_id=feature_spec.id
    )


def demo_token_budget_gate():
    """Demonstriere das Token Budget Gate System."""
    print("🎯 Token Budget Gate Demo")
    print("=" * 50)
    
    # Test 1: Budget eingehalten
    print("\n📊 Test 1: Budget eingehalten")
    gate1 = TokenBudgetGate(budget_limit=5000, spec_id="TEST-001")
    
    # Simuliere LLM-Calls
    from datetime import datetime
    
    usage1 = TokenUsage(
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        model="gpt-4o-mini",
        timestamp=datetime.now().isoformat()
    )
    
    usage2 = TokenUsage(
        prompt_tokens=1200,
        completion_tokens=800,
        total_tokens=2000,
        model="gpt-4o-mini", 
        timestamp=datetime.now().isoformat()
    )
    
    gate1.record_usage(usage1)
    gate1.record_usage(usage2)
    
    summary1 = gate1.get_usage_summary()
    qa_section1 = gate1.generate_qa_summary_section()
    
    print(f"✅ Gate Status: {'PASSED' if gate1.check_gate() else 'FAILED'}")
    print(f"📈 Budget-Nutzung: {summary1['total_tokens_used']}/{summary1['budget_limit']} Tokens ({summary1['budget_utilization_percent']}%)")
    print(f"💰 Geschätzte Kosten: ${summary1['estimated_cost_usd']}")
    print(f"🔍 QA Score: {qa_section1['score']}")
    
    # Test 2: Budget überschritten
    print("\n📊 Test 2: Budget überschritten")
    gate2 = TokenBudgetGate(budget_limit=1000, spec_id="TEST-002")
    
    usage3 = TokenUsage(
        prompt_tokens=800,
        completion_tokens=400,
        total_tokens=1200,  # Überschreitet Budget von 1000
        model="gpt-4o-mini",
        timestamp=datetime.now().isoformat()
    )
    
    gate2.record_usage(usage3)
    
    summary2 = gate2.get_usage_summary()
    qa_section2 = gate2.generate_qa_summary_section()
    
    print(f"❌ Gate Status: {'PASSED' if gate2.check_gate() else 'FAILED'}")
    print(f"📈 Budget-Nutzung: {summary2['total_tokens_used']}/{summary2['budget_limit']} Tokens ({summary2['budget_utilization_percent']}%)")
    print(f"⚠️  Fehlergrund: {summary2['failure_reason']}")
    print(f"🔍 QA Score: {qa_section2['score']}")
    
    # Test 3: Integration in QA-Zusammenfassung
    print("\n📊 Test 3: QA-Integration")
    qa_summary = {
        "spec_id": "TEST-003",
        "gates": [
            qa_section1,
            qa_section2
        ]
    }
    
    print("QA-Zusammenfassung:")
    print(json.dumps(qa_summary, indent=2))
    
    print("\n✅ Demo abgeschlossen!")


if __name__ == "__main__":
    demo_token_budget_gate()
