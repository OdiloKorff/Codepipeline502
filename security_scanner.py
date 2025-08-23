"""
Unified Security Scanner für CodePipeline.

Integriert mehrere Security-Tools in einen einheitlichen Scanner:
- Semgrep (SAST)
- Bandit (Python Security)  
- Secret Scanning (gitleaks/truffleHog)
- Software Composition Analysis (safety/audit)

Erzeugt einheitliche JSON-Ausgabe mit konfigurierbaren Schwellwerten.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Optional import für Static Analysis Baselines
try:
    from static_analysis_baselines import StaticAnalysisBaselines
    BASELINES_AVAILABLE = True
except ImportError:
    BASELINES_AVAILABLE = False


class SeverityLevel(str, Enum):
    """Severity levels für Security Findings."""
    NONE = "none"
    LOW = "low" 
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityFinding(BaseModel):
    """Einzelnes Security Finding."""
    tool: str = Field(..., description="Name des Tools das den Fund gemacht hat")
    rule_id: str = Field(..., description="ID der Regel/des Checks")
    severity: SeverityLevel = Field(..., description="Schweregrad des Funds")
    message: str = Field(..., description="Beschreibung des Problems")
    file: Optional[str] = Field(None, description="Betroffene Datei")
    line: Optional[int] = Field(None, description="Betroffene Zeile")
    column: Optional[int] = Field(None, description="Betroffene Spalte")
    cwe: Optional[str] = Field(None, description="CWE-Referenz falls verfügbar")
    confidence: Optional[str] = Field(None, description="Confidence Level")
    raw_output: Optional[Dict[str, Any]] = Field(None, description="Raw Tool Output")


class SecurityScanResult(BaseModel):
    """Gesamtergebnis eines Security Scans."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    scan_duration_seconds: float = Field(..., description="Dauer des Scans in Sekunden")
    threshold: SeverityLevel = Field(..., description="Konfigurierter Schwellwert")
    passed: bool = Field(..., description="Ob der Scan den Schwellwert erfüllt")
    exit_code: int = Field(..., description="Exit Code (0=Pass, >0=Fail)")
    
    # Tool-spezifische Ergebnisse
    semgrep: Dict[str, Any] = Field(default_factory=dict)
    bandit: Dict[str, Any] = Field(default_factory=dict)
    secrets: Dict[str, Any] = Field(default_factory=dict)
    dependencies: Dict[str, Any] = Field(default_factory=dict)
    
    # Konsolidierte Findings
    findings: List[SecurityFinding] = Field(default_factory=list)
    
    # Statistiken
    total_findings: int = Field(default=0)
    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    failing_severity: Optional[SeverityLevel] = Field(None, description="Höchster Schweregrad der den Threshold überschreitet")


class SecurityScanner:
    """Unified Security Scanner mit mehreren Tools."""
    
    def __init__(
        self, 
        threshold: SeverityLevel = SeverityLevel.MEDIUM,
        target_path: str = ".",
        output_file: Optional[str] = None,
        baseline_profile: Optional[str] = None
    ):
        self.threshold = threshold
        self.target_path = Path(target_path)
        self.output_file = output_file
        self.findings: List[SecurityFinding] = []
        self.baseline_profile = baseline_profile
        
        # Initialisiere Static Analysis Baselines falls verfügbar
        if BASELINES_AVAILABLE and baseline_profile:
            self.baselines = StaticAnalysisBaselines()
            if not self.baselines.set_active_profile(baseline_profile):
                self.baselines = None
        else:
            self.baselines = None
        
        # Severity-Mapping für Vergleiche
        self.severity_order = {
            SeverityLevel.NONE: 0,
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2, 
            SeverityLevel.HIGH: 3,
            SeverityLevel.CRITICAL: 4
        }
    
    def run_full_scan(self) -> SecurityScanResult:
        """Führe kompletten Security Scan aus."""
        start_time = datetime.now()
        
        print(f"🔍 Starte Security Scan mit Threshold: {self.threshold}")
        print(f"📁 Target: {self.target_path}")
        
        # Führe alle Scans aus
        semgrep_result = self._run_semgrep()
        bandit_result = self._run_bandit()
        secrets_result = self._run_secret_scan()
        deps_result = self._run_dependency_scan()
        
        # Berechne Ergebnisse
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Bestimme ob Scan bestanden
        failing_severity = self._get_failing_severity()
        passed = failing_severity is None
        exit_code = 0 if passed else 1
        
        # Erstelle Ergebnis
        result = SecurityScanResult(
            scan_duration_seconds=duration,
            threshold=self.threshold,
            passed=passed,
            exit_code=exit_code,
            semgrep=semgrep_result,
            bandit=bandit_result,
            secrets=secrets_result,
            dependencies=deps_result,
            findings=self.findings,
            total_findings=len(self.findings),
            findings_by_severity=self._count_findings_by_severity(),
            failing_severity=failing_severity
        )
        
        # Speichere Ergebnis falls gewünscht
        if self.output_file:
            self._save_result(result)
        
        return result
    
    def _run_semgrep(self) -> Dict[str, Any]:
        """Führe Semgrep SAST Scan aus."""
        print("  🔍 Semgrep SAST Scan...")
        
        try:
            # Versuche Semgrep mit OWASP und Python Security Rules
            cmd = [
                "semgrep",
                "--config=p/owasp-top-ten",
                "--config=p/security-audit", 
                "--json",
                "--quiet",
                str(self.target_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 Minuten Timeout
            )
            
            if result.returncode in [0, 1]:  # 0=no findings, 1=findings found
                try:
                    semgrep_data = json.loads(result.stdout) if result.stdout.strip() else {"results": []}
                except json.JSONDecodeError:
                    semgrep_data = {"results": [], "error": "Invalid JSON output"}
            else:
                semgrep_data = {
                    "error": f"Semgrep failed with code {result.returncode}",
                    "stderr": result.stderr,
                    "results": []
                }
            
            # Konvertiere Semgrep Findings
            self._process_semgrep_findings(semgrep_data.get("results", []))
            
            return {
                "status": "completed" if result.returncode in [0, 1] else "failed",
                "findings_count": len(semgrep_data.get("results", [])),
                "raw_data": semgrep_data
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Semgrep scan timed out"}
        except FileNotFoundError:
            return {"status": "not_installed", "error": "Semgrep not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _run_bandit(self) -> Dict[str, Any]:
        """Führe Bandit Python Security Scan aus."""
        print("  🐍 Bandit Python Security Scan...")
        
        try:
            cmd = [
                "bandit",
                "-r", str(self.target_path),
                "-f", "json",
                "--quiet"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Bandit gibt verschiedene Exit Codes zurück
            if result.returncode in [0, 1]:  # 0=no issues, 1=issues found
                try:
                    bandit_data = json.loads(result.stdout) if result.stdout.strip() else {"results": []}
                except json.JSONDecodeError:
                    bandit_data = {"results": [], "error": "Invalid JSON output"}
            else:
                bandit_data = {
                    "error": f"Bandit failed with code {result.returncode}",
                    "stderr": result.stderr,
                    "results": []
                }
            
            # Konvertiere Bandit Findings
            self._process_bandit_findings(bandit_data.get("results", []))
            
            return {
                "status": "completed" if result.returncode in [0, 1] else "failed", 
                "findings_count": len(bandit_data.get("results", [])),
                "raw_data": bandit_data
            }
            
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Bandit scan timed out"}
        except FileNotFoundError:
            return {"status": "not_installed", "error": "Bandit not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _run_secret_scan(self) -> Dict[str, Any]:
        """Führe Secret Scanning aus."""
        print("  🔐 Secret Scanning...")
        
        # Versuche zuerst gitleaks, dann truffleHog, dann einfache Regex
        for tool in ["gitleaks", "trufflehog"]:
            try:
                if tool == "gitleaks":
                    result = self._run_gitleaks()
                else:
                    result = self._run_trufflehog()
                
                if result["status"] != "not_installed":
                    return result
            except Exception:
                continue
        
        # Fallback: Einfache Regex-basierte Suche
        return self._run_regex_secret_scan()
    
    def _run_gitleaks(self) -> Dict[str, Any]:
        """Führe gitleaks Secret Scan aus."""
        try:
            cmd = [
                "gitleaks", 
                "detect",
                "--source", str(self.target_path),
                "--format", "json",
                "--no-git"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode in [0, 1]:  # 0=no secrets, 1=secrets found
                try:
                    gitleaks_data = json.loads(result.stdout) if result.stdout.strip() else []
                except json.JSONDecodeError:
                    gitleaks_data = []
            else:
                return {
                    "status": "failed",
                    "error": f"gitleaks failed with code {result.returncode}",
                    "stderr": result.stderr
                }
            
            # Konvertiere gitleaks Findings
            self._process_gitleaks_findings(gitleaks_data)
            
            return {
                "status": "completed",
                "tool": "gitleaks",
                "findings_count": len(gitleaks_data),
                "raw_data": gitleaks_data
            }
            
        except FileNotFoundError:
            return {"status": "not_installed", "error": "gitleaks not found"}
    
    def _run_trufflehog(self) -> Dict[str, Any]:
        """Führe truffleHog Secret Scan aus.""" 
        try:
            cmd = [
                "trufflehog",
                "filesystem",
                str(self.target_path),
                "--json"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse JSON Lines output
            findings = []
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    try:
                        findings.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            
            # Konvertiere truffleHog Findings
            self._process_trufflehog_findings(findings)
            
            return {
                "status": "completed",
                "tool": "trufflehog",
                "findings_count": len(findings),
                "raw_data": findings
            }
            
        except FileNotFoundError:
            return {"status": "not_installed", "error": "trufflehog not found"}
    
    def _run_regex_secret_scan(self) -> Dict[str, Any]:
        """Einfache Regex-basierte Secret-Suche als Fallback."""
        import re
        
        secret_patterns = {
            "api_key": re.compile(r'(?i)api[_-]?key["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})'),
            "password": re.compile(r'(?i)password["\s]*[:=]["\s]*["\']([^"\']{8,})["\']'),
            "token": re.compile(r'(?i)token["\s]*[:=]["\s]*["\']([a-zA-Z0-9_-]{20,})["\']'),
            "secret": re.compile(r'(?i)secret["\s]*[:=]["\s]*["\']([a-zA-Z0-9_-]{16,})["\']'),
        }
        
        findings = []
        
        try:
            for file_path in self.target_path.rglob("*.py"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        for secret_type, pattern in secret_patterns.items():
                            for match in pattern.finditer(content):
                                line_num = content[:match.start()].count('\n') + 1
                                
                                finding = SecurityFinding(
                                    tool="regex_secrets",
                                    rule_id=f"secret_{secret_type}",
                                    severity=SeverityLevel.HIGH,
                                    message=f"Potential {secret_type} found in code",
                                    file=str(file_path.relative_to(self.target_path)),
                                    line=line_num,
                                    raw_output={"match": match.group(0)[:50] + "..."}
                                )
                                
                                findings.append(finding)
                                self.findings.append(finding)
                    except Exception:
                        continue
            
            return {
                "status": "completed",
                "tool": "regex_secrets",
                "findings_count": len(findings),
                "raw_data": [f.model_dump() for f in findings]
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _run_dependency_scan(self) -> Dict[str, Any]:
        """Führe Software Composition Analysis aus."""
        print("  📦 Dependency Security Scan...")
        
        # Versuche verschiedene Tools
        results = {}
        
        # 1. safety (Python)
        safety_result = self._run_safety()
        results["safety"] = safety_result
        
        # 2. pip-audit (Python)
        audit_result = self._run_pip_audit()
        results["pip_audit"] = audit_result
        
        # 3. Lizenz-Check
        license_result = self._check_licenses()
        results["licenses"] = license_result
        
        return {
            "status": "completed",
            "tools": results,
            "total_findings": sum(r.get("findings_count", 0) for r in results.values())
        }
    
    def _run_safety(self) -> Dict[str, Any]:
        """Führe safety vulnerability check aus."""
        try:
            cmd = ["safety", "check", "--json"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode in [0, 64]:  # 0=no vulns, 64=vulns found
                try:
                    safety_data = json.loads(result.stdout) if result.stdout.strip() else []
                except json.JSONDecodeError:
                    safety_data = []
            else:
                return {
                    "status": "failed",
                    "error": f"safety failed with code {result.returncode}"
                }
            
            # Konvertiere safety Findings
            self._process_safety_findings(safety_data)
            
            return {
                "status": "completed",
                "findings_count": len(safety_data),
                "raw_data": safety_data
            }
            
        except FileNotFoundError:
            return {"status": "not_installed", "error": "safety not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _run_pip_audit(self) -> Dict[str, Any]:
        """Führe pip-audit aus."""
        try:
            cmd = ["pip-audit", "--format=json"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode in [0, 1]:
                try:
                    audit_data = json.loads(result.stdout) if result.stdout.strip() else {"vulnerabilities": []}
                except json.JSONDecodeError:
                    audit_data = {"vulnerabilities": []}
            else:
                return {
                    "status": "failed", 
                    "error": f"pip-audit failed with code {result.returncode}"
                }
            
            # Konvertiere pip-audit Findings
            vulnerabilities = audit_data.get("vulnerabilities", [])
            self._process_pip_audit_findings(vulnerabilities)
            
            return {
                "status": "completed",
                "findings_count": len(vulnerabilities),
                "raw_data": audit_data
            }
            
        except FileNotFoundError:
            return {"status": "not_installed", "error": "pip-audit not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _check_licenses(self) -> Dict[str, Any]:
        """Prüfe Lizenz-Compliance."""
        try:
            # Verwende dependency_security.py falls verfügbar
            from dependency_security import _iter_packages
            
            packages = _iter_packages()
            
            # Definiere problematische Lizenzen
            problematic_licenses = {
                "GPL-3.0", "AGPL-3.0", "SSPL-1.0", "BUSL-1.1",
                "Commons Clause", "Elastic License"
            }
            
            violations = []
            for name, version, license_str in packages:
                if license_str and any(prob in license_str for prob in problematic_licenses):
                    finding = SecurityFinding(
                        tool="license_check",
                        rule_id="problematic_license",
                        severity=SeverityLevel.MEDIUM,
                        message=f"Problematic license detected: {license_str}",
                        file=f"package:{name}@{version}",
                        raw_output={"package": name, "version": version, "license": license_str}
                    )
                    violations.append(finding)
                    self.findings.append(finding)
            
            return {
                "status": "completed",
                "total_packages": len(packages),
                "violations": len(violations),
                "findings_count": len(violations),
                "raw_data": {"packages": packages[:10], "violations": [v.dict() for v in violations]}
            }
            
        except ImportError:
            return {"status": "not_available", "error": "dependency_security module not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    # Finding Processors
    def _process_semgrep_findings(self, results: List[Dict[str, Any]]) -> None:
        """Konvertiere Semgrep Findings zu SecurityFinding."""
        for result in results:
            severity = self._map_semgrep_severity(result.get("extra", {}).get("severity", "INFO"))
            
            finding = SecurityFinding(
                tool="semgrep",
                rule_id=result.get("check_id", "unknown"),
                severity=severity,
                message=result.get("extra", {}).get("message", "Security issue detected"),
                file=result.get("path"),
                line=result.get("start", {}).get("line"),
                column=result.get("start", {}).get("col"),
                cwe=result.get("extra", {}).get("metadata", {}).get("cwe"),
                confidence=result.get("extra", {}).get("metadata", {}).get("confidence"),
                raw_output=result
            )
            
            self.findings.append(finding)
    
    def _process_bandit_findings(self, results: List[Dict[str, Any]]) -> None:
        """Konvertiere Bandit Findings zu SecurityFinding."""
        for result in results:
            severity = self._map_bandit_severity(result.get("issue_severity", "LOW"))
            
            finding = SecurityFinding(
                tool="bandit",
                rule_id=result.get("test_id", "unknown"),
                severity=severity,
                message=result.get("issue_text", "Security issue detected"),
                file=result.get("filename"),
                line=result.get("line_number"),
                confidence=result.get("issue_confidence"),
                raw_output=result
            )
            
            self.findings.append(finding)
    
    def _process_gitleaks_findings(self, results: List[Dict[str, Any]]) -> None:
        """Konvertiere gitleaks Findings zu SecurityFinding."""
        for result in results:
            finding = SecurityFinding(
                tool="gitleaks",
                rule_id=result.get("RuleID", "secret_detected"),
                severity=SeverityLevel.HIGH,  # Secrets sind immer HIGH
                message=f"Secret detected: {result.get('Description', 'Unknown secret type')}",
                file=result.get("File"),
                line=result.get("StartLine"),
                raw_output=result
            )
            
            self.findings.append(finding)
    
    def _process_trufflehog_findings(self, results: List[Dict[str, Any]]) -> None:
        """Konvertiere truffleHog Findings zu SecurityFinding."""
        for result in results:
            detector_name = result.get("DetectorName", "unknown")
            
            finding = SecurityFinding(
                tool="trufflehog",
                rule_id=f"secret_{detector_name}",
                severity=SeverityLevel.HIGH,
                message=f"Secret detected by {detector_name}",
                file=result.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("file"),
                line=result.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("line"),
                raw_output=result
            )
            
            self.findings.append(finding)
    
    def _process_safety_findings(self, results: List[Dict[str, Any]]) -> None:
        """Konvertiere safety Findings zu SecurityFinding.""" 
        for result in results:
            # safety hat verschiedene Formate je nach Version
            vuln = result.get("vulnerability", result)
            
            finding = SecurityFinding(
                tool="safety",
                rule_id=vuln.get("id", "unknown"),
                severity=SeverityLevel.HIGH,  # Vulnerabilities sind HIGH
                message=f"Vulnerable package: {result.get('package', 'unknown')} - {vuln.get('advisory', 'No advisory')}",
                file=f"package:{result.get('package', 'unknown')}@{result.get('installed_version', 'unknown')}",
                raw_output=result
            )
            
            self.findings.append(finding)
    
    def _process_pip_audit_findings(self, vulnerabilities: List[Dict[str, Any]]) -> None:
        """Konvertiere pip-audit Findings zu SecurityFinding."""
        for vuln in vulnerabilities:
            package = vuln.get("package", "unknown")
            installed_version = vuln.get("installed_version", "unknown")
            
            finding = SecurityFinding(
                tool="pip_audit",
                rule_id=vuln.get("id", "unknown"),
                severity=SeverityLevel.HIGH,
                message=f"Vulnerable package: {package}@{installed_version} - {vuln.get('description', 'No description')}",
                file=f"package:{package}@{installed_version}",
                raw_output=vuln
            )
            
            self.findings.append(finding)
    
    # Severity Mapping
    def _map_semgrep_severity(self, semgrep_severity: str) -> SeverityLevel:
        """Mappe Semgrep Severity zu SeverityLevel."""
        mapping = {
            "ERROR": SeverityLevel.HIGH,
            "WARNING": SeverityLevel.MEDIUM,
            "INFO": SeverityLevel.LOW
        }
        return mapping.get(semgrep_severity.upper(), SeverityLevel.LOW)
    
    def _map_bandit_severity(self, bandit_severity: str) -> SeverityLevel:
        """Mappe Bandit Severity zu SeverityLevel."""
        mapping = {
            "HIGH": SeverityLevel.HIGH,
            "MEDIUM": SeverityLevel.MEDIUM,
            "LOW": SeverityLevel.LOW
        }
        return mapping.get(bandit_severity.upper(), SeverityLevel.LOW)
    
    # Utility Methods
    def _get_failing_severity(self) -> Optional[SeverityLevel]:
        """Bestimme höchsten Schweregrad der den Threshold überschreitet."""
        threshold_level = self.severity_order[self.threshold]
        
        failing_levels = []
        for finding in self.findings:
            finding_level = self.severity_order[finding.severity]
            if finding_level >= threshold_level:
                failing_levels.append(finding.severity)
        
        if not failing_levels:
            return None
        
        # Gib höchsten Schweregrad zurück
        return max(failing_levels, key=lambda s: self.severity_order[s])
    
    def _count_findings_by_severity(self) -> Dict[str, int]:
        """Zähle Findings nach Schweregrad."""
        counts = {level.value: 0 for level in SeverityLevel}
        
        for finding in self.findings:
            counts[finding.severity.value] += 1
        
        return counts
    
    def _save_result(self, result: SecurityScanResult) -> None:
        """Speichere Scan-Ergebnis in Datei."""
        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
        
        print(f"📄 Scan-Ergebnis gespeichert: {output_path}")


def main():
    """CLI Entry Point für Security Scanner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified Security Scanner")
    parser.add_argument("--threshold", 
                       choices=[level.value for level in SeverityLevel],
                       default=SeverityLevel.MEDIUM.value,
                       help="Security threshold level")
    parser.add_argument("--target", default=".", help="Target path to scan")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--baseline-profile", choices=["security", "development", "cicd"],
                       help="Static analysis baseline profile")
    
    args = parser.parse_args()
    
    # Erstelle Scanner
    scanner = SecurityScanner(
        threshold=SeverityLevel(args.threshold),
        target_path=args.target,
        output_file=args.output,
        baseline_profile=args.baseline_profile
    )
    
    # Führe Scan aus
    result = scanner.run_full_scan()
    
    # Ausgabe
    print("\n" + "="*60)
    print("🔒 SECURITY SCAN ERGEBNIS")
    print("="*60)
    print(f"Threshold: {result.threshold}")
    print(f"Dauer: {result.scan_duration_seconds:.2f}s")
    print(f"Gesamt Findings: {result.total_findings}")
    
    for severity, count in result.findings_by_severity.items():
        if count > 0:
            print(f"  {severity.upper()}: {count}")
    
    if result.passed:
        print("✅ BESTANDEN")
    else:
        print(f"❌ FEHLGESCHLAGEN (Höchster Schweregrad: {result.failing_severity})")
        
        if args.verbose:
            print("\nFailing Findings:")
            threshold_level = scanner.severity_order[scanner.threshold]
            for finding in result.findings:
                finding_level = scanner.severity_order[finding.severity]
                if finding_level >= threshold_level:
                    print(f"  - [{finding.severity}] {finding.tool}: {finding.message}")
                    if finding.file:
                        print(f"    📁 {finding.file}:{finding.line or '?'}")
    
    # JSON Output falls gewünscht
    if not args.output:
        print("\n📄 JSON Output:")
        print(json.dumps(result.model_dump(), indent=2))
    
    # Exit mit entsprechendem Code
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
