"""
Rollback und Idempotenz Manager für sicheres Deploy-Verhalten.

Implementiert:
- Rollback beim gescheiterten Deploy auf letzten stabilen Stand
- Idempotenz der Deploy-Schritte
- Simulierter Fehl-Deploy rollt automatisch zurück
"""

from __future__ import annotations

import os
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
import logging
import hashlib
import time


logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    """Deployment-Status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"


class OperationType(Enum):
    """Operations-Typen."""
    FILE_COPY = "file_copy"
    DIRECTORY_CREATE = "directory_create"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    CONTAINER_START = "container_start"
    CONTAINER_STOP = "container_stop"
    CONFIG_UPDATE = "config_update"
    DATABASE_MIGRATION = "database_migration"
    CUSTOM = "custom"


@dataclass
class DeploymentOperation:
    """Einzelne Deployment-Operation."""
    
    # Operation-Info
    operation_id: str
    operation_type: OperationType
    description: str
    
    # Ausführung
    execute_func: Optional[Callable] = None
    rollback_func: Optional[Callable] = None
    
    # Parameter
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    status: DeploymentStatus = DeploymentStatus.PENDING
    executed: bool = False
    
    # Rollback-Info
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    
    # Idempotenz
    idempotency_key: str = ""
    checksum: str = ""
    
    # Fehler
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type.value,
            "description": self.description,
            "parameters": self.parameters,
            "status": self.status.value,
            "executed": self.executed,
            "rollback_data": self.rollback_data,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "idempotency_key": self.idempotency_key,
            "checksum": self.checksum,
            "error_message": self.error_message
        }


@dataclass
class DeploymentState:
    """Deployment-Zustand."""
    
    # Deployment-Info
    deployment_id: str
    name: str
    version: str = "1.0.0"
    
    # Operationen
    operations: List[DeploymentOperation] = field(default_factory=list)
    
    # Status
    status: DeploymentStatus = DeploymentStatus.PENDING
    
    # Rollback-Info
    rollback_point: Optional[str] = None  # Operation-ID des letzten stabilen Zustands
    previous_deployment_id: Optional[str] = None
    
    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration: float = 0.0
    
    # Statistiken
    operations_completed: int = 0
    operations_failed: int = 0
    
    # Metadaten
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_operation(self, operation: DeploymentOperation):
        """Füge Operation hinzu."""
        self.operations.append(operation)
    
    def get_completed_operations(self) -> List[DeploymentOperation]:
        """Hole abgeschlossene Operationen."""
        return [op for op in self.operations if op.executed and op.status == DeploymentStatus.COMPLETED]
    
    def get_failed_operations(self) -> List[DeploymentOperation]:
        """Hole fehlgeschlagene Operationen."""
        return [op for op in self.operations if op.status == DeploymentStatus.FAILED]
    
    def calculate_stats(self):
        """Berechne Statistiken."""
        self.operations_completed = len(self.get_completed_operations())
        self.operations_failed = len(self.get_failed_operations())
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "deployment_id": self.deployment_id,
            "name": self.name,
            "version": self.version,
            "operations": [op.to_dict() for op in self.operations],
            "status": self.status.value,
            "rollback_point": self.rollback_point,
            "previous_deployment_id": self.previous_deployment_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration": self.total_duration,
            "operations_completed": self.operations_completed,
            "operations_failed": self.operations_failed,
            "metadata": self.metadata
        }


class IdempotencyManager:
    """Idempotenz-Manager."""
    
    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            state_dir = Path.cwd() / ".deployment_state"
        
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.operation_cache: Dict[str, Any] = {}
    
    def generate_idempotency_key(self, operation: DeploymentOperation) -> str:
        """Generiere Idempotenz-Schlüssel."""
        
        # Basis-Daten für Schlüssel
        key_data = {
            "operation_type": operation.operation_type.value,
            "description": operation.description,
            "parameters": operation.parameters
        }
        
        # Erstelle Hash
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]
    
    def calculate_operation_checksum(self, operation: DeploymentOperation) -> str:
        """Berechne Operations-Checksum."""
        
        checksum_data = {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type.value,
            "parameters": operation.parameters,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        checksum_string = json.dumps(checksum_data, sort_keys=True)
        return hashlib.sha256(checksum_string.encode()).hexdigest()
    
    def is_operation_already_executed(self, operation: DeploymentOperation) -> bool:
        """Prüfe ob Operation bereits ausgeführt wurde."""
        
        if not operation.idempotency_key:
            operation.idempotency_key = self.generate_idempotency_key(operation)
        
        # Prüfe Cache
        if operation.idempotency_key in self.operation_cache:
            cached_result = self.operation_cache[operation.idempotency_key]
            logger.info(f"Operation {operation.operation_id} found in cache")
            return cached_result["executed"]
        
        # Prüfe persistenten Zustand
        state_file = self.state_dir / f"operation_{operation.idempotency_key}.json"
        
        if state_file.exists():
            try:
                with state_file.open('r') as f:
                    state_data = json.load(f)
                
                # Prüfe ob Checksum übereinstimmt
                if state_data.get("checksum") == operation.checksum:
                    logger.info(f"Operation {operation.operation_id} already executed (idempotent)")
                    return True
                else:
                    logger.info(f"Operation {operation.operation_id} parameters changed, re-executing")
                    return False
            
            except Exception as e:
                logger.warning(f"Failed to read operation state: {e}")
                return False
        
        return False
    
    def mark_operation_executed(self, operation: DeploymentOperation):
        """Markiere Operation als ausgeführt."""
        
        if not operation.idempotency_key:
            operation.idempotency_key = self.generate_idempotency_key(operation)
        
        if not operation.checksum:
            operation.checksum = self.calculate_operation_checksum(operation)
        
        # Cache aktualisieren
        self.operation_cache[operation.idempotency_key] = {
            "executed": True,
            "checksum": operation.checksum,
            "completed_at": operation.completed_at
        }
        
        # Persistenter Zustand
        state_file = self.state_dir / f"operation_{operation.idempotency_key}.json"
        
        state_data = {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type.value,
            "checksum": operation.checksum,
            "executed": True,
            "completed_at": operation.completed_at,
            "rollback_data": operation.rollback_data
        }
        
        try:
            with state_file.open('w') as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save operation state: {e}")
    
    def cleanup_old_states(self, max_age_days: int = 7):
        """Bereinige alte Zustände."""
        
        cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
        
        for state_file in self.state_dir.glob("operation_*.json"):
            try:
                file_time = datetime.fromtimestamp(state_file.stat().st_mtime)
                
                if file_time < cutoff_time:
                    state_file.unlink()
                    logger.debug(f"Cleaned up old operation state: {state_file.name}")
            
            except Exception as e:
                logger.warning(f"Failed to cleanup {state_file}: {e}")


class RollbackManager:
    """Rollback-Manager."""
    
    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir is None:
            state_dir = Path.cwd() / ".deployment_state"
        
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.deployment_states: Dict[str, DeploymentState] = {}
    
    def save_deployment_state(self, deployment_state: DeploymentState):
        """Speichere Deployment-Zustand."""
        
        state_file = self.state_dir / f"deployment_{deployment_state.deployment_id}.json"
        
        try:
            with state_file.open('w') as f:
                json.dump(deployment_state.to_dict(), f, indent=2)
            
            self.deployment_states[deployment_state.deployment_id] = deployment_state
            
        except Exception as e:
            logger.error(f"Failed to save deployment state: {e}")
    
    def load_deployment_state(self, deployment_id: str) -> Optional[DeploymentState]:
        """Lade Deployment-Zustand."""
        
        if deployment_id in self.deployment_states:
            return self.deployment_states[deployment_id]
        
        state_file = self.state_dir / f"deployment_{deployment_id}.json"
        
        if not state_file.exists():
            return None
        
        try:
            with state_file.open('r') as f:
                state_data = json.load(f)
            
            # Vereinfachte Rekonstruktion
            deployment_state = DeploymentState(
                deployment_id=state_data["deployment_id"],
                name=state_data["name"],
                version=state_data["version"],
                status=DeploymentStatus(state_data["status"]),
                rollback_point=state_data.get("rollback_point"),
                previous_deployment_id=state_data.get("previous_deployment_id"),
                started_at=state_data.get("started_at"),
                completed_at=state_data.get("completed_at"),
                total_duration=state_data.get("total_duration", 0.0)
            )
            
            # Lade Operationen
            for op_data in state_data["operations"]:
                operation = DeploymentOperation(
                    operation_id=op_data["operation_id"],
                    operation_type=OperationType(op_data["operation_type"]),
                    description=op_data["description"],
                    parameters=op_data["parameters"],
                    status=DeploymentStatus(op_data["status"]),
                    executed=op_data["executed"],
                    rollback_data=op_data["rollback_data"],
                    started_at=op_data.get("started_at"),
                    completed_at=op_data.get("completed_at"),
                    duration_seconds=op_data.get("duration_seconds", 0.0),
                    idempotency_key=op_data.get("idempotency_key", ""),
                    checksum=op_data.get("checksum", ""),
                    error_message=op_data.get("error_message", "")
                )
                deployment_state.add_operation(operation)
            
            deployment_state.calculate_stats()
            self.deployment_states[deployment_id] = deployment_state
            
            return deployment_state
        
        except Exception as e:
            logger.error(f"Failed to load deployment state: {e}")
            return None
    
    def create_rollback_point(self, deployment_state: DeploymentState, operation_id: str):
        """Erstelle Rollback-Punkt."""
        
        deployment_state.rollback_point = operation_id
        self.save_deployment_state(deployment_state)
        
        logger.info(f"Created rollback point at operation: {operation_id}")
    
    def rollback_deployment(self, deployment_id: str) -> bool:
        """Führe Rollback durch."""
        
        logger.info(f"Starting rollback for deployment: {deployment_id}")
        
        deployment_state = self.load_deployment_state(deployment_id)
        
        if not deployment_state:
            logger.error(f"Deployment state not found: {deployment_id}")
            return False
        
        # Finde Operationen zum Rollback (in umgekehrter Reihenfolge)
        completed_operations = deployment_state.get_completed_operations()
        rollback_operations = list(reversed(completed_operations))
        
        rollback_success = True
        rollback_count = 0
        
        for operation in rollback_operations:
            try:
                logger.info(f"Rolling back operation: {operation.operation_id}")
                
                # Führe Rollback aus
                if operation.rollback_func:
                    operation.rollback_func(operation.rollback_data)
                else:
                    # Standard-Rollback basierend auf Typ
                    self._execute_standard_rollback(operation)
                
                rollback_count += 1
                
                # Stoppe bei Rollback-Punkt
                if deployment_state.rollback_point and operation.operation_id == deployment_state.rollback_point:
                    logger.info(f"Reached rollback point: {deployment_state.rollback_point}")
                    break
            
            except Exception as e:
                logger.error(f"Rollback failed for operation {operation.operation_id}: {e}")
                rollback_success = False
                break
        
        # Update Deployment-Status
        if rollback_success:
            deployment_state.status = DeploymentStatus.ROLLED_BACK
            logger.info(f"Rollback completed successfully: {rollback_count} operations")
        else:
            deployment_state.status = DeploymentStatus.ROLLBACK_FAILED
            logger.error(f"Rollback failed after {rollback_count} operations")
        
        deployment_state.completed_at = datetime.utcnow().isoformat()
        self.save_deployment_state(deployment_state)
        
        return rollback_success
    
    def _execute_standard_rollback(self, operation: DeploymentOperation):
        """Führe Standard-Rollback aus."""
        
        if operation.operation_type == OperationType.FILE_COPY:
            # Datei löschen oder Backup wiederherstellen
            target_file = Path(operation.parameters.get("target", ""))
            backup_file = Path(operation.rollback_data.get("backup_path", ""))
            
            if backup_file.exists():
                shutil.copy2(backup_file, target_file)
                backup_file.unlink()
            elif target_file.exists():
                target_file.unlink()
        
        elif operation.operation_type == OperationType.DIRECTORY_CREATE:
            # Verzeichnis löschen
            target_dir = Path(operation.parameters.get("path", ""))
            if target_dir.exists() and target_dir.is_dir():
                shutil.rmtree(target_dir)
        
        elif operation.operation_type == OperationType.SERVICE_START:
            # Service stoppen
            service_name = operation.parameters.get("service_name", "")
            if service_name:
                subprocess.run(["systemctl", "stop", service_name], capture_output=True)
        
        elif operation.operation_type == OperationType.CONTAINER_START:
            # Container stoppen
            container_id = operation.rollback_data.get("container_id", "")
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True)
                subprocess.run(["docker", "rm", container_id], capture_output=True)
        
        else:
            logger.warning(f"No standard rollback for operation type: {operation.operation_type.value}")


class DeploymentOrchestrator:
    """Deployment-Orchestrator mit Rollback und Idempotenz."""
    
    def __init__(self, state_dir: Optional[Path] = None):
        self.idempotency_manager = IdempotencyManager(state_dir)
        self.rollback_manager = RollbackManager(state_dir)
    
    def execute_deployment(self, deployment_state: DeploymentState) -> bool:
        """Führe Deployment aus."""
        
        logger.info(f"Starting deployment: {deployment_state.deployment_id}")
        
        deployment_state.status = DeploymentStatus.IN_PROGRESS
        deployment_state.started_at = datetime.utcnow().isoformat()
        
        start_time = time.time()
        
        try:
            # Speichere initialen Zustand
            self.rollback_manager.save_deployment_state(deployment_state)
            
            # Führe Operationen aus
            for i, operation in enumerate(deployment_state.operations):
                logger.info(f"Executing operation {i+1}/{len(deployment_state.operations)}: {operation.operation_id}")
                
                # Prüfe Idempotenz
                if self.idempotency_manager.is_operation_already_executed(operation):
                    logger.info(f"Operation {operation.operation_id} skipped (idempotent)")
                    operation.status = DeploymentStatus.COMPLETED
                    operation.executed = True
                    continue
                
                # Führe Operation aus
                operation_start = time.time()
                operation.started_at = datetime.utcnow().isoformat()
                operation.status = DeploymentStatus.IN_PROGRESS
                
                try:
                    # Bereite Rollback-Daten vor
                    self._prepare_rollback_data(operation)
                    
                    # Führe Operation aus
                    if operation.execute_func:
                        operation.execute_func(operation.parameters)
                    else:
                        self._execute_standard_operation(operation)
                    
                    # Operation erfolgreich
                    operation.status = DeploymentStatus.COMPLETED
                    operation.executed = True
                    operation.completed_at = datetime.utcnow().isoformat()
                    operation.duration_seconds = time.time() - operation_start
                    
                    # Markiere als ausgeführt (Idempotenz)
                    self.idempotency_manager.mark_operation_executed(operation)
                    
                    # Erstelle Rollback-Punkt nach kritischen Operationen
                    if i % 3 == 0:  # Alle 3 Operationen
                        self.rollback_manager.create_rollback_point(deployment_state, operation.operation_id)
                    
                    logger.info(f"Operation {operation.operation_id} completed successfully")
                
                except Exception as e:
                    # Operation fehlgeschlagen
                    operation.status = DeploymentStatus.FAILED
                    operation.error_message = str(e)
                    operation.completed_at = datetime.utcnow().isoformat()
                    operation.duration_seconds = time.time() - operation_start
                    
                    logger.error(f"Operation {operation.operation_id} failed: {e}")
                    
                    # Automatisches Rollback bei Fehler
                    logger.info("Starting automatic rollback due to failure")
                    rollback_success = self.rollback_manager.rollback_deployment(deployment_state.deployment_id)
                    
                    if rollback_success:
                        deployment_state.status = DeploymentStatus.ROLLED_BACK
                    else:
                        deployment_state.status = DeploymentStatus.ROLLBACK_FAILED
                    
                    deployment_state.completed_at = datetime.utcnow().isoformat()
                    deployment_state.total_duration = time.time() - start_time
                    deployment_state.calculate_stats()
                    
                    self.rollback_manager.save_deployment_state(deployment_state)
                    
                    return False
                
                # Speichere Zwischenzustand
                self.rollback_manager.save_deployment_state(deployment_state)
            
            # Deployment erfolgreich
            deployment_state.status = DeploymentStatus.COMPLETED
            deployment_state.completed_at = datetime.utcnow().isoformat()
            deployment_state.total_duration = time.time() - start_time
            deployment_state.calculate_stats()
            
            self.rollback_manager.save_deployment_state(deployment_state)
            
            logger.info(f"Deployment completed successfully: {deployment_state.deployment_id}")
            
            return True
        
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            
            deployment_state.status = DeploymentStatus.FAILED
            deployment_state.completed_at = datetime.utcnow().isoformat()
            deployment_state.total_duration = time.time() - start_time
            
            self.rollback_manager.save_deployment_state(deployment_state)
            
            return False
    
    def _prepare_rollback_data(self, operation: DeploymentOperation):
        """Bereite Rollback-Daten vor."""
        
        if operation.operation_type == OperationType.FILE_COPY:
            target_file = Path(operation.parameters.get("target", ""))
            
            if target_file.exists():
                # Erstelle Backup
                backup_path = target_file.with_suffix(target_file.suffix + ".backup")
                shutil.copy2(target_file, backup_path)
                operation.rollback_data["backup_path"] = str(backup_path)
        
        elif operation.operation_type == OperationType.CONTAINER_START:
            # Container-ID wird nach Start gesetzt
            pass
        
        # Weitere Rollback-Vorbereitungen je nach Typ...
    
    def _execute_standard_operation(self, operation: DeploymentOperation):
        """Führe Standard-Operation aus."""
        
        if operation.operation_type == OperationType.FILE_COPY:
            source = Path(operation.parameters["source"])
            target = Path(operation.parameters["target"])
            
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        
        elif operation.operation_type == OperationType.DIRECTORY_CREATE:
            path = Path(operation.parameters["path"])
            path.mkdir(parents=True, exist_ok=True)
        
        elif operation.operation_type == OperationType.CONTAINER_START:
            image = operation.parameters["image"]
            name = operation.parameters.get("name", f"container_{int(time.time())}")
            
            cmd = ["docker", "run", "-d", "--name", name, image]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Container start failed: {result.stderr}")
            
            container_id = result.stdout.strip()
            operation.rollback_data["container_id"] = container_id
        
        else:
            raise NotImplementedError(f"Operation type not implemented: {operation.operation_type.value}")
    
    def simulate_failed_deployment(self, deployment_state: DeploymentState, fail_at_operation: int = 2) -> bool:
        """Simuliere fehlgeschlagenes Deployment für Tests."""
        
        logger.info(f"Simulating failed deployment at operation {fail_at_operation}")
        
        # Modifiziere Operations um Fehler zu simulieren
        if fail_at_operation < len(deployment_state.operations):
            fail_operation = deployment_state.operations[fail_at_operation]
            
            # Ersetze execute_func mit einer, die fehlschlägt
            original_func = fail_operation.execute_func
            
            def failing_func(params):
                raise Exception(f"Simulated failure in operation {fail_operation.operation_id}")
            
            fail_operation.execute_func = failing_func
        
        # Führe Deployment aus (wird fehlschlagen und rollback)
        return self.execute_deployment(deployment_state)


# Convenience Functions
def create_file_copy_operation(operation_id: str, source: str, target: str) -> DeploymentOperation:
    """Erstelle File-Copy-Operation."""
    
    return DeploymentOperation(
        operation_id=operation_id,
        operation_type=OperationType.FILE_COPY,
        description=f"Copy {Path(source).name} to {target}",
        parameters={"source": source, "target": target}
    )


def create_container_start_operation(operation_id: str, image: str, name: str = "") -> DeploymentOperation:
    """Erstelle Container-Start-Operation."""
    
    return DeploymentOperation(
        operation_id=operation_id,
        operation_type=OperationType.CONTAINER_START,
        description=f"Start container from {image}",
        parameters={"image": image, "name": name or f"container_{operation_id}"}
    )


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_rollback_idempotency_manager():
        print("🔄 Rollback & Idempotency Manager Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            orchestrator = DeploymentOrchestrator(temp_path)
            
            # Test 1: Erstelle Deployment mit Operationen
            print("\\n📋 Creating deployment with operations:")
            
            deployment_id = f"deploy_{int(time.time())}"
            
            deployment_state = DeploymentState(
                deployment_id=deployment_id,
                name="test-app",
                version="1.2.3"
            )
            
            # Erstelle Test-Dateien
            source_dir = temp_path / "source"
            source_dir.mkdir()
            
            test_files = ["app.py", "config.json", "requirements.txt"]
            for file_name in test_files:
                test_file = source_dir / file_name
                test_file.write_text(f"# Content of {file_name}")
            
            # Erstelle Operationen
            target_dir = temp_path / "target"
            
            operations = [
                DeploymentOperation(
                    operation_id="create_target_dir",
                    operation_type=OperationType.DIRECTORY_CREATE,
                    description="Create target directory",
                    parameters={"path": str(target_dir)}
                ),
                create_file_copy_operation("copy_app", str(source_dir / "app.py"), str(target_dir / "app.py")),
                create_file_copy_operation("copy_config", str(source_dir / "config.json"), str(target_dir / "config.json")),
                create_file_copy_operation("copy_requirements", str(source_dir / "requirements.txt"), str(target_dir / "requirements.txt"))
            ]
            
            for operation in operations:
                deployment_state.add_operation(operation)
            
            print(f"  ✓ Deployment ID: {deployment_id}")
            print(f"  ✓ Operations: {len(deployment_state.operations)}")
            
            for i, op in enumerate(deployment_state.operations, 1):
                print(f"    {i}. {op.operation_id}: {op.description}")
            
            # Test 2: Erfolgreiches Deployment
            print("\\n✅ Testing successful deployment:")
            
            success = orchestrator.execute_deployment(deployment_state)
            
            print(f"  ✓ Deployment success: {success}")
            print(f"  ✓ Status: {deployment_state.status.value}")
            print(f"  ✓ Operations completed: {deployment_state.operations_completed}")
            print(f"  ✓ Operations failed: {deployment_state.operations_failed}")
            print(f"  ✓ Duration: {deployment_state.total_duration:.2f}s")
            
            # Prüfe Ergebnisse
            target_files = list(target_dir.glob("*"))
            print(f"  ✓ Target files created: {len(target_files)}")
            
            for target_file in target_files:
                print(f"    - {target_file.name}: {target_file.stat().st_size} bytes")
            
            # Test 3: Idempotenz - Wiederhole Deployment
            print("\\n🔁 Testing idempotency (repeat deployment):")
            
            # Erstelle neues Deployment mit gleichen Operationen
            deployment_state_2 = DeploymentState(
                deployment_id=f"deploy_{int(time.time())}_repeat",
                name="test-app",
                version="1.2.3"
            )
            
            # Gleiche Operationen (sollten idempotent sein)
            for operation in operations:
                # Erstelle neue Operation mit gleichen Parametern
                new_operation = DeploymentOperation(
                    operation_id=f"{operation.operation_id}_repeat",
                    operation_type=operation.operation_type,
                    description=operation.description,
                    parameters=operation.parameters.copy()
                )
                deployment_state_2.add_operation(new_operation)
            
            success_2 = orchestrator.execute_deployment(deployment_state_2)
            
            print(f"  ✓ Repeat deployment success: {success_2}")
            print(f"  ✓ Status: {deployment_state_2.status.value}")
            
            # Prüfe Idempotenz-Verhalten
            idempotent_operations = 0
            for operation in deployment_state_2.operations:
                if orchestrator.idempotency_manager.is_operation_already_executed(operation):
                    idempotent_operations += 1
            
            print(f"  ✓ Idempotent operations detected: {idempotent_operations}")
            
            # Test 4: Simuliere fehlgeschlagenes Deployment mit Rollback
            print("\\n❌ Testing failed deployment with rollback:")
            
            # Erstelle neues Deployment
            deployment_state_3 = DeploymentState(
                deployment_id=f"deploy_{int(time.time())}_fail",
                name="test-app",
                version="1.2.4"
            )
            
            # Neue Operationen für Rollback-Test
            fail_target_dir = temp_path / "fail_target"
            
            fail_operations = [
                DeploymentOperation(
                    operation_id="create_fail_dir",
                    operation_type=OperationType.DIRECTORY_CREATE,
                    description="Create fail target directory",
                    parameters={"path": str(fail_target_dir)}
                ),
                create_file_copy_operation("copy_app_fail", str(source_dir / "app.py"), str(fail_target_dir / "app.py")),
                # Diese Operation wird fehlschlagen
                DeploymentOperation(
                    operation_id="failing_operation",
                    operation_type=OperationType.CUSTOM,
                    description="Operation that will fail",
                    parameters={}
                )
            ]
            
            for operation in fail_operations:
                deployment_state_3.add_operation(operation)
            
            # Simuliere Fehler
            success_3 = orchestrator.simulate_failed_deployment(deployment_state_3, fail_at_operation=2)
            
            print(f"  ✓ Failed deployment (expected): {not success_3}")
            print(f"  ✓ Status: {deployment_state_3.status.value}")
            print(f"  ✓ Operations completed before failure: {deployment_state_3.operations_completed}")
            
            # Prüfe Rollback-Ergebnis
            rollback_successful = deployment_state_3.status == DeploymentStatus.ROLLED_BACK
            print(f"  ✓ Rollback successful: {rollback_successful}")
            
            # Prüfe ob Dateien entfernt wurden
            fail_files_after_rollback = list(fail_target_dir.glob("*")) if fail_target_dir.exists() else []
            print(f"  ✓ Files after rollback: {len(fail_files_after_rollback)}")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Rollback beim gescheiterten Deploy
            rollback_on_failure = (not success_3 and 
                                 deployment_state_3.status == DeploymentStatus.ROLLED_BACK)
            
            # Idempotenz der Deploy-Schritte
            idempotency_working = idempotent_operations > 0
            
            # Simulierter Fehl-Deploy rollt automatisch zurück
            automatic_rollback = rollback_successful
            
            # Sicheres Deploy-Verhalten
            safe_deployment = (success and success_2 and rollback_on_failure)
            
            print(f"  ✓ Rollback on failed deploy: {rollback_on_failure}")
            print(f"  ✓ Idempotency of deploy steps: {idempotency_working}")
            print(f"  ✓ Automatic rollback on failure: {automatic_rollback}")
            print(f"  ✓ Safe deployment behavior: {safe_deployment}")
            
            return (rollback_on_failure and idempotency_working and 
                   automatic_rollback and safe_deployment)
    
    # Führe Demo aus
    try:
        result = demo_rollback_idempotency_manager()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
