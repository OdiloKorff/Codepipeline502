"""
Minimalistische Observability Fassade für CodePipeline.

Bietet eine einheitliche Schnittstelle für:
- Run-Tracking mit eindeutigen Run-IDs
- Metriken-Logging über Zähler und Histogramme
- Standard-Logging Integration
- Abschlussstatus-Tracking

Ersetzt direkte Observability-Aufrufe durch eine saubere Fassade.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

# Setup Logging
_log = logging.getLogger(__name__)


class RunMetrics:
    """Container für Run-spezifische Metriken."""
    
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.histograms: Dict[str, list[float]] = {}
        self.gauges: Dict[str, float] = {}
        self.labels: Dict[str, str] = {}
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Erhöhe einen Zähler."""
        key = f"{name}_{self._labels_to_key(labels or {})}"
        self.counters[key] = self.counters.get(key, 0) + value
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Füge Wert zu Histogramm hinzu."""
        key = f"{name}_{self._labels_to_key(labels or {})}"
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Setze Gauge-Wert."""
        key = f"{name}_{self._labels_to_key(labels or {})}"
        self.gauges[key] = value
    
    def add_label(self, key: str, value: str):
        """Füge Run-weites Label hinzu."""
        self.labels[key] = value
    
    def _labels_to_key(self, labels: Dict[str, str]) -> str:
        """Konvertiere Labels zu String-Key."""
        if not labels:
            return ""
        sorted_items = sorted(labels.items())
        return "_".join(f"{k}={v}" for k, v in sorted_items)
    
    def to_dict(self) -> Dict[str, Any]:
        """Exportiere Metriken als Dictionary."""
        return {
            "counters": self.counters,
            "histograms": {k: {
                "count": len(v),
                "sum": sum(v),
                "min": min(v) if v else 0,
                "max": max(v) if v else 0,
                "avg": sum(v) / len(v) if v else 0
            } for k, v in self.histograms.items()},
            "gauges": self.gauges,
            "labels": self.labels
        }


class ObservabilityRun:
    """Repräsentiert einen einzelnen observierten Run."""
    
    def __init__(self, run_id: str, operation: str, context: Optional[Dict[str, str]] = None):
        self.run_id = run_id
        self.operation = operation
        self.context = context or {}
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.status: Optional[str] = None
        self.metrics = RunMetrics()
        self.error_message: Optional[str] = None
        
        # Setze Standard-Labels
        self.metrics.add_label("run_id", run_id)
        self.metrics.add_label("operation", operation)
        for k, v in self.context.items():
            self.metrics.add_label(k, v)
    
    def log_metric_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Logge Zähler-Metrik."""
        self.metrics.increment_counter(name, value, labels)
        _log.info(f"[{self.run_id}] Counter {name}: +{value}", extra={
            "run_id": self.run_id,
            "metric_type": "counter",
            "metric_name": name,
            "metric_value": value,
            "labels": labels or {}
        })
    
    def log_metric_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Logge Histogramm-Metrik."""
        self.metrics.record_histogram(name, value, labels)
        _log.info(f"[{self.run_id}] Histogram {name}: {value}", extra={
            "run_id": self.run_id,
            "metric_type": "histogram", 
            "metric_name": name,
            "metric_value": value,
            "labels": labels or {}
        })
    
    def log_metric_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Logge Gauge-Metrik."""
        self.metrics.set_gauge(name, value, labels)
        _log.info(f"[{self.run_id}] Gauge {name}: {value}", extra={
            "run_id": self.run_id,
            "metric_type": "gauge",
            "metric_name": name, 
            "metric_value": value,
            "labels": labels or {}
        })
    
    def finish(self, status: str, error_message: Optional[str] = None):
        """Beende den Run mit Status."""
        self.end_time = time.time()
        self.status = status
        self.error_message = error_message
        
        duration = self.end_time - self.start_time
        self.log_metric_histogram("run_duration_seconds", duration)
        self.log_metric_counter("runs_total", labels={"status": status})
        
        _log.info(f"[{self.run_id}] Run finished: {status} (duration: {duration:.2f}s)", extra={
            "run_id": self.run_id,
            "operation": self.operation,
            "status": status,
            "duration_seconds": duration,
            "error_message": error_message,
            "metrics": self.metrics.to_dict()
        })
        
        if status == "success":
            _log.info(f"✅ [{self.run_id}] {self.operation} completed successfully")
        else:
            _log.error(f"❌ [{self.run_id}] {self.operation} failed: {error_message or 'Unknown error'}")


class ObservabilityFacade:
    """Minimalistische Observability Fassade."""
    
    def __init__(self):
        self.active_runs: Dict[str, ObservabilityRun] = {}
    
    def start_run(self, operation: str, context: Optional[Dict[str, str]] = None, run_id: Optional[str] = None) -> ObservabilityRun:
        """Starte einen neuen observierten Run."""
        if run_id is None:
            run_id = str(uuid.uuid4())[:8]  # Kurze Run-ID
        
        run = ObservabilityRun(run_id, operation, context)
        self.active_runs[run_id] = run
        
        _log.info(f"[{run_id}] Starting {operation}", extra={
            "run_id": run_id,
            "operation": operation,
            "context": context or {},
            "start_time": datetime.fromtimestamp(run.start_time).isoformat()
        })
        
        return run
    
    def get_run(self, run_id: str) -> Optional[ObservabilityRun]:
        """Hole aktiven Run by ID."""
        return self.active_runs.get(run_id)
    
    def finish_run(self, run_id: str, status: str, error_message: Optional[str] = None):
        """Beende Run by ID."""
        run = self.active_runs.pop(run_id, None)
        if run:
            run.finish(status, error_message)
        else:
            _log.warning(f"Attempted to finish unknown run: {run_id}")
    
    @contextmanager
    def observe_operation(self, operation: str, context: Optional[Dict[str, str]] = None):
        """Context Manager für automatisches Run-Tracking."""
        run = self.start_run(operation, context)
        try:
            yield run
            run.finish("success")
        except Exception as e:
            run.finish("error", str(e))
            raise
        finally:
            # Cleanup
            self.active_runs.pop(run.run_id, None)
    
    def log_global_metric(self, name: str, value: float, metric_type: str = "gauge", labels: Optional[Dict[str, str]] = None):
        """Logge globale Metrik (ohne Run-Kontext)."""
        _log.info(f"Global {metric_type} {name}: {value}", extra={
            "metric_type": metric_type,
            "metric_name": name,
            "metric_value": value,
            "labels": labels or {}
        })


# Globale Singleton-Instanz
_facade = ObservabilityFacade()


def get_facade() -> ObservabilityFacade:
    """Hole globale Observability Fassade."""
    return _facade


def start_run(operation: str, context: Optional[Dict[str, str]] = None, run_id: Optional[str] = None) -> ObservabilityRun:
    """Convenience-Funktion zum Starten eines Runs."""
    return _facade.start_run(operation, context, run_id)


def observe_operation(operation: str, context: Optional[Dict[str, str]] = None):
    """Convenience Context Manager."""
    return _facade.observe_operation(operation, context)


def log_metric(name: str, value: float, metric_type: str = "gauge", labels: Optional[Dict[str, str]] = None):
    """Convenience-Funktion für globale Metriken."""
    _facade.log_global_metric(name, value, metric_type, labels)


# Beispiel-Demo
def demo_observability_facade():
    """Demonstriere die Observability Fassade."""
    print("🔍 Observability Fassade Demo")
    print("=" * 50)
    
    # Beispiel 1: Manuelles Run-Management
    print("\n📊 Beispiel 1: Manueller Run")
    run = start_run("feature_generation", {"spec_id": "test-001", "user": "demo"})
    
    # Logge verschiedene Metriken
    run.log_metric_counter("files_processed", 3)
    run.log_metric_counter("lines_added", 150)
    run.log_metric_counter("lines_deleted", 25)
    run.log_metric_histogram("processing_time_ms", 1250.0)
    run.log_metric_histogram("processing_time_ms", 890.0)
    run.log_metric_gauge("memory_usage_mb", 128.5)
    
    # Beende erfolgreich
    run.finish("success")
    
    # Beispiel 2: Context Manager
    print("\n📊 Beispiel 2: Context Manager")
    try:
        with observe_operation("qa_validation", {"threshold": "high"}) as run:
            run.log_metric_counter("tests_executed", 45)
            run.log_metric_counter("tests_passed", 43)
            run.log_metric_counter("tests_failed", 2)
            run.log_metric_histogram("test_duration_ms", 2340.0)
            run.log_metric_gauge("coverage_percent", 87.5)
            
            # Simuliere Erfolg
            time.sleep(0.1)
            
    except Exception as e:
        print(f"Error in context manager: {e}")
    
    # Beispiel 3: Fehlgeschlagener Run
    print("\n📊 Beispiel 3: Fehlgeschlagener Run")
    failed_run = start_run("security_scan", {"target": "production"})
    failed_run.log_metric_counter("vulnerabilities_found", 3, {"severity": "high"})
    failed_run.log_metric_counter("vulnerabilities_found", 7, {"severity": "medium"})
    failed_run.log_metric_gauge("scan_progress_percent", 100.0)
    failed_run.finish("failed", "High severity vulnerabilities detected")
    
    # Globale Metriken
    print("\n📊 Globale Metriken")
    log_metric("system_health_score", 0.95, "gauge", {"component": "pipeline"})
    log_metric("active_users", 12, "gauge")
    
    print("\n✅ Demo abgeschlossen!")


if __name__ == "__main__":
    demo_observability_facade()
