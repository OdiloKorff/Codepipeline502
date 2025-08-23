"""
SBOM-Generator für Programm-Artefakte und Container-Images.

Erzeugt Software Bill of Materials (SBOM) sowohl für das Programm-Artefakt 
als auch für Container-Images mit Lizenzprüfung und CVE-Auswertung.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import logging

from .build_system import BuildArtifact
from .container_builder import ContainerImage
from .template_catalog import ProgramTemplate


logger = logging.getLogger(__name__)


@dataclass
class Component:
    """SBOM-Komponente."""
    
    # Identifikation
    name: str
    version: str
    purl: str  # Package URL
    
    # Metadaten
    supplier: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    homepage: Optional[str] = None
    
    # Lizenz-Informationen
    license_declared: Optional[str] = None
    license_concluded: Optional[str] = None
    copyright: Optional[str] = None
    
    # Hashes
    sha256: Optional[str] = None
    
    # Typ
    component_type: str = "library"  # library, application, framework, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class Vulnerability:
    """CVE-Vulnerability."""
    
    # Identifikation
    cve_id: str
    severity: str  # critical, high, medium, low
    title: str
    description: str
    affected_component: str
    
    # Optional fields
    score: Optional[float] = None
    published: Optional[str] = None
    affected_versions: List[str] = None
    fixed_versions: List[str] = None
    
    def __post_init__(self):
        if self.affected_versions is None:
            self.affected_versions = []
        if self.fixed_versions is None:
            self.fixed_versions = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class LicenseInfo:
    """Lizenz-Informationen."""
    
    # Identifikation
    license_id: str
    name: str
    
    # Kategorisierung
    is_osi_approved: bool
    is_copyleft: bool
    is_commercial: bool = False
    
    # Kompatibilität
    compatibility_level: str = "unknown"  # permissive, weak_copyleft, strong_copyleft, proprietary
    
    # Details
    url: Optional[str] = None
    text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class SBOM:
    """Software Bill of Materials."""
    
    # SBOM-Metadaten
    sbom_id: str
    name: str
    version: str
    created_at: str
    
    # Quelle
    source_artifact: Optional[str] = None
    source_container: Optional[str] = None
    
    # Komponenten
    components: List[Component] = None
    
    # Vulnerabilities
    vulnerabilities: List[Vulnerability] = None
    
    # Lizenz-Zusammenfassung
    licenses_found: List[LicenseInfo] = None
    license_violations: List[str] = None
    
    # Metadaten
    tool_name: str = "codepipeline-sbom"
    tool_version: str = "1.0.0"
    spec_version: str = "1.4"
    
    def __post_init__(self):
        if self.components is None:
            self.components = []
        if self.vulnerabilities is None:
            self.vulnerabilities = []
        if self.licenses_found is None:
            self.licenses_found = []
        if self.license_violations is None:
            self.license_violations = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["components"] = [c.to_dict() for c in self.components]
        result["vulnerabilities"] = [v.to_dict() for v in self.vulnerabilities]
        result["licenses_found"] = [l.to_dict() for l in self.licenses_found]
        return result
    
    def to_cyclonedx_json(self) -> Dict[str, Any]:
        """Konvertiere zu CycloneDX JSON-Format."""
        return {
            "bomFormat": "CycloneDX",
            "specVersion": self.spec_version,
            "serialNumber": f"urn:uuid:{uuid.uuid4()}",
            "version": 1,
            "metadata": {
                "timestamp": self.created_at,
                "tools": [
                    {
                        "vendor": "CodePipeline",
                        "name": self.tool_name,
                        "version": self.tool_version
                    }
                ],
                "component": {
                    "type": "application",
                    "name": self.name,
                    "version": self.version
                }
            },
            "components": [
                {
                    "type": comp.component_type,
                    "name": comp.name,
                    "version": comp.version,
                    "purl": comp.purl,
                    "description": comp.description,
                    "licenses": [
                        {"license": {"name": comp.license_declared}}
                    ] if comp.license_declared else [],
                    "hashes": [
                        {"alg": "SHA-256", "content": comp.sha256}
                    ] if comp.sha256 else []
                }
                for comp in self.components
            ],
            "vulnerabilities": [
                {
                    "id": vuln.cve_id,
                    "source": {
                        "name": "NVD",
                        "url": f"https://nvd.nist.gov/vuln/detail/{vuln.cve_id}"
                    },
                    "ratings": [
                        {
                            "source": {"name": "NVD"},
                            "severity": vuln.severity.upper(),
                            "score": vuln.score
                        }
                    ] if vuln.score else [],
                    "description": vuln.description,
                    "published": vuln.published,
                    "affects": [
                        {
                            "ref": f"pkg:pypi/{vuln.affected_component}@{version}"
                            for version in vuln.affected_versions
                        }
                    ]
                }
                for vuln in self.vulnerabilities
            ]
        }


class DependencyCollector:
    """Sammler für Abhängigkeiten."""
    
    @staticmethod
    def collect_python_dependencies() -> List[Component]:
        """Sammle Python-Abhängigkeiten."""
        components = []
        
        try:
            # Hole installierte Pakete
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )
            
            packages = json.loads(result.stdout)
            
            for package in packages:
                name = package["name"]
                version = package["version"]
                
                # Hole zusätzliche Informationen
                package_info = DependencyCollector._get_package_info(name)
                
                component = Component(
                    name=name,
                    version=version,
                    purl=f"pkg:pypi/{name}@{version}",
                    description=package_info.get("description"),
                    homepage=package_info.get("homepage"),
                    license_declared=package_info.get("license"),
                    component_type="library"
                )
                
                components.append(component)
                
        except Exception as e:
            logger.error(f"Failed to collect Python dependencies: {e}")
        
        return components
    
    @staticmethod
    def _get_package_info(package_name: str) -> Dict[str, Any]:
        """Hole Package-Informationen."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", package_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            info = {}
            for line in result.stdout.split('\\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.lower().strip()] = value.strip()
            
            return info
            
        except Exception:
            return {}
    
    @staticmethod
    def collect_container_dependencies(container_image: ContainerImage) -> List[Component]:
        """Sammle Container-Abhängigkeiten."""
        # Simuliere Container-Dependency-Sammlung
        # In Produktion: docker image inspect, Syft, etc.
        
        base_components = [
            Component(
                name="python",
                version="3.11.0",
                purl="pkg:generic/python@3.11.0",
                description="Python interpreter",
                license_declared="Python Software Foundation License",
                component_type="runtime"
            ),
            Component(
                name="debian",
                version="11",
                purl="pkg:generic/debian@11",
                description="Debian base system",
                license_declared="Various",
                component_type="operating-system"
            )
        ]
        
        return base_components


class LicenseChecker:
    """Lizenz-Prüfer."""
    
    def __init__(self):
        self.license_db = self._load_license_database()
    
    def _load_license_database(self) -> Dict[str, LicenseInfo]:
        """Lade Lizenz-Datenbank."""
        return {
            "MIT": LicenseInfo(
                license_id="MIT",
                name="MIT License",
                is_osi_approved=True,
                is_copyleft=False,
                compatibility_level="permissive"
            ),
            "Apache-2.0": LicenseInfo(
                license_id="Apache-2.0",
                name="Apache License 2.0",
                is_osi_approved=True,
                is_copyleft=False,
                compatibility_level="permissive"
            ),
            "GPL-3.0": LicenseInfo(
                license_id="GPL-3.0",
                name="GNU General Public License v3.0",
                is_osi_approved=True,
                is_copyleft=True,
                compatibility_level="strong_copyleft"
            ),
            "BSD-3-Clause": LicenseInfo(
                license_id="BSD-3-Clause",
                name="BSD 3-Clause License",
                is_osi_approved=True,
                is_copyleft=False,
                compatibility_level="permissive"
            ),
            "LGPL-2.1": LicenseInfo(
                license_id="LGPL-2.1",
                name="GNU Lesser General Public License v2.1",
                is_osi_approved=True,
                is_copyleft=True,
                compatibility_level="weak_copyleft"
            ),
            "Proprietary": LicenseInfo(
                license_id="Proprietary",
                name="Proprietary License",
                is_osi_approved=False,
                is_copyleft=False,
                is_commercial=True,
                compatibility_level="proprietary"
            )
        }
    
    def check_component_license(self, component: Component) -> Optional[LicenseInfo]:
        """Prüfe Lizenz einer Komponente."""
        if not component.license_declared:
            return None
        
        # Normalisiere Lizenz-Namen
        license_name = self._normalize_license_name(component.license_declared)
        
        return self.license_db.get(license_name)
    
    def _normalize_license_name(self, license_name: str) -> str:
        """Normalisiere Lizenz-Namen."""
        license_name = license_name.strip()
        
        # Mapping für häufige Varianten
        mappings = {
            "MIT License": "MIT",
            "Apache License": "Apache-2.0",
            "Apache Software License": "Apache-2.0",
            "BSD License": "BSD-3-Clause",
            "GNU General Public License": "GPL-3.0",
            "GNU Lesser General Public License": "LGPL-2.1"
        }
        
        for variant, canonical in mappings.items():
            if variant in license_name:
                return canonical
        
        return license_name
    
    def check_license_compliance(
        self,
        components: List[Component],
        allowed_licenses: List[str],
        forbidden_licenses: List[str]
    ) -> List[str]:
        """Prüfe Lizenz-Compliance."""
        violations = []
        
        for component in components:
            license_info = self.check_component_license(component)
            
            if not license_info:
                violations.append(f"{component.name}: Unknown license '{component.license_declared}'")
                continue
            
            # Prüfe gegen verbotene Lizenzen
            if license_info.license_id in forbidden_licenses:
                violations.append(f"{component.name}: Forbidden license '{license_info.license_id}'")
            
            # Prüfe gegen erlaubte Lizenzen
            if allowed_licenses and license_info.license_id not in allowed_licenses:
                violations.append(f"{component.name}: License '{license_info.license_id}' not in allow-list")
        
        return violations


class VulnerabilityScanner:
    """CVE-Vulnerability-Scanner."""
    
    def scan_components(self, components: List[Component]) -> List[Vulnerability]:
        """Scanne Komponenten nach Vulnerabilities."""
        vulnerabilities = []
        
        # Simuliere CVE-Datenbank-Lookup
        # In Produktion: OSV API, NVD API, etc.
        
        mock_vulnerabilities = {
            "requests": [
                Vulnerability(
                    cve_id="CVE-2023-32681",
                    severity="medium",
                    score=6.1,
                    title="Requests Session object does not verify requests after making first request with verify=False",
                    description="A security vulnerability in requests library",
                    published="2023-05-26T00:00:00Z",
                    affected_component="requests",
                    affected_versions=["2.30.0", "2.29.0"],
                    fixed_versions=["2.31.0"]
                )
            ],
            "urllib3": [
                Vulnerability(
                    cve_id="CVE-2023-45803",
                    severity="high",
                    score=8.1,
                    title="urllib3 Cookie request header isn't stripped on cross-origin redirects",
                    description="urllib3 vulnerability in cookie handling",
                    published="2023-10-17T00:00:00Z",
                    affected_component="urllib3",
                    affected_versions=["2.0.6", "2.0.5"],
                    fixed_versions=["2.0.7"]
                )
            ]
        }
        
        for component in components:
            if component.name in mock_vulnerabilities:
                component_vulns = mock_vulnerabilities[component.name]
                for vuln in component_vulns:
                    if component.version in vuln.affected_versions:
                        vulnerabilities.append(vuln)
        
        return vulnerabilities


class SBOMGenerator:
    """SBOM-Generator."""
    
    def __init__(self):
        self.dependency_collector = DependencyCollector()
        self.license_checker = LicenseChecker()
        self.vulnerability_scanner = VulnerabilityScanner()
    
    def generate_artifact_sbom(
        self,
        artifact: BuildArtifact,
        template: ProgramTemplate
    ) -> SBOM:
        """
        Generiere SBOM für Build-Artefakt.
        
        Args:
            artifact: Build-Artefakt
            template: Program-Template
            
        Returns:
            SBOM
        """
        logger.info(f"Generating SBOM for artifact: {artifact.name}")
        
        # Sammle Abhängigkeiten
        components = self.dependency_collector.collect_python_dependencies()
        
        # Scanne Vulnerabilities
        vulnerabilities = self.vulnerability_scanner.scan_components(components)
        
        # Sammle Lizenz-Informationen
        licenses_found = []
        for component in components:
            license_info = self.license_checker.check_component_license(component)
            if license_info and license_info not in licenses_found:
                licenses_found.append(license_info)
        
        # Erstelle SBOM
        sbom = SBOM(
            sbom_id=f"sbom-{artifact.name}-{artifact.version}",
            name=artifact.name,
            version=artifact.version,
            created_at=datetime.utcnow().isoformat(),
            source_artifact=str(artifact.file_path),
            components=components,
            vulnerabilities=vulnerabilities,
            licenses_found=licenses_found
        )
        
        logger.info(f"SBOM generated: {len(components)} components, {len(vulnerabilities)} vulnerabilities")
        return sbom
    
    def generate_container_sbom(
        self,
        container_image: ContainerImage,
        template: ProgramTemplate
    ) -> SBOM:
        """
        Generiere SBOM für Container-Image.
        
        Args:
            container_image: Container-Image
            template: Program-Template
            
        Returns:
            SBOM
        """
        logger.info(f"Generating SBOM for container: {container_image.name}:{container_image.tag}")
        
        # Sammle Container-Abhängigkeiten
        components = self.dependency_collector.collect_container_dependencies(container_image)
        
        # Füge Anwendungsabhängigkeiten hinzu
        app_components = self.dependency_collector.collect_python_dependencies()
        components.extend(app_components)
        
        # Scanne Vulnerabilities
        vulnerabilities = self.vulnerability_scanner.scan_components(components)
        
        # Sammle Lizenz-Informationen
        licenses_found = []
        for component in components:
            license_info = self.license_checker.check_component_license(component)
            if license_info and license_info not in licenses_found:
                licenses_found.append(license_info)
        
        # Erstelle SBOM
        sbom = SBOM(
            sbom_id=f"sbom-{container_image.name}-{container_image.tag}",
            name=container_image.name,
            version=container_image.tag,
            created_at=datetime.utcnow().isoformat(),
            source_container=f"{container_image.name}:{container_image.tag}",
            components=components,
            vulnerabilities=vulnerabilities,
            licenses_found=licenses_found
        )
        
        logger.info(f"Container SBOM generated: {len(components)} components, {len(vulnerabilities)} vulnerabilities")
        return sbom
    
    def check_sbom_compliance(
        self,
        sbom: SBOM,
        allowed_licenses: List[str],
        forbidden_licenses: List[str],
        max_critical_vulns: int = 0,
        max_high_vulns: int = 0
    ) -> Dict[str, Any]:
        """
        Prüfe SBOM-Compliance.
        
        Args:
            sbom: SBOM
            allowed_licenses: Erlaubte Lizenzen
            forbidden_licenses: Verbotene Lizenzen
            max_critical_vulns: Max. Critical Vulnerabilities
            max_high_vulns: Max. High Vulnerabilities
            
        Returns:
            Compliance-Ergebnis
        """
        # Lizenz-Compliance
        license_violations = self.license_checker.check_license_compliance(
            sbom.components, allowed_licenses, forbidden_licenses
        )
        
        # Vulnerability-Compliance
        critical_vulns = [v for v in sbom.vulnerabilities if v.severity == "critical"]
        high_vulns = [v for v in sbom.vulnerabilities if v.severity == "high"]
        
        vulnerability_violations = []
        if len(critical_vulns) > max_critical_vulns:
            vulnerability_violations.append(f"Critical vulnerabilities: {len(critical_vulns)} (max: {max_critical_vulns})")
        if len(high_vulns) > max_high_vulns:
            vulnerability_violations.append(f"High vulnerabilities: {len(high_vulns)} (max: {max_high_vulns})")
        
        # Update SBOM
        sbom.license_violations = license_violations
        
        # Gesamt-Compliance
        all_violations = license_violations + vulnerability_violations
        compliance_status = "PASS" if not all_violations else "FAIL"
        
        return {
            "status": compliance_status,
            "license_violations": license_violations,
            "vulnerability_violations": vulnerability_violations,
            "total_violations": len(all_violations),
            "critical_vulnerabilities": len(critical_vulns),
            "high_vulnerabilities": len(high_vulns),
            "total_components": len(sbom.components),
            "unique_licenses": len(sbom.licenses_found)
        }
    
    def save_sbom(self, sbom: SBOM, output_path: Path, format: str = "json"):
        """
        Speichere SBOM.
        
        Args:
            sbom: SBOM
            output_path: Output-Pfad
            format: Format (json, cyclonedx)
        """
        if format == "cyclonedx":
            content = json.dumps(sbom.to_cyclonedx_json(), indent=2)
        else:
            content = json.dumps(sbom.to_dict(), indent=2)
        
        output_path.write_text(content)
        logger.info(f"SBOM saved: {output_path}")


# Convenience Functions
def generate_project_sbom(
    artifact: BuildArtifact,
    container_image: ContainerImage,
    template: ProgramTemplate,
    output_dir: Path
) -> Dict[str, Any]:
    """
    Convenience-Funktion für komplette SBOM-Generierung.
    
    Args:
        artifact: Build-Artefakt
        container_image: Container-Image
        template: Program-Template
        output_dir: Output-Verzeichnis
        
    Returns:
        SBOM-Ergebnisse
    """
    generator = SBOMGenerator()
    
    # Generiere SBOMs
    artifact_sbom = generator.generate_artifact_sbom(artifact, template)
    container_sbom = generator.generate_container_sbom(container_image, template)
    
    # Speichere SBOMs
    output_dir.mkdir(parents=True, exist_ok=True)
    
    artifact_sbom_path = output_dir / f"{artifact.name}_sbom.json"
    container_sbom_path = output_dir / f"{container_image.name}_sbom.json"
    
    generator.save_sbom(artifact_sbom, artifact_sbom_path)
    generator.save_sbom(container_sbom, container_sbom_path, format="cyclonedx")
    
    # Prüfe Compliance
    allowed_licenses = ["MIT", "Apache-2.0", "BSD-3-Clause"]
    forbidden_licenses = ["GPL-3.0", "AGPL-3.0"]
    
    artifact_compliance = generator.check_sbom_compliance(
        artifact_sbom, allowed_licenses, forbidden_licenses
    )
    
    container_compliance = generator.check_sbom_compliance(
        container_sbom, allowed_licenses, forbidden_licenses
    )
    
    return {
        "artifact_sbom": {
            "path": str(artifact_sbom_path),
            "components": len(artifact_sbom.components),
            "vulnerabilities": len(artifact_sbom.vulnerabilities),
            "compliance": artifact_compliance
        },
        "container_sbom": {
            "path": str(container_sbom_path),
            "components": len(container_sbom.components),
            "vulnerabilities": len(container_sbom.vulnerabilities),
            "compliance": container_compliance
        }
    }


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    from .build_system import BuildArtifact
    from .container_builder import ContainerImage
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("📋 SBOM Generator Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock-Artefakte
            mock_artifact = BuildArtifact(
                name="demo-api",
                version="1.0.0",
                artifact_type="wheel",
                file_path=temp_path / "demo-api.whl",
                size_bytes=1024,
                checksum_sha256="mock_checksum",
                created_at="2024-01-20T10:00:00Z",
                build_tool="codepipeline-build",
                build_platform="linux-x86_64",
                source_hash="mock_source_hash"
            )
            
            mock_container = ContainerImage(
                name="demo/api",
                tag="1.0.0",
                image_id="sha256:mock_id",
                size_bytes=100_000_000,
                created_at="2024-01-20T10:00:00Z",
                source_artifact="demo-api.whl",
                build_platform="linux/amd64",
                policy_compliant=True
            )
            
            # Generiere SBOMs
            results = generate_project_sbom(
                mock_artifact, mock_container, template, temp_path
            )
            
            print(f"\\nSBOM Generation Results:")
            print(f"Artifact SBOM:")
            print(f"  Components: {results['artifact_sbom']['components']}")
            print(f"  Vulnerabilities: {results['artifact_sbom']['vulnerabilities']}")
            print(f"  Compliance: {results['artifact_sbom']['compliance']['status']}")
            
            print(f"\\nContainer SBOM:")
            print(f"  Components: {results['container_sbom']['components']}")
            print(f"  Vulnerabilities: {results['container_sbom']['vulnerabilities']}")
            print(f"  Compliance: {results['container_sbom']['compliance']['status']}")
            
            # Zeige Dateien
            for sbom_type, sbom_data in results.items():
                path = Path(sbom_data['path'])
                if path.exists():
                    print(f"\\n{sbom_type.replace('_', ' ').title()} saved: {path.name} ({path.stat().st_size} bytes)")
