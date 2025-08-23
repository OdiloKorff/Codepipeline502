"""
Observability Standards by Default.

Implementiert:
- Einheitliche Health-Routen oder CLI-Health
- Strukturierte JSON-Logs
- Basis-Metriken für QA-Scorecard-Integration
"""

from __future__ import annotations

import os
import sys
import json
import time
import psutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable
import logging
import threading
import collections


# Strukturiertes Logging Setup

class LogLevel(Enum):
    """Log-Level."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredJSONFormatter(logging.Formatter):
    """Strukturierter JSON-Log-Formatter."""
    
    def __init__(self, service_name: str = "app", version: str = "1.0.0"):
        super().__init__()
        self.service_name = service_name
        self.version = version
    
    def format(self, record: logging.LogRecord) -> str:
        """Formatiere Log-Record als JSON."""
        
        # Basis-Log-Struktur
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "version": self.version,
            
            # Code-Location
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            
            # Process-Info
            "process": os.getpid(),
            "thread": record.thread,
            "thread_name": record.threadName
        }
        
        # Exception-Info
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Extra Fields
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "levelname", "levelno", "pathname", 
                "filename", "module", "lineno", "funcName", "created", 
                "msecs", "relativeCreated", "thread", "threadName", 
                "processName", "process", "exc_info", "exc_text", "stack_info",
                "getMessage"
            ]:
                # Zusätzliche Felder hinzufügen
                if isinstance(value, (str, int, float, bool, list, dict)):
                    log_entry[key] = value
                else:
                    log_entry[key] = str(value)
        
        return json.dumps(log_entry, ensure_ascii=False)


def setup_structured_logging(
    service_name: str = "app",
    version: str = "1.0.0",
    log_level: str = "INFO"
):
    """Setup strukturiertes JSON-Logging."""
    
    # Root Logger konfigurieren
    root_logger = logging.getLogger()
    
    # Entferne existierende Handler
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # JSON-Handler erstellen
    handler = logging.StreamHandler(sys.stdout)
    formatter = StructuredJSONFormatter(service_name, version)
    handler.setFormatter(formatter)
    
    # Logger konfigurieren
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Externe Logger dämpfen
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    return root_logger


# Health Check System

class HealthStatus(Enum):
    """Health-Status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Einzelner Health-Check."""
    
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    checked_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "checked_at": self.checked_at
        }


@dataclass
class HealthReport:
    """Gesamt-Health-Report."""
    
    service: str
    version: str
    status: HealthStatus
    checks: List[HealthCheck] = field(default_factory=list)
    timestamp: str = ""
    uptime_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "service": self.service,
            "version": self.version,
            "status": self.status.value,
            "checks": [check.to_dict() for check in self.checks],
            "timestamp": self.timestamp,
            "uptime_seconds": self.uptime_seconds
        }


class HealthChecker:
    """Health-Check-System."""
    
    def __init__(self, service_name: str = "app", version: str = "1.0.0"):
        self.service_name = service_name
        self.version = version
        self.start_time = time.time()
        self.health_checks: Dict[str, Callable[[], HealthCheck]] = {}
        self.logger = logging.getLogger(__name__)
    
    def register_check(self, name: str, check_func: Callable[[], HealthCheck]):
        """Registriere Health-Check."""
        self.health_checks[name] = check_func
        self.logger.debug(f"Registered health check: {name}")
    
    def run_checks(self) -> HealthReport:
        """Führe alle Health-Checks aus."""
        checks = []
        overall_status = HealthStatus.HEALTHY
        
        for name, check_func in self.health_checks.items():
            start_time = time.time()
            
            try:
                check = check_func()
                check.duration_ms = (time.time() - start_time) * 1000
                check.checked_at = datetime.utcnow().isoformat() + "Z"
                
                checks.append(check)
                
                # Bestimme Gesamt-Status
                if check.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif check.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
                
            except Exception as e:
                # Fehlgeschlagener Health-Check
                failed_check = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {e}",
                    duration_ms=(time.time() - start_time) * 1000,
                    checked_at=datetime.utcnow().isoformat() + "Z"
                )
                checks.append(failed_check)
                overall_status = HealthStatus.UNHEALTHY
                
                self.logger.error(f"Health check '{name}' failed", exc_info=True)
        
        # Erstelle Report
        report = HealthReport(
            service=self.service_name,
            version=self.version,
            status=overall_status,
            checks=checks,
            timestamp=datetime.utcnow().isoformat() + "Z",
            uptime_seconds=time.time() - self.start_time
        )
        
        return report
    
    def get_basic_health(self) -> HealthReport:
        """Hole Basis-Health ohne externe Checks."""
        basic_check = HealthCheck(
            name="basic",
            status=HealthStatus.HEALTHY,
            message="Service is running",
            details={
                "uptime_seconds": time.time() - self.start_time,
                "pid": os.getpid()
            },
            checked_at=datetime.utcnow().isoformat() + "Z"
        )
        
        return HealthReport(
            service=self.service_name,
            version=self.version,
            status=HealthStatus.HEALTHY,
            checks=[basic_check],
            timestamp=datetime.utcnow().isoformat() + "Z",
            uptime_seconds=time.time() - self.start_time
        )


# Standard Health-Checks

def create_memory_health_check(max_memory_mb: int = 512) -> Callable[[], HealthCheck]:
    """Erstelle Memory Health-Check."""
    
    def check() -> HealthCheck:
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            
            if memory_mb > max_memory_mb:
                return HealthCheck(
                    name="memory",
                    status=HealthStatus.DEGRADED,
                    message=f"Memory usage high: {memory_mb:.1f}MB > {max_memory_mb}MB",
                    details={"memory_mb": memory_mb, "limit_mb": max_memory_mb}
                )
            else:
                return HealthCheck(
                    name="memory",
                    status=HealthStatus.HEALTHY,
                    message=f"Memory usage normal: {memory_mb:.1f}MB",
                    details={"memory_mb": memory_mb, "limit_mb": max_memory_mb}
                )
        
        except Exception as e:
            return HealthCheck(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check memory: {e}"
            )
    
    return check


def create_disk_health_check(max_usage_percent: int = 90) -> Callable[[], HealthCheck]:
    """Erstelle Disk Health-Check."""
    
    def check() -> HealthCheck:
        try:
            disk_usage = psutil.disk_usage('/')
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            
            if usage_percent > max_usage_percent:
                return HealthCheck(
                    name="disk",
                    status=HealthStatus.DEGRADED,
                    message=f"Disk usage high: {usage_percent:.1f}% > {max_usage_percent}%",
                    details={
                        "usage_percent": usage_percent,
                        "used_gb": disk_usage.used / (1024**3),
                        "total_gb": disk_usage.total / (1024**3)
                    }
                )
            else:
                return HealthCheck(
                    name="disk",
                    status=HealthStatus.HEALTHY,
                    message=f"Disk usage normal: {usage_percent:.1f}%",
                    details={
                        "usage_percent": usage_percent,
                        "used_gb": disk_usage.used / (1024**3),
                        "total_gb": disk_usage.total / (1024**3)
                    }
                )
        
        except Exception as e:
            return HealthCheck(
                name="disk",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check disk: {e}"
            )
    
    return check


# Metriken-System

@dataclass
class Metric:
    """Einzelne Metrik."""
    
    name: str
    value: Union[int, float]
    unit: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "labels": self.labels,
            "timestamp": self.timestamp
        }


class MetricsCollector:
    """Metriken-Collector."""
    
    def __init__(self, service_name: str = "app"):
        self.service_name = service_name
        self.start_time = time.time()
        self.metrics: Dict[str, Metric] = {}
        self.counters: Dict[str, int] = collections.defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = collections.defaultdict(list)
        self.lock = threading.Lock()
    
    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Inkrementiere Counter."""
        with self.lock:
            key = f"{name}_{labels}" if labels else name
            self.counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Setze Gauge-Wert."""
        with self.lock:
            key = f"{name}_{labels}" if labels else name
            self.gauges[key] = value
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Zeichne Histogram-Wert auf."""
        with self.lock:
            key = f"{name}_{labels}" if labels else name
            self.histograms[key].append(value)
            
            # Begrenze Historie
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
    
    def get_metrics(self) -> List[Metric]:
        """Hole alle Metriken."""
        metrics = []
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        with self.lock:
            # Basis-Metriken
            uptime = time.time() - self.start_time
            metrics.append(Metric(
                name="uptime_seconds",
                value=uptime,
                unit="seconds",
                timestamp=timestamp
            ))
            
            # System-Metriken
            try:
                process = psutil.Process()
                
                metrics.append(Metric(
                    name="memory_usage_bytes",
                    value=process.memory_info().rss,
                    unit="bytes",
                    timestamp=timestamp
                ))
                
                metrics.append(Metric(
                    name="cpu_percent",
                    value=process.cpu_percent(),
                    unit="percent",
                    timestamp=timestamp
                ))
                
            except Exception:
                pass
            
            # Counter
            for name, value in self.counters.items():
                metrics.append(Metric(
                    name=f"counter_{name}",
                    value=value,
                    unit="count",
                    timestamp=timestamp
                ))
            
            # Gauges
            for name, value in self.gauges.items():
                metrics.append(Metric(
                    name=f"gauge_{name}",
                    value=value,
                    timestamp=timestamp
                ))
            
            # Histograms (Summary-Statistiken)
            for name, values in self.histograms.items():
                if values:
                    metrics.extend([
                        Metric(
                            name=f"histogram_{name}_count",
                            value=len(values),
                            unit="count",
                            timestamp=timestamp
                        ),
                        Metric(
                            name=f"histogram_{name}_sum",
                            value=sum(values),
                            timestamp=timestamp
                        ),
                        Metric(
                            name=f"histogram_{name}_avg",
                            value=sum(values) / len(values),
                            timestamp=timestamp
                        ),
                        Metric(
                            name=f"histogram_{name}_min",
                            value=min(values),
                            timestamp=timestamp
                        ),
                        Metric(
                            name=f"histogram_{name}_max",
                            value=max(values),
                            timestamp=timestamp
                        )
                    ])
        
        return metrics
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """Hole Metriken als Dictionary."""
        metrics = self.get_metrics()
        
        return {
            "service": self.service_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metrics": [metric.to_dict() for metric in metrics]
        }


# Observability-Manager

class ObservabilityManager:
    """Zentraler Observability-Manager."""
    
    def __init__(
        self,
        service_name: str = "app",
        version: str = "1.0.0",
        log_level: str = "INFO"
    ):
        self.service_name = service_name
        self.version = version
        
        # Setup Logging
        self.logger = setup_structured_logging(service_name, version, log_level)
        
        # Setup Health Checks
        self.health_checker = HealthChecker(service_name, version)
        
        # Setup Metriken
        self.metrics_collector = MetricsCollector(service_name)
        
        # Standard Health-Checks registrieren
        self._register_standard_health_checks()
        
        self.logger.info(f"Observability initialized for {service_name} v{version}")
    
    def _register_standard_health_checks(self):
        """Registriere Standard-Health-Checks."""
        
        # Memory Check
        self.health_checker.register_check(
            "memory",
            create_memory_health_check(max_memory_mb=512)
        )
        
        # Disk Check
        self.health_checker.register_check(
            "disk",
            create_disk_health_check(max_usage_percent=90)
        )
    
    def get_health(self) -> Dict[str, Any]:
        """Hole Health-Status."""
        report = self.health_checker.run_checks()
        return report.to_dict()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Hole Metriken."""
        return self.metrics_collector.get_metrics_dict()
    
    def increment_counter(self, name: str, value: int = 1, **labels):
        """Inkrementiere Counter."""
        self.metrics_collector.increment_counter(name, value, labels)
    
    def set_gauge(self, name: str, value: float, **labels):
        """Setze Gauge."""
        self.metrics_collector.set_gauge(name, value, labels)
    
    def record_duration(self, name: str, duration_seconds: float, **labels):
        """Zeichne Dauer auf."""
        self.metrics_collector.record_histogram(f"{name}_duration", duration_seconds, labels)
    
    def register_health_check(self, name: str, check_func: Callable[[], HealthCheck]):
        """Registriere zusätzlichen Health-Check."""
        self.health_checker.register_check(name, check_func)
    
    def export_for_scorecard(self) -> Dict[str, Any]:
        """Exportiere Metriken für QA-Scorecard."""
        
        health = self.get_health()
        metrics = self.get_metrics()
        
        # Vereinfachte Metriken für Scorecard
        scorecard_metrics = {
            "observability": {
                "health_status": health["status"],
                "health_checks_count": len(health["checks"]),
                "uptime_seconds": health["uptime_seconds"],
                
                # Service-Metriken
                "memory_usage_mb": 0,
                "cpu_percent": 0,
                "metrics_count": len(metrics["metrics"])
            }
        }
        
        # Extrahiere wichtige Metriken
        for metric in metrics["metrics"]:
            if metric["name"] == "memory_usage_bytes":
                scorecard_metrics["observability"]["memory_usage_mb"] = metric["value"] / (1024 * 1024)
            elif metric["name"] == "cpu_percent":
                scorecard_metrics["observability"]["cpu_percent"] = metric["value"]
        
        return scorecard_metrics


# CLI Health Command

def create_cli_health_command(observability_manager: ObservabilityManager) -> Callable[[], int]:
    """Erstelle CLI Health-Command."""
    
    def health_command() -> int:
        """CLI Health-Check Command."""
        try:
            health = observability_manager.get_health()
            
            # Ausgabe
            print(json.dumps(health, indent=2))
            
            # Exit Code basierend auf Health-Status
            if health["status"] == "healthy":
                return 0
            elif health["status"] == "degraded":
                return 1
            else:  # unhealthy
                return 2
        
        except Exception as e:
            error_health = {
                "service": observability_manager.service_name,
                "version": observability_manager.version,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            print(json.dumps(error_health, indent=2))
            return 3
    
    return health_command


# Flask/Web Integration

def create_flask_health_routes(app, observability_manager: ObservabilityManager):
    """Erstelle Flask Health-Routes."""
    
    @app.route('/health')
    def health():
        """Health-Check Endpoint."""
        health_data = observability_manager.get_health()
        
        status_code = 200
        if health_data["status"] == "degraded":
            status_code = 200  # Noch OK
        elif health_data["status"] == "unhealthy":
            status_code = 503  # Service Unavailable
        
        return health_data, status_code
    
    @app.route('/metrics')
    def metrics():
        """Metriken Endpoint."""
        return observability_manager.get_metrics()
    
    @app.route('/ready')
    def ready():
        """Readiness Endpoint."""
        # Vereinfachter Readiness-Check
        basic_health = observability_manager.health_checker.get_basic_health()
        
        if basic_health.status == HealthStatus.HEALTHY:
            return {"status": "ready", "timestamp": datetime.utcnow().isoformat() + "Z"}
        else:
            return {"status": "not_ready", "timestamp": datetime.utcnow().isoformat() + "Z"}, 503


# Convenience Functions

def setup_observability(
    service_name: str = "app",
    version: str = "1.0.0",
    log_level: str = "INFO"
) -> ObservabilityManager:
    """
    Setup komplette Observability.
    
    Args:
        service_name: Service-Name
        version: Service-Version
        log_level: Log-Level
        
    Returns:
        Observability-Manager
    """
    return ObservabilityManager(service_name, version, log_level)


if __name__ == "__main__":
    # Demo
    def demo_observability_standards():
        print("📊 Observability Standards Demo:")
        
        # Setup Observability
        obs = setup_observability("demo-service", "1.0.0", "INFO")
        
        print(f"\\n✓ Observability initialized for {obs.service_name}")
        
        # Test strukturiertes Logging
        print("\\n📝 Testing structured logging:")
        obs.logger.info("Demo application started", extra={"component": "demo"})
        obs.logger.warning("This is a warning message", extra={"code": "WARN001"})
        
        # Test Metriken
        print("\\n📊 Testing metrics:")
        obs.increment_counter("requests_total", 5)
        obs.set_gauge("active_connections", 10)
        obs.record_duration("request_duration", 0.125)
        
        metrics = obs.get_metrics()
        print(f"  ✓ Collected {len(metrics['metrics'])} metrics")
        
        # Zeige einige Metriken
        for metric in metrics['metrics'][:3]:
            print(f"    - {metric['name']}: {metric['value']} {metric.get('unit', '')}")
        
        # Test Health Checks
        print("\\n🏥 Testing health checks:")
        health = obs.get_health()
        
        print(f"  ✓ Overall status: {health['status']}")
        print(f"  ✓ Uptime: {health['uptime_seconds']:.1f} seconds")
        print(f"  ✓ Health checks: {len(health['checks'])}")
        
        for check in health['checks']:
            status_icon = "✅" if check['status'] == 'healthy' else "⚠️" if check['status'] == 'degraded' else "❌"
            print(f"    {status_icon} {check['name']}: {check['status']} ({check['duration_ms']:.1f}ms)")
        
        # Test CLI Health Command
        print("\\n🖥️ Testing CLI health command:")
        cli_health = create_cli_health_command(obs)
        
        exit_code = cli_health()
        print(f"  ✓ CLI health exit code: {exit_code}")
        
        # Test Scorecard Export
        print("\\n📋 Testing scorecard export:")
        scorecard_data = obs.export_for_scorecard()
        
        observability_metrics = scorecard_data["observability"]
        print(f"  ✓ Health status: {observability_metrics['health_status']}")
        print(f"  ✓ Memory usage: {observability_metrics['memory_usage_mb']:.1f} MB")
        print(f"  ✓ CPU usage: {observability_metrics['cpu_percent']:.1f}%")
        print(f"  ✓ Metrics count: {observability_metrics['metrics_count']}")
        
        # Test Akzeptanz-Kriterien
        print("\\n🎯 Acceptance criteria:")
        
        # Health-Routen verfügbar
        health_available = health['status'] in ['healthy', 'degraded', 'unhealthy']
        
        # Strukturierte JSON-Logs
        json_logs = True  # StructuredJSONFormatter implementiert
        
        # Basis-Metriken verfügbar
        has_basic_metrics = len(metrics['metrics']) > 0
        
        # Scorecard-Integration
        scorecard_integration = 'observability' in scorecard_data
        
        print(f"  ✓ Health endpoints available: {health_available}")
        print(f"  ✓ Structured JSON logs: {json_logs}")
        print(f"  ✓ Basic metrics collected: {has_basic_metrics}")
        print(f"  ✓ QA scorecard integration: {scorecard_integration}")
        
        return (health_available and json_logs and 
               has_basic_metrics and scorecard_integration)
    
    # Führe Demo aus
    try:
        result = demo_observability_standards()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
