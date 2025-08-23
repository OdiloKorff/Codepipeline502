"""
12-Factor-konformer Scaffolder.

Erzeugt Skeletons die 12-Factor-konform sind:
- Config via env, keine Secrets im Code
- Strukturierte Logs, Health-Endpoint oder Exit-Status bei CLI
- Minimale Unit-Tests und Smoke-Test
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from .enhanced_template_catalog import EnhancedProgramTemplate, EnhancedTemplateCatalog
from .enhanced_planner import ProgramPlan, ProgramClassification


logger = logging.getLogger(__name__)


@dataclass
class ScaffoldConfig:
    """Scaffold-Konfiguration."""
    
    # Projekt-Info
    project_name: str
    project_dir: Path
    
    # 12-Factor Enforcement
    enforce_twelve_factor: bool = True
    config_via_env: bool = True
    no_secrets_in_code: bool = True
    structured_logging: bool = True
    
    # Health & Status
    health_endpoint_required: bool = True
    exit_status_required: bool = True
    
    # Tests
    generate_unit_tests: bool = True
    generate_smoke_test: bool = True
    
    # Zusätzliche Optionen
    generate_dockerfile: bool = True
    generate_gitignore: bool = True
    generate_readme: bool = True


@dataclass
class ScaffoldResult:
    """Scaffold-Ergebnis."""
    
    # Status
    success: bool
    project_dir: Path
    
    # Generierte Dateien
    files_created: List[str] = field(default_factory=list)
    
    # 12-Factor Compliance
    twelve_factor_compliant: bool = True
    compliance_violations: List[str] = field(default_factory=list)
    
    # Health Check
    health_check_available: bool = False
    health_check_command: str = ""
    
    # Tests
    unit_tests_generated: bool = False
    smoke_test_generated: bool = False
    test_command: str = ""
    
    # Startup
    startup_command: str = ""
    can_start_locally: bool = False
    
    # Fehler
    errors: List[str] = field(default_factory=list)


class TwelveFactorScaffolder:
    """12-Factor-konformer Scaffolder."""
    
    def __init__(self):
        self.catalog = EnhancedTemplateCatalog()
    
    def scaffold_program(
        self,
        plan: ProgramPlan,
        config: ScaffoldConfig
    ) -> ScaffoldResult:
        """Scaffolde 12-Factor-konformes Programm."""
        logger.info(f"Scaffolding {plan.program_type.value} program: {config.project_name}")
        
        result = ScaffoldResult(
            success=False,
            project_dir=config.project_dir
        )
        
        try:
            # Erstelle Projekt-Verzeichnis
            config.project_dir.mkdir(parents=True, exist_ok=True)
            
            # Hole Enhanced Template
            template = self.catalog.get_template_with_plan(plan)
            
            if not template:
                result.errors.append(f"Template not found: {plan.template_name}")
                return result
            
            # Generiere Basis-Struktur
            self._create_project_structure(config, template, result)
            
            # Generiere Hauptanwendung
            if plan.program_type == ProgramClassification.CLI:
                self._generate_cli_app(config, template, plan, result)
            elif plan.program_type == ProgramClassification.WEB_API:
                self._generate_web_api_app(config, template, plan, result)
            elif plan.program_type == ProgramClassification.WORKER:
                self._generate_worker_app(config, template, plan, result)
            elif plan.program_type == ProgramClassification.BATCH:
                self._generate_batch_app(config, template, plan, result)
            
            # Generiere Konfiguration
            self._generate_config_module(config, template, result)
            
            # Generiere Tests
            if config.generate_unit_tests:
                self._generate_unit_tests(config, template, plan, result)
            
            if config.generate_smoke_test:
                self._generate_smoke_test(config, template, plan, result)
            
            # Generiere Support-Dateien
            self._generate_requirements(config, template, result)
            
            if config.generate_dockerfile:
                self._generate_dockerfile(config, template, result)
            
            if config.generate_gitignore:
                self._generate_gitignore(config, result)
            
            if config.generate_readme:
                self._generate_readme(config, template, plan, result)
            
            # Validiere 12-Factor Compliance
            self._validate_twelve_factor_compliance(config, result)
            
            result.success = len(result.errors) == 0
            
            logger.info(f"Scaffolding completed: {len(result.files_created)} files created")
            
        except Exception as e:
            result.errors.append(f"Scaffolding failed: {e}")
            logger.error(f"Scaffolding failed: {e}")
        
        return result
    
    def _create_project_structure(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        result: ScaffoldResult
    ):
        """Erstelle Projekt-Struktur."""
        
        # Basis-Verzeichnisse
        directories = [
            config.project_dir / "src" / config.project_name,
            config.project_dir / "tests" / "unit",
            config.project_dir / "tests" / "integration",
            config.project_dir / "config",
            config.project_dir / "docs"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
        # __init__.py Dateien
        init_files = [
            config.project_dir / "src" / config.project_name / "__init__.py",
            config.project_dir / "tests" / "__init__.py",
            config.project_dir / "tests" / "unit" / "__init__.py",
            config.project_dir / "tests" / "integration" / "__init__.py"
        ]
        
        for init_file in init_files:
            init_file.write_text('"""Package initialization."""\\n')
            result.files_created.append(str(init_file.relative_to(config.project_dir)))
    
    def _generate_cli_app(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        plan: ProgramPlan,
        result: ScaffoldResult
    ):
        """Generiere CLI-Anwendung."""
        
        main_file = config.project_dir / "src" / config.project_name / "main.py"
        
        cli_code = f'''#!/usr/bin/env python3
"""
{config.project_name.replace('_', ' ').title()} CLI Application.

12-Factor compliant CLI tool with structured logging and environment-based configuration.
"""

import sys
import logging
import typer
from typing import Optional
from pathlib import Path

from .config import get_config
from .logger import setup_logging


app = typer.Typer(
    name="{config.project_name}",
    help="{config.project_name.replace('_', ' ').title()} CLI tool",
    add_completion=False
)


def setup_app():
    """Setup application."""
    config = get_config()
    setup_logging(config.log_level, config.log_format)
    return config


@app.command()
def version():
    """Show version information."""
    config = setup_app()
    typer.echo(f"{{config.app_name}} v{{config.version}}")


@app.command()
def health():
    """Perform health check."""
    try:
        config = setup_app()
        logger = logging.getLogger(__name__)
        
        # Basic health checks
        logger.info("Performing health check")
        
        # Check configuration
        if not config.is_valid():
            logger.error("Configuration validation failed")
            typer.echo("Health check failed: Invalid configuration", err=True)
            raise typer.Exit(code=1)
        
        # Check dependencies (if any)
        # Add your health checks here
        
        logger.info("Health check passed")
        typer.echo("Health check: OK")
        return True
        
    except Exception as e:
        logger.error(f"Health check failed: {{e}}")
        typer.echo(f"Health check failed: {{e}}", err=True)
        raise typer.Exit(code=1)


@app.command()
def run(
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="Input file path"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Perform dry run without changes")
):
    """Main application logic."""
    try:
        config = setup_app()
        logger = logging.getLogger(__name__)
        
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        logger.info(f"Starting {{config.app_name}} v{{config.version}}")
        
        if dry_run:
            logger.info("Dry run mode enabled")
        
        # Main application logic here
        logger.info("Processing...")
        
        # Example: Process input file
        if input_file:
            if not input_file.exists():
                logger.error(f"Input file not found: {{input_file}}")
                raise typer.Exit(code=2)
            
            logger.info(f"Processing input file: {{input_file}}")
            # Add your processing logic here
        
        # Example: Write output file
        if output_file:
            if not dry_run:
                logger.info(f"Writing output to: {{output_file}}")
                # Add your output logic here
            else:
                logger.info(f"Would write output to: {{output_file}}")
        
        logger.info("Processing completed successfully")
        typer.echo("Processing completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        typer.echo("Operation cancelled by user")
        raise typer.Exit(code=130)
    
    except Exception as e:
        logger.error(f"Application error: {{e}}")
        typer.echo(f"Error: {{e}}", err=True)
        raise typer.Exit(code=1)


def main():
    """Entry point."""
    try:
        app()
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except Exception as e:
        logging.error(f"Unexpected error: {{e}}")
        sys.exit(1)


if __name__ == "__main__":
    main()
'''
        
        main_file.write_text(cli_code)
        result.files_created.append(str(main_file.relative_to(config.project_dir)))
        
        # Health Check verfügbar
        result.health_check_available = True
        result.health_check_command = f"python -m src.{config.project_name}.main health"
        result.startup_command = f"python -m src.{config.project_name}.main run"
        result.can_start_locally = True
    
    def _generate_web_api_app(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        plan: ProgramPlan,
        result: ScaffoldResult
    ):
        """Generiere Web-API-Anwendung."""
        
        main_file = config.project_dir / "src" / config.project_name / "main.py"
        
        web_api_code = f'''#!/usr/bin/env python3
"""
{config.project_name.replace('_', ' ').title()} Web API.

12-Factor compliant web API with structured logging, health endpoints,
and environment-based configuration.
"""

import os
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import get_config
from .logger import setup_logging


def create_app():
    """Create Flask application."""
    app = Flask(__name__)
    
    # Trust proxy headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Setup configuration and logging
    config = get_config()
    setup_logging(config.log_level, config.log_format)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting {{config.app_name}} v{{config.version}}")
    
    @app.route('/')
    def root():
        """Root endpoint with API information."""
        return jsonify({{
            "service": config.app_name,
            "version": config.version,
            "status": "running",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "endpoints": {{
                "/": "GET - API information",
                "/health": "GET - Health check",
                "/ready": "GET - Readiness check",
                "/metrics": "GET - Metrics (if enabled)"
            }}
        }})
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        try:
            logger.debug("Health check requested")
            
            # Perform health checks
            health_status = perform_health_checks(config)
            
            if health_status["healthy"]:
                return jsonify({{
                    "status": "healthy",
                    "service": config.app_name,
                    "version": config.version,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "checks": health_status["checks"]
                }})
            else:
                return jsonify({{
                    "status": "unhealthy",
                    "service": config.app_name,
                    "version": config.version,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "checks": health_status["checks"]
                }}), 503
                
        except Exception as e:
            logger.error(f"Health check failed: {{e}}")
            return jsonify({{
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }}), 503
    
    @app.route('/ready')
    def ready():
        """Readiness check endpoint."""
        try:
            logger.debug("Readiness check requested")
            
            # Check if service is ready to serve traffic
            if config.is_valid():
                return jsonify({{
                    "status": "ready",
                    "service": config.app_name,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }})
            else:
                return jsonify({{
                    "status": "not_ready",
                    "reason": "Configuration invalid",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }}), 503
                
        except Exception as e:
            logger.error(f"Readiness check failed: {{e}}")
            return jsonify({{
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }}), 503
    
    @app.route('/metrics')
    def metrics():
        """Basic metrics endpoint."""
        if not config.metrics_enabled:
            return jsonify({{"error": "Metrics disabled"}}), 404
        
        # Basic metrics (extend as needed)
        return jsonify({{
            "service": config.app_name,
            "version": config.version,
            "uptime_seconds": get_uptime_seconds(),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }})
    
    # Example business endpoint
    @app.route('/api/v1/example', methods=['GET', 'POST'])
    def example_endpoint():
        """Example business logic endpoint."""
        try:
            logger.info(f"{{request.method}} /api/v1/example")
            
            if request.method == 'GET':
                return jsonify({{
                    "message": "Example endpoint",
                    "method": "GET",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }})
            
            elif request.method == 'POST':
                data = request.get_json() or {{}}
                
                # Example validation
                if 'name' not in data:
                    return jsonify({{"error": "Missing 'name' field"}}), 400
                
                # Example processing
                result = {{
                    "message": f"Hello, {{data['name']}}!",
                    "processed_at": datetime.utcnow().isoformat() + "Z"
                }}
                
                logger.info(f"Processed request for: {{data['name']}}")
                return jsonify(result)
        
        except Exception as e:
            logger.error(f"Error in example endpoint: {{e}}")
            return jsonify({{"error": "Internal server error"}}), 500
    
    @app.errorhandler(404)
    def not_found(error):
        """404 error handler."""
        return jsonify({{"error": "Not found"}}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """500 error handler."""
        logger.error(f"Internal server error: {{error}}")
        return jsonify({{"error": "Internal server error"}}), 500
    
    return app


def perform_health_checks(config):
    """Perform application health checks."""
    checks = {{}}
    healthy = True
    
    # Configuration check
    try:
        checks["config"] = {{"status": "ok" if config.is_valid() else "fail"}}
        if not config.is_valid():
            healthy = False
    except Exception as e:
        checks["config"] = {{"status": "fail", "error": str(e)}}
        healthy = False
    
    # Add more health checks as needed
    # Database connectivity, external services, etc.
    
    return {{"healthy": healthy, "checks": checks}}


def get_uptime_seconds():
    """Get application uptime in seconds."""
    # Simple implementation - in production, use proper uptime tracking
    return 0


def main():
    """Main entry point."""
    config = get_config()
    app = create_app()
    
    port = config.port
    debug = config.debug
    host = config.host
    
    logging.info(f"Starting server on {{host}}:{{port}}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
'''
        
        main_file.write_text(web_api_code)
        result.files_created.append(str(main_file.relative_to(config.project_dir)))
        
        # Health Check verfügbar
        result.health_check_available = True
        result.health_check_command = "curl -f http://localhost:5000/health"
        result.startup_command = f"python -m src.{config.project_name}.main"
        result.can_start_locally = True
    
    def _generate_worker_app(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        plan: ProgramPlan,
        result: ScaffoldResult
    ):
        """Generiere Worker-Anwendung."""
        
        main_file = config.project_dir / "src" / config.project_name / "main.py"
        
        worker_code = f'''#!/usr/bin/env python3
"""
{config.project_name.replace('_', ' ').title()} Background Worker.

12-Factor compliant background worker with structured logging,
health monitoring, and environment-based configuration.
"""

import sys
import time
import signal
import logging
from datetime import datetime
from threading import Event, Thread
from typing import Optional

from .config import get_config
from .logger import setup_logging


class WorkerApp:
    """Background worker application."""
    
    def __init__(self):
        self.config = get_config()
        setup_logging(self.config.log_level, self.config.log_format)
        self.logger = logging.getLogger(__name__)
        
        self.shutdown_event = Event()
        self.health_status = {{"healthy": True, "last_check": None}}
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {{signum}}, initiating graceful shutdown")
        self.shutdown_event.set()
    
    def health_check(self) -> bool:
        """Perform health check."""
        try:
            self.logger.debug("Performing health check")
            
            # Check configuration
            if not self.config.is_valid():
                self.health_status["healthy"] = False
                return False
            
            # Check worker status
            if self.shutdown_event.is_set():
                self.health_status["healthy"] = False
                return False
            
            # Add more health checks as needed
            
            self.health_status["healthy"] = True
            self.health_status["last_check"] = datetime.utcnow().isoformat() + "Z"
            
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {{e}}")
            self.health_status["healthy"] = False
            return False
    
    def process_task(self, task_data: dict) -> bool:
        """Process a single task."""
        try:
            self.logger.info(f"Processing task: {{task_data.get('id', 'unknown')}}")
            
            # Example task processing
            task_type = task_data.get('type', 'unknown')
            
            if task_type == 'example':
                # Simulate processing
                time.sleep(0.1)
                self.logger.info(f"Completed example task: {{task_data.get('id')}}")
                return True
            
            else:
                self.logger.warning(f"Unknown task type: {{task_type}}")
                return False
                
        except Exception as e:
            self.logger.error(f"Task processing failed: {{e}}")
            return False
    
    def run_health_monitor(self):
        """Run health monitoring in background."""
        while not self.shutdown_event.is_set():
            try:
                self.health_check()
                self.shutdown_event.wait(self.config.health_check_interval)
            except Exception as e:
                self.logger.error(f"Health monitoring error: {{e}}")
    
    def run(self):
        """Run the worker."""
        self.logger.info(f"Starting {{self.config.app_name}} v{{self.config.version}}")
        
        # Start health monitoring
        health_thread = Thread(target=self.run_health_monitor, daemon=True)
        health_thread.start()
        
        # Main worker loop
        while not self.shutdown_event.is_set():
            try:
                # Example: Poll for tasks (replace with your task source)
                task = self.get_next_task()
                
                if task:
                    self.process_task(task)
                else:
                    # No tasks available, wait
                    self.shutdown_event.wait(self.config.poll_interval)
                
            except Exception as e:
                self.logger.error(f"Worker loop error: {{e}}")
                self.shutdown_event.wait(5)  # Wait before retry
        
        self.logger.info("Worker shutdown completed")
    
    def get_next_task(self) -> Optional[dict]:
        """Get next task from queue (implement your task source)."""
        # Example implementation - replace with your task queue
        return None
    
    def get_status(self) -> dict:
        """Get worker status."""
        return {{
            "service": self.config.app_name,
            "version": self.config.version,
            "healthy": self.health_status["healthy"],
            "last_health_check": self.health_status["last_check"],
            "uptime_seconds": self.get_uptime_seconds(),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }}
    
    def get_uptime_seconds(self) -> int:
        """Get worker uptime."""
        # Simple implementation
        return 0


def main():
    """Main entry point."""
    try:
        worker = WorkerApp()
        worker.run()
        sys.exit(0)
    except KeyboardInterrupt:
        logging.info("Worker interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Worker failed: {{e}}")
        sys.exit(1)


if __name__ == "__main__":
    main()
'''
        
        main_file.write_text(worker_code)
        result.files_created.append(str(main_file.relative_to(config.project_dir)))
        
        # Health Check via Status-Methode
        result.health_check_available = True
        result.health_check_command = f"python -c \"from src.{config.project_name}.main import WorkerApp; w = WorkerApp(); print('OK' if w.health_check() else 'FAIL')\""
        result.startup_command = f"python -m src.{config.project_name}.main"
        result.can_start_locally = True
    
    def _generate_batch_app(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        plan: ProgramPlan,
        result: ScaffoldResult
    ):
        """Generiere Batch-Anwendung."""
        
        main_file = config.project_dir / "src" / config.project_name / "main.py"
        
        batch_code = f'''#!/usr/bin/env python3
"""
{config.project_name.replace('_', ' ').title()} Batch Job.

12-Factor compliant batch processing with structured logging,
checkpointing, and environment-based configuration.
"""

import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from .config import get_config
from .logger import setup_logging


class BatchProcessor:
    """Batch processing application."""
    
    def __init__(self):
        self.config = get_config()
        setup_logging(self.config.log_level, self.config.log_format)
        self.logger = logging.getLogger(__name__)
        
        self.processed_count = 0
        self.error_count = 0
        self.start_time = datetime.utcnow()
    
    def health_check(self) -> bool:
        """Perform health check."""
        try:
            self.logger.debug("Performing health check")
            
            # Check configuration
            if not self.config.is_valid():
                self.logger.error("Configuration validation failed")
                return False
            
            # Check dependencies
            # Add your dependency checks here
            
            self.logger.info("Health check passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {{e}}")
            return False
    
    def process_batch(
        self,
        input_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        dry_run: bool = False,
        checkpoint_interval: int = 100
    ) -> Dict[str, Any]:
        """Process batch job."""
        
        self.logger.info(f"Starting batch processing (dry_run={{dry_run}})")
        
        try:
            # Validate inputs
            if input_path and not input_path.exists():
                raise ValueError(f"Input path does not exist: {{input_path}}")
            
            # Initialize processing
            self.processed_count = 0
            self.error_count = 0
            
            # Example batch processing loop
            items_to_process = self.get_batch_items(input_path)
            total_items = len(items_to_process)
            
            self.logger.info(f"Found {{total_items}} items to process")
            
            for i, item in enumerate(items_to_process):
                try:
                    # Process single item
                    if not dry_run:
                        result = self.process_item(item)
                        if result:
                            self.processed_count += 1
                        else:
                            self.error_count += 1
                    else:
                        self.logger.debug(f"Would process item: {{item}}")
                        self.processed_count += 1
                    
                    # Checkpoint progress
                    if (i + 1) % checkpoint_interval == 0:
                        self.save_checkpoint(i + 1, total_items)
                        self.logger.info(f"Checkpoint: {{i + 1}}/{{total_items}} processed")
                
                except Exception as e:
                    self.logger.error(f"Error processing item {{item}}: {{e}}")
                    self.error_count += 1
            
            # Final results
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            
            results = {{
                "total_items": total_items,
                "processed_count": self.processed_count,
                "error_count": self.error_count,
                "duration_seconds": duration,
                "success_rate": self.processed_count / total_items if total_items > 0 else 0,
                "dry_run": dry_run
            }}
            
            # Write results
            if output_path and not dry_run:
                self.write_results(output_path, results)
            
            self.logger.info(f"Batch processing completed: {{results}}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Batch processing failed: {{e}}")
            raise
    
    def get_batch_items(self, input_path: Optional[Path]) -> list:
        """Get items to process."""
        # Example implementation - replace with your data source
        if input_path and input_path.exists():
            # Read from file
            return [f"item_{{i}}" for i in range(10)]  # Example
        else:
            # Generate example items
            return [f"example_item_{{i}}" for i in range(5)]
    
    def process_item(self, item: Any) -> bool:
        """Process a single item."""
        try:
            # Example processing logic
            self.logger.debug(f"Processing item: {{item}}")
            
            # Add your processing logic here
            # Return True for success, False for failure
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process item {{item}}: {{e}}")
            return False
    
    def save_checkpoint(self, current_position: int, total_items: int):
        """Save processing checkpoint."""
        checkpoint_data = {{
            "position": current_position,
            "total": total_items,
            "processed": self.processed_count,
            "errors": self.error_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }}
        
        # Save checkpoint (implement persistence as needed)
        self.logger.debug(f"Checkpoint saved: {{checkpoint_data}}")
    
    def write_results(self, output_path: Path, results: Dict[str, Any]):
        """Write processing results."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with output_path.open('w') as f:
                import json
                json.dump(results, f, indent=2)
            
            self.logger.info(f"Results written to: {{output_path}}")
            
        except Exception as e:
            self.logger.error(f"Failed to write results: {{e}}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="{config.project_name.replace('_', ' ').title()} Batch Job"
    )
    
    parser.add_argument(
        "--input", "-i",
        type=Path,
        help="Input file or directory path"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file path"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without making changes"
    )
    
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Perform health check and exit"
    )
    
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=100,
        help="Checkpoint interval (default: 100)"
    )
    
    args = parser.parse_args()
    
    try:
        processor = BatchProcessor()
        
        # Health check mode
        if args.health_check:
            if processor.health_check():
                print("Health check: OK")
                sys.exit(0)
            else:
                print("Health check: FAILED")
                sys.exit(1)
        
        # Regular processing
        results = processor.process_batch(
            input_path=args.input,
            output_path=args.output,
            dry_run=args.dry_run,
            checkpoint_interval=args.checkpoint_interval
        )
        
        # Exit with appropriate code
        if results["error_count"] == 0:
            sys.exit(0)  # Success
        elif results["processed_count"] > 0:
            sys.exit(2)  # Partial success
        else:
            sys.exit(1)  # Complete failure
    
    except KeyboardInterrupt:
        logging.info("Batch job interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        logging.error(f"Batch job failed: {{e}}")
        sys.exit(1)


if __name__ == "__main__":
    main()
'''
        
        main_file.write_text(batch_code)
        result.files_created.append(str(main_file.relative_to(config.project_dir)))
        
        # Health Check via --health-check Flag
        result.health_check_available = True
        result.health_check_command = f"python -m src.{config.project_name}.main --health-check"
        result.startup_command = f"python -m src.{config.project_name}.main"
        result.can_start_locally = True
    
    def _generate_config_module(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        result: ScaffoldResult
    ):
        """Generiere 12-Factor-konforme Konfiguration."""
        
        config_file = config.project_dir / "src" / config.project_name / "config.py"
        
        config_code = f'''"""
12-Factor compliant configuration module.

All configuration via environment variables with sensible defaults.
No secrets in code - all sensitive data via environment.
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AppConfig:
    """Application configuration."""
    
    # Application
    app_name: str = "{config.project_name}"
    version: str = "1.0.0"
    environment: str = "development"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Server (for web APIs)
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    
    # Worker settings
    poll_interval: int = 5
    health_check_interval: int = 30
    
    # Monitoring
    metrics_enabled: bool = True
    
    # Database (if needed)
    database_url: Optional[str] = None
    
    # External services
    redis_url: Optional[str] = None
    
    # Security
    secret_key: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Validate configuration."""
        try:
            # Basic validation
            if not self.app_name:
                return False
            
            if self.port < 1 or self.port > 65535:
                return False
            
            # Environment-specific validation
            if self.environment == "production":
                if not self.secret_key:
                    logging.error("SECRET_KEY required in production")
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"Configuration validation error: {{e}}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding secrets)."""
        data = {{
            "app_name": self.app_name,
            "version": self.version,
            "environment": self.environment,
            "log_level": self.log_level,
            "log_format": self.log_format,
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
            "metrics_enabled": self.metrics_enabled
        }}
        
        # Only include non-sensitive config
        if self.database_url:
            data["database_configured"] = True
        
        if self.redis_url:
            data["redis_configured"] = True
        
        return data


def get_config() -> AppConfig:
    """Get application configuration from environment."""
    
    return AppConfig(
        # Application
        app_name=os.getenv("APP_NAME", "{config.project_name}"),
        version=os.getenv("APP_VERSION", "1.0.0"),
        environment=os.getenv("ENVIRONMENT", "development"),
        
        # Logging
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_format=os.getenv("LOG_FORMAT", "json").lower(),
        
        # Server
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("DEBUG", "false").lower() == "true",
        
        # Worker
        poll_interval=int(os.getenv("POLL_INTERVAL", "5")),
        health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "30")),
        
        # Monitoring
        metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
        
        # External services (secrets via environment only)
        database_url=os.getenv("DATABASE_URL"),
        redis_url=os.getenv("REDIS_URL"),
        secret_key=os.getenv("SECRET_KEY")
    )


def validate_required_env_vars():
    """Validate required environment variables."""
    required_vars = []
    
    # Add required environment variables based on your needs
    # Example:
    # if os.getenv("ENVIRONMENT") == "production":
    #     required_vars.extend(["SECRET_KEY", "DATABASE_URL"])
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {{', '.join(missing_vars)}}")
'''
        
        config_file.write_text(config_code)
        result.files_created.append(str(config_file.relative_to(config.project_dir)))
    
    def _generate_logger_module(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        result: ScaffoldResult
    ):
        """Generiere strukturiertes Logging-Modul."""
        
        logger_file = config.project_dir / "src" / config.project_name / "logger.py"
        
        logger_code = '''"""
Structured logging setup for 12-Factor compliance.

Provides JSON and human-readable logging formats.
"""

import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname", 
                          "filename", "module", "lineno", "funcName", "created", 
                          "msecs", "relativeCreated", "thread", "threadName", 
                          "processName", "process", "exc_info", "exc_text", "stack_info"]:
                log_entry[key] = value
        
        return json.dumps(log_entry)


class HumanFormatter(logging.Formatter):
    """Human-readable log formatter."""
    
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def setup_logging(level: str = "INFO", format_type: str = "json"):
    """Setup structured logging."""
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter
    if format_type.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = HumanFormatter()
    
    handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
'''
        
        logger_file.write_text(logger_code)
        result.files_created.append(str(logger_file.relative_to(config.project_dir)))
    
    def _generate_unit_tests(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        plan: ProgramPlan,
        result: ScaffoldResult
    ):
        """Generiere Unit-Tests."""
        
        # Generiere Logger-Modul erst
        self._generate_logger_module(config, template, result)
        
        test_file = config.project_dir / "tests" / "unit" / f"test_{config.project_name}.py"
        
        test_code = f'''"""
Unit tests for {config.project_name}.

Tests basic functionality and 12-Factor compliance.
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.{config.project_name}.config import AppConfig, get_config
from src.{config.project_name}.main import *


class TestConfig:
    """Test configuration module."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = AppConfig()
        
        assert config.app_name == "{config.project_name}"
        assert config.version == "1.0.0"
        assert config.environment == "development"
        assert config.log_level == "INFO"
        assert config.port == 5000
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = AppConfig()
        assert config.is_valid()
        
        # Invalid port
        config = AppConfig(port=0)
        assert not config.is_valid()
        
        config = AppConfig(port=70000)
        assert not config.is_valid()
    
    @patch.dict(os.environ, {{"PORT": "8080", "LOG_LEVEL": "DEBUG"}})
    def test_env_config(self):
        """Test configuration from environment."""
        config = get_config()
        
        assert config.port == 8080
        assert config.log_level == "DEBUG"
    
    def test_config_to_dict(self):
        """Test configuration serialization."""
        config = AppConfig()
        data = config.to_dict()
        
        assert isinstance(data, dict)
        assert "app_name" in data
        assert "secret_key" not in data  # Secrets excluded


class TestApplication:
    """Test main application."""
    
    def test_health_check(self):
        """Test health check functionality."""
        # This test depends on the program type
        pass  # Implement based on your application type
    
    def test_twelve_factor_compliance(self):
        """Test 12-Factor compliance."""
        config = get_config()
        
        # Factor 3: Config via environment
        assert hasattr(config, 'app_name')
        
        # Factor 11: Logs as event streams
        # (Tested by checking structured logging setup)
        
        # Factor 12: Admin processes
        # (Health check endpoint/command available)
'''

        if plan.program_type == ProgramClassification.WEB_API:
            test_code += f'''

class TestWebAPI:
    """Test Web API specific functionality."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        return create_app()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        with app.test_client() as client:
            yield client
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get('/')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert "service" in data
        assert "version" in data
    
    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get('/health')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data["status"] == "healthy"
    
    def test_ready_endpoint(self, client):
        """Test readiness endpoint."""
        response = client.get('/ready')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data["status"] == "ready"
'''

        elif plan.program_type == ProgramClassification.CLI:
            test_code += f'''

class TestCLI:
    """Test CLI specific functionality."""
    
    def test_health_command(self):
        """Test health command."""
        # Mock the health check
        with patch('src.{config.project_name}.main.setup_app') as mock_setup:
            mock_config = MagicMock()
            mock_config.is_valid.return_value = True
            mock_setup.return_value = mock_config
            
            # Test would require running the CLI command
            # This is a placeholder for actual CLI testing
            assert True
'''

        test_code += '''

class TestLogging:
    """Test structured logging."""
    
    def test_json_formatter(self):
        """Test JSON log formatting."""
        from src.{}.logger import JSONFormatter
        
        formatter = JSONFormatter()
        
        # Create test log record
        import logging
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        data = json.loads(formatted)
        
        assert "timestamp" in data
        assert "level" in data
        assert "message" in data
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
'''.format(config.project_name)
        
        test_file.write_text(test_code)
        result.files_created.append(str(test_file.relative_to(config.project_dir)))
        result.unit_tests_generated = True
        result.test_command = "pytest tests/unit/ -v"
    
    def _generate_smoke_test(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        plan: ProgramPlan,
        result: ScaffoldResult
    ):
        """Generiere Smoke-Test."""
        
        smoke_test_file = config.project_dir / "tests" / "test_smoke.py"
        
        smoke_test_code = f'''"""
Smoke tests for {config.project_name}.

Basic integration tests to verify the application starts and responds.
"""

import pytest
import subprocess
import time
import requests
from pathlib import Path


class TestSmoke:
    """Smoke tests."""
    
    def test_application_imports(self):
        """Test that application modules can be imported."""
        try:
            import src.{config.project_name}.main
            import src.{config.project_name}.config
            import src.{config.project_name}.logger
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {{e}}")
    
    def test_config_loads(self):
        """Test that configuration loads without errors."""
        from src.{config.project_name}.config import get_config
        
        config = get_config()
        assert config is not None
        assert config.is_valid()
'''

        if plan.program_type == ProgramClassification.WEB_API:
            smoke_test_code += '''
    
    def test_health_endpoint_responds(self):
        """Test that health endpoint responds (requires running server)."""
        # This test assumes the server is running on localhost:5000
        # In a real test environment, you would start the server in a fixture
        
        try:
            response = requests.get("http://localhost:5000/health", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert "status" in data
            
        except requests.RequestException:
            pytest.skip("Server not running for smoke test")
'''

        elif plan.program_type == ProgramClassification.CLI:
            smoke_test_code += f'''
    
    def test_cli_health_command(self):
        """Test CLI health command."""
        try:
            result = subprocess.run([
                "python", "-m", "src.{config.project_name}.main", "health"
            ], capture_output=True, text=True, timeout=10)
            
            # Should exit with code 0 for healthy
            assert result.returncode == 0
            assert "Health check: OK" in result.stdout or "OK" in result.stdout
            
        except subprocess.TimeoutExpired:
            pytest.fail("Health check command timed out")
        except Exception as e:
            pytest.fail(f"Health check failed: {{e}}")
    
    def test_cli_version_command(self):
        """Test CLI version command."""
        try:
            result = subprocess.run([
                "python", "-m", "src.{config.project_name}.main", "version"
            ], capture_output=True, text=True, timeout=10)
            
            assert result.returncode == 0
            assert "1.0.0" in result.stdout
            
        except Exception as e:
            pytest.fail(f"Version command failed: {{e}}")
'''

        elif plan.program_type == ProgramClassification.BATCH:
            smoke_test_code += f'''
    
    def test_batch_health_check(self):
        """Test batch job health check."""
        try:
            result = subprocess.run([
                "python", "-m", "src.{config.project_name}.main", "--health-check"
            ], capture_output=True, text=True, timeout=10)
            
            assert result.returncode == 0
            assert "Health check: OK" in result.stdout
            
        except Exception as e:
            pytest.fail(f"Batch health check failed: {{e}}")
    
    def test_batch_dry_run(self):
        """Test batch job dry run."""
        try:
            result = subprocess.run([
                "python", "-m", "src.{config.project_name}.main", "--dry-run"
            ], capture_output=True, text=True, timeout=30)
            
            # Dry run should complete successfully
            assert result.returncode == 0
            
        except Exception as e:
            pytest.fail(f"Batch dry run failed: {{e}}")
'''

        smoke_test_code += '''

    def test_twelve_factor_compliance_smoke(self):
        """Smoke test for 12-Factor compliance."""
        from src.{}.config import get_config
        
        config = get_config()
        
        # Factor 3: Config stored in environment
        import os
        original_port = os.environ.get("PORT")
        os.environ["PORT"] = "9999"
        
        try:
            new_config = get_config()
            assert new_config.port == 9999
        finally:
            if original_port:
                os.environ["PORT"] = original_port
            elif "PORT" in os.environ:
                del os.environ["PORT"]
        
        # Factor 11: Logs as event streams (JSON format available)
        from src.{}.logger import JSONFormatter
        formatter = JSONFormatter()
        assert formatter is not None
'''.format(config.project_name, config.project_name)
        
        smoke_test_file.write_text(smoke_test_code)
        result.files_created.append(str(smoke_test_file.relative_to(config.project_dir)))
        result.smoke_test_generated = True
    
    def _generate_requirements(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        result: ScaffoldResult
    ):
        """Generiere requirements.txt."""
        
        requirements_file = config.project_dir / "requirements.txt"
        
        # Basis-Requirements basierend auf Template
        requirements = []
        
        if template.base_template.program_type.value == "cli":
            requirements.extend([
                "typer>=0.9.0",
                "click>=8.0.0"
            ])
        elif template.base_template.program_type.value == "web-api":
            requirements.extend([
                "Flask>=2.3.0",
                "Werkzeug>=2.3.0",
                "requests>=2.31.0"
            ])
        elif template.base_template.program_type.value == "worker":
            requirements.extend([
                "celery>=5.3.0",
                "redis>=4.5.0"
            ])
        
        # Test-Requirements
        requirements.extend([
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0"
        ])
        
        requirements_content = "\\n".join(requirements) + "\\n"
        requirements_file.write_text(requirements_content)
        result.files_created.append(str(requirements_file.relative_to(config.project_dir)))
    
    def _generate_dockerfile(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        result: ScaffoldResult
    ):
        """Generiere 12-Factor-konformes Dockerfile."""
        
        dockerfile = config.project_dir / "Dockerfile"
        
        dockerfile_content = f'''# Multi-stage build for {config.project_name}
FROM python:{template.runtime.version}-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:{template.runtime.version}-slim as runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN adduser --disabled-password --gecos '' {template.container.user_name}

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/{template.container.user_name}/.local

# Copy application code
COPY src/ src/
COPY config/ config/

# Set ownership
RUN chown -R {template.container.user_name}:{template.container.user_name} /app

# Switch to non-root user
USER {template.container.user_name}

# Update PATH
ENV PATH=/home/{template.container.user_name}/.local/bin:$PATH

# Set Python path
ENV PYTHONPATH=/app

# 12-Factor: Config via environment
ENV ENVIRONMENT=production
ENV LOG_FORMAT=json
ENV LOG_LEVEL=INFO

# Expose port (if applicable)'''

        if template.container.exposed_ports:
            dockerfile_content += f"\\nEXPOSE {template.container.exposed_ports[0]}"

        dockerfile_content += f'''

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD {template.runtime.health_check_command} || exit 1

# Start application
CMD ["python", "-m", "src.{config.project_name}.main"]
'''
        
        dockerfile.write_text(dockerfile_content)
        result.files_created.append(str(dockerfile.relative_to(config.project_dir)))
    
    def _generate_gitignore(self, config: ScaffoldConfig, result: ScaffoldResult):
        """Generiere .gitignore."""
        
        gitignore_file = config.project_dir / ".gitignore"
        
        gitignore_content = '''# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# celery beat schedule file
celerybeat-schedule

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Application specific
config/local.py
*.pid
'''
        
        gitignore_file.write_text(gitignore_content)
        result.files_created.append(str(gitignore_file.relative_to(config.project_dir)))
    
    def _generate_readme(
        self,
        config: ScaffoldConfig,
        template: EnhancedProgramTemplate,
        plan: ProgramPlan,
        result: ScaffoldResult
    ):
        """Generiere README.md."""
        
        readme_file = config.project_dir / "README.md"
        
        program_type_desc = {
            ProgramClassification.CLI: "command-line tool",
            ProgramClassification.WEB_API: "web API service",
            ProgramClassification.WORKER: "background worker",
            ProgramClassification.BATCH: "batch processing job"
        }
        
        readme_content = f'''# {config.project_name.replace('_', ' ').title()}

A 12-Factor compliant {program_type_desc.get(plan.program_type, 'application')} built with Python.

## Features

- ✅ 12-Factor App compliance
- ✅ Environment-based configuration
- ✅ Structured JSON logging
- ✅ Health check endpoints/commands
- ✅ Container-ready with multi-stage builds
- ✅ Non-root user execution
- ✅ Comprehensive test suite

## Quick Start

### Local Development

1. **Clone and setup:**
   ```bash
   cd {config.project_name}
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   {result.startup_command}
   ```

3. **Health check:**
   ```bash
   {result.health_check_command}
   ```

### Docker

1. **Build container:**
   ```bash
   docker build -t {config.project_name}:latest .
   ```

2. **Run container:**
   ```bash'''

        if plan.program_type == ProgramClassification.WEB_API:
            readme_content += f'''
   docker run -p 5000:5000 -e ENVIRONMENT=production {config.project_name}:latest
   ```

3. **Test health:**
   ```bash
   curl http://localhost:5000/health
   ```'''
        else:
            readme_content += f'''
   docker run -e ENVIRONMENT=production {config.project_name}:latest
   ```'''

        readme_content += f'''

## Configuration

All configuration via environment variables (12-Factor compliant):

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Runtime environment |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` | Log format (json/human) |'''

        if plan.program_type == ProgramClassification.WEB_API:
            readme_content += '''
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `5000` | Server port |
| `DEBUG` | `false` | Debug mode |'''

        readme_content += '''

### Secrets

All secrets must be provided via environment variables:

- `SECRET_KEY` - Application secret key (required in production)
- `DATABASE_URL` - Database connection string (if applicable)
- `REDIS_URL` - Redis connection string (if applicable)

## Testing

```bash
# Run unit tests
pytest tests/unit/ -v

# Run smoke tests
pytest tests/test_smoke.py -v

# Run all tests with coverage
pytest --cov=src --cov-report=html
```

## Health Checks'''

        if plan.program_type == ProgramClassification.WEB_API:
            readme_content += '''

- **Health:** `GET /health` - Application health status
- **Readiness:** `GET /ready` - Service readiness
- **Metrics:** `GET /metrics` - Basic metrics (if enabled)'''
        elif plan.program_type == ProgramClassification.CLI:
            readme_content += '''

- **Health:** `python -m src.{}.main health`
- **Version:** `python -m src.{}.main version`'''.format(config.project_name, config.project_name)
        elif plan.program_type == ProgramClassification.BATCH:
            readme_content += '''

- **Health:** `python -m src.{}.main --health-check`
- **Dry Run:** `python -m src.{}.main --dry-run`'''.format(config.project_name, config.project_name)

        readme_content += f'''

## 12-Factor Compliance

This application follows the [12-Factor App](https://12factor.net/) methodology:

1. ✅ **Codebase:** Single codebase tracked in version control
2. ✅ **Dependencies:** Explicitly declared via requirements.txt
3. ✅ **Config:** Configuration via environment variables
4. ✅ **Backing Services:** External services via connection strings
5. ✅ **Build/Release/Run:** Strict separation of stages
6. ✅ **Processes:** Stateless, share-nothing processes
7. ✅ **Port Binding:** Self-contained service export
8. ✅ **Concurrency:** Horizontal scaling ready
9. ✅ **Disposability:** Fast startup and graceful shutdown
10. ✅ **Dev/Prod Parity:** Development matches production
11. ✅ **Logs:** Structured logs as event streams
12. ✅ **Admin Processes:** Health checks and admin commands

## Development

### Project Structure

```
{config.project_name}/
├── src/{config.project_name}/          # Application code
│   ├── main.py                         # Main application
│   ├── config.py                       # Configuration
│   └── logger.py                       # Structured logging
├── tests/                              # Test suite
│   ├── unit/                          # Unit tests
│   └── test_smoke.py                  # Smoke tests
├── config/                            # Configuration files
├── Dockerfile                         # Container definition
├── requirements.txt                   # Dependencies
└── README.md                          # This file
```

### Contributing

1. Follow 12-Factor principles
2. Add tests for new features
3. Ensure health checks pass
4. Update documentation

## License

[Add your license here]
'''
        
        readme_file.write_text(readme_content)
        result.files_created.append(str(readme_file.relative_to(config.project_dir)))
    
    def _validate_twelve_factor_compliance(
        self,
        config: ScaffoldConfig,
        result: ScaffoldResult
    ):
        """Validiere 12-Factor-Compliance."""
        
        violations = []
        
        # Factor 3: Config via Environment
        config_file = config.project_dir / "src" / config.project_name / "config.py"
        if config_file.exists():
            config_content = config_file.read_text()
            if "os.getenv" not in config_content:
                violations.append("Config not loaded from environment variables")
            if "SECRET_KEY" in config_content and "os.getenv" not in config_content:
                violations.append("Secrets hardcoded in configuration")
        
        # Factor 11: Structured Logs
        logger_file = config.project_dir / "src" / config.project_name / "logger.py"
        if logger_file.exists():
            logger_content = logger_file.read_text()
            if "JSONFormatter" not in logger_content:
                violations.append("Structured logging not implemented")
        
        # Factor 12: Health Checks
        if not result.health_check_available:
            violations.append("Health check not available")
        
        # Dockerfile compliance
        dockerfile = config.project_dir / "Dockerfile"
        if dockerfile.exists():
            dockerfile_content = dockerfile.read_text()
            if "USER" not in dockerfile_content:
                violations.append("Container runs as root user")
            if "HEALTHCHECK" not in dockerfile_content:
                violations.append("Container health check not defined")
        
        result.compliance_violations = violations
        result.twelve_factor_compliant = len(violations) == 0


# Convenience Functions
def scaffold_twelve_factor_program(
    plan: ProgramPlan,
    project_name: str,
    project_dir: Path
) -> ScaffoldResult:
    """
    Scaffold 12-Factor-konformes Programm.
    
    Args:
        plan: Program-Plan
        project_name: Projekt-Name
        project_dir: Projekt-Verzeichnis
        
    Returns:
        Scaffold-Ergebnis
    """
    scaffolder = TwelveFactorScaffolder()
    
    config = ScaffoldConfig(
        project_name=project_name,
        project_dir=project_dir,
        enforce_twelve_factor=True
    )
    
    return scaffolder.scaffold_program(plan, config)


if __name__ == "__main__":
    # Demo
    def demo_twelve_factor_scaffolder():
        print("🏗️ 12-Factor Scaffolder Demo:")
        
        from .enhanced_planner import create_deterministic_plan
        import tempfile
        
        # Test verschiedene Programmtypen
        test_cases = [
            ("CLI Tool", "Create a CLI tool to process files"),
            ("Web API", "Build a REST API for user management"),
            ("Worker", "Create a background worker for image processing"),
            ("Batch Job", "Build a batch job for data migration")
        ]
        
        scaffolder = TwelveFactorScaffolder()
        
        for case_name, prompt in test_cases:
            print(f"\\n🧪 Testing {case_name}:")
            
            # Erstelle Plan
            plan = create_deterministic_plan(prompt, seed=42)
            
            print(f"  Program type: {plan.program_type.value}")
            
            # Scaffold in temporärem Verzeichnis
            with tempfile.TemporaryDirectory() as temp_dir:
                project_dir = Path(temp_dir) / "test_project"
                
                config = ScaffoldConfig(
                    project_name="test_app",
                    project_dir=project_dir
                )
                
                result = scaffolder.scaffold_program(plan, config)
                
                print(f"  ✓ Success: {result.success}")
                print(f"  ✓ Files created: {len(result.files_created)}")
                print(f"  ✓ 12-Factor compliant: {result.twelve_factor_compliant}")
                print(f"  ✓ Health check available: {result.health_check_available}")
                print(f"  ✓ Unit tests: {result.unit_tests_generated}")
                print(f"  ✓ Smoke test: {result.smoke_test_generated}")
                print(f"  ✓ Can start locally: {result.can_start_locally}")
                
                if result.compliance_violations:
                    print(f"  ⚠️ Violations: {result.compliance_violations}")
                
                if result.errors:
                    print(f"  ❌ Errors: {result.errors}")
        
        return True
    
    # Führe Demo aus
    try:
        result = demo_twelve_factor_scaffolder()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
