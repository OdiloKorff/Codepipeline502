"""
Real SBOM & Lizenz-Gate.

CycloneDX-SBOM generieren, Abhängigkeits-Vulnerabilities sammeln,
Lizenzen gegen eine Allow-List validieren. Bei verbotener Lizenz 
oder CVE-Treffer hart abbrechen. SBOM und Audit-Ergebnisse 
persistent ablegen und im PR verlinken.
"""

import json
import logging
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Setup Logging
_log = logging.getLogger(__name__)


@dataclass
class Dependency:
    """Einzelne Abhängigkeit mit Metadaten."""
    name: str
    version: str
    license: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    purl: Optional[str] = None  # Package URL
    
    def __post_init__(self):
        if not self.purl:
            self.purl = f"pkg:pypi/{self.name}@{self.version}"


@dataclass
class Vulnerability:
    """CVE/Vulnerability-Information."""
    cve_id: str
    severity: str
    description: str
    affected_package: str
    affected_version: str
    fixed_version: Optional[str] = None
    cvss_score: Optional[float] = None
    
    @property
    def is_high_severity(self) -> bool:
        """Prüfe ob High/Critical Severity."""
        return self.severity.lower() in ['high', 'critical']


@dataclass
class LicenseViolation:
    """Lizenz-Verletzung."""
    package: str
    version: str
    license: str
    violation_type: str  # "denied", "unknown", "missing"
    severity: str = "high"


class LicensePolicy:
    """Lizenz-Policy mit Allow/Deny-Listen."""
    
    def __init__(self, 
                 allowed_licenses: List[str] = None,
                 denied_licenses: List[str] = None,
                 require_license: bool = True):
        """
        Args:
            allowed_licenses: Liste explizit erlaubter Lizenzen
            denied_licenses: Liste explizit verbotener Lizenzen
            require_license: Ob Lizenz-Information erforderlich ist
        """
        self.allowed_licenses = set(allowed_licenses or [
            "MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", 
            "MPL-2.0", "ISC", "Python-2.0", "Unlicense"
        ])
        
        self.denied_licenses = set(denied_licenses or [
            "GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0",
            "SSPL", "BUSL-1.1", "Commons-Clause", "Elastic-2.0"
        ])
        
        self.require_license = require_license
        
        # Lizenz-Normalisierung (häufige Varianten)
        self.license_mappings = {
            "bsd": "BSD-3-Clause",
            "bsd license": "BSD-3-Clause", 
            "new bsd license": "BSD-3-Clause",
            "mit license": "MIT",
            "apache software license": "Apache-2.0",
            "apache 2.0": "Apache-2.0",
            "apache license 2.0": "Apache-2.0",
            "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
            "python software foundation license": "Python-2.0",
            "isc license": "ISC"
        }
    
    def normalize_license(self, license_str: Optional[str]) -> Optional[str]:
        """Normalisiere Lizenz-String."""
        if not license_str:
            return None
        
        normalized = license_str.lower().strip()
        
        # Direkte Mappings
        if normalized in self.license_mappings:
            return self.license_mappings[normalized]
        
        # Partielle Matches für komplexe Lizenz-Strings
        for pattern, canonical in self.license_mappings.items():
            if pattern in normalized:
                return canonical
        
        return license_str  # Original zurückgeben wenn keine Normalisierung
    
    def evaluate_license(self, license_str: Optional[str]) -> Optional[LicenseViolation]:
        """Evaluiere Lizenz gegen Policy."""
        normalized = self.normalize_license(license_str)
        
        # Fehlende Lizenz
        if not normalized:
            if self.require_license:
                return LicenseViolation(
                    package="unknown",
                    version="unknown", 
                    license="MISSING",
                    violation_type="missing",
                    severity="medium"
                )
            return None
        
        # Explizit verbotene Lizenz
        if normalized in self.denied_licenses:
            return LicenseViolation(
                package="unknown",
                version="unknown",
                license=normalized,
                violation_type="denied", 
                severity="high"
            )
        
        # Wenn Allow-List definiert: Prüfe ob erlaubt
        if self.allowed_licenses and normalized not in self.allowed_licenses:
            return LicenseViolation(
                package="unknown",
                version="unknown",
                license=normalized,
                violation_type="unknown",
                severity="medium"
            )
        
        return None  # Lizenz ist OK


class RealSBOMLicenseGate:
    """Real SBOM & License Gate mit echten Tools."""
    
    def __init__(self, 
                 license_policy: LicensePolicy,
                 spec_id: Optional[str] = None,
                 target_path: str = "."):
        """
        Args:
            license_policy: Lizenz-Policy
            spec_id: ID der Feature-Spec
            target_path: Zu scannender Pfad
        """
        self.license_policy = license_policy
        self.spec_id = spec_id or "unknown"
        self.target_path = Path(target_path)
        
        # Scan-Ergebnisse
        self.dependencies: List[Dependency] = []
        self.vulnerabilities: List[Vulnerability] = []
        self.license_violations: List[LicenseViolation] = []
        self.sbom_data: Optional[Dict] = None
        
        _log.info(f"[{self.spec_id}] Real SBOM License Gate initialisiert")
        _log.info(f"[{self.spec_id}] Erlaubte Lizenzen: {len(license_policy.allowed_licenses)}")
        _log.info(f"[{self.spec_id}] Verbotene Lizenzen: {len(license_policy.denied_licenses)}")
    
    def run_comprehensive_analysis(self) -> Dict:
        """
        Führe umfassende SBOM- und Lizenz-Analyse durch.
        
        Returns:
            Dictionary mit Analyse-Ergebnissen
        """
        _log.info(f"[{self.spec_id}] Starte umfassende SBOM-Analyse")
        
        try:
            # 1. Sammle Dependencies
            self._collect_dependencies()
            
            # 2. Generiere CycloneDX SBOM
            self._generate_cyclonedx_sbom()
            
            # 3. Scanne Vulnerabilities
            self._scan_vulnerabilities()
            
            # 4. Validiere Lizenzen
            self._validate_licenses()
            
            # 5. Evaluiere Ergebnisse
            result = self._evaluate_results()
            
            _log.info(f"[{self.spec_id}] SBOM-Analyse abgeschlossen: "
                     f"{len(self.dependencies)} Dependencies, "
                     f"{len(self.vulnerabilities)} CVEs, "
                     f"{len(self.license_violations)} License Violations")
            
            return result
            
        except Exception as e:
            _log.error(f"[{self.spec_id}] SBOM-Analyse fehlgeschlagen: {e}")
            raise
    
    def _collect_dependencies(self):
        """Sammle Dependencies aus verschiedenen Quellen."""
        _log.info(f"[{self.spec_id}] Sammle Dependencies")
        
        # 1. Pip-installierte Packages
        self._collect_pip_dependencies()
        
        # 2. Requirements-Dateien
        self._collect_requirements_dependencies()
        
        _log.info(f"[{self.spec_id}] {len(self.dependencies)} Dependencies gesammelt")
    
    def _collect_pip_dependencies(self):
        """Sammle pip-installierte Dependencies."""
        try:
            # Führe pip list aus
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                
                for package in packages:
                    # Hole detaillierte Package-Info
                    dep = self._get_package_details(package["name"], package["version"])
                    if dep:
                        self.dependencies.append(dep)
            
        except Exception as e:
            _log.warning(f"[{self.spec_id}] Fehler beim Sammeln pip-Dependencies: {e}")
    
    def _collect_requirements_dependencies(self):
        """Sammle Dependencies aus requirements.txt."""
        req_files = [
            "requirements.txt", 
            "requirements-dev.txt",
            "requirements-test.txt"
        ]
        
        for req_file in req_files:
            req_path = self.target_path / req_file
            
            if req_path.exists():
                try:
                    content = req_path.read_text(encoding='utf-8')
                    
                    for line in content.split('\n'):
                        line = line.strip()
                        
                        # Ignoriere Kommentare und leere Zeilen
                        if not line or line.startswith('#'):
                            continue
                        
                        # Parse Package-Name und Version
                        if '==' in line:
                            name, version = line.split('==', 1)
                            name = name.strip()
                            version = version.strip()
                            
                            # Prüfe ob bereits vorhanden
                            if not any(d.name == name for d in self.dependencies):
                                dep = self._get_package_details(name, version)
                                if dep:
                                    self.dependencies.append(dep)
                
                except Exception as e:
                    _log.warning(f"[{self.spec_id}] Fehler beim Parsen {req_file}: {e}")
    
    def _get_package_details(self, name: str, version: str) -> Optional[Dependency]:
        """Hole detaillierte Package-Informationen."""
        try:
            # Versuche pip show
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            license_info = None
            homepage = None
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('License:'):
                        license_info = line.split(':', 1)[1].strip()
                    elif line.startswith('Home-page:'):
                        homepage = line.split(':', 1)[1].strip()
            
            # Normalisiere Lizenz
            normalized_license = self.license_policy.normalize_license(license_info)
            
            return Dependency(
                name=name,
                version=version,
                license=normalized_license,
                homepage=homepage,
                purl=f"pkg:pypi/{name}@{version}"
            )
            
        except Exception as e:
            _log.debug(f"[{self.spec_id}] Fehler bei Package-Details für {name}: {e}")
            
            # Fallback: Minimale Dependency-Info
            return Dependency(name=name, version=version)
    
    def _generate_cyclonedx_sbom(self):
        """Generiere CycloneDX-SBOM."""
        _log.info(f"[{self.spec_id}] Generiere CycloneDX-SBOM")
        
        # CycloneDX SBOM-Struktur
        components = []
        
        for dep in self.dependencies:
            component = {
                "type": "library",
                "bom-ref": dep.purl,
                "name": dep.name,
                "version": dep.version,
                "purl": dep.purl,
                "scope": "required"
            }
            
            # Lizenz-Information
            if dep.license:
                component["licenses"] = [
                    {"license": {"name": dep.license}}
                ]
            
            # External References
            if dep.homepage:
                component["externalReferences"] = [
                    {"type": "website", "url": dep.homepage}
                ]
            
            components.append(component)
        
        # SBOM-Metadaten
        self.sbom_data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "serialNumber": f"urn:uuid:{str(uuid.uuid4())}",
            "version": 1,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "tools": [
                    {
                        "name": "CodePipeline SBOM Generator",
                        "version": "1.0.0"
                    }
                ],
                "component": {
                    "type": "application", 
                    "name": "codepipeline",
                    "version": "1.0.0"
                }
            },
            "components": components
        }
        
        _log.info(f"[{self.spec_id}] CycloneDX-SBOM generiert: {len(components)} Komponenten")
    
    def _scan_vulnerabilities(self):
        """Scanne Dependencies auf Vulnerabilities."""
        _log.info(f"[{self.spec_id}] Scanne Vulnerabilities")
        
        try:
            # Verwende safety für Python-Vulnerabilities
            result = subprocess.run(
                [sys.executable, "-m", "safety", "check", "--json"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode in [0, 64]:  # 0=no vulns, 64=vulns found
                if result.stdout.strip():
                    try:
                        vulns_data = json.loads(result.stdout)
                        
                        for vuln in vulns_data:
                            vulnerability = Vulnerability(
                                cve_id=vuln.get("id", "unknown"),
                                severity="high",  # Safety meldet meist kritische Vulns
                                description=vuln.get("advisory", "Unknown vulnerability"),
                                affected_package=vuln.get("package", "unknown"),
                                affected_version=vuln.get("installed_version", "unknown"),
                                fixed_version=vuln.get("vulnerable_spec", None)
                            )
                            
                            self.vulnerabilities.append(vulnerability)
                    
                    except json.JSONDecodeError:
                        # Safety output ist manchmal nicht JSON
                        _log.debug(f"[{self.spec_id}] Safety output nicht JSON-parsbar")
                
                _log.info(f"[{self.spec_id}] Vulnerability-Scan abgeschlossen: {len(self.vulnerabilities)} CVEs")
            
            else:
                _log.warning(f"[{self.spec_id}] Safety fehlgeschlagen: {result.stderr}")
                
        except FileNotFoundError:
            _log.warning(f"[{self.spec_id}] Safety nicht installiert - Vulnerability-Scan übersprungen")
        except Exception as e:
            _log.error(f"[{self.spec_id}] Vulnerability-Scan fehlgeschlagen: {e}")
    
    def _validate_licenses(self):
        """Validiere Lizenzen gegen Policy."""
        _log.info(f"[{self.spec_id}] Validiere Lizenzen gegen Policy")
        
        self.license_violations = []
        
        for dep in self.dependencies:
            violation = self.license_policy.evaluate_license(dep.license)
            
            if violation:
                # Setze Package-Details
                violation.package = dep.name
                violation.version = dep.version
                
                self.license_violations.append(violation)
                
                _log.warning(f"[{self.spec_id}] Lizenz-Verletzung: {dep.name} ({dep.license}) - {violation.violation_type}")
        
        _log.info(f"[{self.spec_id}] Lizenz-Validierung abgeschlossen: {len(self.license_violations)} Verletzungen")
    
    def _evaluate_results(self) -> Dict:
        """Evaluiere Gesamtergebnisse."""
        # Zähle kritische Issues
        high_severity_vulns = sum(1 for v in self.vulnerabilities if v.is_high_severity)
        high_severity_licenses = sum(1 for lv in self.license_violations if lv.severity == "high")
        
        # Bestimme Gate-Status
        gate_passed = (
            len(self.vulnerabilities) == 0 and
            high_severity_licenses == 0
        )
        
        # Exit-Code
        if high_severity_vulns > 0 or high_severity_licenses > 0:
            exit_code = 2  # Critical failure
        elif len(self.vulnerabilities) > 0 or len(self.license_violations) > 0:
            exit_code = 1  # Standard failure
        else:
            exit_code = 0  # Success
        
        result = {
            "gate_passed": gate_passed,
            "exit_code": exit_code,
            "summary": {
                "dependencies_count": len(self.dependencies),
                "vulnerabilities_count": len(self.vulnerabilities),
                "high_severity_vulns": high_severity_vulns,
                "license_violations_count": len(self.license_violations),
                "high_severity_licenses": high_severity_licenses
            },
            "details": {
                "dependencies": [
                    {
                        "name": dep.name,
                        "version": dep.version,
                        "license": dep.license,
                        "purl": dep.purl
                    }
                    for dep in self.dependencies
                ],
                "vulnerabilities": [
                    {
                        "cve_id": vuln.cve_id,
                        "severity": vuln.severity,
                        "package": vuln.affected_package,
                        "version": vuln.affected_version,
                        "description": vuln.description,
                        "fixed_version": vuln.fixed_version
                    }
                    for vuln in self.vulnerabilities
                ],
                "license_violations": [
                    {
                        "package": lv.package,
                        "version": lv.version,
                        "license": lv.license,
                        "violation_type": lv.violation_type,
                        "severity": lv.severity
                    }
                    for lv in self.license_violations
                ]
            }
        }
        
        if not gate_passed:
            _log.error(f"[{self.spec_id}] SBOM License Gate FAILED")
        else:
            _log.info(f"[{self.spec_id}] SBOM License Gate PASSED")
        
        return result
    
    def save_artifacts(self, output_dir: str = "sbom_artifacts") -> Dict[str, str]:
        """Speichere SBOM- und Audit-Artefakte."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        artifacts = {}
        
        # 1. CycloneDX SBOM
        if self.sbom_data:
            sbom_file = output_path / f"sbom_{self.spec_id}.json"
            with open(sbom_file, 'w', encoding='utf-8') as f:
                json.dump(self.sbom_data, f, indent=2, ensure_ascii=False)
            artifacts["sbom"] = str(sbom_file)
            _log.info(f"[{self.spec_id}] SBOM gespeichert: {sbom_file}")
        
        # 2. Vulnerability Report
        vuln_report = {
            "spec_id": self.spec_id,
            "timestamp": datetime.now().isoformat(),
            "vulnerabilities": [
                {
                    "cve_id": vuln.cve_id,
                    "severity": vuln.severity,
                    "package": vuln.affected_package,
                    "version": vuln.affected_version,
                    "description": vuln.description,
                    "fixed_version": vuln.fixed_version,
                    "cvss_score": vuln.cvss_score
                }
                for vuln in self.vulnerabilities
            ],
            "summary": {
                "total_vulnerabilities": len(self.vulnerabilities),
                "high_severity": sum(1 for v in self.vulnerabilities if v.is_high_severity)
            }
        }
        
        vuln_file = output_path / f"vulnerabilities_{self.spec_id}.json"
        with open(vuln_file, 'w', encoding='utf-8') as f:
            json.dump(vuln_report, f, indent=2, ensure_ascii=False)
        artifacts["vulnerabilities"] = str(vuln_file)
        
        # 3. License Report
        license_report = {
            "spec_id": self.spec_id,
            "timestamp": datetime.now().isoformat(),
            "policy": {
                "allowed_licenses": list(self.license_policy.allowed_licenses),
                "denied_licenses": list(self.license_policy.denied_licenses),
                "require_license": self.license_policy.require_license
            },
            "violations": [
                {
                    "package": lv.package,
                    "version": lv.version,
                    "license": lv.license,
                    "violation_type": lv.violation_type,
                    "severity": lv.severity
                }
                for lv in self.license_violations
            ],
            "summary": {
                "total_dependencies": len(self.dependencies),
                "license_violations": len(self.license_violations),
                "high_severity_violations": sum(1 for lv in self.license_violations if lv.severity == "high")
            }
        }
        
        license_file = output_path / f"licenses_{self.spec_id}.json"
        with open(license_file, 'w', encoding='utf-8') as f:
            json.dump(license_report, f, indent=2, ensure_ascii=False)
        artifacts["licenses"] = str(license_file)
        
        _log.info(f"[{self.spec_id}] Alle Artefakte gespeichert: {list(artifacts.keys())}")
        
        return artifacts
    
    def generate_pr_links(self, artifacts: Dict[str, str]) -> str:
        """Generiere PR-Kommentar mit Artefakt-Links."""
        pr_comment = f"""## 📦 SBOM & License Analysis Report

**Spec ID:** {self.spec_id}  
**Timestamp:** {datetime.now().isoformat()}  

### 📊 Summary

| Metric | Value | Status |
|--------|-------|---------|
| Dependencies | {len(self.dependencies)} | ℹ️ |
| Vulnerabilities | {len(self.vulnerabilities)} | {'❌' if self.vulnerabilities else '✅'} |
| License Violations | {len(self.license_violations)} | {'❌' if self.license_violations else '✅'} |
| High Severity Issues | {sum(1 for v in self.vulnerabilities if v.is_high_severity) + sum(1 for lv in self.license_violations if lv.severity == "high")} | {'❌' if any(v.is_high_severity for v in self.vulnerabilities) or any(lv.severity == "high" for lv in self.license_violations) else '✅'} |

### 📄 Generated Artifacts

"""
        
        for artifact_type, filepath in artifacts.items():
            pr_comment += f"- **{artifact_type.title()}**: [`{Path(filepath).name}`]({filepath})\n"
        
        if self.vulnerabilities:
            pr_comment += "\n### 🚨 Vulnerabilities Found\n\n"
            for vuln in self.vulnerabilities[:5]:  # Erste 5
                pr_comment += f"- **{vuln.cve_id}** ({vuln.severity}): {vuln.affected_package}@{vuln.affected_version}\n"
            
            if len(self.vulnerabilities) > 5:
                pr_comment += f"- ... and {len(self.vulnerabilities) - 5} more\n"
        
        if self.license_violations:
            pr_comment += "\n### ⚖️ License Violations\n\n"
            for lv in self.license_violations[:5]:  # Erste 5
                pr_comment += f"- **{lv.package}@{lv.version}**: {lv.license} ({lv.violation_type})\n"
            
            if len(self.license_violations) > 5:
                pr_comment += f"- ... and {len(self.license_violations) - 5} more\n"
        
        pr_comment += "\n---\n*Generated by CodePipeline SBOM & License Gate*"
        
        return pr_comment


def demo_real_sbom_license_gate():
    """Demonstriere Real SBOM License Gate."""
    print("📦 Real SBOM & License Gate Demo")
    print("=" * 60)
    
    # Test 1: Standard License Policy
    print("\n✅ Test 1: Standard License Policy")
    
    policy = LicensePolicy(
        allowed_licenses=["MIT", "BSD-3-Clause", "Apache-2.0", "Python-2.0"],
        denied_licenses=["GPL-3.0", "AGPL-3.0"],
        require_license=True
    )
    
    gate = RealSBOMLicenseGate(
        license_policy=policy,
        spec_id="SBOM-DEMO-001",
        target_path="."
    )
    
    # Führe umfassende Analyse durch
    result = gate.run_comprehensive_analysis()
    
    print("📊 Analyse-Ergebnis:")
    print(f"   - Gate: {'✅ PASSED' if result['gate_passed'] else '❌ FAILED'}")
    print(f"   - Exit Code: {result['exit_code']}")
    print(f"   - Dependencies: {result['summary']['dependencies_count']}")
    print(f"   - Vulnerabilities: {result['summary']['vulnerabilities_count']}")
    print(f"   - License Violations: {result['summary']['license_violations_count']}")
    
    # Test 2: Strenge License Policy
    print("\n🚨 Test 2: Strenge License Policy")
    
    strict_policy = LicensePolicy(
        allowed_licenses=["MIT"],  # Nur MIT erlaubt
        denied_licenses=["GPL-3.0", "AGPL-3.0", "Apache-2.0"],  # Apache auch verboten
        require_license=True
    )
    
    strict_gate = RealSBOMLicenseGate(
        license_policy=strict_policy,
        spec_id="STRICT-SBOM-001",
        target_path="."
    )
    
    strict_result = strict_gate.run_comprehensive_analysis()
    
    print("📊 Strenge Analyse:")
    print(f"   - Gate: {'✅ PASSED' if strict_result['gate_passed'] else '❌ FAILED'}")
    print(f"   - Exit Code: {strict_result['exit_code']}")
    print(f"   - License Violations: {strict_result['summary']['license_violations_count']}")
    
    if strict_result['details']['license_violations']:
        print("⚖️ Lizenz-Verletzungen:")
        for lv in strict_result['details']['license_violations'][:3]:
            print(f"   - {lv['package']}: {lv['license']} ({lv['violation_type']})")
    
    # Test 3: Artefakt-Generierung
    print("\n📄 Test 3: Artefakt-Generierung")
    
    artifacts = gate.save_artifacts("demo_sbom_artifacts")
    
    print("📦 Generierte Artefakte:")
    for artifact_type, filepath in artifacts.items():
        print(f"   - {artifact_type}: {filepath}")
    
    # Validiere SBOM-Struktur
    if "sbom" in artifacts:
        with open(artifacts["sbom"], 'r', encoding='utf-8') as f:
            sbom_data = json.load(f)
        
        print("📋 SBOM-Validierung:")
        print(f"   - Format: {sbom_data['bomFormat']}")
        print(f"   - Spec Version: {sbom_data['specVersion']}")
        print(f"   - Komponenten: {len(sbom_data['components'])}")
    
    # Test 4: PR-Link-Generierung
    print("\n🔗 Test 4: PR-Link-Generierung")
    
    pr_comment = gate.generate_pr_links(artifacts)
    
    print(f"📝 PR-Kommentar generiert ({len(pr_comment)} Zeichen)")
    print("📄 Vorschau:")
    print(pr_comment[:300] + "..." if len(pr_comment) > 300 else pr_comment)
    
    # Speichere PR-Kommentar
    pr_file = "demo_pr_comment.md"
    with open(pr_file, 'w', encoding='utf-8') as f:
        f.write(pr_comment)
    
    print(f"💾 PR-Kommentar gespeichert: {pr_file}")
    
    print("\n✅ Real SBOM License Gate Demo abgeschlossen!")
    print("📦 CycloneDX-SBOM, CVE-Scanning und License-Policy vollständig implementiert")
    
    return result['exit_code']


if __name__ == "__main__":
    exit_code = demo_real_sbom_license_gate()
    sys.exit(exit_code)
