"""
Secure Policy Governance für keine Laufzeitabsenkung.

Implementiert:
- Zentralisierte Schwellen mit Secure-Mode-Schutz
- Verhindert Absenkungen zur Laufzeit, nur per Konfiguration möglich
- Versuch einer Laufzeitabsenkung führt zu erklärtem Fail
"""

from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging


logger = logging.getLogger(__name__)


class PolicyViolationType(Enum):
    """Policy-Verletzungs-Typen."""
    THRESHOLD_LOWERING = "threshold_lowering"
    SECURE_MODE_BYPASS = "secure_mode_bypass"
    UNAUTHORIZED_OVERRIDE = "unauthorized_override"
    CONFIGURATION_TAMPERING = "configuration_tampering"
    RUNTIME_MANIPULATION = "runtime_manipulation"


class PolicySeverity(Enum):
    """Policy-Schweregrade."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class PolicyThreshold:
    """Policy-Schwellenwert."""
    
    # Identifikation
    name: str
    category: str
    current_value: Union[int, float, str, bool]
    description: str = ""
    
    # Werte
    minimum_value: Optional[Union[int, float]] = None
    maximum_value: Optional[Union[int, float]] = None
    
    # Governance
    secure_mode_protected: bool = True
    runtime_modifiable: bool = False
    config_source: str = "default"
    
    # Metadaten
    last_modified: str = ""
    modified_by: str = "system"
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.last_modified:
            self.last_modified = datetime.utcnow().isoformat()
    
    def is_lowering_attempt(self, new_value: Union[int, float, str, bool]) -> bool:
        """Prüfe ob Versuch einer Absenkung."""
        
        # Nur für numerische Werte prüfbar
        if not isinstance(self.current_value, (int, float)) or not isinstance(new_value, (int, float)):
            return new_value != self.current_value
        
        # Prüfe je nach Kontext (höhere Werte sind normalerweise besser)
        if self.category in ["coverage", "security_score", "quality_score"]:
            return new_value < self.current_value
        elif self.category in ["max_errors", "max_warnings", "timeout"]:
            return new_value > self.current_value
        else:
            # Standard: Absenkung = kleinerer Wert
            return new_value < self.current_value
    
    def validate_new_value(self, new_value: Union[int, float, str, bool]) -> Tuple[bool, str]:
        """Validiere neuen Wert."""
        
        # Typ-Check
        if type(new_value) != type(self.current_value):
            return False, f"Type mismatch: expected {type(self.current_value).__name__}, got {type(new_value).__name__}"
        
        # Min/Max-Check für numerische Werte
        if isinstance(new_value, (int, float)):
            if self.minimum_value is not None and new_value < self.minimum_value:
                return False, f"Value {new_value} below minimum {self.minimum_value}"
            
            if self.maximum_value is not None and new_value > self.maximum_value:
                return False, f"Value {new_value} above maximum {self.maximum_value}"
        
        return True, ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "current_value": self.current_value,
            "minimum_value": self.minimum_value,
            "maximum_value": self.maximum_value,
            "secure_mode_protected": self.secure_mode_protected,
            "runtime_modifiable": self.runtime_modifiable,
            "config_source": self.config_source,
            "last_modified": self.last_modified,
            "modified_by": self.modified_by
        }


@dataclass
class PolicyViolation:
    """Policy-Verletzung."""
    
    # Violation-Info
    violation_type: PolicyViolationType
    severity: PolicySeverity
    threshold_name: str
    
    # Details
    attempted_value: Any
    current_value: Any
    message: str = ""
    
    # Kontext
    caller: str = "unknown"
    stack_trace: str = ""
    
    # Zeitstempel
    timestamp: str = ""
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "threshold_name": self.threshold_name,
            "attempted_value": self.attempted_value,
            "current_value": self.current_value,
            "message": self.message,
            "caller": self.caller,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp
        }


class SecureModeManager:
    """Secure Mode Manager."""
    
    def __init__(self):
        self._secure_mode = self._get_secure_mode_from_env()
        self._locked = False
    
    def _get_secure_mode_from_env(self) -> bool:
        """Hole Secure Mode aus Environment."""
        
        secure_mode_env = os.getenv("SECURE_MODE", "true").lower()
        return secure_mode_env in ["true", "1", "yes", "on"]
    
    def is_secure_mode(self) -> bool:
        """Prüfe ob Secure Mode aktiv."""
        return self._secure_mode
    
    def lock_secure_mode(self):
        """Sperre Secure Mode (verhindert Änderungen)."""
        self._locked = True
        logger.info("Secure mode locked - no runtime changes allowed")
    
    def is_locked(self) -> bool:
        """Prüfe ob Secure Mode gesperrt ist."""
        return self._locked
    
    def attempt_disable(self, caller: str = "unknown") -> bool:
        """Versuche Secure Mode zu deaktivieren."""
        
        if self._locked:
            logger.error(f"Attempt to disable locked secure mode by {caller}")
            return False
        
        if self._secure_mode:
            logger.warning(f"Attempt to disable secure mode by {caller} - BLOCKED")
            return False
        
        return True


class PolicyConfigurationManager:
    """Policy-Konfigurations-Manager."""
    
    def __init__(self, config_file: Path = None):
        if config_file is None:
            config_file = Path.cwd() / "policies" / "secure_policies.json"
        
        self.config_file = config_file
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Lade Konfiguration
        self.thresholds: Dict[str, PolicyThreshold] = {}
        self._load_configuration()
        
        # Berechne Config-Hash für Tamper-Detection
        self._config_hash = self._calculate_config_hash()
    
    def _load_configuration(self):
        """Lade Konfiguration."""
        
        if not self.config_file.exists():
            self._create_default_configuration()
        
        try:
            with self.config_file.open('r') as f:
                config_data = json.load(f)
            
            for threshold_name, threshold_data in config_data.get("thresholds", {}).items():
                threshold = PolicyThreshold(
                    name=threshold_name,
                    category=threshold_data.get("category", "unknown"),
                    description=threshold_data.get("description", ""),
                    current_value=threshold_data.get("current_value"),
                    minimum_value=threshold_data.get("minimum_value"),
                    maximum_value=threshold_data.get("maximum_value"),
                    secure_mode_protected=threshold_data.get("secure_mode_protected", True),
                    runtime_modifiable=threshold_data.get("runtime_modifiable", False),
                    config_source=threshold_data.get("config_source", "file"),
                    last_modified=threshold_data.get("last_modified", ""),
                    modified_by=threshold_data.get("modified_by", "system")
                )
                
                self.thresholds[threshold_name] = threshold
            
            logger.info(f"Loaded {len(self.thresholds)} policy thresholds from {self.config_file}")
        
        except Exception as e:
            logger.error(f"Failed to load policy configuration: {e}")
            self._create_default_configuration()
    
    def _create_default_configuration(self):
        """Erstelle Standard-Konfiguration."""
        
        default_thresholds = {
            "coverage_minimum": PolicyThreshold(
                name="coverage_minimum",
                category="coverage",
                description="Minimum test coverage percentage",
                current_value=30.0,
                minimum_value=10.0,
                maximum_value=100.0,
                secure_mode_protected=True,
                runtime_modifiable=False
            ),
            "security_score_minimum": PolicyThreshold(
                name="security_score_minimum",
                category="security_score",
                description="Minimum security score",
                current_value=70.0,
                minimum_value=50.0,
                maximum_value=100.0,
                secure_mode_protected=True,
                runtime_modifiable=False
            ),
            "quality_score_minimum": PolicyThreshold(
                name="quality_score_minimum",
                category="quality_score",
                description="Minimum quality score",
                current_value=70.0,
                minimum_value=50.0,
                maximum_value=100.0,
                secure_mode_protected=True,
                runtime_modifiable=False
            ),
            "max_critical_issues": PolicyThreshold(
                name="max_critical_issues",
                category="max_errors",
                description="Maximum allowed critical security issues",
                current_value=0,
                minimum_value=0,
                maximum_value=10,
                secure_mode_protected=True,
                runtime_modifiable=False
            ),
            "token_budget_limit": PolicyThreshold(
                name="token_budget_limit",
                category="budget",
                description="Maximum token budget per run",
                current_value=1000,
                minimum_value=100,
                maximum_value=10000,
                secure_mode_protected=False,
                runtime_modifiable=True
            )
        }
        
        for name, threshold in default_thresholds.items():
            self.thresholds[name] = threshold
        
        self._save_configuration()
    
    def _save_configuration(self):
        """Speichere Konfiguration."""
        
        try:
            config_data = {
                "thresholds": {
                    name: threshold.to_dict()
                    for name, threshold in self.thresholds.items()
                },
                "metadata": {
                    "created_at": datetime.utcnow().isoformat(),
                    "version": "1.0"
                }
            }
            
            with self.config_file.open('w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved policy configuration to {self.config_file}")
        
        except Exception as e:
            logger.error(f"Failed to save policy configuration: {e}")
    
    def _calculate_config_hash(self) -> str:
        """Berechne Konfigurations-Hash."""
        
        config_content = json.dumps(
            {name: threshold.to_dict() for name, threshold in self.thresholds.items()},
            sort_keys=True
        )
        
        return hashlib.sha256(config_content.encode('utf-8')).hexdigest()
    
    def verify_config_integrity(self) -> bool:
        """Verifiziere Konfigurations-Integrität."""
        
        current_hash = self._calculate_config_hash()
        
        if current_hash != self._config_hash:
            logger.error("Policy configuration tampering detected!")
            return False
        
        return True
    
    def get_threshold(self, name: str) -> Optional[PolicyThreshold]:
        """Hole Schwellenwert."""
        return self.thresholds.get(name)
    
    def list_thresholds(self, category: str = None) -> List[PolicyThreshold]:
        """Liste Schwellenwerte."""
        
        if category:
            return [t for t in self.thresholds.values() if t.category == category]
        else:
            return list(self.thresholds.values())


class SecurePolicyGovernance:
    """Secure Policy Governance."""
    
    def __init__(self, config_file: Path = None):
        self.config_manager = PolicyConfigurationManager(config_file)
        self.secure_mode = SecureModeManager()
        self.violations: List[PolicyViolation] = []
        
        # Sperre Secure Mode nach Initialisierung
        if self.secure_mode.is_secure_mode():
            self.secure_mode.lock_secure_mode()
    
    def get_threshold_value(self, threshold_name: str) -> Any:
        """Hole Schwellenwert."""
        
        threshold = self.config_manager.get_threshold(threshold_name)
        
        if not threshold:
            logger.warning(f"Unknown threshold: {threshold_name}")
            return None
        
        return threshold.current_value
    
    def attempt_threshold_change(
        self,
        threshold_name: str,
        new_value: Any,
        caller: str = "unknown",
        justification: str = ""
    ) -> Tuple[bool, str]:
        """Versuche Schwellenwert-Änderung."""
        
        threshold = self.config_manager.get_threshold(threshold_name)
        
        if not threshold:
            return False, f"Unknown threshold: {threshold_name}"
        
        # Prüfe Secure Mode Protection
        if threshold.secure_mode_protected and self.secure_mode.is_secure_mode():
            violation = PolicyViolation(
                violation_type=PolicyViolationType.SECURE_MODE_BYPASS,
                severity=PolicySeverity.CRITICAL,
                threshold_name=threshold_name,
                attempted_value=new_value,
                current_value=threshold.current_value,
                message=f"Attempt to modify secure-mode-protected threshold '{threshold_name}' by {caller}",
                caller=caller
            )
            
            self.violations.append(violation)
            
            logger.error(f"BLOCKED: Secure mode prevents modification of {threshold_name}")
            return False, f"Secure mode prevents modification of protected threshold '{threshold_name}'"
        
        # Prüfe Runtime Modifiable
        if not threshold.runtime_modifiable:
            violation = PolicyViolation(
                violation_type=PolicyViolationType.RUNTIME_MANIPULATION,
                severity=PolicySeverity.HIGH,
                threshold_name=threshold_name,
                attempted_value=new_value,
                current_value=threshold.current_value,
                message=f"Attempt to modify non-runtime-modifiable threshold '{threshold_name}' by {caller}",
                caller=caller
            )
            
            self.violations.append(violation)
            
            logger.error(f"BLOCKED: Runtime modification not allowed for {threshold_name}")
            return False, f"Runtime modification not allowed for threshold '{threshold_name}'. Use configuration file."
        
        # Prüfe Absenkungsversuch
        if threshold.is_lowering_attempt(new_value):
            violation = PolicyViolation(
                violation_type=PolicyViolationType.THRESHOLD_LOWERING,
                severity=PolicySeverity.HIGH,
                threshold_name=threshold_name,
                attempted_value=new_value,
                current_value=threshold.current_value,
                message=f"Attempt to lower threshold '{threshold_name}' from {threshold.current_value} to {new_value} by {caller}",
                caller=caller
            )
            
            self.violations.append(violation)
            
            logger.error(f"BLOCKED: Threshold lowering attempt for {threshold_name}: {threshold.current_value} -> {new_value}")
            return False, f"Lowering threshold '{threshold_name}' from {threshold.current_value} to {new_value} is not allowed"
        
        # Validiere neuen Wert
        is_valid, validation_message = threshold.validate_new_value(new_value)
        
        if not is_valid:
            violation = PolicyViolation(
                violation_type=PolicyViolationType.UNAUTHORIZED_OVERRIDE,
                severity=PolicySeverity.MEDIUM,
                threshold_name=threshold_name,
                attempted_value=new_value,
                current_value=threshold.current_value,
                message=f"Invalid value for threshold '{threshold_name}': {validation_message}",
                caller=caller
            )
            
            self.violations.append(violation)
            
            logger.error(f"BLOCKED: Invalid value for {threshold_name}: {validation_message}")
            return False, f"Invalid value for threshold '{threshold_name}': {validation_message}"
        
        # Änderung erlaubt
        threshold.current_value = new_value
        threshold.last_modified = datetime.utcnow().isoformat()
        threshold.modified_by = caller
        
        logger.info(f"Threshold '{threshold_name}' changed to {new_value} by {caller} - {justification}")
        
        return True, f"Threshold '{threshold_name}' successfully updated to {new_value}"
    
    def validate_against_thresholds(self, metrics: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validiere Metriken gegen Schwellenwerte."""
        
        violations = []
        
        for metric_name, metric_value in metrics.items():
            threshold = self.config_manager.get_threshold(metric_name)
            
            if not threshold:
                continue
            
            # Prüfe je nach Kategorie
            if threshold.category in ["coverage", "security_score", "quality_score"]:
                if isinstance(metric_value, (int, float)) and metric_value < threshold.current_value:
                    violations.append(f"{metric_name}: {metric_value} below threshold {threshold.current_value}")
            
            elif threshold.category in ["max_errors", "max_warnings"]:
                if isinstance(metric_value, (int, float)) and metric_value > threshold.current_value:
                    violations.append(f"{metric_name}: {metric_value} exceeds threshold {threshold.current_value}")
        
        return len(violations) == 0, violations
    
    def get_policy_status(self) -> Dict[str, Any]:
        """Hole Policy-Status."""
        
        return {
            "secure_mode_active": self.secure_mode.is_secure_mode(),
            "secure_mode_locked": self.secure_mode.is_locked(),
            "total_thresholds": len(self.config_manager.thresholds),
            "protected_thresholds": len([t for t in self.config_manager.thresholds.values() if t.secure_mode_protected]),
            "runtime_modifiable_thresholds": len([t for t in self.config_manager.thresholds.values() if t.runtime_modifiable]),
            "total_violations": len(self.violations),
            "config_integrity_ok": self.config_manager.verify_config_integrity(),
            "recent_violations": [v.to_dict() for v in self.violations[-5:]]  # Letzte 5
        }
    
    def generate_policy_report(self) -> Dict[str, Any]:
        """Generiere Policy-Report."""
        
        thresholds_by_category = {}
        
        for threshold in self.config_manager.thresholds.values():
            category = threshold.category
            if category not in thresholds_by_category:
                thresholds_by_category[category] = []
            thresholds_by_category[category].append(threshold.to_dict())
        
        violations_by_type = {}
        
        for violation in self.violations:
            vtype = violation.violation_type.value
            if vtype not in violations_by_type:
                violations_by_type[vtype] = []
            violations_by_type[vtype].append(violation.to_dict())
        
        return {
            "policy_status": self.get_policy_status(),
            "thresholds_by_category": thresholds_by_category,
            "violations_by_type": violations_by_type,
            "generated_at": datetime.utcnow().isoformat()
        }


# Convenience Functions
def create_secure_policy_governance(config_file: Path = None) -> SecurePolicyGovernance:
    """
    Erstelle Secure Policy Governance.
    
    Args:
        config_file: Konfigurations-Datei
        
    Returns:
        Secure Policy Governance
    """
    
    return SecurePolicyGovernance(config_file)


def check_threshold_compliance(
    governance: SecurePolicyGovernance,
    metrics: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Prüfe Threshold-Compliance.
    
    Args:
        governance: Policy Governance
        metrics: Metriken
        
    Returns:
        (Compliant, Violations)
    """
    
    return governance.validate_against_thresholds(metrics)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_secure_policy_governance():
        print("🔒 Secure Policy Governance Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test 1: Erstelle Policy Governance
            print("\\n🚀 Creating secure policy governance:")
            
            governance = create_secure_policy_governance(temp_path / "secure_policies.json")
            
            status = governance.get_policy_status()
            
            print(f"  ✓ Secure mode active: {status['secure_mode_active']}")
            print(f"  ✓ Secure mode locked: {status['secure_mode_locked']}")
            print(f"  ✓ Total thresholds: {status['total_thresholds']}")
            print(f"  ✓ Protected thresholds: {status['protected_thresholds']}")
            
            # Test 2: Hole Schwellenwerte
            print("\\n📊 Current thresholds:")
            
            threshold_names = ["coverage_minimum", "security_score_minimum", "max_critical_issues"]
            
            for name in threshold_names:
                value = governance.get_threshold_value(name)
                threshold = governance.config_manager.get_threshold(name)
                
                if threshold:
                    protected = "🔒" if threshold.secure_mode_protected else "🔓"
                    modifiable = "✏️" if threshold.runtime_modifiable else "❌"
                    print(f"  ✓ {name}: {value} {protected} {modifiable}")
            
            # Test 3: Versuche erlaubte Änderung (nicht-geschützter Threshold)
            print("\\n✅ Testing allowed threshold change:")
            
            token_budget_name = "token_budget_limit"
            current_budget = governance.get_threshold_value(token_budget_name)
            new_budget = current_budget + 500  # Erhöhung ist erlaubt
            
            success, message = governance.attempt_threshold_change(
                token_budget_name,
                new_budget,
                caller="test_user",
                justification="Increased budget for complex feature"
            )
            
            print(f"  ✓ Attempt to change {token_budget_name}: {'SUCCESS' if success else 'BLOCKED'}")
            print(f"  ✓ Message: {message}")
            
            # Test 4: Versuche Absenkung (sollte blockiert werden)
            print("\\n❌ Testing threshold lowering (should be blocked):")
            
            coverage_name = "coverage_minimum"
            current_coverage = governance.get_threshold_value(coverage_name)
            lower_coverage = current_coverage - 10  # Absenkung
            
            success, message = governance.attempt_threshold_change(
                coverage_name,
                lower_coverage,
                caller="malicious_user",
                justification="Lower coverage for faster builds"
            )
            
            print(f"  ✓ Attempt to lower {coverage_name}: {'SUCCESS' if success else 'BLOCKED'}")
            print(f"  ✓ Message: {message}")
            
            # Test 5: Versuche Secure-Mode-geschützten Threshold zu ändern
            print("\\n🔒 Testing secure-mode-protected threshold change:")
            
            security_name = "security_score_minimum"
            current_security = governance.get_threshold_value(security_name)
            higher_security = current_security + 5  # Erhöhung, aber geschützt
            
            success, message = governance.attempt_threshold_change(
                security_name,
                higher_security,
                caller="admin_user",
                justification="Increase security requirements"
            )
            
            print(f"  ✓ Attempt to change {security_name}: {'SUCCESS' if success else 'BLOCKED'}")
            print(f"  ✓ Message: {message}")
            
            # Test 6: Validiere Metriken gegen Thresholds
            print("\\n🎯 Testing metrics validation:")
            
            test_metrics = {
                "coverage_minimum": 85.0,  # Über Threshold (30.0)
                "security_score_minimum": 65.0,  # Unter Threshold (70.0)
                "max_critical_issues": 0  # Gleich Threshold (0)
            }
            
            compliant, violations = governance.validate_against_thresholds(test_metrics)
            
            print(f"  ✓ Metrics compliant: {compliant}")
            print(f"  ✓ Violations: {len(violations)}")
            
            for violation in violations:
                print(f"    - {violation}")
            
            # Test 7: Policy-Status und Violations
            print("\\n📋 Policy status and violations:")
            
            final_status = governance.get_policy_status()
            
            print(f"  ✓ Total violations recorded: {final_status['total_violations']}")
            print(f"  ✓ Config integrity OK: {final_status['config_integrity_ok']}")
            
            # Zeige Recent Violations
            for violation in final_status['recent_violations']:
                print(f"    - {violation['violation_type']}: {violation['message'][:60]}...")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Zentralisierte Schwellen
            centralized_thresholds = len(governance.config_manager.thresholds) > 0
            
            # Verhindert Absenkungen im Secure-Mode
            lowering_blocked = not governance.attempt_threshold_change(
                "coverage_minimum",
                20.0,  # Unter aktuellem Wert
                caller="test_lowering"
            )[0]
            
            # Nur per Konfiguration möglich
            config_only_modification = any(
                not t.runtime_modifiable and t.secure_mode_protected
                for t in governance.config_manager.thresholds.values()
            )
            
            # Versuch führt zu erklärtem Fail
            explained_failures = len([
                v for v in governance.violations 
                if v.violation_type in [PolicyViolationType.THRESHOLD_LOWERING, PolicyViolationType.SECURE_MODE_BYPASS]
            ]) > 0
            
            print(f"  ✓ Zentralisierte Schwellen: {centralized_thresholds}")
            print(f"  ✓ Absenkungen im Secure-Mode verhindert: {lowering_blocked}")
            print(f"  ✓ Nur per Konfiguration modifizierbar: {config_only_modification}")
            print(f"  ✓ Laufzeitabsenkung führt zu erklärtem Fail: {explained_failures}")
            
            return (centralized_thresholds and lowering_blocked and 
                   config_only_modification and explained_failures)
    
    # Führe Demo aus
    try:
        result = demo_secure_policy_governance()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
