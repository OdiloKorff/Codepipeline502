"""
Security Scanner für generierten Code.

Implementiert:
- Aktivierung mindestens eines aktiven Security-Tools
- Rauscharme Regelbasis für generierten Code
- Normalisierte Schweregrade mit High/Secret Hard-Fail
- Erkennung absichtlich eingebauter Unsicherheitsmarker
"""

from __future__ import annotations

import os
import re
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import logging


logger = logging.getLogger(__name__)


class SecuritySeverity(Enum):
    """Security-Schweregrade."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SecurityCategory(Enum):
    """Security-Kategorien."""
    INJECTION = "injection"
    SECRETS = "secrets"
    CRYPTO = "crypto"
    AUTH = "auth"
    XSS = "xss"
    SQLI = "sqli"
    HARDCODED = "hardcoded"
    INSECURE_RANDOM = "insecure_random"
    PATH_TRAVERSAL = "path_traversal"
    UNSAFE_EVAL = "unsafe_eval"


@dataclass
class SecurityFinding:
    """Security-Fund."""
    
    # Fund-Details
    rule_id: str
    severity: SecuritySeverity
    category: SecurityCategory
    title: str
    description: str
    
    # Location
    file_path: str
    line_number: int = 0
    column: int = 0
    
    # Code
    code_snippet: str = ""
    
    # Tool-Info
    tool_name: str = ""
    
    # Remediation
    remediation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column": self.column,
            "code_snippet": self.code_snippet,
            "tool_name": self.tool_name,
            "remediation": self.remediation
        }


@dataclass
class SecurityScanResult:
    """Security-Scan-Ergebnis."""
    
    # Scan-Info
    scan_id: str
    target_path: str
    scan_type: str = "generated_code"
    
    # Tools
    active_tools: List[str] = field(default_factory=list)
    
    # Findings
    findings: List[SecurityFinding] = field(default_factory=list)
    
    # Statistiken
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    secrets_count: int = 0
    
    # Status
    scan_status: str = "completed"
    is_blocked: bool = False
    block_reason: str = ""
    
    # Timing
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    
    def calculate_stats(self):
        """Berechne Statistiken."""
        self.critical_count = len([f for f in self.findings if f.severity == SecuritySeverity.CRITICAL])
        self.high_count = len([f for f in self.findings if f.severity == SecuritySeverity.HIGH])
        self.medium_count = len([f for f in self.findings if f.severity == SecuritySeverity.MEDIUM])
        self.low_count = len([f for f in self.findings if f.severity == SecuritySeverity.LOW])
        self.info_count = len([f for f in self.findings if f.severity == SecuritySeverity.INFO])
        self.secrets_count = len([f for f in self.findings if f.category == SecurityCategory.SECRETS])
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "scan_id": self.scan_id,
            "target_path": self.target_path,
            "scan_type": self.scan_type,
            "active_tools": self.active_tools,
            "findings": [f.to_dict() for f in self.findings],
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "info_count": self.info_count,
            "secrets_count": self.secrets_count,
            "scan_status": self.scan_status,
            "is_blocked": self.is_blocked,
            "block_reason": self.block_reason,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds
        }


class SecurityTool:
    """Basis-Klasse für Security-Tools."""
    
    def __init__(self, name: str):
        self.name = name
    
    def is_available(self) -> bool:
        """Prüfe ob Tool verfügbar ist."""
        raise NotImplementedError
    
    def scan(self, target_path: Path) -> List[SecurityFinding]:
        """Führe Security-Scan aus."""
        raise NotImplementedError


class BanditTool(SecurityTool):
    """Bandit Security-Tool."""
    
    def __init__(self):
        super().__init__("bandit")
    
    def is_available(self) -> bool:
        """Prüfe Bandit-Verfügbarkeit."""
        try:
            result = subprocess.run(["bandit", "--version"], capture_output=True, timeout=10)
            return result.returncode == 0
        except:
            return False
    
    def scan(self, target_path: Path) -> List[SecurityFinding]:
        """Führe Bandit-Scan aus."""
        
        findings = []
        
        try:
            # Bandit mit Low-Noise-Konfiguration
            cmd = [
                "bandit", "-r", str(target_path),
                "-f", "json",
                "-ll",  # Low confidence, Low severity minimum
                "--skip", "B101,B601,B602,B603,B604,B605,B606,B607"  # Skip noise
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode in [0, 1]:  # 0 = no issues, 1 = issues found
                try:
                    bandit_output = json.loads(result.stdout)
                    
                    for issue in bandit_output.get("results", []):
                        severity = self._map_bandit_severity(
                            issue.get("issue_severity", "LOW"),
                            issue.get("issue_confidence", "LOW")
                        )
                        
                        category = self._map_bandit_category(issue.get("test_id", ""))
                        
                        finding = SecurityFinding(
                            rule_id=issue.get("test_id", "unknown"),
                            severity=severity,
                            category=category,
                            title=issue.get("test_name", "Security Issue"),
                            description=issue.get("issue_text", ""),
                            file_path=issue.get("filename", ""),
                            line_number=issue.get("line_number", 0),
                            code_snippet=issue.get("code", ""),
                            tool_name=self.name,
                            remediation=self._get_remediation(issue.get("test_id", ""))
                        )
                        
                        findings.append(finding)
                
                except json.JSONDecodeError:
                    logger.error("Failed to parse Bandit JSON output")
        
        except Exception as e:
            logger.error(f"Bandit scan failed: {e}")
        
        return findings
    
    def _map_bandit_severity(self, severity: str, confidence: str) -> SecuritySeverity:
        """Mappe Bandit-Schweregrad."""
        
        severity = severity.upper()
        confidence = confidence.upper()
        
        # High severity oder high confidence -> HIGH
        if severity == "HIGH" or confidence == "HIGH":
            return SecuritySeverity.HIGH
        elif severity == "MEDIUM":
            return SecuritySeverity.MEDIUM
        else:
            return SecuritySeverity.LOW
    
    def _map_bandit_category(self, test_id: str) -> SecurityCategory:
        """Mappe Bandit-Kategorie."""
        
        category_map = {
            "B105": SecurityCategory.HARDCODED,  # hardcoded_password_string
            "B106": SecurityCategory.HARDCODED,  # hardcoded_password_funcarg
            "B107": SecurityCategory.HARDCODED,  # hardcoded_password_default
            "B108": SecurityCategory.HARDCODED,  # hardcoded_tmp_directory
            "B201": SecurityCategory.INJECTION,  # flask_debug_true
            "B301": SecurityCategory.CRYPTO,     # pickle
            "B302": SecurityCategory.INJECTION,  # marshal
            "B303": SecurityCategory.CRYPTO,     # md5
            "B304": SecurityCategory.CRYPTO,     # insecure_cipher
            "B305": SecurityCategory.CRYPTO,     # insecure_cipher_mode
            "B311": SecurityCategory.INSECURE_RANDOM,  # random
            "B312": SecurityCategory.INSECURE_RANDOM,  # telnetlib
            "B313": SecurityCategory.INJECTION,  # xml_bad_cElementTree
            "B314": SecurityCategory.INJECTION,  # xml_bad_ElementTree
            "B315": SecurityCategory.INJECTION,  # xml_bad_expatreader
            "B316": SecurityCategory.INJECTION,  # xml_bad_expatbuilder
            "B317": SecurityCategory.INJECTION,  # xml_bad_sax
            "B318": SecurityCategory.INJECTION,  # xml_bad_minidom
            "B319": SecurityCategory.INJECTION,  # xml_bad_pulldom
            "B320": SecurityCategory.INJECTION,  # xml_bad_etree
            "B501": SecurityCategory.INJECTION,  # request_with_no_cert_validation
            "B502": SecurityCategory.CRYPTO,     # ssl_with_bad_version
            "B503": SecurityCategory.CRYPTO,     # ssl_with_bad_defaults
            "B504": SecurityCategory.CRYPTO,     # ssl_with_no_version
            "B505": SecurityCategory.CRYPTO,     # weak_cryptographic_key
            "B506": SecurityCategory.CRYPTO,     # yaml_load
            "B507": SecurityCategory.INJECTION,  # ssh_no_host_key_verification
            "B601": SecurityCategory.INJECTION,  # paramiko_calls
            "B602": SecurityCategory.INJECTION,  # subprocess_popen_with_shell_equals_true
            "B603": SecurityCategory.INJECTION,  # subprocess_without_shell_equals_false
            "B604": SecurityCategory.INJECTION,  # any_other_function_with_shell_equals_true
            "B605": SecurityCategory.INJECTION,  # start_process_with_a_shell
            "B606": SecurityCategory.INJECTION,  # start_process_with_no_shell
            "B607": SecurityCategory.INJECTION,  # start_process_with_partial_path
            "B608": SecurityCategory.INJECTION,  # hardcoded_sql_expressions
            "B609": SecurityCategory.INJECTION,  # linux_commands_wildcard_injection
            "B701": SecurityCategory.INJECTION,  # jinja2_autoescape_false
            "B702": SecurityCategory.INJECTION,  # use_of_mako_templates
            "B703": SecurityCategory.INJECTION   # django_mark_safe
        }
        
        return category_map.get(test_id, SecurityCategory.INJECTION)
    
    def _get_remediation(self, test_id: str) -> str:
        """Hole Remediation für Test-ID."""
        
        remediation_map = {
            "B105": "Use environment variables or secure key management for passwords",
            "B106": "Avoid hardcoded passwords in function arguments",
            "B107": "Use secure configuration for password defaults",
            "B301": "Avoid using pickle with untrusted data",
            "B303": "Use secure hash algorithms like SHA-256 instead of MD5",
            "B311": "Use secrets.SystemRandom() for cryptographic purposes",
            "B501": "Enable SSL certificate validation",
            "B502": "Use secure SSL/TLS versions",
            "B602": "Avoid shell=True in subprocess calls",
            "B608": "Use parameterized queries to prevent SQL injection"
        }
        
        return remediation_map.get(test_id, "Follow security best practices")


class SecretsPatternTool(SecurityTool):
    """Pattern-basiertes Secrets-Detection-Tool."""
    
    def __init__(self):
        super().__init__("secrets_pattern")
        
        # Patterns für verschiedene Secret-Typen
        self.patterns = {
            "api_key": [
                r"(?i)api[_-]?key[\"']?\s*[:=]\s*[\"']?([a-z0-9]{20,})",
                r"(?i)[\"']api[_-]?key[\"']?\s*[:=]\s*[\"']([a-z0-9]{20,})[\"']"
            ],
            "password": [
                r"(?i)password[\"']?\s*[:=]\s*[\"']([^\"'\\s]{8,})[\"']",
                r"(?i)[\"']password[\"']?\s*[:=]\s*[\"']([^\"'\\s]{8,})[\"']"
            ],
            "secret": [
                r"(?i)secret[\"']?\s*[:=]\s*[\"']([a-z0-9]{16,})[\"']",
                r"(?i)[\"']secret[\"']?\s*[:=]\s*[\"']([a-z0-9]{16,})[\"']"
            ],
            "token": [
                r"(?i)token[\"']?\s*[:=]\s*[\"']([a-z0-9]{20,})[\"']",
                r"(?i)[\"']token[\"']?\s*[:=]\s*[\"']([a-z0-9]{20,})[\"']"
            ],
            "private_key": [
                r"-----BEGIN PRIVATE KEY-----",
                r"-----BEGIN RSA PRIVATE KEY-----",
                r"-----BEGIN ENCRYPTED PRIVATE KEY-----"
            ],
            "aws_key": [
                r"AKIA[0-9A-Z]{16}",
                r"(?i)aws[_-]?access[_-]?key[_-]?id[\"']?\s*[:=]\s*[\"']?(AKIA[0-9A-Z]{16})"
            ],
            "github_token": [
                r"ghp_[a-zA-Z0-9]{36}",
                r"ghs_[a-zA-Z0-9]{36}",
                r"gho_[a-zA-Z0-9]{36}"
            ]
        }
        
        # Whitelist für false positives
        self.whitelist_patterns = [
            r"(?i)example",
            r"(?i)test",
            r"(?i)dummy",
            r"(?i)placeholder",
            r"(?i)your[_-]?api[_-]?key",
            r"(?i)insert[_-]?your",
            r"(?i)replace[_-]?with"
        ]
    
    def is_available(self) -> bool:
        """Pattern-Tool ist immer verfügbar."""
        return True
    
    def scan(self, target_path: Path) -> List[SecurityFinding]:
        """Führe Secrets-Pattern-Scan aus."""
        
        findings = []
        
        # Scanne alle Python-Dateien
        for py_file in target_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                findings.extend(self._scan_file(py_file, content))
            except Exception as e:
                logger.warning(f"Failed to scan {py_file}: {e}")
        
        return findings
    
    def _scan_file(self, file_path: Path, content: str) -> List[SecurityFinding]:
        """Scanne einzelne Datei."""
        
        findings = []
        lines = content.splitlines()
        
        for line_num, line in enumerate(lines, 1):
            for secret_type, patterns in self.patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, line)
                    
                    for match in matches:
                        # Prüfe Whitelist
                        if self._is_whitelisted(line):
                            continue
                        
                        # Prüfe ob es ein Test-Marker ist
                        if self._is_test_marker(match.group(0)):
                            # Das ist ein absichtlicher Unsicherheitsmarker!
                            severity = SecuritySeverity.CRITICAL
                        else:
                            severity = SecuritySeverity.HIGH
                        
                        finding = SecurityFinding(
                            rule_id=f"SECRET_{secret_type.upper()}",
                            severity=severity,
                            category=SecurityCategory.SECRETS,
                            title=f"Potential {secret_type.replace('_', ' ').title()} Detected",
                            description=f"Found potential {secret_type} in source code",
                            file_path=str(file_path),
                            line_number=line_num,
                            column=match.start(),
                            code_snippet=line.strip(),
                            tool_name=self.name,
                            remediation=f"Move {secret_type} to environment variables or secure storage"
                        )
                        
                        findings.append(finding)
        
        return findings
    
    def _is_whitelisted(self, line: str) -> bool:
        """Prüfe ob Zeile auf Whitelist steht."""
        
        for pattern in self.whitelist_patterns:
            if re.search(pattern, line):
                return True
        
        return False
    
    def _is_test_marker(self, match_text: str) -> bool:
        """Prüfe ob es ein Test-Marker ist."""
        
        # Spezielle Marker für Tests
        test_markers = [
            "INSECURE_TEST_MARKER",
            "VULNERABILITY_TEST",
            "SECURITY_TEST_FAIL"
        ]
        
        for marker in test_markers:
            if marker in match_text:
                return True
        
        return False


class UnsafePatternTool(SecurityTool):
    """Tool für unsichere Code-Patterns."""
    
    def __init__(self):
        super().__init__("unsafe_patterns")
        
        # Unsafe Patterns
        self.unsafe_patterns = {
            "eval": {
                "patterns": [r"\\beval\\s*\\(", r"\\bexec\\s*\\("],
                "severity": SecuritySeverity.HIGH,
                "category": SecurityCategory.UNSAFE_EVAL,
                "title": "Use of eval() or exec()",
                "description": "Dynamic code execution can lead to code injection vulnerabilities"
            },
            "shell_injection": {
                "patterns": [r"os\\.system\\s*\\(", r"subprocess\\.call\\(.+shell=True"],
                "severity": SecuritySeverity.HIGH,
                "category": SecurityCategory.INJECTION,
                "title": "Potential Shell Injection",
                "description": "Shell command execution without proper sanitization"
            },
            "path_traversal": {
                "patterns": [r"\\.\\./", r"\\.\\.\\\\"],
                "severity": SecuritySeverity.MEDIUM,
                "category": SecurityCategory.PATH_TRAVERSAL,
                "title": "Path Traversal Pattern",
                "description": "Potential directory traversal vulnerability"
            },
            "sql_injection": {
                "patterns": [r"\\bSELECT\\b.+%s", r"\\bINSERT\\b.+%s", r"\\bUPDATE\\b.+%s"],
                "severity": SecuritySeverity.HIGH,
                "category": SecurityCategory.SQLI,
                "title": "Potential SQL Injection",
                "description": "SQL query with string formatting instead of parameterized queries"
            }
        }
    
    def is_available(self) -> bool:
        """Pattern-Tool ist immer verfügbar."""
        return True
    
    def scan(self, target_path: Path) -> List[SecurityFinding]:
        """Führe Unsafe-Pattern-Scan aus."""
        
        findings = []
        
        for py_file in target_path.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                findings.extend(self._scan_file(py_file, content))
            except Exception as e:
                logger.warning(f"Failed to scan {py_file}: {e}")
        
        return findings
    
    def _scan_file(self, file_path: Path, content: str) -> List[SecurityFinding]:
        """Scanne einzelne Datei."""
        
        findings = []
        lines = content.splitlines()
        
        for line_num, line in enumerate(lines, 1):
            for pattern_name, pattern_config in self.unsafe_patterns.items():
                for pattern in pattern_config["patterns"]:
                    if re.search(pattern, line, re.IGNORECASE):
                        finding = SecurityFinding(
                            rule_id=f"UNSAFE_{pattern_name.upper()}",
                            severity=pattern_config["severity"],
                            category=pattern_config["category"],
                            title=pattern_config["title"],
                            description=pattern_config["description"],
                            file_path=str(file_path),
                            line_number=line_num,
                            code_snippet=line.strip(),
                            tool_name=self.name,
                            remediation=self._get_remediation(pattern_name)
                        )
                        
                        findings.append(finding)
        
        return findings
    
    def _get_remediation(self, pattern_name: str) -> str:
        """Hole Remediation für Pattern."""
        
        remediation_map = {
            "eval": "Avoid eval() and exec(). Use safe alternatives like ast.literal_eval()",
            "shell_injection": "Use subprocess with shell=False and validate inputs",
            "path_traversal": "Validate and sanitize file paths. Use os.path.normpath()",
            "sql_injection": "Use parameterized queries or ORM instead of string formatting"
        }
        
        return remediation_map.get(pattern_name, "Follow secure coding practices")


class GeneratedCodeSecurityScanner:
    """Security-Scanner für generierten Code."""
    
    def __init__(self):
        self.tools = [
            BanditTool(),
            SecretsPatternTool(),
            UnsafePatternTool()
        ]
    
    def scan_generated_code(
        self,
        target_path: Path,
        scan_id: Optional[str] = None
    ) -> SecurityScanResult:
        """Scanne generierten Code."""
        
        if scan_id is None:
            scan_id = f"gen_scan_{int(time.time())}"
        
        logger.info(f"Starting security scan: {scan_id}")
        
        result = SecurityScanResult(
            scan_id=scan_id,
            target_path=str(target_path),
            started_at=datetime.utcnow().isoformat()
        )
        
        start_time = time.time()
        
        # Prüfe verfügbare Tools
        active_tools = []
        all_findings = []
        
        for tool in self.tools:
            if tool.is_available():
                logger.info(f"Running {tool.name} scan")
                active_tools.append(tool.name)
                
                try:
                    findings = tool.scan(target_path)
                    all_findings.extend(findings)
                    logger.info(f"{tool.name} found {len(findings)} issues")
                
                except Exception as e:
                    logger.error(f"{tool.name} scan failed: {e}")
            else:
                logger.warning(f"{tool.name} not available")
        
        # Mindestens ein Tool muss aktiv sein
        if not active_tools:
            result.scan_status = "error"
            result.block_reason = "No security tools available"
            result.is_blocked = True
        else:
            result.active_tools = active_tools
            result.findings = all_findings
            result.calculate_stats()
            
            # Prüfe Blocking-Kriterien
            if result.critical_count > 0 or result.high_count > 0 or result.secrets_count > 0:
                result.is_blocked = True
                
                block_reasons = []
                if result.critical_count > 0:
                    block_reasons.append(f"{result.critical_count} critical issues")
                if result.high_count > 0:
                    block_reasons.append(f"{result.high_count} high severity issues")
                if result.secrets_count > 0:
                    block_reasons.append(f"{result.secrets_count} secrets detected")
                
                result.block_reason = "; ".join(block_reasons)
            
            result.scan_status = "completed"
        
        result.completed_at = datetime.utcnow().isoformat()
        result.duration_seconds = time.time() - start_time
        
        logger.info(f"Security scan completed: {result.scan_status}")
        
        return result
    
    def create_test_vulnerability(self, target_path: Path) -> Path:
        """Erstelle Test-Vulnerability für Akzeptanz-Test."""
        
        test_file = target_path / "test_security.py"
        
        # Absichtlich unsicherer Code mit Markern
        vulnerable_code = '''"""
Test file with intentional security vulnerabilities.
"""

# INSECURE_TEST_MARKER: This should be detected
API_KEY = "INSECURE_TEST_MARKER_abc123def456ghi789"

# Another vulnerability
PASSWORD = "hardcoded_password_123"

def unsafe_eval_function(user_input):
    # SECURITY FIX: eval() ersetzt durch sichere Alternative
    import ast
    try:
        # Sichere ast.literal_eval() für Datenstrukturen verwenden
        return ast.literal_eval(user_input)
    except (ValueError, SyntaxError):
        # Für komplexere Fälle: Whitelist-basierte Funktionsdispatch
        safe_operations = {
            "len('hello')": lambda: len('hello'),
            "str.upper('test')": lambda: str.upper('test'),
            "abs(-5)": lambda: abs(-5),
        }
        return safe_operations.get(user_input.strip(), lambda: None)()

def sql_injection_risk(user_id):
    # This should trigger SQL injection detection
    query = "SELECT * FROM users WHERE id = %s" % user_id
    return query
'''
        
        test_file.write_text(vulnerable_code)
        logger.info(f"Created test vulnerability file: {test_file}")
        
        return test_file


# Convenience Functions
def scan_generated_code(target_path: Path) -> SecurityScanResult:
    """Scanne generierten Code."""
    
    scanner = GeneratedCodeSecurityScanner()
    return scanner.scan_generated_code(target_path)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_generated_code_security_scanner():
        print("🛡️ Generated Code Security Scanner Demo:")
        
        scanner = GeneratedCodeSecurityScanner()
        
        # Test Tool-Verfügbarkeit
        print("\\n🔧 Testing tool availability:")
        
        available_tools = []
        for tool in scanner.tools:
            available = tool.is_available()
            status = "✓" if available else "✗"
            print(f"  {status} {tool.name}: {available}")
            
            if available:
                available_tools.append(tool.name)
        
        print(f"  ✓ Active tools: {len(available_tools)}")
        
        # Test mit temporärem Code
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Test-Vulnerability
            print("\\n🎯 Creating test vulnerability:")
            
            vuln_file = scanner.create_test_vulnerability(temp_path)
            print(f"  ✓ Created: {vuln_file.name}")
            
            # Zeige Inhalt
            content = vuln_file.read_text()
            lines = content.splitlines()[:10]  # Erste 10 Zeilen
            for i, line in enumerate(lines, 1):
                print(f"    {i:2}: {line}")
            
            # Führe Scan aus
            print("\\n🔍 Running security scan:")
            
            result = scanner.scan_generated_code(temp_path, "demo_scan")
            
            print(f"  ✓ Scan ID: {result.scan_id}")
            print(f"  ✓ Active tools: {result.active_tools}")
            print(f"  ✓ Scan status: {result.scan_status}")
            print(f"  ✓ Duration: {result.duration_seconds:.2f}s")
            
            # Zeige Findings
            print(f"\\n📊 Security findings: {len(result.findings)}")
            print(f"  ✓ Critical: {result.critical_count}")
            print(f"  ✓ High: {result.high_count}")
            print(f"  ✓ Medium: {result.medium_count}")
            print(f"  ✓ Low: {result.low_count}")
            print(f"  ✓ Secrets: {result.secrets_count}")
            
            # Zeige erste paar Findings
            for i, finding in enumerate(result.findings[:3], 1):
                print(f"\\n  Finding {i}: {finding.title}")
                print(f"    Rule: {finding.rule_id}")
                print(f"    Severity: {finding.severity.value}")
                print(f"    Category: {finding.category.value}")
                print(f"    File: {Path(finding.file_path).name}:{finding.line_number}")
                print(f"    Tool: {finding.tool_name}")
            
            # Prüfe Blocking
            print(f"\\n🚫 Blocking status:")
            print(f"  ✓ Is blocked: {result.is_blocked}")
            if result.is_blocked:
                print(f"  ✓ Block reason: {result.block_reason}")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Mindestens ein aktives Tool
            has_active_tool = len(result.active_tools) > 0
            
            # Rauscharme Regelbasis (wenig Low/Info)
            low_noise = (result.low_count + result.info_count) <= (result.critical_count + result.high_count + result.medium_count)
            
            # High und Secrets sind Hard-Fail
            hard_fail_logic = result.is_blocked if (result.high_count > 0 or result.secrets_count > 0) else True
            
            # Absichtlicher Unsicherheitsmarker wurde erkannt
            marker_detected = any("INSECURE_TEST_MARKER" in f.code_snippet for f in result.findings)
            
            print(f"  ✓ At least one active tool: {has_active_tool}")
            print(f"  ✓ Low-noise rule base: {low_noise}")
            print(f"  ✓ High/Secrets hard-fail: {hard_fail_logic}")
            print(f"  ✓ Test marker detected: {marker_detected}")
            
            return (has_active_tool and low_noise and 
                   hard_fail_logic and marker_detected)
    
    # Führe Demo aus
    try:
        result = demo_generated_code_security_scanner()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
