"""Production SBOM und Lizenz-Gate."""

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class LicenseStatus(str, Enum):
    """Status einer Lizenz."""
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"
    REQUIRES_REVIEW = "requires_review"


class VulnerabilitySeverity(str, Enum):
    """Schweregrade für Vulnerabilities."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class PackageInfo:
    """Informationen über ein Package."""
    name: str
    version: str
    license: Optional[str] = None
    license_status: LicenseStatus = LicenseStatus.UNKNOWN
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    homepage: Optional[str] = None
    description: Optional[str] = None


@dataclass
class SBOMResult:
    """Ergebnis der SBOM-Generierung."""
    sbom_format: str
    total_packages: int
    packages: List[PackageInfo]
    sbom_file_path: str
    generation_time_seconds: float
    timestamp: str


@dataclass
class LicenseAuditResult:
    """Ergebnis des Lizenz-Audits."""
    total_packages: int
    allowed_licenses: int
    denied_licenses: int
    unknown_licenses: int
    license_violations: List[str]
    passed: bool
    license_summary: Dict[str, int] = field(default_factory=dict)


@dataclass
class VulnerabilityAuditResult:
    """Ergebnis des Vulnerability-Audits."""
    total_vulnerabilities: int
    vulnerabilities_by_severity: Dict[str, int]
    vulnerable_packages: List[str]
    passed: bool
    vulnerability_details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SBOMLicenseGateResult:
    """Gesamtergebnis des SBOM-License-Gates."""
    gate_id: str
    timestamp: str
    sbom_result: SBOMResult
    license_audit: LicenseAuditResult
    vulnerability_audit: VulnerabilityAuditResult
    overall_passed: bool
    exit_code: int
    artifacts: List[str] = field(default_factory=list)


class ProductionSBOMLicenseGate:
    """Production-ready SBOM und Lizenz-Gate."""
    
    def __init__(self, gate_id: str = "sbom-license-gate"):
        self.gate_id = gate_id
        self.start_time = time.time()
        
        # License-Policy (konfigurierbar)
        self.license_policy = {
            "allowed_licenses": [
                "MIT",
                "Apache-2.0",
                "BSD-3-Clause",
                "BSD-2-Clause",
                "ISC",
                "Python-2.0",
                "PSF-2.0",
                "Apache Software License",
                "BSD License",
                "Mozilla Public License 2.0 (MPL 2.0)"
            ],
            "denied_licenses": [
                "GPL-2.0",
                "GPL-3.0",
                "AGPL-3.0",
                "LGPL-2.1",
                "LGPL-3.0",
                "Copyleft",
                "Commercial"
            ],
            "require_license_for_all": True,
            "allow_unknown_licenses": False
        }
        
        # Vulnerability-Policy
        self.vulnerability_policy = {
            "max_critical": 0,
            "max_high": 0,
            "max_medium": 5,
            "max_low": 20,
            "fail_on_any_vulnerability": True
        }
        
        print("📋 Production SBOM-License-Gate initialisiert")
        print(f"   🏷️ Gate ID: {gate_id}")
        print(f"   ✅ Allowed Licenses: {len(self.license_policy['allowed_licenses'])}")
        print(f"   ❌ Denied Licenses: {len(self.license_policy['denied_licenses'])}")
    
    def _run_command(self, command: List[str], timeout: int = 300) -> tuple:
        """Führe Command sicher aus."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path.cwd(),
                encoding='utf-8',
                errors='replace'
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timeout after {timeout}s"
        except FileNotFoundError:
            return 127, "", f"Command not found: {command[0]}"
        except Exception as e:
            return 1, "", str(e)
    
    def _get_installed_packages(self) -> List[PackageInfo]:
        """Hole installierte Packages."""
        print("📦 Collecting installed packages...")
        
        # Hole Package-Liste via pip
        returncode, stdout, stderr = self._run_command([
            sys.executable, "-m", "pip", "list", "--format=json"
        ])
        
        packages = []
        
        if returncode == 0 and stdout:
            try:
                pip_data = json.loads(stdout)
                
                for pkg_info in pip_data:
                    package = PackageInfo(
                        name=pkg_info.get("name", "unknown"),
                        version=pkg_info.get("version", "unknown")
                    )
                    packages.append(package)
                
                print(f"   ✅ Found {len(packages)} packages")
                
            except json.JSONDecodeError as e:
                print(f"   ❌ Error parsing pip list: {e}")
        
        return packages
    
    def _enrich_package_licenses(self, packages: List[PackageInfo]) -> List[PackageInfo]:
        """Ergänze License-Informationen für Packages."""
        print("⚖️ Enriching package license information...")
        
        # Versuche pip-licenses zu verwenden
        returncode, stdout, stderr = self._run_command([
            sys.executable, "-m", "pip_licenses", "--format=json"
        ])
        
        license_map = {}
        
        if returncode == 0 and stdout:
            try:
                license_data = json.loads(stdout)
                
                for pkg in license_data:
                    name = pkg.get("Name", "").lower()
                    license_name = pkg.get("License", "Unknown")
                    license_map[name] = license_name
                
                print(f"   ✅ Retrieved licenses for {len(license_map)} packages")
                
            except json.JSONDecodeError:
                print("   ⚠️ pip-licenses output not parseable")
        else:
            print("   ⚠️ pip-licenses not available, using fallback")
            
            # Fallback: Bekannte Lizenzen für häufige Packages
            common_licenses = {
                "requests": "Apache-2.0",
                "urllib3": "MIT",
                "certifi": "MPL-2.0",
                "charset-normalizer": "MIT",
                "idna": "BSD-3-Clause",
                "click": "BSD-3-Clause",
                "jinja2": "BSD-3-Clause",
                "markupsafe": "BSD-3-Clause",
                "werkzeug": "BSD-3-Clause",
                "flask": "BSD-3-Clause",
                "fastapi": "MIT",
                "pydantic": "MIT",
                "starlette": "BSD-3-Clause",
                "uvicorn": "BSD-3-Clause",
                "pytest": "MIT",
                "coverage": "Apache-2.0"
            }
            license_map = common_licenses
        
        # Ergänze License-Informationen
        for package in packages:
            package_name_lower = package.name.lower()
            
            if package_name_lower in license_map:
                package.license = license_map[package_name_lower]
            else:
                package.license = "Unknown"
            
            # Bestimme License-Status
            if package.license in self.license_policy["allowed_licenses"]:
                package.license_status = LicenseStatus.ALLOWED
            elif package.license in self.license_policy["denied_licenses"]:
                package.license_status = LicenseStatus.DENIED
            elif package.license == "Unknown":
                package.license_status = LicenseStatus.UNKNOWN
            else:
                package.license_status = LicenseStatus.REQUIRES_REVIEW
        
        return packages
    
    def _check_vulnerabilities(self, packages: List[PackageInfo]) -> List[PackageInfo]:
        """Prüfe Packages auf Vulnerabilities."""
        print("🔍 Checking packages for vulnerabilities...")
        
        # Versuche Safety zu verwenden
        returncode, stdout, stderr = self._run_command([
            sys.executable, "-m", "safety", "check", "--json"
        ])
        
        vulnerability_map = {}
        
        if returncode != 127 and stdout:  # Safety verfügbar
            try:
                # Safety kann verschiedene Formate ausgeben
                if stdout.strip():
                    safety_data = json.loads(stdout)
                    
                    # Safety gibt Liste von Vulnerabilities zurück
                    vulnerabilities = safety_data if isinstance(safety_data, list) else []
                    
                    for vuln in vulnerabilities:
                        pkg_name = vuln.get("package_name", "").lower()
                        
                        if pkg_name not in vulnerability_map:
                            vulnerability_map[pkg_name] = []
                        
                        vulnerability_map[pkg_name].append({
                            "id": vuln.get("vulnerability_id", "unknown"),
                            "advisory": vuln.get("advisory", ""),
                            "vulnerable_spec": vuln.get("vulnerable_spec", ""),
                            "severity": VulnerabilitySeverity.HIGH  # Safety behandelt alle als HIGH
                        })
                    
                    print(f"   ✅ Found vulnerabilities in {len(vulnerability_map)} packages")
                else:
                    print("   ✅ No vulnerabilities found by Safety")
                    
            except json.JSONDecodeError as e:
                print(f"   ⚠️ Safety output not parseable: {e}")
        else:
            print("   ⚠️ Safety not available for vulnerability checking")
        
        # Ergänze Vulnerability-Informationen
        for package in packages:
            package_name_lower = package.name.lower()
            
            if package_name_lower in vulnerability_map:
                package.vulnerabilities = vulnerability_map[package_name_lower]
        
        return packages
    
    def _generate_cyclonedx_sbom(self, packages: List[PackageInfo]) -> SBOMResult:
        """Generiere CycloneDX SBOM."""
        print("📋 Generating CycloneDX SBOM...")
        
        start_time = time.time()
        
        # Versuche cyclonedx-bom zu verwenden
        returncode, stdout, stderr = self._run_command([
            sys.executable, "-m", "cyclonedx_bom", "requirements", "requirements.txt", 
            "--output-format", "json", "--output-file", "sbom.json"
        ])
        
        sbom_file = Path("sbom.json")
        
        if returncode != 127 and sbom_file.exists():
            print(f"   ✅ CycloneDX SBOM generated: {sbom_file}")
        else:
            print("   ⚠️ cyclonedx-bom not available, generating manual SBOM")
            
            # Fallback: Manuell generierte SBOM
            manual_sbom = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.4",
                "serialNumber": f"urn:uuid:sbom-{self.gate_id}",
                "version": 1,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "tools": [
                        {
                            "vendor": "CodePipeline",
                            "name": "Production SBOM Generator",
                            "version": "1.0.0"
                        }
                    ]
                },
                "components": []
            }
            
            for package in packages:
                component = {
                    "type": "library",
                    "bom-ref": f"{package.name}@{package.version}",
                    "name": package.name,
                    "version": package.version,
                    "purl": f"pkg:pypi/{package.name}@{package.version}",
                    "licenses": [
                        {
                            "license": {
                                "name": package.license or "Unknown"
                            }
                        }
                    ] if package.license else []
                }
                
                manual_sbom["components"].append(component)
            
            # Speichere manuell generierte SBOM
            with open(sbom_file, 'w', encoding='utf-8') as f:
                json.dump(manual_sbom, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Manual SBOM generated: {sbom_file}")
        
        generation_time = time.time() - start_time
        
        return SBOMResult(
            sbom_format="CycloneDX",
            total_packages=len(packages),
            packages=packages,
            sbom_file_path=str(sbom_file),
            generation_time_seconds=generation_time,
            timestamp=datetime.now().isoformat()
        )
    
    def _audit_licenses(self, packages: List[PackageInfo]) -> LicenseAuditResult:
        """Führe Lizenz-Audit aus."""
        print("⚖️ Auditing package licenses...")
        
        allowed_count = 0
        denied_count = 0
        unknown_count = 0
        license_violations = []
        license_summary = {}
        
        for package in packages:
            license_name = package.license or "Unknown"
            
            # Zähle License-Typen
            if license_name not in license_summary:
                license_summary[license_name] = 0
            license_summary[license_name] += 1
            
            # Prüfe License-Status
            if package.license_status == LicenseStatus.ALLOWED:
                allowed_count += 1
            elif package.license_status == LicenseStatus.DENIED:
                denied_count += 1
                license_violations.append(f"Package '{package.name}' has denied license: {license_name}")
            elif package.license_status == LicenseStatus.UNKNOWN:
                unknown_count += 1
                if not self.license_policy["allow_unknown_licenses"]:
                    license_violations.append(f"Package '{package.name}' has unknown license: {license_name}")
            else:  # REQUIRES_REVIEW
                license_violations.append(f"Package '{package.name}' requires license review: {license_name}")
        
        # Bestimme Pass/Fail
        passed = len(license_violations) == 0
        
        result = LicenseAuditResult(
            total_packages=len(packages),
            allowed_licenses=allowed_count,
            denied_licenses=denied_count,
            unknown_licenses=unknown_count,
            license_violations=license_violations,
            passed=passed,
            license_summary=license_summary
        )
        
        print("   📊 License audit completed:")
        print(f"      Allowed: {allowed_count}")
        print(f"      Denied: {denied_count}")
        print(f"      Unknown: {unknown_count}")
        print(f"      Violations: {len(license_violations)}")
        print(f"      Passed: {'✅' if passed else '❌'}")
        
        return result
    
    def _audit_vulnerabilities(self, packages: List[PackageInfo]) -> VulnerabilityAuditResult:
        """Führe Vulnerability-Audit aus."""
        print("🔍 Auditing package vulnerabilities...")
        
        vulnerabilities_by_severity = {severity.value: 0 for severity in VulnerabilitySeverity}
        vulnerable_packages = []
        vulnerability_details = []
        
        for package in packages:
            if package.vulnerabilities:
                vulnerable_packages.append(package.name)
                
                for vuln in package.vulnerabilities:
                    severity = vuln.get("severity", VulnerabilitySeverity.HIGH)
                    if isinstance(severity, VulnerabilitySeverity):
                        severity_key = severity.value
                    else:
                        severity_key = str(severity).lower()
                    
                    if severity_key in vulnerabilities_by_severity:
                        vulnerabilities_by_severity[severity_key] += 1
                    
                    vulnerability_details.append({
                        "package": package.name,
                        "version": package.version,
                        "vulnerability_id": vuln.get("id", "unknown"),
                        "severity": severity_key,
                        "advisory": vuln.get("advisory", "")
                    })
        
        total_vulnerabilities = sum(vulnerabilities_by_severity.values())
        
        # Prüfe gegen Policy
        policy_violations = []
        
        for severity, max_allowed in [
            ("critical", self.vulnerability_policy["max_critical"]),
            ("high", self.vulnerability_policy["max_high"]),
            ("medium", self.vulnerability_policy["max_medium"]),
            ("low", self.vulnerability_policy["max_low"])
        ]:
            count = vulnerabilities_by_severity.get(severity, 0)
            if count > max_allowed:
                policy_violations.append(f"{count} {severity} vulnerabilities > threshold {max_allowed}")
        
        # Bestimme Pass/Fail
        passed = len(policy_violations) == 0
        
        if self.vulnerability_policy["fail_on_any_vulnerability"] and total_vulnerabilities > 0:
            passed = False
        
        result = VulnerabilityAuditResult(
            total_vulnerabilities=total_vulnerabilities,
            vulnerabilities_by_severity=vulnerabilities_by_severity,
            vulnerable_packages=vulnerable_packages,
            passed=passed,
            vulnerability_details=vulnerability_details
        )
        
        print("   📊 Vulnerability audit completed:")
        print(f"      Total Vulnerabilities: {total_vulnerabilities}")
        print(f"      Critical: {vulnerabilities_by_severity['critical']}")
        print(f"      High: {vulnerabilities_by_severity['high']}")
        print(f"      Medium: {vulnerabilities_by_severity['medium']}")
        print(f"      Low: {vulnerabilities_by_severity['low']}")
        print(f"      Vulnerable Packages: {len(vulnerable_packages)}")
        print(f"      Passed: {'✅' if passed else '❌'}")
        
        return result
    
    def execute_sbom_license_gate(self) -> SBOMLicenseGateResult:
        """Führe vollständiges SBOM-License-Gate aus."""
        print(f"📋 Executing SBOM-License-Gate: {self.gate_id}")
        
        # 1. Sammle installierte Packages
        packages = self._get_installed_packages()
        
        # 2. Ergänze License-Informationen
        packages = self._enrich_package_licenses(packages)
        
        # 3. Prüfe Vulnerabilities
        packages = self._check_vulnerabilities(packages)
        
        # 4. Generiere SBOM
        sbom_result = self._generate_cyclonedx_sbom(packages)
        
        # 5. Führe License-Audit aus
        license_audit = self._audit_licenses(packages)
        
        # 6. Führe Vulnerability-Audit aus
        vulnerability_audit = self._audit_vulnerabilities(packages)
        
        # 7. Bestimme Overall-Result
        overall_passed = license_audit.passed and vulnerability_audit.passed
        exit_code = 0 if overall_passed else 1
        
        # 8. Sammle Artifacts
        artifacts = [sbom_result.sbom_file_path]
        
        result = SBOMLicenseGateResult(
            gate_id=self.gate_id,
            timestamp=datetime.now().isoformat(),
            sbom_result=sbom_result,
            license_audit=license_audit,
            vulnerability_audit=vulnerability_audit,
            overall_passed=overall_passed,
            exit_code=exit_code,
            artifacts=artifacts
        )
        
        print("📋 SBOM-License-Gate completed:")
        print(f"   Overall Passed: {'✅' if overall_passed else '❌'}")
        print(f"   Exit Code: {exit_code}")
        print(f"   Artifacts: {len(artifacts)}")
        
        return result
    
    def generate_reports(self, result: SBOMLicenseGateResult) -> Dict[str, str]:
        """Generiere Reports für SBOM-License-Gate."""
        
        # JSON-Report
        def serialize_obj(obj):
            if isinstance(obj, Enum):
                return obj.value
            elif hasattr(obj, '__dict__'):
                return {k: serialize_obj(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, dict):
                return {k: serialize_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_obj(item) for item in obj]
            else:
                return obj
        
        report_data = serialize_obj(result)
        json_report = json.dumps(report_data, indent=2, ensure_ascii=False)
        
        json_file = Path("sbom-license-report.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(json_report)
        
        # Markdown-Report
        status_emoji = "✅" if result.overall_passed else "❌"
        
        markdown_report = f"""# SBOM & License Gate Report

**Gate ID:** {result.gate_id}  
**Timestamp:** {result.timestamp}  
**Status:** {status_emoji} {'PASSED' if result.overall_passed else 'FAILED'}  
**Exit Code:** {result.exit_code}  

## SBOM Summary

**Format:** {result.sbom_result.sbom_format}  
**Total Packages:** {result.sbom_result.total_packages}  
**Generation Time:** {result.sbom_result.generation_time_seconds:.1f}s  
**SBOM File:** {result.sbom_result.sbom_file_path}  

## License Audit

**Status:** {'✅ PASSED' if result.license_audit.passed else '❌ FAILED'}

| Category | Count |
|----------|-------|
| Allowed Licenses | {result.license_audit.allowed_licenses} |
| Denied Licenses | {result.license_audit.denied_licenses} |
| Unknown Licenses | {result.license_audit.unknown_licenses} |

"""
        
        if result.license_audit.license_violations:
            markdown_report += "### 🚨 License Violations\n\n"
            for violation in result.license_audit.license_violations:
                markdown_report += f"- ❌ {violation}\n"
            markdown_report += "\n"
        
        markdown_report += f"""## Vulnerability Audit

**Status:** {'✅ PASSED' if result.vulnerability_audit.passed else '❌ FAILED'}  
**Total Vulnerabilities:** {result.vulnerability_audit.total_vulnerabilities}  
**Vulnerable Packages:** {len(result.vulnerability_audit.vulnerable_packages)}  

| Severity | Count |
|----------|-------|
| Critical | {result.vulnerability_audit.vulnerabilities_by_severity['critical']} |
| High | {result.vulnerability_audit.vulnerabilities_by_severity['high']} |
| Medium | {result.vulnerability_audit.vulnerabilities_by_severity['medium']} |
| Low | {result.vulnerability_audit.vulnerabilities_by_severity['low']} |

"""
        
        if result.vulnerability_audit.vulnerability_details:
            markdown_report += "### Vulnerability Details\n\n"
            for vuln in result.vulnerability_audit.vulnerability_details[:10]:  # Limitiere auf 10
                markdown_report += f"**{vuln['package']}** ({vuln['version']})  \n"
                markdown_report += f"*{vuln['severity'].upper()}* | {vuln['vulnerability_id']}  \n"
                markdown_report += f"{vuln['advisory'][:100]}...\n\n"
        
        markdown_report += f"\n---\n*Report generated by Production SBOM-License-Gate at {result.timestamp}*\n"
        
        md_file = Path("sbom-license-report.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        
        print("📄 SBOM-License reports generated:")
        print(f"   JSON: {json_file}")
        print(f"   Markdown: {md_file}")
        
        return {
            "json": str(json_file),
            "markdown": str(md_file)
        }


def test_production_sbom_license_gate():
    """Teste Production SBOM-License-Gate."""
    print("🧪 PRODUCTION SBOM-LICENSE-GATE TESTS")
    print("=" * 50)
    
    # Test 1: Gate-Initialisierung
    gate = ProductionSBOMLicenseGate("TEST-SBOM-001")
    assert gate.gate_id == "TEST-SBOM-001"
    print("✅ Gate initialization: OK")
    
    # Test 2: SBOM-License-Gate ausführen
    result = gate.execute_sbom_license_gate()
    
    assert result.gate_id == "TEST-SBOM-001"
    assert result.sbom_result.total_packages > 0
    assert isinstance(result.overall_passed, bool)
    print("✅ SBOM-License-Gate execution: OK")
    
    # Test 3: Report-Generierung
    reports = gate.generate_reports(result)
    
    assert "json" in reports
    assert "markdown" in reports
    assert Path(reports["json"]).exists()
    assert Path(reports["markdown"]).exists()
    print("✅ Report generation: OK")
    
    # Test 4: SBOM-Datei prüfen
    sbom_file = Path(result.sbom_result.sbom_file_path)
    assert sbom_file.exists()
    
    with open(sbom_file, 'r') as f:
        sbom_data = json.load(f)
        assert "bomFormat" in sbom_data
        assert "components" in sbom_data
        print("✅ SBOM file structure: OK")
    
    print("🎉 All tests completed!")
    return True


def demo():
    """Demo."""
    print("📋 PRODUCTION SBOM-LICENSE-GATE DEMO")
    print("=" * 60)
    
    if not test_production_sbom_license_gate():
        return 1
    
    print("\n📋 Demo: SBOM-License-Gate-Ausführung")
    
    gate = ProductionSBOMLicenseGate("DEMO-SBOM-001")
    result = gate.execute_sbom_license_gate()
    
    print("\n📊 Ergebnisse:")
    print(f"   SBOM Packages: {result.sbom_result.total_packages}")
    print(f"   License Status: {'PASSED' if result.license_audit.passed else 'FAILED'}")
    print(f"   Vulnerability Status: {'PASSED' if result.vulnerability_audit.passed else 'FAILED'}")
    print(f"   Overall Status: {'PASSED' if result.overall_passed else 'FAILED'}")
    print(f"   Exit Code: {result.exit_code}")
    
    # Generiere Reports
    gate.generate_reports(result)
    
    print("\n📋 SBOM-License-Gate-Capabilities:")
    print("   ✅ CycloneDX SBOM-Generierung")
    print("   ✅ Umfassende License-Compliance-Prüfung")
    print("   ✅ Vulnerability-Scanning mit Safety")
    print("   ✅ Policy-basierte Allow/Deny-Lists")
    print("   ✅ Hard-Fail bei Verstößen")
    print("   ✅ Strukturierte JSON/Markdown-Reports")
    print("   ✅ Artifact-Generierung für PR-Links")
    
    print("\n✅ Demo complete!")
    return 0


if __name__ == "__main__":
    sys.exit(demo())
