"""
Enhanced Planner für Mehrzweck-Programmtypen.

Implementiert regelbasierte Klassifikation mit deterministischer Plan-JSON-Generierung.
Mappt Prompts deterministisch in Programmtypen (cli, web-api, worker, batch).
"""

from __future__ import annotations

import re
import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging

from .template_catalog import ProgramType
from .nfr_planner import NonFunctionalRequirement, NFRExtractor, LatencyClass, ThroughputClass, MemoryClass


logger = logging.getLogger(__name__)


class ProgramClassification(Enum):
    """Program-Klassifikationen."""
    CLI = "cli"
    WEB_API = "web-api"
    WORKER = "worker"
    BATCH = "batch"


@dataclass
class ClassificationReason:
    """Klassifikations-Begründung."""
    
    # Klassifikation
    program_type: ProgramClassification
    confidence: float  # 0.0 - 1.0
    
    # Begründung
    primary_indicators: List[str] = field(default_factory=list)
    secondary_indicators: List[str] = field(default_factory=list)
    excluded_types: Dict[str, str] = field(default_factory=dict)  # type -> reason
    
    # Pattern-Matches
    matched_patterns: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "program_type": self.program_type.value,
            "confidence": self.confidence,
            "primary_indicators": self.primary_indicators,
            "secondary_indicators": self.secondary_indicators,
            "excluded_types": self.excluded_types,
            "matched_patterns": self.matched_patterns
        }


@dataclass
class ComponentSpec:
    """Komponenten-Spezifikation."""
    
    # Komponente
    name: str
    type: str  # service, database, cache, queue, etc.
    required: bool = True
    
    # Konfiguration
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Dependencies
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class PortSpec:
    """Port-Spezifikation."""
    
    # Port
    port: int
    protocol: str = "HTTP"
    
    # Beschreibung
    name: str = ""
    description: str = ""
    
    # Eigenschaften
    public: bool = False
    health_check_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class PolicySpec:
    """Policy-Spezifikation."""
    
    # Security
    security_level: str = "standard"  # minimal, standard, strict
    
    # Quality
    coverage_min: int = 30
    security_scan_required: bool = True
    license_check_required: bool = True
    
    # Performance
    response_time_max_ms: int = 1000
    memory_limit_mb: int = 512
    cpu_limit_cores: float = 1.0
    
    # Compliance
    twelve_factor_enforced: bool = True
    secrets_via_env_only: bool = True
    structured_logging: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class BudgetSpec:
    """Budget-Spezifikation."""
    
    # Token-Budget
    token_budget: int = 200
    
    # Zeit-Budget
    build_time_max_minutes: int = 10
    test_time_max_minutes: int = 5
    
    # Ressourcen-Budget
    disk_usage_max_mb: int = 100
    network_calls_max: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


@dataclass
class ProgramPlan:
    """Vollständiger Program-Plan."""
    
    # Plan-Metadaten
    plan_id: str
    created_at: str
    prompt_hash: str
    
    # Klassifikation
    program_type: ProgramClassification
    classification_reason: ClassificationReason
    
    # Plan-Komponenten
    components: List[ComponentSpec] = field(default_factory=list)
    ports: List[PortSpec] = field(default_factory=list)
    nfrs: List[NonFunctionalRequirement] = field(default_factory=list)
    policies: PolicySpec = field(default_factory=PolicySpec)
    budget: BudgetSpec = field(default_factory=BudgetSpec)
    
    # Template-Mapping
    template_name: str = ""
    template_overrides: Dict[str, Any] = field(default_factory=dict)
    
    # Validierung
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "prompt_hash": self.prompt_hash,
            "program_type": self.program_type.value,
            "classification_reason": self.classification_reason.to_dict(),
            "components": [c.to_dict() for c in self.components],
            "ports": [p.to_dict() for p in self.ports],
            "nfrs": [nfr.to_dict() for nfr in self.nfrs],
            "policies": self.policies.to_dict(),
            "budget": self.budget.to_dict(),
            "template_name": self.template_name,
            "template_overrides": self.template_overrides,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors
        }


class ProgramTypeClassifier:
    """Programmtyp-Klassifizierer."""
    
    def __init__(self):
        self.classification_rules = self._load_classification_rules()
    
    def classify_program_type(self, prompt: str) -> ClassificationReason:
        """Klassifiziere Programmtyp basierend auf Prompt."""
        logger.info("Classifying program type from prompt")
        
        prompt_lower = prompt.lower().strip()
        
        # Sammle Evidenz für jeden Typ
        cli_evidence = self._collect_cli_evidence(prompt_lower)
        web_api_evidence = self._collect_web_api_evidence(prompt_lower)
        worker_evidence = self._collect_worker_evidence(prompt_lower)
        batch_evidence = self._collect_batch_evidence(prompt_lower)
        
        # Berechne Scores
        scores = {
            ProgramClassification.CLI: self._calculate_score(cli_evidence),
            ProgramClassification.WEB_API: self._calculate_score(web_api_evidence),
            ProgramClassification.WORKER: self._calculate_score(worker_evidence),
            ProgramClassification.BATCH: self._calculate_score(batch_evidence)
        }
        
        # Bestimme besten Typ
        best_type = max(scores.keys(), key=lambda k: scores[k])
        confidence = scores[best_type]
        
        # Sammle Begründung
        if best_type == ProgramClassification.CLI:
            evidence = cli_evidence
        elif best_type == ProgramClassification.WEB_API:
            evidence = web_api_evidence
        elif best_type == ProgramClassification.WORKER:
            evidence = worker_evidence
        else:
            evidence = batch_evidence
        
        # Erstelle Begründung
        reason = ClassificationReason(
            program_type=best_type,
            confidence=confidence,
            primary_indicators=evidence.get("primary", []),
            secondary_indicators=evidence.get("secondary", []),
            matched_patterns=evidence.get("patterns", {}),
            excluded_types=self._get_exclusion_reasons(scores, best_type)
        )
        
        logger.info(f"Classified as {best_type.value} with confidence {confidence:.2f}")
        return reason
    
    def _collect_cli_evidence(self, prompt: str) -> Dict[str, Any]:
        """Sammle CLI-Evidenz."""
        evidence = {"primary": [], "secondary": [], "patterns": {}}
        
        # Primäre Indikatoren
        cli_primary_patterns = [
            (r'\bcli\b', "CLI keyword"),
            (r'\bcommand.?line\b', "Command line keyword"),
            (r'\btool\b', "Tool keyword"),
            (r'\bscript\b', "Script keyword"),
            (r'\barguments?\b', "Arguments keyword"),
            (r'\bflags?\b', "Flags keyword"),
            (r'\boptions?\b', "Options keyword"),
            (r'\bparse.?args\b', "Argument parsing"),
            (r'\btyper\b', "Typer framework"),
            (r'\bargparse\b', "Argparse library"),
            (r'\bclick\b', "Click framework")
        ]
        
        for pattern, description in cli_primary_patterns:
            if re.search(pattern, prompt):
                evidence["primary"].append(description)
                if "cli" not in evidence["patterns"]:
                    evidence["patterns"]["cli"] = []
                evidence["patterns"]["cli"].append(pattern)
        
        # Sekundäre Indikatoren
        cli_secondary_patterns = [
            (r'\bprocess\b', "Process keyword"),
            (r'\bfile.?processing\b', "File processing"),
            (r'\bdata.?conversion\b', "Data conversion"),
            (r'\butility\b', "Utility keyword"),
            (r'\bhelper\b', "Helper keyword"),
            (r'\bautomation\b', "Automation keyword")
        ]
        
        for pattern, description in cli_secondary_patterns:
            if re.search(pattern, prompt):
                evidence["secondary"].append(description)
        
        return evidence
    
    def _collect_web_api_evidence(self, prompt: str) -> Dict[str, Any]:
        """Sammle Web-API-Evidenz."""
        evidence = {"primary": [], "secondary": [], "patterns": {}}
        
        # Primäre Indikatoren
        web_api_primary_patterns = [
            (r'\bapi\b', "API keyword"),
            (r'\bweb.?api\b', "Web API keyword"),
            (r'\brest\b', "REST keyword"),
            (r'\bendpoint\b', "Endpoint keyword"),
            (r'\broute\b', "Route keyword"),
            (r'\bhttp\b', "HTTP keyword"),
            (r'\bget\b.*\bpost\b', "HTTP methods"),
            (r'\bflask\b', "Flask framework"),
            (r'\bfastapi\b', "FastAPI framework"),
            (r'\bdjango\b', "Django framework"),
            (r'\bserver\b', "Server keyword"),
            (r'\bservice\b', "Service keyword"),
            (r'\bmicroservice\b', "Microservice keyword"),
            (r'\bhealth.?check\b', "Health check"),
            (r'\bswagger\b', "Swagger/OpenAPI"),
            (r'\bopenapi\b', "OpenAPI")
        ]
        
        for pattern, description in web_api_primary_patterns:
            if re.search(pattern, prompt):
                evidence["primary"].append(description)
                if "web_api" not in evidence["patterns"]:
                    evidence["patterns"]["web_api"] = []
                evidence["patterns"]["web_api"].append(pattern)
        
        # Sekundäre Indikatoren
        web_api_secondary_patterns = [
            (r'\bjson\b', "JSON format"),
            (r'\bxml\b', "XML format"),
            (r'\bdatabase\b', "Database interaction"),
            (r'\bauth\b', "Authentication"),
            (r'\blogin\b', "Login functionality"),
            (r'\bcrud\b', "CRUD operations"),
            (r'\bvalidation\b', "Input validation")
        ]
        
        for pattern, description in web_api_secondary_patterns:
            if re.search(pattern, prompt):
                evidence["secondary"].append(description)
        
        return evidence
    
    def _collect_worker_evidence(self, prompt: str) -> Dict[str, Any]:
        """Sammle Worker-Evidenz."""
        evidence = {"primary": [], "secondary": [], "patterns": {}}
        
        # Primäre Indikatoren
        worker_primary_patterns = [
            (r'\bworker\b', "Worker keyword"),
            (r'\bbackground\b', "Background keyword"),
            (r'\btask\b', "Task keyword"),
            (r'\bqueue\b', "Queue keyword"),
            (r'\bjob\b', "Job keyword"),
            (r'\bcelery\b', "Celery framework"),
            (r'\brq\b', "RQ framework"),
            (r'\basync\b', "Async keyword"),
            (r'\bevent.?driven\b', "Event-driven"),
            (r'\bmessage\b', "Message processing"),
            (r'\bsubscriber\b', "Subscriber pattern"),
            (r'\bconsumer\b', "Consumer pattern"),
            (r'\blistener\b', "Listener pattern")
        ]
        
        for pattern, description in worker_primary_patterns:
            if re.search(pattern, prompt):
                evidence["primary"].append(description)
                if "worker" not in evidence["patterns"]:
                    evidence["patterns"]["worker"] = []
                evidence["patterns"]["worker"].append(pattern)
        
        # Sekundäre Indikatoren
        worker_secondary_patterns = [
            (r'\bprocess\b', "Processing"),
            (r'\bhandle\b', "Handling"),
            (r'\bnotification\b', "Notification"),
            (r'\bemail\b', "Email processing"),
            (r'\bimage.?processing\b', "Image processing"),
            (r'\bdata.?processing\b', "Data processing")
        ]
        
        for pattern, description in worker_secondary_patterns:
            if re.search(pattern, prompt):
                evidence["secondary"].append(description)
        
        return evidence
    
    def _collect_batch_evidence(self, prompt: str) -> Dict[str, Any]:
        """Sammle Batch-Evidenz."""
        evidence = {"primary": [], "secondary": [], "patterns": {}}
        
        # Primäre Indikatoren
        batch_primary_patterns = [
            (r'\bbatch\b', "Batch keyword"),
            (r'\bbulk\b', "Bulk keyword"),
            (r'\bmass\b', "Mass processing"),
            (r'\bschedule\b', "Scheduled processing"),
            (r'\bcron\b', "Cron job"),
            (r'\betl\b', "ETL process"),
            (r'\bextract\b.*\btransform\b.*\bload\b', "ETL pattern"),
            (r'\bmigration\b', "Data migration"),
            (r'\bimport\b', "Data import"),
            (r'\bexport\b', "Data export"),
            (r'\breport\b', "Report generation"),
            (r'\baggregate\b', "Data aggregation"),
            (r'\banalytics\b', "Analytics processing")
        ]
        
        for pattern, description in batch_primary_patterns:
            if re.search(pattern, prompt):
                evidence["primary"].append(description)
                if "batch" not in evidence["patterns"]:
                    evidence["patterns"]["batch"] = []
                evidence["patterns"]["batch"].append(pattern)
        
        # Sekundäre Indikatoren
        batch_secondary_patterns = [
            (r'\blarge.?dataset\b', "Large dataset"),
            (r'\bperiodic\b', "Periodic processing"),
            (r'\bdaily\b', "Daily processing"),
            (r'\bhourly\b', "Hourly processing"),
            (r'\bweekly\b', "Weekly processing"),
            (r'\bcleanup\b', "Cleanup process"),
            (r'\bmaintenance\b', "Maintenance task")
        ]
        
        for pattern, description in batch_secondary_patterns:
            if re.search(pattern, prompt):
                evidence["secondary"].append(description)
        
        return evidence
    
    def _calculate_score(self, evidence: Dict[str, Any]) -> float:
        """Berechne Score basierend auf Evidenz."""
        primary_weight = 2.0
        secondary_weight = 1.0
        
        primary_score = len(evidence.get("primary", [])) * primary_weight
        secondary_score = len(evidence.get("secondary", [])) * secondary_weight
        
        total_score = primary_score + secondary_score
        
        # Normalisiere auf 0.0 - 1.0
        max_possible_score = 10 * primary_weight + 5 * secondary_weight  # Geschätzte Obergrenze
        normalized_score = min(1.0, total_score / max_possible_score)
        
        return normalized_score
    
    def _get_exclusion_reasons(self, scores: Dict[ProgramClassification, float], best_type: ProgramClassification) -> Dict[str, str]:
        """Hole Ausschluss-Gründe für andere Typen."""
        exclusions = {}
        
        for program_type, score in scores.items():
            if program_type != best_type:
                if score < 0.1:
                    exclusions[program_type.value] = f"Very low confidence ({score:.2f})"
                elif score < 0.3:
                    exclusions[program_type.value] = f"Low confidence ({score:.2f})"
                else:
                    exclusions[program_type.value] = f"Lower confidence than {best_type.value} ({score:.2f} vs {scores[best_type]:.2f})"
        
        return exclusions
    
    def _load_classification_rules(self) -> Dict[str, Any]:
        """Lade Klassifikations-Regeln."""
        # In Produktion: aus Konfigurationsdatei laden
        return {
            "confidence_threshold": 0.3,
            "primary_weight": 2.0,
            "secondary_weight": 1.0
        }


class EnhancedProgramPlanner:
    """Erweiterter Program-Planner."""
    
    def __init__(self):
        self.classifier = ProgramTypeClassifier()
        self.nfr_extractor = NFRExtractor()
    
    def create_program_plan(self, prompt: str, deterministic_seed: Optional[int] = None) -> ProgramPlan:
        """Erstelle deterministischen Program-Plan."""
        logger.info("Creating program plan from prompt")
        
        # Deterministischer Hash
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        
        if deterministic_seed is not None:
            plan_id = f"plan_{prompt_hash}_{deterministic_seed}"
        else:
            plan_id = f"plan_{prompt_hash}_{int(datetime.utcnow().timestamp())}"
        
        # Klassifiziere Programmtyp
        classification_reason = self.classifier.classify_program_type(prompt)
        
        # Extrahiere NFRs
        nfrs = self.nfr_extractor.extract_nfrs_from_prompt(prompt)
        
        # Erstelle Plan
        plan = ProgramPlan(
            plan_id=plan_id,
            created_at=datetime.utcnow().isoformat(),
            prompt_hash=prompt_hash,
            program_type=classification_reason.program_type,
            classification_reason=classification_reason,
            nfrs=nfrs
        )
        
        # Generiere Komponenten
        plan.components = self._generate_components(classification_reason.program_type, prompt, nfrs)
        
        # Generiere Ports
        plan.ports = self._generate_ports(classification_reason.program_type, nfrs)
        
        # Generiere Policies
        plan.policies = self._generate_policies(classification_reason.program_type, nfrs)
        
        # Generiere Budget
        plan.budget = self._generate_budget(classification_reason.program_type, nfrs)
        
        # Template-Mapping
        plan.template_name = self._map_to_template(classification_reason.program_type)
        plan.template_overrides = self._generate_template_overrides(nfrs)
        
        # Validiere Plan
        plan.is_valid, plan.validation_errors = self._validate_plan(plan)
        
        logger.info(f"Created plan {plan_id} for {classification_reason.program_type.value}")
        return plan
    
    def _generate_components(self, program_type: ProgramClassification, prompt: str, nfrs: List[NonFunctionalRequirement]) -> List[ComponentSpec]:
        """Generiere Komponenten basierend auf Programmtyp."""
        components = []
        
        if program_type == ProgramClassification.CLI:
            components.append(ComponentSpec(
                name="cli_app",
                type="application",
                config={
                    "entry_point": "main.py",
                    "argument_parser": "typer",
                    "exit_codes": True,
                    "help_system": True
                }
            ))
        
        elif program_type == ProgramClassification.WEB_API:
            components.extend([
                ComponentSpec(
                    name="web_server",
                    type="service",
                    config={
                        "framework": "flask",
                        "workers": self._get_worker_count(nfrs),
                        "timeout": self._get_timeout(nfrs),
                        "health_endpoint": "/health"
                    }
                ),
                ComponentSpec(
                    name="api_routes",
                    type="routing",
                    dependencies=["web_server"],
                    config={
                        "openapi": True,
                        "validation": True,
                        "error_handling": True
                    }
                )
            ])
            
            # Database falls erwähnt
            if re.search(r'\bdatabase\b|\bdb\b|\bstore\b|\bpersist\b', prompt.lower()):
                components.append(ComponentSpec(
                    name="database",
                    type="database",
                    required=False,
                    config={
                        "type": "sqlite",
                        "migrations": True,
                        "connection_pool": True
                    }
                ))
        
        elif program_type == ProgramClassification.WORKER:
            components.extend([
                ComponentSpec(
                    name="worker_process",
                    type="service",
                    config={
                        "framework": "celery",
                        "concurrency": self._get_worker_count(nfrs),
                        "task_timeout": self._get_timeout(nfrs)
                    }
                ),
                ComponentSpec(
                    name="message_queue",
                    type="queue",
                    config={
                        "type": "redis",
                        "persistence": True
                    }
                )
            ])
        
        elif program_type == ProgramClassification.BATCH:
            components.append(ComponentSpec(
                name="batch_processor",
                type="application",
                config={
                    "scheduler": "cron",
                    "parallel_processing": True,
                    "checkpoint_support": True,
                    "retry_mechanism": True
                }
            ))
        
        return components
    
    def _generate_ports(self, program_type: ProgramClassification, nfrs: List[NonFunctionalRequirement]) -> List[PortSpec]:
        """Generiere Ports basierend auf Programmtyp."""
        ports = []
        
        if program_type == ProgramClassification.WEB_API:
            # Haupt-API Port
            api_port = PortSpec(
                port=5000,
                protocol="HTTP",
                name="api",
                description="Main API endpoint",
                public=True,
                health_check_path="/health"
            )
            ports.append(api_port)
            
            # Metrics Port falls High-Performance NFR
            high_perf_nfrs = [nfr for nfr in nfrs if nfr.requirement_type == "throughput" and nfr.classification in ["high", "ultra_high"]]
            if high_perf_nfrs:
                metrics_port = PortSpec(
                    port=9090,
                    protocol="HTTP",
                    name="metrics",
                    description="Prometheus metrics",
                    public=False,
                    health_check_path="/metrics"
                )
                ports.append(metrics_port)
        
        elif program_type == ProgramClassification.WORKER:
            # Management Port
            mgmt_port = PortSpec(
                port=5555,
                protocol="HTTP",
                name="management",
                description="Worker management interface",
                public=False,
                health_check_path="/status"
            )
            ports.append(mgmt_port)
        
        return ports
    
    def _generate_policies(self, program_type: ProgramClassification, nfrs: List[NonFunctionalRequirement]) -> PolicySpec:
        """Generiere Policies basierend auf Programmtyp und NFRs."""
        policies = PolicySpec()
        
        # Security-Level basierend auf Programmtyp
        if program_type == ProgramClassification.WEB_API:
            policies.security_level = "strict"
            policies.security_scan_required = True
        elif program_type == ProgramClassification.CLI:
            policies.security_level = "standard"
        else:
            policies.security_level = "standard"
        
        # NFR-basierte Anpassungen
        for nfr in nfrs:
            if nfr.requirement_type == "latency":
                if nfr.classification in [LatencyClass.ULTRA_LOW, LatencyClass.LOW]:
                    policies.response_time_max_ms = min(policies.response_time_max_ms, int(nfr.value))
            
            elif nfr.requirement_type == "memory":
                if nfr.classification in [MemoryClass.MINIMAL, MemoryClass.LOW]:
                    policies.memory_limit_mb = min(policies.memory_limit_mb, int(nfr.value))
                elif nfr.classification in [MemoryClass.HIGH, MemoryClass.ULTRA_HIGH]:
                    policies.memory_limit_mb = max(policies.memory_limit_mb, int(nfr.value))
            
            elif nfr.requirement_type == "availability":
                if nfr.value >= 99.9:
                    policies.security_level = "strict"
                    policies.coverage_min = max(policies.coverage_min, 50)
        
        return policies
    
    def _generate_budget(self, program_type: ProgramClassification, nfrs: List[NonFunctionalRequirement]) -> BudgetSpec:
        """Generiere Budget basierend auf Programmtyp und NFRs."""
        budget = BudgetSpec()
        
        # Programmtyp-spezifische Budgets
        if program_type == ProgramClassification.CLI:
            budget.token_budget = 150  # Einfacher
            budget.build_time_max_minutes = 5
        elif program_type == ProgramClassification.WEB_API:
            budget.token_budget = 250  # Komplexer
            budget.build_time_max_minutes = 10
        elif program_type == ProgramClassification.WORKER:
            budget.token_budget = 200
            budget.build_time_max_minutes = 8
        elif program_type == ProgramClassification.BATCH:
            budget.token_budget = 300  # Kann komplex sein
            budget.build_time_max_minutes = 15
        
        # NFR-basierte Anpassungen
        high_throughput_nfrs = [nfr for nfr in nfrs if nfr.requirement_type == "throughput" and nfr.classification in ["high", "ultra_high"]]
        if high_throughput_nfrs:
            budget.token_budget += 50  # Mehr Komplexität
            budget.build_time_max_minutes += 2
        
        return budget
    
    def _get_worker_count(self, nfrs: List[NonFunctionalRequirement]) -> int:
        """Bestimme Worker-Anzahl basierend auf NFRs."""
        base_workers = 2
        
        for nfr in nfrs:
            if nfr.requirement_type == "throughput":
                if nfr.classification == ThroughputClass.ULTRA_HIGH:
                    return 8
                elif nfr.classification == ThroughputClass.HIGH:
                    return 4
                elif nfr.classification == ThroughputClass.MINIMAL:
                    return 1
        
        return base_workers
    
    def _get_timeout(self, nfrs: List[NonFunctionalRequirement]) -> int:
        """Bestimme Timeout basierend auf NFRs."""
        base_timeout = 30
        
        for nfr in nfrs:
            if nfr.requirement_type == "latency":
                if nfr.classification in [LatencyClass.ULTRA_LOW, LatencyClass.LOW]:
                    return 10
                elif nfr.classification == LatencyClass.BATCH:
                    return 300
        
        return base_timeout
    
    def _map_to_template(self, program_type: ProgramClassification) -> str:
        """Mappe Programmtyp zu Template."""
        mapping = {
            ProgramClassification.CLI: "python-cli",
            ProgramClassification.WEB_API: "python-web-api",
            ProgramClassification.WORKER: "python-worker",
            ProgramClassification.BATCH: "python-batch-job"
        }
        return mapping.get(program_type, "python-cli")
    
    def _generate_template_overrides(self, nfrs: List[NonFunctionalRequirement]) -> Dict[str, Any]:
        """Generiere Template-Overrides basierend auf NFRs."""
        overrides = {}
        
        for nfr in nfrs:
            if nfr.requirement_type == "latency" and nfr.classification == LatencyClass.ULTRA_LOW:
                overrides["server"] = overrides.get("server", {})
                overrides["server"]["worker_processes"] = 1
                overrides["server"]["keep_alive_timeout"] = 5
            
            elif nfr.requirement_type == "memory" and nfr.classification == MemoryClass.MINIMAL:
                overrides["resources"] = overrides.get("resources", {})
                overrides["resources"]["memory_limit"] = f"{nfr.value}MB"
        
        return overrides
    
    def _validate_plan(self, plan: ProgramPlan) -> Tuple[bool, List[str]]:
        """Validiere Plan."""
        errors = []
        
        # Basis-Validierungen
        if not plan.components:
            errors.append("Plan must have at least one component")
        
        if plan.program_type == ProgramClassification.WEB_API and not plan.ports:
            errors.append("Web API must have at least one port")
        
        if plan.budget.token_budget <= 0:
            errors.append("Token budget must be positive")
        
        if plan.policies.coverage_min < 0 or plan.policies.coverage_min > 100:
            errors.append("Coverage minimum must be between 0 and 100")
        
        # NFR-Konsistenz
        for nfr in plan.nfrs:
            if nfr.requirement_type == "memory" and nfr.value > plan.policies.memory_limit_mb:
                errors.append(f"Memory NFR ({nfr.value}MB) exceeds policy limit ({plan.policies.memory_limit_mb}MB)")
        
        return len(errors) == 0, errors


# Convenience Functions
def create_deterministic_plan(prompt: str, seed: int = 42) -> ProgramPlan:
    """
    Erstelle deterministischen Plan aus Prompt.
    
    Args:
        prompt: Benutzer-Prompt
        seed: Deterministischer Seed
        
    Returns:
        Program-Plan
    """
    planner = EnhancedProgramPlanner()
    return planner.create_program_plan(prompt, deterministic_seed=seed)


def validate_plan_json(plan_json: str) -> Tuple[bool, List[str]]:
    """
    Validiere Plan-JSON.
    
    Args:
        plan_json: JSON-String des Plans
        
    Returns:
        Tuple von (is_valid, errors)
    """
    try:
        plan_data = json.loads(plan_json)
        
        # Erforderliche Felder prüfen
        required_fields = [
            "plan_id", "program_type", "classification_reason",
            "components", "ports", "nfrs", "policies", "budget"
        ]
        
        errors = []
        for field in required_fields:
            if field not in plan_data:
                errors.append(f"Missing required field: {field}")
        
        # Begründungsfeld prüfen
        if "classification_reason" in plan_data:
            reason = plan_data["classification_reason"]
            if "program_type" not in reason or "confidence" not in reason:
                errors.append("Classification reason must include program_type and confidence")
        
        return len(errors) == 0, errors
    
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]


if __name__ == "__main__":
    # Demo
    def demo_enhanced_planner():
        print("🎯 Enhanced Program Planner Demo:")
        
        test_prompts = [
            "Create a CLI tool to convert CSV files to JSON format",
            "Build a REST API for user management with authentication",
            "Develop a background worker to process image uploads",
            "Create a batch job to generate daily reports from database"
        ]
        
        planner = EnhancedProgramPlanner()
        
        print(f"\\nTesting {len(test_prompts)} different program types:")
        
        for i, prompt in enumerate(test_prompts, 1):
            print(f"\\n🧪 Test {i}: {prompt}")
            
            # Erstelle Plan
            plan = planner.create_program_plan(prompt, deterministic_seed=42)
            
            print(f"  ✓ Program Type: {plan.program_type.value}")
            print(f"  ✓ Confidence: {plan.classification_reason.confidence:.2f}")
            print(f"  ✓ Components: {len(plan.components)}")
            print(f"  ✓ Ports: {len(plan.ports)}")
            print(f"  ✓ NFRs: {len(plan.nfrs)}")
            print(f"  ✓ Template: {plan.template_name}")
            print(f"  ✓ Valid: {plan.is_valid}")
            
            # Zeige Begründung
            if plan.classification_reason.primary_indicators:
                print(f"    Primary indicators: {plan.classification_reason.primary_indicators[:2]}")
            
            # Zeige Komponenten
            for component in plan.components[:2]:
                print(f"    Component: {component.name} ({component.type})")
            
            # Zeige Ports
            for port in plan.ports:
                print(f"    Port: {port.port} ({port.name})")
        
        # Teste Determinismus
        print(f"\\n🎲 Testing Determinism:")
        
        test_prompt = "Create a web API for managing tasks"
        plan1 = planner.create_program_plan(test_prompt, deterministic_seed=42)
        plan2 = planner.create_program_plan(test_prompt, deterministic_seed=42)
        
        deterministic = (
            plan1.program_type == plan2.program_type and
            plan1.prompt_hash == plan2.prompt_hash and
            len(plan1.components) == len(plan2.components) and
            plan1.template_name == plan2.template_name
        )
        
        print(f"  ✓ Same prompt, same seed → Same result: {deterministic}")
        print(f"    Plan 1 type: {plan1.program_type.value}")
        print(f"    Plan 2 type: {plan2.program_type.value}")
        print(f"    Plan 1 hash: {plan1.prompt_hash}")
        print(f"    Plan 2 hash: {plan2.prompt_hash}")
        
        # Teste JSON-Validierung
        print(f"\\n📋 Testing JSON Validation:")
        
        plan_json = json.dumps(plan1.to_dict(), indent=2)
        is_valid, errors = validate_plan_json(plan_json)
        
        print(f"  ✓ JSON valid: {is_valid}")
        if errors:
            print(f"    Errors: {errors}")
        
        print(f"  ✓ JSON size: {len(plan_json)} chars")
        print(f"  ✓ Has reasoning field: {'classification_reason' in plan_json}")
        
        return deterministic and is_valid and len(errors) == 0
    
    # Führe Demo aus
    try:
        result = demo_enhanced_planner()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
