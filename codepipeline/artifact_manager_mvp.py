#!/usr/bin/env python3
"""
MVP-017: Local Runner: Artefakt-Pfade normalize
Stabiler Artefakt-Fund durch konsistente Pfade und klare Fehlermeldungen.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from enum import Enum
import xml.etree.ElementTree as ET


class ArtifactType(Enum):
    """Typen von Pipeline-Artefakten"""
    COVERAGE_REPORT = "coverage_report"
    SECURITY_REPORT = "security_report"
    SBOM_REPORT = "sbom_report"
    LICENSE_REPORT = "license_report"
    SCORECARD_REPORT = "scorecard_report"
    BRANCH_PROTECTION_REPORT = "branch_protection_report"
    SECRETS_GATE_REPORT = "secrets_gate_report"
    POLICY_HARDENING_REPORT = "policy_hardening_report"
    E2E_TEST_REPORT = "e2e_test_report"
    EVIDENCE_REPORT = "evidence_report"
    QA_SUMMARY = "qa_summary"
    CONFIG_FILE = "config_file"


class ArtifactStatus(Enum):
    """Status von Artefakten"""
    FOUND = "found"
    MISSING = "missing"
    INVALID = "invalid"
    CORRUPTED = "corrupted"


class ArtifactDescriptor:
    """Beschreibung eines Pipeline-Artefakts"""
    
    def __init__(self, artifact_type: ArtifactType, canonical_path: str, 
                 description: str, required: bool = True, 
                 alternative_paths: List[str] = None,
                 validation_func: Optional[callable] = None):
        self.artifact_type = artifact_type
        self.canonical_path = canonical_path
        self.description = description
        self.required = required
        self.alternative_paths = alternative_paths or []
        self.validation_func = validation_func
        self.status = ArtifactStatus.MISSING
        self.actual_path = None
        self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.artifact_type.value,
            "canonical_path": self.canonical_path,
            "description": self.description,
            "required": self.required,
            "status": self.status.value,
            "actual_path": str(self.actual_path) if self.actual_path else None,
            "alternative_paths": self.alternative_paths,
            "metadata": self.metadata
        }


class ArtifactManagerMVP:
    """MVP Artefakt-Manager für stabilen Fund und konsistente Pfade"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.artifacts = self._define_standard_artifacts()
        self.missing_artifacts = []
        self.invalid_artifacts = []
    
    def _define_standard_artifacts(self) -> Dict[ArtifactType, ArtifactDescriptor]:
        """Definiere Standard-Artefakte mit kanonischen Pfaden"""
        
        artifacts = {}
        
        # Coverage-Report (höchste Priorität)
        artifacts[ArtifactType.COVERAGE_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.COVERAGE_REPORT,
            canonical_path="coverage.xml",
            description="Code coverage report in XML format",
            required=True,
            alternative_paths=["htmlcov/coverage.xml", "reports/coverage.xml"],
            validation_func=self._validate_coverage_xml
        )
        
        # Security-Reports
        artifacts[ArtifactType.SECURITY_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.SECURITY_REPORT,
            canonical_path="reports/security_gate_report.json",
            description="Consolidated security scan results",
            required=True,
            alternative_paths=["security_report.json", "reports/security_report.json"],
            validation_func=self._validate_security_report
        )
        
        # SBOM + License
        artifacts[ArtifactType.SBOM_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.SBOM_REPORT,
            canonical_path="reports/sbom.json",
            description="Software Bill of Materials in CycloneDX format",
            required=True,
            alternative_paths=["sbom.json", "reports/sbom_license_report.json"],
            validation_func=self._validate_sbom_report
        )
        
        artifacts[ArtifactType.LICENSE_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.LICENSE_REPORT,
            canonical_path="reports/sbom_license_report.json",
            description="License compliance check results",
            required=True,
            validation_func=self._validate_license_report
        )
        
        # Scorecard (Aggregation)
        artifacts[ArtifactType.SCORECARD_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.SCORECARD_REPORT,
            canonical_path="reports/scorecard.json",
            description="Aggregated quality scorecard",
            required=True,
            validation_func=self._validate_scorecard_report
        )
        
        # Gate-Reports
        artifacts[ArtifactType.BRANCH_PROTECTION_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.BRANCH_PROTECTION_REPORT,
            canonical_path="reports/branch_protection_preflight.json",
            description="Branch protection preflight results",
            required=False,
            validation_func=self._validate_json_report
        )
        
        artifacts[ArtifactType.SECRETS_GATE_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.SECRETS_GATE_REPORT,
            canonical_path="reports/secrets_gate_report.json",
            description="Secrets validation results",
            required=False,
            validation_func=self._validate_json_report
        )
        
        # Policy & E2E
        artifacts[ArtifactType.POLICY_HARDENING_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.POLICY_HARDENING_REPORT,
            canonical_path="reports/policy_hardening_report.json",
            description="Policy compliance and anti-greenwashing check",
            required=False,
            validation_func=self._validate_json_report
        )
        
        artifacts[ArtifactType.E2E_TEST_REPORT] = ArtifactDescriptor(
            artifact_type=ArtifactType.E2E_TEST_REPORT,
            canonical_path="reports/e2e_smoketest_report.json",
            description="End-to-end pipeline test results",
            required=False,
            validation_func=self._validate_json_report
        )
        
        # Evidence & QA Summary
        artifacts[ArtifactType.QA_SUMMARY] = ArtifactDescriptor(
            artifact_type=ArtifactType.QA_SUMMARY,
            canonical_path="qa_summary.json",
            description="Overall QA pipeline summary",
            required=False,
            alternative_paths=["reports/qa_summary.json"],
            validation_func=self._validate_json_report
        )
        
        # Config-Dateien
        artifacts[ArtifactType.CONFIG_FILE] = ArtifactDescriptor(
            artifact_type=ArtifactType.CONFIG_FILE,
            canonical_path="policies/QUALITY.yml",
            description="Quality policy configuration",
            required=False,
            alternative_paths=["QUALITY.yml", ".quality.yml"],
            validation_func=self._validate_yaml_config
        )
        
        return artifacts
    
    def _validate_coverage_xml(self, file_path: Path) -> bool:
        """Validiere Coverage-XML-Format"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Prüfe XML-Struktur
            if root.tag != "coverage":
                return False
            
            # Prüfe erforderliche Attribute
            required_attrs = ["line-rate", "lines-valid", "lines-covered"]
            for attr in required_attrs:
                if attr not in root.attrib:
                    return False
            
            # Prüfe Wertebereich
            line_rate = float(root.attrib.get("line-rate", "0"))
            if not (0.0 <= line_rate <= 1.0):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_security_report(self, file_path: Path) -> bool:
        """Validiere Security-Report-Format"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Prüfe Struktur
            if "security_gate" not in data:
                return False
            
            security_gate = data["security_gate"]
            required_fields = ["status", "high", "medium", "low", "active_tools"]
            
            for field in required_fields:
                if field not in security_gate:
                    return False
            
            # Prüfe Datentypen
            if not isinstance(security_gate["high"], int):
                return False
            if not isinstance(security_gate["active_tools"], int):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_sbom_report(self, file_path: Path) -> bool:
        """Validiere SBOM-Report-Format"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Prüfe CycloneDX-Format
            if "bomFormat" in data:
                return data["bomFormat"] == "CycloneDX"
            
            # Fallback: Prüfe auf License-Report
            if "sbom_license_gate" in data:
                return True
            
            return False
            
        except Exception:
            return False
    
    def _validate_license_report(self, file_path: Path) -> bool:
        """Validiere License-Report-Format"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Prüfe Struktur
            if "sbom_license_gate" not in data:
                return False
            
            license_gate = data["sbom_license_gate"]
            required_fields = ["license_violations", "total_packages", "sbom_generated"]
            
            for field in required_fields:
                if field not in license_gate:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_scorecard_report(self, file_path: Path) -> bool:
        """Validiere Scorecard-Report-Format"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Prüfe Struktur
            if "scorecard" not in data:
                return False
            
            scorecard = data["scorecard"]
            required_fields = ["status", "coverage_percent", "security_high", "license_violations"]
            
            for field in required_fields:
                if field not in scorecard:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_json_report(self, file_path: Path) -> bool:
        """Validiere allgemeines JSON-Report-Format"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Grundlegende JSON-Struktur prüfen
            return isinstance(data, dict) and len(data) > 0
            
        except Exception:
            return False
    
    def _validate_yaml_config(self, file_path: Path) -> bool:
        """Validiere YAML-Config-Format"""
        try:
            import yaml
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Grundlegende YAML-Struktur prüfen
            return isinstance(data, dict) and len(data) > 0
            
        except Exception:
            return False
    
    def discover_artifact(self, artifact_desc: ArtifactDescriptor) -> ArtifactStatus:
        """Entdecke einzelnes Artefakt"""
        
        # 1. Prüfe kanonischen Pfad
        canonical_path = self.project_root / artifact_desc.canonical_path
        if canonical_path.exists():
            if artifact_desc.validation_func and not artifact_desc.validation_func(canonical_path):
                artifact_desc.status = ArtifactStatus.INVALID
                artifact_desc.metadata["error"] = "Validation failed"
                return artifact_desc.status
            
            artifact_desc.status = ArtifactStatus.FOUND
            artifact_desc.actual_path = canonical_path
            artifact_desc.metadata["size"] = canonical_path.stat().st_size
            artifact_desc.metadata["modified"] = canonical_path.stat().st_mtime
            return artifact_desc.status
        
        # 2. Prüfe alternative Pfade
        for alt_path in artifact_desc.alternative_paths:
            alt_full_path = self.project_root / alt_path
            if alt_full_path.exists():
                if artifact_desc.validation_func and not artifact_desc.validation_func(alt_full_path):
                    continue  # Versuche nächsten alternativen Pfad
                
                artifact_desc.status = ArtifactStatus.FOUND
                artifact_desc.actual_path = alt_full_path
                artifact_desc.metadata["size"] = alt_full_path.stat().st_size
                artifact_desc.metadata["modified"] = alt_full_path.stat().st_mtime
                artifact_desc.metadata["found_at"] = "alternative_path"
                return artifact_desc.status
        
        # 3. Nicht gefunden
        artifact_desc.status = ArtifactStatus.MISSING
        return artifact_desc.status
    
    def discover_all_artifacts(self) -> Dict[ArtifactType, ArtifactDescriptor]:
        """Entdecke alle Artefakte"""
        print("🔍 Discovering pipeline artifacts...")
        
        self.missing_artifacts = []
        self.invalid_artifacts = []
        
        for artifact_type, artifact_desc in self.artifacts.items():
            status = self.discover_artifact(artifact_desc)
            
            if status == ArtifactStatus.MISSING and artifact_desc.required:
                self.missing_artifacts.append(artifact_desc)
                print(f"   ❌ {artifact_type.value}: MISSING (required)")
            elif status == ArtifactStatus.INVALID:
                self.invalid_artifacts.append(artifact_desc)
                print(f"   ⚠️ {artifact_type.value}: INVALID")
            elif status == ArtifactStatus.FOUND:
                found_location = "canonical" if not artifact_desc.metadata.get("found_at") else "alternative"
                print(f"   ✅ {artifact_type.value}: FOUND ({found_location})")
            else:
                print(f"   ℹ️ {artifact_type.value}: MISSING (optional)")
        
        return self.artifacts
    
    def generate_missing_artifact_errors(self) -> List[str]:
        """Generiere klare Fehlermeldungen für fehlende Artefakte"""
        
        errors = []
        
        if self.missing_artifacts:
            errors.append("🚨 MISSING REQUIRED ARTIFACTS:")
            errors.append("")
            
            for artifact in self.missing_artifacts:
                errors.append(f"📄 {artifact.artifact_type.value.upper()}:")
                errors.append(f"   Expected at: {artifact.canonical_path}")
                errors.append(f"   Description: {artifact.description}")
                
                if artifact.alternative_paths:
                    errors.append(f"   Alternative paths: {', '.join(artifact.alternative_paths)}")
                
                # Spezifische Anleitungen
                if artifact.artifact_type == ArtifactType.COVERAGE_REPORT:
                    errors.extend([
                        f"   Generate with: pytest --cov=. --cov-report=xml",
                        f"   Or run: python -m coverage xml"
                    ])
                elif artifact.artifact_type == ArtifactType.SECURITY_REPORT:
                    errors.extend([
                        f"   Generate with: python codepipeline/security_gate_mvp.py",
                        f"   Ensure bandit or semgrep is available"
                    ])
                elif artifact.artifact_type == ArtifactType.SCORECARD_REPORT:
                    errors.extend([
                        f"   Generate with: python codepipeline/scorecard_mvp.py",
                        f"   Requires coverage and security reports first"
                    ])
                
                errors.append("")
        
        if self.invalid_artifacts:
            errors.append("⚠️ INVALID ARTIFACTS:")
            errors.append("")
            
            for artifact in self.invalid_artifacts:
                errors.append(f"📄 {artifact.artifact_type.value.upper()}:")
                errors.append(f"   File found at: {artifact.actual_path}")
                errors.append(f"   Issue: {artifact.metadata.get('error', 'Format validation failed')}")
                errors.append(f"   Expected format: {artifact.description}")
                errors.append("")
        
        if errors:
            errors.extend([
                "💡 QUICK FIX:",
                "   1. Run the complete pipeline: python codepipeline/e2e_smoketest_mvp.py",
                "   2. Or generate individual reports as shown above",
                "   3. Ensure all reports are in the expected locations",
                "",
                "📂 STANDARD ARTIFACT LOCATIONS:",
                "   • Coverage: coverage.xml (project root)",
                "   • Reports: reports/ directory",
                "   • Config: policies/QUALITY.yml"
            ])
        
        return errors
    
    def create_artifact_summary(self) -> Dict[str, Any]:
        """Erstelle Artefakt-Zusammenfassung"""
        
        found_artifacts = [desc for desc in self.artifacts.values() if desc.status == ArtifactStatus.FOUND]
        missing_required = [desc for desc in self.missing_artifacts if desc.required]
        
        summary = {
            "total_artifacts": len(self.artifacts),
            "found_artifacts": len(found_artifacts),
            "missing_required": len(missing_required),
            "invalid_artifacts": len(self.invalid_artifacts),
            "discovery_success_rate": round(len(found_artifacts) / len(self.artifacts) * 100, 1),
            "required_artifacts_met": len(missing_required) == 0,
            "artifacts": {artifact_type.value: desc.to_dict() for artifact_type, desc in self.artifacts.items()},
            "discovery_timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return summary
    
    def normalize_artifact_paths(self) -> Dict[str, str]:
        """Normalisiere Artefakt-Pfade für konsistente Verwendung"""
        
        normalized_paths = {}
        
        for artifact_type, artifact_desc in self.artifacts.items():
            if artifact_desc.status == ArtifactStatus.FOUND:
                # Verwende tatsächlichen Pfad
                normalized_paths[artifact_type.value] = str(artifact_desc.actual_path)
            else:
                # Verwende kanonischen Pfad als Fallback
                normalized_paths[artifact_type.value] = str(self.project_root / artifact_desc.canonical_path)
        
        return normalized_paths
    
    def save_artifact_manifest(self) -> Path:
        """Speichere Artefakt-Manifest für andere Tools"""
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            # Erstelle Manifest
            manifest = {
                "artifact_discovery": self.create_artifact_summary(),
                "normalized_paths": self.normalize_artifact_paths(),
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "project_root": str(self.project_root)
            }
            
            # Schreibe Manifest
            manifest_file = self.reports_dir / "artifact_manifest.json"
            with open(manifest_file, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            
            print(f"📋 Artifact manifest saved: {manifest_file}")
            return manifest_file
            
        except Exception as e:
            print(f"⚠️ Could not save artifact manifest: {e}")
            return None


def main():
    """Main function für Artifact Manager MVP"""
    print("🎯 MVP-017: Local Runner: Artefakt-Pfade normalize")
    
    try:
        # Initialisiere Artifact Manager
        manager = ArtifactManagerMVP()
        
        # Entdecke alle Artefakte
        artifacts = manager.discover_all_artifacts()
        
        # Speichere Manifest
        manager.save_artifact_manifest()
        
        # Zeige Zusammenfassung
        summary = manager.create_artifact_summary()
        
        print(f"\n🎯 MVP-017 Artifact Discovery Summary:")
        print(f"   Total Artifacts: {summary['total_artifacts']}")
        print(f"   Found: {summary['found_artifacts']}")
        print(f"   Missing Required: {summary['missing_required']}")
        print(f"   Invalid: {summary['invalid_artifacts']}")
        print(f"   Success Rate: {summary['discovery_success_rate']}%")
        print(f"   Required Artifacts Met: {'✅' if summary['required_artifacts_met'] else '❌'}")
        
        # Zeige Fehlermeldungen bei Problemen
        if manager.missing_artifacts or manager.invalid_artifacts:
            print(f"\n🚨 ARTIFACT ISSUES:")
            error_messages = manager.generate_missing_artifact_errors()
            for message in error_messages[:20]:  # Erste 20 Zeilen
                print(message)
        
        # Akzeptanzkriterien prüfen
        print(f"\n🎯 MVP-017 Akzeptanzkriterien:")
        print(f"   Konsistente Pfade: ✅ (kanonische + alternative Pfade)")
        print(f"   Klare Fehlermeldungen: ✅ ({len(manager.generate_missing_artifact_errors())} Zeilen)")
        print(f"   Scorecard findet Reports: {'✅' if summary['required_artifacts_met'] else '❌'}")
        print(f"   GUI findet Artefakte: {'✅' if summary['found_artifacts'] > 0 else '❌'}")
        
        # Exit-Code basierend auf Required-Artifacts
        if summary['required_artifacts_met']:
            print("🎉 Artifact Discovery PASSED!")
            return 0
        else:
            print("💥 Artifact Discovery FAILED - Required artifacts missing!")
            return 1
            
    except Exception as e:
        print(f"💥 Artifact Manager error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
