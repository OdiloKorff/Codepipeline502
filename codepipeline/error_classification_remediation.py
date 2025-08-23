"""
Error Classification und Remediation für handlungsorientierte Fehler.

Implementiert:
- Standardisierte Klassen: guard, diff, sandbox, build, test, security, sbom, deploy
- Zu jedem Fail einen kurzen remediation-hinweis ausgeben
- Simulierter Fehler wird korrekt klassifiziert mit klarer Handlungsempfehlung
"""

from __future__ import annotations

import re
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
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
    SBOM = "sbom"
    DEPLOY = "deploy"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Fehler-Schweregrade."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RemediationAction(Enum):
    """Remediation-Aktionen."""
    RETRY = "retry"
    RECONFIGURE = "reconfigure"
    UPDATE_DEPENDENCIES = "update_dependencies"
    FIX_CODE = "fix_code"
    ADJUST_PERMISSIONS = "adjust_permissions"
    CHECK_ENVIRONMENT = "check_environment"
    CONTACT_ADMIN = "contact_admin"
    ESCALATE = "escalate"


@dataclass
class RemediationStep:
    """Remediation-Schritt."""
    
    action: RemediationAction
    description: str
    command: str = ""
    estimated_time: str = "5 minutes"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "action": self.action.value,
            "description": self.description,
            "command": self.command,
            "estimated_time": self.estimated_time
        }


@dataclass
class ClassifiedError:
    """Klassifizierter Fehler."""
    
    # Basis-Info
    category: ErrorCategory
    severity: ErrorSeverity
    title: str
    message: str
    
    # Details
    original_exception: str = ""
    stack_trace: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Remediation
    remediation_steps: List[RemediationStep] = field(default_factory=list)
    quick_fix: str = ""
    
    # Metadaten
    error_id: str = ""
    timestamp: str = ""
    component: str = "unknown"
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        
        if not self.error_id:
            self.error_id = self._generate_error_id()
    
    def _generate_error_id(self) -> str:
        """Generiere Error-ID."""
        import hashlib
        
        content = f"{self.category.value}:{self.title}:{self.timestamp}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]
    
    def get_remediation_summary(self) -> str:
        """Hole Remediation-Zusammenfassung."""
        
        if self.quick_fix:
            return self.quick_fix
        
        if self.remediation_steps:
            first_step = self.remediation_steps[0]
            return f"{first_step.action.value.replace('_', ' ').title()}: {first_step.description}"
        
        return "Check logs and documentation for resolution steps"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "error_id": self.error_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "original_exception": self.original_exception,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "remediation_steps": [step.to_dict() for step in self.remediation_steps],
            "quick_fix": self.quick_fix,
            "remediation_summary": self.get_remediation_summary(),
            "timestamp": self.timestamp,
            "component": self.component
        }


class ErrorPatternMatcher:
    """Error Pattern Matcher für Kategorisierung."""
    
    def __init__(self):
        # Definiere Error-Patterns für jede Kategorie
        self.patterns = {
            ErrorCategory.GUARD: [
                (r"prompt.*injection", "Prompt injection attempt detected"),
                (r"guard.*violation", "Guard rule violation"),
                (r"unsafe.*pattern", "Unsafe pattern in input"),
                (r"blocked.*content", "Content blocked by guard"),
                (r"threat.*detected", "Security threat detected in input")
            ],
            
            ErrorCategory.DIFF: [
                (r"patch.*failed", "Patch application failed"),
                (r"unified.*diff", "Unified diff processing error"),
                (r"hunk.*mismatch", "Diff hunk mismatch"),
                (r"file.*not.*found.*patch", "Target file not found for patch"),
                (r"merge.*conflict", "Merge conflict in diff")
            ],
            
            ErrorCategory.SANDBOX: [
                (r"permission.*denied", "Permission denied in sandbox"),
                (r"sandbox.*violation", "Sandbox security violation"),
                (r"resource.*limit", "Resource limit exceeded"),
                (r"network.*blocked", "Network access blocked"),
                (r"timeout.*sandbox", "Sandbox execution timeout")
            ],
            
            ErrorCategory.BUILD: [
                (r"compilation.*error", "Code compilation failed"),
                (r"dependency.*not.*found", "Missing dependency"),
                (r"build.*failed", "Build process failed"),
                (r"syntax.*error", "Syntax error in code"),
                (r"import.*error", "Import error during build")
            ],
            
            ErrorCategory.TEST: [
                (r"test.*failed", "Test execution failed"),
                (r"assertion.*error", "Test assertion failed"),
                (r"coverage.*below", "Test coverage below threshold"),
                (r"pytest.*error", "Pytest execution error"),
                (r"unittest.*failed", "Unit test failed")
            ],
            
            ErrorCategory.SECURITY: [
                (r"vulnerability.*found", "Security vulnerability detected"),
                (r"bandit.*error", "Bandit security scan failed"),
                (r"semgrep.*finding", "Semgrep security finding"),
                (r"secret.*detected", "Secret detected in code"),
                (r"cve.*found", "CVE vulnerability found")
            ],
            
            ErrorCategory.SBOM: [
                (r"sbom.*generation.*failed", "SBOM generation failed"),
                (r"license.*violation", "License policy violation"),
                (r"dependency.*scan.*error", "Dependency scan error"),
                (r"cyclonedx.*error", "CycloneDX SBOM error"),
                (r"license.*check.*failed", "License check failed")
            ],
            
            ErrorCategory.DEPLOY: [
                (r"deployment.*failed", "Deployment failed"),
                (r"container.*error", "Container deployment error"),
                (r"kubernetes.*error", "Kubernetes deployment error"),
                (r"rollback.*failed", "Rollback failed"),
                (r"health.*check.*failed", "Health check failed during deployment")
            ]
        }
    
    def classify_error(self, error_message: str, exception_type: str = "") -> Tuple[ErrorCategory, str]:
        """Klassifiziere Fehler basierend auf Message."""
        
        error_text = f"{error_message} {exception_type}".lower()
        
        for category, patterns in self.patterns.items():
            for pattern, description in patterns:
                if re.search(pattern, error_text, re.IGNORECASE):
                    return category, description
        
        return ErrorCategory.UNKNOWN, "Unknown error type"


class RemediationGenerator:
    """Remediation Generator für verschiedene Fehler-Kategorien."""
    
    def __init__(self):
        # Definiere Standard-Remediations für jede Kategorie
        self.remediations = {
            ErrorCategory.GUARD: [
                RemediationStep(
                    action=RemediationAction.FIX_CODE,
                    description="Review and sanitize input prompt",
                    command="Review prompt for unsafe patterns and remove them",
                    estimated_time="10 minutes"
                ),
                RemediationStep(
                    action=RemediationAction.RECONFIGURE,
                    description="Adjust guard rules if false positive",
                    command="Update guard configuration in policies/",
                    estimated_time="15 minutes"
                )
            ],
            
            ErrorCategory.DIFF: [
                RemediationStep(
                    action=RemediationAction.RETRY,
                    description="Regenerate diff with correct base",
                    command="Ensure target file exists and base version matches",
                    estimated_time="5 minutes"
                ),
                RemediationStep(
                    action=RemediationAction.FIX_CODE,
                    description="Manually resolve merge conflicts",
                    command="Review conflicting hunks and apply changes manually",
                    estimated_time="20 minutes"
                )
            ],
            
            ErrorCategory.SANDBOX: [
                RemediationStep(
                    action=RemediationAction.ADJUST_PERMISSIONS,
                    description="Check sandbox permissions and limits",
                    command="Review sandbox configuration and resource limits",
                    estimated_time="10 minutes"
                ),
                RemediationStep(
                    action=RemediationAction.CHECK_ENVIRONMENT,
                    description="Verify sandbox environment setup",
                    command="Check Docker/container runtime status",
                    estimated_time="15 minutes"
                )
            ],
            
            ErrorCategory.BUILD: [
                RemediationStep(
                    action=RemediationAction.UPDATE_DEPENDENCIES,
                    description="Install missing dependencies",
                    command="pip install -r requirements.txt",
                    estimated_time="5 minutes"
                ),
                RemediationStep(
                    action=RemediationAction.FIX_CODE,
                    description="Fix syntax or import errors",
                    command="Review error message and fix code issues",
                    estimated_time="15 minutes"
                )
            ],
            
            ErrorCategory.TEST: [
                RemediationStep(
                    action=RemediationAction.FIX_CODE,
                    description="Fix failing tests or code",
                    command="Review test failures and fix implementation",
                    estimated_time="30 minutes"
                ),
                RemediationStep(
                    action=RemediationAction.RECONFIGURE,
                    description="Adjust test configuration or thresholds",
                    command="Update pytest.ini or coverage thresholds",
                    estimated_time="10 minutes"
                )
            ],
            
            ErrorCategory.SECURITY: [
                RemediationStep(
                    action=RemediationAction.FIX_CODE,
                    description="Fix security vulnerabilities in code",
                    command="Review security findings and implement fixes",
                    estimated_time="45 minutes"
                ),
                RemediationStep(
                    action=RemediationAction.UPDATE_DEPENDENCIES,
                    description="Update vulnerable dependencies",
                    command="pip install --upgrade <vulnerable-package>",
                    estimated_time="10 minutes"
                )
            ],
            
            ErrorCategory.SBOM: [
                RemediationStep(
                    action=RemediationAction.RECONFIGURE,
                    description="Review license policies",
                    command="Update license allowlist in policies/QUALITY.yml",
                    estimated_time="15 minutes"
                ),
                RemediationStep(
                    action=RemediationAction.UPDATE_DEPENDENCIES,
                    description="Replace problematic dependencies",
                    command="Find alternative packages with compatible licenses",
                    estimated_time="60 minutes"
                )
            ],
            
            ErrorCategory.DEPLOY: [
                RemediationStep(
                    action=RemediationAction.CHECK_ENVIRONMENT,
                    description="Verify deployment environment",
                    command="Check cluster status and resource availability",
                    estimated_time="10 minutes"
                ),
                RemediationStep(
                    action=RemediationAction.RETRY,
                    description="Retry deployment with rollback",
                    command="kubectl rollout restart deployment/<name>",
                    estimated_time="5 minutes"
                )
            ]
        }
        
        # Quick-Fix-Messages
        self.quick_fixes = {
            ErrorCategory.GUARD: "Review prompt for unsafe patterns and sanitize input",
            ErrorCategory.DIFF: "Check file paths and regenerate diff with correct base",
            ErrorCategory.SANDBOX: "Verify sandbox permissions and resource limits",
            ErrorCategory.BUILD: "Install missing dependencies: pip install -r requirements.txt",
            ErrorCategory.TEST: "Run tests locally and fix failing assertions",
            ErrorCategory.SECURITY: "Review security scan results and fix vulnerabilities",
            ErrorCategory.SBOM: "Check license policies and update allowlist if needed",
            ErrorCategory.DEPLOY: "Verify deployment environment and retry with rollback"
        }
    
    def generate_remediation(self, category: ErrorCategory, context: Dict[str, Any] = None) -> Tuple[List[RemediationStep], str]:
        """Generiere Remediation für Kategorie."""
        
        if context is None:
            context = {}
        
        # Hole Standard-Remediations
        steps = self.remediations.get(category, [])
        quick_fix = self.quick_fixes.get(category, "Check logs and documentation")
        
        # Passe Remediations an Kontext an
        if context:
            steps = self._customize_remediation(steps, context)
        
        return steps, quick_fix
    
    def _customize_remediation(self, steps: List[RemediationStep], context: Dict[str, Any]) -> List[RemediationStep]:
        """Passe Remediation an Kontext an."""
        
        customized_steps = []
        
        for step in steps:
            # Kopiere Schritt
            custom_step = RemediationStep(
                action=step.action,
                description=step.description,
                command=step.command,
                estimated_time=step.estimated_time
            )
            
            # Passe Command an falls spezifische Info verfügbar
            if "missing_package" in context and step.action == RemediationAction.UPDATE_DEPENDENCIES:
                package = context["missing_package"]
                custom_step.command = f"pip install {package}"
            
            elif "test_file" in context and step.action == RemediationAction.FIX_CODE:
                test_file = context["test_file"]
                custom_step.command = f"Review and fix {test_file}"
            
            customized_steps.append(custom_step)
        
        return customized_steps


class ErrorClassificationSystem:
    """Error Classification System."""
    
    def __init__(self):
        self.pattern_matcher = ErrorPatternMatcher()
        self.remediation_generator = RemediationGenerator()
        self.classified_errors: List[ClassifiedError] = []
    
    def classify_and_remediate(
        self,
        error_message: str,
        exception: Exception = None,
        context: Dict[str, Any] = None,
        component: str = "unknown"
    ) -> ClassifiedError:
        """Klassifiziere Fehler und generiere Remediation."""
        
        if context is None:
            context = {}
        
        # Extrahiere Exception-Info
        exception_type = ""
        stack_trace = ""
        original_exception = ""
        
        if exception:
            exception_type = type(exception).__name__
            original_exception = str(exception)
            stack_trace = traceback.format_exc()
        
        # Klassifiziere Fehler
        category, pattern_description = self.pattern_matcher.classify_error(
            error_message, 
            exception_type
        )
        
        # Bestimme Severity basierend auf Kategorie
        severity = self._determine_severity(category, error_message)
        
        # Generiere Remediation
        remediation_steps, quick_fix = self.remediation_generator.generate_remediation(
            category, 
            context
        )
        
        # Erstelle klassifizierten Fehler
        classified_error = ClassifiedError(
            category=category,
            severity=severity,
            title=pattern_description if pattern_description != "Unknown error type" else error_message[:50],
            message=error_message,
            original_exception=original_exception,
            stack_trace=stack_trace,
            context=context,
            remediation_steps=remediation_steps,
            quick_fix=quick_fix,
            component=component
        )
        
        # Speichere klassifizierten Fehler
        self.classified_errors.append(classified_error)
        
        logger.error(f"Classified error [{classified_error.error_id}] {category.value}: {error_message}")
        logger.info(f"Remediation: {classified_error.get_remediation_summary()}")
        
        return classified_error
    
    def _determine_severity(self, category: ErrorCategory, message: str) -> ErrorSeverity:
        """Bestimme Severity basierend auf Kategorie und Message."""
        
        message_lower = message.lower()
        
        # Critical Keywords
        if any(keyword in message_lower for keyword in ["critical", "fatal", "crash", "security breach"]):
            return ErrorSeverity.CRITICAL
        
        # High Keywords
        if any(keyword in message_lower for keyword in ["failed", "error", "violation", "vulnerability"]):
            return ErrorSeverity.HIGH
        
        # Kategorie-basierte Severity
        category_severities = {
            ErrorCategory.SECURITY: ErrorSeverity.HIGH,
            ErrorCategory.GUARD: ErrorSeverity.HIGH,
            ErrorCategory.DEPLOY: ErrorSeverity.HIGH,
            ErrorCategory.BUILD: ErrorSeverity.MEDIUM,
            ErrorCategory.TEST: ErrorSeverity.MEDIUM,
            ErrorCategory.DIFF: ErrorSeverity.MEDIUM,
            ErrorCategory.SANDBOX: ErrorSeverity.MEDIUM,
            ErrorCategory.SBOM: ErrorSeverity.LOW
        }
        
        return category_severities.get(category, ErrorSeverity.MEDIUM)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Hole Fehler-Statistiken."""
        
        total_errors = len(self.classified_errors)
        
        if total_errors == 0:
            return {"total_errors": 0}
        
        # Statistiken nach Kategorie
        category_counts = {}
        for error in self.classified_errors:
            category = error.category.value
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Statistiken nach Severity
        severity_counts = {}
        for error in self.classified_errors:
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Häufigste Remediations
        remediation_actions = {}
        for error in self.classified_errors:
            for step in error.remediation_steps:
                action = step.action.value
                remediation_actions[action] = remediation_actions.get(action, 0) + 1
        
        return {
            "total_errors": total_errors,
            "by_category": category_counts,
            "by_severity": severity_counts,
            "top_remediations": dict(sorted(remediation_actions.items(), key=lambda x: x[1], reverse=True)[:5]),
            "recent_errors": [error.to_dict() for error in self.classified_errors[-5:]]
        }
    
    def simulate_errors_for_demo(self) -> List[ClassifiedError]:
        """Simuliere verschiedene Fehler für Demo."""
        
        simulated_errors = [
            ("Prompt injection attempt detected in user input", ValueError("Unsafe pattern found"), {"input_type": "prompt"}, "guard"),
            ("Patch application failed: hunk mismatch at line 42", RuntimeError("Diff hunk error"), {"file": "main.py"}, "diff"),
            ("Permission denied: sandbox write access blocked", PermissionError("Access denied"), {"operation": "write"}, "sandbox"),
            ("Build failed: missing dependency 'requests'", ImportError("No module named 'requests'"), {"missing_package": "requests"}, "build"),
            ("Test failed: assertion error in test_user_auth", AssertionError("Expected True, got False"), {"test_file": "test_auth.py"}, "test"),
            ("Vulnerability found: SQL injection in login function", SecurityWarning("CVE-2023-1234"), {"cve": "CVE-2023-1234"}, "security"),
            ("SBOM generation failed: license violation for GPL package", LicenseError("GPL not allowed"), {"license": "GPL"}, "sbom"),
            ("Deployment failed: container health check timeout", TimeoutError("Health check failed"), {"container": "app"}, "deploy")
        ]
        
        classified_errors = []
        
        for message, exception, context, component in simulated_errors:
            classified_error = self.classify_and_remediate(message, exception, context, component)
            classified_errors.append(classified_error)
        
        return classified_errors


# Custom Exceptions für Demo
class LicenseError(Exception):
    """License Error."""
    pass


class SecurityWarning(Warning):
    """Security Warning."""
    pass


# Convenience Functions
def classify_error(
    error_message: str,
    exception: Exception = None,
    context: Dict[str, Any] = None,
    component: str = "unknown"
) -> ClassifiedError:
    """
    Klassifiziere einzelnen Fehler.
    
    Args:
        error_message: Fehler-Nachricht
        exception: Exception (optional)
        context: Kontext-Informationen
        component: Komponenten-Name
        
    Returns:
        Klassifizierter Fehler
    """
    
    classifier = ErrorClassificationSystem()
    return classifier.classify_and_remediate(error_message, exception, context, component)


def get_remediation_for_category(category: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Hole Remediation für Kategorie.
    
    Args:
        category: Fehler-Kategorie
        
    Returns:
        (Remediation Steps, Quick Fix)
    """
    
    try:
        error_category = ErrorCategory(category)
    except ValueError:
        error_category = ErrorCategory.UNKNOWN
    
    generator = RemediationGenerator()
    steps, quick_fix = generator.generate_remediation(error_category)
    
    return [step.to_dict() for step in steps], quick_fix


if __name__ == "__main__":
    # Demo
    
    def demo_error_classification_system():
        print("🛠️ Error Classification & Remediation Demo:")
        
        # Test 1: Erstelle Classification System
        print("\\n🚀 Creating error classification system:")
        
        classifier = ErrorClassificationSystem()
        
        print(f"  ✓ Pattern matcher with {len(classifier.pattern_matcher.patterns)} categories")
        print(f"  ✓ Remediation generator with {len(classifier.remediation_generator.remediations)} categories")
        
        # Test 2: Simuliere verschiedene Fehler
        print("\\n🎯 Simulating various error types:")
        
        simulated_errors = classifier.simulate_errors_for_demo()
        
        print(f"  ✓ Simulated {len(simulated_errors)} different error types")
        
        # Zeige erste paar Fehler
        for i, error in enumerate(simulated_errors[:4], 1):
            print(f"    {i}. {error.category.value}: {error.title}")
            print(f"       Quick fix: {error.quick_fix}")
        
        # Test 3: Detaillierte Fehler-Analyse
        print("\\n🔍 Detailed error analysis:")
        
        # Wähle einen Fehler für detaillierte Analyse
        sample_error = simulated_errors[0]  # Guard error
        
        print(f"  ✓ Error ID: {sample_error.error_id}")
        print(f"  ✓ Category: {sample_error.category.value}")
        print(f"  ✓ Severity: {sample_error.severity.value}")
        print(f"  ✓ Component: {sample_error.component}")
        print(f"  ✓ Remediation steps: {len(sample_error.remediation_steps)}")
        
        for i, step in enumerate(sample_error.remediation_steps, 1):
            print(f"    Step {i}: {step.action.value} - {step.description}")
            if step.command:
                print(f"             Command: {step.command}")
        
        # Test 4: Fehler-Statistiken
        print("\\n📊 Error statistics:")
        
        stats = classifier.get_error_statistics()
        
        print(f"  ✓ Total errors: {stats['total_errors']}")
        print(f"  ✓ Categories: {list(stats['by_category'].keys())}")
        print(f"  ✓ Severities: {list(stats['by_severity'].keys())}")
        print(f"  ✓ Top remediations: {list(stats['top_remediations'].keys())[:3]}")
        
        # Test 5: Kategorien-Coverage
        print("\\n🎯 Testing all error categories:")
        
        all_categories = list(ErrorCategory)
        covered_categories = set(error.category for error in simulated_errors)
        
        print(f"  ✓ Total categories: {len(all_categories)}")
        print(f"  ✓ Covered categories: {len(covered_categories)}")
        
        for category in all_categories:
            covered = "✓" if category in covered_categories else "○"
            print(f"    {covered} {category.value}")
        
        # Test 6: Remediation-Generierung
        print("\\n🔧 Testing remediation generation:")
        
        test_categories = ["guard", "build", "security", "deploy"]
        
        for category in test_categories:
            steps, quick_fix = get_remediation_for_category(category)
            
            print(f"  ✓ {category}: {len(steps)} steps")
            print(f"    Quick fix: {quick_fix[:60]}...")
        
        # Test Akzeptanz-Kriterien
        print("\\n🎯 Acceptance criteria:")
        
        # Standardisierte Klassen (alle 8 Kategorien)
        required_categories = {"guard", "diff", "sandbox", "build", "test", "security", "sbom", "deploy"}
        available_categories = set(category.value for category in ErrorCategory if category != ErrorCategory.UNKNOWN)
        
        standardized_classes = required_categories.issubset(available_categories)
        
        # Zu jedem Fail kurzer Remediation-Hinweis
        all_have_remediation = all(
            error.quick_fix or error.remediation_steps 
            for error in simulated_errors
        )
        
        # Simulierter Fehler korrekt klassifiziert
        guard_error = next((e for e in simulated_errors if e.category == ErrorCategory.GUARD), None)
        correct_classification = (guard_error is not None and 
                                "injection" in guard_error.message.lower())
        
        # Klare Handlungsempfehlung
        clear_remediation = (guard_error is not None and 
                           guard_error.quick_fix and
                           len(guard_error.remediation_steps) > 0)
        
        print(f"  ✓ Standardisierte Klassen (guard/diff/sandbox/build/test/security/sbom/deploy): {standardized_classes}")
        print(f"  ✓ Alle Fehler haben Remediation-Hinweise: {all_have_remediation}")
        print(f"  ✓ Simulierter Fehler korrekt klassifiziert: {correct_classification}")
        print(f"  ✓ Klare Handlungsempfehlung vorhanden: {clear_remediation}")
        
        return (standardized_classes and all_have_remediation and 
               correct_classification and clear_remediation)
    
    # Führe Demo aus
    try:
        result = demo_error_classification_system()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
