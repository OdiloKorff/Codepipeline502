"""
Performance-Sanity-Budget.

Definiert ein kleines Performance-Budget pro Template und prüft es 
im E2E-Harness. Ergebnisse werden geloggt und in die Scorecard übernommen.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

from .template_catalog import ProgramTemplate, ProgramType
from .e2e_test_harness import E2ETestResult


logger = logging.getLogger(__name__)


class PerformanceMetric(Enum):
    """Performance-Metriken."""
    STARTUP_TIME = "startup_time"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    SHUTDOWN_TIME = "shutdown_time"


class BudgetStatus(Enum):
    """Budget-Status."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass
class PerformanceBudgetLimit:
    """Performance-Budget-Limit."""
    
    metric: PerformanceMetric
    
    # Limits
    target_value: float  # Zielwert
    warning_threshold: float  # Warnschwelle
    failure_threshold: float  # Fehlerschwelle
    
    # Einheit
    unit: str = ""
    
    # Beschreibung
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "metric": self.metric.value,
            "target_value": self.target_value,
            "warning_threshold": self.warning_threshold,
            "failure_threshold": self.failure_threshold,
            "unit": self.unit,
            "description": self.description
        }


@dataclass
class PerformanceMeasurement:
    """Performance-Messung."""
    
    metric: PerformanceMetric
    value: float
    unit: str
    
    # Messung-Metadaten
    measured_at: str
    measurement_duration: float = 0.0
    
    # Kontext
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "metric": self.metric.value,
            "value": self.value,
            "unit": self.unit,
            "measured_at": self.measured_at,
            "measurement_duration": self.measurement_duration,
            "context": self.context
        }


@dataclass
class BudgetEvaluation:
    """Budget-Evaluation."""
    
    metric: PerformanceMetric
    measured_value: float
    budget_limit: PerformanceBudgetLimit
    
    # Evaluation-Ergebnis
    status: BudgetStatus = BudgetStatus.UNKNOWN
    deviation_percent: float = 0.0
    
    # Details
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "metric": self.metric.value,
            "measured_value": self.measured_value,
            "budget_limit": self.budget_limit.to_dict(),
            "status": self.status.value,
            "deviation_percent": self.deviation_percent,
            "message": self.message
        }


@dataclass
class PerformanceBudget:
    """Performance-Budget für Template."""
    
    # Template-Informationen
    template_name: str
    template_type: ProgramType
    
    # Budget-Limits
    limits: List[PerformanceBudgetLimit] = field(default_factory=list)
    
    # Metadaten
    created_at: str = ""
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "template_name": self.template_name,
            "template_type": self.template_type.value,
            "limits": [limit.to_dict() for limit in self.limits],
            "created_at": self.created_at,
            "version": self.version
        }


@dataclass
class PerformanceBudgetResult:
    """Performance-Budget-Ergebnis."""
    
    # Budget-Informationen
    budget: PerformanceBudget
    
    # Messungen
    measurements: List[PerformanceMeasurement] = field(default_factory=list)
    
    # Evaluationen
    evaluations: List[BudgetEvaluation] = field(default_factory=list)
    
    # Gesamt-Status
    overall_status: BudgetStatus = BudgetStatus.UNKNOWN
    
    # Zusammenfassung
    passed_checks: int = 0
    warning_checks: int = 0
    failed_checks: int = 0
    
    # Metadaten
    evaluated_at: str = ""
    evaluation_duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "budget": self.budget.to_dict(),
            "measurements": [m.to_dict() for m in self.measurements],
            "evaluations": [e.to_dict() for e in self.evaluations],
            "overall_status": self.overall_status.value,
            "passed_checks": self.passed_checks,
            "warning_checks": self.warning_checks,
            "failed_checks": self.failed_checks,
            "evaluated_at": self.evaluated_at,
            "evaluation_duration": self.evaluation_duration
        }


class PerformanceBudgetRegistry:
    """Registry für Performance-Budgets."""
    
    @staticmethod
    def get_default_budgets() -> Dict[ProgramType, PerformanceBudget]:
        """Hole Standard-Budgets für Programm-Typen."""
        budgets = {}
        
        # Web-API Budget
        web_api_budget = PerformanceBudget(
            template_name="web-api",
            template_type=ProgramType.WEB_API,
            created_at=datetime.utcnow().isoformat(),
            limits=[
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.STARTUP_TIME,
                    target_value=5.0,
                    warning_threshold=10.0,
                    failure_threshold=20.0,
                    unit="seconds",
                    description="Time to start and become ready"
                ),
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.RESPONSE_TIME,
                    target_value=100.0,
                    warning_threshold=500.0,
                    failure_threshold=2000.0,
                    unit="ms",
                    description="Average HTTP response time"
                ),
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.THROUGHPUT,
                    target_value=100.0,
                    warning_threshold=50.0,
                    failure_threshold=10.0,
                    unit="req/s",
                    description="Requests per second under load"
                ),
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.MEMORY_USAGE,
                    target_value=128.0,
                    warning_threshold=256.0,
                    failure_threshold=512.0,
                    unit="MB",
                    description="Peak memory usage"
                )
            ]
        )
        budgets[ProgramType.WEB_API] = web_api_budget
        
        # CLI Budget
        cli_budget = PerformanceBudget(
            template_name="cli",
            template_type=ProgramType.CLI,
            created_at=datetime.utcnow().isoformat(),
            limits=[
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.STARTUP_TIME,
                    target_value=1.0,
                    warning_threshold=3.0,
                    failure_threshold=10.0,
                    unit="seconds",
                    description="Time to CLI ready"
                ),
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.RESPONSE_TIME,
                    target_value=500.0,
                    warning_threshold=2000.0,
                    failure_threshold=10000.0,
                    unit="ms",
                    description="Command execution time"
                ),
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.MEMORY_USAGE,
                    target_value=64.0,
                    warning_threshold=128.0,
                    failure_threshold=256.0,
                    unit="MB",
                    description="Peak memory usage"
                )
            ]
        )
        budgets[ProgramType.CLI] = cli_budget
        
        # Worker Budget
        worker_budget = PerformanceBudget(
            template_name="worker",
            template_type=ProgramType.WORKER,
            created_at=datetime.utcnow().isoformat(),
            limits=[
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.STARTUP_TIME,
                    target_value=3.0,
                    warning_threshold=10.0,
                    failure_threshold=30.0,
                    unit="seconds",
                    description="Time to worker ready"
                ),
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.THROUGHPUT,
                    target_value=10.0,
                    warning_threshold=5.0,
                    failure_threshold=1.0,
                    unit="jobs/s",
                    description="Job processing rate"
                ),
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.MEMORY_USAGE,
                    target_value=256.0,
                    warning_threshold=512.0,
                    failure_threshold=1024.0,
                    unit="MB",
                    description="Peak memory usage"
                )
            ]
        )
        budgets[ProgramType.WORKER] = worker_budget
        
        # Batch-Job Budget
        batch_budget = PerformanceBudget(
            template_name="batch-job",
            template_type=ProgramType.BATCH_JOB,
            created_at=datetime.utcnow().isoformat(),
            limits=[
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.STARTUP_TIME,
                    target_value=2.0,
                    warning_threshold=5.0,
                    failure_threshold=15.0,
                    unit="seconds",
                    description="Time to job ready"
                ),
                PerformanceBudgetLimit(
                    metric=PerformanceMetric.MEMORY_USAGE,
                    target_value=512.0,
                    warning_threshold=1024.0,
                    failure_threshold=2048.0,
                    unit="MB",
                    description="Peak memory usage during batch processing"
                )
            ]
        )
        budgets[ProgramType.BATCH_JOB] = batch_budget
        
        return budgets


class PerformanceMeasurementCollector:
    """Sammelt Performance-Messungen."""
    
    def __init__(self):
        pass
    
    async def measure_startup_time(
        self,
        service_name: str,
        start_callback: callable,
        health_check_callback: callable
    ) -> PerformanceMeasurement:
        """Messe Startup-Zeit."""
        logger.info(f"Measuring startup time for {service_name}")
        
        start_time = time.time()
        measured_at = datetime.utcnow().isoformat()
        
        try:
            # Starte Service
            await start_callback()
            
            # Warte auf Health-Check
            max_wait_time = 60.0  # 60 Sekunden Maximum
            check_interval = 0.5  # 0.5 Sekunden zwischen Checks
            
            elapsed = 0.0
            while elapsed < max_wait_time:
                if await health_check_callback():
                    break
                
                await asyncio.sleep(check_interval)
                elapsed = time.time() - start_time
            
            startup_time = time.time() - start_time
            
            return PerformanceMeasurement(
                metric=PerformanceMetric.STARTUP_TIME,
                value=startup_time,
                unit="seconds",
                measured_at=measured_at,
                measurement_duration=startup_time,
                context={"service_name": service_name}
            )
            
        except Exception as e:
            logger.error(f"Failed to measure startup time for {service_name}: {e}")
            # Fallback: sehr hoher Wert bei Fehler
            return PerformanceMeasurement(
                metric=PerformanceMetric.STARTUP_TIME,
                value=999.0,
                unit="seconds",
                measured_at=measured_at,
                context={"service_name": service_name, "error": str(e)}
            )
    
    async def measure_response_time(
        self,
        service_name: str,
        request_callback: callable,
        num_requests: int = 10
    ) -> PerformanceMeasurement:
        """Messe Response-Zeit."""
        logger.info(f"Measuring response time for {service_name}")
        
        measured_at = datetime.utcnow().isoformat()
        response_times = []
        
        try:
            for i in range(num_requests):
                start_time = time.time()
                
                try:
                    await request_callback()
                    response_time = (time.time() - start_time) * 1000  # ms
                    response_times.append(response_time)
                except Exception as e:
                    logger.warning(f"Request {i+1} failed: {e}")
                    response_times.append(5000.0)  # 5s penalty für Fehler
                
                # Kurze Pause zwischen Requests
                await asyncio.sleep(0.1)
            
            # Berechne Durchschnitt
            avg_response_time = statistics.mean(response_times) if response_times else 5000.0
            
            return PerformanceMeasurement(
                metric=PerformanceMetric.RESPONSE_TIME,
                value=avg_response_time,
                unit="ms",
                measured_at=measured_at,
                measurement_duration=len(response_times) * 0.1,
                context={
                    "service_name": service_name,
                    "num_requests": len(response_times),
                    "min_response_time": min(response_times) if response_times else 0,
                    "max_response_time": max(response_times) if response_times else 0
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to measure response time for {service_name}: {e}")
            return PerformanceMeasurement(
                metric=PerformanceMetric.RESPONSE_TIME,
                value=5000.0,
                unit="ms",
                measured_at=measured_at,
                context={"service_name": service_name, "error": str(e)}
            )
    
    async def measure_throughput(
        self,
        service_name: str,
        request_callback: callable,
        duration_seconds: float = 10.0
    ) -> PerformanceMeasurement:
        """Messe Durchsatz."""
        logger.info(f"Measuring throughput for {service_name}")
        
        measured_at = datetime.utcnow().isoformat()
        
        try:
            start_time = time.time()
            successful_requests = 0
            
            # Führe Requests für gegebene Dauer aus
            while (time.time() - start_time) < duration_seconds:
                try:
                    await request_callback()
                    successful_requests += 1
                except Exception:
                    pass  # Ignoriere Fehler für Durchsatz-Messung
                
                # Minimale Pause
                await asyncio.sleep(0.01)
            
            actual_duration = time.time() - start_time
            throughput = successful_requests / actual_duration
            
            return PerformanceMeasurement(
                metric=PerformanceMetric.THROUGHPUT,
                value=throughput,
                unit="req/s",
                measured_at=measured_at,
                measurement_duration=actual_duration,
                context={
                    "service_name": service_name,
                    "successful_requests": successful_requests,
                    "duration_seconds": actual_duration
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to measure throughput for {service_name}: {e}")
            return PerformanceMeasurement(
                metric=PerformanceMetric.THROUGHPUT,
                value=0.0,
                unit="req/s",
                measured_at=measured_at,
                context={"service_name": service_name, "error": str(e)}
            )
    
    def measure_memory_usage(
        self,
        service_name: str,
        memory_callback: callable
    ) -> PerformanceMeasurement:
        """Messe Memory-Usage."""
        logger.info(f"Measuring memory usage for {service_name}")
        
        measured_at = datetime.utcnow().isoformat()
        
        try:
            memory_mb = memory_callback()
            
            return PerformanceMeasurement(
                metric=PerformanceMetric.MEMORY_USAGE,
                value=memory_mb,
                unit="MB",
                measured_at=measured_at,
                context={"service_name": service_name}
            )
            
        except Exception as e:
            logger.error(f"Failed to measure memory usage for {service_name}: {e}")
            return PerformanceMeasurement(
                metric=PerformanceMetric.MEMORY_USAGE,
                value=999.0,
                unit="MB",
                measured_at=measured_at,
                context={"service_name": service_name, "error": str(e)}
            )


class PerformanceBudgetEvaluator:
    """Evaluiert Performance-Budgets."""
    
    def __init__(self):
        pass
    
    def evaluate_budget(
        self,
        budget: PerformanceBudget,
        measurements: List[PerformanceMeasurement]
    ) -> PerformanceBudgetResult:
        """Evaluiere Performance-Budget."""
        logger.info(f"Evaluating performance budget for {budget.template_name}")
        
        start_time = time.time()
        
        result = PerformanceBudgetResult(
            budget=budget,
            measurements=measurements,
            evaluated_at=datetime.utcnow().isoformat()
        )
        
        # Erstelle Mapping von Messungen
        measurement_map = {}
        for measurement in measurements:
            measurement_map[measurement.metric] = measurement
        
        # Evaluiere jedes Budget-Limit
        for limit in budget.limits:
            if limit.metric in measurement_map:
                measurement = measurement_map[limit.metric]
                evaluation = self._evaluate_limit(limit, measurement)
                result.evaluations.append(evaluation)
                
                # Aktualisiere Zähler
                if evaluation.status == BudgetStatus.PASS:
                    result.passed_checks += 1
                elif evaluation.status == BudgetStatus.WARN:
                    result.warning_checks += 1
                elif evaluation.status == BudgetStatus.FAIL:
                    result.failed_checks += 1
        
        # Bestimme Overall-Status
        result.overall_status = self._determine_overall_status(result.evaluations)
        
        result.evaluation_duration = time.time() - start_time
        
        logger.info(f"Budget evaluation completed: {result.overall_status.value}")
        return result
    
    def _evaluate_limit(
        self,
        limit: PerformanceBudgetLimit,
        measurement: PerformanceMeasurement
    ) -> BudgetEvaluation:
        """Evaluiere einzelnes Budget-Limit."""
        evaluation = BudgetEvaluation(
            metric=limit.metric,
            measured_value=measurement.value,
            budget_limit=limit
        )
        
        # Berechne Abweichung vom Zielwert
        if limit.target_value > 0:
            evaluation.deviation_percent = (
                (measurement.value - limit.target_value) / limit.target_value * 100
            )
        
        # Bestimme Status basierend auf Schwellwerten
        if measurement.value <= limit.target_value:
            evaluation.status = BudgetStatus.PASS
            evaluation.message = f"Within target ({measurement.value} {limit.unit} ≤ {limit.target_value} {limit.unit})"
        elif measurement.value <= limit.warning_threshold:
            evaluation.status = BudgetStatus.WARN
            evaluation.message = f"Above target but within warning threshold ({measurement.value} {limit.unit} ≤ {limit.warning_threshold} {limit.unit})"
        elif measurement.value <= limit.failure_threshold:
            evaluation.status = BudgetStatus.FAIL
            evaluation.message = f"Above warning threshold ({measurement.value} {limit.unit} > {limit.warning_threshold} {limit.unit})"
        else:
            evaluation.status = BudgetStatus.FAIL
            evaluation.message = f"Exceeds failure threshold ({measurement.value} {limit.unit} > {limit.failure_threshold} {limit.unit})"
        
        return evaluation
    
    def _determine_overall_status(self, evaluations: List[BudgetEvaluation]) -> BudgetStatus:
        """Bestimme Overall-Status."""
        if not evaluations:
            return BudgetStatus.UNKNOWN
        
        statuses = [eval.status for eval in evaluations]
        
        if BudgetStatus.FAIL in statuses:
            return BudgetStatus.FAIL
        elif BudgetStatus.WARN in statuses:
            return BudgetStatus.WARN
        elif all(status == BudgetStatus.PASS for status in statuses):
            return BudgetStatus.PASS
        else:
            return BudgetStatus.UNKNOWN


class PerformanceBudgetOrchestrator:
    """Performance-Budget-Orchestrator."""
    
    def __init__(self):
        self.registry = PerformanceBudgetRegistry()
        self.collector = PerformanceMeasurementCollector()
        self.evaluator = PerformanceBudgetEvaluator()
    
    async def evaluate_template_performance(
        self,
        template: ProgramTemplate,
        service_name: str,
        service_callbacks: Dict[str, callable]
    ) -> PerformanceBudgetResult:
        """Evaluiere Performance für Template."""
        logger.info(f"Evaluating performance for template: {template.name}")
        
        # Hole Budget für Template-Typ
        budgets = self.registry.get_default_budgets()
        budget = budgets.get(template.program_type)
        
        if not budget:
            logger.warning(f"No budget defined for program type: {template.program_type}")
            return PerformanceBudgetResult(
                budget=PerformanceBudget(
                    template_name=template.name,
                    template_type=template.program_type
                ),
                overall_status=BudgetStatus.UNKNOWN
            )
        
        # Sammle Messungen
        measurements = []
        
        for limit in budget.limits:
            try:
                measurement = await self._collect_measurement(
                    limit.metric, service_name, service_callbacks
                )
                measurements.append(measurement)
            except Exception as e:
                logger.error(f"Failed to collect measurement for {limit.metric.value}: {e}")
        
        # Evaluiere Budget
        result = self.evaluator.evaluate_budget(budget, measurements)
        
        logger.info(f"Performance evaluation completed: {result.overall_status.value}")
        return result
    
    async def _collect_measurement(
        self,
        metric: PerformanceMetric,
        service_name: str,
        callbacks: Dict[str, callable]
    ) -> PerformanceMeasurement:
        """Sammle einzelne Messung."""
        if metric == PerformanceMetric.STARTUP_TIME:
            return await self.collector.measure_startup_time(
                service_name,
                callbacks.get("start_service", lambda: None),
                callbacks.get("health_check", lambda: True)
            )
        
        elif metric == PerformanceMetric.RESPONSE_TIME:
            return await self.collector.measure_response_time(
                service_name,
                callbacks.get("make_request", lambda: None)
            )
        
        elif metric == PerformanceMetric.THROUGHPUT:
            return await self.collector.measure_throughput(
                service_name,
                callbacks.get("make_request", lambda: None)
            )
        
        elif metric == PerformanceMetric.MEMORY_USAGE:
            return self.collector.measure_memory_usage(
                service_name,
                callbacks.get("get_memory_usage", lambda: 64.0)  # Default 64MB
            )
        
        else:
            # Fallback für unbekannte Metriken
            return PerformanceMeasurement(
                metric=metric,
                value=0.0,
                unit="unknown",
                measured_at=datetime.utcnow().isoformat(),
                context={"service_name": service_name, "error": "Unknown metric"}
            )


# Convenience Functions
async def evaluate_performance_budget(
    template: ProgramTemplate,
    service_name: str,
    service_callbacks: Dict[str, callable]
) -> PerformanceBudgetResult:
    """
    Convenience-Funktion für Performance-Budget-Evaluation.
    
    Args:
        template: Program-Template
        service_name: Service-Name
        service_callbacks: Service-Callbacks für Messungen
        
    Returns:
        Performance-Budget-Ergebnis
    """
    orchestrator = PerformanceBudgetOrchestrator()
    return await orchestrator.evaluate_template_performance(
        template, service_name, service_callbacks
    )


if __name__ == "__main__":
    # Demo
    import asyncio
    from .template_catalog import get_catalog
    
    async def demo_performance_budget():
        print("📊 Performance Budget Demo:")
        
        # Hole Template
        catalog = get_catalog()
        template = catalog.get_template("python-web-api")
        
        if not template:
            print("Template not found")
            return False
        
        print(f"\\nEvaluating performance for template: {template.name}")
        
        # Mock-Service-Callbacks
        async def mock_start_service():
            await asyncio.sleep(2.0)  # Simuliere 2s Startup
        
        async def mock_health_check():
            return True
        
        async def mock_make_request():
            await asyncio.sleep(0.05)  # Simuliere 50ms Request
        
        def mock_get_memory_usage():
            return 128.0  # Simuliere 128MB Memory
        
        callbacks = {
            "start_service": mock_start_service,
            "health_check": mock_health_check,
            "make_request": mock_make_request,
            "get_memory_usage": mock_get_memory_usage
        }
        
        # Führe Performance-Evaluation aus
        result = await evaluate_performance_budget(
            template=template,
            service_name="demo-api",
            service_callbacks=callbacks
        )
        
        print(f"\\nPerformance Budget Results:")
        print(f"Overall Status: {result.overall_status.value}")
        print(f"Measurements: {len(result.measurements)}")
        print(f"Evaluations: {len(result.evaluations)}")
        print(f"Passed: {result.passed_checks}")
        print(f"Warnings: {result.warning_checks}")
        print(f"Failed: {result.failed_checks}")
        
        print(f"\\nDetailed Results:")
        for evaluation in result.evaluations:
            status_icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}.get(evaluation.status.value, "❓")
            print(f"  {status_icon} {evaluation.metric.value}: {evaluation.measured_value} {evaluation.budget_limit.unit}")
            print(f"    {evaluation.message}")
        
        return result.overall_status in [BudgetStatus.PASS, BudgetStatus.WARN]
    
    # Führe Demo aus
    try:
        result = asyncio.run(demo_performance_budget())
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
