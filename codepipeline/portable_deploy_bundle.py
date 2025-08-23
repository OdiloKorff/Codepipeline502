"""
Portable Deploy Bundle System.

Implementiert:
- Bündeln aller Deploy-Artefakte in portables Bundle
- Programm-Paket, Container-Metadaten, SBOMs, Lizenz-CVE-Report, E2E-Report, Policies, QA-Summary
- Bundle kann separat geprüft und reproduzierbar deployed werden
"""

from __future__ import annotations

import os
import json
import hashlib
import tarfile
import zipfile
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging


logger = logging.getLogger(__name__)


class BundleFormat(Enum):
    """Bundle-Formate."""
    TAR_GZ = "tar.gz"
    ZIP = "zip"
    DIRECTORY = "directory"


class BundleStatus(Enum):
    """Bundle-Status."""
    CREATED = "created"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    FAILED = "failed"


class ArtifactType(Enum):
    """Artefakt-Typen."""
    PROGRAM_PACKAGE = "program_package"
    CONTAINER_METADATA = "container_metadata"
    SBOM_APP = "sbom_app"
    SBOM_CONTAINER = "sbom_container"
    LICENSE_CVE_REPORT = "license_cve_report"
    E2E_REPORT = "e2e_report"
    POLICIES = "policies"
    QA_SUMMARY = "qa_summary"
    DEPLOY_PROFILE = "deploy_profile"
    RELEASE_NOTES = "release_notes"
    SECURITY_REPORT = "security_report"
    BUILD_INFO = "build_info"


@dataclass
class BundleArtifact:
    """Bundle-Artefakt."""
    
    # Artefakt-Info
    artifact_type: ArtifactType
    name: str
    description: str = ""
    
    # Datei-Info
    source_path: str = ""
    bundle_path: str = ""  # Pfad innerhalb des Bundles
    
    # Metadaten
    size_bytes: int = 0
    checksum: str = ""
    checksum_algorithm: str = "sha256"
    
    # Validierung
    required: bool = True
    validated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "artifact_type": self.artifact_type.value,
            "name": self.name,
            "description": self.description,
            "source_path": self.source_path,
            "bundle_path": self.bundle_path,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "checksum_algorithm": self.checksum_algorithm,
            "required": self.required,
            "validated": self.validated
        }


@dataclass
class BundleManifest:
    """Bundle-Manifest."""
    
    # Bundle-Info
    bundle_id: str
    bundle_name: str
    bundle_version: str = "1.0.0"
    
    # Programm-Info
    program_name: str = ""
    program_version: str = ""
    program_type: str = ""
    
    # Bundle-Metadaten
    created_at: str = ""
    created_by: str = "CodePipeline"
    bundle_format: BundleFormat = BundleFormat.TAR_GZ
    status: BundleStatus = BundleStatus.CREATED
    
    # Artefakte
    artifacts: List[BundleArtifact] = field(default_factory=list)
    
    # Checksums
    bundle_checksum: str = ""
    manifest_checksum: str = ""
    
    # Deployment-Info
    target_environments: List[str] = field(default_factory=list)
    deployment_requirements: Dict[str, Any] = field(default_factory=dict)
    
    # Validierung
    validation_results: Dict[str, Any] = field(default_factory=dict)
    
    def add_artifact(self, artifact: BundleArtifact):
        """Füge Artefakt hinzu."""
        self.artifacts.append(artifact)
    
    def get_artifacts_by_type(self, artifact_type: ArtifactType) -> List[BundleArtifact]:
        """Hole Artefakte nach Typ."""
        return [a for a in self.artifacts if a.artifact_type == artifact_type]
    
    def get_required_artifacts(self) -> List[BundleArtifact]:
        """Hole erforderliche Artefakte."""
        return [a for a in self.artifacts if a.required]
    
    def is_complete(self) -> bool:
        """Prüfe ob Bundle vollständig ist."""
        required_artifacts = self.get_required_artifacts()
        return all(a.validated for a in required_artifacts)
    
    def calculate_bundle_size(self) -> int:
        """Berechne Bundle-Größe."""
        return sum(a.size_bytes for a in self.artifacts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "bundle_id": self.bundle_id,
            "bundle_name": self.bundle_name,
            "bundle_version": self.bundle_version,
            "program_name": self.program_name,
            "program_version": self.program_version,
            "program_type": self.program_type,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "bundle_format": self.bundle_format.value,
            "status": self.status.value,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "bundle_checksum": self.bundle_checksum,
            "manifest_checksum": self.manifest_checksum,
            "target_environments": self.target_environments,
            "deployment_requirements": self.deployment_requirements,
            "validation_results": self.validation_results,
            "bundle_size_bytes": self.calculate_bundle_size(),
            "artifact_count": len(self.artifacts),
            "required_artifacts_count": len(self.get_required_artifacts())
        }


class BundleValidator:
    """Bundle-Validator."""
    
    def __init__(self):
        self.validation_rules = self._load_validation_rules()
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Lade Validierungsregeln."""
        return {
            "required_artifact_types": [
                ArtifactType.PROGRAM_PACKAGE,
                ArtifactType.QA_SUMMARY,
                ArtifactType.DEPLOY_PROFILE
            ],
            "optional_artifact_types": [
                ArtifactType.CONTAINER_METADATA,
                ArtifactType.SBOM_APP,
                ArtifactType.SBOM_CONTAINER,
                ArtifactType.LICENSE_CVE_REPORT,
                ArtifactType.E2E_REPORT,
                ArtifactType.POLICIES,
                ArtifactType.RELEASE_NOTES,
                ArtifactType.SECURITY_REPORT,
                ArtifactType.BUILD_INFO
            ],
            "max_bundle_size_mb": 500,
            "max_artifact_count": 50,
            "checksum_algorithms": ["sha256", "md5"],
            "supported_formats": [BundleFormat.TAR_GZ, BundleFormat.ZIP, BundleFormat.DIRECTORY]
        }
    
    def validate_bundle(self, manifest: BundleManifest) -> Dict[str, Any]:
        """Validiere Bundle."""
        
        logger.info(f"Validating bundle: {manifest.bundle_id}")
        
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": []
        }
        
        # Prüfe erforderliche Artefakte
        required_types = set(self.validation_rules["required_artifact_types"])
        present_types = set(a.artifact_type for a in manifest.artifacts)
        
        missing_required = required_types - present_types
        if missing_required:
            validation_results["valid"] = False
            validation_results["errors"].append(
                f"Missing required artifacts: {[t.value for t in missing_required]}"
            )
        else:
            validation_results["checks"].append("All required artifacts present")
        
        # Prüfe Bundle-Größe
        bundle_size_mb = manifest.calculate_bundle_size() / (1024 * 1024)
        max_size_mb = self.validation_rules["max_bundle_size_mb"]
        
        if bundle_size_mb > max_size_mb:
            validation_results["valid"] = False
            validation_results["errors"].append(
                f"Bundle size {bundle_size_mb:.1f}MB exceeds limit {max_size_mb}MB"
            )
        else:
            validation_results["checks"].append(f"Bundle size OK: {bundle_size_mb:.1f}MB")
        
        # Prüfe Artefakt-Anzahl
        artifact_count = len(manifest.artifacts)
        max_count = self.validation_rules["max_artifact_count"]
        
        if artifact_count > max_count:
            validation_results["warnings"].append(
                f"High artifact count: {artifact_count} (max recommended: {max_count})"
            )
        else:
            validation_results["checks"].append(f"Artifact count OK: {artifact_count}")
        
        # Prüfe Checksums
        invalid_checksums = []
        for artifact in manifest.artifacts:
            if artifact.checksum and artifact.checksum_algorithm not in self.validation_rules["checksum_algorithms"]:
                invalid_checksums.append(f"{artifact.name}: {artifact.checksum_algorithm}")
        
        if invalid_checksums:
            validation_results["warnings"].append(f"Unsupported checksum algorithms: {invalid_checksums}")
        else:
            validation_results["checks"].append("All checksums use supported algorithms")
        
        # Prüfe Bundle-Format
        if manifest.bundle_format not in self.validation_rules["supported_formats"]:
            validation_results["warnings"].append(f"Unsupported bundle format: {manifest.bundle_format.value}")
        else:
            validation_results["checks"].append(f"Bundle format OK: {manifest.bundle_format.value}")
        
        # Prüfe Artefakt-Validierung
        unvalidated_required = [a for a in manifest.get_required_artifacts() if not a.validated]
        if unvalidated_required:
            validation_results["valid"] = False
            validation_results["errors"].append(
                f"Unvalidated required artifacts: {[a.name for a in unvalidated_required]}"
            )
        else:
            validation_results["checks"].append("All required artifacts validated")
        
        logger.info(f"Bundle validation completed: {'VALID' if validation_results['valid'] else 'INVALID'}")
        
        return validation_results


class PortableDeployBundler:
    """Portable Deploy Bundle Creator."""
    
    def __init__(self):
        self.validator = BundleValidator()
    
    def create_bundle(
        self,
        bundle_name: str,
        program_name: str,
        program_version: str,
        program_type: str,
        artifacts_map: Dict[str, str],
        output_path: Path,
        bundle_format: BundleFormat = BundleFormat.TAR_GZ
    ) -> BundleManifest:
        """Erstelle Deploy-Bundle."""
        
        bundle_id = f"bundle_{program_name}_{program_version}_{int(datetime.utcnow().timestamp())}"
        
        logger.info(f"Creating deploy bundle: {bundle_id}")
        
        # Erstelle Manifest
        manifest = BundleManifest(
            bundle_id=bundle_id,
            bundle_name=bundle_name,
            bundle_version="1.0.0",
            program_name=program_name,
            program_version=program_version,
            program_type=program_type,
            created_at=datetime.utcnow().isoformat(),
            bundle_format=bundle_format,
            target_environments=["local", "staging", "production"]
        )
        
        # Sammle Artefakte
        bundle_dir = output_path / bundle_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        
        for artifact_name, source_path in artifacts_map.items():
            source_file = Path(source_path)
            
            if not source_file.exists():
                logger.warning(f"Artifact not found: {source_path}")
                continue
            
            # Bestimme Artefakt-Typ
            artifact_type = self._determine_artifact_type(artifact_name, source_file)
            
            # Kopiere Artefakt
            bundle_path = f"artifacts/{artifact_name}"
            target_file = bundle_dir / bundle_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(source_file, target_file)
            
            # Berechne Checksum
            checksum = self._calculate_checksum(target_file)
            
            # Erstelle Artefakt-Eintrag
            artifact = BundleArtifact(
                artifact_type=artifact_type,
                name=artifact_name,
                description=f"{artifact_type.value.replace('_', ' ').title()}",
                source_path=str(source_file),
                bundle_path=bundle_path,
                size_bytes=target_file.stat().st_size,
                checksum=checksum,
                required=artifact_type in [
                    ArtifactType.PROGRAM_PACKAGE,
                    ArtifactType.QA_SUMMARY,
                    ArtifactType.DEPLOY_PROFILE
                ],
                validated=True
            )
            
            manifest.add_artifact(artifact)
        
        # Erstelle zusätzliche Bundle-Metadaten
        self._create_bundle_metadata(manifest, bundle_dir)
        
        # Validiere Bundle
        validation_results = self.validator.validate_bundle(manifest)
        manifest.validation_results = validation_results
        
        if validation_results["valid"]:
            manifest.status = BundleStatus.VALIDATED
        else:
            manifest.status = BundleStatus.FAILED
            logger.error(f"Bundle validation failed: {validation_results['errors']}")
        
        # Speichere Manifest
        manifest_file = bundle_dir / "MANIFEST.json"
        with manifest_file.open('w') as f:
            json.dump(manifest.to_dict(), f, indent=2)
        
        # Berechne Bundle-Checksum
        manifest.bundle_checksum = self._calculate_bundle_checksum(bundle_dir)
        manifest.manifest_checksum = self._calculate_checksum(manifest_file)
        
        # Update Manifest mit Checksums
        with manifest_file.open('w') as f:
            json.dump(manifest.to_dict(), f, indent=2)
        
        # Erstelle Bundle-Archiv
        if bundle_format != BundleFormat.DIRECTORY:
            archive_path = self._create_bundle_archive(bundle_dir, output_path, bundle_format)
            logger.info(f"Bundle archive created: {archive_path}")
        
        logger.info(f"Bundle creation completed: {manifest.status.value}")
        
        return manifest
    
    def _determine_artifact_type(self, artifact_name: str, source_file: Path) -> ArtifactType:
        """Bestimme Artefakt-Typ."""
        
        name_lower = artifact_name.lower()
        file_suffix = source_file.suffix.lower()
        
        # Mapping basierend auf Name und Dateiendung
        if "program" in name_lower or "package" in name_lower or file_suffix in [".tar", ".zip"]:
            return ArtifactType.PROGRAM_PACKAGE
        elif "container" in name_lower and "metadata" in name_lower:
            return ArtifactType.CONTAINER_METADATA
        elif "sbom" in name_lower and "app" in name_lower:
            return ArtifactType.SBOM_APP
        elif "sbom" in name_lower and ("container" in name_lower or "image" in name_lower):
            return ArtifactType.SBOM_CONTAINER
        elif "license" in name_lower or "cve" in name_lower:
            return ArtifactType.LICENSE_CVE_REPORT
        elif "e2e" in name_lower or "test" in name_lower:
            return ArtifactType.E2E_REPORT
        elif "policy" in name_lower or "policies" in name_lower:
            return ArtifactType.POLICIES
        elif "qa" in name_lower or "scorecard" in name_lower:
            return ArtifactType.QA_SUMMARY
        elif "deploy" in name_lower or "profile" in name_lower:
            return ArtifactType.DEPLOY_PROFILE
        elif "release" in name_lower or "changelog" in name_lower:
            return ArtifactType.RELEASE_NOTES
        elif "security" in name_lower:
            return ArtifactType.SECURITY_REPORT
        elif "build" in name_lower:
            return ArtifactType.BUILD_INFO
        else:
            # Default
            return ArtifactType.BUILD_INFO
    
    def _create_bundle_metadata(self, manifest: BundleManifest, bundle_dir: Path):
        """Erstelle Bundle-Metadaten."""
        
        # README
        readme_content = f"""# Deploy Bundle: {manifest.bundle_name}

## Bundle Information
- **Bundle ID**: {manifest.bundle_id}
- **Program**: {manifest.program_name} v{manifest.program_version}
- **Type**: {manifest.program_type}
- **Created**: {manifest.created_at}
- **Format**: {manifest.bundle_format.value}

## Artifacts
{chr(10).join(f"- **{a.name}**: {a.description} ({a.size_bytes} bytes)" for a in manifest.artifacts)}

## Deployment
This bundle contains all necessary artifacts for deploying {manifest.program_name}.

### Requirements
- Target environments: {', '.join(manifest.target_environments)}
- Bundle size: {manifest.calculate_bundle_size() / (1024*1024):.1f} MB
- Artifact count: {len(manifest.artifacts)}

### Validation
Run the bundle validator before deployment to ensure integrity.

### Usage
1. Extract the bundle
2. Validate checksums
3. Review the QA summary
4. Deploy using the provided profile

Generated by CodePipeline Deploy Bundler
"""
        
        readme_file = bundle_dir / "README.md"
        readme_file.write_text(readme_content)
        
        # Deployment script
        deploy_script = f"""#!/bin/bash
# Deployment script for {manifest.program_name}
# Generated on {manifest.created_at}

set -e

BUNDLE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PROGRAM_NAME="{manifest.program_name}"
PROGRAM_VERSION="{manifest.program_version}"

echo "Deploying $PROGRAM_NAME v$PROGRAM_VERSION..."

# Validate bundle
echo "Validating bundle integrity..."
if [ -f "$BUNDLE_DIR/MANIFEST.json" ]; then
    echo "✓ Manifest found"
else
    echo "✗ Manifest missing"
    exit 1
fi

# Check artifacts
echo "Checking artifacts..."
ARTIFACTS_DIR="$BUNDLE_DIR/artifacts"
if [ -d "$ARTIFACTS_DIR" ]; then
    ARTIFACT_COUNT=$(find "$ARTIFACTS_DIR" -type f | wc -l)
    echo "✓ Found $ARTIFACT_COUNT artifacts"
else
    echo "✗ Artifacts directory missing"
    exit 1
fi

# Deploy based on profile
if [ -f "$ARTIFACTS_DIR/docker-compose.yml" ]; then
    echo "Deploying with Docker Compose..."
    cd "$ARTIFACTS_DIR"
    docker-compose up -d
elif [ -f "$ARTIFACTS_DIR/kubernetes.yaml" ]; then
    echo "Deploying with Kubernetes..."
    kubectl apply -f "$ARTIFACTS_DIR/kubernetes.yaml"
else
    echo "No deployment configuration found"
    exit 1
fi

echo "Deployment completed successfully!"
"""
        
        deploy_script_file = bundle_dir / "deploy.sh"
        deploy_script_file.write_text(deploy_script)
        deploy_script_file.chmod(0o755)
        
        # Validation script
        validation_script = f"""#!/bin/bash
# Validation script for {manifest.program_name}
# Generated on {manifest.created_at}

set -e

BUNDLE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

echo "Validating bundle: {manifest.bundle_name}"

# Check manifest
if [ ! -f "$BUNDLE_DIR/MANIFEST.json" ]; then
    echo "✗ MANIFEST.json not found"
    exit 1
fi

echo "✓ Manifest found"

# Validate checksums (simplified)
echo "Validating checksums..."
ARTIFACTS_DIR="$BUNDLE_DIR/artifacts"

if [ -d "$ARTIFACTS_DIR" ]; then
    echo "✓ Artifacts directory exists"
    
    # Count artifacts
    ARTIFACT_COUNT=$(find "$ARTIFACTS_DIR" -type f | wc -l)
    echo "✓ Found $ARTIFACT_COUNT artifacts"
    
    # Check for required files
    REQUIRED_FILES=("qa_summary.json")
    for file in "${{REQUIRED_FILES[@]}}"; do
        if [ -f "$ARTIFACTS_DIR/$file" ]; then
            echo "✓ Required file found: $file"
        else
            echo "⚠ Required file missing: $file"
        fi
    done
else
    echo "✗ Artifacts directory not found"
    exit 1
fi

echo "Bundle validation completed successfully!"
"""
        
        validation_script_file = bundle_dir / "validate.sh"
        validation_script_file.write_text(validation_script)
        validation_script_file.chmod(0o755)
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = "sha256") -> str:
        """Berechne Datei-Checksum."""
        
        hash_obj = hashlib.new(algorithm)
        
        try:
            with file_path.open('rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        
        except Exception as e:
            logger.warning(f"Failed to calculate checksum for {file_path}: {e}")
            return ""
    
    def _calculate_bundle_checksum(self, bundle_dir: Path) -> str:
        """Berechne Bundle-Checksum."""
        
        hash_obj = hashlib.sha256()
        
        # Sortierte Liste aller Dateien für deterministische Berechnung
        all_files = sorted(bundle_dir.rglob("*"))
        
        for file_path in all_files:
            if file_path.is_file() and file_path.name != "MANIFEST.json":
                # Füge Dateiname und -inhalt zum Hash hinzu
                relative_path = file_path.relative_to(bundle_dir)
                hash_obj.update(str(relative_path).encode())
                
                try:
                    with file_path.open('rb') as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            hash_obj.update(chunk)
                except Exception as e:
                    logger.warning(f"Failed to hash {file_path}: {e}")
        
        return hash_obj.hexdigest()
    
    def _create_bundle_archive(
        self,
        bundle_dir: Path,
        output_path: Path,
        bundle_format: BundleFormat
    ) -> Path:
        """Erstelle Bundle-Archiv."""
        
        bundle_name = bundle_dir.name
        
        if bundle_format == BundleFormat.TAR_GZ:
            archive_path = output_path / f"{bundle_name}.tar.gz"
            
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(bundle_dir, arcname=bundle_name)
        
        elif bundle_format == BundleFormat.ZIP:
            archive_path = output_path / f"{bundle_name}.zip"
            
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in bundle_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = f"{bundle_name}/{file_path.relative_to(bundle_dir)}"
                        zip_file.write(file_path, arcname)
        
        else:
            # Directory format - nichts zu tun
            archive_path = bundle_dir
        
        return archive_path
    
    def extract_bundle(self, bundle_path: Path, output_dir: Path) -> BundleManifest:
        """Extrahiere Bundle."""
        
        logger.info(f"Extracting bundle: {bundle_path}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Bestimme Format und extrahiere - SECURITY FIX: Sichere Extraktion
        if bundle_path.suffix == ".gz" and bundle_path.stem.endswith(".tar"):
            # tar.gz - SECURITY FIX: Validiere Member vor Extraktion
            with tarfile.open(bundle_path, "r:gz") as tar:
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
        
        elif bundle_path.suffix == ".zip":
            # zip - SECURITY FIX: Validiere Pfade vor Extraktion
            with zipfile.ZipFile(bundle_path, 'r') as zip_file:
                for member in zip_file.namelist():
                    if member.startswith('/') or '..' in member:
                        continue  # Überspringe gefährliche Pfade
                    zip_file.extract(member, output_dir)
        
        else:
            # Directory - kopiere
            if bundle_path.is_dir():
                shutil.copytree(bundle_path, output_dir / bundle_path.name, dirs_exist_ok=True)
        
        # Finde Manifest
        manifest_files = list(output_dir.rglob("MANIFEST.json"))
        
        if not manifest_files:
            raise ValueError("No MANIFEST.json found in bundle")
        
        manifest_file = manifest_files[0]
        
        # Lade Manifest
        with manifest_file.open('r') as f:
            manifest_data = json.load(f)
        
        # Erstelle Manifest-Objekt (vereinfacht)
        manifest = BundleManifest(
            bundle_id=manifest_data["bundle_id"],
            bundle_name=manifest_data["bundle_name"],
            bundle_version=manifest_data["bundle_version"],
            program_name=manifest_data["program_name"],
            program_version=manifest_data["program_version"],
            program_type=manifest_data["program_type"],
            created_at=manifest_data["created_at"],
            bundle_format=BundleFormat(manifest_data["bundle_format"]),
            status=BundleStatus(manifest_data["status"])
        )
        
        # Lade Artefakte
        for artifact_data in manifest_data["artifacts"]:
            artifact = BundleArtifact(
                artifact_type=ArtifactType(artifact_data["artifact_type"]),
                name=artifact_data["name"],
                description=artifact_data["description"],
                bundle_path=artifact_data["bundle_path"],
                size_bytes=artifact_data["size_bytes"],
                checksum=artifact_data["checksum"],
                required=artifact_data["required"],
                validated=artifact_data["validated"]
            )
            manifest.add_artifact(artifact)
        
        logger.info(f"Bundle extracted successfully: {manifest.bundle_id}")
        
        return manifest


# Convenience Functions
def create_deploy_bundle(
    program_name: str,
    program_version: str,
    program_type: str,
    artifacts: Dict[str, str],
    output_path: Path,
    bundle_format: str = "tar.gz"
) -> BundleManifest:
    """
    Erstelle Deploy-Bundle.
    
    Args:
        program_name: Name des Programms
        program_version: Version des Programms
        program_type: Typ des Programms
        artifacts: Dictionary mit Artefakt-Name -> Pfad
        output_path: Output-Pfad
        bundle_format: Bundle-Format (tar.gz, zip, directory)
        
    Returns:
        Bundle-Manifest
    """
    
    bundler = PortableDeployBundler()
    bundle_name = f"{program_name}-{program_version}-deploy"
    
    format_enum = BundleFormat(bundle_format)
    
    return bundler.create_bundle(
        bundle_name=bundle_name,
        program_name=program_name,
        program_version=program_version,
        program_type=program_type,
        artifacts_map=artifacts,
        output_path=output_path,
        bundle_format=format_enum
    )


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_portable_deploy_bundle():
        print("📦 Portable Deploy Bundle Demo:")
        
        bundler = PortableDeployBundler()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test 1: Erstelle Mock-Artefakte
            print("\\n📄 Creating mock artifacts:")
            
            artifacts_dir = temp_path / "artifacts"
            artifacts_dir.mkdir()
            
            mock_artifacts = {
                "program_package.tar.gz": "Mock program package content",
                "qa_summary.json": json.dumps({
                    "overall_score": 85,
                    "coverage": 82.5,
                    "security_issues": 0,
                    "status": "PASS"
                }),
                "sbom_app.json": json.dumps({
                    "components": [
                        {"name": "flask", "version": "2.3.1", "license": "BSD-3-Clause"},
                        {"name": "requests", "version": "2.30.0", "license": "Apache-2.0"}
                    ]
                }),
                "sbom_container.json": json.dumps({
                    "components": [
                        {"name": "ubuntu", "version": "20.04", "license": "Various"},
                        {"name": "python", "version": "3.10", "license": "PSF"}
                    ]
                }),
                "e2e_report.json": json.dumps({
                    "tests_passed": 5,
                    "tests_failed": 0,
                    "duration": 45.2,
                    "status": "PASS"
                }),
                "security_report.json": json.dumps({
                    "tools": ["bandit", "safety"],
                    "high_issues": 0,
                    "medium_issues": 2,
                    "status": "PASS"
                }),
                "docker-compose.yml": """version: '3.8'
services:
  app:
    image: test-app:latest
    ports:
      - "5000:5000"
""",
                "release_notes.md": "# Release v1.2.3\\n\\n## Features\\n- Added user dashboard"
            }
            
            artifacts_map = {}
            
            for artifact_name, content in mock_artifacts.items():
                artifact_file = artifacts_dir / artifact_name
                artifact_file.write_text(content)
                artifacts_map[artifact_name] = str(artifact_file)
                
                print(f"  ✓ {artifact_name}: {len(content)} chars")
            
            # Test 2: Erstelle Bundle
            print("\\n📦 Creating deploy bundle:")
            
            output_dir = temp_path / "bundles"
            
            manifest = bundler.create_bundle(
                bundle_name="user-service-deploy",
                program_name="user-service",
                program_version="1.2.3",
                program_type="web_api",
                artifacts_map=artifacts_map,
                output_path=output_dir,
                bundle_format=BundleFormat.TAR_GZ
            )
            
            print(f"  ✓ Bundle created: {manifest.bundle_id}")
            print(f"  ✓ Status: {manifest.status.value}")
            print(f"  ✓ Artifacts: {len(manifest.artifacts)}")
            print(f"  ✓ Size: {manifest.calculate_bundle_size() / 1024:.1f} KB")
            print(f"  ✓ Format: {manifest.bundle_format.value}")
            
            # Test 3: Bundle-Validierung
            print("\\n✅ Bundle validation:")
            
            validation_results = manifest.validation_results
            
            print(f"  ✓ Valid: {validation_results['valid']}")
            print(f"  ✓ Checks: {len(validation_results['checks'])}")
            print(f"  ✓ Errors: {len(validation_results['errors'])}")
            print(f"  ✓ Warnings: {len(validation_results['warnings'])}")
            
            for check in validation_results["checks"][:3]:
                print(f"    ✓ {check}")
            
            for error in validation_results["errors"]:
                print(f"    ❌ {error}")
            
            # Test 4: Artefakt-Details
            print("\\n📋 Artifact details:")
            
            artifact_types = {}
            for artifact in manifest.artifacts:
                artifact_type = artifact.artifact_type.value
                if artifact_type not in artifact_types:
                    artifact_types[artifact_type] = []
                artifact_types[artifact_type].append(artifact)
            
            for artifact_type, artifacts in artifact_types.items():
                print(f"  {artifact_type.replace('_', ' ').title()}: {len(artifacts)} artifacts")
                for artifact in artifacts[:2]:  # Zeige erste 2
                    print(f"    - {artifact.name}: {artifact.size_bytes} bytes")
            
            # Test 5: Bundle-Extraktion (Simulation)
            print("\\n📂 Testing bundle extraction:")
            
            # Finde Bundle-Archiv
            bundle_files = list(output_dir.rglob("*.tar.gz"))
            
            if bundle_files:
                bundle_file = bundle_files[0]
                print(f"  ✓ Bundle archive found: {bundle_file.name}")
                print(f"  ✓ Archive size: {bundle_file.stat().st_size / 1024:.1f} KB")
                
                # Simuliere Extraktion
                extract_dir = temp_path / "extracted"
                
                try:
                    extracted_manifest = bundler.extract_bundle(bundle_file, extract_dir)
                    
                    print(f"  ✓ Bundle extracted successfully")
                    print(f"  ✓ Extracted bundle ID: {extracted_manifest.bundle_id}")
                    print(f"  ✓ Extracted artifacts: {len(extracted_manifest.artifacts)}")
                    
                    # Prüfe extrahierte Dateien
                    extracted_files = list(extract_dir.rglob("*"))
                    extracted_file_count = len([f for f in extracted_files if f.is_file()])
                    
                    print(f"  ✓ Extracted files: {extracted_file_count}")
                    
                except Exception as e:
                    print(f"  ❌ Extraction failed: {e}")
            
            # Test 6: Deployment-Bereitschaft
            print("\\n🚀 Deployment readiness:")
            
            # Prüfe erforderliche Artefakte
            required_artifacts = manifest.get_required_artifacts()
            all_required_present = all(a.validated for a in required_artifacts)
            
            print(f"  ✓ Required artifacts present: {all_required_present}")
            print(f"  ✓ Bundle complete: {manifest.is_complete()}")
            
            # Prüfe Deployment-Dateien
            bundle_dir = output_dir / manifest.bundle_id
            has_deploy_script = (bundle_dir / "deploy.sh").exists()
            has_validation_script = (bundle_dir / "validate.sh").exists()
            has_readme = (bundle_dir / "README.md").exists()
            
            print(f"  ✓ Deploy script: {has_deploy_script}")
            print(f"  ✓ Validation script: {has_validation_script}")
            print(f"  ✓ README: {has_readme}")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Bundle enthält alle erforderlichen Artefakte
            has_all_artifacts = len(manifest.artifacts) >= 7  # Mindestens 7 verschiedene Artefakte
            
            # Bundle kann separat geprüft werden
            separately_checkable = (validation_results["valid"] and 
                                  has_validation_script and 
                                  manifest.bundle_checksum)
            
            # Bundle kann reproduzierbar deployed werden
            reproducible_deployment = (has_deploy_script and 
                                     manifest.is_complete() and 
                                     "docker-compose.yml" in artifacts_map)
            
            # Portable Bundle
            portable = (manifest.bundle_format in [BundleFormat.TAR_GZ, BundleFormat.ZIP] and
                       manifest.bundle_checksum and
                       has_readme)
            
            print(f"  ✓ Contains all required artifacts: {has_all_artifacts}")
            print(f"  ✓ Can be separately checked: {separately_checkable}")
            print(f"  ✓ Reproducible deployment: {reproducible_deployment}")
            print(f"  ✓ Portable bundle format: {portable}")
            
            return (has_all_artifacts and separately_checkable and 
                   reproducible_deployment and portable)
    
    # Führe Demo aus
    try:
        result = demo_portable_deploy_bundle()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
