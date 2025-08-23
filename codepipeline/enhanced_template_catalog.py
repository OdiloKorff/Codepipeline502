"""
Enhanced Template Catalog mit Policy- und NFR-Integration.

Erweitert Templates um Metadaten und Policy-Consumption.
Mappt Plan-NFRs auf Template-Defaults (timeouts, threads, probes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any
import logging

from .template_catalog import ProgramType, ProgramTemplate
from .enhanced_planner import ProgramPlan, PolicySpec, NonFunctionalRequirement
from .nfr_planner import LatencyClass, ThroughputClass, MemoryClass


logger = logging.getLogger(__name__)


class RuntimeType(Enum):
    """Runtime-Typen."""
    PYTHON = "python"
    NODEJS = "nodejs"
    JAVA = "java"
    GO = "go"
    DOTNET = "dotnet"


class ObservabilityLevel(Enum):
    """Observability-Level."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


class TestType(Enum):
    """Test-Typen."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"


class BuildType(Enum):
    """Build-Typen."""
    SCRIPT = "script"
    PACKAGE = "package"
    CONTAINER = "container"
    BINARY = "binary"


class DeployProfile(Enum):
    """Deploy-Profile."""
    LOCAL = "local"
    SINGLE_NODE = "single_node"
    CLUSTER = "cluster"
    SERVERLESS = "serverless"


@dataclass
class RuntimeMetadata:
    """Runtime-Metadaten."""
    
    # Runtime
    runtime_type: RuntimeType
    version: str = "latest"
    
    # Konfiguration
    startup_command: str = ""
    health_check_command: str = ""
    
    # Ressourcen
    memory_default_mb: int = 256
    cpu_default_cores: float = 0.5
    
    # Environment
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "runtime_type": self.runtime_type.value,
            "version": self.version,
            "startup_command": self.startup_command,
            "health_check_command": self.health_check_command,
            "memory_default_mb": self.memory_default_mb,
            "cpu_default_cores": self.cpu_default_cores,
            "env_vars": self.env_vars
        }


@dataclass
class ObservabilityMetadata:
    """Observability-Metadaten."""
    
    # Level
    level: ObservabilityLevel
    
    # Logging
    structured_logging: bool = True
    log_level: str = "INFO"
    
    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    
    # Health Checks
    health_endpoint: str = "/health"
    readiness_endpoint: str = "/ready"
    liveness_endpoint: str = "/alive"
    
    # Tracing
    tracing_enabled: bool = False
    tracing_sample_rate: float = 0.1
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "level": self.level.value,
            "structured_logging": self.structured_logging,
            "log_level": self.log_level,
            "metrics_enabled": self.metrics_enabled,
            "metrics_port": self.metrics_port,
            "metrics_path": self.metrics_path,
            "health_endpoint": self.health_endpoint,
            "readiness_endpoint": self.readiness_endpoint,
            "liveness_endpoint": self.liveness_endpoint,
            "tracing_enabled": self.tracing_enabled,
            "tracing_sample_rate": self.tracing_sample_rate
        }


@dataclass
class TestMetadata:
    """Test-Metadaten."""
    
    # Test-Typen
    test_types: List[TestType] = field(default_factory=list)
    
    # Konfiguration
    test_framework: str = "pytest"
    coverage_target: int = 80
    
    # Test-Kommandos
    unit_test_command: str = "pytest tests/unit/"
    integration_test_command: str = "pytest tests/integration/"
    e2e_test_command: str = "pytest tests/e2e/"
    
    # Performance
    performance_test_enabled: bool = False
    performance_budget: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "test_types": [t.value for t in self.test_types],
            "test_framework": self.test_framework,
            "coverage_target": self.coverage_target,
            "unit_test_command": self.unit_test_command,
            "integration_test_command": self.integration_test_command,
            "e2e_test_command": self.e2e_test_command,
            "performance_test_enabled": self.performance_test_enabled,
            "performance_budget": self.performance_budget
        }


@dataclass
class BuildMetadata:
    """Build-Metadaten."""
    
    # Build-Typ
    build_type: BuildType
    
    # Build-Kommandos
    build_command: str = ""
    test_command: str = ""
    package_command: str = ""
    
    # Artefakte
    output_directory: str = "dist"
    artifact_pattern: str = "*"
    
    # Dependencies
    dependency_file: str = "requirements.txt"
    lock_file: str = "requirements.lock"
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "build_type": self.build_type.value,
            "build_command": self.build_command,
            "test_command": self.test_command,
            "package_command": self.package_command,
            "output_directory": self.output_directory,
            "artifact_pattern": self.artifact_pattern,
            "dependency_file": self.dependency_file,
            "lock_file": self.lock_file
        }


@dataclass
class ContainerMetadata:
    """Container-Metadaten."""
    
    # Base Image
    base_image: str = "python:3.10-slim"
    
    # Build
    dockerfile_template: str = "Dockerfile.template"
    multi_stage: bool = True
    
    # Security
    non_root_user: bool = True
    user_name: str = "appuser"
    readonly_filesystem: bool = False
    
    # Ports
    exposed_ports: List[int] = field(default_factory=list)
    
    # Health Check
    health_check_command: str = ""
    health_check_interval: int = 30
    health_check_timeout: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "base_image": self.base_image,
            "dockerfile_template": self.dockerfile_template,
            "multi_stage": self.multi_stage,
            "non_root_user": self.non_root_user,
            "user_name": self.user_name,
            "readonly_filesystem": self.readonly_filesystem,
            "exposed_ports": self.exposed_ports,
            "health_check_command": self.health_check_command,
            "health_check_interval": self.health_check_interval,
            "health_check_timeout": self.health_check_timeout
        }


@dataclass
class DeployMetadata:
    """Deploy-Metadaten."""
    
    # Deploy-Profile
    supported_profiles: List[DeployProfile] = field(default_factory=list)
    
    # Ressourcen
    resource_requests: Dict[str, Any] = field(default_factory=dict)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    
    # Probes
    readiness_probe: Dict[str, Any] = field(default_factory=dict)
    liveness_probe: Dict[str, Any] = field(default_factory=dict)
    startup_probe: Dict[str, Any] = field(default_factory=dict)
    
    # Scaling
    min_replicas: int = 1
    max_replicas: int = 3
    auto_scaling: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "supported_profiles": [p.value for p in self.supported_profiles],
            "resource_requests": self.resource_requests,
            "resource_limits": self.resource_limits,
            "readiness_probe": self.readiness_probe,
            "liveness_probe": self.liveness_probe,
            "startup_probe": self.startup_probe,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "auto_scaling": self.auto_scaling
        }


@dataclass
class EnhancedProgramTemplate:
    """Erweiterte Program-Template."""
    
    # Basis-Template
    base_template: ProgramTemplate
    
    # Erweiterte Metadaten
    runtime: RuntimeMetadata
    observability: ObservabilityMetadata
    tests: TestMetadata
    build: BuildMetadata
    container: ContainerMetadata
    deploy: DeployMetadata
    
    # Policy-Defaults
    default_policies: PolicySpec = field(default_factory=PolicySpec)
    
    # NFR-Mappings
    nfr_mappings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.base_template.name,
            "program_type": self.base_template.program_type.value,
            "description": self.base_template.description,
            "runtime": self.runtime.to_dict(),
            "observability": self.observability.to_dict(),
            "tests": self.tests.to_dict(),
            "build": self.build.to_dict(),
            "container": self.container.to_dict(),
            "deploy": self.deploy.to_dict(),
            "default_policies": self.default_policies.to_dict(),
            "nfr_mappings": self.nfr_mappings
        }


class NFRTemplateMapper:
    """NFR-Template-Mapper."""
    
    def __init__(self):
        pass
    
    def apply_nfrs_to_template(
        self,
        template: EnhancedProgramTemplate,
        nfrs: List[NonFunctionalRequirement]
    ) -> EnhancedProgramTemplate:
        """Wende NFRs auf Template an."""
        logger.info(f"Applying {len(nfrs)} NFRs to template {template.base_template.name}")
        
        # Kopiere Template für Modifikation
        modified_template = self._deep_copy_template(template)
        
        for nfr in nfrs:
            if nfr.requirement_type == "latency":
                self._apply_latency_nfr(modified_template, nfr)
            elif nfr.requirement_type == "throughput":
                self._apply_throughput_nfr(modified_template, nfr)
            elif nfr.requirement_type == "memory":
                self._apply_memory_nfr(modified_template, nfr)
            elif nfr.requirement_type == "availability":
                self._apply_availability_nfr(modified_template, nfr)
        
        logger.info(f"Applied NFRs to template")
        return modified_template
    
    def _apply_latency_nfr(self, template: EnhancedProgramTemplate, nfr: NonFunctionalRequirement):
        """Wende Latenz-NFR an."""
        if nfr.classification == LatencyClass.ULTRA_LOW:
            # Ultra-niedrige Latenz
            template.runtime.cpu_default_cores = max(template.runtime.cpu_default_cores, 1.0)
            template.deploy.readiness_probe["timeoutSeconds"] = 2
            template.deploy.liveness_probe["timeoutSeconds"] = 2
            template.container.health_check_timeout = 2
            
        elif nfr.classification == LatencyClass.LOW:
            # Niedrige Latenz
            template.deploy.readiness_probe["timeoutSeconds"] = 5
            template.deploy.liveness_probe["timeoutSeconds"] = 5
            template.container.health_check_timeout = 5
            
        elif nfr.classification == LatencyClass.BATCH:
            # Batch-Verarbeitung
            template.deploy.readiness_probe["timeoutSeconds"] = 30
            template.deploy.liveness_probe["timeoutSeconds"] = 60
            template.container.health_check_timeout = 30
            template.default_policies.response_time_max_ms = 10000
    
    def _apply_throughput_nfr(self, template: EnhancedProgramTemplate, nfr: NonFunctionalRequirement):
        """Wende Durchsatz-NFR an."""
        if nfr.classification == ThroughputClass.ULTRA_HIGH:
            # Ultra-hoher Durchsatz
            template.runtime.cpu_default_cores = max(template.runtime.cpu_default_cores, 2.0)
            template.runtime.memory_default_mb = max(template.runtime.memory_default_mb, 1024)
            template.deploy.max_replicas = max(template.deploy.max_replicas, 10)
            template.deploy.auto_scaling = True
            template.observability.metrics_enabled = True
            
        elif nfr.classification == ThroughputClass.HIGH:
            # Hoher Durchsatz
            template.runtime.cpu_default_cores = max(template.runtime.cpu_default_cores, 1.0)
            template.runtime.memory_default_mb = max(template.runtime.memory_default_mb, 512)
            template.deploy.max_replicas = max(template.deploy.max_replicas, 5)
            template.deploy.auto_scaling = True
            
        elif nfr.classification == ThroughputClass.MINIMAL:
            # Minimaler Durchsatz
            template.runtime.cpu_default_cores = 0.25
            template.runtime.memory_default_mb = 128
            template.deploy.max_replicas = 1
            template.deploy.auto_scaling = False
    
    def _apply_memory_nfr(self, template: EnhancedProgramTemplate, nfr: NonFunctionalRequirement):
        """Wende Speicher-NFR an."""
        if nfr.classification == MemoryClass.MINIMAL:
            # Minimaler Speicher
            template.runtime.memory_default_mb = min(template.runtime.memory_default_mb, int(nfr.value))
            template.deploy.resource_limits["memory"] = f"{nfr.value}Mi"
            template.observability.level = ObservabilityLevel.MINIMAL
            template.observability.metrics_enabled = False
            
        elif nfr.classification == MemoryClass.LOW:
            # Niedriger Speicher
            template.runtime.memory_default_mb = min(template.runtime.memory_default_mb, int(nfr.value))
            template.deploy.resource_limits["memory"] = f"{nfr.value}Mi"
            
        elif nfr.classification == MemoryClass.ULTRA_HIGH:
            # Ultra-hoher Speicher
            template.runtime.memory_default_mb = max(template.runtime.memory_default_mb, int(nfr.value))
            template.deploy.resource_requests["memory"] = f"{nfr.value}Mi"
            template.observability.level = ObservabilityLevel.COMPREHENSIVE
    
    def _apply_availability_nfr(self, template: EnhancedProgramTemplate, nfr: NonFunctionalRequirement):
        """Wende Verfügbarkeits-NFR an."""
        if nfr.value >= 99.9:  # High availability
            template.deploy.min_replicas = max(template.deploy.min_replicas, 2)
            template.deploy.readiness_probe["periodSeconds"] = 10
            template.deploy.liveness_probe["periodSeconds"] = 10
            template.deploy.readiness_probe["failureThreshold"] = 1
            template.deploy.liveness_probe["failureThreshold"] = 3
            template.observability.level = ObservabilityLevel.COMPREHENSIVE
            template.observability.tracing_enabled = True
            template.default_policies.security_level = "strict"
    
    def _deep_copy_template(self, template: EnhancedProgramTemplate) -> EnhancedProgramTemplate:
        """Erstelle Deep-Copy des Templates."""
        # Vereinfachte Deep-Copy über JSON-Serialisierung
        template_dict = template.to_dict()
        
        # Rekonstruiere Template
        runtime = RuntimeMetadata(
            runtime_type=RuntimeType(template_dict["runtime"]["runtime_type"]),
            version=template_dict["runtime"]["version"],
            startup_command=template_dict["runtime"]["startup_command"],
            health_check_command=template_dict["runtime"]["health_check_command"],
            memory_default_mb=template_dict["runtime"]["memory_default_mb"],
            cpu_default_cores=template_dict["runtime"]["cpu_default_cores"],
            env_vars=template_dict["runtime"]["env_vars"]
        )
        
        observability = ObservabilityMetadata(
            level=ObservabilityLevel(template_dict["observability"]["level"]),
            structured_logging=template_dict["observability"]["structured_logging"],
            log_level=template_dict["observability"]["log_level"],
            metrics_enabled=template_dict["observability"]["metrics_enabled"],
            metrics_port=template_dict["observability"]["metrics_port"],
            metrics_path=template_dict["observability"]["metrics_path"],
            health_endpoint=template_dict["observability"]["health_endpoint"],
            readiness_endpoint=template_dict["observability"]["readiness_endpoint"],
            liveness_endpoint=template_dict["observability"]["liveness_endpoint"],
            tracing_enabled=template_dict["observability"]["tracing_enabled"],
            tracing_sample_rate=template_dict["observability"]["tracing_sample_rate"]
        )
        
        # Weitere Metadaten kopieren (vereinfacht)
        tests = TestMetadata(
            test_types=[TestType(t) for t in template_dict["tests"]["test_types"]],
            test_framework=template_dict["tests"]["test_framework"],
            coverage_target=template_dict["tests"]["coverage_target"]
        )
        
        build = BuildMetadata(
            build_type=BuildType(template_dict["build"]["build_type"]),
            build_command=template_dict["build"]["build_command"]
        )
        
        container = ContainerMetadata(
            base_image=template_dict["container"]["base_image"],
            multi_stage=template_dict["container"]["multi_stage"],
            non_root_user=template_dict["container"]["non_root_user"]
        )
        
        deploy = DeployMetadata(
            supported_profiles=[DeployProfile(p) for p in template_dict["deploy"]["supported_profiles"]],
            resource_requests=template_dict["deploy"]["resource_requests"].copy(),
            resource_limits=template_dict["deploy"]["resource_limits"].copy(),
            readiness_probe=template_dict["deploy"]["readiness_probe"].copy(),
            liveness_probe=template_dict["deploy"]["liveness_probe"].copy(),
            min_replicas=template_dict["deploy"]["min_replicas"],
            max_replicas=template_dict["deploy"]["max_replicas"],
            auto_scaling=template_dict["deploy"]["auto_scaling"]
        )
        
        # Erstelle neues Template
        return EnhancedProgramTemplate(
            base_template=template.base_template,
            runtime=runtime,
            observability=observability,
            tests=tests,
            build=build,
            container=container,
            deploy=deploy,
            default_policies=PolicySpec(**template_dict["default_policies"]),
            nfr_mappings=template_dict["nfr_mappings"].copy()
        )


class EnhancedTemplateCatalog:
    """Erweiterter Template-Katalog."""
    
    def __init__(self):
        self.templates: Dict[str, EnhancedProgramTemplate] = {}
        self.nfr_mapper = NFRTemplateMapper()
        self._load_default_templates()
    
    def get_template(self, name: str) -> Optional[EnhancedProgramTemplate]:
        """Hole Template nach Name."""
        return self.templates.get(name)
    
    def get_template_with_plan(self, plan: ProgramPlan) -> Optional[EnhancedProgramTemplate]:
        """Hole Template und wende Plan-NFRs an."""
        base_template = self.get_template(plan.template_name)
        
        if not base_template:
            return None
        
        # Wende NFRs an
        enhanced_template = self.nfr_mapper.apply_nfrs_to_template(base_template, plan.nfrs)
        
        # Wende Template-Overrides an
        enhanced_template = self._apply_template_overrides(enhanced_template, plan.template_overrides)
        
        return enhanced_template
    
    def list_templates(self) -> List[str]:
        """Liste alle Template-Namen."""
        return list(self.templates.keys())
    
    def _apply_template_overrides(
        self,
        template: EnhancedProgramTemplate,
        overrides: Dict[str, Any]
    ) -> EnhancedProgramTemplate:
        """Wende Template-Overrides an."""
        if not overrides:
            return template
        
        # Server-Overrides
        if "server" in overrides:
            server_overrides = overrides["server"]
            if "worker_processes" in server_overrides:
                # Mappe auf CPU-Cores
                template.runtime.cpu_default_cores = float(server_overrides["worker_processes"]) * 0.25
            if "keep_alive_timeout" in server_overrides:
                template.container.health_check_timeout = server_overrides["keep_alive_timeout"]
        
        # Ressourcen-Overrides
        if "resources" in overrides:
            resource_overrides = overrides["resources"]
            if "memory_limit" in resource_overrides:
                memory_str = resource_overrides["memory_limit"]
                if memory_str.endswith("MB"):
                    memory_mb = int(memory_str[:-2])
                    template.runtime.memory_default_mb = memory_mb
                    template.deploy.resource_limits["memory"] = f"{memory_mb}Mi"
        
        return template
    
    def _load_default_templates(self):
        """Lade Standard-Templates."""
        
        # Python CLI Template
        cli_template = self._create_python_cli_template()
        self.templates["python-cli"] = cli_template
        
        # Python Web API Template
        web_api_template = self._create_python_web_api_template()
        self.templates["python-web-api"] = web_api_template
        
        # Python Worker Template
        worker_template = self._create_python_worker_template()
        self.templates["python-worker"] = worker_template
        
        # Python Batch Job Template
        batch_template = self._create_python_batch_job_template()
        self.templates["python-batch-job"] = batch_template
    
    def _create_python_cli_template(self) -> EnhancedProgramTemplate:
        """Erstelle Python CLI Template."""
        base_template = ProgramTemplate(
            name="python-cli",
            program_type=ProgramType.CLI,
            description="Python CLI application with argument parsing"
        )
        
        runtime = RuntimeMetadata(
            runtime_type=RuntimeType.PYTHON,
            version="3.10",
            startup_command="python main.py",
            health_check_command="python main.py --version",
            memory_default_mb=128,
            cpu_default_cores=0.25,
            env_vars={"PYTHONPATH": "."}
        )
        
        observability = ObservabilityMetadata(
            level=ObservabilityLevel.MINIMAL,
            structured_logging=True,
            log_level="INFO",
            metrics_enabled=False
        )
        
        tests = TestMetadata(
            test_types=[TestType.UNIT],
            test_framework="pytest",
            coverage_target=70,
            unit_test_command="pytest tests/ -v"
        )
        
        build = BuildMetadata(
            build_type=BuildType.SCRIPT,
            build_command="python -m py_compile main.py",
            test_command="pytest",
            dependency_file="requirements.txt"
        )
        
        container = ContainerMetadata(
            base_image="python:3.10-slim",
            multi_stage=True,
            non_root_user=True,
            user_name="appuser"
        )
        
        deploy = DeployMetadata(
            supported_profiles=[DeployProfile.LOCAL],
            resource_requests={"memory": "128Mi", "cpu": "0.1"},
            resource_limits={"memory": "256Mi", "cpu": "0.5"}
        )
        
        return EnhancedProgramTemplate(
            base_template=base_template,
            runtime=runtime,
            observability=observability,
            tests=tests,
            build=build,
            container=container,
            deploy=deploy
        )
    
    def _create_python_web_api_template(self) -> EnhancedProgramTemplate:
        """Erstelle Python Web API Template."""
        base_template = ProgramTemplate(
            name="python-web-api",
            program_type=ProgramType.WEB_API,
            description="Python web API with Flask/FastAPI"
        )
        
        runtime = RuntimeMetadata(
            runtime_type=RuntimeType.PYTHON,
            version="3.10",
            startup_command="python main.py",
            health_check_command="curl -f http://localhost:5000/health",
            memory_default_mb=256,
            cpu_default_cores=0.5,
            env_vars={"PYTHONPATH": ".", "PORT": "5000"}
        )
        
        observability = ObservabilityMetadata(
            level=ObservabilityLevel.STANDARD,
            structured_logging=True,
            log_level="INFO",
            metrics_enabled=True,
            metrics_port=9090,
            health_endpoint="/health",
            readiness_endpoint="/ready",
            liveness_endpoint="/health"
        )
        
        tests = TestMetadata(
            test_types=[TestType.UNIT, TestType.INTEGRATION, TestType.E2E],
            test_framework="pytest",
            coverage_target=80,
            unit_test_command="pytest tests/unit/",
            integration_test_command="pytest tests/integration/",
            e2e_test_command="pytest tests/e2e/"
        )
        
        build = BuildMetadata(
            build_type=BuildType.PACKAGE,
            build_command="python -m build",
            test_command="pytest",
            package_command="python -m build --wheel"
        )
        
        container = ContainerMetadata(
            base_image="python:3.10-slim",
            multi_stage=True,
            non_root_user=True,
            user_name="appuser",
            exposed_ports=[5000],
            health_check_command="curl -f http://localhost:5000/health",
            health_check_interval=30,
            health_check_timeout=5
        )
        
        deploy = DeployMetadata(
            supported_profiles=[DeployProfile.LOCAL, DeployProfile.SINGLE_NODE, DeployProfile.CLUSTER],
            resource_requests={"memory": "256Mi", "cpu": "0.25"},
            resource_limits={"memory": "512Mi", "cpu": "1.0"},
            readiness_probe={
                "httpGet": {"path": "/ready", "port": 5000},
                "initialDelaySeconds": 10,
                "periodSeconds": 10,
                "timeoutSeconds": 5,
                "failureThreshold": 3
            },
            liveness_probe={
                "httpGet": {"path": "/health", "port": 5000},
                "initialDelaySeconds": 30,
                "periodSeconds": 30,
                "timeoutSeconds": 5,
                "failureThreshold": 3
            },
            min_replicas=1,
            max_replicas=3,
            auto_scaling=False
        )
        
        return EnhancedProgramTemplate(
            base_template=base_template,
            runtime=runtime,
            observability=observability,
            tests=tests,
            build=build,
            container=container,
            deploy=deploy
        )
    
    def _create_python_worker_template(self) -> EnhancedProgramTemplate:
        """Erstelle Python Worker Template."""
        base_template = ProgramTemplate(
            name="python-worker",
            program_type=ProgramType.WORKER,
            description="Python background worker with queue processing"
        )
        
        runtime = RuntimeMetadata(
            runtime_type=RuntimeType.PYTHON,
            version="3.10",
            startup_command="celery worker -A main",
            health_check_command="celery inspect ping",
            memory_default_mb=256,
            cpu_default_cores=0.5,
            env_vars={"PYTHONPATH": ".", "CELERY_BROKER_URL": "redis://localhost:6379"}
        )
        
        observability = ObservabilityMetadata(
            level=ObservabilityLevel.STANDARD,
            structured_logging=True,
            log_level="INFO",
            metrics_enabled=True,
            metrics_port=9090,
            health_endpoint="/status"
        )
        
        tests = TestMetadata(
            test_types=[TestType.UNIT, TestType.INTEGRATION],
            test_framework="pytest",
            coverage_target=75
        )
        
        build = BuildMetadata(
            build_type=BuildType.PACKAGE,
            build_command="python -m build",
            test_command="pytest"
        )
        
        container = ContainerMetadata(
            base_image="python:3.10-slim",
            multi_stage=True,
            non_root_user=True,
            user_name="worker",
            exposed_ports=[5555]  # Celery Flower
        )
        
        deploy = DeployMetadata(
            supported_profiles=[DeployProfile.LOCAL, DeployProfile.CLUSTER],
            resource_requests={"memory": "256Mi", "cpu": "0.25"},
            resource_limits={"memory": "512Mi", "cpu": "1.0"},
            min_replicas=1,
            max_replicas=5,
            auto_scaling=True
        )
        
        return EnhancedProgramTemplate(
            base_template=base_template,
            runtime=runtime,
            observability=observability,
            tests=tests,
            build=build,
            container=container,
            deploy=deploy
        )
    
    def _create_python_batch_job_template(self) -> EnhancedProgramTemplate:
        """Erstelle Python Batch Job Template."""
        base_template = ProgramTemplate(
            name="python-batch-job",
            program_type=ProgramType.BATCH_JOB,
            description="Python batch job for scheduled processing"
        )
        
        runtime = RuntimeMetadata(
            runtime_type=RuntimeType.PYTHON,
            version="3.10",
            startup_command="python main.py",
            health_check_command="python main.py --dry-run",
            memory_default_mb=512,
            cpu_default_cores=1.0,
            env_vars={"PYTHONPATH": "."}
        )
        
        observability = ObservabilityMetadata(
            level=ObservabilityLevel.STANDARD,
            structured_logging=True,
            log_level="INFO",
            metrics_enabled=True
        )
        
        tests = TestMetadata(
            test_types=[TestType.UNIT, TestType.INTEGRATION],
            test_framework="pytest",
            coverage_target=80
        )
        
        build = BuildMetadata(
            build_type=BuildType.PACKAGE,
            build_command="python -m build",
            test_command="pytest"
        )
        
        container = ContainerMetadata(
            base_image="python:3.10-slim",
            multi_stage=True,
            non_root_user=True,
            user_name="batchuser"
        )
        
        deploy = DeployMetadata(
            supported_profiles=[DeployProfile.LOCAL, DeployProfile.CLUSTER],
            resource_requests={"memory": "512Mi", "cpu": "0.5"},
            resource_limits={"memory": "1Gi", "cpu": "2.0"}
        )
        
        return EnhancedProgramTemplate(
            base_template=base_template,
            runtime=runtime,
            observability=observability,
            tests=tests,
            build=build,
            container=container,
            deploy=deploy
        )


# Convenience Functions
def get_enhanced_catalog() -> EnhancedTemplateCatalog:
    """
    Hole erweiterten Template-Katalog.
    
    Returns:
        Enhanced Template Catalog
    """
    return EnhancedTemplateCatalog()


def apply_plan_to_template(plan: ProgramPlan) -> Optional[EnhancedProgramTemplate]:
    """
    Wende Plan auf Template an.
    
    Args:
        plan: Program-Plan
        
    Returns:
        Enhanced Template mit angewendeten NFRs und Policies
    """
    catalog = get_enhanced_catalog()
    return catalog.get_template_with_plan(plan)


if __name__ == "__main__":
    # Demo
    def demo_enhanced_template_catalog():
        print("📋 Enhanced Template Catalog Demo:")
        
        catalog = get_enhanced_catalog()
        
        print(f"\\nAvailable templates: {catalog.list_templates()}")
        
        # Test Template-Laden
        web_api_template = catalog.get_template("python-web-api")
        
        if web_api_template:
            print(f"\\n🌐 Web API Template:")
            print(f"  Runtime: {web_api_template.runtime.runtime_type.value} {web_api_template.runtime.version}")
            print(f"  Memory: {web_api_template.runtime.memory_default_mb}MB")
            print(f"  CPU: {web_api_template.runtime.cpu_default_cores} cores")
            print(f"  Observability: {web_api_template.observability.level.value}")
            print(f"  Health endpoint: {web_api_template.observability.health_endpoint}")
            print(f"  Test types: {[t.value for t in web_api_template.tests.test_types]}")
            print(f"  Deploy profiles: {[p.value for p in web_api_template.deploy.supported_profiles]}")
        
        # Test NFR-Anwendung
        from .enhanced_planner import create_deterministic_plan
        
        test_prompt = "Create a high-performance web API with ultra-low latency and minimal memory usage"
        plan = create_deterministic_plan(test_prompt)
        
        print(f"\\n🎯 Plan with NFRs:")
        print(f"  Program type: {plan.program_type.value}")
        print(f"  NFRs: {len(plan.nfrs)}")
        
        for nfr in plan.nfrs:
            print(f"    - {nfr.requirement_type}: {nfr.value} {nfr.unit} ({nfr.classification.value if nfr.classification else 'None'})")
        
        # Wende Plan auf Template an
        enhanced_template = catalog.get_template_with_plan(plan)
        
        if enhanced_template:
            print(f"\\n⚡ Enhanced Template (with NFRs applied):")
            print(f"  Memory: {enhanced_template.runtime.memory_default_mb}MB")
            print(f"  CPU: {enhanced_template.runtime.cpu_default_cores} cores")
            print(f"  Health check timeout: {enhanced_template.container.health_check_timeout}s")
            print(f"  Readiness probe timeout: {enhanced_template.deploy.readiness_probe.get('timeoutSeconds', 'N/A')}s")
            print(f"  Auto-scaling: {enhanced_template.deploy.auto_scaling}")
        
        # Test Determinismus
        template1 = catalog.get_template_with_plan(plan)
        template2 = catalog.get_template_with_plan(plan)
        
        deterministic = (
            template1 and template2 and
            template1.runtime.memory_default_mb == template2.runtime.memory_default_mb and
            template1.runtime.cpu_default_cores == template2.runtime.cpu_default_cores
        )
        
        print(f"\\n🎲 Template determinism: {deterministic}")
        
        return enhanced_template is not None and deterministic
    
    # Führe Demo aus
    try:
        result = demo_enhanced_template_catalog()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
