"""
Policy-Governance konfigurierbar machen.

Zentralisiert alle Schwellwerte und erlaubte Praktiken in einer 
maschinenlesbaren Policy. Verhindert Policy-Absenkung zur Laufzeit 
im Secure-Modus.
"""

from __future__ import annotations

import json
import os
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging


logger = logging.getLogger(__name__)


class PolicyDomain(Enum):
    """Policy-Domänen."""
    QUALITY = "quality"
    SECURITY = "security"
    BUILD = "build"
    TEST = "test"
    DEPLOY = "deploy"
    GUARD = "guard"
    SANDBOX = "sandbox"
    PERFORMANCE = "performance"


class PolicyEnforcementMode(Enum):
    """Policy-Durchsetzungsmodi."""
    PERMISSIVE = "permissive"  # Warnungen, aber keine Blockierung
    STRICT = "strict"          # Blockierung bei Verletzungen
    SECURE = "secure"          # Maximale Sicherheit, keine Runtime-Änderungen


@dataclass
class PolicyRule:
    """Policy-Regel."""
    
    # Regel-Identifikation
    rule_id: str
    domain: PolicyDomain
    name: str
    description: str
    
    # Regel-Wert
    value: Union[int, float, str, bool, List[str]]
    value_type: str  # int, float, string, boolean, list
    
    # Metadaten
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[str]] = None
    
    # Enforcement
    enforcement_mode: PolicyEnforcementMode = PolicyEnforcementMode.STRICT
    can_be_overridden: bool = False
    
    # Dokumentation
    rationale: str = ""
    impact: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "rule_id": self.rule_id,
            "domain": self.domain.value,
            "name": self.name,
            "description": self.description,
            "value": self.value,
            "value_type": self.value_type,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "allowed_values": self.allowed_values,
            "enforcement_mode": self.enforcement_mode.value,
            "can_be_overridden": self.can_be_overridden,
            "rationale": self.rationale,
            "impact": self.impact
        }


@dataclass
class PolicyViolation:
    """Policy-Verletzung."""
    
    rule_id: str
    rule_name: str
    expected_value: Any
    actual_value: Any
    
    severity: str = "high"  # low, medium, high, critical
    message: str = ""
    component: str = ""
    
    # Remediation
    suggested_action: str = ""
    can_continue: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "severity": self.severity,
            "message": self.message,
            "component": self.component,
            "suggested_action": self.suggested_action,
            "can_continue": self.can_continue
        }


@dataclass
class PolicyConfiguration:
    """Policy-Konfiguration."""
    
    # Konfiguration-Metadaten
    version: str
    created_at: str
    last_modified: str
    
    # Globale Einstellungen
    global_enforcement_mode: PolicyEnforcementMode
    secure_mode_enabled: bool
    
    # Policy-Regeln
    rules: Dict[str, PolicyRule] = field(default_factory=dict)
    
    # Konfiguration-Schutz
    config_hash: Optional[str] = None
    signed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "global_enforcement_mode": self.global_enforcement_mode.value,
            "secure_mode_enabled": self.secure_mode_enabled,
            "rules": {rule_id: rule.to_dict() for rule_id, rule in self.rules.items()},
            "config_hash": self.config_hash,
            "signed": self.signed
        }


class PolicyManager:
    """Policy-Manager."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("policies/governance.yml")
        self.config: Optional[PolicyConfiguration] = None
        self.runtime_overrides: Dict[str, Any] = {}
        self.secure_mode = self._detect_secure_mode()
        
        # Lade Konfiguration
        self._load_configuration()
    
    def _detect_secure_mode(self) -> bool:
        """Erkenne Secure-Mode."""
        return os.getenv("SECURE_MODE", "true").lower() == "true"
    
    def _load_configuration(self):
        """Lade Policy-Konfiguration."""
        if not self.config_path.exists():
            logger.warning(f"Policy configuration not found: {self.config_path}")
            self.config = self._create_default_configuration()
            self._save_configuration()
            return
        
        try:
            with self.config_path.open('r') as f:
                if self.config_path.suffix.lower() in ['.yml', '.yaml']:
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)
            
            self.config = self._parse_configuration(config_data)
            
            # Validiere Konfiguration
            self._validate_configuration()
            
            logger.info(f"Loaded policy configuration from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load policy configuration: {e}")
            self.config = self._create_default_configuration()
    
    def _create_default_configuration(self) -> PolicyConfiguration:
        """Erstelle Standard-Konfiguration."""
        config = PolicyConfiguration(
            version="1.0.0",
            created_at=datetime.utcnow().isoformat(),
            last_modified=datetime.utcnow().isoformat(),
            global_enforcement_mode=PolicyEnforcementMode.STRICT,
            secure_mode_enabled=self.secure_mode
        )
        
        # Quality-Regeln
        config.rules["quality.coverage_min"] = PolicyRule(
            rule_id="quality.coverage_min",
            domain=PolicyDomain.QUALITY,
            name="Minimum Test Coverage",
            description="Minimum required test coverage percentage",
            value=30.0,
            value_type="float",
            min_value=0.0,
            max_value=100.0,
            enforcement_mode=PolicyEnforcementMode.STRICT,
            can_be_overridden=False,
            rationale="Ensures adequate test coverage for code quality",
            impact="Blocks deployment if coverage is below threshold"
        )
        
        config.rules["quality.score_threshold"] = PolicyRule(
            rule_id="quality.score_threshold",
            domain=PolicyDomain.QUALITY,
            name="Quality Score Threshold",
            description="Minimum quality score required",
            value=70.0,
            value_type="float",
            min_value=0.0,
            max_value=100.0,
            enforcement_mode=PolicyEnforcementMode.STRICT,
            can_be_overridden=True,
            rationale="Maintains overall code quality standards",
            impact="Blocks deployment if quality score is below threshold"
        )
        
        # Security-Regeln
        config.rules["security.high_severity_max"] = PolicyRule(
            rule_id="security.high_severity_max",
            domain=PolicyDomain.SECURITY,
            name="Maximum High Severity Findings",
            description="Maximum allowed high severity security findings",
            value=0,
            value_type="int",
            min_value=0,
            enforcement_mode=PolicyEnforcementMode.STRICT,
            can_be_overridden=False,
            rationale="Critical security issues must be resolved",
            impact="Blocks deployment if high severity findings exist"
        )
        
        config.rules["security.active_tools_min"] = PolicyRule(
            rule_id="security.active_tools_min",
            domain=PolicyDomain.SECURITY,
            name="Minimum Active Security Tools",
            description="Minimum number of security tools that must run",
            value=1,
            value_type="int",
            min_value=0,
            enforcement_mode=PolicyEnforcementMode.STRICT,
            can_be_overridden=False,
            rationale="Ensures security scanning is performed",
            impact="Blocks deployment if insufficient security tools run"
        )
        
        config.rules["security.allowed_licenses"] = PolicyRule(
            rule_id="security.allowed_licenses",
            domain=PolicyDomain.SECURITY,
            name="Allowed Licenses",
            description="List of allowed dependency licenses",
            value=["MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause"],
            value_type="list",
            enforcement_mode=PolicyEnforcementMode.STRICT,
            can_be_overridden=True,
            rationale="Ensures license compatibility",
            impact="Blocks deployment if forbidden licenses detected"
        )
        
        # Build-Regeln
        config.rules["build.timeout_minutes"] = PolicyRule(
            rule_id="build.timeout_minutes",
            domain=PolicyDomain.BUILD,
            name="Build Timeout",
            description="Maximum build time in minutes",
            value=30,
            value_type="int",
            min_value=1,
            max_value=120,
            enforcement_mode=PolicyEnforcementMode.STRICT,
            can_be_overridden=True,
            rationale="Prevents runaway builds",
            impact="Terminates build if timeout exceeded"
        )
        
        # Test-Regeln
        config.rules["test.timeout_minutes"] = PolicyRule(
            rule_id="test.timeout_minutes",
            domain=PolicyDomain.TEST,
            name="Test Timeout",
            description="Maximum test execution time in minutes",
            value=15,
            value_type="int",
            min_value=1,
            max_value=60,
            enforcement_mode=PolicyEnforcementMode.STRICT,
            can_be_overridden=True,
            rationale="Prevents runaway tests",
            impact="Terminates tests if timeout exceeded"
        )
        
        # Performance-Regeln
        config.rules["performance.startup_time_max"] = PolicyRule(
            rule_id="performance.startup_time_max",
            domain=PolicyDomain.PERFORMANCE,
            name="Maximum Startup Time",
            description="Maximum allowed startup time in seconds",
            value=30.0,
            value_type="float",
            min_value=1.0,
            enforcement_mode=PolicyEnforcementMode.PERMISSIVE,
            can_be_overridden=True,
            rationale="Ensures reasonable startup performance",
            impact="Warning if startup time exceeds threshold"
        )
        
        # Token-Budget
        config.rules["llm.token_budget_max"] = PolicyRule(
            rule_id="llm.token_budget_max",
            domain=PolicyDomain.QUALITY,
            name="Maximum Token Budget",
            description="Maximum allowed LLM tokens per run",
            value=500,
            value_type="int",
            min_value=50,
            enforcement_mode=PolicyEnforcementMode.STRICT,
            can_be_overridden=True,
            rationale="Controls LLM costs and prevents runaway generation",
            impact="Blocks execution if token budget exceeded"
        )
        
        return config
    
    def _parse_configuration(self, config_data: Dict[str, Any]) -> PolicyConfiguration:
        """Parse Konfigurationsdaten."""
        config = PolicyConfiguration(
            version=config_data.get("version", "1.0.0"),
            created_at=config_data.get("created_at", datetime.utcnow().isoformat()),
            last_modified=config_data.get("last_modified", datetime.utcnow().isoformat()),
            global_enforcement_mode=PolicyEnforcementMode(
                config_data.get("global_enforcement_mode", "strict")
            ),
            secure_mode_enabled=config_data.get("secure_mode_enabled", self.secure_mode),
            config_hash=config_data.get("config_hash"),
            signed=config_data.get("signed", False)
        )
        
        # Parse Regeln
        rules_data = config_data.get("rules", {})
        for rule_id, rule_data in rules_data.items():
            config.rules[rule_id] = PolicyRule(
                rule_id=rule_id,
                domain=PolicyDomain(rule_data["domain"]),
                name=rule_data["name"],
                description=rule_data["description"],
                value=rule_data["value"],
                value_type=rule_data["value_type"],
                min_value=rule_data.get("min_value"),
                max_value=rule_data.get("max_value"),
                allowed_values=rule_data.get("allowed_values"),
                enforcement_mode=PolicyEnforcementMode(
                    rule_data.get("enforcement_mode", "strict")
                ),
                can_be_overridden=rule_data.get("can_be_overridden", False),
                rationale=rule_data.get("rationale", ""),
                impact=rule_data.get("impact", "")
            )
        
        return config
    
    def _validate_configuration(self):
        """Validiere Konfiguration."""
        if not self.config:
            raise ValueError("No configuration loaded")
        
        # Validiere Regeln
        for rule_id, rule in self.config.rules.items():
            # Validiere Wert-Typ
            if rule.value_type == "int" and not isinstance(rule.value, int):
                raise ValueError(f"Rule {rule_id}: value must be integer")
            elif rule.value_type == "float" and not isinstance(rule.value, (int, float)):
                raise ValueError(f"Rule {rule_id}: value must be number")
            elif rule.value_type == "boolean" and not isinstance(rule.value, bool):
                raise ValueError(f"Rule {rule_id}: value must be boolean")
            elif rule.value_type == "list" and not isinstance(rule.value, list):
                raise ValueError(f"Rule {rule_id}: value must be list")
            
            # Validiere Bereiche
            if rule.min_value is not None and isinstance(rule.value, (int, float)):
                if rule.value < rule.min_value:
                    raise ValueError(f"Rule {rule_id}: value below minimum")
            
            if rule.max_value is not None and isinstance(rule.value, (int, float)):
                if rule.value > rule.max_value:
                    raise ValueError(f"Rule {rule_id}: value above maximum")
    
    def _save_configuration(self):
        """Speichere Konfiguration."""
        if not self.config:
            return
        
        self.config.last_modified = datetime.utcnow().isoformat()
        
        # Erstelle Verzeichnis falls nötig
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = self.config.to_dict()
        
        try:
            with self.config_path.open('w') as f:
                if self.config_path.suffix.lower() in ['.yml', '.yaml']:
                    yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                else:
                    json.dump(config_dict, f, indent=2)
            
            logger.info(f"Saved policy configuration to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save policy configuration: {e}")
    
    def get_rule_value(self, rule_id: str, default: Any = None) -> Any:
        """Hole Regel-Wert."""
        if not self.config or rule_id not in self.config.rules:
            return default
        
        rule = self.config.rules[rule_id]
        
        # Prüfe Runtime-Override
        if rule_id in self.runtime_overrides:
            if self._can_override_rule(rule):
                return self.runtime_overrides[rule_id]
            else:
                logger.warning(f"Runtime override blocked for rule {rule_id} (secure mode or non-overrideable)")
        
        return rule.value
    
    def set_rule_value(
        self,
        rule_id: str,
        value: Any,
        runtime_override: bool = False
    ) -> bool:
        """Setze Regel-Wert."""
        if not self.config:
            return False
        
        if rule_id not in self.config.rules:
            logger.error(f"Rule {rule_id} not found")
            return False
        
        rule = self.config.rules[rule_id]
        
        # Validiere neuen Wert
        if not self._validate_rule_value(rule, value):
            logger.error(f"Invalid value for rule {rule_id}: {value}")
            return False
        
        if runtime_override:
            # Runtime-Override
            if not self._can_override_rule(rule):
                logger.error(f"Runtime override not allowed for rule {rule_id}")
                return False
            
            self.runtime_overrides[rule_id] = value
            logger.info(f"Set runtime override for rule {rule_id}: {value}")
            return True
        
        else:
            # Permanente Änderung
            rule.value = value
            self._save_configuration()
            logger.info(f"Updated rule {rule_id}: {value}")
            return True
    
    def _can_override_rule(self, rule: PolicyRule) -> bool:
        """Prüfe ob Regel überschrieben werden kann."""
        # Secure-Mode verhindert alle Runtime-Overrides
        if self.secure_mode or self.config.secure_mode_enabled:
            return False
        
        # Regel muss explizit überschreibbar sein
        return rule.can_be_overridden
    
    def _validate_rule_value(self, rule: PolicyRule, value: Any) -> bool:
        """Validiere Regel-Wert."""
        # Typ-Validierung
        if rule.value_type == "int" and not isinstance(value, int):
            return False
        elif rule.value_type == "float" and not isinstance(value, (int, float)):
            return False
        elif rule.value_type == "boolean" and not isinstance(value, bool):
            return False
        elif rule.value_type == "string" and not isinstance(value, str):
            return False
        elif rule.value_type == "list" and not isinstance(value, list):
            return False
        
        # Bereich-Validierung
        if rule.min_value is not None and isinstance(value, (int, float)):
            if value < rule.min_value:
                return False
        
        if rule.max_value is not None and isinstance(value, (int, float)):
            if value > rule.max_value:
                return False
        
        # Allowed-Values-Validierung
        if rule.allowed_values and isinstance(value, str):
            if value not in rule.allowed_values:
                return False
        
        return True
    
    def validate_compliance(
        self,
        metrics: Dict[str, Any],
        component: str = ""
    ) -> List[PolicyViolation]:
        """Validiere Policy-Compliance."""
        violations = []
        
        if not self.config:
            return violations
        
        for rule_id, rule in self.config.rules.items():
            # Hole aktuellen Wert
            current_value = self.get_rule_value(rule_id)
            
            # Prüfe ob Metrik verfügbar ist
            metric_key = self._map_rule_to_metric(rule_id)
            if metric_key not in metrics:
                continue
            
            actual_value = metrics[metric_key]
            violation = self._check_rule_violation(rule, current_value, actual_value)
            
            if violation:
                violation.component = component
                violations.append(violation)
        
        return violations
    
    def _map_rule_to_metric(self, rule_id: str) -> str:
        """Mappe Regel-ID zu Metrik-Key."""
        mapping = {
            "quality.coverage_min": "coverage_percent",
            "quality.score_threshold": "overall_score",
            "security.high_severity_max": "high_severity_findings",
            "security.active_tools_min": "active_tools",
            "llm.token_budget_max": "total_tokens",
            "performance.startup_time_max": "startup_time_seconds"
        }
        
        return mapping.get(rule_id, rule_id.split(".")[-1])
    
    def _check_rule_violation(
        self,
        rule: PolicyRule,
        expected_value: Any,
        actual_value: Any
    ) -> Optional[PolicyViolation]:
        """Prüfe Regel-Verletzung."""
        violation = None
        
        if rule.domain == PolicyDomain.QUALITY:
            if "min" in rule.rule_id and actual_value < expected_value:
                violation = PolicyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    expected_value=f">= {expected_value}",
                    actual_value=actual_value,
                    severity="high",
                    message=f"{rule.name} below threshold: {actual_value} < {expected_value}",
                    suggested_action="Improve code quality or test coverage"
                )
            elif "threshold" in rule.rule_id and actual_value < expected_value:
                violation = PolicyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    expected_value=f">= {expected_value}",
                    actual_value=actual_value,
                    severity="medium",
                    message=f"{rule.name} below threshold: {actual_value} < {expected_value}",
                    suggested_action="Address quality issues identified in reports"
                )
        
        elif rule.domain == PolicyDomain.SECURITY:
            if "max" in rule.rule_id and actual_value > expected_value:
                violation = PolicyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    expected_value=f"<= {expected_value}",
                    actual_value=actual_value,
                    severity="critical",
                    message=f"{rule.name} exceeded: {actual_value} > {expected_value}",
                    suggested_action="Fix security vulnerabilities before deployment"
                )
            elif "min" in rule.rule_id and actual_value < expected_value:
                violation = PolicyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    expected_value=f">= {expected_value}",
                    actual_value=actual_value,
                    severity="high",
                    message=f"{rule.name} not met: {actual_value} < {expected_value}",
                    suggested_action="Ensure security tools are properly configured and running"
                )
        
        elif rule.domain == PolicyDomain.PERFORMANCE:
            if "max" in rule.rule_id and actual_value > expected_value:
                violation = PolicyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    expected_value=f"<= {expected_value}",
                    actual_value=actual_value,
                    severity="medium",
                    message=f"{rule.name} exceeded: {actual_value} > {expected_value}",
                    suggested_action="Optimize performance or adjust performance budget"
                )
        
        # Setze can_continue basierend auf Enforcement-Mode
        if violation:
            violation.can_continue = (
                rule.enforcement_mode == PolicyEnforcementMode.PERMISSIVE or
                violation.severity in ["low", "medium"]
            )
        
        return violation
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """Hole Policy-Zusammenfassung."""
        if not self.config:
            return {}
        
        summary = {
            "version": self.config.version,
            "enforcement_mode": self.config.global_enforcement_mode.value,
            "secure_mode": self.config.secure_mode_enabled,
            "total_rules": len(self.config.rules),
            "rules_by_domain": {},
            "runtime_overrides": len(self.runtime_overrides),
            "overrideable_rules": 0
        }
        
        # Gruppiere Regeln nach Domäne
        for rule in self.config.rules.values():
            domain = rule.domain.value
            if domain not in summary["rules_by_domain"]:
                summary["rules_by_domain"][domain] = 0
            summary["rules_by_domain"][domain] += 1
            
            if rule.can_be_overridden:
                summary["overrideable_rules"] += 1
        
        return summary


# Convenience Functions
def get_global_policy_manager(config_path: Optional[Path] = None) -> PolicyManager:
    """
    Hole globalen Policy-Manager.
    
    Args:
        config_path: Pfad zur Policy-Konfiguration
        
    Returns:
        Policy-Manager-Instanz
    """
    global _global_policy_manager
    
    if not hasattr(get_global_policy_manager, '_global_policy_manager'):
        get_global_policy_manager._global_policy_manager = PolicyManager(config_path)
    
    return get_global_policy_manager._global_policy_manager


def validate_policy_compliance(
    metrics: Dict[str, Any],
    component: str = "",
    config_path: Optional[Path] = None
) -> List[PolicyViolation]:
    """
    Convenience-Funktion für Policy-Compliance-Validierung.
    
    Args:
        metrics: Zu validierende Metriken
        component: Komponente die validiert wird
        config_path: Pfad zur Policy-Konfiguration
        
    Returns:
        Liste von Policy-Verletzungen
    """
    policy_manager = get_global_policy_manager(config_path)
    return policy_manager.validate_compliance(metrics, component)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_policy_governance():
        print("⚖️ Policy Governance Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "governance.yml"
            
            # Erstelle Policy-Manager
            policy_manager = PolicyManager(config_path)
            
            print(f"\n✓ Policy Manager initialized")
            print(f"  Config path: {config_path}")
            print(f"  Secure mode: {policy_manager.secure_mode}")
            print(f"  Total rules: {len(policy_manager.config.rules)}")
            
            # Zeige Policy-Zusammenfassung
            summary = policy_manager.get_policy_summary()
            print(f"\n📋 Policy Summary:")
            print(f"  Version: {summary['version']}")
            print(f"  Enforcement mode: {summary['enforcement_mode']}")
            print(f"  Rules by domain: {summary['rules_by_domain']}")
            print(f"  Overrideable rules: {summary['overrideable_rules']}")
            
            # Teste Rule-Zugriff
            coverage_min = policy_manager.get_rule_value("quality.coverage_min", 0)
            token_budget = policy_manager.get_rule_value("llm.token_budget_max", 100)
            
            print(f"\n🔍 Rule Values:")
            print(f"  Coverage minimum: {coverage_min}%")
            print(f"  Token budget: {token_budget}")
            
            # Teste Policy-Compliance
            test_metrics = {
                "coverage_percent": 25.0,  # Unter Minimum (30)
                "overall_score": 85.0,     # Über Threshold (70)
                "high_severity_findings": 2,  # Über Maximum (0)
                "active_tools": 1,         # Minimum erfüllt (1)
                "total_tokens": 600        # Über Budget (500)
            }
            
            violations = policy_manager.validate_compliance(test_metrics, "test_component")
            
            print(f"\n⚠️ Policy Violations: {len(violations)}")
            for violation in violations:
                print(f"  - {violation.rule_name}: {violation.message}")
                print(f"    Severity: {violation.severity}")
                print(f"    Can continue: {violation.can_continue}")
                print(f"    Suggested action: {violation.suggested_action}")
            
            # Teste Runtime-Override (sollte in Secure-Mode blockiert werden)
            print(f"\n🔒 Testing Runtime Override:")
            
            # Versuche Coverage-Minimum zu senken
            override_success = policy_manager.set_rule_value(
                "quality.coverage_min", 20.0, runtime_override=True
            )
            print(f"  Override coverage minimum: {'SUCCESS' if override_success else 'BLOCKED'}")
            
            # Versuche Quality-Threshold zu ändern (überschreibbar)
            policy_manager.secure_mode = False  # Temporär für Demo
            override_success = policy_manager.set_rule_value(
                "quality.score_threshold", 60.0, runtime_override=True
            )
            print(f"  Override quality threshold: {'SUCCESS' if override_success else 'BLOCKED'}")
            
            # Teste Policy-Änderung
            print(f"\n📝 Testing Policy Changes:")
            
            # Permanente Änderung
            change_success = policy_manager.set_rule_value("test.timeout_minutes", 20)
            print(f"  Change test timeout: {'SUCCESS' if change_success else 'FAILED'}")
            
            # Teste absichtlich provozierte Policy-Verletzung
            print(f"\n🧪 Testing Intentionally Provoked Policy Violation:")
            
            violation_metrics = {
                "coverage_percent": 15.0,  # Deutlich unter Minimum
                "high_severity_findings": 5,  # Viele kritische Findings
                "active_tools": 0          # Keine Security-Tools
            }
            
            provoked_violations = policy_manager.validate_compliance(
                violation_metrics, "provoked_test"
            )
            
            print(f"  Provoked violations: {len(provoked_violations)}")
            for violation in provoked_violations:
                print(f"  ❌ {violation.rule_name}: {violation.severity} severity")
                print(f"     Expected: {violation.expected_value}, Got: {violation.actual_value}")
            
            return len(violations) > 0 and len(provoked_violations) > 0
    
    # Führe Demo aus
    try:
        result = demo_policy_governance()
        print(f"\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\nDemo failed: {e}")
    
    print("\nDemo completed!")
