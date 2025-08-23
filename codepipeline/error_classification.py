"""
Robuste Fehlerklassifikation und Abbruchgründe.

Führt ein standardisiertes Fehlerklassifikationsschema ein (Guard, Diff, 
Sandbox, Build, Test, Security, Deploy) und gibt klare Abbruchgründe 
mit Remediations aus.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging


logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Fehler-Kategorien."""
    GUARD = "guard"
    DIFF = "diff"
    SANDBOX = "sandbox"
    BUILD = "build"
    TEST = "test"
    SECURITY = "security"
    DEPLOY = "deploy"
    POLICY = "policy"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Fehler-Schweregrade."""
    CRITICAL = "critical"  # Sofortiger Abbruch, keine Wiederholung
    HIGH = "high"         # Abbruch, Wiederholung nach Korrektur möglich
    MEDIUM = "medium"     # Warnung, Fortsetzung mit Einschränkungen
    LOW = "low"          # Information, keine Auswirkung
    INFO = "info"        # Nur zur Information


class RemediationType(Enum):
    """Remediation-Typen."""
    MANUAL_FIX = "manual_fix"           # Manuelle Korrektur erforderlich
    AUTO_RETRY = "auto_retry"           # Automatische Wiederholung möglich
    CONFIG_CHANGE = "config_change"     # Konfigurationsänderung nötig
    POLICY_UPDATE = "policy_update"     # Policy-Update erforderlich
    SYSTEM_CHECK = "system_check"       # System-Check nötig
    ESCALATION = "escalation"           # Eskalation an Admin
    ABORT_CLEAN = "abort_clean"         # Sauberer Abbruch ohne Retry


@dataclass
class RemediationAction:
    """Remediation-Aktion."""
    
    action_type: RemediationType
    description: str
    
    # Ausführungsdetails
    automated: bool = False
    estimated_time_minutes: int = 5
    
    # Anweisungen
    instructions: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    
    # Referenzen
    documentation_url: Optional[str] = None
    support_contact: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "action_type": self.action_type.value,
            "description": self.description,
            "automated": self.automated,
            "estimated_time_minutes": self.estimated_time_minutes,
            "instructions": self.instructions,
            "commands": self.commands,
            "documentation_url": self.documentation_url,
            "support_contact": self.support_contact
        }


@dataclass
class ClassifiedError:
    """Klassifizierter Fehler."""
    
    # Fehler-Identifikation
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    
    # Fehler-Details
    title: str
    description: str
    original_exception: Optional[str] = None
    
    # Kontext
    component: str = ""
    operation: str = ""
    timestamp: str = ""
    
    # Technische Details
    stack_trace: Optional[str] = None
    error_code: Optional[str] = None
    
    # Remediation
    remediations: List[RemediationAction] = field(default_factory=list)
    
    # Metadaten
    retry_count: int = 0
    max_retries: int = 0
    can_retry: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "error_id": self.error_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "original_exception": self.original_exception,
            "component": self.component,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "stack_trace": self.stack_trace,
            "error_code": self.error_code,
            "remediations": [r.to_dict() for r in self.remediations],
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "can_retry": self.can_retry
        }


class ErrorClassifier:
    """Fehler-Klassifizierer."""
    
    def __init__(self):
        self.classification_rules = self._load_classification_rules()
        self.remediation_templates = self._load_remediation_templates()
    
    def classify_error(
        self,
        exception: Exception,
        component: str = "",
        operation: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> ClassifiedError:
        """Klassifiziere Fehler."""
        logger.debug(f"Classifying error: {type(exception).__name__} in {component}")
        
        # Generiere Fehler-ID
        error_id = f"ERR_{component.upper()}_{int(datetime.utcnow().timestamp())}"
        
        # Bestimme Kategorie
        category = self._determine_category(exception, component, operation)
        
        # Bestimme Schweregrad
        severity = self._determine_severity(exception, category, context)
        
        # Erstelle Basis-Fehler
        classified_error = ClassifiedError(
            error_id=error_id,
            category=category,
            severity=severity,
            title=self._generate_title(exception, category),
            description=self._generate_description(exception, category),
            original_exception=str(exception),
            component=component,
            operation=operation,
            timestamp=datetime.utcnow().isoformat(),
            stack_trace=self._extract_stack_trace(exception)
        )
        
        # Füge Remediations hinzu
        classified_error.remediations = self._generate_remediations(
            exception, category, severity, context
        )
        
        # Setze Retry-Informationen
        classified_error.can_retry = self._can_retry(exception, category, severity)
        classified_error.max_retries = self._get_max_retries(category, severity)
        
        logger.info(f"Classified error {error_id}: {category.value}/{severity.value}")
        return classified_error
    
    def _determine_category(
        self,
        exception: Exception,
        component: str,
        operation: str
    ) -> ErrorCategory:
        """Bestimme Fehler-Kategorie."""
        exception_name = type(exception).__name__.lower()
        exception_message = str(exception).lower()
        component_lower = component.lower()
        operation_lower = operation.lower()
        
        # Guard-Fehler
        if any(term in exception_message for term in ["guard", "blocked", "injection", "unsafe"]):
            return ErrorCategory.GUARD
        if "guard" in component_lower:
            return ErrorCategory.GUARD
        
        # Diff-Fehler
        if any(term in exception_message for term in ["diff", "patch", "unified", "hunk"]):
            return ErrorCategory.DIFF
        if "diff" in component_lower or "patch" in operation_lower:
            return ErrorCategory.DIFF
        
        # Sandbox-Fehler
        if any(term in exception_message for term in ["sandbox", "permission", "access", "write"]):
            return ErrorCategory.SANDBOX
        if "sandbox" in component_lower:
            return ErrorCategory.SANDBOX
        
        # Build-Fehler
        if any(term in exception_message for term in ["build", "compile", "dependency", "import"]):
            return ErrorCategory.BUILD
        if any(term in component_lower for term in ["build", "scaffolder", "container"]):
            return ErrorCategory.BUILD
        
        # Test-Fehler
        if any(term in exception_message for term in ["test", "assertion", "coverage"]):
            return ErrorCategory.TEST
        if any(term in component_lower for term in ["test", "e2e", "pytest"]):
            return ErrorCategory.TEST
        
        # Security-Fehler
        if any(term in exception_message for term in ["security", "vulnerability", "cve", "bandit", "semgrep"]):
            return ErrorCategory.SECURITY
        if "security" in component_lower or "scanner" in component_lower:
            return ErrorCategory.SECURITY
        
        # Deploy-Fehler
        if any(term in exception_message for term in ["deploy", "container", "orchestrat"]):
            return ErrorCategory.DEPLOY
        if any(term in component_lower for term in ["deploy", "bundle", "release"]):
            return ErrorCategory.DEPLOY
        
        # Policy-Fehler
        if any(term in exception_message for term in ["policy", "threshold", "violation"]):
            return ErrorCategory.POLICY
        if "policy" in component_lower or "scorecard" in component_lower:
            return ErrorCategory.POLICY
        
        # System-Fehler
        if any(term in exception_name for term in ["system", "os", "file", "network"]):
            return ErrorCategory.SYSTEM
        
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(
        self,
        exception: Exception,
        category: ErrorCategory,
        context: Optional[Dict[str, Any]]
    ) -> ErrorSeverity:
        """Bestimme Fehler-Schweregrad."""
        exception_name = type(exception).__name__.lower()
        exception_message = str(exception).lower()
        
        # Kritische Fehler
        if any(term in exception_message for term in ["critical", "fatal", "corrupted"]):
            return ErrorSeverity.CRITICAL
        
        if category == ErrorCategory.GUARD and "blocked" in exception_message:
            return ErrorSeverity.CRITICAL
        
        if category == ErrorCategory.SECURITY and any(term in exception_message for term in ["high", "critical"]):
            return ErrorSeverity.HIGH
        
        # Hohe Schweregrade
        if any(term in exception_name for term in ["runtime", "value", "type"]):
            return ErrorSeverity.HIGH
        
        if category in [ErrorCategory.BUILD, ErrorCategory.DEPLOY]:
            return ErrorSeverity.HIGH
        
        # Mittlere Schweregrade
        if category in [ErrorCategory.TEST, ErrorCategory.DIFF]:
            return ErrorSeverity.MEDIUM
        
        # Niedrige Schweregrade
        if category in [ErrorCategory.POLICY] and "warning" in exception_message:
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    def _generate_title(self, exception: Exception, category: ErrorCategory) -> str:
        """Generiere Fehler-Titel."""
        exception_name = type(exception).__name__
        
        titles = {
            ErrorCategory.GUARD: f"Prompt Guard Violation: {exception_name}",
            ErrorCategory.DIFF: f"Diff Generation/Application Failed: {exception_name}",
            ErrorCategory.SANDBOX: f"Sandbox Security Violation: {exception_name}",
            ErrorCategory.BUILD: f"Build Process Failed: {exception_name}",
            ErrorCategory.TEST: f"Test Execution Failed: {exception_name}",
            ErrorCategory.SECURITY: f"Security Scan Failed: {exception_name}",
            ErrorCategory.DEPLOY: f"Deployment Failed: {exception_name}",
            ErrorCategory.POLICY: f"Policy Violation: {exception_name}",
            ErrorCategory.SYSTEM: f"System Error: {exception_name}",
            ErrorCategory.UNKNOWN: f"Unclassified Error: {exception_name}"
        }
        
        return titles.get(category, f"Error: {exception_name}")
    
    def _generate_description(self, exception: Exception, category: ErrorCategory) -> str:
        """Generiere Fehler-Beschreibung."""
        base_message = str(exception)
        
        descriptions = {
            ErrorCategory.GUARD: f"The prompt guard detected unsafe content and blocked execution. Details: {base_message}",
            ErrorCategory.DIFF: f"Failed to generate or apply unified diff. This may indicate malformed patches or file conflicts. Details: {base_message}",
            ErrorCategory.SANDBOX: f"Sandbox security policy violation detected. The operation attempted unauthorized file system access. Details: {base_message}",
            ErrorCategory.BUILD: f"The build process encountered an error during compilation or packaging. Check dependencies and build configuration. Details: {base_message}",
            ErrorCategory.TEST: f"Test execution failed. This may indicate code quality issues or test environment problems. Details: {base_message}",
            ErrorCategory.SECURITY: f"Security scanning detected issues or the scanner itself failed. Review security policies and tool configuration. Details: {base_message}",
            ErrorCategory.DEPLOY: f"Deployment process failed. Check container configuration, networking, and resource availability. Details: {base_message}",
            ErrorCategory.POLICY: f"Operation violated configured policies or quality gates. Review policy settings and compliance requirements. Details: {base_message}",
            ErrorCategory.SYSTEM: f"System-level error occurred. Check system resources, permissions, and environment configuration. Details: {base_message}",
            ErrorCategory.UNKNOWN: f"An unclassified error occurred. Manual investigation required. Details: {base_message}"
        }
        
        return descriptions.get(category, base_message)
    
    def _generate_remediations(
        self,
        exception: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        context: Optional[Dict[str, Any]]
    ) -> List[RemediationAction]:
        """Generiere Remediation-Aktionen."""
        remediations = []
        
        # Kategorie-spezifische Remediations
        if category == ErrorCategory.GUARD:
            remediations.extend([
                RemediationAction(
                    action_type=RemediationType.MANUAL_FIX,
                    description="Review and modify the input prompt to remove unsafe content",
                    instructions=[
                        "Check the prompt for potential injection attempts",
                        "Remove or rephrase suspicious instructions",
                        "Ensure the prompt follows security guidelines"
                    ]
                ),
                RemediationAction(
                    action_type=RemediationType.CONFIG_CHANGE,
                    description="Adjust guard sensitivity if legitimate content was blocked",
                    instructions=[
                        "Review guard configuration",
                        "Consider updating guard rules",
                        "Test with modified sensitivity settings"
                    ]
                )
            ])
        
        elif category == ErrorCategory.DIFF:
            remediations.extend([
                RemediationAction(
                    action_type=RemediationType.AUTO_RETRY,
                    description="Regenerate diff with different parameters",
                    automated=True,
                    instructions=[
                        "Retry diff generation with adjusted context",
                        "Check for file encoding issues",
                        "Verify target file exists and is writable"
                    ]
                ),
                RemediationAction(
                    action_type=RemediationType.MANUAL_FIX,
                    description="Manually resolve file conflicts",
                    instructions=[
                        "Check target files for conflicts",
                        "Resolve merge conflicts manually",
                        "Ensure proper file permissions"
                    ]
                )
            ])
        
        elif category == ErrorCategory.SANDBOX:
            remediations.extend([
                RemediationAction(
                    action_type=RemediationType.POLICY_UPDATE,
                    description="Update sandbox write permissions if legitimate access was blocked",
                    instructions=[
                        "Review sandbox policy configuration",
                        "Add legitimate paths to allow-list",
                        "Ensure proper path sanitization"
                    ]
                ),
                RemediationAction(
                    action_type=RemediationType.SYSTEM_CHECK,
                    description="Verify sandbox environment integrity",
                    instructions=[
                        "Check sandbox isolation",
                        "Verify file system permissions",
                        "Test sandbox boundaries"
                    ]
                )
            ])
        
        elif category == ErrorCategory.BUILD:
            remediations.extend([
                RemediationAction(
                    action_type=RemediationType.AUTO_RETRY,
                    description="Retry build with dependency resolution",
                    automated=True,
                    estimated_time_minutes=10,
                    instructions=[
                        "Clear build cache",
                        "Reinstall dependencies",
                        "Retry build process"
                    ],
                    commands=[
                        "rm -rf build/ dist/",
                        "pip install --upgrade --force-reinstall -r requirements.txt",
                        "python -m build"
                    ]
                ),
                RemediationAction(
                    action_type=RemediationType.MANUAL_FIX,
                    description="Fix build configuration or dependencies",
                    instructions=[
                        "Check build tool configuration",
                        "Verify dependency versions",
                        "Review build logs for specific errors"
                    ]
                )
            ])
        
        elif category == ErrorCategory.TEST:
            remediations.extend([
                RemediationAction(
                    action_type=RemediationType.AUTO_RETRY,
                    description="Retry tests with clean environment",
                    automated=True,
                    instructions=[
                        "Clean test environment",
                        "Reset test database/fixtures",
                        "Retry test execution"
                    ]
                ),
                RemediationAction(
                    action_type=RemediationType.MANUAL_FIX,
                    description="Fix failing tests or test environment",
                    instructions=[
                        "Review test failure details",
                        "Fix broken test cases",
                        "Update test environment configuration"
                    ]
                )
            ])
        
        elif category == ErrorCategory.SECURITY:
            remediations.extend([
                RemediationAction(
                    action_type=RemediationType.MANUAL_FIX,
                    description="Address security findings",
                    instructions=[
                        "Review security scan results",
                        "Fix identified vulnerabilities",
                        "Update vulnerable dependencies"
                    ]
                ),
                RemediationAction(
                    action_type=RemediationType.CONFIG_CHANGE,
                    description="Adjust security scan configuration",
                    instructions=[
                        "Review security policy settings",
                        "Update scanner configuration",
                        "Add legitimate exceptions if needed"
                    ]
                )
            ])
        
        elif category == ErrorCategory.DEPLOY:
            remediations.extend([
                RemediationAction(
                    action_type=RemediationType.SYSTEM_CHECK,
                    description="Verify deployment environment",
                    instructions=[
                        "Check system resources",
                        "Verify network connectivity",
                        "Ensure proper permissions"
                    ]
                ),
                RemediationAction(
                    action_type=RemediationType.AUTO_RETRY,
                    description="Retry deployment with rollback on failure",
                    automated=True,
                    estimated_time_minutes=15,
                    instructions=[
                        "Prepare rollback strategy",
                        "Retry deployment",
                        "Monitor deployment health"
                    ]
                )
            ])
        
        elif category == ErrorCategory.POLICY:
            remediations.extend([
                RemediationAction(
                    action_type=RemediationType.MANUAL_FIX,
                    description="Address policy violations",
                    instructions=[
                        "Review policy violation details",
                        "Fix code quality issues",
                        "Improve test coverage if needed"
                    ]
                ),
                RemediationAction(
                    action_type=RemediationType.CONFIG_CHANGE,
                    description="Review policy configuration",
                    instructions=[
                        "Check policy thresholds",
                        "Verify policy applicability",
                        "Consider policy adjustments if appropriate"
                    ]
                )
            ])
        
        # Schweregrad-spezifische Remediations
        if severity == ErrorSeverity.CRITICAL:
            remediations.append(
                RemediationAction(
                    action_type=RemediationType.ABORT_CLEAN,
                    description="Clean abort required - no retry possible",
                    instructions=[
                        "Document the critical error",
                        "Notify operations team",
                        "Perform clean shutdown"
                    ]
                )
            )
        
        elif severity == ErrorSeverity.HIGH:
            remediations.append(
                RemediationAction(
                    action_type=RemediationType.ESCALATION,
                    description="Escalate to operations team",
                    support_contact="ops-team@company.com",
                    instructions=[
                        "Gather error context and logs",
                        "Contact operations team",
                        "Provide detailed error information"
                    ]
                )
            )
        
        return remediations
    
    def _can_retry(
        self,
        exception: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity
    ) -> bool:
        """Bestimme ob Retry möglich ist."""
        if severity == ErrorSeverity.CRITICAL:
            return False
        
        if category == ErrorCategory.GUARD:
            return False  # Guard-Fehler sind meist nicht durch Retry lösbar
        
        if category in [ErrorCategory.BUILD, ErrorCategory.TEST, ErrorCategory.DEPLOY]:
            return True  # Diese Kategorien können oft durch Retry gelöst werden
        
        return severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM]
    
    def _get_max_retries(self, category: ErrorCategory, severity: ErrorSeverity) -> int:
        """Hole maximale Retry-Anzahl."""
        if severity == ErrorSeverity.CRITICAL:
            return 0
        
        retry_limits = {
            ErrorCategory.BUILD: 3,
            ErrorCategory.TEST: 2,
            ErrorCategory.DEPLOY: 2,
            ErrorCategory.SECURITY: 1,
            ErrorCategory.DIFF: 2,
            ErrorCategory.SANDBOX: 1,
            ErrorCategory.POLICY: 1
        }
        
        base_limit = retry_limits.get(category, 1)
        
        # Reduziere Retries für höhere Schweregrade
        if severity == ErrorSeverity.HIGH:
            return max(1, base_limit - 1)
        
        return base_limit
    
    def _extract_stack_trace(self, exception: Exception) -> Optional[str]:
        """Extrahiere Stack-Trace."""
        import traceback
        try:
            return traceback.format_exc()
        except Exception:
            return None
    
    def _load_classification_rules(self) -> Dict[str, Any]:
        """Lade Klassifikations-Regeln."""
        # In Produktion: aus Konfigurationsdatei laden
        return {
            "patterns": {
                "guard": ["guard", "blocked", "injection", "unsafe"],
                "diff": ["diff", "patch", "unified", "hunk"],
                "sandbox": ["sandbox", "permission", "access", "write"],
                "build": ["build", "compile", "dependency", "import"],
                "test": ["test", "assertion", "coverage"],
                "security": ["security", "vulnerability", "cve"],
                "deploy": ["deploy", "container", "orchestrat"],
                "policy": ["policy", "threshold", "violation"]
            }
        }
    
    def _load_remediation_templates(self) -> Dict[str, Any]:
        """Lade Remediation-Templates."""
        # In Produktion: aus Konfigurationsdatei laden
        return {
            "auto_retry_categories": ["build", "test", "deploy"],
            "escalation_severities": ["critical", "high"],
            "documentation_base_url": "https://docs.company.com/codepipeline"
        }


class ErrorReporter:
    """Fehler-Reporter."""
    
    def __init__(self, output_directory: Path):
        self.output_directory = output_directory
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.classifier = ErrorClassifier()
    
    def report_error(
        self,
        exception: Exception,
        component: str = "",
        operation: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> ClassifiedError:
        """Melde und klassifiziere Fehler."""
        # Klassifiziere Fehler
        classified_error = self.classifier.classify_error(
            exception, component, operation, context
        )
        
        # Speichere Fehler-Report
        self._save_error_report(classified_error)
        
        # Log Fehler
        self._log_error(classified_error)
        
        return classified_error
    
    def _save_error_report(self, error: ClassifiedError):
        """Speichere Fehler-Report."""
        report_file = self.output_directory / f"error_report_{error.error_id}.json"
        
        with report_file.open('w') as f:
            json.dump(error.to_dict(), f, indent=2)
        
        logger.debug(f"Saved error report: {report_file}")
    
    def _log_error(self, error: ClassifiedError):
        """Logge Fehler."""
        log_level = {
            ErrorSeverity.CRITICAL: logging.CRITICAL,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.INFO: logging.INFO
        }.get(error.severity, logging.ERROR)
        
        logger.log(
            log_level,
            f"[{error.error_id}] {error.title} | "
            f"Category: {error.category.value} | "
            f"Severity: {error.severity.value} | "
            f"Component: {error.component} | "
            f"Remediations: {len(error.remediations)}"
        )
    
    def generate_error_summary(self, error_reports_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Generiere Fehler-Zusammenfassung."""
        if error_reports_dir is None:
            error_reports_dir = self.output_directory
        
        summary = {
            "total_errors": 0,
            "by_category": {},
            "by_severity": {},
            "recent_errors": [],
            "remediation_stats": {}
        }
        
        # Sammle alle Fehler-Reports
        for report_file in error_reports_dir.glob("error_report_*.json"):
            try:
                with report_file.open('r') as f:
                    error_data = json.load(f)
                
                summary["total_errors"] += 1
                
                # Kategorie-Statistiken
                category = error_data["category"]
                summary["by_category"][category] = summary["by_category"].get(category, 0) + 1
                
                # Schweregrad-Statistiken
                severity = error_data["severity"]
                summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
                
                # Aktuelle Fehler
                if len(summary["recent_errors"]) < 10:
                    summary["recent_errors"].append({
                        "error_id": error_data["error_id"],
                        "title": error_data["title"],
                        "category": category,
                        "severity": severity,
                        "timestamp": error_data["timestamp"]
                    })
                
                # Remediation-Statistiken
                for remediation in error_data.get("remediations", []):
                    action_type = remediation["action_type"]
                    summary["remediation_stats"][action_type] = summary["remediation_stats"].get(action_type, 0) + 1
                
            except Exception as e:
                logger.warning(f"Failed to process error report {report_file}: {e}")
        
        # Sortiere aktuelle Fehler nach Zeitstempel
        summary["recent_errors"].sort(key=lambda x: x["timestamp"], reverse=True)
        
        return summary


# Convenience Functions
def classify_and_report_error(
    exception: Exception,
    component: str = "",
    operation: str = "",
    context: Optional[Dict[str, Any]] = None,
    output_directory: Optional[Path] = None
) -> ClassifiedError:
    """
    Convenience-Funktion für Fehler-Klassifikation und -Reporting.
    
    Args:
        exception: Die zu klassifizierende Exception
        component: Komponente in der der Fehler auftrat
        operation: Operation die den Fehler verursachte
        context: Zusätzlicher Kontext
        output_directory: Ausgabe-Verzeichnis für Reports
        
    Returns:
        Klassifizierter Fehler
    """
    if output_directory is None:
        output_directory = Path.cwd() / "reports" / "errors"
    
    reporter = ErrorReporter(output_directory)
    return reporter.report_error(exception, component, operation, context)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_error_classification():
        print("🔍 Error Classification Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle verschiedene Test-Fehler
            test_errors = [
                (ValueError("Prompt contains unsafe injection attempt"), "guard", "validate_prompt"),
                (FileNotFoundError("Target file not found for diff application"), "diff", "apply_patch"),
                (PermissionError("Write access denied to /restricted/path"), "sandbox", "write_file"),
                (ImportError("No module named 'missing_dependency'"), "build", "install_dependencies"),
                (AssertionError("Test failed: expected 5, got 3"), "test", "run_tests"),
                (RuntimeError("Security scan detected high severity vulnerability"), "security", "scan_code"),
                (ConnectionError("Failed to connect to deployment target"), "deploy", "deploy_container")
            ]
            
            reporter = ErrorReporter(temp_path / "error_reports")
            classified_errors = []
            
            print(f"\nClassifying {len(test_errors)} test errors:")
            
            for exception, component, operation in test_errors:
                classified_error = reporter.report_error(exception, component, operation)
                classified_errors.append(classified_error)
                
                print(f"\n✓ Error ID: {classified_error.error_id}")
                print(f"  Category: {classified_error.category.value}")
                print(f"  Severity: {classified_error.severity.value}")
                print(f"  Title: {classified_error.title}")
                print(f"  Can Retry: {classified_error.can_retry}")
                print(f"  Max Retries: {classified_error.max_retries}")
                print(f"  Remediations: {len(classified_error.remediations)}")
                
                # Zeige erste Remediation
                if classified_error.remediations:
                    first_remediation = classified_error.remediations[0]
                    print(f"  First Remediation: {first_remediation.action_type.value}")
                    print(f"    Description: {first_remediation.description}")
                    if first_remediation.instructions:
                        print(f"    Instructions: {first_remediation.instructions[0]}")
            
            # Generiere Zusammenfassung
            summary = reporter.generate_error_summary()
            
            print(f"\n📊 Error Summary:")
            print(f"  Total Errors: {summary['total_errors']}")
            print(f"  Categories: {list(summary['by_category'].keys())}")
            print(f"  Severities: {list(summary['by_severity'].keys())}")
            print(f"  Recent Errors: {len(summary['recent_errors'])}")
            print(f"  Remediation Types: {len(summary['remediation_stats'])}")
            
            # Teste absichtlich provozierten Fehler
            print(f"\n🧪 Testing intentionally provoked error:")
            
            try:
                raise RuntimeError("Guard blocked: Prompt contains 'rm -rf /' command injection")
            except Exception as e:
                provoked_error = reporter.report_error(e, "guard", "validate_prompt")
                
                print(f"✓ Provoked Error Classification:")
                print(f"  Category: {provoked_error.category.value}")
                print(f"  Severity: {provoked_error.severity.value}")
                print(f"  Title: {provoked_error.title}")
                print(f"  Remediation Actions: {len(provoked_error.remediations)}")
                
                if provoked_error.remediations:
                    remediation = provoked_error.remediations[0]
                    print(f"  Recommended Action: {remediation.action_type.value}")
                    print(f"  Instructions: {remediation.instructions[0] if remediation.instructions else 'None'}")
            
            return len(classified_errors) == len(test_errors) and summary['total_errors'] > 0
    
    # Führe Demo aus
    try:
        result = demo_error_classification()
        print(f"\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\nDemo failed: {e}")
    
    print("\nDemo completed!")
