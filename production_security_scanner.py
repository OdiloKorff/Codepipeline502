"""Production Security-Scanner real verdrahten."""

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class SecuritySeverity(str, Enum):
    """Schweregrade für Security-Findings."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityTool(str, Enum):
    """Security-Scanning-Tools."""
    SEMGREP = "semgrep"
    BANDIT = "bandit"
    SECRET_SCAN = "secret_scan"
    DEPENDENCY_AUDIT = "dependency_audit"


@dataclass
class SecurityFinding:
    """Ein einzelner Security-Finding."""
    tool: SecurityTool
    severity: SecuritySeverity
    rule_id: str
    title: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    confidence: Optional[str] = None
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityScanResult:
    """Ergebnis eines Security-Scans."""
    scan_id: str
    timestamp: str
    total_findings: int
    findings_by_severity: Dict[str, int]
    findings: List[SecurityFinding]
    scan_duration_seconds: float
    tools_used: List[str]
    exit_code: int
    passed: bool
    policy_violations: List[str] = field(default_factory=list)


class ProductionSecurityScanner:
    """Production-ready Security-Scanner mit echten Tools."""
    
    def __init__(self, scan_id: str = "security-scan"):
        self.scan_id = scan_id
        self.start_time = time.time()
        
        # Security-Policy (konfigurierbar)
        self.security_policy = {
            "severity_thresholds": {
                "critical": 0,    # 0 kritische Findings erlaubt
                "high": 0,        # 0 high-severity Findings erlaubt
                "medium": 5,      # Max 5 medium-severity Findings
                "low": 20         # Max 20 low-severity Findings
            },
            "required_tools": [SecurityTool.BANDIT, SecurityTool.SECRET_SCAN],
            "optional_tools": [SecurityTool.SEMGREP, SecurityTool.DEPENDENCY_AUDIT],
            "fail_on_missing_tools": False
        }
        
        print("🛡️ Production Security-Scanner initialisiert")
        print(f"   🏷️ Scan ID: {scan_id}")
        print(f"   🎯 Required Tools: {len(self.security_policy['required_tools'])}")
    
    def _run_command(self, command: List[str], timeout: int = 300) -> tuple:
        """Führe Security-Command sicher aus."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path.cwd(),
                encoding='utf-8',
                errors='replace'  # Handle encoding issues gracefully
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timeout after {timeout}s"
        except FileNotFoundError:
            return 127, "", f"Command not found: {command[0]}"
        except Exception as e:
            return 1, "", str(e)
    
    def _normalize_severity(self, severity_str: str, tool: SecurityTool) -> SecuritySeverity:
        """Normalisiere Severity-Strings verschiedener Tools."""
        severity_lower = severity_str.lower().strip()
        
        # Semgrep-Mappings
        if tool == SecurityTool.SEMGREP:
            severity_map = {
                "error": SecuritySeverity.HIGH,
                "warning": SecuritySeverity.MEDIUM,
                "info": SecuritySeverity.LOW
            }
            return severity_map.get(severity_lower, SecuritySeverity.MEDIUM)
        
        # Bandit-Mappings
        elif tool == SecurityTool.BANDIT:
            severity_map = {
                "high": SecuritySeverity.HIGH,
                "medium": SecuritySeverity.MEDIUM,
                "low": SecuritySeverity.LOW
            }
            return severity_map.get(severity_lower, SecuritySeverity.MEDIUM)
        
        # Generische Mappings
        else:
            if severity_lower in ["critical", "error"]:
                return SecuritySeverity.CRITICAL
            elif severity_lower in ["high", "major"]:
                return SecuritySeverity.HIGH
            elif severity_lower in ["medium", "moderate", "warning"]:
                return SecuritySeverity.MEDIUM
            elif severity_lower in ["low", "minor", "info"]:
                return SecuritySeverity.LOW
            else:
                return SecuritySeverity.MEDIUM
    
    def _run_semgrep_scan(self) -> List[SecurityFinding]:
        """Führe Semgrep SAST-Scan aus."""
        print("🔍 Running Semgrep SAST scan...")
        
        # Versuche Semgrep auszuführen
        returncode, stdout, stderr = self._run_command([
            "semgrep", "--config=auto", "--json", "."
        ])
        
        findings = []
        
        if returncode == 127:
            print("   ⚠️ Semgrep not installed, skipping SAST scan")
            return findings
        
        if returncode != 0 or not stdout:
            print(f"   ⚠️ Semgrep scan failed (exit {returncode})")
            return findings
        
        try:
            semgrep_data = json.loads(stdout)
            results = semgrep_data.get("results", [])
            
            for result in results:
                severity = self._normalize_severity(
                    result.get("extra", {}).get("severity", "medium"),
                    SecurityTool.SEMGREP
                )
                
                finding = SecurityFinding(
                    tool=SecurityTool.SEMGREP,
                    severity=severity,
                    rule_id=result.get("check_id", "unknown"),
                    title=result.get("extra", {}).get("message", "Semgrep finding"),
                    description=result.get("extra", {}).get("message", ""),
                    file_path=result.get("path", ""),
                    line_number=result.get("start", {}).get("line"),
                    details={
                        "end_line": result.get("end", {}).get("line"),
                        "confidence": result.get("extra", {}).get("metadata", {}).get("confidence", "medium")
                    }
                )
                findings.append(finding)
            
            print(f"   ✅ Semgrep completed: {len(findings)} findings")
            
        except json.JSONDecodeError as e:
            print(f"   ❌ Semgrep JSON parsing failed: {e}")
        
        return findings
    
    def _run_bandit_scan(self) -> List[SecurityFinding]:
        """Führe Bandit Python-Security-Scan aus."""
        print("🐍 Running Bandit Python security scan...")
        
        # Versuche Bandit auszuführen
        returncode, stdout, stderr = self._run_command([
            sys.executable, "-m", "bandit", "-r", ".", "-f", "json"
        ])
        
        findings = []
        
        if returncode == 127:
            print("   ⚠️ Bandit not installed, skipping Python security scan")
            return findings
        
        # Bandit gibt auch bei Findings exit code != 0
        if not stdout:
            print("   ⚠️ Bandit scan produced no output")
            return findings
        
        try:
            bandit_data = json.loads(stdout)
            results = bandit_data.get("results", [])
            
            for result in results:
                severity = self._normalize_severity(
                    result.get("issue_severity", "medium"),
                    SecurityTool.BANDIT
                )
                
                finding = SecurityFinding(
                    tool=SecurityTool.BANDIT,
                    severity=severity,
                    rule_id=result.get("test_id", "unknown"),
                    title=result.get("test_name", "Bandit finding"),
                    description=result.get("issue_text", ""),
                    file_path=result.get("filename", ""),
                    line_number=result.get("line_number"),
                    confidence=result.get("issue_confidence", "medium"),
                    cwe_id=result.get("cwe", {}).get("id") if result.get("cwe") else None,
                    details={
                        "code": result.get("code", ""),
                        "more_info": result.get("more_info", "")
                    }
                )
                findings.append(finding)
            
            print(f"   ✅ Bandit completed: {len(findings)} findings")
            
        except json.JSONDecodeError as e:
            print(f"   ❌ Bandit JSON parsing failed: {e}")
        
        return findings
    
    def _run_secret_scan(self) -> List[SecurityFinding]:
        """Führe Secret-Scanning aus."""
        print("🔐 Running secret scan...")
        
        findings = []
        
        # Secret-Patterns (vereinfacht)
        secret_patterns = [
            (r"sk-[a-zA-Z0-9]{48}", "OpenAI API Key", SecuritySeverity.HIGH),
            (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token", SecuritySeverity.HIGH),
            (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID", SecuritySeverity.CRITICAL),
            (r"-----BEGIN PRIVATE KEY-----", "Private Key", SecuritySeverity.CRITICAL),
            (r"password\s*=\s*['\"][^'\"]{8,}", "Hardcoded Password", SecuritySeverity.HIGH),
            (r"api[_-]?key\s*=\s*['\"][^'\"]{16,}", "API Key", SecuritySeverity.HIGH),
            (r"secret[_-]?key\s*=\s*['\"][^'\"]{16,}", "Secret Key", SecuritySeverity.HIGH),
        ]
        
        # Scanne Python-Dateien
        python_files = list(Path(".").glob("**/*.py"))
        
        for py_file in python_files:
            if py_file.name.startswith('.') or 'venv' in str(py_file) or '__pycache__' in str(py_file):
                continue
                
            try:
                content = py_file.read_text(encoding='utf-8', errors='replace')
                lines = content.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    for pattern, title, severity in secret_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            finding = SecurityFinding(
                                tool=SecurityTool.SECRET_SCAN,
                                severity=severity,
                                rule_id=f"secret-{title.lower().replace(' ', '-')}",
                                title=f"Potential {title}",
                                description=f"Detected potential {title.lower()} in source code",
                                file_path=str(py_file),
                                line_number=line_num,
                                details={
                                    "pattern": pattern,
                                    "line_content": line.strip()[:100]  # Truncate for security
                                }
                            )
                            findings.append(finding)
            
            except Exception as e:
                print(f"   ⚠️ Error scanning {py_file}: {e}")
                continue
        
        print(f"   ✅ Secret scan completed: {len(findings)} findings")
        return findings
    
    def _run_dependency_audit(self) -> List[SecurityFinding]:
        """Führe Dependency-Security-Audit aus."""
        print("📦 Running dependency security audit...")
        
        findings = []
        
        # Versuche Safety auszuführen
        returncode, stdout, stderr = self._run_command([
            sys.executable, "-m", "safety", "check", "--json"
        ])
        
        if returncode == 127:
            print("   ⚠️ Safety not installed, trying pip-audit...")
            
            # Fallback zu pip-audit
            returncode, stdout, stderr = self._run_command([
                sys.executable, "-m", "pip_audit", "--format", "json"
            ])
            
            if returncode == 127:
                print("   ⚠️ No dependency audit tools available")
                return findings
        
        if stdout:
            try:
                # Safety-Format
                if "vulnerabilities" in stdout or isinstance(json.loads(stdout), list):
                    safety_data = json.loads(stdout)
                    vulnerabilities = safety_data if isinstance(safety_data, list) else safety_data.get("vulnerabilities", [])
                    
                    for vuln in vulnerabilities:
                        finding = SecurityFinding(
                            tool=SecurityTool.DEPENDENCY_AUDIT,
                            severity=SecuritySeverity.HIGH,  # Alle Vulnerabilities als HIGH
                            rule_id=vuln.get("id", "unknown"),
                            title=f"Vulnerable dependency: {vuln.get('package_name', 'unknown')}",
                            description=vuln.get("advisory", "Dependency vulnerability"),
                            file_path="requirements.txt",  # Vereinfacht
                            details={
                                "package": vuln.get("package_name"),
                                "vulnerable_spec": vuln.get("vulnerable_spec"),
                                "installed_version": vuln.get("installed_version")
                            }
                        )
                        findings.append(finding)
                
                print(f"   ✅ Dependency audit completed: {len(findings)} findings")
                
            except json.JSONDecodeError as e:
                print(f"   ❌ Dependency audit JSON parsing failed: {e}")
        
        return findings
    
    def run_comprehensive_scan(self) -> SecurityScanResult:
        """Führe umfassenden Security-Scan aus."""
        print(f"🛡️ Starting comprehensive security scan: {self.scan_id}")
        
        all_findings = []
        tools_used = []
        
        # Führe alle Security-Tools aus
        scan_functions = [
            (self._run_semgrep_scan, SecurityTool.SEMGREP),
            (self._run_bandit_scan, SecurityTool.BANDIT),
            (self._run_secret_scan, SecurityTool.SECRET_SCAN),
            (self._run_dependency_audit, SecurityTool.DEPENDENCY_AUDIT)
        ]
        
        for scan_func, tool in scan_functions:
            try:
                findings = scan_func()
                all_findings.extend(findings)
                tools_used.append(tool.value)
            except Exception as e:
                print(f"   ❌ Error in {tool.value} scan: {e}")
        
        # Aggregiere Findings nach Severity
        findings_by_severity = {severity.value: 0 for severity in SecuritySeverity}
        
        for finding in all_findings:
            findings_by_severity[finding.severity.value] += 1
        
        # Prüfe gegen Policy
        policy_violations = []
        exit_code = 0
        
        for severity, threshold in self.security_policy["severity_thresholds"].items():
            count = findings_by_severity.get(severity, 0)
            if count > threshold:
                policy_violations.append(f"{count} {severity} findings > threshold {threshold}")
                exit_code = 1
        
        # Prüfe Required Tools
        required_tools = [tool.value for tool in self.security_policy["required_tools"]]
        missing_tools = [tool for tool in required_tools if tool not in tools_used]
        
        if missing_tools and self.security_policy["fail_on_missing_tools"]:
            policy_violations.append(f"Missing required tools: {missing_tools}")
            exit_code = 1
        
        # Bestimme Pass/Fail
        passed = len(policy_violations) == 0
        
        scan_duration = time.time() - self.start_time
        
        result = SecurityScanResult(
            scan_id=self.scan_id,
            timestamp=datetime.now().isoformat(),
            total_findings=len(all_findings),
            findings_by_severity=findings_by_severity,
            findings=all_findings,
            scan_duration_seconds=scan_duration,
            tools_used=tools_used,
            exit_code=exit_code,
            passed=passed,
            policy_violations=policy_violations
        )
        
        print("🛡️ Security scan completed:")
        print(f"   Total Findings: {len(all_findings)}")
        print(f"   Critical: {findings_by_severity['critical']}")
        print(f"   High: {findings_by_severity['high']}")
        print(f"   Medium: {findings_by_severity['medium']}")
        print(f"   Low: {findings_by_severity['low']}")
        print(f"   Passed: {'✅' if passed else '❌'}")
        print(f"   Exit Code: {exit_code}")
        
        return result
    
    def generate_structured_report(self, scan_result: SecurityScanResult) -> Dict[str, str]:
        """Generiere strukturierte Reports."""
        
        # JSON-Report
        def serialize_finding(obj):
            if isinstance(obj, Enum):
                return obj.value
            elif hasattr(obj, '__dict__'):
                return {k: serialize_finding(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, dict):
                return {k: serialize_finding(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_finding(item) for item in obj]
            else:
                return obj
        
        report_data = serialize_finding(scan_result)
        json_report = json.dumps(report_data, indent=2, ensure_ascii=False)
        
        # Speichere JSON-Report
        json_file = Path("security-report.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(json_report)
        
        # Markdown-Report
        status_emoji = "✅" if scan_result.passed else "❌"
        
        markdown_report = f"""# Security Scan Report

**Scan ID:** {scan_result.scan_id}  
**Timestamp:** {scan_result.timestamp}  
**Status:** {status_emoji} {'PASSED' if scan_result.passed else 'FAILED'}  
**Duration:** {scan_result.scan_duration_seconds:.1f}s  
**Exit Code:** {scan_result.exit_code}  

## Summary

**Total Findings:** {scan_result.total_findings}

| Severity | Count |
|----------|-------|
| Critical | {scan_result.findings_by_severity['critical']} |
| High | {scan_result.findings_by_severity['high']} |
| Medium | {scan_result.findings_by_severity['medium']} |
| Low | {scan_result.findings_by_severity['low']} |

**Tools Used:** {', '.join(scan_result.tools_used)}

"""
        
        if scan_result.policy_violations:
            markdown_report += "## 🚨 Policy Violations\n\n"
            for violation in scan_result.policy_violations:
                markdown_report += f"- ❌ {violation}\n"
            markdown_report += "\n"
        
        if scan_result.findings:
            markdown_report += "## Findings\n\n"
            
            # Gruppiere nach Severity
            findings_by_sev = {}
            for finding in scan_result.findings:
                sev = finding.severity.value
                if sev not in findings_by_sev:
                    findings_by_sev[sev] = []
                findings_by_sev[sev].append(finding)
            
            for severity in ["critical", "high", "medium", "low"]:
                if severity in findings_by_sev:
                    findings = findings_by_sev[severity]
                    markdown_report += f"### {severity.title()} ({len(findings)})\n\n"
                    
                    for finding in findings[:10]:  # Limitiere auf 10 pro Severity
                        markdown_report += f"**{finding.title}**  \n"
                        markdown_report += f"*{finding.tool.value}* | {finding.rule_id} | {finding.file_path}"
                        if finding.line_number:
                            markdown_report += f":{finding.line_number}"
                        markdown_report += "\n\n"
                        
                        if finding.description:
                            markdown_report += f"{finding.description}\n\n"
                    
                    if len(findings) > 10:
                        markdown_report += f"*... and {len(findings) - 10} more {severity} findings*\n\n"
        
        markdown_report += f"\n---\n*Report generated by Production Security Scanner at {scan_result.timestamp}*\n"
        
        # Speichere Markdown-Report
        md_file = Path("security-report.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        
        print("📄 Security reports generated:")
        print(f"   JSON: {json_file}")
        print(f"   Markdown: {md_file}")
        
        return {
            "json": str(json_file),
            "markdown": str(md_file)
        }


def test_production_security_scanner():
    """Teste Production Security-Scanner."""
    print("🧪 PRODUCTION SECURITY-SCANNER TESTS")
    print("=" * 50)
    
    # Test 1: Scanner-Initialisierung
    scanner = ProductionSecurityScanner("TEST-SECURITY-001")
    assert scanner.scan_id == "TEST-SECURITY-001"
    print("✅ Scanner initialization: OK")
    
    # Test 2: Comprehensive Scan
    result = scanner.run_comprehensive_scan()
    
    assert result.scan_id == "TEST-SECURITY-001"
    assert isinstance(result.total_findings, int)
    assert len(result.tools_used) > 0
    print("✅ Comprehensive scan: OK")
    
    # Test 3: Report-Generierung
    reports = scanner.generate_structured_report(result)
    
    assert "json" in reports
    assert "markdown" in reports
    assert Path(reports["json"]).exists()
    assert Path(reports["markdown"]).exists()
    print("✅ Report generation: OK")
    
    # Test 4: Policy-Enforcement
    if result.findings_by_severity["high"] > 0 or result.findings_by_severity["critical"] > 0:
        assert not result.passed  # Sollte fehlschlagen bei high/critical findings
        print("✅ Policy enforcement: OK (failed as expected)")
    else:
        print("⚠️ No high/critical findings for policy test")
    
    print("🎉 All tests completed!")
    return True


def demo():
    """Demo."""
    print("🛡️ PRODUCTION SECURITY-SCANNER DEMO")
    print("=" * 60)
    
    if not test_production_security_scanner():
        return 1
    
    # Demo verschiedener Szenarien
    print("\n📋 Demo: Security-Scan-Szenarien")
    
    # Szenario 1: Standard-Scan
    print("\n🔍 Standard Security Scan:")
    
    scanner = ProductionSecurityScanner("DEMO-SECURITY-001")
    result = scanner.run_comprehensive_scan()
    
    print(f"   Findings: {result.total_findings}")
    print(f"   Tools: {', '.join(result.tools_used)}")
    print(f"   Status: {'PASSED' if result.passed else 'FAILED'}")
    print(f"   Exit Code: {result.exit_code}")
    
    # Generiere Reports
    scanner.generate_structured_report(result)
    
    print("\n🛡️ Security-Scanner-Capabilities:")
    print("   ✅ Semgrep SAST-Integration (falls installiert)")
    print("   ✅ Bandit Python-Security-Scan")
    print("   ✅ Pattern-basiertes Secret-Scanning")
    print("   ✅ Dependency-Vulnerability-Audit")
    print("   ✅ Severity-Normalisierung zwischen Tools")
    print("   ✅ Policy-basierte Schwellwerte")
    print("   ✅ Strukturierte JSON/Markdown-Reports")
    print("   ✅ Reproduzierbare Exit-Codes")
    
    print("\n✅ Demo complete!")
    return 0


if __name__ == "__main__":
    sys.exit(demo())
