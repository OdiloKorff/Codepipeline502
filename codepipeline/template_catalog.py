"""
Template-Katalog für deployable Programme.

Unterstützte Programm-Typen: CLI, Web-API, Worker, Batch-Job
Jedes Template definiert Sprache, Subsysteme, Tests, Container-Build, Release-Artefakte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum


class ProgramType(Enum):
    """Unterstützte Programm-Typen."""
    CLI = "cli"
    WEB_API = "web-api"
    WORKER = "worker"
    BATCH_JOB = "batch-job"


class Language(Enum):
    """Unterstützte Sprachen/Runtimes."""
    PYTHON = "python"
    NODE_JS = "nodejs"
    GO = "go"
    JAVA = "java"


class Subsystem(Enum):
    """Verfügbare Subsysteme."""
    ROUTING = "routing"
    CONFIG = "config"
    HEALTH = "health"
    LOGGING = "logging"
    DATABASE = "database"
    QUEUE = "queue"
    METRICS = "metrics"
    AUTH = "auth"
    VALIDATION = "validation"


class TestType(Enum):
    """Test-Arten."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    LOAD = "load"
    HEALTH = "health"


@dataclass
class ContainerConfig:
    """Container-Build-Konfiguration."""
    base_image: str
    ports: List[int]
    health_check: str
    environment_vars: List[str]
    volumes: List[str]


@dataclass
class ReleaseArtifacts:
    """Release-Artefakte."""
    binary: Optional[str]
    container_image: str
    helm_chart: Optional[str]
    config_files: List[str]
    documentation: List[str]


@dataclass
class ProgramTemplate:
    """Template für einen Programm-Typ."""
    name: str
    program_type: ProgramType
    language: Language
    description: str
    
    # Erforderliche Subsysteme
    required_subsystems: List[Subsystem]
    optional_subsystems: List[Subsystem]
    
    # Test-Strategie
    test_types: List[TestType]
    test_coverage_min: float
    
    # Container & Deployment
    container_config: ContainerConfig
    release_artifacts: ReleaseArtifacts
    
    # Matching-Keywords für natürlichsprachliche Zuordnung
    keywords: List[str]
    
    # 12-Factor-App Compliance
    twelve_factor_compliant: bool = True


class TemplateCatalog:
    """Katalog für Programm-Templates."""
    
    def __init__(self):
        self.templates: Dict[str, ProgramTemplate] = {}
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """Initialisiere Standard-Templates."""
        
        # CLI Template
        cli_template = ProgramTemplate(
            name="python-cli",
            program_type=ProgramType.CLI,
            language=Language.PYTHON,
            description="Command-line tool with argument parsing and structured output",
            required_subsystems=[
                Subsystem.CONFIG,
                Subsystem.LOGGING,
                Subsystem.VALIDATION
            ],
            optional_subsystems=[
                Subsystem.DATABASE,
                Subsystem.METRICS
            ],
            test_types=[TestType.UNIT, TestType.INTEGRATION],
            test_coverage_min=80.0,
            container_config=ContainerConfig(
                base_image="python:3.11-slim",
                ports=[],
                health_check="python -c 'import sys; sys.exit(0)'",
                environment_vars=["LOG_LEVEL", "CONFIG_PATH"],
                volumes=["/app/config"]
            ),
            release_artifacts=ReleaseArtifacts(
                binary="dist/cli-tool",
                container_image="registry/cli-tool:latest",
                helm_chart=None,
                config_files=["config.yaml", "logging.yaml"],
                documentation=["README.md", "CLI_USAGE.md"]
            ),
            keywords=[
                "command", "cli", "tool", "script", "batch", "automation",
                "terminal", "console", "argument", "parameter", "option"
            ]
        )
        
        # Web API Template
        web_api_template = ProgramTemplate(
            name="python-web-api",
            program_type=ProgramType.WEB_API,
            language=Language.PYTHON,
            description="RESTful web API with routing, health checks, and structured logging",
            required_subsystems=[
                Subsystem.ROUTING,
                Subsystem.CONFIG,
                Subsystem.HEALTH,
                Subsystem.LOGGING,
                Subsystem.VALIDATION
            ],
            optional_subsystems=[
                Subsystem.DATABASE,
                Subsystem.AUTH,
                Subsystem.METRICS,
                Subsystem.QUEUE
            ],
            test_types=[TestType.UNIT, TestType.INTEGRATION, TestType.E2E, TestType.HEALTH],
            test_coverage_min=85.0,
            container_config=ContainerConfig(
                base_image="python:3.11-slim",
                ports=[8000, 8080],
                health_check="curl -f http://localhost:8000/health || exit 1",
                environment_vars=["PORT", "LOG_LEVEL", "DATABASE_URL", "API_KEY"],
                volumes=["/app/config", "/app/logs"]
            ),
            release_artifacts=ReleaseArtifacts(
                binary=None,
                container_image="registry/web-api:latest",
                helm_chart="charts/web-api",
                config_files=["config.yaml", "openapi.yaml"],
                documentation=["README.md", "API_DOCS.md", "DEPLOYMENT.md"]
            ),
            keywords=[
                "api", "rest", "web", "service", "http", "server", "endpoint",
                "microservice", "backend", "json", "swagger", "openapi"
            ]
        )
        
        # Worker Template
        worker_template = ProgramTemplate(
            name="python-worker",
            program_type=ProgramType.WORKER,
            language=Language.PYTHON,
            description="Background worker processing tasks from queues",
            required_subsystems=[
                Subsystem.CONFIG,
                Subsystem.HEALTH,
                Subsystem.LOGGING,
                Subsystem.QUEUE
            ],
            optional_subsystems=[
                Subsystem.DATABASE,
                Subsystem.METRICS
            ],
            test_types=[TestType.UNIT, TestType.INTEGRATION, TestType.HEALTH],
            test_coverage_min=75.0,
            container_config=ContainerConfig(
                base_image="python:3.11-slim",
                ports=[8080],  # Health check port
                health_check="python -c 'import health; health.check()' || exit 1",
                environment_vars=["QUEUE_URL", "LOG_LEVEL", "WORKER_CONCURRENCY"],
                volumes=["/app/config", "/app/logs", "/app/data"]
            ),
            release_artifacts=ReleaseArtifacts(
                binary=None,
                container_image="registry/worker:latest",
                helm_chart="charts/worker",
                config_files=["config.yaml", "worker.yaml"],
                documentation=["README.md", "WORKER_GUIDE.md"]
            ),
            keywords=[
                "worker", "background", "queue", "task", "job", "async", "celery",
                "consumer", "processor", "daemon", "service", "event"
            ]
        )
        
        # Batch Job Template
        batch_job_template = ProgramTemplate(
            name="python-batch-job",
            program_type=ProgramType.BATCH_JOB,
            language=Language.PYTHON,
            description="Batch processing job for scheduled or triggered execution",
            required_subsystems=[
                Subsystem.CONFIG,
                Subsystem.LOGGING
            ],
            optional_subsystems=[
                Subsystem.DATABASE,
                Subsystem.METRICS,
                Subsystem.VALIDATION
            ],
            test_types=[TestType.UNIT, TestType.INTEGRATION],
            test_coverage_min=70.0,
            container_config=ContainerConfig(
                base_image="python:3.11-slim",
                ports=[],
                health_check="python -c 'import sys; sys.exit(0)'",
                environment_vars=["LOG_LEVEL", "BATCH_SIZE", "INPUT_PATH", "OUTPUT_PATH"],
                volumes=["/app/input", "/app/output", "/app/config"]
            ),
            release_artifacts=ReleaseArtifacts(
                binary="dist/batch-job",
                container_image="registry/batch-job:latest",
                helm_chart="charts/batch-job",
                config_files=["config.yaml", "batch.yaml"],
                documentation=["README.md", "BATCH_GUIDE.md"]
            ),
            keywords=[
                "batch", "job", "cron", "scheduled", "etl", "process", "data",
                "pipeline", "transform", "import", "export", "migration"
            ]
        )
        
        # Registriere Templates
        self.templates = {
            "python-cli": cli_template,
            "python-web-api": web_api_template,
            "python-worker": worker_template,
            "python-batch-job": batch_job_template
        }
    
    def get_template(self, name: str) -> Optional[ProgramTemplate]:
        """Hole Template nach Name."""
        return self.templates.get(name)
    
    def list_templates(self) -> List[ProgramTemplate]:
        """Liste alle verfügbaren Templates."""
        return list(self.templates.values())
    
    def match_template_by_description(self, description: str) -> Dict[str, Any]:
        """
        Ordne Template deterministisch anhand natürlichsprachlicher Beschreibung zu.
        
        Args:
            description: Natürlichsprachliche Beschreibung des gewünschten Programms
            
        Returns:
            Dict mit Template, Confidence-Score und Begründung
        """
        description_lower = description.lower()
        
        # Scoring für jedes Template
        template_scores = {}
        
        for template_name, template in self.templates.items():
            score = 0
            matched_keywords = []
            
            # Keyword-Matching
            for keyword in template.keywords:
                if keyword in description_lower:
                    score += 10
                    matched_keywords.append(keyword)
                    
                # Partial matches (weniger Punkte)
                if any(keyword in word for word in description_lower.split()):
                    score += 3
            
            # Program-Type spezifische Patterns
            if template.program_type == ProgramType.CLI:
                if re.search(r'\b(command|cli|tool|script)\b', description_lower):
                    score += 15
            elif template.program_type == ProgramType.WEB_API:
                if re.search(r'\b(api|rest|web|service|http)\b', description_lower):
                    score += 15
            elif template.program_type == ProgramType.WORKER:
                if re.search(r'\b(worker|background|queue|async)\b', description_lower):
                    score += 15
            elif template.program_type == ProgramType.BATCH_JOB:
                if re.search(r'\b(batch|job|cron|scheduled)\b', description_lower):
                    score += 15
            
            # Subsystem-Hints
            subsystem_hints = {
                Subsystem.DATABASE: ['database', 'db', 'sql', 'postgres', 'mysql'],
                Subsystem.AUTH: ['auth', 'login', 'user', 'token', 'jwt'],
                Subsystem.QUEUE: ['queue', 'message', 'rabbit', 'redis', 'kafka'],
                Subsystem.METRICS: ['metrics', 'monitoring', 'prometheus', 'grafana']
            }
            
            for subsystem, hints in subsystem_hints.items():
                if any(hint in description_lower for hint in hints):
                    if subsystem in template.required_subsystems:
                        score += 5
                    elif subsystem in template.optional_subsystems:
                        score += 2
            
            template_scores[template_name] = {
                'template': template,
                'score': score,
                'matched_keywords': matched_keywords
            }
        
        # Finde bestes Match
        if not template_scores:
            return {
                'template': None,
                'confidence': 0.0,
                'reasoning': 'No templates available'
            }
        
        best_match = max(template_scores.items(), key=lambda x: x[1]['score'])
        best_name, best_data = best_match
        
        # Berechne Confidence (0.0 - 1.0)
        max_possible_score = 50  # Geschätzt
        confidence = min(1.0, best_data['score'] / max_possible_score)
        
        # Generiere Begründung
        reasoning_parts = []
        if best_data['matched_keywords']:
            reasoning_parts.append(f"Matched keywords: {', '.join(best_data['matched_keywords'])}")
        
        reasoning_parts.append(f"Program type: {best_data['template'].program_type.value}")
        reasoning_parts.append(f"Score: {best_data['score']}")
        
        # Fallback bei niedrigem Score
        if confidence < 0.3:
            reasoning_parts.append("Low confidence - consider providing more specific description")
        
        return {
            'template': best_data['template'],
            'template_name': best_name,
            'confidence': confidence,
            'reasoning': '; '.join(reasoning_parts),
            'all_scores': {name: data['score'] for name, data in template_scores.items()}
        }
    
    def add_template(self, name: str, template: ProgramTemplate):
        """Füge neues Template hinzu."""
        self.templates[name] = template
    
    def get_templates_by_type(self, program_type: ProgramType) -> List[ProgramTemplate]:
        """Hole alle Templates eines bestimmten Typs."""
        return [t for t in self.templates.values() if t.program_type == program_type]
    
    def get_templates_by_language(self, language: Language) -> List[ProgramTemplate]:
        """Hole alle Templates einer bestimmten Sprache."""
        return [t for t in self.templates.values() if t.language == language]


# Globaler Katalog
_catalog = TemplateCatalog()


def get_catalog() -> TemplateCatalog:
    """Hole globalen Template-Katalog."""
    return _catalog


def match_template(description: str) -> Dict[str, Any]:
    """
    Convenience-Funktion für Template-Matching.
    
    Args:
        description: Natürlichsprachliche Beschreibung
        
    Returns:
        Template-Match mit Confidence und Begründung
    """
    return _catalog.match_template_by_description(description)


# API-Funktionen
def list_available_templates() -> List[str]:
    """Liste verfügbare Template-Namen."""
    return list(_catalog.templates.keys())


def get_template_info(name: str) -> Optional[Dict[str, Any]]:
    """Hole detaillierte Template-Informationen."""
    template = _catalog.get_template(name)
    if not template:
        return None
    
    return {
        'name': name,
        'type': template.program_type.value,
        'language': template.language.value,
        'description': template.description,
        'required_subsystems': [s.value for s in template.required_subsystems],
        'optional_subsystems': [s.value for s in template.optional_subsystems],
        'test_types': [t.value for t in template.test_types],
        'test_coverage_min': template.test_coverage_min,
        'container_base_image': template.container_config.base_image,
        'container_ports': template.container_config.ports,
        'keywords': template.keywords,
        'twelve_factor_compliant': template.twelve_factor_compliant
    }


if __name__ == "__main__":
    # Demo
    catalog = get_catalog()
    
    test_descriptions = [
        "I need a REST API for user management",
        "Build a command line tool for file processing",
        "Create a background worker to process emails",
        "I want a batch job for data migration"
    ]
    
    print("🔍 Template Matching Demo:")
    for desc in test_descriptions:
        result = match_template(desc)
        print(f"\nDescription: '{desc}'")
        print(f"Best Match: {result['template_name']} (confidence: {result['confidence']:.2f})")
        print(f"Reasoning: {result['reasoning']}")
