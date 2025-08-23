"""
Self-Healing Checks im Deploy.

Fügt einfache Selbstheilungslogik hinzu: Neustart bei Crashloop, 
Delay-Backoff, Health-Rechecks.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Awaitable
import logging

from .local_orchestrator import ServiceInstance, ServiceStatus


logger = logging.getLogger(__name__)


class HealingAction(Enum):
    """Healing-Aktionen."""
    RESTART = "restart"
    RECREATE = "recreate"
    SCALE_DOWN = "scale_down"
    SCALE_UP = "scale_up"
    WAIT = "wait"
    FAIL = "fail"


class HealthCheckResult(Enum):
    """Health-Check-Ergebnis."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealingPolicy:
    """Healing-Policy."""
    
    # Retry-Konfiguration
    max_restart_attempts: int = 3
    max_recreate_attempts: int = 2
    max_total_attempts: int = 5
    
    # Backoff-Konfiguration
    initial_backoff_seconds: float = 5.0
    max_backoff_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    
    # Health-Check-Konfiguration
    health_check_timeout_seconds: float = 30.0
    health_check_interval_seconds: float = 10.0
    consecutive_failures_threshold: int = 3
    
    # Crashloop-Erkennung
    crashloop_detection_window_minutes: int = 5
    crashloop_restart_threshold: int = 5
    
    # Service-spezifische Einstellungen
    startup_timeout_seconds: float = 120.0
    graceful_shutdown_timeout_seconds: float = 30.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "max_restart_attempts": self.max_restart_attempts,
            "max_recreate_attempts": self.max_recreate_attempts,
            "max_total_attempts": self.max_total_attempts,
            "initial_backoff_seconds": self.initial_backoff_seconds,
            "max_backoff_seconds": self.max_backoff_seconds,
            "backoff_multiplier": self.backoff_multiplier,
            "health_check_timeout_seconds": self.health_check_timeout_seconds,
            "health_check_interval_seconds": self.health_check_interval_seconds,
            "consecutive_failures_threshold": self.consecutive_failures_threshold,
            "crashloop_detection_window_minutes": self.crashloop_detection_window_minutes,
            "crashloop_restart_threshold": self.crashloop_restart_threshold,
            "startup_timeout_seconds": self.startup_timeout_seconds,
            "graceful_shutdown_timeout_seconds": self.graceful_shutdown_timeout_seconds
        }


@dataclass
class HealingAttempt:
    """Healing-Versuch."""
    
    # Versuch-Metadaten
    attempt_number: int
    action: HealingAction
    started_at: str
    
    # Ergebnis
    completed_at: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None
    
    # Backoff
    backoff_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "action": self.action.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "success": self.success,
            "error_message": self.error_message,
            "backoff_seconds": self.backoff_seconds
        }


@dataclass
class ServiceHealthState:
    """Service-Health-Zustand."""
    
    # Service-Identifikation
    service_name: str
    instance_id: str
    
    # Health-Status
    current_health: HealthCheckResult = HealthCheckResult.UNKNOWN
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    
    # Restart-Historie
    restart_history: List[datetime] = field(default_factory=list)
    
    # Healing-Versuche
    healing_attempts: List[HealingAttempt] = field(default_factory=list)
    
    # Zustandsänderungen
    last_health_check: Optional[str] = None
    last_restart: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "current_health": self.current_health.value,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "restart_history": [dt.isoformat() for dt in self.restart_history],
            "healing_attempts": [attempt.to_dict() for attempt in self.healing_attempts],
            "last_health_check": self.last_health_check,
            "last_restart": self.last_restart
        }


class BackoffCalculator:
    """Berechnet Backoff-Zeiten."""
    
    def __init__(self, policy: HealingPolicy):
        self.policy = policy
    
    def calculate_backoff(self, attempt_number: int) -> float:
        """Berechne Backoff-Zeit für Versuch."""
        if attempt_number <= 1:
            return self.policy.initial_backoff_seconds
        
        # Exponential backoff
        backoff = self.policy.initial_backoff_seconds * (
            self.policy.backoff_multiplier ** (attempt_number - 1)
        )
        
        # Cap bei Maximum
        return min(backoff, self.policy.max_backoff_seconds)


class CrashloopDetector:
    """Erkennt Crashloops."""
    
    def __init__(self, policy: HealingPolicy):
        self.policy = policy
    
    def is_crashloop(self, health_state: ServiceHealthState) -> bool:
        """Prüfe ob Service in Crashloop ist."""
        if not health_state.restart_history:
            return False
        
        # Zeitfenster für Crashloop-Erkennung
        window_start = datetime.utcnow() - timedelta(
            minutes=self.policy.crashloop_detection_window_minutes
        )
        
        # Zähle Restarts im Zeitfenster
        recent_restarts = [
            restart_time for restart_time in health_state.restart_history
            if restart_time >= window_start
        ]
        
        return len(recent_restarts) >= self.policy.crashloop_restart_threshold


class ServiceHealthChecker:
    """Service-Health-Checker."""
    
    def __init__(self, policy: HealingPolicy):
        self.policy = policy
    
    async def check_service_health(
        self,
        service: ServiceInstance
    ) -> HealthCheckResult:
        """Prüfe Service-Health."""
        logger.debug(f"Checking health for service: {service.name}")
        
        try:
            # Timeout für Health-Check
            health_check_task = self._perform_health_check(service)
            
            result = await asyncio.wait_for(
                health_check_task,
                timeout=self.policy.health_check_timeout_seconds
            )
            
            logger.debug(f"Health check result for {service.name}: {result.value}")
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Health check timed out for service: {service.name}")
            return HealthCheckResult.UNHEALTHY
        
        except Exception as e:
            logger.error(f"Health check failed for service {service.name}: {e}")
            return HealthCheckResult.UNKNOWN
    
    async def _perform_health_check(self, service: ServiceInstance) -> HealthCheckResult:
        """Führe tatsächlichen Health-Check durch."""
        # Prüfe Container-Status
        if service.status == ServiceStatus.STOPPED:
            return HealthCheckResult.UNHEALTHY
        elif service.status == ServiceStatus.STARTING:
            return HealthCheckResult.DEGRADED
        elif service.status != ServiceStatus.RUNNING:
            return HealthCheckResult.UNKNOWN
        
        # Simuliere HTTP-Health-Check
        if hasattr(service, 'assigned_ports') and service.assigned_ports:
            port = service.assigned_ports.get('http', service.assigned_ports.get('main'))
            if port:
                # In Produktion: echter HTTP-Request
                # Hier: Simulation basierend auf Service-Zustand
                await asyncio.sleep(0.1)  # Simuliere Netzwerk-Delay
                
                # Simuliere gelegentliche Health-Check-Fehler
                import random
                if random.random() < 0.1:  # 10% Chance auf Fehler
                    return HealthCheckResult.UNHEALTHY
                
                return HealthCheckResult.HEALTHY
        
        # Fallback: Service läuft, aber kein Port verfügbar
        return HealthCheckResult.DEGRADED


class ServiceHealer:
    """Service-Heiler."""
    
    def __init__(self, policy: HealingPolicy):
        self.policy = policy
        self.backoff_calculator = BackoffCalculator(policy)
    
    async def heal_service(
        self,
        service: ServiceInstance,
        health_state: ServiceHealthState,
        action: HealingAction
    ) -> bool:
        """Heile Service mit gegebener Aktion."""
        attempt_number = len(health_state.healing_attempts) + 1
        
        # Berechne Backoff
        backoff_seconds = self.backoff_calculator.calculate_backoff(attempt_number)
        
        # Erstelle Healing-Versuch
        attempt = HealingAttempt(
            attempt_number=attempt_number,
            action=action,
            started_at=datetime.utcnow().isoformat(),
            backoff_seconds=backoff_seconds
        )
        
        health_state.healing_attempts.append(attempt)
        
        try:
            # Backoff warten
            if backoff_seconds > 0:
                logger.info(f"Waiting {backoff_seconds}s before healing {service.name}")
                await asyncio.sleep(backoff_seconds)
            
            # Führe Healing-Aktion aus
            logger.info(f"Executing healing action {action.value} for service {service.name}")
            
            success = await self._execute_healing_action(service, action, health_state)
            
            attempt.success = success
            attempt.completed_at = datetime.utcnow().isoformat()
            
            if success:
                logger.info(f"Healing action {action.value} succeeded for {service.name}")
            else:
                logger.warning(f"Healing action {action.value} failed for {service.name}")
            
            return success
            
        except Exception as e:
            attempt.success = False
            attempt.error_message = str(e)
            attempt.completed_at = datetime.utcnow().isoformat()
            
            logger.error(f"Healing action {action.value} failed for {service.name}: {e}")
            return False
    
    async def _execute_healing_action(
        self,
        service: ServiceInstance,
        action: HealingAction,
        health_state: ServiceHealthState
    ) -> bool:
        """Führe spezifische Healing-Aktion aus."""
        if action == HealingAction.RESTART:
            return await self._restart_service(service, health_state)
        elif action == HealingAction.RECREATE:
            return await self._recreate_service(service, health_state)
        elif action == HealingAction.SCALE_DOWN:
            return await self._scale_service(service, scale_down=True)
        elif action == HealingAction.SCALE_UP:
            return await self._scale_service(service, scale_down=False)
        elif action == HealingAction.WAIT:
            await asyncio.sleep(self.policy.health_check_interval_seconds)
            return True
        elif action == HealingAction.FAIL:
            return False
        else:
            logger.error(f"Unknown healing action: {action}")
            return False
    
    async def _restart_service(
        self,
        service: ServiceInstance,
        health_state: ServiceHealthState
    ) -> bool:
        """Starte Service neu."""
        try:
            # Simuliere Service-Neustart
            logger.info(f"Restarting service: {service.name}")
            
            # Graceful shutdown
            service.status = ServiceStatus.STOPPING
            await asyncio.sleep(1.0)  # Simuliere Shutdown-Zeit
            
            # Start service
            service.status = ServiceStatus.STARTING
            await asyncio.sleep(2.0)  # Simuliere Startup-Zeit
            
            # Simuliere gelegentliche Startup-Fehler
            import random
            if random.random() < 0.2:  # 20% Chance auf Startup-Fehler
                service.status = ServiceStatus.STOPPED
                return False
            
            service.status = ServiceStatus.RUNNING
            
            # Aktualisiere Restart-Historie
            health_state.restart_history.append(datetime.utcnow())
            health_state.last_restart = datetime.utcnow().isoformat()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart service {service.name}: {e}")
            service.status = ServiceStatus.STOPPED
            return False
    
    async def _recreate_service(
        self,
        service: ServiceInstance,
        health_state: ServiceHealthState
    ) -> bool:
        """Erstelle Service neu."""
        try:
            logger.info(f"Recreating service: {service.name}")
            
            # Simuliere Service-Recreation
            service.status = ServiceStatus.STOPPING
            await asyncio.sleep(1.0)
            
            service.status = ServiceStatus.CREATING
            await asyncio.sleep(3.0)  # Recreation dauert länger
            
            service.status = ServiceStatus.STARTING
            await asyncio.sleep(2.0)
            
            # Simuliere Recreation-Erfolgsrate
            import random
            if random.random() < 0.1:  # 10% Chance auf Recreation-Fehler
                service.status = ServiceStatus.STOPPED
                return False
            
            service.status = ServiceStatus.RUNNING
            
            # Reset Health-State nach Recreation
            health_state.consecutive_failures = 0
            health_state.consecutive_successes = 0
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to recreate service {service.name}: {e}")
            service.status = ServiceStatus.STOPPED
            return False
    
    async def _scale_service(self, service: ServiceInstance, scale_down: bool) -> bool:
        """Skaliere Service."""
        try:
            action = "down" if scale_down else "up"
            logger.info(f"Scaling service {service.name} {action}")
            
            # Simuliere Scaling
            await asyncio.sleep(1.0)
            
            # Scaling ist immer erfolgreich (Simulation)
            return True
            
        except Exception as e:
            logger.error(f"Failed to scale service {service.name}: {e}")
            return False


class SelfHealingOrchestrator:
    """Self-Healing-Orchestrator."""
    
    def __init__(self, policy: Optional[HealingPolicy] = None):
        self.policy = policy or HealingPolicy()
        
        self.health_checker = ServiceHealthChecker(self.policy)
        self.healer = ServiceHealer(self.policy)
        self.crashloop_detector = CrashloopDetector(self.policy)
        
        # Zustandsspeicher
        self.health_states: Dict[str, ServiceHealthState] = {}
        
        # Healing-Status
        self.healing_active = False
    
    def get_or_create_health_state(self, service: ServiceInstance) -> ServiceHealthState:
        """Hole oder erstelle Health-State für Service."""
        key = f"{service.name}_{service.container_id or 'unknown'}"
        
        if key not in self.health_states:
            self.health_states[key] = ServiceHealthState(
                service_name=service.name,
                instance_id=service.container_id or 'unknown'
            )
        
        return self.health_states[key]
    
    async def monitor_and_heal_service(
        self,
        service: ServiceInstance,
        max_monitoring_duration: float = 300.0
    ) -> Dict[str, Any]:
        """Überwache und heile Service."""
        logger.info(f"Starting self-healing monitoring for service: {service.name}")
        
        health_state = self.get_or_create_health_state(service)
        start_time = time.time()
        
        monitoring_result = {
            "service_name": service.name,
            "monitoring_duration": 0.0,
            "final_health": HealthCheckResult.UNKNOWN.value,
            "healing_attempts": 0,
            "successful_heals": 0,
            "final_status": "unknown"
        }
        
        try:
            self.healing_active = True
            
            while time.time() - start_time < max_monitoring_duration:
                # Health-Check durchführen
                health_result = await self.health_checker.check_service_health(service)
                health_state.current_health = health_result
                health_state.last_health_check = datetime.utcnow().isoformat()
                
                # Health-Statistiken aktualisieren
                if health_result == HealthCheckResult.HEALTHY:
                    health_state.consecutive_successes += 1
                    health_state.consecutive_failures = 0
                else:
                    health_state.consecutive_failures += 1
                    health_state.consecutive_successes = 0
                
                # Prüfe ob Healing notwendig ist
                healing_action = self._determine_healing_action(service, health_state)
                
                if healing_action != HealingAction.WAIT:
                    # Prüfe Healing-Limits
                    if self._should_attempt_healing(health_state):
                        success = await self.healer.heal_service(service, health_state, healing_action)
                        monitoring_result["healing_attempts"] += 1
                        
                        if success:
                            monitoring_result["successful_heals"] += 1
                    else:
                        # Healing-Limits erreicht
                        logger.error(f"Healing limits reached for service {service.name}")
                        monitoring_result["final_status"] = "healing_limits_exceeded"
                        break
                
                # Service ist gesund - Monitoring erfolgreich
                if (health_state.consecutive_successes >= 2 and 
                    health_result == HealthCheckResult.HEALTHY):
                    logger.info(f"Service {service.name} is stable and healthy")
                    monitoring_result["final_status"] = "healthy"
                    break
                
                # Warte vor nächstem Check
                await asyncio.sleep(self.policy.health_check_interval_seconds)
        
        except Exception as e:
            logger.error(f"Self-healing monitoring failed for {service.name}: {e}")
            monitoring_result["final_status"] = "monitoring_error"
        
        finally:
            self.healing_active = False
            monitoring_result["monitoring_duration"] = time.time() - start_time
            monitoring_result["final_health"] = health_state.current_health.value
        
        logger.info(f"Self-healing monitoring completed for {service.name}: {monitoring_result['final_status']}")
        return monitoring_result
    
    def _determine_healing_action(
        self,
        service: ServiceInstance,
        health_state: ServiceHealthState
    ) -> HealingAction:
        """Bestimme notwendige Healing-Aktion."""
        # Service ist gesund - keine Aktion
        if health_state.current_health == HealthCheckResult.HEALTHY:
            return HealingAction.WAIT
        
        # Prüfe Crashloop
        if self.crashloop_detector.is_crashloop(health_state):
            logger.warning(f"Crashloop detected for service {service.name}")
            return HealingAction.RECREATE
        
        # Service ist unhealthy
        if health_state.current_health == HealthCheckResult.UNHEALTHY:
            # Wenige Failures - versuche Restart
            if health_state.consecutive_failures <= 2:
                return HealingAction.RESTART
            # Viele Failures - versuche Recreation
            else:
                return HealingAction.RECREATE
        
        # Service ist degraded - warte zunächst
        if health_state.current_health == HealthCheckResult.DEGRADED:
            if health_state.consecutive_failures >= self.policy.consecutive_failures_threshold:
                return HealingAction.RESTART
            else:
                return HealingAction.WAIT
        
        # Unknown state - warte
        return HealingAction.WAIT
    
    def _should_attempt_healing(self, health_state: ServiceHealthState) -> bool:
        """Prüfe ob Healing versucht werden soll."""
        total_attempts = len(health_state.healing_attempts)
        
        # Maximale Gesamtversuche erreicht
        if total_attempts >= self.policy.max_total_attempts:
            return False
        
        # Zähle spezifische Aktionen
        restart_attempts = sum(
            1 for attempt in health_state.healing_attempts 
            if attempt.action == HealingAction.RESTART
        )
        
        recreate_attempts = sum(
            1 for attempt in health_state.healing_attempts 
            if attempt.action == HealingAction.RECREATE
        )
        
        # Prüfe spezifische Limits
        if restart_attempts >= self.policy.max_restart_attempts:
            return False
        
        if recreate_attempts >= self.policy.max_recreate_attempts:
            return False
        
        return True
    
    def get_healing_summary(self) -> Dict[str, Any]:
        """Hole Healing-Zusammenfassung."""
        summary = {
            "total_services": len(self.health_states),
            "healing_active": self.healing_active,
            "services": {}
        }
        
        for key, health_state in self.health_states.items():
            summary["services"][key] = {
                "current_health": health_state.current_health.value,
                "consecutive_failures": health_state.consecutive_failures,
                "total_restarts": len(health_state.restart_history),
                "healing_attempts": len(health_state.healing_attempts),
                "last_health_check": health_state.last_health_check
            }
        
        return summary


# Convenience Functions
async def monitor_service_with_self_healing(
    service: ServiceInstance,
    policy: Optional[HealingPolicy] = None,
    monitoring_duration: float = 300.0
) -> Dict[str, Any]:
    """
    Convenience-Funktion für Service-Monitoring mit Self-Healing.
    
    Args:
        service: Service-Instance
        policy: Healing-Policy
        monitoring_duration: Monitoring-Dauer in Sekunden
        
    Returns:
        Monitoring-Ergebnis
    """
    orchestrator = SelfHealingOrchestrator(policy)
    return await orchestrator.monitor_and_heal_service(service, monitoring_duration)


if __name__ == "__main__":
    # Demo
    import asyncio
    from .local_orchestrator import ServiceInstance, ServiceStatus
    from .container_builder import ContainerImage
    
    async def demo_self_healing():
        print("🔄 Self-Healing Demo:")
        
        # Erstelle Mock-Service
        mock_container = ContainerImage(
            name="demo/api",
            tag="1.0.0",
            image_id="mock_id",
            size_bytes=100_000_000,
            created_at="2024-01-20T10:00:00Z"
        )
        
        mock_service = ServiceInstance(
            name="demo-api",
            container_image=mock_container,
            status=ServiceStatus.RUNNING,
            assigned_ports={"http": 8000}
        )
        
        # Healing-Policy
        policy = HealingPolicy(
            max_restart_attempts=2,
            max_recreate_attempts=1,
            initial_backoff_seconds=2.0,
            max_backoff_seconds=10.0,
            health_check_interval_seconds=3.0
        )
        
        print(f"\\nStarting monitoring for service: {mock_service.name}")
        print(f"Policy: {policy.max_restart_attempts} restarts, {policy.max_recreate_attempts} recreates")
        
        # Führe Self-Healing-Monitoring aus
        result = await monitor_service_with_self_healing(
            service=mock_service,
            policy=policy,
            monitoring_duration=30.0  # 30 Sekunden für Demo
        )
        
        print(f"\\nSelf-Healing Results:")
        print(f"Final Status: {result['final_status']}")
        print(f"Final Health: {result['final_health']}")
        print(f"Healing Attempts: {result['healing_attempts']}")
        print(f"Successful Heals: {result['successful_heals']}")
        print(f"Monitoring Duration: {result['monitoring_duration']:.2f}s")
        
        return result['final_status'] in ['healthy', 'healing_limits_exceeded']
    
    # Führe Demo aus
    try:
        result = asyncio.run(demo_self_healing())
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
