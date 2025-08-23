"""
Lokale Container-Orchestrierung.

Erzeugt eine lokale Orchestrierung, die mehrere Dienste des generierten 
Programms gemeinsam startet, Health aller Instanzen prüft und einen 
konsistenten Stopp durchführt.
"""

from __future__ import annotations

import asyncio
import json
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import logging

from .deploy_profiles import DeployProfile, DeploymentTarget
from .e2e_test_harness import HealthChecker
from .container_builder import ContainerImage


logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service-Status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    FAILED = "failed"


class OrchestrationMode(Enum):
    """Orchestrierungs-Modi."""
    SEQUENTIAL = "sequential"  # Services nacheinander starten
    PARALLEL = "parallel"     # Services parallel starten
    DEPENDENCY = "dependency" # Abhängigkeiten-basiert


@dataclass
class ServiceInstance:
    """Service-Instanz."""
    
    # Service-Identifikation
    name: str
    instance_id: str
    container_name: str
    
    # Konfiguration
    profile: DeployProfile
    container_image: ContainerImage
    
    # Runtime-Status
    status: ServiceStatus = ServiceStatus.STOPPED
    container_id: Optional[str] = None
    pid: Optional[int] = None
    
    # Health-Status
    last_health_check: Optional[str] = None
    health_check_failures: int = 0
    
    # Ports und Netzwerk
    assigned_ports: Dict[str, int] = field(default_factory=dict)
    
    # Logs
    log_file: Optional[Path] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["status"] = self.status.value
        result["profile"] = self.profile.name
        result["container_image"] = f"{self.container_image.name}:{self.container_image.tag}"
        return result


@dataclass
class OrchestrationPlan:
    """Orchestrierungs-Plan."""
    
    # Plan-Metadaten
    name: str
    description: str
    
    # Services
    services: List[ServiceInstance]
    
    # Orchestrierungs-Konfiguration
    mode: OrchestrationMode = OrchestrationMode.PARALLEL
    startup_timeout_seconds: int = 120
    health_check_interval_seconds: int = 10
    
    # Abhängigkeiten (service_name -> [dependencies])
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    
    # Globale Konfiguration
    log_directory: Path = Path("./orchestration_logs")
    enable_service_discovery: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        result = asdict(self)
        result["mode"] = self.mode.value
        result["services"] = [service.to_dict() for service in self.services]
        result["log_directory"] = str(self.log_directory)
        return result


class PortManager:
    """Port-Manager für Service-Isolation."""
    
    def __init__(self, port_range_start: int = 8000, port_range_end: int = 9000):
        self.port_range_start = port_range_start
        self.port_range_end = port_range_end
        self.allocated_ports: Set[int] = set()
        self.service_ports: Dict[str, Dict[str, int]] = {}
    
    def allocate_ports_for_service(
        self,
        service_name: str,
        required_ports: List[str]
    ) -> Dict[str, int]:
        """Allokiere Ports für Service."""
        allocated = {}
        
        for port_name in required_ports:
            port = self._find_free_port()
            if port:
                allocated[port_name] = port
                self.allocated_ports.add(port)
            else:
                raise RuntimeError(f"No free ports available for {service_name}")
        
        self.service_ports[service_name] = allocated
        logger.info(f"Allocated ports for {service_name}: {allocated}")
        return allocated
    
    def _find_free_port(self) -> Optional[int]:
        """Finde freien Port."""
        import socket
        
        for port in range(self.port_range_start, self.port_range_end):
            if port in self.allocated_ports:
                continue
            
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                continue
        
        return None
    
    def release_ports_for_service(self, service_name: str):
        """Gebe Ports für Service frei."""
        if service_name in self.service_ports:
            for port in self.service_ports[service_name].values():
                self.allocated_ports.discard(port)
            del self.service_ports[service_name]
            logger.info(f"Released ports for {service_name}")


class ServiceManager:
    """Manager für einzelne Services."""
    
    def __init__(self, port_manager: PortManager):
        self.port_manager = port_manager
        self.health_checker = HealthChecker()
    
    def start_service(self, service: ServiceInstance) -> bool:
        """Starte Service."""
        logger.info(f"Starting service: {service.name}")
        service.status = ServiceStatus.STARTING
        
        try:
            # Allokiere Ports
            required_ports = [port.name for port in service.profile.ports]
            if required_ports:
                service.assigned_ports = self.port_manager.allocate_ports_for_service(
                    service.name, required_ports
                )
            
            # Erstelle Log-Datei
            if service.profile.logging:
                log_dir = Path("orchestration_logs") / service.name
                log_dir.mkdir(parents=True, exist_ok=True)
                service.log_file = log_dir / f"{service.instance_id}.log"
            
            # Starte Container (simuliert)
            container_id = self._start_container(service)
            service.container_id = container_id
            service.status = ServiceStatus.RUNNING
            
            logger.info(f"Service {service.name} started with container ID: {container_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service {service.name}: {e}")
            service.status = ServiceStatus.FAILED
            return False
    
    def _start_container(self, service: ServiceInstance) -> str:
        """Starte Container (simuliert)."""
        # Simuliere Docker-Container-Start
        # In Produktion: docker run -d --name {service.container_name} ...
        
        container_id = f"mock_container_{service.name}_{int(time.time())}"
        
        # Simuliere Container-Prozess
        service.pid = 12345  # Mock-PID
        
        return container_id
    
    def stop_service(self, service: ServiceInstance) -> bool:
        """Stoppe Service."""
        logger.info(f"Stopping service: {service.name}")
        service.status = ServiceStatus.STOPPING
        
        try:
            if service.container_id:
                # Simuliere Container-Stop
                # In Produktion: docker stop {service.container_id}
                logger.debug(f"Stopping container: {service.container_id}")
            
            # Gebe Ports frei
            self.port_manager.release_ports_for_service(service.name)
            
            service.status = ServiceStatus.STOPPED
            service.container_id = None
            service.pid = None
            
            logger.info(f"Service {service.name} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service {service.name}: {e}")
            return False
    
    def check_service_health(self, service: ServiceInstance) -> bool:
        """Prüfe Service-Health."""
        if service.status != ServiceStatus.RUNNING:
            return False
        
        try:
            # Verwende Health-Probe aus Profil
            if service.profile.liveness_probe:
                probe = service.profile.liveness_probe
                
                # Hole zugewiesenen Port
                port = None
                if probe.http_port and service.assigned_ports:
                    # Finde Port-Mapping
                    for port_name, assigned_port in service.assigned_ports.items():
                        if port_name == "http":  # Standard HTTP-Port
                            port = assigned_port
                            break
                
                if not port:
                    port = probe.http_port or 8000
                
                # Führe Health-Check durch
                if probe.probe_type.value == "http":
                    health_ok = self.health_checker.wait_for_health(
                        "localhost", port, probe.http_path, timeout_seconds=5
                    )
                else:
                    # Für andere Probe-Typen: Simuliere
                    health_ok = True
                
                if health_ok:
                    service.status = ServiceStatus.HEALTHY
                    service.health_check_failures = 0
                    service.last_health_check = datetime.utcnow().isoformat()
                    return True
                else:
                    service.health_check_failures += 1
                    if service.health_check_failures >= 3:
                        service.status = ServiceStatus.UNHEALTHY
                    return False
            else:
                # Kein Health-Check definiert - assume healthy
                service.status = ServiceStatus.HEALTHY
                return True
                
        except Exception as e:
            logger.error(f"Health check failed for {service.name}: {e}")
            service.health_check_failures += 1
            if service.health_check_failures >= 3:
                service.status = ServiceStatus.UNHEALTHY
            return False
    
    def get_service_logs(self, service: ServiceInstance, lines: int = 50) -> str:
        """Hole Service-Logs."""
        if service.log_file and service.log_file.exists():
            try:
                content = service.log_file.read_text()
                log_lines = content.split('\\n')[-lines:]
                return '\\n'.join(log_lines)
            except Exception as e:
                logger.error(f"Failed to read logs for {service.name}: {e}")
        
        # Fallback: Mock-Logs
        return f"""
{datetime.utcnow().isoformat()} INFO Starting {service.name}
{datetime.utcnow().isoformat()} INFO Service {service.name} is running
{datetime.utcnow().isoformat()} INFO Health check passed
{datetime.utcnow().isoformat()} INFO Service {service.name} ready
"""


class LocalOrchestrator:
    """Lokaler Container-Orchestrator."""
    
    def __init__(self):
        self.port_manager = PortManager()
        self.service_manager = ServiceManager(self.port_manager)
        self.current_plan: Optional[OrchestrationPlan] = None
        self.running = False
        self._shutdown_handlers_registered = False
    
    def create_orchestration_plan(
        self,
        services: List[ServiceInstance],
        mode: OrchestrationMode = OrchestrationMode.PARALLEL
    ) -> OrchestrationPlan:
        """Erstelle Orchestrierungs-Plan."""
        plan = OrchestrationPlan(
            name=f"local-orchestration-{int(time.time())}",
            description=f"Local orchestration of {len(services)} services",
            services=services,
            mode=mode
        )
        
        logger.info(f"Created orchestration plan: {plan.name}")
        return plan
    
    def start_orchestration(self, plan: OrchestrationPlan) -> bool:
        """Starte Orchestrierung."""
        logger.info(f"Starting orchestration: {plan.name}")
        
        self.current_plan = plan
        self.running = True
        
        # Registriere Shutdown-Handler
        if not self._shutdown_handlers_registered:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            self._shutdown_handlers_registered = True
        
        # Erstelle Log-Verzeichnis
        plan.log_directory.mkdir(parents=True, exist_ok=True)
        
        try:
            if plan.mode == OrchestrationMode.SEQUENTIAL:
                success = self._start_services_sequential(plan)
            elif plan.mode == OrchestrationMode.PARALLEL:
                success = self._start_services_parallel(plan)
            else:
                success = self._start_services_with_dependencies(plan)
            
            if success:
                # Starte Health-Check-Loop
                self._start_health_monitoring(plan)
                logger.info("Orchestration started successfully")
            else:
                logger.error("Orchestration startup failed")
                self.stop_orchestration()
            
            return success
            
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            self.stop_orchestration()
            return False
    
    def _start_services_sequential(self, plan: OrchestrationPlan) -> bool:
        """Starte Services sequenziell."""
        logger.info("Starting services sequentially")
        
        for service in plan.services:
            if not self.service_manager.start_service(service):
                logger.error(f"Failed to start service {service.name}")
                return False
            
            # Warte auf Health-Check
            if not self._wait_for_service_health(service, plan.startup_timeout_seconds):
                logger.error(f"Service {service.name} failed health check")
                return False
        
        return True
    
    def _start_services_parallel(self, plan: OrchestrationPlan) -> bool:
        """Starte Services parallel."""
        logger.info("Starting services in parallel")
        
        # Starte alle Services
        start_results = []
        for service in plan.services:
            success = self.service_manager.start_service(service)
            start_results.append((service, success))
        
        # Prüfe Start-Ergebnisse
        failed_services = [s for s, success in start_results if not success]
        if failed_services:
            logger.error(f"Failed to start services: {[s.name for s in failed_services]}")
            return False
        
        # Warte auf Health-Checks aller Services
        for service in plan.services:
            if not self._wait_for_service_health(service, plan.startup_timeout_seconds):
                logger.error(f"Service {service.name} failed health check")
                return False
        
        return True
    
    def _start_services_with_dependencies(self, plan: OrchestrationPlan) -> bool:
        """Starte Services basierend auf Abhängigkeiten."""
        logger.info("Starting services with dependency resolution")
        
        started_services = set()
        remaining_services = {s.name: s for s in plan.services}
        
        while remaining_services:
            # Finde Services ohne unerfüllte Abhängigkeiten
            ready_services = []
            for service_name, service in remaining_services.items():
                dependencies = plan.dependencies.get(service_name, [])
                if all(dep in started_services for dep in dependencies):
                    ready_services.append(service)
            
            if not ready_services:
                logger.error("Circular dependency detected or unresolvable dependencies")
                return False
            
            # Starte bereite Services
            for service in ready_services:
                if self.service_manager.start_service(service):
                    if self._wait_for_service_health(service, plan.startup_timeout_seconds):
                        started_services.add(service.name)
                        del remaining_services[service.name]
                    else:
                        logger.error(f"Service {service.name} failed health check")
                        return False
                else:
                    logger.error(f"Failed to start service {service.name}")
                    return False
        
        return True
    
    def _wait_for_service_health(self, service: ServiceInstance, timeout_seconds: int) -> bool:
        """Warte auf Service-Health."""
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            if self.service_manager.check_service_health(service):
                return True
            time.sleep(2)
        
        return False
    
    def _start_health_monitoring(self, plan: OrchestrationPlan):
        """Starte Health-Monitoring."""
        def monitor_health():
            while self.running:
                for service in plan.services:
                    if service.status in [ServiceStatus.RUNNING, ServiceStatus.HEALTHY]:
                        self.service_manager.check_service_health(service)
                
                time.sleep(plan.health_check_interval_seconds)
        
        import threading
        monitor_thread = threading.Thread(target=monitor_health, daemon=True)
        monitor_thread.start()
        logger.info("Health monitoring started")
    
    def stop_orchestration(self) -> bool:
        """Stoppe Orchestrierung."""
        if not self.current_plan:
            return True
        
        logger.info("Stopping orchestration")
        self.running = False
        
        # Stoppe Services in umgekehrter Reihenfolge
        services_to_stop = list(reversed(self.current_plan.services))
        
        stop_results = []
        for service in services_to_stop:
            if service.status != ServiceStatus.STOPPED:
                success = self.service_manager.stop_service(service)
                stop_results.append((service, success))
        
        # Prüfe Stop-Ergebnisse
        failed_stops = [s for s, success in stop_results if not success]
        if failed_stops:
            logger.warning(f"Failed to cleanly stop services: {[s.name for s in failed_stops]}")
        
        # Cleanup
        self.port_manager = PortManager()
        self.current_plan = None
        
        logger.info("Orchestration stopped")
        return len(failed_stops) == 0
    
    def get_orchestration_status(self) -> Dict[str, Any]:
        """Hole Orchestrierungs-Status."""
        if not self.current_plan:
            return {"status": "not_running", "services": []}
        
        services_status = []
        for service in self.current_plan.services:
            services_status.append({
                "name": service.name,
                "status": service.status.value,
                "container_id": service.container_id,
                "assigned_ports": service.assigned_ports,
                "health_check_failures": service.health_check_failures,
                "last_health_check": service.last_health_check
            })
        
        overall_status = "healthy"
        if any(s.status == ServiceStatus.FAILED for s in self.current_plan.services):
            overall_status = "failed"
        elif any(s.status == ServiceStatus.UNHEALTHY for s in self.current_plan.services):
            overall_status = "unhealthy"
        elif any(s.status in [ServiceStatus.STARTING, ServiceStatus.STOPPING] for s in self.current_plan.services):
            overall_status = "transitioning"
        
        return {
            "status": overall_status,
            "plan_name": self.current_plan.name,
            "services": services_status,
            "total_services": len(self.current_plan.services),
            "healthy_services": len([s for s in self.current_plan.services if s.status == ServiceStatus.HEALTHY])
        }
    
    def _signal_handler(self, signum, frame):
        """Signal-Handler für graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop_orchestration()
        sys.exit(0)
    
    def wait_for_shutdown(self):
        """Warte auf Shutdown-Signal."""
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.stop_orchestration()


# Convenience Functions
def create_multi_instance_orchestration(
    service_name: str,
    profile: DeployProfile,
    container_image: ContainerImage,
    instance_count: int = 3
) -> OrchestrationPlan:
    """
    Erstelle Multi-Instanz-Orchestrierung.
    
    Args:
        service_name: Service-Name
        profile: Deploy-Profil
        container_image: Container-Image
        instance_count: Anzahl Instanzen
        
    Returns:
        Orchestrierungs-Plan
    """
    services = []
    
    for i in range(instance_count):
        instance = ServiceInstance(
            name=f"{service_name}-{i+1}",
            instance_id=f"{service_name}-instance-{i+1}",
            container_name=f"{service_name}-container-{i+1}",
            profile=profile,
            container_image=container_image
        )
        services.append(instance)
    
    orchestrator = LocalOrchestrator()
    return orchestrator.create_orchestration_plan(services, OrchestrationMode.PARALLEL)


if __name__ == "__main__":
    # Demo
    import tempfile
    from .template_catalog import get_catalog
    from .deploy_profiles import DeployProfileFactory
    from .container_builder import ContainerImage
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🎭 Local Orchestrator Demo:")
        
        # Erstelle Mock-Services
        container_image = ContainerImage(
            name="demo/api",
            tag="1.0.0",
            image_id="mock_id",
            size_bytes=100_000_000,
            created_at="2024-01-20T10:00:00Z",
            source_artifact="demo.whl",
            build_platform="linux/amd64",
            policy_compliant=True
        )
        
        profile = DeployProfileFactory.create_local_profile("demo-api", template)
        
        # Erstelle Orchestrierungs-Plan
        plan = create_multi_instance_orchestration(
            "demo-api", profile, container_image, instance_count=2
        )
        
        print(f"\\nOrchestration Plan: {plan.name}")
        print(f"Services: {len(plan.services)}")
        print(f"Mode: {plan.mode.value}")
        
        # Starte Orchestrierung (simuliert)
        orchestrator = LocalOrchestrator()
        
        print("\\nStarting orchestration...")
        success = orchestrator.start_orchestration(plan)
        
        print(f"Startup Success: {success}")
        
        if success:
            # Hole Status
            status = orchestrator.get_orchestration_status()
            print(f"\\nOrchestration Status: {status['status']}")
            print(f"Healthy Services: {status['healthy_services']}/{status['total_services']}")
            
            print("\\nService Details:")
            for service_status in status['services']:
                print(f"  - {service_status['name']}: {service_status['status']}")
                if service_status['assigned_ports']:
                    print(f"    Ports: {service_status['assigned_ports']}")
            
            # Stoppe Orchestrierung
            print("\\nStopping orchestration...")
            stop_success = orchestrator.stop_orchestration()
            print(f"Stop Success: {stop_success}")
        
        print("\\nDemo completed!")
