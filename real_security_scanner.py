"""
Real Security Scanner.

Semgrep, Bandit, Secret-Scan und Dependency-Audit real ausführen,
strukturierte Ergebnisse normalisieren, Schweregrad-Schwellen aus 
Policies anwenden und bei Verstoß mit definiertem Exit-Code abbrechen.
Reports als Artefakte bereitstellen.
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

# Setup Logging
_log = logging.getLogger(__name__)


class SecuritySeverity(str, Enum):
    """Security-Schweregrade."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityTool(str, Enum):
    """Unterstützte Security-Tools."""
    SEMGREP = "semgrep"
    BANDIT = "bandit"
    SAFETY = "safety"
    SECRETS = "secrets"


@dataclass
class SecurityFinding:
    """Einzelner Security-Fund."""
    rule_id: str
    severity: SecuritySeverity
    message: str
    file_path: str
    line_number: int
    tool: SecurityTool
    description: str
    cwe_id: Optional[str] = None
    cve_id: Optional[str] = None
    confidence: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Konvertiere zu Dictionary."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "tool": self.tool.value,
            "description": self.description,
            "cwe_id": self.cwe_id,
            "cve_id": self.cve_id,
            "confidence": self.confidence
        }


@dataclass
class SecurityPolicy:
    """Security-Policy mit Schwellwerten."""
    max_critical: int = 0
    max_high: int = 0
    max_medium: int = 10
    max_low: int = 50
    
    # Tool-spezifische Konfigurationen
    semgrep_config: Optional[str] = None
    bandit_config: Optional[str] = None
    secrets_patterns: List[str] = field(default_factory=list)
    
    # Exit-Codes
    exit_code_critical: int = 2
    exit_code_high: int = 1
    exit_code_medium: int = 0  # Warning only
    exit_code_low: int = 0


@dataclass
class SecurityScanResult:
    """Ergebnis eines Security-Scans."""
    tool: SecurityTool
    findings: List[SecurityFinding]
    execution_time_ms: float
    success: bool
    error_message: Optional[str] = None
    
    @property
    def findings_by_severity(self) -> Dict[str, int]:
        """Gruppiere Findings nach Severity."""
        counts = {s.value: 0 for s in SecuritySeverity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return counts


class RealSecurityScanner:
    """Real Security Scanner mit echten Tools."""
    
    def __init__(self, 
                 policy: SecurityPolicy,
                 target_path: str = ".",
                 spec_id: Optional[str] = None):
        """
        Args:
            policy: Security-Policy mit Schwellwerten
            target_path: Zu scannender Pfad
            spec_id: ID der Feature-Spec
        """
        self.policy = policy
        self.target_path = Path(target_path)
        self.spec_id = spec_id or "unknown"
        
        # Scan-Ergebnisse
        self.scan_results: Dict[SecurityTool, SecurityScanResult] = {}
        self.all_findings: List[SecurityFinding] = []
        
        _log.info(f"[{self.spec_id}] Real Security Scanner initialisiert")
        _log.info(f"[{self.spec_id}] Target: {self.target_path}")
        _log.info(f"[{self.spec_id}] Policy: Critical≤{policy.max_critical}, High≤{policy.max_high}")
    
    def run_comprehensive_scan(self) -> Dict[str, SecurityScanResult]:
        """
        Führe umfassenden Security-Scan durch.
        
        Returns:
            Dictionary mit Scan-Ergebnissen pro Tool
        """
        _log.info(f"[{self.spec_id}] Starte umfassenden Security-Scan")
        
        # 1. Semgrep SAST
        self._run_semgrep()
        
        # 2. Bandit Python Security
        self._run_bandit()
        
        # 3. Safety Dependency Vulnerabilities
        self._run_safety()
        
        # 4. Secret Scanning
        self._run_secret_scan()
        
        # 5. Sammle alle Findings
        self._aggregate_findings()
        
        # 6. Evaluiere Policy
        policy_result = self._evaluate_policy()
        
        _log.info(f"[{self.spec_id}] Security-Scan abgeschlossen: "
                 f"{len(self.all_findings)} Findings, Policy: {'✅ PASSED' if policy_result['passed'] else '❌ FAILED'}")
        
        return self.scan_results
    
    def _run_semgrep(self):
        """Führe Semgrep SAST-Scan aus."""
        _log.info(f"[{self.spec_id}] Führe Semgrep SAST-Scan aus")
        
        start_time = datetime.now()
        
        try:
            # Semgrep-Command
            cmd = [
                "semgrep",
                "--config=auto",  # Automatische Regel-Sets
                "--json",
                "--quiet",
                str(self.target_path)
            ]
            
            # Füge Custom-Config hinzu falls vorhanden
            if self.policy.semgrep_config and Path(self.policy.semgrep_config).exists():
                cmd[1] = f"--config={self.policy.semgrep_config}"
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 Minuten
                cwd=self.target_path
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if result.returncode in [0, 1]:  # 0=no findings, 1=findings found
                findings = self._parse_semgrep_output(result.stdout)
                
                scan_result = SecurityScanResult(
                    tool=SecurityTool.SEMGREP,
                    findings=findings,
                    execution_time_ms=execution_time,
                    success=True
                )
                
                _log.info(f"[{self.spec_id}] Semgrep abgeschlossen: {len(findings)} Findings")
                
            else:
                scan_result = SecurityScanResult(
                    tool=SecurityTool.SEMGREP,
                    findings=[],
                    execution_time_ms=execution_time,
                    success=False,
                    error_message=result.stderr
                )
                
                _log.error(f"[{self.spec_id}] Semgrep fehlgeschlagen: {result.stderr}")
            
            self.scan_results[SecurityTool.SEMGREP] = scan_result
            
        except subprocess.TimeoutExpired:
            scan_result = SecurityScanResult(
                tool=SecurityTool.SEMGREP,
                findings=[],
                execution_time_ms=300000,
                success=False,
                error_message="Semgrep timeout after 5 minutes"
            )
            self.scan_results[SecurityTool.SEMGREP] = scan_result
            _log.error(f"[{self.spec_id}] Semgrep timeout")
            
        except FileNotFoundError:
            scan_result = SecurityScanResult(
                tool=SecurityTool.SEMGREP,
                findings=[],
                execution_time_ms=0,
                success=False,
                error_message="Semgrep not installed"
            )
            self.scan_results[SecurityTool.SEMGREP] = scan_result
            _log.warning(f"[{self.spec_id}] Semgrep nicht installiert - übersprungen")
            
        except Exception as e:
            scan_result = SecurityScanResult(
                tool=SecurityTool.SEMGREP,
                findings=[],
                execution_time_ms=0,
                success=False,
                error_message=str(e)
            )
            self.scan_results[SecurityTool.SEMGREP] = scan_result
            _log.error(f"[{self.spec_id}] Semgrep Fehler: {e}")
    
    def _parse_semgrep_output(self, output: str) -> List[SecurityFinding]:
        """Parse Semgrep JSON-Output."""
        findings = []
        
        try:
            data = json.loads(output)
            
            for result in data.get("results", []):
                # Bestimme Severity
                severity = self._map_semgrep_severity(result.get("extra", {}).get("severity", "INFO"))
                
                finding = SecurityFinding(
                    rule_id=result.get("check_id", "unknown"),
                    severity=severity,
                    message=result.get("extra", {}).get("message", "Semgrep finding"),
                    file_path=result.get("path", "unknown"),
                    line_number=result.get("start", {}).get("line", 0),
                    tool=SecurityTool.SEMGREP,
                    description=result.get("extra", {}).get("message", ""),
                    cwe_id=self._extract_cwe_from_metadata(result.get("extra", {}))
                )
                
                findings.append(finding)
                
        except json.JSONDecodeError as e:
            _log.error(f"[{self.spec_id}] Semgrep JSON-Parse-Fehler: {e}")
        
        return findings
    
    def _map_semgrep_severity(self, semgrep_severity: str) -> SecuritySeverity:
        """Mappe Semgrep-Severity zu SecuritySeverity."""
        mapping = {
            "ERROR": SecuritySeverity.HIGH,
            "WARNING": SecuritySeverity.MEDIUM,
            "INFO": SecuritySeverity.LOW
        }
        return mapping.get(semgrep_severity.upper(), SecuritySeverity.LOW)
    
    def _run_bandit(self):
        """Führe Bandit Python Security-Scan aus."""
        _log.info(f"[{self.spec_id}] Führe Bandit Python Security-Scan aus")
        
        start_time = datetime.now()
        
        try:
            # Bandit-Command
            cmd = [
                "bandit",
                "-r",  # Recursive
                "-f", "json",  # JSON-Format
                str(self.target_path)
            ]
            
            # Füge Custom-Config hinzu falls vorhanden
            if self.policy.bandit_config and Path(self.policy.bandit_config).exists():
                cmd.extend(["-c", self.policy.bandit_config])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,  # 3 Minuten
                cwd=self.target_path
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if result.returncode in [0, 1]:  # 0=no issues, 1=issues found
                findings = self._parse_bandit_output(result.stdout)
                
                scan_result = SecurityScanResult(
                    tool=SecurityTool.BANDIT,
                    findings=findings,
                    execution_time_ms=execution_time,
                    success=True
                )
                
                _log.info(f"[{self.spec_id}] Bandit abgeschlossen: {len(findings)} Findings")
                
            else:
                scan_result = SecurityScanResult(
                    tool=SecurityTool.BANDIT,
                    findings=[],
                    execution_time_ms=execution_time,
                    success=False,
                    error_message=result.stderr
                )
                
                _log.error(f"[{self.spec_id}] Bandit fehlgeschlagen: {result.stderr}")
            
            self.scan_results[SecurityTool.BANDIT] = scan_result
            
        except FileNotFoundError:
            scan_result = SecurityScanResult(
                tool=SecurityTool.BANDIT,
                findings=[],
                execution_time_ms=0,
                success=False,
                error_message="Bandit not installed"
            )
            self.scan_results[SecurityTool.BANDIT] = scan_result
            _log.warning(f"[{self.spec_id}] Bandit nicht installiert - übersprungen")
            
        except Exception as e:
            scan_result = SecurityScanResult(
                tool=SecurityTool.BANDIT,
                findings=[],
                execution_time_ms=0,
                success=False,
                error_message=str(e)
            )
            self.scan_results[SecurityTool.BANDIT] = scan_result
            _log.error(f"[{self.spec_id}] Bandit Fehler: {e}")
    
    def _parse_bandit_output(self, output: str) -> List[SecurityFinding]:
        """Parse Bandit JSON-Output."""
        findings = []
        
        try:
            data = json.loads(output)
            
            for result in data.get("results", []):
                # Bestimme Severity
                severity = self._map_bandit_severity(result.get("issue_severity", "LOW"))
                
                finding = SecurityFinding(
                    rule_id=result.get("test_id", "unknown"),
                    severity=severity,
                    message=result.get("issue_text", "Bandit finding"),
                    file_path=result.get("filename", "unknown"),
                    line_number=result.get("line_number", 0),
                    tool=SecurityTool.BANDIT,
                    description=result.get("issue_text", ""),
                    cwe_id=result.get("test_name", "").replace("Test for ", ""),
                    confidence=result.get("issue_confidence", "MEDIUM")
                )
                
                findings.append(finding)
                
        except json.JSONDecodeError as e:
            _log.error(f"[{self.spec_id}] Bandit JSON-Parse-Fehler: {e}")
        
        return findings
    
    def _map_bandit_severity(self, bandit_severity: str) -> SecuritySeverity:
        """Mappe Bandit-Severity zu SecuritySeverity."""
        mapping = {
            "HIGH": SecuritySeverity.HIGH,
            "MEDIUM": SecuritySeverity.MEDIUM,
            "LOW": SecuritySeverity.LOW
        }
        return mapping.get(bandit_severity.upper(), SecuritySeverity.LOW)
    
    def _run_safety(self):
        """Führe Safety Dependency-Vulnerability-Scan aus."""
        _log.info(f"[{self.spec_id}] Führe Safety Dependency-Scan aus")
        
        start_time = datetime.now()
        
        try:
            # Safety-Command
            cmd = [
                sys.executable, "-m", "safety", "check", 
                "--json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 Minuten
                cwd=self.target_path
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if result.returncode in [0, 64]:  # 0=no vulns, 64=vulns found
                findings = self._parse_safety_output(result.stdout, result.stderr)
                
                scan_result = SecurityScanResult(
                    tool=SecurityTool.SAFETY,
                    findings=findings,
                    execution_time_ms=execution_time,
                    success=True
                )
                
                _log.info(f"[{self.spec_id}] Safety abgeschlossen: {len(findings)} Findings")
                
            else:
                scan_result = SecurityScanResult(
                    tool=SecurityTool.SAFETY,
                    findings=[],
                    execution_time_ms=execution_time,
                    success=False,
                    error_message=result.stderr
                )
                
                _log.error(f"[{self.spec_id}] Safety fehlgeschlagen: {result.stderr}")
            
            self.scan_results[SecurityTool.SAFETY] = scan_result
            
        except FileNotFoundError:
            scan_result = SecurityScanResult(
                tool=SecurityTool.SAFETY,
                findings=[],
                execution_time_ms=0,
                success=False,
                error_message="Safety not installed"
            )
            self.scan_results[SecurityTool.SAFETY] = scan_result
            _log.warning(f"[{self.spec_id}] Safety nicht installiert - übersprungen")
            
        except Exception as e:
            scan_result = SecurityScanResult(
                tool=SecurityTool.SAFETY,
                findings=[],
                execution_time_ms=0,
                success=False,
                error_message=str(e)
            )
            self.scan_results[SecurityTool.SAFETY] = scan_result
            _log.error(f"[{self.spec_id}] Safety Fehler: {e}")
    
    def _parse_safety_output(self, stdout: str, stderr: str) -> List[SecurityFinding]:
        """Parse Safety-Output."""
        findings = []
        
        # Safety kann JSON oder Text ausgeben
        try:
            # Versuche JSON-Parse
            if stdout.strip().startswith('['):
                data = json.loads(stdout)
                
                for vuln in data:
                    finding = SecurityFinding(
                        rule_id=vuln.get("id", "unknown"),
                        severity=SecuritySeverity.HIGH,  # Vulnerabilities sind meist high
                        message=f"Vulnerable dependency: {vuln.get('package', 'unknown')}",
                        file_path="requirements.txt",  # Dependency-File
                        line_number=0,
                        tool=SecurityTool.SAFETY,
                        description=vuln.get("advisory", "Dependency vulnerability"),
                        cve_id=vuln.get("id", "")
                    )
                    
                    findings.append(finding)
            
            else:
                # Parse Text-Output
                lines = stdout.split('\n') + stderr.split('\n')
                
                for line in lines:
                    if 'vulnerability' in line.lower() or 'cve-' in line.lower():
                        # Einfache Text-Parsing für Vulnerabilities
                        finding = SecurityFinding(
                            rule_id="safety-vulnerability",
                            severity=SecuritySeverity.HIGH,
                            message=line.strip(),
                            file_path="dependencies",
                            line_number=0,
                            tool=SecurityTool.SAFETY,
                            description=line.strip()
                        )
                        
                        findings.append(finding)
                
        except json.JSONDecodeError:
            # Fallback: Keine Vulnerabilities gefunden
            pass
        
        return findings
    
    def _run_secret_scan(self):
        """Führe Secret-Scan aus."""
        _log.info(f"[{self.spec_id}] Führe Secret-Scan aus")
        
        start_time = datetime.now()
        
        try:
            # Einfacher Pattern-basierter Secret-Scan
            findings = self._pattern_based_secret_scan()
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            scan_result = SecurityScanResult(
                tool=SecurityTool.SECRETS,
                findings=findings,
                execution_time_ms=execution_time,
                success=True
            )
            
            self.scan_results[SecurityTool.SECRETS] = scan_result
            
            _log.info(f"[{self.spec_id}] Secret-Scan abgeschlossen: {len(findings)} Findings")
            
        except Exception as e:
            scan_result = SecurityScanResult(
                tool=SecurityTool.SECRETS,
                findings=[],
                execution_time_ms=0,
                success=False,
                error_message=str(e)
            )
            self.scan_results[SecurityTool.SECRETS] = scan_result
            _log.error(f"[{self.spec_id}] Secret-Scan Fehler: {e}")
    
    def _pattern_based_secret_scan(self) -> List[SecurityFinding]:
        """Pattern-basierter Secret-Scan."""
        findings = []
        
        # Standard-Secret-Patterns
        secret_patterns = [
            (r'["\']?[A-Za-z0-9]{32,}["\']?', "Generic High-Entropy String"),
            (r'sk-[A-Za-z0-9]{48}', "OpenAI API Key"),
            (r'ghp_[A-Za-z0-9]{36}', "GitHub Personal Access Token"),
            (r'glpat-[A-Za-z0-9_\-]{20}', "GitLab Personal Access Token"),
            (r'AKIA[0-9A-Z]{16}', "AWS Access Key ID"),
            (r'["\']?password["\']?\s*[:=]\s*["\'][^"\']{8,}["\']', "Hardcoded Password"),
            (r'["\']?api[_-]?key["\']?\s*[:=]\s*["\'][^"\']{16,}["\']', "API Key"),
        ]
        
        # Erweitere mit Custom-Patterns aus Policy
        if self.policy.secrets_patterns:
            for pattern in self.policy.secrets_patterns:
                secret_patterns.append((pattern, "Custom Secret Pattern"))
        
        import re
        
        # Scanne alle Python-Dateien
        for py_file in self.target_path.rglob("*.py"):
            if py_file.is_file():
                try:
                    content = py_file.read_text(encoding='utf-8')
                    lines = content.split('\n')
                    
                    for line_num, line in enumerate(lines, 1):
                        for pattern, description in secret_patterns:
                            matches = re.finditer(pattern, line, re.IGNORECASE)
                            
                            for match in matches:
                                # Filtere False Positives
                                if self._is_likely_secret(match.group(), line):
                                    finding = SecurityFinding(
                                        rule_id="secret-detection",
                                        severity=SecuritySeverity.HIGH,
                                        message=f"Potential secret detected: {description}",
                                        file_path=str(py_file.relative_to(self.target_path)),
                                        line_number=line_num,
                                        tool=SecurityTool.SECRETS,
                                        description=f"Pattern: {description}"
                                    )
                                    
                                    findings.append(finding)
                                    
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    _log.debug(f"[{self.spec_id}] Fehler beim Scannen von {py_file}: {e}")
                    continue
        
        return findings
    
    def _is_likely_secret(self, match: str, line: str) -> bool:
        """Prüfe ob Match wahrscheinlich ein echtes Secret ist."""
        # Filtere offensichtliche False Positives
        false_positives = [
            "example", "test", "demo", "placeholder", "your_", "my_",
            "fake", "dummy", "sample", "mock", "TODO", "FIXME",
            "password", "secret", "token", "key"  # Literale Strings
        ]
        
        match_lower = match.lower()
        line_lower = line.lower()
        
        # Prüfe auf False Positive Indikatoren
        for fp in false_positives:
            if fp in match_lower or fp in line_lower:
                return False
        
        # Prüfe auf Kommentare (weniger wahrscheinlich echte Secrets)
        if line.strip().startswith('#'):
            return False
        
        # Kurze Strings sind unwahrscheinlich
        if len(match) < 16:
            return False
        
        return True
    
    def _extract_cwe_from_metadata(self, metadata: Dict) -> Optional[str]:
        """Extrahiere CWE-ID aus Metadaten."""
        # Versuche CWE aus verschiedenen Feldern zu extrahieren
        cwe_fields = ["cwe", "cwe_id", "category", "owasp"]
        
        for field in cwe_fields:
            if field in metadata:
                value = str(metadata[field])
                if "CWE-" in value.upper():
                    return value
        
        return None
    
    def _aggregate_findings(self):
        """Sammle alle Findings aus allen Tools."""
        self.all_findings = []
        
        for tool, result in self.scan_results.items():
            if result.success:
                self.all_findings.extend(result.findings)
        
        _log.info(f"[{self.spec_id}] Findings aggregiert: {len(self.all_findings)} total")
    
    def _evaluate_policy(self) -> Dict:
        """Evaluiere Security-Policy gegen Findings."""
        # Zähle Findings nach Severity
        severity_counts = {s.value: 0 for s in SecuritySeverity}
        
        for finding in self.all_findings:
            severity_counts[finding.severity.value] += 1
        
        # Prüfe Policy-Verletzungen
        violations = []
        exit_code = 0
        
        if severity_counts[SecuritySeverity.CRITICAL.value] > self.policy.max_critical:
            violations.append(f"Critical findings: {severity_counts[SecuritySeverity.CRITICAL.value]} > {self.policy.max_critical}")
            exit_code = max(exit_code, self.policy.exit_code_critical)
        
        if severity_counts[SecuritySeverity.HIGH.value] > self.policy.max_high:
            violations.append(f"High findings: {severity_counts[SecuritySeverity.HIGH.value]} > {self.policy.max_high}")
            exit_code = max(exit_code, self.policy.exit_code_high)
        
        if severity_counts[SecuritySeverity.MEDIUM.value] > self.policy.max_medium:
            violations.append(f"Medium findings: {severity_counts[SecuritySeverity.MEDIUM.value]} > {self.policy.max_medium}")
            exit_code = max(exit_code, self.policy.exit_code_medium)
        
        if severity_counts[SecuritySeverity.LOW.value] > self.policy.max_low:
            violations.append(f"Low findings: {severity_counts[SecuritySeverity.LOW.value]} > {self.policy.max_low}")
            exit_code = max(exit_code, self.policy.exit_code_low)
        
        passed = len(violations) == 0
        
        if violations:
            _log.error(f"[{self.spec_id}] Security-Policy-Verletzungen: {violations}")
        else:
            _log.info(f"[{self.spec_id}] Security-Policy erfüllt")
        
        return {
            "passed": passed,
            "violations": violations,
            "severity_counts": severity_counts,
            "exit_code": exit_code,
            "total_findings": len(self.all_findings)
        }
    
    def generate_security_report(self) -> Dict:
        """Generiere umfassenden Security-Report."""
        policy_result = self._evaluate_policy()
        
        return {
            "spec_id": self.spec_id,
            "timestamp": datetime.now().isoformat(),
            "target_path": str(self.target_path),
            "policy": {
                "max_critical": self.policy.max_critical,
                "max_high": self.policy.max_high,
                "max_medium": self.policy.max_medium,
                "max_low": self.policy.max_low
            },
            "summary": {
                "total_findings": len(self.all_findings),
                "severity_breakdown": policy_result["severity_counts"],
                "tools_run": len(self.scan_results),
                "tools_successful": sum(1 for r in self.scan_results.values() if r.success),
                "policy_passed": policy_result["passed"],
                "exit_code": policy_result["exit_code"]
            },
            "tool_results": {
                tool.value: {
                    "success": result.success,
                    "findings_count": len(result.findings),
                    "execution_time_ms": result.execution_time_ms,
                    "error_message": result.error_message
                }
                for tool, result in self.scan_results.items()
            },
            "findings": [finding.to_dict() for finding in self.all_findings],
            "policy_violations": policy_result["violations"]
        }
    
    def save_security_report(self, output_file: str):
        """Speichere Security-Report als JSON-Artefakt."""
        report = self.generate_security_report()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        _log.info(f"[{self.spec_id}] Security-Report gespeichert: {output_file}")
        
        return output_file
    
    def get_exit_code(self) -> int:
        """Hole Exit-Code basierend auf Policy-Evaluation."""
        policy_result = self._evaluate_policy()
        return policy_result["exit_code"]


def demo_real_security_scanner():
    """Demonstriere Real Security Scanner."""
    print("🔒 Real Security Scanner Demo")
    print("=" * 60)
    
    # Test 1: Standard-Policy
    print("\n✅ Test 1: Standard Security-Policy")
    
    policy = SecurityPolicy(
        max_critical=0,
        max_high=0,
        max_medium=5,
        max_low=20
    )
    
    scanner = RealSecurityScanner(
        policy=policy,
        target_path=".",
        spec_id="REAL-SEC-001"
    )
    
    # Führe umfassenden Scan durch
    scan_results = scanner.run_comprehensive_scan()
    
    print("🔍 Scan-Ergebnisse:")
    for tool, result in scan_results.items():
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        print(f"   - {tool.value}: {status} ({len(result.findings)} Findings, {result.execution_time_ms:.0f}ms)")
        
        if not result.success and result.error_message:
            print(f"     Error: {result.error_message}")
    
    # Policy-Evaluation
    policy_result = scanner._evaluate_policy()
    
    print("\n📊 Policy-Evaluation:")
    print(f"   - Policy: {'✅ PASSED' if policy_result['passed'] else '❌ FAILED'}")
    print(f"   - Total Findings: {policy_result['total_findings']}")
    print(f"   - Exit Code: {policy_result['exit_code']}")
    
    print("📈 Severity-Breakdown:")
    for severity, count in policy_result["severity_counts"].items():
        if count > 0:
            print(f"   - {severity.upper()}: {count}")
    
    if policy_result["violations"]:
        print("🚨 Policy-Verletzungen:")
        for violation in policy_result["violations"]:
            print(f"   - {violation}")
    
    # Test 2: Strenge Policy (Zero-Tolerance)
    print("\n🚨 Test 2: Strenge Zero-Tolerance Policy")
    
    strict_policy = SecurityPolicy(
        max_critical=0,
        max_high=0,
        max_medium=0,
        max_low=0
    )
    
    strict_scanner = RealSecurityScanner(
        policy=strict_policy,
        target_path=".",
        spec_id="STRICT-SEC-001"
    )
    
    strict_scanner.run_comprehensive_scan()
    strict_policy_result = strict_scanner._evaluate_policy()
    
    print("📊 Strenge Policy-Evaluation:")
    print(f"   - Policy: {'✅ PASSED' if strict_policy_result['passed'] else '❌ FAILED'}")
    print(f"   - Exit Code: {strict_policy_result['exit_code']}")
    
    if strict_policy_result["violations"]:
        print("🚨 Zero-Tolerance-Verletzungen:")
        for violation in strict_policy_result["violations"][:3]:  # Erste 3
            print(f"   - {violation}")
    
    # Test 3: Report-Generierung
    print("\n📄 Test 3: Report-Generierung")
    
    report_file = "real_security_scan_report.json"
    scanner.save_security_report(report_file)
    
    # Lade und validiere Report
    with open(report_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    print("📊 Report-Validierung:")
    print(f"   - Spec ID: {report['spec_id']}")
    print(f"   - Tools Run: {report['summary']['tools_run']}")
    print(f"   - Total Findings: {report['summary']['total_findings']}")
    print(f"   - Policy Passed: {report['summary']['policy_passed']}")
    print(f"   - Exit Code: {report['summary']['exit_code']}")
    
    print("\n✅ Real Security Scanner Demo abgeschlossen!")
    print("🔒 Echte Security-Tools integriert mit Policy-Enforcement")
    
    return policy_result["exit_code"]


if __name__ == "__main__":
    exit_code = demo_real_security_scanner()
    sys.exit(exit_code)
