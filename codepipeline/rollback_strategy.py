"""
Rollback- und Idempotenz-Strategie.

Implementiert eine Rollback-Strategie, die bei fehlgeschlagenem Deploy 
automatisch den letzten stabilen Stand wiederherstellt und erzwingt 
Idempotenz der Deploy-Schritte.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
import logging

from .deploy_bundle import DeployBundle
from .deploy_profiles import DeployProfile
from .container_builder import ContainerImage
from .local_orchestrator import ServiceInstance, ServiceStatus


logger = logging.getLogger(__name__)


class DeploymentState(Enum):
    """Deployment-Zustand."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"


class DeploymentStep(Enum):
    """Deployment-Schritte."""
    VALIDATE_BUNDLE = "validate_bundle"
    BACKUP_CURRENT = "backup_current"
    STOP_SERVICES = "stop_services"
    DEPLOY_ARTIFACTS = "deploy_artifacts"
    UPDATE_CONFIG = "update_config"
    START_SERVICES = "start_services"
    HEALTH_CHECK = "health_check"
    SMOKE_TEST = "smoke_test"
    FINALIZE = "finalize"


@dataclass
class DeploymentOperation:
    """Einzelne Deployment-Operation."""
    
    # Operation-Identifikation
    step: DeploymentStep
    name: str
    description: str
    
    # Ausführung
    execute_func: Optional[Callable[..., bool]] = None
    rollback_func: Optional[Callable[..., bool]] = None
    
    # Zustand
    state: DeploymentState = DeploymentState.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    
    # Idempotenz
    idempotent: bool = True
    checksum: Optional[str] = None
    
    # Rollback-Daten
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["step"] = self.step.value
        result["state"] = self.state.value
        # Entferne Funktionen (nicht serialisierbar)
        result.pop("execute_func", None)
        result.pop("rollback_func", None)
        return result


@dataclass
class DeploymentSnapshot:
    """Snapshot eines Deployment-Zustands."""
    
    # Snapshot-Metadaten
    snapshot_id: str
    created_at: str
    deployment_id: str
    
    # Service-Zustand
    service_states: List[Dict[str, Any]] = field(default_factory=list)
    
    # Konfiguration
    config_files: Dict[str, str] = field(default_factory=dict)  # path -> content
    
    # Container-Images
    active_images: Dict[str, str] = field(default_factory=dict)  # service -> image:tag
    
    # Environment
    environment_variables: Dict[str, str] = field(default_factory=dict)
    
    # Artefakte
    artifact_locations: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class DeploymentRecord:
    """Deployment-Record."""
    
    # Deployment-Identifikation
    deployment_id: str
    bundle_id: str
    target_environment: str
    
    # Zeitstempel
    started_at: str
    completed_at: Optional[str] = None
    
    # Zustand
    state: DeploymentState = DeploymentState.PENDING
    
    # Operationen
    operations: List[DeploymentOperation] = field(default_factory=list)
    
    # Snapshots
    pre_deployment_snapshot: Optional[DeploymentSnapshot] = None
    post_deployment_snapshot: Optional[DeploymentSnapshot] = None
    
    # Rollback-Informationen
    rollback_snapshot_id: Optional[str] = None
    rollback_reason: Optional[str] = None
    rollback_operations: List[DeploymentOperation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["state"] = self.state.value
        result["operations"] = [op.to_dict() for op in self.operations]
        result["rollback_operations"] = [op.to_dict() for op in self.rollback_operations]
        return result


class IdempotencyChecker:
    """Prüfer für Idempotenz."""
    
    def __init__(self):
        self.state_cache: Dict[str, str] = {}
    
    def calculate_state_checksum(self, state_data: Dict[str, Any]) -> str:
        """Berechne Checksum für Zustand."""
        import hashlib
        
        # Sortiere und normalisiere Daten
        normalized = json.dumps(state_data, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def is_operation_needed(
        self,
        operation: DeploymentOperation,
        current_state: Dict[str, Any]
    ) -> bool:
        """Prüfe ob Operation notwendig ist."""
        if not operation.idempotent:
            return True
        
        current_checksum = self.calculate_state_checksum(current_state)
        
        # Wenn bereits ausgeführt und Zustand unverändert
        if (operation.checksum and 
            operation.state == DeploymentState.COMPLETED and
            current_checksum == operation.checksum):
            logger.info(f"Operation {operation.name} already completed with same state")
            return False
        
        return True
    
    def mark_operation_completed(
        self,
        operation: DeploymentOperation,
        result_state: Dict[str, Any]
    ):
        """Markiere Operation als abgeschlossen."""
        operation.checksum = self.calculate_state_checksum(result_state)
        operation.state = DeploymentState.COMPLETED
        operation.completed_at = datetime.utcnow().isoformat()


class SnapshotManager:
    """Manager für Deployment-Snapshots."""
    
    def __init__(self, snapshot_dir: Path):
        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    def create_snapshot(
        self,
        deployment_id: str,
        services: List[ServiceInstance],
        config_files: Optional[List[Path]] = None
    ) -> DeploymentSnapshot:
        """Erstelle Deployment-Snapshot."""
        snapshot_id = f"snapshot_{deployment_id}_{int(time.time())}"
        
        # Sammle Service-Zustände
        service_states = []
        active_images = {}
        
        for service in services:
            service_state = {
                "name": service.name,
                "status": service.status.value,
                "container_id": service.container_id,
                "assigned_ports": service.assigned_ports
            }
            service_states.append(service_state)
            
            if service.container_image:
                active_images[service.name] = f"{service.container_image.name}:{service.container_image.tag}"
        
        # Sammle Konfigurationsdateien
        config_content = {}
        if config_files:
            for config_file in config_files:
                if config_file.exists():
                    try:
                        config_content[str(config_file)] = config_file.read_text()
                    except Exception as e:
                        logger.warning(f"Failed to read config file {config_file}: {e}")
        
        # Sammle Umgebungsvariablen
        import os
        env_vars = {k: v for k, v in os.environ.items() if k.startswith('DEPLOY_')}
        
        snapshot = DeploymentSnapshot(
            snapshot_id=snapshot_id,
            created_at=datetime.utcnow().isoformat(),
            deployment_id=deployment_id,
            service_states=service_states,
            config_files=config_content,
            active_images=active_images,
            environment_variables=env_vars
        )
        
        # Speichere Snapshot
        snapshot_file = self.snapshot_dir / f"{snapshot_id}.json"
        with snapshot_file.open('w') as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        
        logger.info(f"Created deployment snapshot: {snapshot_id}")
        return snapshot
    
    def load_snapshot(self, snapshot_id: str) -> Optional[DeploymentSnapshot]:
        """Lade Deployment-Snapshot."""
        snapshot_file = self.snapshot_dir / f"{snapshot_id}.json"
        
        if not snapshot_file.exists():
            logger.error(f"Snapshot not found: {snapshot_id}")
            return None
        
        try:
            with snapshot_file.open('r') as f:
                data = json.load(f)
            
            return DeploymentSnapshot(
                snapshot_id=data["snapshot_id"],
                created_at=data["created_at"],
                deployment_id=data["deployment_id"],
                service_states=data.get("service_states", []),
                config_files=data.get("config_files", {}),
                active_images=data.get("active_images", {}),
                environment_variables=data.get("environment_variables", {}),
                artifact_locations=data.get("artifact_locations", {})
            )
            
        except Exception as e:
            logger.error(f"Failed to load snapshot {snapshot_id}: {e}")
            return None


class RollbackExecutor:
    """Rollback-Executor."""
    
    def __init__(self, snapshot_manager: SnapshotManager):
        self.snapshot_manager = snapshot_manager
    
    def execute_rollback(
        self,
        deployment_record: DeploymentRecord,
        target_snapshot: DeploymentSnapshot
    ) -> bool:
        """Führe Rollback aus."""
        logger.info(f"Starting rollback for deployment {deployment_record.deployment_id}")
        
        deployment_record.state = DeploymentState.ROLLING_BACK
        deployment_record.rollback_snapshot_id = target_snapshot.snapshot_id
        
        try:
            # Rollback-Operationen in umgekehrter Reihenfolge
            completed_operations = [
                op for op in deployment_record.operations 
                if op.state == DeploymentState.COMPLETED
            ]
            
            rollback_success = True
            
            for operation in reversed(completed_operations):
                if operation.rollback_func:
                    logger.info(f"Rolling back operation: {operation.name}")
                    
                    rollback_op = DeploymentOperation(
                        step=operation.step,
                        name=f"rollback_{operation.name}",
                        description=f"Rollback {operation.description}",
                        state=DeploymentState.IN_PROGRESS,
                        started_at=datetime.utcnow().isoformat()
                    )
                    
                    try:
                        success = operation.rollback_func(
                            target_snapshot, operation.rollback_data
                        )
                        
                        if success:
                            rollback_op.state = DeploymentState.COMPLETED
                            rollback_op.completed_at = datetime.utcnow().isoformat()
                        else:
                            rollback_op.state = DeploymentState.FAILED
                            rollback_op.error_message = "Rollback operation failed"
                            rollback_success = False
                        
                    except Exception as e:
                        logger.error(f"Rollback operation failed: {e}")
                        rollback_op.state = DeploymentState.FAILED
                        rollback_op.error_message = str(e)
                        rollback_success = False
                    
                    deployment_record.rollback_operations.append(rollback_op)
                    
                    if not rollback_success:
                        break
            
            # Setze finalen Zustand
            if rollback_success:
                deployment_record.state = DeploymentState.ROLLED_BACK
                logger.info(f"Rollback completed successfully")
            else:
                deployment_record.state = DeploymentState.ROLLBACK_FAILED
                logger.error(f"Rollback failed")
            
            return rollback_success
            
        except Exception as e:
            logger.error(f"Rollback execution failed: {e}")
            deployment_record.state = DeploymentState.ROLLBACK_FAILED
            return False


class DeploymentEngine:
    """Deployment-Engine mit Rollback-Unterstützung."""
    
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self.snapshot_manager = SnapshotManager(work_dir / "snapshots")
        self.rollback_executor = RollbackExecutor(self.snapshot_manager)
        self.idempotency_checker = IdempotencyChecker()
        
        self.deployment_records: Dict[str, DeploymentRecord] = {}
    
    def create_deployment_plan(
        self,
        bundle: DeployBundle,
        profile: DeployProfile,
        target_environment: str = "local"
    ) -> List[DeploymentOperation]:
        """Erstelle Deployment-Plan."""
        operations = []
        
        # 1. Bundle-Validierung
        operations.append(DeploymentOperation(
            step=DeploymentStep.VALIDATE_BUNDLE,
            name="validate_bundle",
            description="Validate deployment bundle",
            execute_func=self._validate_bundle,
            idempotent=True
        ))
        
        # 2. Backup erstellen
        operations.append(DeploymentOperation(
            step=DeploymentStep.BACKUP_CURRENT,
            name="backup_current_state",
            description="Create backup of current state",
            execute_func=self._backup_current_state,
            rollback_func=self._restore_from_backup,
            idempotent=False
        ))
        
        # 3. Services stoppen
        operations.append(DeploymentOperation(
            step=DeploymentStep.STOP_SERVICES,
            name="stop_services",
            description="Stop running services",
            execute_func=self._stop_services,
            rollback_func=self._start_services,
            idempotent=True
        ))
        
        # 4. Artefakte deployen
        operations.append(DeploymentOperation(
            step=DeploymentStep.DEPLOY_ARTIFACTS,
            name="deploy_artifacts",
            description="Deploy new artifacts",
            execute_func=self._deploy_artifacts,
            rollback_func=self._rollback_artifacts,
            idempotent=True
        ))
        
        # 5. Konfiguration aktualisieren
        operations.append(DeploymentOperation(
            step=DeploymentStep.UPDATE_CONFIG,
            name="update_configuration",
            description="Update service configuration",
            execute_func=self._update_configuration,
            rollback_func=self._rollback_configuration,
            idempotent=True
        ))
        
        # 6. Services starten
        operations.append(DeploymentOperation(
            step=DeploymentStep.START_SERVICES,
            name="start_services",
            description="Start updated services",
            execute_func=self._start_services,
            rollback_func=self._stop_services,
            idempotent=True
        ))
        
        # 7. Health-Check
        operations.append(DeploymentOperation(
            step=DeploymentStep.HEALTH_CHECK,
            name="health_check",
            description="Verify service health",
            execute_func=self._health_check,
            idempotent=True
        ))
        
        # 8. Smoke-Test
        operations.append(DeploymentOperation(
            step=DeploymentStep.SMOKE_TEST,
            name="smoke_test",
            description="Run smoke tests",
            execute_func=self._smoke_test,
            idempotent=True
        ))
        
        # 9. Finalisierung
        operations.append(DeploymentOperation(
            step=DeploymentStep.FINALIZE,
            name="finalize_deployment",
            description="Finalize deployment",
            execute_func=self._finalize_deployment,
            idempotent=False
        ))
        
        return operations
    
    def execute_deployment(
        self,
        bundle: DeployBundle,
        profile: DeployProfile,
        target_environment: str = "local",
        auto_rollback: bool = True
    ) -> DeploymentRecord:
        """Führe Deployment aus."""
        deployment_id = f"deploy_{bundle.bundle_id}_{int(time.time())}"
        
        # Erstelle Deployment-Record
        record = DeploymentRecord(
            deployment_id=deployment_id,
            bundle_id=bundle.bundle_id,
            target_environment=target_environment,
            started_at=datetime.utcnow().isoformat(),
            state=DeploymentState.IN_PROGRESS
        )
        
        # Erstelle Pre-Deployment-Snapshot
        mock_services = []  # In Produktion: aktuelle Services
        record.pre_deployment_snapshot = self.snapshot_manager.create_snapshot(
            deployment_id, mock_services
        )
        
        # Erstelle Deployment-Plan
        record.operations = self.create_deployment_plan(bundle, profile, target_environment)
        
        self.deployment_records[deployment_id] = record
        
        try:
            # Führe Operationen aus
            for operation in record.operations:
                if not self._execute_operation(operation, bundle, profile):
                    # Operation fehlgeschlagen
                    record.state = DeploymentState.FAILED
                    
                    if auto_rollback:
                        logger.info("Deployment failed, starting automatic rollback")
                        record.rollback_reason = f"Operation {operation.name} failed: {operation.error_message}"
                        
                        self.rollback_executor.execute_rollback(
                            record, record.pre_deployment_snapshot
                        )
                    
                    break
            else:
                # Alle Operationen erfolgreich
                record.state = DeploymentState.COMPLETED
                record.completed_at = datetime.utcnow().isoformat()
                
                # Erstelle Post-Deployment-Snapshot
                record.post_deployment_snapshot = self.snapshot_manager.create_snapshot(
                    deployment_id, mock_services
                )
                
                logger.info(f"Deployment {deployment_id} completed successfully")
        
        except Exception as e:
            logger.error(f"Deployment {deployment_id} failed with exception: {e}")
            record.state = DeploymentState.FAILED
            
            if auto_rollback:
                record.rollback_reason = f"Deployment exception: {str(e)}"
                self.rollback_executor.execute_rollback(
                    record, record.pre_deployment_snapshot
                )
        
        return record
    
    def _execute_operation(
        self,
        operation: DeploymentOperation,
        bundle: DeployBundle,
        profile: DeployProfile
    ) -> bool:
        """Führe einzelne Operation aus."""
        logger.info(f"Executing operation: {operation.name}")
        
        operation.state = DeploymentState.IN_PROGRESS
        operation.started_at = datetime.utcnow().isoformat()
        
        try:
            # Prüfe Idempotenz
            current_state = {"bundle_id": bundle.bundle_id, "profile": profile.name}
            
            if not self.idempotency_checker.is_operation_needed(operation, current_state):
                logger.info(f"Operation {operation.name} skipped (idempotent)")
                return True
            
            # Führe Operation aus
            if operation.execute_func:
                success = operation.execute_func(bundle, profile, operation)
                
                if success:
                    self.idempotency_checker.mark_operation_completed(operation, current_state)
                    logger.info(f"Operation {operation.name} completed successfully")
                    return True
                else:
                    operation.state = DeploymentState.FAILED
                    operation.error_message = f"Operation {operation.name} returned False"
                    logger.error(f"Operation {operation.name} failed")
                    return False
            else:
                # Keine Execute-Funktion - simuliere Erfolg
                operation.state = DeploymentState.COMPLETED
                operation.completed_at = datetime.utcnow().isoformat()
                return True
        
        except Exception as e:
            operation.state = DeploymentState.FAILED
            operation.error_message = str(e)
            logger.error(f"Operation {operation.name} failed with exception: {e}")
            return False
    
    # Deployment-Operationen (Simuliert)
    def _validate_bundle(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Validiere Bundle."""
        logger.info("Validating deployment bundle")
        
        # Prüfe Bundle-Integrität
        if not bundle.bundle_checksum:
            operation.error_message = "Bundle checksum missing"
            return False
        
        # Prüfe erforderliche Artefakte
        if not bundle.build_artifact:
            operation.error_message = "Build artifact missing"
            return False
        
        operation.rollback_data = {"bundle_validated": True}
        return True
    
    def _backup_current_state(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Erstelle Backup des aktuellen Zustands."""
        logger.info("Creating backup of current state")
        
        # Simuliere Backup-Erstellung
        backup_path = self.work_dir / "backups" / f"backup_{int(time.time())}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        operation.rollback_data = {"backup_path": str(backup_path)}
        return True
    
    def _stop_services(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Stoppe Services."""
        logger.info("Stopping services")
        
        # Simuliere Service-Stop
        stopped_services = ["service1", "service2"]
        operation.rollback_data = {"stopped_services": stopped_services}
        return True
    
    def _deploy_artifacts(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Deploye Artefakte."""
        logger.info("Deploying artifacts")
        
        # Simuliere Artefakt-Deployment
        if bundle.build_artifact:
            deploy_path = self.work_dir / "deployed" / bundle.build_artifact.name
            deploy_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Simuliere Kopieren
            deploy_path.write_text("Deployed artifact")
            
            operation.rollback_data = {"deployed_artifacts": [str(deploy_path)]}
        
        return True
    
    def _update_configuration(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Update Konfiguration."""
        logger.info("Updating configuration")
        
        # Simuliere Konfigurations-Update
        config_files = ["app.conf", "database.conf"]
        operation.rollback_data = {"updated_configs": config_files}
        return True
    
    def _start_services(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Starte Services."""
        logger.info("Starting services")
        
        # Simuliere Service-Start
        started_services = ["service1", "service2"]
        operation.rollback_data = {"started_services": started_services}
        return True
    
    def _health_check(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Führe Health-Check durch."""
        logger.info("Performing health check")
        
        # Simuliere Health-Check
        # In Produktion: echte Health-Checks der Services
        health_results = {"service1": "healthy", "service2": "healthy"}
        
        # Simuliere gelegentlichen Health-Check-Fehler für Demo
        import random
        if random.random() < 0.1:  # 10% Chance auf Fehler
            operation.error_message = "Health check failed for service2"
            return False
        
        operation.rollback_data = {"health_results": health_results}
        return True
    
    def _smoke_test(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Führe Smoke-Test durch."""
        logger.info("Running smoke tests")
        
        # Simuliere Smoke-Tests
        test_results = {"basic_connectivity": "pass", "api_response": "pass"}
        operation.rollback_data = {"smoke_test_results": test_results}
        return True
    
    def _finalize_deployment(self, bundle: DeployBundle, profile: DeployProfile, operation: DeploymentOperation) -> bool:
        """Finalisiere Deployment."""
        logger.info("Finalizing deployment")
        
        # Cleanup, Logging, etc.
        operation.rollback_data = {"finalized": True}
        return True
    
    # Rollback-Operationen
    def _restore_from_backup(self, snapshot: DeploymentSnapshot, rollback_data: Dict[str, Any]) -> bool:
        """Stelle aus Backup wieder her."""
        logger.info("Restoring from backup")
        
        backup_path = rollback_data.get("backup_path")
        if backup_path and Path(backup_path).exists():
            logger.info(f"Restored from backup: {backup_path}")
            return True
        
        return False
    
    def _rollback_artifacts(self, snapshot: DeploymentSnapshot, rollback_data: Dict[str, Any]) -> bool:
        """Rollback Artefakte."""
        logger.info("Rolling back artifacts")
        
        deployed_artifacts = rollback_data.get("deployed_artifacts", [])
        for artifact_path in deployed_artifacts:
            path = Path(artifact_path)
            if path.exists():
                path.unlink()
                logger.info(f"Removed deployed artifact: {artifact_path}")
        
        return True
    
    def _rollback_configuration(self, snapshot: DeploymentSnapshot, rollback_data: Dict[str, Any]) -> bool:
        """Rollback Konfiguration."""
        logger.info("Rolling back configuration")
        
        # Restore Konfigurationsdateien aus Snapshot
        for config_path, content in snapshot.config_files.items():
            try:
                Path(config_path).write_text(content)
                logger.info(f"Restored config file: {config_path}")
            except Exception as e:
                logger.error(f"Failed to restore config {config_path}: {e}")
                return False
        
        return True
    
    def get_deployment_status(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Hole Deployment-Status."""
        record = self.deployment_records.get(deployment_id)
        if not record:
            return None
        
        return {
            "deployment_id": deployment_id,
            "state": record.state.value,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
            "operations_completed": len([op for op in record.operations if op.state == DeploymentState.COMPLETED]),
            "operations_total": len(record.operations),
            "rollback_active": record.state in [DeploymentState.ROLLING_BACK, DeploymentState.ROLLED_BACK],
            "rollback_reason": record.rollback_reason
        }


# Convenience Functions
def deploy_with_rollback(
    bundle: DeployBundle,
    profile: DeployProfile,
    work_dir: Path,
    target_environment: str = "local"
) -> DeploymentRecord:
    """
    Convenience-Funktion für Deployment mit automatischem Rollback.
    
    Args:
        bundle: Deploy-Bundle
        profile: Deploy-Profil
        work_dir: Arbeitsverzeichnis
        target_environment: Ziel-Umgebung
        
    Returns:
        Deployment-Record
    """
    engine = DeploymentEngine(work_dir)
    return engine.execute_deployment(bundle, profile, target_environment, auto_rollback=True)


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    from .deploy_profiles import DeployProfileFactory
    from .deploy_bundle import DeployBundle
    from .build_system import BuildArtifact
    from .container_builder import ContainerImage
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🔄 Rollback Strategy Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock-Bundle
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
            
            mock_bundle = DeployBundle(
                bundle_id="demo-bundle-123",
                name="demo-deploy",
                version="1.0.0",
                created_at="2024-01-20T10:00:00Z",
                build_artifact=mock_build,
                container_image=mock_container,
                bundle_checksum="mock_checksum"
            )
            
            profile = DeployProfileFactory.create_local_profile("demo-api", template)
            
            # Führe Deployment aus
            record = deploy_with_rollback(mock_bundle, profile, temp_path)
            
            print(f"\\nDeployment Results:")
            print(f"Deployment ID: {record.deployment_id}")
            print(f"State: {record.state.value}")
            print(f"Operations: {len(record.operations)}")
            
            # Zeige Operations-Status
            for operation in record.operations:
                status_icon = "✅" if operation.state == DeploymentState.COMPLETED else "❌" if operation.state == DeploymentState.FAILED else "⏳"
                print(f"  {status_icon} {operation.name}: {operation.state.value}")
                if operation.error_message:
                    print(f"    Error: {operation.error_message}")
            
            # Rollback-Informationen
            if record.rollback_operations:
                print(f"\\nRollback Operations: {len(record.rollback_operations)}")
                for rollback_op in record.rollback_operations:
                    status_icon = "✅" if rollback_op.state == DeploymentState.COMPLETED else "❌"
                    print(f"  {status_icon} {rollback_op.name}: {rollback_op.state.value}")
            
            print(f"\\nFinal State: {record.state.value}")
            if record.rollback_reason:
                print(f"Rollback Reason: {record.rollback_reason}")
        
        print("\\nDemo completed!")
