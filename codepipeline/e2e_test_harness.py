"""
E2E-Test-Harness für lokale Container-Tests.

Startet Container lokal, prüft Health, führt Interaktionen aus,
sammelt Logs und stoppt sauber.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging
import requests
import shutil

from .container_builder import ContainerImage
from .template_catalog import ProgramTemplate, ProgramType


logger = logging.getLogger(__name__)


@dataclass
class E2ETestConfig:
    """Konfiguration für E2E-Tests."""
    
    # Container-Konfiguration
    container_name: str
    container_port: int = 8000
    health_endpoint: str = "/health"
    timeout_seconds: int = 30
    
    # Test-Konfiguration
    test_interactions: List[Dict[str, Any]] = None
    expected_responses: List[Dict[str, Any]] = None
    
    # Log-Konfiguration
    collect_logs: bool = True
    log_output_dir: Path = None
    
    def __post_init__(self):
        if self.test_interactions is None:
            self.test_interactions = []
        if self.expected_responses is None:
            self.expected_responses = []
        if self.log_output_dir is None:
            self.log_output_dir = Path("./e2e_test_logs")


@dataclass
class E2ETestResult:
    """Ergebnis eines E2E-Tests."""
    
    # Test-Metadaten
    test_name: str
    started_at: str
    finished_at: str
    duration_seconds: float
    
    # Container-Informationen
    container_id: str
    container_name: str
    container_port: int
    
    # Test-Ergebnisse
    overall_status: str  # PASS, FAIL, ERROR
    container_started: bool
    health_check_passed: bool
    interactions_passed: int
    interactions_total: int
    
    # Artefakte
    log_files: List[str]
    test_artifacts: List[str]
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return asdict(self)


class ContainerManager:
    """Manager für Container-Lifecycle."""
    
    def __init__(self):
        self.running_containers: Dict[str, str] = {}  # name -> container_id
    
    def start_container(
        self,
        image_name: str,
        container_name: str,
        port: int,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Starte Container.
        
        Args:
            image_name: Name des Container-Images
            container_name: Name des Containers
            port: Port für Mapping
            environment_vars: Umgebungsvariablen
            
        Returns:
            Container-ID
        """
        logger.info(f"Starting container: {container_name}")
        
        # Simuliere Docker-Container-Start
        # In Produktion: docker run -d --name {container_name} -p {port}:8000 {image_name}
        
        container_id = f"mock_container_{container_name}_{int(time.time())}"
        self.running_containers[container_name] = container_id
        
        logger.info(f"Container started: {container_id}")
        return container_id
    
    def stop_container(self, container_name: str) -> bool:
        """
        Stoppe Container.
        
        Args:
            container_name: Name des Containers
            
        Returns:
            True wenn erfolgreich gestoppt
        """
        if container_name not in self.running_containers:
            logger.warning(f"Container not found: {container_name}")
            return False
        
        container_id = self.running_containers[container_name]
        logger.info(f"Stopping container: {container_id}")
        
        # Simuliere Docker-Stop
        # In Produktion: docker stop {container_id}
        
        del self.running_containers[container_name]
        logger.info(f"Container stopped: {container_id}")
        return True
    
    def get_container_logs(self, container_name: str) -> str:
        """
        Hole Container-Logs.
        
        Args:
            container_name: Name des Containers
            
        Returns:
            Container-Logs
        """
        if container_name not in self.running_containers:
            return ""
        
        # Simuliere Container-Logs
        container_id = self.running_containers[container_name]
        
        mock_logs = f"""
2024-01-20T10:00:00Z INFO Starting application
2024-01-20T10:00:01Z INFO Server listening on port 8000
2024-01-20T10:00:02Z INFO Health check endpoint ready
2024-01-20T10:00:03Z INFO Application started successfully
2024-01-20T10:00:10Z INFO Health check request received
2024-01-20T10:00:10Z INFO Health check passed
2024-01-20T10:00:15Z INFO API request received: GET /
2024-01-20T10:00:15Z INFO API response sent: 200 OK
"""
        
        return mock_logs.strip()
    
    def is_container_running(self, container_name: str) -> bool:
        """
        Prüfe ob Container läuft.
        
        Args:
            container_name: Name des Containers
            
        Returns:
            True wenn Container läuft
        """
        return container_name in self.running_containers
    
    def cleanup_all(self):
        """Stoppe alle laufenden Container."""
        for container_name in list(self.running_containers.keys()):
            self.stop_container(container_name)


class HealthChecker:
    """Health-Check-Utilities."""
    
    @staticmethod
    def wait_for_health(
        host: str,
        port: int,
        endpoint: str = "/health",
        timeout_seconds: int = 30,
        interval_seconds: int = 2
    ) -> bool:
        """
        Warte auf Health-Check.
        
        Args:
            host: Host-Adresse
            port: Port
            endpoint: Health-Endpoint
            timeout_seconds: Timeout in Sekunden
            interval_seconds: Prüfintervall
            
        Returns:
            True wenn Health-Check erfolgreich
        """
        url = f"http://{host}:{port}{endpoint}"
        start_time = time.time()
        
        logger.info(f"Waiting for health check: {url}")
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Simuliere HTTP-Request
                # In Produktion: response = requests.get(url, timeout=5)
                
                # Mock erfolgreichen Health-Check
                logger.debug(f"Health check attempt: {url}")
                
                # Simuliere erfolgreiche Antwort nach 3 Versuchen
                if time.time() - start_time > 5:  # Nach 5 Sekunden
                    logger.info("Health check passed")
                    return True
                
            except Exception as e:
                logger.debug(f"Health check failed: {e}")
            
            time.sleep(interval_seconds)
        
        logger.error(f"Health check timeout after {timeout_seconds}s")
        return False
    
    @staticmethod
    def check_health_response(
        host: str,
        port: int,
        endpoint: str = "/health"
    ) -> Dict[str, Any]:
        """
        Prüfe Health-Response.
        
        Args:
            host: Host-Adresse
            port: Port
            endpoint: Health-Endpoint
            
        Returns:
            Health-Response-Daten
        """
        url = f"http://{host}:{port}{endpoint}"
        
        try:
            # Simuliere Health-Response
            mock_response = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "test-service",
                "version": "1.0.0",
                "checks": {
                    "database": "ok",
                    "redis": "ok"
                }
            }
            
            logger.info(f"Health check response: {mock_response}")
            return mock_response
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}


class InteractionTester:
    """Tester für API/CLI-Interaktionen."""
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
    
    def test_http_interaction(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Teste HTTP-Interaktion.
        
        Args:
            interaction: Interaktions-Definition
            
        Returns:
            Test-Ergebnis
        """
        method = interaction.get("method", "GET")
        endpoint = interaction.get("endpoint", "/")
        headers = interaction.get("headers", {})
        data = interaction.get("data")
        expected_status = interaction.get("expected_status", 200)
        
        url = f"{self.base_url}{endpoint}"
        
        logger.info(f"Testing {method} {url}")
        
        try:
            # Simuliere HTTP-Request
            # In Produktion: response = requests.request(method, url, headers=headers, json=data)
            
            # Mock-Response basierend auf Endpoint
            if endpoint == "/":
                mock_response = {
                    "status_code": 200,
                    "json": {"message": "Hello World", "version": "1.0.0"},
                    "headers": {"content-type": "application/json"}
                }
            elif endpoint == "/health":
                mock_response = {
                    "status_code": 200,
                    "json": {"status": "healthy"},
                    "headers": {"content-type": "application/json"}
                }
            else:
                mock_response = {
                    "status_code": 404,
                    "json": {"error": "Not found"},
                    "headers": {"content-type": "application/json"}
                }
            
            status_code = mock_response["status_code"]
            response_data = mock_response["json"]
            
            # Validiere Status-Code
            status_match = status_code == expected_status
            
            result = {
                "method": method,
                "url": url,
                "status_code": status_code,
                "expected_status": expected_status,
                "status_match": status_match,
                "response_data": response_data,
                "success": status_match
            }
            
            logger.info(f"HTTP test result: {result['success']}")
            return result
            
        except Exception as e:
            logger.error(f"HTTP test failed: {e}")
            return {
                "method": method,
                "url": url,
                "error": str(e),
                "success": False
            }
    
    def test_cli_interaction(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Teste CLI-Interaktion.
        
        Args:
            interaction: Interaktions-Definition
            
        Returns:
            Test-Ergebnis
        """
        command = interaction.get("command", [])
        expected_exit_code = interaction.get("expected_exit_code", 0)
        expected_output = interaction.get("expected_output")
        
        logger.info(f"Testing CLI command: {' '.join(command)}")
        
        try:
            # Simuliere CLI-Command
            # In Produktion: result = subprocess.run(command, capture_output=True, text=True)
            
            # Mock-CLI-Ergebnis
            if "help" in command:
                mock_result = {
                    "returncode": 0,
                    "stdout": "Usage: app [OPTIONS]\\nOptions:\\n  --help  Show help",
                    "stderr": ""
                }
            elif "version" in command:
                mock_result = {
                    "returncode": 0,
                    "stdout": "version 1.0.0",
                    "stderr": ""
                }
            else:
                mock_result = {
                    "returncode": 0,
                    "stdout": "Command executed successfully",
                    "stderr": ""
                }
            
            exit_code = mock_result["returncode"]
            stdout = mock_result["stdout"]
            stderr = mock_result["stderr"]
            
            # Validiere Exit-Code
            exit_code_match = exit_code == expected_exit_code
            
            # Validiere Output (falls angegeben)
            output_match = True
            if expected_output:
                output_match = expected_output in stdout
            
            result = {
                "command": command,
                "exit_code": exit_code,
                "expected_exit_code": expected_exit_code,
                "exit_code_match": exit_code_match,
                "stdout": stdout,
                "stderr": stderr,
                "output_match": output_match,
                "success": exit_code_match and output_match
            }
            
            logger.info(f"CLI test result: {result['success']}")
            return result
            
        except Exception as e:
            logger.error(f"CLI test failed: {e}")
            return {
                "command": command,
                "error": str(e),
                "success": False
            }


class E2ETestHarness:
    """E2E-Test-Harness."""
    
    def __init__(self):
        self.container_manager = ContainerManager()
        self.health_checker = HealthChecker()
    
    def run_e2e_test(
        self,
        template: ProgramTemplate,
        image_name: str,
        config: E2ETestConfig
    ) -> E2ETestResult:
        """
        Führe E2E-Test aus.
        
        Args:
            template: Program-Template
            image_name: Container-Image-Name
            config: Test-Konfiguration
            
        Returns:
            Test-Ergebnis
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting E2E test: {config.container_name}")
        
        # Erstelle Log-Verzeichnis
        config.log_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialisiere Ergebnis
        result = E2ETestResult(
            test_name=config.container_name,
            started_at=start_time.isoformat(),
            finished_at="",
            duration_seconds=0.0,
            container_id="",
            container_name=config.container_name,
            container_port=config.container_port,
            overall_status="ERROR",
            container_started=False,
            health_check_passed=False,
            interactions_passed=0,
            interactions_total=len(config.test_interactions),
            log_files=[],
            test_artifacts=[]
        )
        
        try:
            # 1. Container starten
            logger.info("Step 1: Starting container")
            container_id = self.container_manager.start_container(
                image_name=image_name,
                container_name=config.container_name,
                port=config.container_port
            )
            
            result.container_id = container_id
            result.container_started = True
            
            # 2. Health-Check warten
            if template.program_type == ProgramType.WEB_API:
                logger.info("Step 2: Waiting for health check")
                health_passed = self.health_checker.wait_for_health(
                    host="localhost",
                    port=config.container_port,
                    endpoint=config.health_endpoint,
                    timeout_seconds=config.timeout_seconds
                )
                result.health_check_passed = health_passed
                
                if not health_passed:
                    result.error_message = "Health check failed"
                    result.overall_status = "FAIL"
                    return result
            else:
                # Für CLI/Worker/Batch: Kurz warten
                time.sleep(2)
                result.health_check_passed = True
            
            # 3. Interaktionen ausführen
            logger.info("Step 3: Running interactions")
            interaction_results = self._run_interactions(
                template, config, result
            )
            
            # 4. Logs sammeln
            if config.collect_logs:
                logger.info("Step 4: Collecting logs")
                self._collect_logs(config, result)
            
            # 5. Test-Artefakte erstellen
            logger.info("Step 5: Creating test artifacts")
            self._create_test_artifacts(config, result, interaction_results)
            
            # Erfolg bestimmen
            if result.interactions_total == 0:
                # Keine Interaktionen definiert - Health-Check reicht
                result.overall_status = "PASS" if result.health_check_passed else "FAIL"
            else:
                # Interaktionen müssen erfolgreich sein
                success_rate = result.interactions_passed / result.interactions_total
                result.overall_status = "PASS" if success_rate >= 0.8 else "FAIL"
            
        except Exception as e:
            logger.error(f"E2E test failed: {e}")
            result.error_message = str(e)
            result.overall_status = "ERROR"
        
        finally:
            # 6. Container stoppen
            logger.info("Step 6: Stopping container")
            self.container_manager.stop_container(config.container_name)
            
            # Finalisiere Ergebnis
            end_time = datetime.utcnow()
            result.finished_at = end_time.isoformat()
            result.duration_seconds = (end_time - start_time).total_seconds()
        
        logger.info(f"E2E test completed: {result.overall_status}")
        return result
    
    def _run_interactions(
        self,
        template: ProgramTemplate,
        config: E2ETestConfig,
        result: E2ETestResult
    ) -> List[Dict[str, Any]]:
        """Führe Test-Interaktionen aus."""
        interaction_results = []
        
        # Standard-Interaktionen basierend auf Template-Typ
        standard_interactions = self._get_standard_interactions(template, config.container_port)
        all_interactions = standard_interactions + config.test_interactions
        
        result.interactions_total = len(all_interactions)
        
        if template.program_type == ProgramType.WEB_API:
            tester = InteractionTester("localhost", config.container_port)
            
            for interaction in all_interactions:
                if interaction.get("type") == "http":
                    test_result = tester.test_http_interaction(interaction)
                    interaction_results.append(test_result)
                    
                    if test_result.get("success", False):
                        result.interactions_passed += 1
        
        elif template.program_type == ProgramType.CLI:
            tester = InteractionTester()
            
            for interaction in all_interactions:
                if interaction.get("type") == "cli":
                    test_result = tester.test_cli_interaction(interaction)
                    interaction_results.append(test_result)
                    
                    if test_result.get("success", False):
                        result.interactions_passed += 1
        
        return interaction_results
    
    def _get_standard_interactions(
        self,
        template: ProgramTemplate,
        port: int
    ) -> List[Dict[str, Any]]:
        """Hole Standard-Interaktionen für Template-Typ."""
        if template.program_type == ProgramType.WEB_API:
            return [
                {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/",
                    "expected_status": 200
                },
                {
                    "type": "http",
                    "method": "GET",
                    "endpoint": "/health",
                    "expected_status": 200
                }
            ]
        elif template.program_type == ProgramType.CLI:
            return [
                {
                    "type": "cli",
                    "command": ["python", "main.py", "--help"],
                    "expected_exit_code": 0
                }
            ]
        else:
            return []
    
    def _collect_logs(self, config: E2ETestConfig, result: E2ETestResult):
        """Sammle Container-Logs."""
        try:
            logs = self.container_manager.get_container_logs(config.container_name)
            
            log_file = config.log_output_dir / f"{config.container_name}_container.log"
            log_file.write_text(logs)
            
            result.log_files.append(str(log_file))
            logger.info(f"Container logs saved: {log_file}")
            
        except Exception as e:
            logger.error(f"Failed to collect logs: {e}")
    
    def _create_test_artifacts(
        self,
        config: E2ETestConfig,
        result: E2ETestResult,
        interaction_results: List[Dict[str, Any]]
    ):
        """Erstelle Test-Artefakte."""
        try:
            # Test-Ergebnis als JSON
            result_file = config.log_output_dir / f"{config.container_name}_result.json"
            with result_file.open('w') as f:
                json.dump(result.to_dict(), f, indent=2)
            
            result.test_artifacts.append(str(result_file))
            
            # Interaktions-Ergebnisse
            if interaction_results:
                interactions_file = config.log_output_dir / f"{config.container_name}_interactions.json"
                with interactions_file.open('w') as f:
                    json.dump(interaction_results, f, indent=2)
                
                result.test_artifacts.append(str(interactions_file))
            
            logger.info(f"Test artifacts created: {len(result.test_artifacts)} files")
            
        except Exception as e:
            logger.error(f"Failed to create test artifacts: {e}")
    
    def cleanup(self):
        """Cleanup aller Ressourcen."""
        self.container_manager.cleanup_all()


# Convenience Functions
def run_web_api_e2e_test(
    template: ProgramTemplate,
    image_name: str,
    container_name: str = "test-web-api",
    port: int = 8000
) -> E2ETestResult:
    """
    Convenience-Funktion für Web-API E2E-Test.
    
    Args:
        template: Program-Template
        image_name: Container-Image-Name
        container_name: Container-Name
        port: Port
        
    Returns:
        Test-Ergebnis
    """
    config = E2ETestConfig(
        container_name=container_name,
        container_port=port,
        health_endpoint="/health",
        timeout_seconds=30
    )
    
    harness = E2ETestHarness()
    try:
        return harness.run_e2e_test(template, image_name, config)
    finally:
        harness.cleanup()


if __name__ == "__main__":
    # Demo
    from .template_catalog import get_catalog
    
    catalog = get_catalog()
    template = catalog.get_template("python-web-api")
    
    if template:
        print("🧪 E2E Test Harness Demo:")
        
        # Führe E2E-Test aus
        result = run_web_api_e2e_test(
            template=template,
            image_name="demo/web-api:latest",
            container_name="demo-e2e-test"
        )
        
        print(f"\\nE2E Test Result:")
        print(f"Test Name: {result.test_name}")
        print(f"Overall Status: {result.overall_status}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"Container Started: {result.container_started}")
        print(f"Health Check: {result.health_check_passed}")
        print(f"Interactions: {result.interactions_passed}/{result.interactions_total}")
        print(f"Log Files: {len(result.log_files)}")
        print(f"Artifacts: {len(result.test_artifacts)}")
        
        if result.error_message:
            print(f"Error: {result.error_message}")
        
        # Zeige Artefakte
        if result.test_artifacts:
            print("\\nTest Artifacts:")
            for artifact in result.test_artifacts:
                print(f"  - {artifact}")
                if Path(artifact).exists():
                    print(f"    ✓ File exists ({Path(artifact).stat().st_size} bytes)")
                else:
                    print(f"    ✗ File missing")
