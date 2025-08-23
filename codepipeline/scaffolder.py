"""
Programm-Scaffolder mit 12-Factor-App Policies.

Erzeugt aus Template + Plan lauffähige Skelette mit:
- Einstiegspunkt
- Routing oder Command-Parsing
- Health-Check
- Strukturierte Logs
- Einfache Tests
- Config-Stub

Erzwingt 12-Factor-Prinzipien:
- Keine fest verdrahteten Secrets
- Keine absoluten Pfade
- Environment-basierte Konfiguration
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .template_catalog import ProgramTemplate, ProgramType, Subsystem, get_catalog


@dataclass
class ScaffoldPlan:
    """Plan für das Scaffolding."""
    project_name: str
    template_name: str
    output_dir: str
    
    # Optionale Konfiguration
    port: Optional[int] = None
    database_url_env: str = "DATABASE_URL"
    log_level_env: str = "LOG_LEVEL"
    config_file_env: str = "CONFIG_FILE"
    
    # 12-Factor Enforcement
    enforce_twelve_factor: bool = True
    
    # Zusätzliche Features
    include_docker: bool = True
    include_tests: bool = True
    include_health_check: bool = True


class TwelveFactorValidator:
    """Validator für 12-Factor-App Prinzipien."""
    
    @staticmethod
    def validate_config(content: str) -> List[str]:
        """Validiere Konfiguration gegen 12-Factor-Prinzipien."""
        violations = []
        
        # Prüfe auf hartcodierte Secrets
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']*["\']',
            r'api_key\s*=\s*["\'][^"\']*["\']',
            r'secret\s*=\s*["\'][^"\']*["\']',
            r'token\s*=\s*["\'][^"\']*["\']'
        ]
        
        import re
        for pattern in secret_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"Hardcoded secret detected: {pattern}")
        
        # Prüfe auf absolute Pfade
        if re.search(r'["\'][/\\][^"\']*["\']', content):
            violations.append("Absolute paths detected - use relative paths or environment variables")
        
        # Prüfe auf fehlende Environment-Variablen
        if 'os.environ' not in content and 'getenv' not in content:
            violations.append("No environment variable usage detected - consider 12-Factor config")
        
        return violations
    
    @staticmethod
    def validate_dockerfile(content: str) -> List[str]:
        """Validiere Dockerfile gegen 12-Factor-Prinzipien."""
        violations = []
        
        # Prüfe auf hardcoded values
        if 'COPY config.yaml' in content:
            violations.append("Hardcoded config file in Dockerfile - use environment variables")
        
        # Prüfe auf non-root user
        if 'USER' not in content:
            violations.append("Dockerfile should run as non-root user")
        
        return violations


class ProgramScaffolder:
    """Scaffolder für Programme basierend auf Templates."""
    
    def __init__(self):
        self.catalog = get_catalog()
        self.validator = TwelveFactorValidator()
    
    def scaffold(self, plan: ScaffoldPlan) -> Dict[str, Any]:
        """
        Erzeuge Programm-Skelett aus Plan.
        
        Args:
            plan: Scaffolding-Plan
            
        Returns:
            Dict mit Ergebnis und generierten Dateien
        """
        # Hole Template
        template = self.catalog.get_template(plan.template_name)
        if not template:
            return {
                'success': False,
                'error': f'Template {plan.template_name} not found'
            }
        
        # Erstelle Output-Verzeichnis
        output_path = Path(plan.output_dir) / plan.project_name
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generiere Dateien basierend auf Template-Typ
        generated_files = []
        
        try:
            if template.program_type == ProgramType.CLI:
                generated_files.extend(self._scaffold_cli(template, plan, output_path))
            elif template.program_type == ProgramType.WEB_API:
                generated_files.extend(self._scaffold_web_api(template, plan, output_path))
            elif template.program_type == ProgramType.WORKER:
                generated_files.extend(self._scaffold_worker(template, plan, output_path))
            elif template.program_type == ProgramType.BATCH_JOB:
                generated_files.extend(self._scaffold_batch_job(template, plan, output_path))
            
            # Gemeinsame Dateien
            generated_files.extend(self._scaffold_common(template, plan, output_path))
            
            # 12-Factor Validation
            violations = []
            if plan.enforce_twelve_factor:
                violations = self._validate_twelve_factor(output_path)
            
            return {
                'success': True,
                'project_path': str(output_path),
                'generated_files': generated_files,
                'twelve_factor_violations': violations,
                'template_used': plan.template_name
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'project_path': str(output_path)
            }
    
    def _scaffold_cli(self, template: ProgramTemplate, plan: ScaffoldPlan, output_path: Path) -> List[str]:
        """Scaffolde CLI-Programm."""
        files = []
        
        # Main CLI Entry Point
        main_py = output_path / "main.py"
        main_content = f'''#!/usr/bin/env python3
"""
{plan.project_name} - CLI Tool

Generated from template: {template.name}
"""

import os
import sys
import argparse
import logging
from pathlib import Path


def setup_logging():
    """Setup structured logging."""
    log_level = os.getenv("{plan.log_level_env}", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def load_config():
    """Load configuration from environment or config file."""
    config = {{}}
    
    # Load from environment
    config["log_level"] = os.getenv("{plan.log_level_env}", "INFO")
    config["config_file"] = os.getenv("{plan.config_file_env}")
    
    # Load from config file if specified
    if config["config_file"] and Path(config["config_file"]).exists():
        # TODO: Implement config file loading
        pass
    
    return config


def main():
    """Main CLI entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(description="{plan.project_name} CLI")
    parser.add_argument("--version", action="version", version="1.0.0")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    # Add your CLI arguments here
    parser.add_argument("input", help="Input file or data")
    parser.add_argument("--output", "-o", help="Output file")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    config = load_config()
    logger.info(f"Starting {{plan.project_name}} with config: {{config}}")
    
    try:
        # Your CLI logic here
        logger.info(f"Processing input: {{args.input}}")
        
        if args.output:
            logger.info(f"Output will be written to: {{args.output}}")
        
        # TODO: Implement your CLI logic
        print("CLI execution completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"CLI execution failed: {{e}}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
'''
        main_py.write_text(main_content)
        files.append("main.py")
        
        return files
    
    def _scaffold_web_api(self, template: ProgramTemplate, plan: ScaffoldPlan, output_path: Path) -> List[str]:
        """Scaffolde Web-API-Programm."""
        files = []
        
        # FastAPI App
        app_py = output_path / "app.py"
        port = plan.port or 8000
        
        app_content = f'''"""
{plan.project_name} - Web API

Generated from template: {template.name}
"""

import os
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


# Setup structured logging
def setup_logging():
    """Setup structured logging."""
    log_level = os.getenv("{plan.log_level_env}", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


# Initialize app
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="{plan.project_name}",
    description="Generated Web API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {{"message": "Welcome to {plan.project_name}", "version": "1.0.0"}}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {{
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "{plan.project_name}",
        "version": "1.0.0"
    }}


@app.get("/api/v1/example")
async def example_endpoint():
    """Example API endpoint."""
    logger.info("Example endpoint called")
    return {{
        "data": "This is example data",
        "timestamp": datetime.utcnow().isoformat()
    }}


@app.post("/api/v1/example")
async def create_example(data: dict):
    """Example POST endpoint."""
    logger.info(f"Creating example with data: {{data}}")
    
    # TODO: Implement your business logic here
    
    return {{
        "message": "Example created successfully",
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }}


def load_config():
    """Load configuration from environment."""
    return {{
        "port": int(os.getenv("PORT", "{port}")),
        "host": os.getenv("HOST", "0.0.0.0"),
        "log_level": os.getenv("{plan.log_level_env}", "INFO"),
        "database_url": os.getenv("{plan.database_url_env}"),
    }}


if __name__ == "__main__":
    config = load_config()
    logger.info(f"Starting {plan.project_name} API with config: {{config}}")
    
    uvicorn.run(
        "app:app",
        host=config["host"],
        port=config["port"],
        log_level=config["log_level"].lower(),
        reload=os.getenv("RELOAD", "false").lower() == "true"
    )
'''
        app_py.write_text(app_content)
        files.append("app.py")
        
        # Requirements
        requirements_txt = output_path / "requirements.txt"
        requirements_content = """fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
"""
        requirements_txt.write_text(requirements_content)
        files.append("requirements.txt")
        
        return files
    
    def _scaffold_worker(self, template: ProgramTemplate, plan: ScaffoldPlan, output_path: Path) -> List[str]:
        """Scaffolde Worker-Programm."""
        files = []
        
        # Worker Main
        worker_py = output_path / "worker.py"
        worker_content = f'''"""
{plan.project_name} - Background Worker

Generated from template: {template.name}
"""

import os
import time
import logging
import signal
import sys
from datetime import datetime
from typing import Any, Dict


class WorkerHealth:
    """Worker health check."""
    
    def __init__(self):
        self.is_healthy = True
        self.last_heartbeat = datetime.utcnow()
    
    def check(self) -> Dict[str, Any]:
        """Check worker health."""
        return {{
            "status": "healthy" if self.is_healthy else "unhealthy",
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "service": "{plan.project_name}",
            "version": "1.0.0"
        }}
    
    def heartbeat(self):
        """Update heartbeat."""
        self.last_heartbeat = datetime.utcnow()


class BackgroundWorker:
    """Background worker for processing tasks."""
    
    def __init__(self):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        self.health = WorkerHealth()
        self.running = False
        self.config = self.load_config()
    
    def setup_logging(self):
        """Setup structured logging."""
        log_level = os.getenv("{plan.log_level_env}", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from environment."""
        return {{
            "queue_url": os.getenv("QUEUE_URL"),
            "worker_concurrency": int(os.getenv("WORKER_CONCURRENCY", "1")),
            "log_level": os.getenv("{plan.log_level_env}", "INFO"),
            "health_check_port": int(os.getenv("HEALTH_CHECK_PORT", "8080")),
        }}
    
    def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a single task.
        
        Args:
            task: Task data to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Processing task: {{task.get('id', 'unknown')}}")
            
            # TODO: Implement your task processing logic here
            # Example: 
            # - Validate task data
            # - Perform business logic
            # - Update database
            # - Send notifications
            
            time.sleep(1)  # Simulate work
            
            self.logger.info(f"Task completed: {{task.get('id', 'unknown')}}")
            return True
            
        except Exception as e:
            self.logger.error(f"Task processing failed: {{e}}")
            return False
    
    def get_next_task(self) -> Dict[str, Any] | None:
        """
        Get next task from queue.
        
        Returns:
            Task data or None if no tasks available
        """
        # TODO: Implement queue integration
        # Example implementations:
        # - Redis/RQ
        # - Celery
        # - AWS SQS
        # - RabbitMQ
        
        # Mock task for demo
        return {{
            "id": f"task-{{int(time.time())}}", 
            "type": "example",
            "data": {{"message": "Hello, World!"}}
        }}
    
    def run(self):
        """Run worker main loop."""
        self.running = True
        self.logger.info(f"Starting {{plan.project_name}} worker")
        
        while self.running:
            try:
                self.health.heartbeat()
                
                # Get next task
                task = self.get_next_task()
                
                if task:
                    success = self.process_task(task)
                    if not success:
                        self.logger.warning(f"Task processing failed: {{task.get('id')}}")
                else:
                    # No tasks available, wait a bit
                    time.sleep(5)
                
            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal")
                break
            except Exception as e:
                self.logger.error(f"Worker error: {{e}}")
                time.sleep(10)  # Wait before retrying
        
        self.logger.info("Worker shutdown complete")
    
    def stop(self):
        """Stop worker."""
        self.running = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {{signum}}, shutting down...")
    worker.stop()


if __name__ == "__main__":
    # Setup signal handlers
    worker = BackgroundWorker()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        worker.run()
    except Exception as e:
        worker.logger.error(f"Worker failed: {{e}}")
        sys.exit(1)
'''
        worker_py.write_text(worker_content)
        files.append("worker.py")
        
        return files
    
    def _scaffold_batch_job(self, template: ProgramTemplate, plan: ScaffoldPlan, output_path: Path) -> List[str]:
        """Scaffolde Batch-Job-Programm."""
        files = []
        
        # Batch Job Main
        batch_py = output_path / "batch_job.py"
        batch_content = f'''"""
{plan.project_name} - Batch Job

Generated from template: {template.name}
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class BatchJob:
    """Batch processing job."""
    
    def __init__(self):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        self.config = self.load_config()
    
    def setup_logging(self):
        """Setup structured logging."""
        log_level = os.getenv("{plan.log_level_env}", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from environment."""
        return {{
            "batch_size": int(os.getenv("BATCH_SIZE", "100")),
            "input_path": os.getenv("INPUT_PATH", "/app/input"),
            "output_path": os.getenv("OUTPUT_PATH", "/app/output"),
            "log_level": os.getenv("{plan.log_level_env}", "INFO"),
            "database_url": os.getenv("{plan.database_url_env}"),
        }}
    
    def validate_inputs(self) -> bool:
        """Validate input requirements."""
        input_path = Path(self.config["input_path"])
        
        if not input_path.exists():
            self.logger.error(f"Input path does not exist: {{input_path}}")
            return False
        
        if not input_path.is_dir():
            self.logger.error(f"Input path is not a directory: {{input_path}}")
            return False
        
        # Create output directory if it doesn't exist
        output_path = Path(self.config["output_path"])
        output_path.mkdir(parents=True, exist_ok=True)
        
        return True
    
    def get_input_files(self) -> List[Path]:
        """Get list of input files to process."""
        input_path = Path(self.config["input_path"])
        
        # TODO: Implement your file filtering logic
        # Example: Get all .csv files
        files = list(input_path.glob("*.csv"))
        
        self.logger.info(f"Found {{len(files)}} files to process")
        return files
    
    def process_file(self, file_path: Path) -> bool:
        """
        Process a single file.
        
        Args:
            file_path: Path to file to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Processing file: {{file_path}}")
            
            # TODO: Implement your file processing logic
            # Example:
            # - Read CSV/JSON/XML file
            # - Transform data
            # - Validate data
            # - Write to database or output file
            
            # Mock processing
            output_path = Path(self.config["output_path"]) / f"processed_{{file_path.name}}"
            
            with file_path.open('r') as infile, output_path.open('w') as outfile:
                # Simple copy for demo - replace with your logic
                outfile.write(f"# Processed at {{datetime.utcnow().isoformat()}}\\n")
                outfile.write(infile.read())
            
            self.logger.info(f"File processed successfully: {{file_path}} -> {{output_path}}")
            return True
            
        except Exception as e:
            self.logger.error(f"File processing failed: {{file_path}} - {{e}}")
            return False
    
    def process_batch(self, files: List[Path]) -> Dict[str, Any]:
        """
        Process batch of files.
        
        Args:
            files: List of files to process
            
        Returns:
            Batch processing results
        """
        batch_size = self.config["batch_size"]
        total_files = len(files)
        processed = 0
        failed = 0
        
        self.logger.info(f"Starting batch processing: {{total_files}} files, batch size: {{batch_size}}")
        
        for i in range(0, total_files, batch_size):
            batch_files = files[i:i + batch_size]
            self.logger.info(f"Processing batch {{i // batch_size + 1}}: {{len(batch_files)}} files")
            
            for file_path in batch_files:
                if self.process_file(file_path):
                    processed += 1
                else:
                    failed += 1
        
        results = {{
            "total_files": total_files,
            "processed": processed,
            "failed": failed,
            "success_rate": processed / total_files if total_files > 0 else 0
        }}
        
        self.logger.info(f"Batch processing complete: {{results}}")
        return results
    
    def run(self) -> int:
        """
        Run batch job.
        
        Returns:
            Exit code (0 for success, 1 for failure)
        """
        start_time = datetime.utcnow()
        self.logger.info(f"Starting {{plan.project_name}} batch job")
        
        try:
            # Validate inputs
            if not self.validate_inputs():
                return 1
            
            # Get input files
            files = self.get_input_files()
            if not files:
                self.logger.warning("No files to process")
                return 0
            
            # Process batch
            results = self.process_batch(files)
            
            # Check results
            if results["failed"] > 0:
                self.logger.warning(f"Batch job completed with {{results['failed']}} failures")
                if results["success_rate"] < 0.8:  # Less than 80% success rate
                    return 1
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(f"Batch job completed successfully in {{duration:.2f}} seconds")
            return 0
            
        except Exception as e:
            self.logger.error(f"Batch job failed: {{e}}")
            return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="{plan.project_name} Batch Job")
    parser.add_argument("--version", action="version", version="1.0.0")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("Dry run mode - no actual processing will occur")
        # TODO: Implement dry run logic
        return 0
    
    job = BatchJob()
    return job.run()


if __name__ == "__main__":
    sys.exit(main())
'''
        batch_py.write_text(batch_content)
        files.append("batch_job.py")
        
        return files
    
    def _scaffold_common(self, template: ProgramTemplate, plan: ScaffoldPlan, output_path: Path) -> List[str]:
        """Scaffolde gemeinsame Dateien."""
        files = []
        
        # README.md
        readme_md = output_path / "README.md"
        readme_content = f"""# {plan.project_name}

{template.description}

Generated from template: `{template.name}`

## Features

- ✅ 12-Factor App compliant
- ✅ Environment-based configuration
- ✅ Structured logging
- ✅ Health checks
- ✅ Docker support
- ✅ Test framework

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export {plan.log_level_env}=INFO
export {plan.config_file_env}=config.yaml

# Run the application
python main.py  # or app.py, worker.py, batch_job.py
```

### Docker

```bash
# Build image
docker build -t {plan.project_name} .

# Run container
docker run -e {plan.log_level_env}=INFO {plan.project_name}
```

## Configuration

All configuration is done via environment variables (12-Factor principle):

| Variable | Description | Default |
|----------|-------------|---------|
| `{plan.log_level_env}` | Log level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `{plan.config_file_env}` | Optional config file path | None |
| `{plan.database_url_env}` | Database connection URL | None |

## Health Check

Health check endpoint available at:
- Web API: `GET /health`
- Worker: Health check on port 8080
- CLI/Batch: Exit code 0 for success

## Testing

```bash
# Run tests
python -m pytest

# Run with coverage
python -m pytest --cov={plan.project_name}
```

## Deployment

This application follows 12-Factor App principles:

1. ✅ **Codebase**: One codebase tracked in revision control
2. ✅ **Dependencies**: Explicitly declare and isolate dependencies
3. ✅ **Config**: Store config in the environment
4. ✅ **Backing services**: Treat backing services as attached resources
5. ✅ **Build, release, run**: Strictly separate build and run stages
6. ✅ **Processes**: Execute the app as one or more stateless processes
7. ✅ **Port binding**: Export services via port binding
8. ✅ **Concurrency**: Scale out via the process model
9. ✅ **Disposability**: Maximize robustness with fast startup and graceful shutdown
10. ✅ **Dev/prod parity**: Keep development, staging, and production as similar as possible
11. ✅ **Logs**: Treat logs as event streams
12. ✅ **Admin processes**: Run admin/management tasks as one-off processes

## License

MIT License
"""
        readme_md.write_text(readme_content)
        files.append("README.md")
        
        # Dockerfile
        if plan.include_docker:
            dockerfile = output_path / "Dockerfile"
            dockerfile_content = f"""# {plan.project_name} Dockerfile
# Generated from template: {template.name}

FROM {template.container_config.base_image}

# Create non-root user (12-Factor: Security)
RUN useradd --create-home --shell /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports
{chr(10).join(f'EXPOSE {port}' for port in template.container_config.ports) if template.container_config.ports else '# No ports to expose'}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD {template.container_config.health_check}

# Environment variables (12-Factor: Config)
ENV {plan.log_level_env}=INFO
ENV PYTHONUNBUFFERED=1

# Run application
CMD ["python", "{'app.py' if template.program_type.value == 'web-api' else 'main.py'}"]
"""
            dockerfile.write_text(dockerfile_content)
            files.append("Dockerfile")
        
        # Basic tests
        if plan.include_tests:
            tests_dir = output_path / "tests"
            tests_dir.mkdir(exist_ok=True)
            
            test_main_py = tests_dir / "test_main.py"
            test_content = f'''"""
Tests for {plan.project_name}

Generated from template: {template.name}
"""

import pytest
import os
from unittest.mock import patch, MagicMock


def test_environment_variables():
    """Test environment variable loading."""
    with patch.dict(os.environ, {{"{plan.log_level_env}": "DEBUG"}}):
        assert os.getenv("{plan.log_level_env}") == "DEBUG"


def test_config_loading():
    """Test configuration loading."""
    # TODO: Import and test your config loading function
    pass


@pytest.mark.integration
def test_health_check():
    """Test health check functionality."""
    # TODO: Implement health check test
    pass


def test_twelve_factor_compliance():
    """Test 12-Factor App compliance."""
    # Test that no hardcoded secrets exist
    # Test that configuration comes from environment
    # Test that the app is stateless
    pass


# Add more tests specific to your application type
'''
            test_main_py.write_text(test_content)
            files.append("tests/test_main.py")
            
            # pytest.ini
            pytest_ini = tests_dir / "pytest.ini"
            pytest_content = """[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    integration: Integration tests
    slow: Slow tests
"""
            pytest_ini.write_text(pytest_content)
            files.append("tests/pytest.ini")
        
        # .env.example
        env_example = output_path / ".env.example"
        env_content = f"""# Environment variables for {plan.project_name}
# Copy to .env and customize for local development

# Logging
{plan.log_level_env}=INFO

# Configuration
{plan.config_file_env}=config.yaml

# Database (if needed)
{plan.database_url_env}=postgresql://user:pass@localhost/dbname

# Application specific
{'PORT=8000' if template.program_type == ProgramType.WEB_API else ''}
{'QUEUE_URL=redis://localhost:6379/0' if template.program_type == ProgramType.WORKER else ''}
{'BATCH_SIZE=100' if template.program_type == ProgramType.BATCH_JOB else ''}
"""
        env_example.write_text(env_content.strip())
        files.append(".env.example")
        
        # .gitignore
        gitignore = output_path / ".gitignore"
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
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

# Environment
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.coverage
.pytest_cache/
htmlcov/

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db

# Application specific
config.yaml
data/
output/
"""
        gitignore.write_text(gitignore_content)
        files.append(".gitignore")
        
        return files
    
    def _validate_twelve_factor(self, project_path: Path) -> List[str]:
        """Validiere 12-Factor-App Compliance."""
        violations = []
        
        # Prüfe alle Python-Dateien
        for py_file in project_path.rglob("*.py"):
            if py_file.name.startswith('.'):
                continue
                
            try:
                content = py_file.read_text()
                file_violations = self.validator.validate_config(content)
                for violation in file_violations:
                    violations.append(f"{py_file.name}: {violation}")
            except Exception:
                continue
        
        # Prüfe Dockerfile
        dockerfile = project_path / "Dockerfile"
        if dockerfile.exists():
            try:
                content = dockerfile.read_text()
                docker_violations = self.validator.validate_dockerfile(content)
                violations.extend(docker_violations)
            except Exception:
                pass
        
        return violations


# Convenience functions
def scaffold_from_description(description: str, project_name: str, output_dir: str = ".") -> Dict[str, Any]:
    """
    Scaffolde Programm aus natürlichsprachlicher Beschreibung.
    
    Args:
        description: Beschreibung des gewünschten Programms
        project_name: Name des Projekts
        output_dir: Output-Verzeichnis
        
    Returns:
        Scaffolding-Ergebnis
    """
    from .template_catalog import match_template
    
    # Finde passendes Template
    match_result = match_template(description)
    
    if not match_result['template'] or match_result['confidence'] < 0.3:
        return {
            'success': False,
            'error': f'No suitable template found for: {description}',
            'suggestion': 'Try being more specific about the program type (CLI, API, worker, batch job)'
        }
    
    # Erstelle Scaffolding-Plan
    plan = ScaffoldPlan(
        project_name=project_name,
        template_name=match_result['template_name'],
        output_dir=output_dir
    )
    
    # Scaffolde Programm
    scaffolder = ProgramScaffolder()
    result = scaffolder.scaffold(plan)
    
    # Füge Template-Matching-Info hinzu
    result['template_match'] = {
        'confidence': match_result['confidence'],
        'reasoning': match_result['reasoning']
    }
    
    return result


if __name__ == "__main__":
    # Demo
    descriptions = [
        "I need a REST API for managing users",
        "Create a CLI tool for file processing", 
        "Build a worker to process email notifications"
    ]
    
    print("🏗️ Scaffolder Demo:")
    for desc in descriptions:
        print(f"\\nDescription: '{desc}'")
        result = scaffold_from_description(desc, "demo-project", "/tmp")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Template: {result['template_used']}")
            print(f"Files: {len(result['generated_files'])} generated")
            print(f"12-Factor violations: {len(result['twelve_factor_violations'])}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
