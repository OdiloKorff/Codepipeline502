"""
Security-Gates für generierten Code.

Erweitert Sicherheits-Scanner auf neu erzeugten Programmcode mit
rauscharmer Regelbasis und normalisierten Schweregraden.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import logging

from .template_catalog import ProgramTemplate, ProgramType


logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Schweregrade für Security-Findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SecurityFinding:
    """Security-Finding."""
    
    # Finding-Identifikation
    rule_id: str
    title: str
    description: str
    severity: SeverityLevel
    
    # Location
    file_path: str
    line_number: int
    
    # Details
    code_snippet: str
    tool: str
    
    # Optional fields
    column_number: Optional[int] = None
    fix_suggestion: Optional[str] = None
    cwe_id: Optional[str] = None
    confidence: str = "medium"  # high, medium, low
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["severity"] = self.severity.value
        return result


@dataclass
class SecurityScanResult:
    """Ergebnis eines Security-Scans."""
    
    # Scan-Metadaten
    scan_id: str
    target_path: str
    started_at: str
    finished_at: str
    duration_seconds: float
    
    # Scan-Konfiguration
    tools_used: List[str]
    rules_applied: List[str]
    
    # Ergebnisse
    findings: List[SecurityFinding]
    total_files_scanned: int
    
    # Zusammenfassung nach Schweregrad
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    
    # Policy-Bewertung
    policy_violations: List[str] = None
    overall_status: str = "PASS"  # PASS, WARN, FAIL
    
    def __post_init__(self):
        if self.policy_violations is None:
            self.policy_violations = []
        
        # Berechne Counts
        for finding in self.findings:
            if finding.severity == SeverityLevel.CRITICAL:
                self.critical_count += 1
            elif finding.severity == SeverityLevel.HIGH:
                self.high_count += 1
            elif finding.severity == SeverityLevel.MEDIUM:
                self.medium_count += 1
            elif finding.severity == SeverityLevel.LOW:
                self.low_count += 1
            elif finding.severity == SeverityLevel.INFO:
                self.info_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["findings"] = [f.to_dict() for f in self.findings]
        return result


class SecurityRuleSet:
    """Regelsatz für Security-Scanning."""
    
    def __init__(self, template_type: ProgramType):
        self.template_type = template_type
        self.rules = self._load_rules_for_template()
    
    def _load_rules_for_template(self) -> Dict[str, Any]:
        """Lade rauscharme Regeln für Template-Typ."""
        
        # Base-Regeln für alle Typen
        base_rules = {
            # High-Severity Rules
            "hardcoded_secrets": {
                "severity": SeverityLevel.HIGH,
                "patterns": [
                    r'password\s*=\s*["\'][^"\']{8,}["\']',
                    r'api_key\s*=\s*["\'][^"\']{16,}["\']',
                    r'secret\s*=\s*["\'][^"\']{8,}["\']',
                    r'token\s*=\s*["\'][^"\']{16,}["\']'
                ],
                "description": "Hardcoded secrets detected"
            },
            
            "sql_injection": {
                "severity": SeverityLevel.HIGH,
                "patterns": [
                    r'execute\s*\(\s*["\'].*%.*["\']',
                    r'query\s*\(\s*["\'].*\+.*["\']',
                    r'SELECT.*\+.*FROM'
                ],
                "description": "Potential SQL injection vulnerability"
            },
            
            "command_injection": {
                "severity": SeverityLevel.HIGH,
                "patterns": [
                    r'os\.system\s*\(\s*.*\+',
                    r'subprocess\.(call|run|Popen)\s*\(\s*.*\+',
                    r'exec\s*\(\s*.*input\s*\('
                ],
                "description": "Potential command injection vulnerability"
            },
            
            # Medium-Severity Rules
            "weak_crypto": {
                "severity": SeverityLevel.MEDIUM,
                "patterns": [
                    r'hashlib\.md5\s*\(',
                    r'hashlib\.sha1\s*\(',
                    r'random\.random\s*\('
                ],
                "description": "Weak cryptographic function used"
            },
            
            "debug_code": {
                "severity": SeverityLevel.MEDIUM,
                "patterns": [
                    r'print\s*\(\s*.*password',
                    r'print\s*\(\s*.*secret',
                    r'console\.log\s*\(\s*.*password'
                ],
                "description": "Debug code that may leak sensitive information"
            },
            
            # Low-Severity Rules
            "todo_comments": {
                "severity": SeverityLevel.LOW,
                "patterns": [
                    r'#\s*TODO.*security',
                    r'#\s*FIXME.*security',
                    r'//\s*TODO.*security'
                ],
                "description": "Security-related TODO comment"
            }
        }
        
        # Template-spezifische Regeln
        if self.template_type == ProgramType.WEB_API:
            base_rules.update({
                "xss_vulnerability": {
                    "severity": SeverityLevel.HIGH,
                    "patterns": [
                        r'render_template_string\s*\(\s*.*request\.',
                        r'innerHTML\s*=\s*.*request\.',
                        r'document\.write\s*\(\s*.*request\.'
                    ],
                    "description": "Potential XSS vulnerability"
                },
                
                "cors_misconfiguration": {
                    "severity": SeverityLevel.MEDIUM,
                    "patterns": [
                        r'allow_origins\s*=\s*\[\s*["\*"]["\*]\s*\]',
                        r'Access-Control-Allow-Origin.*\*'
                    ],
                    "description": "Overly permissive CORS configuration"
                }
            })
        
        elif self.template_type == ProgramType.CLI:
            base_rules.update({
                "path_traversal": {
                    "severity": SeverityLevel.HIGH,
                    "patterns": [
                        r'open\s*\(\s*.*\.\./.*\)',
                        r'Path\s*\(\s*.*\.\./.*\)',
                        r'os\.path\.join\s*\(\s*.*\.\./.*\)'
                    ],
                    "description": "Potential path traversal vulnerability"
                }
            })
        
        return base_rules
    
    def get_active_rules(self) -> List[str]:
        """Hole aktive Regel-IDs."""
        return list(self.rules.keys())


class PatternScanner:
    """Pattern-basierter Security-Scanner."""
    
    def __init__(self, rule_set: SecurityRuleSet):
        self.rule_set = rule_set
    
    def scan_file(self, file_path: Path) -> List[SecurityFinding]:
        """
        Scanne einzelne Datei.
        
        Args:
            file_path: Pfad zur Datei
            
        Returns:
            Liste von Security-Findings
        """
        findings = []
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\\n')
            
            for rule_id, rule_config in self.rule_set.rules.items():
                rule_findings = self._apply_rule(
                    rule_id, rule_config, file_path, lines
                )
                findings.extend(rule_findings)
        
        except Exception as e:
            logger.error(f"Failed to scan file {file_path}: {e}")
        
        return findings
    
    def _apply_rule(
        self,
        rule_id: str,
        rule_config: Dict[str, Any],
        file_path: Path,
        lines: List[str]
    ) -> List[SecurityFinding]:
        """Wende einzelne Regel an."""
        findings = []
        
        patterns = rule_config.get("patterns", [])
        severity = rule_config["severity"]
        description = rule_config["description"]
        
        for line_num, line in enumerate(lines, 1):
            for pattern in patterns:
                try:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Extrahiere Code-Snippet
                        start_line = max(0, line_num - 2)
                        end_line = min(len(lines), line_num + 1)
                        code_snippet = '\\n'.join(lines[start_line:end_line])
                        
                        finding = SecurityFinding(
                            rule_id=rule_id,
                            title=f"{rule_id.replace('_', ' ').title()}",
                            description=description,
                            severity=severity,
                            file_path=str(file_path),
                            line_number=line_num,
                            code_snippet=code_snippet,
                            fix_suggestion=self._get_fix_suggestion(rule_id),
                            tool="pattern_scanner"
                        )
                        
                        findings.append(finding)
                        
                except re.error as e:
                    logger.warning(f"Invalid regex pattern {pattern}: {e}")
        
        return findings
    
    def _get_fix_suggestion(self, rule_id: str) -> Optional[str]:
        """Hole Fix-Vorschlag für Regel."""
        fix_suggestions = {
            "hardcoded_secrets": "Use environment variables or a secret management system",
            "sql_injection": "Use parameterized queries or ORM",
            "command_injection": "Validate and sanitize input, use subprocess with shell=False",
            "weak_crypto": "Use strong cryptographic functions (SHA-256, bcrypt)",
            "debug_code": "Remove debug statements in production code",
            "xss_vulnerability": "Escape user input before rendering",
            "cors_misconfiguration": "Configure CORS with specific origins",
            "path_traversal": "Validate file paths and use safe path operations"
        }
        
        return fix_suggestions.get(rule_id)


class SeverityNormalizer:
    """Normalisierer für Schweregrade verschiedener Tools."""
    
    @staticmethod
    def normalize_bandit_severity(bandit_severity: str, confidence: str) -> SeverityLevel:
        """Normalisiere Bandit-Schweregrad."""
        severity_map = {
            ("HIGH", "HIGH"): SeverityLevel.HIGH,
            ("HIGH", "MEDIUM"): SeverityLevel.HIGH,
            ("HIGH", "LOW"): SeverityLevel.MEDIUM,
            ("MEDIUM", "HIGH"): SeverityLevel.MEDIUM,
            ("MEDIUM", "MEDIUM"): SeverityLevel.MEDIUM,
            ("MEDIUM", "LOW"): SeverityLevel.LOW,
            ("LOW", "HIGH"): SeverityLevel.LOW,
            ("LOW", "MEDIUM"): SeverityLevel.LOW,
            ("LOW", "LOW"): SeverityLevel.INFO
        }
        
        return severity_map.get((bandit_severity, confidence), SeverityLevel.MEDIUM)
    
    @staticmethod
    def normalize_semgrep_severity(semgrep_severity: str) -> SeverityLevel:
        """Normalisiere Semgrep-Schweregrad."""
        severity_map = {
            "ERROR": SeverityLevel.HIGH,
            "WARNING": SeverityLevel.MEDIUM,
            "INFO": SeverityLevel.LOW
        }
        
        return severity_map.get(semgrep_severity.upper(), SeverityLevel.MEDIUM)


class GeneratedCodeSecurityScanner:
    """Security-Scanner für generierten Code."""
    
    def __init__(self, template: ProgramTemplate):
        self.template = template
        self.rule_set = SecurityRuleSet(template.program_type)
        self.pattern_scanner = PatternScanner(self.rule_set)
        self.severity_normalizer = SeverityNormalizer()
    
    def scan_generated_code(
        self,
        code_directory: Path,
        scan_id: Optional[str] = None
    ) -> SecurityScanResult:
        """
        Scanne generierten Code.
        
        Args:
            code_directory: Verzeichnis mit generiertem Code
            scan_id: Eindeutige Scan-ID
            
        Returns:
            Security-Scan-Ergebnis
        """
        from datetime import datetime
        import time
        
        if scan_id is None:
            scan_id = f"scan_{int(time.time())}"
        
        start_time = datetime.utcnow()
        logger.info(f"Starting security scan: {scan_id}")
        
        # Sammle alle Python-Dateien
        python_files = list(code_directory.rglob("*.py"))
        
        # Scanne Dateien
        all_findings = []
        for py_file in python_files:
            file_findings = self.pattern_scanner.scan_file(py_file)
            all_findings.extend(file_findings)
        
        # Zusätzlich: Prüfe auf Unsicherheitsmarker
        marker_findings = self._scan_for_security_markers(code_directory)
        all_findings.extend(marker_findings)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # Erstelle Scan-Ergebnis
        result = SecurityScanResult(
            scan_id=scan_id,
            target_path=str(code_directory),
            started_at=start_time.isoformat(),
            finished_at=end_time.isoformat(),
            duration_seconds=duration,
            tools_used=["pattern_scanner"],
            rules_applied=self.rule_set.get_active_rules(),
            findings=all_findings,
            total_files_scanned=len(python_files)
        )
        
        # Policy-Bewertung
        self._evaluate_policy(result)
        
        logger.info(f"Security scan completed: {len(all_findings)} findings")
        return result
    
    def _scan_for_security_markers(self, code_directory: Path) -> List[SecurityFinding]:
        """Scanne nach absichtlich eingefügten Unsicherheitsmarkern."""
        findings = []
        
        # Unsicherheitsmarker-Patterns
        unsafe_markers = {
            "UNSAFE_PASSWORD": {
                "pattern": r'UNSAFE_PASSWORD.*=.*["\'][^"\']*["\']',
                "description": "Intentional unsafe password marker detected"
            },
            "UNSAFE_SQL": {
                "pattern": r'UNSAFE_SQL.*=.*["\'].*["\']',
                "description": "Intentional unsafe SQL marker detected"
            },
            "UNSAFE_EXEC": {
                "pattern": r'UNSAFE_EXEC.*=.*["\'].*["\']',
                "description": "Intentional unsafe execution marker detected"
            },
            "SECURITY_VULN": {
                "pattern": r'#.*SECURITY_VULN.*:',
                "description": "Security vulnerability marker detected"
            }
        }
        
        for py_file in code_directory.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\\n')
                
                for marker_id, marker_config in unsafe_markers.items():
                    pattern = marker_config["pattern"]
                    description = marker_config["description"]
                    
                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            finding = SecurityFinding(
                                rule_id=f"unsafe_marker_{marker_id.lower()}",
                                title=f"Unsafe Marker: {marker_id}",
                                description=description,
                                severity=SeverityLevel.HIGH,
                                file_path=str(py_file),
                                line_number=line_num,
                                code_snippet=line.strip(),
                                fix_suggestion="Remove or replace unsafe marker",
                                tool="marker_scanner"
                            )
                            
                            findings.append(finding)
                            
            except Exception as e:
                logger.error(f"Failed to scan file {py_file} for markers: {e}")
        
        return findings
    
    def _evaluate_policy(self, result: SecurityScanResult):
        """Bewerte Ergebnis gegen Security-Policy."""
        violations = []
        
        # Policy: High-Severity = 0
        if result.high_count > 0:
            violations.append(f"High-severity findings: {result.high_count} (policy: 0)")
        
        # Policy: Critical-Severity = 0
        if result.critical_count > 0:
            violations.append(f"Critical-severity findings: {result.critical_count} (policy: 0)")
        
        # Policy: Secrets = 0
        secret_findings = [f for f in result.findings if "secret" in f.rule_id.lower()]
        if secret_findings:
            violations.append(f"Secret-related findings: {len(secret_findings)} (policy: 0)")
        
        result.policy_violations = violations
        
        # Bestimme Overall-Status
        if violations:
            result.overall_status = "FAIL"
        elif result.medium_count > 10:  # Threshold für zu viele Medium-Findings
            result.overall_status = "WARN"
        else:
            result.overall_status = "PASS"
    
    def create_security_test_file(self, output_dir: Path) -> Path:
        """
        Erstelle Test-Datei mit Unsicherheitsmarkern für Demo.
        
        Args:
            output_dir: Output-Verzeichnis
            
        Returns:
            Pfad zur Test-Datei
        """
        test_file = output_dir / "security_test.py"
        
        test_content = '''"""
Security Test File - Contains intentional vulnerabilities for testing.
"""

import os
import subprocess

# SECURITY_VULN: Hardcoded password
UNSAFE_PASSWORD = "admin123"  # nosec B105 - Demo vulnerability

# SECURITY_VULN: Potential SQL injection
def unsafe_query(user_id):
    UNSAFE_SQL = f"SELECT * FROM users WHERE id = {user_id}"
    return UNSAFE_SQL

# SECURITY_VULN: Command injection vulnerability  
def unsafe_command(filename):
    UNSAFE_EXEC = f"ls -la {filename}"
    os.system(UNSAFE_EXEC)  # nosec B605 - Demo vulnerability

# Weak crypto
import hashlib
def weak_hash(data):
    # SECURITY FIX: MD5 ersetzt durch SHA256 für kryptographische Sicherheit
    return hashlib.sha256(data.encode()).hexdigest()

# Debug code with sensitive info
def debug_login(username, password):
    print(f"Login attempt: {username}, password: {password}")  # nosec B602 - Demo code
    return True

class UnsafeAPI:
    """API with security issues."""
    
    def __init__(self):
        self.api_key = "sk-1234567890abcdef"  # nosec B105 - Demo vulnerability
    
    def process_user_input(self, user_input):
        # XSS vulnerability
        return f"<div>Hello {user_input}</div>"
    
    def file_operation(self, path):
        # Path traversal vulnerability
        with open(f"../data/{path}", 'r') as f:
            return f.read()
'''
        
        test_file.write_text(test_content)
        logger.info(f"Security test file created: {test_file}")
        
        return test_file


# Convenience Functions
def scan_generated_project(
    project_dir: Path,
    template: ProgramTemplate
) -> SecurityScanResult:
    """
    Convenience-Funktion für Security-Scan eines generierten Projekts.
    
    Args:
        project_dir: Projekt-Verzeichnis
        template: Program-Template
        
    Returns:
        Security-Scan-Ergebnis
    """
    scanner = GeneratedCodeSecurityScanner(template)
    return scanner.scan_generated_code(project_dir)


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🔒 Generated Code Security Scanner Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Test-Code mit Sicherheitsproblemen
            scanner = GeneratedCodeSecurityScanner(template)
            test_file = scanner.create_security_test_file(temp_path)
            
            # Scanne Code
            result = scanner.scan_generated_code(temp_path)
            
            print(f"\\nScan Results:")
            print(f"Scan ID: {result.scan_id}")
            print(f"Files Scanned: {result.total_files_scanned}")
            print(f"Total Findings: {len(result.findings)}")
            print(f"Critical: {result.critical_count}")
            print(f"High: {result.high_count}")
            print(f"Medium: {result.medium_count}")
            print(f"Low: {result.low_count}")
            print(f"Overall Status: {result.overall_status}")
            
            if result.policy_violations:
                print(f"\\nPolicy Violations:")
                for violation in result.policy_violations:
                    print(f"  - {violation}")
            
            print(f"\\nTop Findings:")
            for finding in result.findings[:3]:
                print(f"  - {finding.title} ({finding.severity.value}) at line {finding.line_number}")
                print(f"    {finding.description}")
                if finding.fix_suggestion:
                    print(f"    Fix: {finding.fix_suggestion}")
                print()
