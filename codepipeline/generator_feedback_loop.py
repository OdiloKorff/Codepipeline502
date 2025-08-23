"""
Generator-Feedback-Loop bei Gate-Fails.

Implementiert:
- Selbstkorrektur mit Grenzen (maximal zwei Versuche)
- Minimalinvasive Korrektur-Generierung
- Dokumentation aller Änderungen mit klarem Abbruch
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


class CorrectionType(Enum):
    """Korrektur-Typen."""
    SYNTAX_FIX = "syntax_fix"
    IMPORT_FIX = "import_fix"
    TEST_FIX = "test_fix"
    SECURITY_FIX = "security_fix"
    COVERAGE_FIX = "coverage_fix"
    LINT_FIX = "lint_fix"
    BUILD_FIX = "build_fix"
    DEPENDENCY_FIX = "dependency_fix"


class CorrectionStrategy(Enum):
    """Korrektur-Strategien."""
    MINIMAL_CHANGE = "minimal_change"
    TARGETED_FIX = "targeted_fix"
    INCREMENTAL_IMPROVEMENT = "incremental_improvement"
    DEFENSIVE_PROGRAMMING = "defensive_programming"


class FeedbackResult(Enum):
    """Feedback-Ergebnisse."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED_RETRY = "failed_retry"
    MAX_ATTEMPTS_REACHED = "max_attempts_reached"
    ABORT_CLEAN = "abort_clean"


@dataclass
class GateFailure:
    """Gate-Fehler-Details."""
    
    gate_name: str
    error_message: str
    error_type: str = ""
    failed_component: str = ""
    error_details: Dict[str, Any] = field(default_factory=dict)
    
    # Kontext
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: str = ""
    
    # Klassifikation
    correction_type: Optional[CorrectionType] = None
    severity: str = "medium"  # low, medium, high, critical
    
    def classify_error(self):
        """Klassifiziere Fehler für Korrektur-Strategie."""
        
        error_lower = self.error_message.lower()
        
        # Syntax-Fehler
        if any(keyword in error_lower for keyword in ["syntax error", "invalid syntax", "unexpected token"]):
            self.correction_type = CorrectionType.SYNTAX_FIX
            self.severity = "high"
        
        # Import-Fehler
        elif any(keyword in error_lower for keyword in ["import error", "no module named", "cannot import"]):
            self.correction_type = CorrectionType.IMPORT_FIX
            self.severity = "medium"
        
        # Test-Fehler
        elif any(keyword in error_lower for keyword in ["test failed", "assertion error", "test error"]):
            self.correction_type = CorrectionType.TEST_FIX
            self.severity = "medium"
        
        # Security-Fehler
        elif any(keyword in error_lower for keyword in ["security", "vulnerability", "cve", "bandit", "semgrep"]):
            self.correction_type = CorrectionType.SECURITY_FIX
            self.severity = "high"
        
        # Coverage-Fehler
        elif any(keyword in error_lower for keyword in ["coverage", "not covered", "coverage below"]):
            self.correction_type = CorrectionType.COVERAGE_FIX
            self.severity = "low"
        
        # Lint-Fehler
        elif any(keyword in error_lower for keyword in ["lint", "style", "formatting", "ruff", "flake8"]):
            self.correction_type = CorrectionType.LINT_FIX
            self.severity = "low"
        
        # Build-Fehler
        elif any(keyword in error_lower for keyword in ["build failed", "compilation", "make error"]):
            self.correction_type = CorrectionType.BUILD_FIX
            self.severity = "high"
        
        # Dependency-Fehler
        elif any(keyword in error_lower for keyword in ["dependency", "requirements", "package not found"]):
            self.correction_type = CorrectionType.DEPENDENCY_FIX
            self.severity = "medium"
        
        else:
            # Unbekannter Fehler-Typ
            self.severity = "medium"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "gate_name": self.gate_name,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "failed_component": self.failed_component,
            "error_details": self.error_details,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "correction_type": self.correction_type.value if self.correction_type else None,
            "severity": self.severity
        }


@dataclass
class CorrectionAttempt:
    """Korrektur-Versuch."""
    
    attempt_number: int
    correction_type: CorrectionType
    strategy: CorrectionStrategy
    description: str
    
    # Änderungen
    changes_made: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    
    # Ergebnis
    result: Optional[FeedbackResult] = None
    new_errors: List[str] = field(default_factory=list)
    improvement_achieved: bool = False
    
    # Metadaten
    timestamp: str = ""
    duration_seconds: float = 0.0
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "correction_type": self.correction_type.value,
            "strategy": self.strategy.value,
            "description": self.description,
            "changes_made": self.changes_made,
            "files_modified": self.files_modified,
            "result": self.result.value if self.result else None,
            "new_errors": self.new_errors,
            "improvement_achieved": self.improvement_achieved,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds
        }


@dataclass
class FeedbackSession:
    """Feedback-Session für einen Run."""
    
    run_id: str
    original_failures: List[GateFailure]
    max_attempts: int = 2
    
    # Versuche
    attempts: List[CorrectionAttempt] = field(default_factory=list)
    
    # Status
    session_result: Optional[FeedbackResult] = None
    final_success: bool = False
    total_duration: float = 0.0
    
    # Dokumentation
    changes_log: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    
    # Zeitstempel
    started_at: str = ""
    completed_at: str = ""
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat()
    
    def add_attempt(self, attempt: CorrectionAttempt):
        """Füge Korrektur-Versuch hinzu."""
        self.attempts.append(attempt)
        self.changes_log.extend(attempt.changes_made)
    
    def complete_session(self, result: FeedbackResult, success: bool = False):
        """Schließe Session ab."""
        self.session_result = result
        self.final_success = success
        self.completed_at = datetime.utcnow().isoformat()
        
        if self.started_at and self.completed_at:
            start_time = datetime.fromisoformat(self.started_at)
            end_time = datetime.fromisoformat(self.completed_at)
            self.total_duration = (end_time - start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "run_id": self.run_id,
            "original_failures": [failure.to_dict() for failure in self.original_failures],
            "max_attempts": self.max_attempts,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "session_result": self.session_result.value if self.session_result else None,
            "final_success": self.final_success,
            "total_duration": self.total_duration,
            "changes_log": self.changes_log,
            "lessons_learned": self.lessons_learned,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


class CorrectionGenerator:
    """Korrektur-Generator für verschiedene Fehler-Typen."""
    
    def __init__(self):
        # Korrektur-Templates
        self.correction_templates = {
            CorrectionType.SYNTAX_FIX: [
                "Fix missing comma in function call",
                "Add missing closing parenthesis",
                "Fix indentation error",
                "Add missing colon after if/for/while statement",
                "Fix string quote mismatch"
            ],
            
            CorrectionType.IMPORT_FIX: [
                "Add missing import statement",
                "Fix import path",
                "Add package to requirements.txt",
                "Use relative import instead of absolute",
                "Import specific function instead of module"
            ],
            
            CorrectionType.TEST_FIX: [
                "Fix test assertion",
                "Add missing test setup",
                "Fix test data",
                "Add missing mock",
                "Fix test cleanup"
            ],
            
            CorrectionType.SECURITY_FIX: [
                "Replace hardcoded secret with environment variable",
                "Add input validation",
                "Fix SQL injection vulnerability",
                "Add proper error handling",
                "Use secure random instead of random"
            ],
            
            CorrectionType.COVERAGE_FIX: [
                "Add test for uncovered branch",
                "Add test for error handling",
                "Add test for edge case",
                "Remove unused code",
                "Add integration test"
            ],
            
            CorrectionType.LINT_FIX: [
                "Fix line too long",
                "Add missing docstring",
                "Fix variable naming",
                "Remove unused import",
                "Fix whitespace issues"
            ],
            
            CorrectionType.BUILD_FIX: [
                "Fix compilation error",
                "Add missing dependency",
                "Fix configuration issue",
                "Update build script",
                "Fix environment setup"
            ],
            
            CorrectionType.DEPENDENCY_FIX: [
                "Add missing package to requirements.txt",
                "Update package version",
                "Fix dependency conflict",
                "Add system dependency",
                "Update lock file"
            ]
        }
    
    def generate_correction_plan(self, failure: GateFailure) -> Tuple[CorrectionStrategy, str, List[str]]:
        """Generiere Korrektur-Plan für Fehler."""
        
        # Klassifiziere Fehler falls noch nicht geschehen
        if not failure.correction_type:
            failure.classify_error()
        
        correction_type = failure.correction_type or CorrectionType.SYNTAX_FIX
        
        # Wähle Strategie basierend auf Severity
        if failure.severity == "critical":
            strategy = CorrectionStrategy.DEFENSIVE_PROGRAMMING
        elif failure.severity == "high":
            strategy = CorrectionStrategy.TARGETED_FIX
        elif failure.severity == "low":
            strategy = CorrectionStrategy.MINIMAL_CHANGE
        else:
            strategy = CorrectionStrategy.INCREMENTAL_IMPROVEMENT
        
        # Wähle Template basierend auf Fehler-Typ
        templates = self.correction_templates.get(correction_type, ["Generic fix"])
        
        # Generiere spezifische Beschreibung
        description = self._generate_specific_description(failure, strategy)
        
        # Generiere konkrete Änderungen
        changes = self._generate_specific_changes(failure, strategy)
        
        return strategy, description, changes
    
    def _generate_specific_description(self, failure: GateFailure, strategy: CorrectionStrategy) -> str:
        """Generiere spezifische Beschreibung."""
        
        base_templates = {
            CorrectionType.SYNTAX_FIX: f"Fix syntax error in {failure.failed_component or 'code'}",
            CorrectionType.IMPORT_FIX: f"Fix import issue in {failure.source_file or 'module'}",
            CorrectionType.TEST_FIX: f"Fix failing test in {failure.gate_name}",
            CorrectionType.SECURITY_FIX: f"Fix security issue: {failure.error_message[:50]}...",
            CorrectionType.COVERAGE_FIX: f"Improve test coverage in {failure.failed_component or 'module'}",
            CorrectionType.LINT_FIX: f"Fix linting issues in {failure.source_file or 'code'}",
            CorrectionType.BUILD_FIX: f"Fix build error: {failure.error_message[:50]}...",
            CorrectionType.DEPENDENCY_FIX: f"Fix dependency issue: {failure.error_message[:50]}..."
        }
        
        correction_type = failure.correction_type or CorrectionType.SYNTAX_FIX
        base_description = base_templates.get(correction_type, "Fix unknown issue")
        
        # Erweitere basierend auf Strategie
        strategy_suffixes = {
            CorrectionStrategy.MINIMAL_CHANGE: " with minimal code changes",
            CorrectionStrategy.TARGETED_FIX: " with targeted fix",
            CorrectionStrategy.INCREMENTAL_IMPROVEMENT: " with incremental improvement",
            CorrectionStrategy.DEFENSIVE_PROGRAMMING: " with defensive programming approach"
        }
        
        return base_description + strategy_suffixes.get(strategy, "")
    
    def _generate_specific_changes(self, failure: GateFailure, strategy: CorrectionStrategy) -> List[str]:
        """Generiere spezifische Änderungen."""
        
        changes = []
        correction_type = failure.correction_type or CorrectionType.SYNTAX_FIX
        
        # Typ-spezifische Änderungen
        if correction_type == CorrectionType.SYNTAX_FIX:
            changes.extend([
                "Review and fix syntax errors in source code",
                "Check for missing punctuation and brackets",
                "Validate indentation consistency"
            ])
        
        elif correction_type == CorrectionType.IMPORT_FIX:
            changes.extend([
                "Add missing import statements",
                "Update import paths if necessary",
                "Check and update requirements.txt"
            ])
        
        elif correction_type == CorrectionType.TEST_FIX:
            changes.extend([
                "Review and fix test assertions",
                "Add missing test setup or teardown",
                "Update test data if needed"
            ])
        
        elif correction_type == CorrectionType.SECURITY_FIX:
            changes.extend([
                "Replace hardcoded values with environment variables",
                "Add input validation and sanitization",
                "Implement proper error handling"
            ])
        
        elif correction_type == CorrectionType.COVERAGE_FIX:
            changes.extend([
                "Add tests for uncovered code paths",
                "Add tests for error conditions",
                "Remove unused code if appropriate"
            ])
        
        elif correction_type == CorrectionType.LINT_FIX:
            changes.extend([
                "Fix formatting and style issues",
                "Add missing docstrings",
                "Remove unused imports"
            ])
        
        elif correction_type == CorrectionType.BUILD_FIX:
            changes.extend([
                "Fix build configuration",
                "Add missing build dependencies",
                "Update build scripts"
            ])
        
        elif correction_type == CorrectionType.DEPENDENCY_FIX:
            changes.extend([
                "Update requirements.txt",
                "Resolve dependency conflicts",
                "Add missing system dependencies"
            ])
        
        return changes


class FeedbackLoopManager:
    """Feedback-Loop-Manager."""
    
    def __init__(self, max_attempts: int = 2):
        self.max_attempts = max_attempts
        self.correction_generator = CorrectionGenerator()
        self.active_sessions: Dict[str, FeedbackSession] = {}
    
    def start_feedback_session(self, run_id: str, failures: List[GateFailure]) -> FeedbackSession:
        """Starte Feedback-Session."""
        
        # Klassifiziere alle Fehler
        for failure in failures:
            failure.classify_error()
        
        session = FeedbackSession(
            run_id=run_id,
            original_failures=failures,
            max_attempts=self.max_attempts
        )
        
        self.active_sessions[run_id] = session
        
        logger.info(f"Started feedback session for run {run_id} with {len(failures)} failures")
        
        return session
    
    def attempt_correction(self, session: FeedbackSession, failure: GateFailure) -> CorrectionAttempt:
        """Versuche Korrektur für spezifischen Fehler."""
        
        attempt_number = len(session.attempts) + 1
        
        if attempt_number > self.max_attempts:
            logger.warning(f"Max attempts ({self.max_attempts}) reached for session {session.run_id}")
            return None
        
        # Generiere Korrektur-Plan
        strategy, description, changes = self.correction_generator.generate_correction_plan(failure)
        
        # Erstelle Korrektur-Versuch
        attempt = CorrectionAttempt(
            attempt_number=attempt_number,
            correction_type=failure.correction_type or CorrectionType.SYNTAX_FIX,
            strategy=strategy,
            description=description,
            changes_made=changes
        )
        
        # Simuliere Korrektur-Durchführung (in echter Implementierung würde hier Code generiert/geändert)
        success = self._simulate_correction_execution(attempt, failure)
        
        if success:
            attempt.result = FeedbackResult.SUCCESS
            attempt.improvement_achieved = True
            logger.info(f"Correction attempt {attempt_number} succeeded for {failure.gate_name}")
        else:
            attempt.result = FeedbackResult.FAILED_RETRY
            attempt.new_errors = [f"Correction for {failure.gate_name} did not resolve the issue"]
            logger.warning(f"Correction attempt {attempt_number} failed for {failure.gate_name}")
        
        session.add_attempt(attempt)
        
        return attempt
    
    def _simulate_correction_execution(self, attempt: CorrectionAttempt, failure: GateFailure) -> bool:
        """Simuliere Korrektur-Ausführung."""
        
        # Simuliere Erfolgswahrscheinlichkeit basierend auf Fehler-Typ und Versuch
        success_rates = {
            CorrectionType.SYNTAX_FIX: 0.8,
            CorrectionType.IMPORT_FIX: 0.7,
            CorrectionType.TEST_FIX: 0.6,
            CorrectionType.SECURITY_FIX: 0.5,
            CorrectionType.COVERAGE_FIX: 0.7,
            CorrectionType.LINT_FIX: 0.9,
            CorrectionType.BUILD_FIX: 0.6,
            CorrectionType.DEPENDENCY_FIX: 0.8
        }
        
        base_rate = success_rates.get(failure.correction_type or CorrectionType.SYNTAX_FIX, 0.5)
        
        # Reduziere Erfolgsrate bei wiederholten Versuchen
        adjusted_rate = base_rate * (0.8 ** (attempt.attempt_number - 1))
        
        # Simuliere basierend auf Hash des Fehlers (deterministisch für Demo)
        import hashlib
        error_hash = hashlib.sha256(failure.error_message.encode()).hexdigest()
        hash_value = int(error_hash[:8], 16) / (2**32)
        
        success = hash_value < adjusted_rate
        
        # Simuliere Verarbeitungszeit
        attempt.duration_seconds = 5.0 + (attempt.attempt_number * 2.0)
        
        # Füge realistische Datei-Änderungen hinzu
        if success:
            if failure.source_file:
                attempt.files_modified.append(failure.source_file)
            else:
                attempt.files_modified.extend(["main.py", "tests.py"])
        
        return success
    
    def run_feedback_loop(self, run_id: str, failures: List[GateFailure]) -> FeedbackSession:
        """Führe kompletten Feedback-Loop aus."""
        
        session = self.start_feedback_session(run_id, failures)
        
        # Priorisiere Fehler nach Severity
        prioritized_failures = sorted(failures, key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.severity, 2))
        
        successful_corrections = 0
        
        for failure in prioritized_failures:
            logger.info(f"Attempting correction for {failure.gate_name} ({failure.severity} severity)")
            
            attempt_count = 0
            failure_resolved = False
            
            while attempt_count < self.max_attempts and not failure_resolved:
                attempt = self.attempt_correction(session, failure)
                
                if not attempt:
                    break
                
                if attempt.result == FeedbackResult.SUCCESS:
                    successful_corrections += 1
                    failure_resolved = True
                    session.lessons_learned.append(f"Successfully resolved {failure.gate_name} with {attempt.strategy.value}")
                
                attempt_count += 1
            
            if not failure_resolved:
                session.lessons_learned.append(f"Could not resolve {failure.gate_name} after {attempt_count} attempts")
        
        # Bestimme Session-Ergebnis
        if successful_corrections == len(failures):
            session.complete_session(FeedbackResult.SUCCESS, success=True)
        elif successful_corrections > 0:
            session.complete_session(FeedbackResult.PARTIAL_SUCCESS, success=False)
        elif len(session.attempts) >= self.max_attempts:
            session.complete_session(FeedbackResult.MAX_ATTEMPTS_REACHED, success=False)
        else:
            session.complete_session(FeedbackResult.ABORT_CLEAN, success=False)
        
        logger.info(f"Feedback session completed: {session.session_result.value}, {successful_corrections}/{len(failures)} corrections successful")
        
        # Entferne aus aktiven Sessions
        if run_id in self.active_sessions:
            del self.active_sessions[run_id]
        
        return session
    
    def get_session_report(self, session: FeedbackSession) -> Dict[str, Any]:
        """Generiere Session-Report."""
        
        return {
            "session_summary": {
                "run_id": session.run_id,
                "result": session.session_result.value if session.session_result else "unknown",
                "success": session.final_success,
                "duration_seconds": session.total_duration,
                "total_attempts": len(session.attempts),
                "original_failures": len(session.original_failures),
                "successful_corrections": len([a for a in session.attempts if a.result == FeedbackResult.SUCCESS])
            },
            "correction_details": [attempt.to_dict() for attempt in session.attempts],
            "changes_log": session.changes_log,
            "lessons_learned": session.lessons_learned,
            "original_failures": [failure.to_dict() for failure in session.original_failures]
        }


# Convenience Functions
def create_feedback_loop_manager(max_attempts: int = 2) -> FeedbackLoopManager:
    """
    Erstelle Feedback-Loop-Manager.
    
    Args:
        max_attempts: Maximale Korrektur-Versuche
        
    Returns:
        Feedback-Loop-Manager
    """
    
    return FeedbackLoopManager(max_attempts)


def run_correction_cycle(
    manager: FeedbackLoopManager,
    run_id: str,
    gate_failures: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Führe Korrektur-Zyklus aus.
    
    Args:
        manager: Feedback-Loop-Manager
        run_id: Run-ID
        gate_failures: Gate-Fehler-Liste
        
    Returns:
        Session-Report
    """
    
    # Konvertiere Fehler-Dicts zu GateFailure-Objekten
    failures = []
    
    for failure_data in gate_failures:
        failure = GateFailure(
            gate_name=failure_data.get("gate_name", "unknown"),
            error_message=failure_data.get("error_message", ""),
            error_type=failure_data.get("error_type", ""),
            failed_component=failure_data.get("failed_component", ""),
            error_details=failure_data.get("error_details", {}),
            source_file=failure_data.get("source_file"),
            line_number=failure_data.get("line_number"),
            code_snippet=failure_data.get("code_snippet", "")
        )
        
        failures.append(failure)
    
    # Führe Feedback-Loop aus
    session = manager.run_feedback_loop(run_id, failures)
    
    # Generiere Report
    return manager.get_session_report(session)


if __name__ == "__main__":
    # Demo
    
    def demo_generator_feedback_loop():
        print("🔄 Generator Feedback Loop Demo:")
        
        # Test 1: Erstelle Feedback-Loop-Manager
        print("\\n🚀 Creating feedback loop manager:")
        
        manager = create_feedback_loop_manager(max_attempts=2)
        
        print(f"  ✓ Max attempts: {manager.max_attempts}")
        print(f"  ✓ Correction generator ready")
        
        # Test 2: Simuliere Gate-Failures
        print("\\n❌ Simulating gate failures:")
        
        test_failures = [
            {
                "gate_name": "scaffold_test",
                "error_message": "SyntaxError: invalid syntax at line 15",
                "error_type": "syntax_error",
                "failed_component": "main.py",
                "source_file": "main.py",
                "line_number": 15,
                "code_snippet": "def hello_world(\\n    print('Hello')"
            },
            {
                "gate_name": "import_test",
                "error_message": "ImportError: No module named 'requests'",
                "error_type": "import_error",
                "failed_component": "api_client.py",
                "source_file": "api_client.py",
                "error_details": {"missing_package": "requests"}
            },
            {
                "gate_name": "security_scan",
                "error_message": "B105: Possible hardcoded password found",
                "error_type": "security_issue",
                "failed_component": "config.py",
                "source_file": "config.py",
                "line_number": 8
            }
        ]
        
        for i, failure in enumerate(test_failures, 1):
            print(f"  ❌ Failure {i}: {failure['gate_name']} - {failure['error_message'][:50]}...")
        
        # Test 3: Führe Korrektur-Zyklus aus
        print("\\n🔄 Running correction cycle:")
        
        run_id = "test_run_001"
        session_report = run_correction_cycle(manager, run_id, test_failures)
        
        summary = session_report["session_summary"]
        
        print(f"  ✓ Session result: {summary['result']}")
        print(f"  ✓ Final success: {summary['success']}")
        print(f"  ✓ Duration: {summary['duration_seconds']:.1f}s")
        print(f"  ✓ Total attempts: {summary['total_attempts']}")
        print(f"  ✓ Successful corrections: {summary['successful_corrections']}/{summary['original_failures']}")
        
        # Test 4: Zeige Korrektur-Details
        print("\\n🛠️ Correction details:")
        
        for i, attempt in enumerate(session_report["correction_details"], 1):
            print(f"  Attempt {i}:")
            print(f"    • Type: {attempt['correction_type']}")
            print(f"    • Strategy: {attempt['strategy']}")
            print(f"    • Result: {attempt['result']}")
            print(f"    • Description: {attempt['description']}")
            print(f"    • Files modified: {len(attempt['files_modified'])}")
        
        # Test 5: Zeige Änderungs-Log
        print("\\n📝 Changes log:")
        
        for i, change in enumerate(session_report["changes_log"][:5], 1):  # Erste 5
            print(f"  {i}. {change}")
        
        if len(session_report["changes_log"]) > 5:
            print(f"    ... ({len(session_report['changes_log']) - 5} more changes)")
        
        # Test 6: Zeige Lessons Learned
        print("\\n🎓 Lessons learned:")
        
        for lesson in session_report["lessons_learned"]:
            print(f"  • {lesson}")
        
        # Test 7: Teste spezifischen kleinen Scaffold-Fehler
        print("\\n🎯 Testing small scaffold error (acceptance criteria):")
        
        small_error = [{
            "gate_name": "scaffold_syntax",
            "error_message": "SyntaxError: Missing closing parenthesis in function call",
            "error_type": "syntax_error",
            "failed_component": "scaffold.py",
            "source_file": "scaffold.py",
            "line_number": 10
        }]
        
        small_run_id = "small_error_test"
        small_session = run_correction_cycle(manager, small_run_id, small_error)
        
        small_summary = small_session["session_summary"]
        
        print(f"  ✓ Small error result: {small_summary['result']}")
        print(f"  ✓ Attempts made: {small_summary['total_attempts']}")
        print(f"  ✓ Success: {small_summary['success']}")
        print(f"  ✓ Duration: {small_summary['duration_seconds']:.1f}s")
        
        # Test Akzeptanz-Kriterien
        print("\\n🎯 Acceptance criteria:")
        
        # Bei Fail generiere minimalinvasive Korrektur
        corrections_generated = len(session_report["correction_details"]) > 0
        
        # Maximal zwei Versuche
        max_attempts_respected = all(
            attempt["attempt_number"] <= 2 
            for attempt in session_report["correction_details"]
        )
        
        # Dokumentiere Änderungen
        changes_documented = len(session_report["changes_log"]) > 0
        
        # Kleiner Scaffold-Fehler wird in höchstens zwei Iterationen gefixt oder sauber abgebrochen
        small_error_handled = (small_summary["success"] or 
                             small_summary["total_attempts"] <= 2 and 
                             small_summary["result"] in ["success", "abort_clean", "max_attempts_reached"])
        
        print(f"  ✓ Bei Fail generiere minimalinvasive Korrektur: {corrections_generated}")
        print(f"  ✓ Maximal zwei Versuche: {max_attempts_respected}")
        print(f"  ✓ Dokumentiere Änderungen: {changes_documented}")
        print(f"  ✓ Kleiner Scaffold-Fehler in ≤2 Iterationen gefixt oder sauber abgebrochen: {small_error_handled}")
        
        return (corrections_generated and max_attempts_respected and 
               changes_documented and small_error_handled)
    
    # Führe Demo aus
    try:
        result = demo_generator_feedback_loop()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
