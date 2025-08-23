"""
Deploy-Artefakt-Bündelung.

Packt alle für den Deploy notwendigen Artefakte zusammen:
Build-Artefakt, Container-Image-Metadaten, SBOMs, Policies, E2E-Report.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging

from .build_system import BuildArtifact
from .container_builder import ContainerImage
from .sbom_generator import SBOM
from .e2e_test_harness import E2ETestResult
from .version_manager import ReleaseInfo
from .deploy_profiles import DeployProfile


logger = logging.getLogger(__name__)


@dataclass
class PolicyBundle:
    """Policy-Bundle."""
    
    # Quality-Policies
    quality_policy: Dict[str, Any]
    security_policy: Dict[str, Any]
    license_policy: Dict[str, Any]
    
    # Deployment-Policies
    resource_limits: Dict[str, Any]
    network_policies: Dict[str, Any]
    
    # Compliance
    compliance_requirements: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class SecurityReport:
    """Konsolidierter Security-Report."""
    
    # Scan-Ergebnisse
    sast_findings: List[Dict[str, Any]] = field(default_factory=list)
    dependency_vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    container_scan_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Zusammenfassung
    total_high_severity: int = 0
    total_medium_severity: int = 0
    total_low_severity: int = 0
    
    # Policy-Compliance
    policy_violations: List[str] = field(default_factory=list)
    compliance_status: str = "UNKNOWN"  # PASS, WARN, FAIL
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class QualityReport:
    """Konsolidierter Quality-Report."""
    
    # Coverage
    code_coverage: float = 0.0
    test_coverage: float = 0.0
    
    # Code-Quality-Metriken
    cyclomatic_complexity: Optional[float] = None
    maintainability_index: Optional[float] = None
    technical_debt_ratio: Optional[float] = None
    
    # Test-Ergebnisse
    unit_tests_passed: int = 0
    unit_tests_total: int = 0
    integration_tests_passed: int = 0
    integration_tests_total: int = 0
    
    # Linter-Ergebnisse
    linter_warnings: int = 0
    linter_errors: int = 0
    
    # Scorecard
    overall_score: float = 0.0
    quality_gate_status: str = "UNKNOWN"  # PASS, WARN, FAIL
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class DeployArtifact:
    """Einzelnes Deploy-Artefakt."""
    
    # Artefakt-Identifikation
    name: str
    type: str  # build, container, sbom, policy, report, etc.
    file_path: Path
    
    # Metadaten
    size_bytes: int
    checksum_sha256: str
    created_at: str
    
    # Zusätzliche Metadaten
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["file_path"] = str(self.file_path)
        return result


@dataclass
class DeployBundle:
    """Deploy-Bundle mit allen Artefakten."""
    
    # Bundle-Metadaten
    bundle_id: str
    name: str
    version: str
    created_at: str
    
    # Kern-Artefakte
    build_artifact: Optional[BuildArtifact] = None
    container_image: Optional[ContainerImage] = None
    container_build_result: Optional[Dict[str, Any]] = None
    
    # SBOMs
    application_sbom: Optional[SBOM] = None
    container_sbom: Optional[SBOM] = None
    
    # Reports
    security_report: Optional[SecurityReport] = None
    quality_report: Optional[QualityReport] = None
    e2e_test_results: List[E2ETestResult] = field(default_factory=list)
    
    # Policies und Konfiguration
    policy_bundle: Optional[PolicyBundle] = None
    deploy_profiles: List[DeployProfile] = field(default_factory=list)
    
    # Release-Informationen
    release_info: Optional[ReleaseInfo] = None
    
    # Artefakt-Liste
    artifacts: List[DeployArtifact] = field(default_factory=list)
    
    # Bundle-Eigenschaften
    bundle_size_bytes: int = 0
    bundle_checksum: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        
        # Konvertiere komplexe Objekte
        if self.build_artifact:
            result["build_artifact"] = self.build_artifact.to_dict()
        if self.container_image:
            result["container_image"] = self.container_image.to_dict()
        if self.container_build_result:
            result["container_build_result"] = self.container_build_result
        if self.application_sbom:
            result["application_sbom"] = self.application_sbom.to_dict()
        if self.container_sbom:
            result["container_sbom"] = self.container_sbom.to_dict()
        if self.policy_bundle:
            result["policy_bundle"] = self.policy_bundle.to_dict()
        if self.release_info:
            result["release_info"] = self.release_info.to_dict()
        
        result["deploy_profiles"] = [p.to_dict() for p in self.deploy_profiles]
        result["e2e_test_results"] = [r.to_dict() for r in self.e2e_test_results]
        result["artifacts"] = [a.to_dict() for a in self.artifacts]
        
        return result


class DeployBundleBuilder:
    """Builder für Deploy-Bundles."""
    
    def __init__(self):
        self.bundle = None
        self.temp_dir = None
    
    def create_bundle(
        self,
        bundle_name: str,
        version: str,
        bundle_id: Optional[str] = None
    ) -> DeployBundleBuilder:
        """Erstelle neues Bundle."""
        if bundle_id is None:
            bundle_id = f"{bundle_name}-{version}-{int(datetime.utcnow().timestamp())}"
        
        self.bundle = DeployBundle(
            bundle_id=bundle_id,
            name=bundle_name,
            version=version,
            created_at=datetime.utcnow().isoformat()
        )
        
        # Erstelle temporäres Arbeitsverzeichnis
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"deploy_bundle_{bundle_id}_"))
        logger.info(f"Created deploy bundle: {bundle_id}")
        
        return self
    
    def add_build_artifact(self, build_artifact: BuildArtifact) -> DeployBundleBuilder:
        """Füge Build-Artefakt hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        self.bundle.build_artifact = build_artifact
        
        # Kopiere Artefakt-Datei
        if build_artifact.file_path.exists():
            dest_path = self.temp_dir / "build" / build_artifact.file_path.name
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(build_artifact.file_path, dest_path)
            
            self._add_artifact(
                name=f"build-{build_artifact.name}",
                type="build",
                file_path=dest_path,
                metadata={
                    "artifact_type": build_artifact.artifact_type,
                    "build_tool": build_artifact.build_tool,
                    "build_platform": build_artifact.build_platform
                }
            )
        
        logger.info(f"Added build artifact: {build_artifact.name}")
        return self
    
    def add_container_image(
        self,
        container_image: ContainerImage,
        container_build_result: Optional[Dict[str, Any]] = None
    ) -> DeployBundleBuilder:
        """Füge Container-Image hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        self.bundle.container_image = container_image
        self.bundle.container_build_result = container_build_result
        
        # Erstelle Container-Metadaten-Datei
        container_metadata = {
            "image": container_image.to_dict(),
            "build_result": container_build_result if container_build_result else None
        }
        
        metadata_path = self.temp_dir / "container" / "metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        
        with metadata_path.open('w') as f:
            json.dump(container_metadata, f, indent=2)
        
        self._add_artifact(
            name=f"container-{container_image.name}",
            type="container_metadata",
            file_path=metadata_path,
            metadata={
                "image_name": container_image.name,
                "image_tag": container_image.tag,
                "image_size": container_image.size_bytes,
                "policy_compliant": container_image.policy_compliant
            }
        )
        
        logger.info(f"Added container image: {container_image.name}:{container_image.tag}")
        return self
    
    def add_sboms(
        self,
        application_sbom: Optional[SBOM] = None,
        container_sbom: Optional[SBOM] = None
    ) -> DeployBundleBuilder:
        """Füge SBOMs hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        sbom_dir = self.temp_dir / "sbom"
        sbom_dir.mkdir(parents=True, exist_ok=True)
        
        if application_sbom:
            self.bundle.application_sbom = application_sbom
            
            app_sbom_path = sbom_dir / "application_sbom.json"
            with app_sbom_path.open('w') as f:
                json.dump(application_sbom.to_dict(), f, indent=2)
            
            self._add_artifact(
                name="application-sbom",
                type="sbom",
                file_path=app_sbom_path,
                metadata={
                    "sbom_type": "application",
                    "components": len(application_sbom.components),
                    "vulnerabilities": len(application_sbom.vulnerabilities)
                }
            )
        
        if container_sbom:
            self.bundle.container_sbom = container_sbom
            
            container_sbom_path = sbom_dir / "container_sbom.json"
            with container_sbom_path.open('w') as f:
                json.dump(container_sbom.to_cyclonedx_json(), f, indent=2)
            
            self._add_artifact(
                name="container-sbom",
                type="sbom",
                file_path=container_sbom_path,
                metadata={
                    "sbom_type": "container",
                    "format": "cyclonedx",
                    "components": len(container_sbom.components),
                    "vulnerabilities": len(container_sbom.vulnerabilities)
                }
            )
        
        logger.info("Added SBOMs to bundle")
        return self
    
    def add_security_report(self, security_report: SecurityReport) -> DeployBundleBuilder:
        """Füge Security-Report hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        self.bundle.security_report = security_report
        
        # Speichere Security-Report
        security_path = self.temp_dir / "reports" / "security_report.json"
        security_path.parent.mkdir(parents=True, exist_ok=True)
        
        with security_path.open('w') as f:
            json.dump(security_report.to_dict(), f, indent=2)
        
        self._add_artifact(
            name="security-report",
            type="security_report",
            file_path=security_path,
            metadata={
                "total_findings": len(security_report.sast_findings) + len(security_report.dependency_vulnerabilities),
                "high_severity": security_report.total_high_severity,
                "compliance_status": security_report.compliance_status
            }
        )
        
        logger.info("Added security report to bundle")
        return self
    
    def add_quality_report(self, quality_report: QualityReport) -> DeployBundleBuilder:
        """Füge Quality-Report hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        self.bundle.quality_report = quality_report
        
        # Speichere Quality-Report
        quality_path = self.temp_dir / "reports" / "quality_report.json"
        quality_path.parent.mkdir(parents=True, exist_ok=True)
        
        with quality_path.open('w') as f:
            json.dump(quality_report.to_dict(), f, indent=2)
        
        self._add_artifact(
            name="quality-report",
            type="quality_report",
            file_path=quality_path,
            metadata={
                "code_coverage": quality_report.code_coverage,
                "overall_score": quality_report.overall_score,
                "quality_gate_status": quality_report.quality_gate_status
            }
        )
        
        logger.info("Added quality report to bundle")
        return self
    
    def add_e2e_test_results(self, e2e_results: List[E2ETestResult]) -> DeployBundleBuilder:
        """Füge E2E-Test-Ergebnisse hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        self.bundle.e2e_test_results = e2e_results
        
        # Speichere E2E-Ergebnisse
        e2e_dir = self.temp_dir / "e2e_results"
        e2e_dir.mkdir(parents=True, exist_ok=True)
        
        for i, result in enumerate(e2e_results):
            result_path = e2e_dir / f"e2e_test_{i+1}.json"
            
            with result_path.open('w') as f:
                json.dump(result.to_dict(), f, indent=2)
            
            self._add_artifact(
                name=f"e2e-test-{result.test_name}",
                type="e2e_test_result",
                file_path=result_path,
                metadata={
                    "test_name": result.test_name,
                    "overall_status": result.overall_status,
                    "duration": result.duration_seconds,
                    "interactions_passed": result.interactions_passed
                }
            )
        
        logger.info(f"Added {len(e2e_results)} E2E test results to bundle")
        return self
    
    def add_policy_bundle(self, policy_bundle: PolicyBundle) -> DeployBundleBuilder:
        """Füge Policy-Bundle hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        self.bundle.policy_bundle = policy_bundle
        
        # Speichere Policy-Bundle
        policy_path = self.temp_dir / "policies" / "policy_bundle.json"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        
        with policy_path.open('w') as f:
            json.dump(policy_bundle.to_dict(), f, indent=2)
        
        self._add_artifact(
            name="policy-bundle",
            type="policy_bundle",
            file_path=policy_path,
            metadata={
                "compliance_requirements": len(policy_bundle.compliance_requirements)
            }
        )
        
        logger.info("Added policy bundle")
        return self
    
    def add_deploy_profiles(self, deploy_profiles: List[DeployProfile]) -> DeployBundleBuilder:
        """Füge Deploy-Profile hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        self.bundle.deploy_profiles = deploy_profiles
        
        # Speichere Deploy-Profile
        profiles_dir = self.temp_dir / "deploy_profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        
        for profile in deploy_profiles:
            profile_path = profiles_dir / f"{profile.name}.json"
            
            with profile_path.open('w') as f:
                json.dump(profile.to_dict(), f, indent=2)
            
            self._add_artifact(
                name=f"deploy-profile-{profile.name}",
                type="deploy_profile",
                file_path=profile_path,
                metadata={
                    "profile_name": profile.name,
                    "target": profile.target.value,
                    "replicas": profile.replicas
                }
            )
        
        logger.info(f"Added {len(deploy_profiles)} deploy profiles")
        return self
    
    def add_release_info(self, release_info: ReleaseInfo) -> DeployBundleBuilder:
        """Füge Release-Informationen hinzu."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        self.bundle.release_info = release_info
        
        # Speichere Release-Info
        release_path = self.temp_dir / "release" / "release_info.json"
        release_path.parent.mkdir(parents=True, exist_ok=True)
        
        with release_path.open('w') as f:
            json.dump(release_info.to_dict(), f, indent=2)
        
        self._add_artifact(
            name="release-info",
            type="release_info",
            file_path=release_path,
            metadata={
                "version": str(release_info.version),
                "tag": release_info.tag,
                "is_prerelease": release_info.is_prerelease
            }
        )
        
        logger.info(f"Added release info: {release_info.version}")
        return self
    
    def _add_artifact(
        self,
        name: str,
        type: str,
        file_path: Path,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Füge Artefakt zur Liste hinzu."""
        if not file_path.exists():
            logger.warning(f"Artifact file does not exist: {file_path}")
            return
        
        # Berechne Checksum
        checksum = self._calculate_file_checksum(file_path)
        
        artifact = DeployArtifact(
            name=name,
            type=type,
            file_path=file_path,
            size_bytes=file_path.stat().st_size,
            checksum_sha256=checksum,
            created_at=datetime.utcnow().isoformat(),
            metadata=metadata or {}
        )
        
        self.bundle.artifacts.append(artifact)
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Berechne SHA256-Checksum einer Datei."""
        sha256_hash = hashlib.sha256()
        
        with file_path.open('rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def build_bundle(self, output_path: Path, format: str = "tar.gz") -> Path:
        """Erstelle finales Bundle."""
        if not self.bundle:
            raise RuntimeError("Bundle not created")
        
        # Erstelle Bundle-Manifest
        manifest_path = self.temp_dir / "bundle_manifest.json"
        with manifest_path.open('w') as f:
            json.dump(self.bundle.to_dict(), f, indent=2)
        
        self._add_artifact(
            name="bundle-manifest",
            type="manifest",
            file_path=manifest_path
        )
        
        # Berechne Bundle-Größe und Checksum
        self._finalize_bundle_metadata()
        
        # Erstelle gepacktes Bundle
        bundle_file_path = self._create_bundle_archive(output_path, format)
        
        logger.info(f"Deploy bundle created: {bundle_file_path}")
        return bundle_file_path
    
    def _finalize_bundle_metadata(self):
        """Finalisiere Bundle-Metadaten."""
        # Berechne Gesamt-Bundle-Größe
        total_size = sum(artifact.size_bytes for artifact in self.bundle.artifacts)
        self.bundle.bundle_size_bytes = total_size
        
        # Berechne Bundle-Checksum (basierend auf allen Artefakt-Checksums)
        combined_checksums = "".join(sorted(artifact.checksum_sha256 for artifact in self.bundle.artifacts))
        bundle_checksum = hashlib.sha256(combined_checksums.encode()).hexdigest()
        self.bundle.bundle_checksum = bundle_checksum
        
        logger.info(f"Bundle metadata: {total_size} bytes, checksum {bundle_checksum[:16]}...")
    
    def _create_bundle_archive(self, output_path: Path, format: str) -> Path:
        """Erstelle Bundle-Archiv."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "tar.gz":
            bundle_file = output_path.with_suffix('.tar.gz')
            
            with tarfile.open(bundle_file, 'w:gz') as tar:
                tar.add(self.temp_dir, arcname=self.bundle.bundle_id)
        
        elif format == "zip":
            bundle_file = output_path.with_suffix('.zip')
            
            with zipfile.ZipFile(bundle_file, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in self.temp_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = self.bundle.bundle_id + "/" + str(file_path.relative_to(self.temp_dir))
                        zip_file.write(file_path, arcname)
        
        else:
            raise ValueError(f"Unsupported bundle format: {format}")
        
        return bundle_file
    
    def cleanup(self):
        """Cleanup temporäre Dateien."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            logger.debug(f"Cleaned up temp directory: {self.temp_dir}")


class DeployBundleExtractor:
    """Extraktor für Deploy-Bundles."""
    
    @staticmethod
    def extract_bundle(bundle_path: Path, output_dir: Path) -> DeployBundle:
        """Extrahiere Deploy-Bundle."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extrahiere Archiv - SECURITY FIX: Sichere Extraktion mit Path-Validierung
        if bundle_path.suffix == '.gz':
            with tarfile.open(bundle_path, 'r:gz') as tar:
                # SECURITY FIX: Validiere alle Member vor Extraktion (verhindert Path Traversal)
                def is_safe_member(member):
                    # Verhindere Path-Traversal-Angriffe
                    if member.name.startswith('/') or '..' in member.name:
                        return False
                    # Verhindere Symlink-Angriffe
                    if member.issym() or member.islnk():
                        return False
                    return True
                
                safe_members = [m for m in tar.getmembers() if is_safe_member(m)]
                tar.extractall(output_dir, members=safe_members)
        elif bundle_path.suffix == '.zip':
            with zipfile.ZipFile(bundle_path, 'r') as zip_file:
                # SECURITY FIX: Validiere alle Pfade vor Extraktion
                for member in zip_file.namelist():
                    if member.startswith('/') or '..' in member:
                        continue  # Überspringe gefährliche Pfade
                    zip_file.extract(member, output_dir)
        else:
            raise ValueError(f"Unsupported bundle format: {bundle_path.suffix}")
        
        # Finde Bundle-Manifest
        manifest_files = list(output_dir.rglob("bundle_manifest.json"))
        if not manifest_files:
            raise RuntimeError("Bundle manifest not found")
        
        manifest_path = manifest_files[0]
        
        # Lade Bundle-Metadaten
        with manifest_path.open('r') as f:
            bundle_data = json.load(f)
        
        # Rekonstruiere Bundle-Objekt
        bundle = DeployBundle(
            bundle_id=bundle_data["bundle_id"],
            name=bundle_data["name"],
            version=bundle_data["version"],
            created_at=bundle_data["created_at"],
            bundle_size_bytes=bundle_data.get("bundle_size_bytes", 0),
            bundle_checksum=bundle_data.get("bundle_checksum", "")
        )
        
        # Lade Artefakte
        for artifact_data in bundle_data.get("artifacts", []):
            artifact = DeployArtifact(
                name=artifact_data["name"],
                type=artifact_data["type"],
                file_path=Path(artifact_data["file_path"]),
                size_bytes=artifact_data["size_bytes"],
                checksum_sha256=artifact_data["checksum_sha256"],
                created_at=artifact_data["created_at"],
                metadata=artifact_data.get("metadata", {})
            )
            bundle.artifacts.append(artifact)
        
        logger.info(f"Extracted deploy bundle: {bundle.bundle_id}")
        return bundle
    
    @staticmethod
    def validate_bundle(bundle: DeployBundle, bundle_dir: Path) -> Dict[str, Any]:
        """Validiere extrahiertes Bundle."""
        validation_results = {
            "bundle_id": bundle.bundle_id,
            "valid": True,
            "errors": [],
            "warnings": [],
            "artifact_checks": {}
        }
        
        # Prüfe Artefakte
        for artifact in bundle.artifacts:
            artifact_path = bundle_dir / artifact.file_path.name
            
            if not artifact_path.exists():
                validation_results["errors"].append(f"Missing artifact: {artifact.name}")
                validation_results["valid"] = False
                continue
            
            # Prüfe Dateigröße
            actual_size = artifact_path.stat().st_size
            if actual_size != artifact.size_bytes:
                validation_results["errors"].append(
                    f"Size mismatch for {artifact.name}: expected {artifact.size_bytes}, got {actual_size}"
                )
                validation_results["valid"] = False
            
            # Prüfe Checksum
            actual_checksum = DeployBundleBuilder()._calculate_file_checksum(artifact_path)
            if actual_checksum != artifact.checksum_sha256:
                validation_results["errors"].append(f"Checksum mismatch for {artifact.name}")
                validation_results["valid"] = False
            
            validation_results["artifact_checks"][artifact.name] = {
                "exists": True,
                "size_match": actual_size == artifact.size_bytes,
                "checksum_match": actual_checksum == artifact.checksum_sha256
            }
        
        return validation_results


# Convenience Functions
def create_complete_deploy_bundle(
    bundle_name: str,
    version: str,
    build_artifact: BuildArtifact,
    container_image: ContainerImage,
    application_sbom: SBOM,
    container_sbom: SBOM,
    security_report: SecurityReport,
    quality_report: QualityReport,
    e2e_results: List[E2ETestResult],
    deploy_profiles: List[DeployProfile],
    output_path: Path
) -> Path:
    """
    Convenience-Funktion für komplettes Deploy-Bundle.
    
    Returns:
        Pfad zum erstellten Bundle
    """
    builder = DeployBundleBuilder()
    
    try:
        bundle_path = (builder
                      .create_bundle(bundle_name, version)
                      .add_build_artifact(build_artifact)
                      .add_container_image(container_image)
                      .add_sboms(application_sbom, container_sbom)
                      .add_security_report(security_report)
                      .add_quality_report(quality_report)
                      .add_e2e_test_results(e2e_results)
                      .add_deploy_profiles(deploy_profiles)
                      .build_bundle(output_path))
        
        return bundle_path
        
    finally:
        builder.cleanup()


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    from .build_system import BuildArtifact
    from .container_builder import ContainerImage
    from .sbom_generator import SBOM
    from .deploy_profiles import DeployProfileFactory
    from .e2e_test_harness import E2ETestResult
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("📦 Deploy Bundle Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock-Artefakte erstellen
            mock_build = BuildArtifact(
                name="demo-api",
                version="1.0.0",
                artifact_type="wheel",
                file_path=temp_path / "demo.whl",
                size_bytes=1024,
                checksum_sha256="mock_checksum",
                created_at="2024-01-20T10:00:00Z",
                build_tool="codepipeline",
                build_platform="linux-x86_64",
                source_hash="mock_source"
            )
            
            # Erstelle Mock-Wheel-Datei
            mock_build.file_path.write_text("Mock wheel content")
            
            mock_container = ContainerImage(
                name="demo/api",
                tag="1.0.0",
                image_id="mock_id",
                size_bytes=100_000_000,
                created_at="2024-01-20T10:00:00Z",
                source_artifact="demo.whl",
                build_platform="linux/amd64",
                policy_compliant=True
            )
            
            mock_sbom = SBOM(
                sbom_id="demo-sbom",
                name="demo-api",
                version="1.0.0",
                created_at="2024-01-20T10:00:00Z"
            )
            
            mock_security = SecurityReport(
                total_high_severity=0,
                compliance_status="PASS"
            )
            
            mock_quality = QualityReport(
                code_coverage=85.0,
                overall_score=90.0,
                quality_gate_status="PASS"
            )
            
            mock_e2e = E2ETestResult(
                test_name="demo-e2e",
                started_at="2024-01-20T10:00:00Z",
                finished_at="2024-01-20T10:05:00Z",
                duration_seconds=300.0,
                container_id="mock_container",
                container_name="demo-test",
                container_port=8000,
                overall_status="PASS",
                container_started=True,
                health_check_passed=True,
                interactions_passed=2,
                interactions_total=2,
                log_files=[],
                test_artifacts=[]
            )
            
            mock_profile = DeployProfileFactory.create_local_profile("demo-api", template)
            
            # Erstelle Bundle
            builder = DeployBundleBuilder()
            
            try:
                bundle_path = (builder
                              .create_bundle("demo-deploy-bundle", "1.0.0")
                              .add_build_artifact(mock_build)
                              .add_container_image(mock_container)
                              .add_sboms(mock_sbom, mock_sbom)
                              .add_security_report(mock_security)
                              .add_quality_report(mock_quality)
                              .add_e2e_test_results([mock_e2e])
                              .add_deploy_profiles([mock_profile])
                              .build_bundle(temp_path / "bundle"))
                
                print(f"\\nBundle created: {bundle_path.name}")
                print(f"Bundle size: {bundle_path.stat().st_size} bytes")
                
                # Extrahiere und validiere Bundle
                extract_dir = temp_path / "extracted"
                extracted_bundle = DeployBundleExtractor.extract_bundle(bundle_path, extract_dir)
                
                print(f"\\nExtracted Bundle:")
                print(f"Bundle ID: {extracted_bundle.bundle_id}")
                print(f"Artifacts: {len(extracted_bundle.artifacts)}")
                
                validation = DeployBundleExtractor.validate_bundle(extracted_bundle, extract_dir)
                print(f"Validation: {'PASS' if validation['valid'] else 'FAIL'}")
                
                if validation['errors']:
                    print("Errors:")
                    for error in validation['errors']:
                        print(f"  - {error}")
                
            finally:
                builder.cleanup()
        
        print("\\nDemo completed!")
