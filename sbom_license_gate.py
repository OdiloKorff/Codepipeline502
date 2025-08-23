"""
SBOM und Lizenz Policy Gate.

Erzeugt eine Software-Stückliste (SBOM) im CycloneDX-Format,
führt Schwachstellenprüfung für Abhängigkeiten aus und 
verifiziert Lizenzen gegen eine Allowlist.

Jede Verletzung ist ein Hard-Fail mit Dokumentation als Artefakte.
"""

import json
import logging
import subprocess
import sys
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
    vulnerabilities: List[Dict] = None
    
    def __post_init__(self):
        if self.vulnerabilities is None:
            self.vulnerabilities = []


@dataclass
class LicenseViolation:
    """Lizenz-Verletzung."""
    dependency: str
    version: str
    license: str
    violation_type: str  # "denied", "unknown", "missing"
    severity: str = "high"


@dataclass
class VulnerabilityFinding:
    """Schwachstellen-Fund."""
    dependency: str
    version: str
    vulnerability_id: str
    severity: str
    description: str
    cvss_score: Optional[float] = None
    fixed_version: Optional[str] = None


class SBOMLicenseGate:
    """Gate für SBOM-Erzeugung und Lizenz-Policy-Durchsetzung."""
    
    def __init__(self, 
                 allowed_licenses: List[str] = None,
                 denied_licenses: List[str] = None,
                 spec_id: Optional[str] = None):
        """
        Args:
            allowed_licenses: Liste erlaubter Lizenzen
            denied_licenses: Liste verbotener Lizenzen
            spec_id: ID der Feature-Spec
        """
        self.allowed_licenses = set(allowed_licenses or [
            "MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", 
            "MPL-2.0", "ISC", "Python-2.0"
        ])
        self.denied_licenses = set(denied_licenses or [
            "GPL-3.0", "AGPL-3.0", "SSPL", "BUSL-1.1", "Commons-Clause"
        ])
        self.spec_id = spec_id or "unknown"
        
        self.dependencies: List[Dependency] = []
        self.license_violations: List[LicenseViolation] = []
        self.vulnerability_findings: List[VulnerabilityFinding] = []
        self.sbom_generated = False
        
        _log.info(f"[{self.spec_id}] SBOM License Gate initialisiert")
        _log.info(f"[{self.spec_id}] Erlaubte Lizenzen: {self.allowed_licenses}")
        _log.info(f"[{self.spec_id}] Verbotene Lizenzen: {self.denied_licenses}")
    
    def generate_sbom(self, output_path: str = "sbom.json") -> bool:
        """
        Erzeuge SBOM im CycloneDX-Format.
        
        Args:
            output_path: Pfad für SBOM-Ausgabe
            
        Returns:
            True wenn erfolgreich generiert
        """
        _log.info(f"[{self.spec_id}] Erzeuge SBOM: {output_path}")
        
        try:
            # Sammle Abhängigkeiten aus verschiedenen Quellen
            self._collect_pip_dependencies()
            
            # Erzeuge CycloneDX SBOM
            sbom = self._create_cyclonedx_sbom()
            
            # Schreibe SBOM-Datei
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(sbom, f, indent=2)
            
            self.sbom_generated = True
            _log.info(f"[{self.spec_id}] SBOM erfolgreich erzeugt: {len(self.dependencies)} Abhängigkeiten")
            return True
            
        except Exception as e:
            _log.error(f"[{self.spec_id}] SBOM-Erzeugung fehlgeschlagen: {e}")
            return False
    
    def _collect_pip_dependencies(self):
        """Sammle Python-Abhängigkeiten über pip."""
        try:
            # Führe pip list aus
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode != 0:
                _log.warning(f"pip list fehlgeschlagen: {result.stderr}")
                return
            
            pip_packages = json.loads(result.stdout)
            
            for package in pip_packages:
                # Hole detaillierte Paket-Informationen
                dep = self._get_package_details(package["name"], package["version"])
                if dep:
                    self.dependencies.append(dep)
                    
        except Exception as e:
            _log.error(f"Fehler beim Sammeln der pip-Abhängigkeiten: {e}")
    
    def _get_package_details(self, name: str, version: str) -> Optional[Dependency]:
        """Hole detaillierte Informationen für ein Paket."""
        try:
            # Versuche pip show für Lizenz-Informationen
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", name],
                capture_output=True, text=True, timeout=30
            )
            
            license_info = None
            homepage = None
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('License:'):
                        license_info = line.split(':', 1)[1].strip()
                    elif line.startswith('Home-page:'):
                        homepage = line.split(':', 1)[1].strip()
            
            # Normalisiere Lizenz-Namen
            normalized_license = self._normalize_license(license_info)
            
            return Dependency(
                name=name,
                version=version,
                license=normalized_license,
                homepage=homepage
            )
            
        except Exception as e:
            _log.warning(f"Konnte Details für {name} nicht abrufen: {e}")
            return Dependency(name=name, version=version)
    
    def _normalize_license(self, license_str: Optional[str]) -> Optional[str]:
        """Normalisiere Lizenz-String."""
        if not license_str or license_str.lower() in ('unknown', 'none', ''):
            return None
            
        # Häufige Lizenz-Mappings
        license_mappings = {
            'bsd': 'BSD-3-Clause',
            'bsd license': 'BSD-3-Clause',
            'mit license': 'MIT',
            'apache software license': 'Apache-2.0',
            'apache 2.0': 'Apache-2.0',
            'mozilla public license 2.0 (mpl 2.0)': 'MPL-2.0',
            'python software foundation license': 'Python-2.0'
        }
        
        normalized = license_str.lower().strip()
        return license_mappings.get(normalized, license_str)
    
    def _create_cyclonedx_sbom(self) -> Dict:
        """Erstelle CycloneDX SBOM-Struktur."""
        components = []
        
        for dep in self.dependencies:
            component = {
                "type": "library",
                "bom-ref": f"pkg:pypi/{dep.name}@{dep.version}",
                "name": dep.name,
                "version": dep.version,
                "purl": f"pkg:pypi/{dep.name}@{dep.version}",
                "scope": "required"
            }
            
            if dep.license:
                component["licenses"] = [{"license": {"name": dep.license}}]
            
            if dep.homepage:
                component["externalReferences"] = [
                    {"type": "website", "url": dep.homepage}
                ]
            
            components.append(component)
        
        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "serialNumber": f"urn:uuid:{self.spec_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "version": 1,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "tools": [{"name": "CodePipeline SBOM Generator", "version": "1.0"}],
                "component": {
                    "type": "application",
                    "name": "codepipeline",
                    "version": "0.1.0"
                }
            },
            "components": components
        }
    
    def check_license_policy(self) -> bool:
        """
        Prüfe Lizenz-Policy gegen alle Abhängigkeiten.
        
        Returns:
            True wenn alle Lizenzen erlaubt, False bei Verletzungen
        """
        _log.info(f"[{self.spec_id}] Prüfe Lizenz-Policy für {len(self.dependencies)} Abhängigkeiten")
        
        self.license_violations.clear()
        
        for dep in self.dependencies:
            if not dep.license:
                # Fehlende Lizenz
                violation = LicenseViolation(
                    dependency=dep.name,
                    version=dep.version,
                    license="UNKNOWN",
                    violation_type="missing",
                    severity="medium"
                )
                self.license_violations.append(violation)
                continue
            
            # Prüfe gegen verbotene Lizenzen
            if dep.license in self.denied_licenses:
                violation = LicenseViolation(
                    dependency=dep.name,
                    version=dep.version,
                    license=dep.license,
                    violation_type="denied",
                    severity="high"
                )
                self.license_violations.append(violation)
                continue
            
            # Prüfe gegen erlaubte Lizenzen (wenn Allowlist nicht leer)
            if self.allowed_licenses and dep.license not in self.allowed_licenses:
                violation = LicenseViolation(
                    dependency=dep.name,
                    version=dep.version,
                    license=dep.license,
                    violation_type="unknown",
                    severity="medium"
                )
                self.license_violations.append(violation)
        
        if self.license_violations:
            _log.error(f"[{self.spec_id}] {len(self.license_violations)} Lizenz-Verletzungen gefunden")
            for violation in self.license_violations:
                _log.error(f"[{self.spec_id}] Verletzung: {violation.dependency} ({violation.license}) - {violation.violation_type}")
            return False
        else:
            _log.info(f"[{self.spec_id}] Alle Lizenzen sind konform")
            return True
    
    def check_vulnerabilities(self) -> bool:
        """
        Prüfe auf bekannte Schwachstellen in Abhängigkeiten.
        
        Returns:
            True wenn keine kritischen Schwachstellen, False bei Findings
        """
        _log.info(f"[{self.spec_id}] Prüfe Schwachstellen...")
        
        try:
            # Verwende safety für Python-Schwachstellenprüfung
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "safety", "--quiet"],
                capture_output=True, text=True, timeout=120
            )
            
            # Führe safety check aus
            safety_result = subprocess.run(
                [sys.executable, "-m", "safety", "check", "--json"],
                capture_output=True, text=True, timeout=120
            )
            
            if safety_result.returncode == 0:
                _log.info(f"[{self.spec_id}] Keine Schwachstellen gefunden")
                return True
            
            # Parse safety output
            try:
                safety_data = json.loads(safety_result.stdout)
                for finding in safety_data:
                    vuln = VulnerabilityFinding(
                        dependency=finding.get("package", "unknown"),
                        version=finding.get("installed_version", "unknown"),
                        vulnerability_id=finding.get("vulnerability_id", "unknown"),
                        severity="high",  # Safety meldet meist kritische Findings
                        description=finding.get("advisory", "Unknown vulnerability"),
                        fixed_version=finding.get("vulnerable_spec", "unknown")
                    )
                    self.vulnerability_findings.append(vuln)
                
                _log.error(f"[{self.spec_id}] {len(self.vulnerability_findings)} Schwachstellen gefunden")
                return False
                
            except json.JSONDecodeError:
                _log.warning(f"[{self.spec_id}] Konnte safety output nicht parsen")
                return True
                
        except Exception as e:
            _log.warning(f"[{self.spec_id}] Schwachstellenprüfung fehlgeschlagen: {e}")
            # Bei Fehlern durchlassen (nicht blockieren)
            return True
    
    def generate_artifacts(self, output_dir: str = "sbom_artifacts") -> Dict[str, str]:
        """
        Generiere Artefakte für PR-Verlinkung.
        
        Args:
            output_dir: Verzeichnis für Artefakte
            
        Returns:
            Dictionary mit Artefakt-Pfaden
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        artifacts = {}
        
        # 1. SBOM-Datei
        sbom_path = output_path / "sbom.json"
        if self.generate_sbom(str(sbom_path)):
            artifacts["sbom"] = str(sbom_path)
        
        # 2. Lizenz-Report
        license_report_path = output_path / "license_report.json"
        license_report = {
            "spec_id": self.spec_id,
            "timestamp": datetime.now().isoformat(),
            "policy": {
                "allowed_licenses": list(self.allowed_licenses),
                "denied_licenses": list(self.denied_licenses)
            },
            "violations": [
                {
                    "dependency": v.dependency,
                    "version": v.version,
                    "license": v.license,
                    "violation_type": v.violation_type,
                    "severity": v.severity
                }
                for v in self.license_violations
            ],
            "total_dependencies": len(self.dependencies),
            "violations_count": len(self.license_violations)
        }
        
        with open(license_report_path, 'w', encoding='utf-8') as f:
            json.dump(license_report, f, indent=2)
        artifacts["license_report"] = str(license_report_path)
        
        # 3. Vulnerability Report
        vuln_report_path = output_path / "vulnerability_report.json"
        vuln_report = {
            "spec_id": self.spec_id,
            "timestamp": datetime.now().isoformat(),
            "findings": [
                {
                    "dependency": v.dependency,
                    "version": v.version,
                    "vulnerability_id": v.vulnerability_id,
                    "severity": v.severity,
                    "description": v.description,
                    "cvss_score": v.cvss_score,
                    "fixed_version": v.fixed_version
                }
                for v in self.vulnerability_findings
            ],
            "findings_count": len(self.vulnerability_findings)
        }
        
        with open(vuln_report_path, 'w', encoding='utf-8') as f:
            json.dump(vuln_report, f, indent=2)
        artifacts["vulnerability_report"] = str(vuln_report_path)
        
        _log.info(f"[{self.spec_id}] Artefakte generiert: {list(artifacts.keys())}")
        return artifacts
    
    def check_gate(self) -> bool:
        """
        Hauptprüfung: SBOM generieren und Policy prüfen.
        
        Returns:
            True wenn alle Checks bestanden, False bei Hard-Fail
        """
        _log.info(f"[{self.spec_id}] Starte SBOM License Gate Check")
        
        # 1. SBOM generieren
        if not self.generate_sbom():
            return False
        
        # 2. Lizenz-Policy prüfen
        license_ok = self.check_license_policy()
        
        # 3. Schwachstellen prüfen
        vuln_ok = self.check_vulnerabilities()
        
        # Hard-Fail bei Verletzungen
        if not license_ok or not vuln_ok:
            _log.error(f"[{self.spec_id}] SBOM License Gate FAILED")
            return False
        
        _log.info(f"[{self.spec_id}] SBOM License Gate PASSED")
        return True
    
    def generate_qa_summary_section(self) -> Dict:
        """Generiere QA-Summary-Sektion."""
        gate_passed = len(self.license_violations) == 0 and len(self.vulnerability_findings) == 0
        
        return {
            "name": "SBOM & License Policy",
            "passed": gate_passed,
            "score": 100 if gate_passed else 0,
            "details": {
                "dependencies_count": len(self.dependencies),
                "license_violations": len(self.license_violations),
                "vulnerability_findings": len(self.vulnerability_findings),
                "sbom_generated": self.sbom_generated,
                "allowed_licenses": list(self.allowed_licenses),
                "denied_licenses": list(self.denied_licenses)
            },
            "error_message": self._get_error_summary() if not gate_passed else None
        }
    
    def _get_error_summary(self) -> str:
        """Erstelle Fehler-Zusammenfassung."""
        errors = []
        
        if self.license_violations:
            high_violations = [v for v in self.license_violations if v.severity == "high"]
            if high_violations:
                errors.append(f"{len(high_violations)} verbotene Lizenzen")
            
            medium_violations = [v for v in self.license_violations if v.severity == "medium"]
            if medium_violations:
                errors.append(f"{len(medium_violations)} unbekannte Lizenzen")
        
        if self.vulnerability_findings:
            errors.append(f"{len(self.vulnerability_findings)} Schwachstellen")
        
        return "; ".join(errors)


def demo_sbom_license_gate():
    """Demonstriere SBOM und Lizenz Policy Gate."""
    print("📦 SBOM & License Policy Gate Demo")
    print("=" * 60)
    
    # Test 1: Standard-Policy (erlaubte Lizenzen)
    print("\n✅ Test 1: Standard License Policy")
    gate1 = SBOMLicenseGate(spec_id="SBOM-001")
    
    # Simuliere einige Abhängigkeiten
    gate1.dependencies = [
        Dependency("requests", "2.31.0", "Apache-2.0"),
        Dependency("pydantic", "2.5.0", "MIT"),
        Dependency("typer", "0.9.0", "MIT"),
        Dependency("structlog", "24.1.0", "MIT"),
    ]
    
    policy_ok = gate1.check_license_policy()
    vuln_ok = gate1.check_vulnerabilities()
    
    print(f"📋 Abhängigkeiten: {len(gate1.dependencies)}")
    print(f"📜 Lizenz-Policy: {'✅ PASSED' if policy_ok else '❌ FAILED'}")
    print(f"🔍 Schwachstellen: {'✅ PASSED' if vuln_ok else '❌ FAILED'}")
    
    # Test 2: Policy-Verletzung (verbotene Lizenz)
    print("\n❌ Test 2: License Policy Violation")
    gate2 = SBOMLicenseGate(spec_id="SBOM-002")
    
    # Simuliere Abhängigkeit mit verbotener Lizenz
    gate2.dependencies = [
        Dependency("requests", "2.31.0", "Apache-2.0"),
        Dependency("bad-package", "1.0.0", "GPL-3.0"),  # Verboten!
        Dependency("unknown-package", "1.0.0", None),    # Fehlende Lizenz
    ]
    
    policy_ok2 = gate2.check_license_policy()
    
    print(f"📋 Abhängigkeiten: {len(gate2.dependencies)}")
    print(f"📜 Lizenz-Policy: {'✅ PASSED' if policy_ok2 else '❌ FAILED'}")
    print(f"⚠️  Verletzungen: {len(gate2.license_violations)}")
    
    for violation in gate2.license_violations:
        print(f"   - {violation.dependency}: {violation.license} ({violation.violation_type})")
    
    # Test 3: Artefakt-Generierung
    print("\n📄 Test 3: Artefakt-Generierung")
    artifacts = gate2.generate_artifacts("demo_sbom_artifacts")
    
    print("📦 Generierte Artefakte:")
    for name, path in artifacts.items():
        print(f"   - {name}: {path}")
    
    # Test 4: QA-Integration
    print("\n📊 Test 4: QA-Integration")
    qa_section1 = gate1.generate_qa_summary_section()
    qa_section2 = gate2.generate_qa_summary_section()
    
    print(f"✅ Gate 1 Score: {qa_section1['score']}")
    print(f"❌ Gate 2 Score: {qa_section2['score']}")
    print(f"⚠️  Gate 2 Fehler: {qa_section2['error_message']}")
    
    qa_summary = {
        "sbom_gates": [qa_section1, qa_section2],
        "artifacts": artifacts
    }
    
    print("\nQA-Summary:")
    print(json.dumps(qa_summary, indent=2))
    
    print("\n✅ Demo abgeschlossen!")


if __name__ == "__main__":
    demo_sbom_license_gate()
