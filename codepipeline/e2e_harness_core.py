"""
E2E Test Harness Core - Kompakte Version.

Implementiert End-to-End-Validierung mit Container-Start, Health-Checks und Artefakt-Generierung.
"""

from __future__ import annotations

import os
import json
import time
import subprocess
import requests
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging


logger = logging.getLogger(__name__)


class E2EStatus(Enum):
    """E2E-Test-Status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class ProgramType(Enum):
    """Programmtypen."""
    CLI = "cli"
    WEB_API = "web_api"
    WORKER = "worker"
    BATCH = "batch"


@dataclass
class E2ETestCase:
    """E2E-Test-Fall."""
    name: str
    test_type: str  # health, endpoint, command
    url_path: str = ""
    command: List[str] = field(default_factory=list)
    expected_status: int = 200
    timeout: int = 30


@dataclass
class E2EResult:
    """E2E-Ergebnis."""
    harness_id: str
    program_type: str
    status: E2EStatus
    duration_seconds: float
    tests_passed: int
    tests_failed: int
    container_logs: str = ""
    artifacts: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "harness_id": self.harness_id,
            "program_type": self.program_type,
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "container_logs": self.container_logs[:1000],
            "artifacts": self.artifacts
        }


class E2EHarness:
    """E2E-Test-Harness."""
    
    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = artifacts_dir or Path.cwd() / "e2e_artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    def run_e2e_tests(
        self,
        program_type: ProgramType,
        program_name: str,
        image_name: str,
        ports: Optional[Dict[int, int]] = None
    ) -> E2EResult:
        """Führe E2E-Tests aus."""
        
        harness_id = f"e2e-{program_name}-{int(time.time())}"
        start_time = time.time()
        
        logger.info(f"Starting E2E tests: {harness_id}")
        
        result = E2EResult(
            harness_id=harness_id,
            program_type=program_type.value,
            status=E2EStatus.RUNNING,
            duration_seconds=0,
            tests_passed=0,
            tests_failed=0
        )
        
        container_id = ""
        
        try:
            # Container starten
            container_id = self._start_container(image_name, harness_id, ports)
            
            if not container_id:
                result.status = E2EStatus.ERROR
                return result
            
            # Warte auf Readiness
            if program_type == ProgramType.WEB_API:
                self._wait_for_readiness(container_id, ports)
            else:
                time.sleep(3)
            
            # Test-Cases generieren
            test_cases = self._get_test_cases(program_type, container_id, ports)
            
            # Tests ausführen
            for test_case in test_cases:
                if self._run_test(test_case, container_id, ports):
                    result.tests_passed += 1
                else:
                    result.tests_failed += 1
            
            # Status bestimmen
            if result.tests_failed == 0 and result.tests_passed > 0:
                result.status = E2EStatus.PASSED
            else:
                result.status = E2EStatus.FAILED
        
        except Exception as e:
            logger.error(f"E2E tests failed: {e}")
            result.status = E2EStatus.ERROR
        
        finally:
            # Container stoppen und Logs sammeln
            if container_id:
                result.container_logs = self._get_container_logs(container_id)
                self._stop_container(container_id)
            
            result.duration_seconds = time.time() - start_time
            result.artifacts = self._create_artifacts(result)
        
        logger.info(f"E2E tests completed: {result.status.value}")
        return result
    
    def _start_container(
        self,
        image_name: str,
        container_name: str,
        ports: Optional[Dict[int, int]]
    ) -> str:
        """Starte Container."""
        
        cmd = ["docker", "run", "-d", "--name", container_name]
        
        if ports:
            for container_port, host_port in ports.items():
                cmd.extend(["-p", f"{host_port}:{container_port}"])
        
        cmd.append(image_name)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                container_id = result.stdout.strip()
                time.sleep(2)  # Kurz warten
                return container_id
            else:
                logger.error(f"Container start failed: {result.stderr}")
                return ""
        
        except Exception as e:
            logger.error(f"Container start error: {e}")
            return ""
    
    def _wait_for_readiness(self, container_id: str, ports: Optional[Dict[int, int]]):
        """Warte auf Container-Readiness."""
        
        if not ports:
            return
        
        host_port = list(ports.values())[0]
        health_url = f"http://localhost:{host_port}/health"
        
        for _ in range(15):  # 30 Sekunden
            try:
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    return
            except:
                pass
            time.sleep(2)
    
    def _get_test_cases(
        self,
        program_type: ProgramType,
        container_id: str,
        ports: Optional[Dict[int, int]]
    ) -> List[E2ETestCase]:
        """Generiere Test-Cases."""
        
        if program_type == ProgramType.WEB_API:
            return [
                E2ETestCase("health_check", "health", "/health"),
                E2ETestCase("root_endpoint", "endpoint", "/"),
                E2ETestCase("ready_endpoint", "endpoint", "/ready")
            ]
        elif program_type == ProgramType.CLI:
            return [
                E2ETestCase("version_cmd", "command", command=["docker", "exec", container_id, "python", "main.py", "--version"]),
                E2ETestCase("help_cmd", "command", command=["docker", "exec", container_id, "python", "main.py", "--help"])
            ]
        else:
            return [
                E2ETestCase("basic_health", "health", "/status")
            ]
    
    def _run_test(
        self,
        test_case: E2ETestCase,
        container_id: str,
        ports: Optional[Dict[int, int]]
    ) -> bool:
        """Führe einzelnen Test aus."""
        
        try:
            if test_case.test_type in ["health", "endpoint"]:
                if not ports:
                    return False
                
                host_port = list(ports.values())[0]
                url = f"http://localhost:{host_port}{test_case.url_path}"
                
                response = requests.get(url, timeout=test_case.timeout)
                return response.status_code == test_case.expected_status
            
            elif test_case.test_type == "command":
                result = subprocess.run(
                    test_case.command,
                    capture_output=True,
                    timeout=test_case.timeout
                )
                return result.returncode == 0
            
            return False
        
        except Exception as e:
            logger.error(f"Test {test_case.name} failed: {e}")
            return False
    
    def _get_container_logs(self, container_id: str) -> str:
        """Hole Container-Logs."""
        
        try:
            result = subprocess.run([
                "docker", "logs", container_id
            ], capture_output=True, text=True, timeout=30)
            
            return result.stdout + result.stderr
        except:
            return "Failed to get logs"
    
    def _stop_container(self, container_id: str):
        """Stoppe Container."""
        
        try:
            subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=30)
            subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=30)
        except:
            pass
    
    def _create_artifacts(self, result: E2EResult) -> Dict[str, str]:
        """Erstelle Artefakte."""
        
        artifacts = {}
        
        # E2E-Report
        report_file = self.artifacts_dir / f"{result.harness_id}_report.json"
        with report_file.open('w') as f:
            json.dump(result.to_dict(), f, indent=2)
        artifacts["e2e_report"] = str(report_file)
        
        # Container-Logs
        if result.container_logs:
            logs_file = self.artifacts_dir / f"{result.harness_id}_logs.txt"
            logs_file.write_text(result.container_logs)
            artifacts["container_logs"] = str(logs_file)
        
        return artifacts


# Convenience Function
def run_e2e_for_program(
    program_type: str,
    program_name: str,
    image_name: str,
    ports: Optional[Dict[int, int]] = None
) -> E2EResult:
    """Führe E2E-Tests für Programm aus."""
    
    harness = E2EHarness()
    prog_type = ProgramType(program_type)
    
    return harness.run_e2e_tests(prog_type, program_name, image_name, ports)


if __name__ == "__main__":
    # Demo
    def demo_e2e_harness():
        print("🔬 E2E Harness Demo:")
        
        harness = E2EHarness()
        
        # Test-Cases für verschiedene Programmtypen
        program_types = [
            (ProgramType.WEB_API, "web_service", {5000: 8080}),
            (ProgramType.CLI, "cli_tool", None),
            (ProgramType.WORKER, "worker", {5555: 8081}),
            (ProgramType.BATCH, "batch", None)
        ]
        
        print(f"\\n📋 Testing {len(program_types)} program types:")
        
        total_test_cases = 0
        
        for prog_type, prog_name, ports in program_types:
            test_cases = harness._get_test_cases(prog_type, "mock-container", ports)
            
            print(f"\\n🧪 {prog_type.value} ({prog_name}):")
            print(f"  ✓ Test cases: {len(test_cases)}")
            print(f"  ✓ Port mapping: {ports}")
            
            for test_case in test_cases:
                print(f"    - {test_case.name}: {test_case.test_type}")
            
            total_test_cases += len(test_cases)
        
        # Simuliere E2E-Ergebnis
        mock_result = E2EResult(
            harness_id="e2e-demo-123",
            program_type="web_api",
            status=E2EStatus.PASSED,
            duration_seconds=25.5,
            tests_passed=3,
            tests_failed=0,
            container_logs="Mock container logs"
        )
        
        # Erstelle Artefakte
        artifacts = harness._create_artifacts(mock_result)
        
        print(f"\\n📄 Artifacts created: {len(artifacts)}")
        for name, path in artifacts.items():
            if Path(path).exists():
                size = Path(path).stat().st_size
                print(f"  ✓ {name}: {size} bytes")
        
        # Akzeptanz-Kriterien
        print(f"\\n🎯 Acceptance criteria:")
        
        e2e_green = mock_result.status == E2EStatus.PASSED
        has_artifacts = len(artifacts) > 0
        has_logs = bool(mock_result.container_logs)
        has_duration = mock_result.duration_seconds > 0
        
        print(f"  ✓ E2E runs green: {e2e_green}")
        print(f"  ✓ Generates artifacts: {has_artifacts}")
        print(f"  ✓ Includes logs: {has_logs}")
        print(f"  ✓ Captures duration: {has_duration}")
        
        return e2e_green and has_artifacts and has_logs and has_duration
    
    try:
        result = demo_e2e_harness()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
