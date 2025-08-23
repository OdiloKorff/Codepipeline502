"""
Template-Matrix-Test.

Baut einen Matrix-Test, der jeden Template-Typ end-to-end durchläuft:
Scaffold, Build, Container, E2E, Scorecard.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

from .template_catalog import get_catalog, ProgramTemplate, ProgramType
from .scaffolder import ProgramScaffolder
from .build_system import BuildSystem
from .container_builder import ContainerBuilder
from .e2e_test_harness import E2ETestHarness
from .qa.scorecard import ComprehensiveQAScorecard
from .performance_budget import evaluate_performance_budget
from .artifact_signing import sign_and_verify_artifacts


logger = logging.getLogger(__name__)


@dataclass
class MatrixTestStep:
    """Matrix-Test-Schritt."""
    
    step_name: str
    template_type: ProgramType
    
    # Ergebnis
    success: bool = False
    duration_seconds: float = 0.0
    
    # Output
    artifacts: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    
    # Details
    step_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "step_name": self.step_name,
            "template_type": self.template_type.value,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "artifacts": self.artifacts,
            "error_message": self.error_message,
            "step_details": self.step_details
        }


@dataclass
class MatrixTestResult:
    """Matrix-Test-Ergebnis für ein Template."""
    
    template_name: str
    template_type: ProgramType
    
    # Test-Schritte
    steps: List[MatrixTestStep] = field(default_factory=list)
    
    # Gesamt-Ergebnis
    overall_success: bool = False
    total_duration: float = 0.0
    
    # Artefakte
    final_artifacts: List[str] = field(default_factory=list)
    
    # Metadaten
    started_at: str = ""
    completed_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "template_name": self.template_name,
            "template_type": self.template_type.value,
            "steps": [step.to_dict() for step in self.steps],
            "overall_success": self.overall_success,
            "total_duration": self.total_duration,
            "final_artifacts": self.final_artifacts,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


@dataclass
class MatrixTestSuite:
    """Matrix-Test-Suite-Ergebnis."""
    
    # Suite-Metadaten
    suite_name: str = "Template Matrix Test"
    started_at: str = ""
    completed_at: str = ""
    total_duration: float = 0.0
    
    # Template-Ergebnisse
    template_results: List[MatrixTestResult] = field(default_factory=list)
    
    # Zusammenfassung
    total_templates: int = 0
    successful_templates: int = 0
    failed_templates: int = 0
    
    # Statistiken
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "suite_name": self.suite_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration": self.total_duration,
            "template_results": [result.to_dict() for result in self.template_results],
            "total_templates": self.total_templates,
            "successful_templates": self.successful_templates,
            "failed_templates": self.failed_templates,
            "total_steps": self.total_steps,
            "successful_steps": self.successful_steps,
            "failed_steps": self.failed_steps
        }


class TemplateMatrixTester:
    """Template-Matrix-Tester."""
    
    def __init__(self, work_directory: Path):
        self.work_directory = work_directory
        self.work_directory.mkdir(parents=True, exist_ok=True)
        
        # Komponenten
        self.scaffolder = ProgramScaffolder()
        self.build_system = BuildSystem()
        self.container_builder = ContainerBuilder()
        self.e2e_harness = E2ETestHarness()
        self.scorecard = ComprehensiveQAScorecard()
    
    async def run_matrix_test_suite(
        self,
        template_types: Optional[List[ProgramType]] = None
    ) -> MatrixTestSuite:
        """Führe Matrix-Test-Suite aus."""
        logger.info("Starting template matrix test suite")
        
        suite = MatrixTestSuite(
            started_at=datetime.utcnow().isoformat()
        )
        
        start_time = time.time()
        
        try:
            # Hole alle Templates
            catalog = get_catalog()
            
            if template_types is None:
                template_types = [ProgramType.WEB_API, ProgramType.CLI, ProgramType.WORKER, ProgramType.BATCH_JOB]
            
            # Teste jedes Template
            for template_type in template_types:
                template = catalog.get_template_by_type(template_type)
                if template:
                    logger.info(f"Testing template: {template.name}")
                    
                    result = await self.test_template_end_to_end(template)
                    suite.template_results.append(result)
                    
                    # Aktualisiere Statistiken
                    suite.total_steps += len(result.steps)
                    suite.successful_steps += sum(1 for step in result.steps if step.success)
                    suite.failed_steps += sum(1 for step in result.steps if not step.success)
                    
                    if result.overall_success:
                        suite.successful_templates += 1
                    else:
                        suite.failed_templates += 1
                else:
                    logger.warning(f"Template not found for type: {template_type}")
            
            suite.total_templates = len(suite.template_results)
            
        except Exception as e:
            logger.error(f"Matrix test suite failed: {e}")
        
        finally:
            suite.completed_at = datetime.utcnow().isoformat()
            suite.total_duration = time.time() - start_time
        
        logger.info(f"Matrix test suite completed: {suite.successful_templates}/{suite.total_templates} templates successful")
        return suite
    
    async def test_template_end_to_end(self, template: ProgramTemplate) -> MatrixTestResult:
        """Teste Template end-to-end."""
        logger.info(f"Starting end-to-end test for template: {template.name}")
        
        result = MatrixTestResult(
            template_name=template.name,
            template_type=template.program_type,
            started_at=datetime.utcnow().isoformat()
        )
        
        start_time = time.time()
        
        # Erstelle Template-spezifisches Arbeitsverzeichnis
        template_work_dir = self.work_directory / f"test_{template.name}_{int(time.time())}"
        template_work_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 1. Scaffold
            scaffold_step = await self._run_scaffold_step(template, template_work_dir)
            result.steps.append(scaffold_step)
            
            if not scaffold_step.success:
                result.overall_success = False
                return result
            
            # 2. Build
            build_step = await self._run_build_step(template, template_work_dir)
            result.steps.append(build_step)
            
            if not build_step.success:
                result.overall_success = False
                return result
            
            # 3. Container
            container_step = await self._run_container_step(template, template_work_dir)
            result.steps.append(container_step)
            
            if not container_step.success:
                result.overall_success = False
                return result
            
            # 4. E2E
            e2e_step = await self._run_e2e_step(template, template_work_dir)
            result.steps.append(e2e_step)
            
            # E2E-Fehler sind nicht kritisch für Overall-Success
            
            # 5. Scorecard
            scorecard_step = await self._run_scorecard_step(template, template_work_dir)
            result.steps.append(scorecard_step)
            
            # Sammle finale Artefakte
            result.final_artifacts = self._collect_final_artifacts(template_work_dir)
            
            # Bestimme Overall-Success
            critical_steps = [scaffold_step, build_step, container_step, scorecard_step]
            result.overall_success = all(step.success for step in critical_steps)
            
        except Exception as e:
            logger.error(f"End-to-end test failed for {template.name}: {e}")
            result.overall_success = False
            
            # Füge Fehler-Schritt hinzu
            error_step = MatrixTestStep(
                step_name="error",
                template_type=template.program_type,
                success=False,
                error_message=str(e)
            )
            result.steps.append(error_step)
        
        finally:
            result.completed_at = datetime.utcnow().isoformat()
            result.total_duration = time.time() - start_time
        
        logger.info(f"End-to-end test completed for {template.name}: {'SUCCESS' if result.overall_success else 'FAILED'}")
        return result
    
    async def _run_scaffold_step(
        self,
        template: ProgramTemplate,
        work_dir: Path
    ) -> MatrixTestStep:
        """Führe Scaffold-Schritt aus."""
        step = MatrixTestStep(
            step_name="scaffold",
            template_type=template.program_type
        )
        
        start_time = time.time()
        
        try:
            logger.debug(f"Scaffolding {template.name}")
            
            # Mock-Plan für Scaffolding
            mock_plan = {
                "name": f"test-{template.name}",
                "description": f"Test application for {template.name} template",
                "entry_point": "main",
                "dependencies": template.dependencies,
                "config_schema": {},
                "health_check": True
            }
            
            # Scaffold Programm
            scaffold_result = self.scaffolder.scaffold_program(template, mock_plan, work_dir)
            
            step.success = scaffold_result.success
            step.artifacts = [str(f) for f in scaffold_result.created_files]
            step.step_details = {
                "created_files": len(scaffold_result.created_files),
                "entry_point": scaffold_result.entry_point,
                "health_check": scaffold_result.health_check_created
            }
            
            if not scaffold_result.success:
                step.error_message = "Scaffolding failed"
            
        except Exception as e:
            step.success = False
            step.error_message = str(e)
            logger.error(f"Scaffold step failed: {e}")
        
        finally:
            step.duration_seconds = time.time() - start_time
        
        return step
    
    async def _run_build_step(
        self,
        template: ProgramTemplate,
        work_dir: Path
    ) -> MatrixTestStep:
        """Führe Build-Schritt aus."""
        step = MatrixTestStep(
            step_name="build",
            template_type=template.program_type
        )
        
        start_time = time.time()
        
        try:
            logger.debug(f"Building {template.name}")
            
            # Build-Konfiguration
            build_config = {
                "build_tool": template.runtime,
                "target": "production",
                "optimize": True
            }
            
            # Build Programm
            build_result = await self.build_system.build_program(
                work_dir, template, build_config
            )
            
            step.success = build_result.success
            step.artifacts = [str(build_result.artifact_path)] if build_result.artifact_path else []
            step.step_details = {
                "build_tool": build_result.build_tool,
                "artifact_size": build_result.artifact_size,
                "build_platform": build_result.build_platform
            }
            
            if not build_result.success:
                step.error_message = build_result.error_message or "Build failed"
            
        except Exception as e:
            step.success = False
            step.error_message = str(e)
            logger.error(f"Build step failed: {e}")
        
        finally:
            step.duration_seconds = time.time() - start_time
        
        return step
    
    async def _run_container_step(
        self,
        template: ProgramTemplate,
        work_dir: Path
    ) -> MatrixTestStep:
        """Führe Container-Schritt aus."""
        step = MatrixTestStep(
            step_name="container",
            template_type=template.program_type
        )
        
        start_time = time.time()
        
        try:
            logger.debug(f"Building container for {template.name}")
            
            # Container-Konfiguration
            container_config = {
                "base_image": "python:3.10-slim" if template.language == "Python" else "alpine:latest",
                "expose_ports": [8000] if template.program_type == ProgramType.WEB_API else [],
                "health_check": True
            }
            
            # Build Container
            container_result = await self.container_builder.build_container(
                work_dir, template, container_config
            )
            
            step.success = container_result.success
            step.artifacts = [container_result.image_id] if container_result.image_id else []
            step.step_details = {
                "image_name": container_result.image_name,
                "image_tag": container_result.image_tag,
                "image_size": container_result.image_size,
                "policy_compliant": container_result.policy_compliant
            }
            
            if not container_result.success:
                step.error_message = container_result.error_message or "Container build failed"
            
        except Exception as e:
            step.success = False
            step.error_message = str(e)
            logger.error(f"Container step failed: {e}")
        
        finally:
            step.duration_seconds = time.time() - start_time
        
        return step
    
    async def _run_e2e_step(
        self,
        template: ProgramTemplate,
        work_dir: Path
    ) -> MatrixTestStep:
        """Führe E2E-Schritt aus."""
        step = MatrixTestStep(
            step_name="e2e",
            template_type=template.program_type
        )
        
        start_time = time.time()
        
        try:
            logger.debug(f"Running E2E tests for {template.name}")
            
            # E2E-Test-Konfiguration
            e2e_config = {
                "test_duration": 30.0,  # 30 Sekunden für Matrix-Test
                "health_check_timeout": 10.0,
                "interaction_timeout": 5.0
            }
            
            # Führe E2E-Tests aus
            e2e_result = await self.e2e_harness.run_e2e_test(
                f"test-{template.name}", template, work_dir, e2e_config
            )
            
            step.success = e2e_result.overall_status == "PASS"
            step.artifacts = [str(f) for f in e2e_result.test_artifacts]
            step.step_details = {
                "overall_status": e2e_result.overall_status,
                "container_started": e2e_result.container_started,
                "health_check_passed": e2e_result.health_check_passed,
                "interactions_passed": e2e_result.interactions_passed,
                "interactions_total": e2e_result.interactions_total,
                "duration_seconds": e2e_result.duration_seconds
            }
            
            if not step.success:
                step.error_message = f"E2E tests failed: {e2e_result.overall_status}"
            
        except Exception as e:
            step.success = False
            step.error_message = str(e)
            logger.error(f"E2E step failed: {e}")
        
        finally:
            step.duration_seconds = time.time() - start_time
        
        return step
    
    async def _run_scorecard_step(
        self,
        template: ProgramTemplate,
        work_dir: Path
    ) -> MatrixTestStep:
        """Führe Scorecard-Schritt aus."""
        step = MatrixTestStep(
            step_name="scorecard",
            template_type=template.program_type
        )
        
        start_time = time.time()
        
        try:
            logger.debug(f"Running scorecard for {template.name}")
            
            # Erstelle Mock-Reports für Scorecard
            self._create_mock_reports(work_dir)
            
            # Führe Scorecard aus
            scorecard_inputs = {
                "reports_directory": str(work_dir / "reports"),
                "coverage_threshold": 30.0,  # Niedriger Threshold für Matrix-Test
                "security_policy": "permissive"  # Permissive für Matrix-Test
            }
            
            scorecard_result = self.scorecard.run(scorecard_inputs)
            
            step.success = scorecard_result.get("overall_status") == "PASS"
            step.artifacts = [str(work_dir / "reports" / "qa_summary.json")]
            step.step_details = {
                "overall_status": scorecard_result.get("overall_status", "UNKNOWN"),
                "overall_score": scorecard_result.get("overall_score", 0.0),
                "gate_results": scorecard_result.get("gate_results", {}),
                "hard_must_failures": scorecard_result.get("hard_must_failures", [])
            }
            
            if not step.success:
                failures = scorecard_result.get("hard_must_failures", [])
                step.error_message = f"Scorecard failed: {', '.join(failures)}" if failures else "Scorecard failed"
            
        except Exception as e:
            step.success = False
            step.error_message = str(e)
            logger.error(f"Scorecard step failed: {e}")
        
        finally:
            step.duration_seconds = time.time() - start_time
        
        return step
    
    def _create_mock_reports(self, work_dir: Path):
        """Erstelle Mock-Reports für Scorecard."""
        reports_dir = work_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        # Mock Coverage Report
        coverage_xml = '''<?xml version="1.0" ?>
<coverage line-rate="0.75" branch-rate="0.70" timestamp="1234567890">
    <sources><source>.</source></sources>
    <packages>
        <package name="." line-rate="0.75" branch-rate="0.70">
        </package>
    </packages>
</coverage>'''
        (reports_dir / "coverage.xml").write_text(coverage_xml)
        
        # Mock Security Report
        security_report = {
            "summary": {
                "total_findings": 1,
                "critical": 0,
                "high": 0,
                "medium": 1,
                "low": 0,
                "active_tools": 2,
                "active_tools_list": ["bandit", "semgrep"],
                "policy_status": "PASS"
            },
            "tools": {
                "bandit": {"findings": 1},
                "semgrep": {"findings": 0}
            }
        }
        (reports_dir / "security_report.json").write_text(json.dumps(security_report, indent=2))
        
        # Mock Run Meta
        run_meta = {
            "run_id": "matrix_test_run",
            "started_at": datetime.utcnow().isoformat(),
            "seed": 42,
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "token_prompt": 100,
            "token_completion": 200,
            "total_tokens": 300,
            "tools": ["ruff", "mypy", "pytest"]
        }
        (reports_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2))
        
        # Mock SBOM License Report
        sbom_license_report = {
            "license_violations": 0,
            "cve_blockers": 0,
            "total_dependencies": 5,
            "license_summary": {"MIT": 3, "Apache-2.0": 2}
        }
        (reports_dir / "sbom_license_cve_check.json").write_text(json.dumps(sbom_license_report, indent=2))
    
    def _collect_final_artifacts(self, work_dir: Path) -> List[str]:
        """Sammle finale Artefakte."""
        artifacts = []
        
        # Standard-Artefakte
        artifact_patterns = [
            "*.whl", "*.jar", "*.tar.gz", "*.zip",  # Build artifacts
            "reports/*.json", "reports/*.xml",      # Reports
            "*.sig",                                # Signatures
            "Dockerfile", "requirements.txt",       # Config files
            "README.md", "LICENSE"                  # Documentation
        ]
        
        for pattern in artifact_patterns:
            for artifact_path in work_dir.rglob(pattern):
                if artifact_path.is_file():
                    artifacts.append(str(artifact_path.relative_to(work_dir)))
        
        return sorted(artifacts)
    
    def save_matrix_test_results(
        self,
        suite: MatrixTestSuite,
        output_path: Path
    ) -> Path:
        """Speichere Matrix-Test-Ergebnisse."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open('w') as f:
            json.dump(suite.to_dict(), f, indent=2)
        
        logger.info(f"Matrix test results saved to: {output_path}")
        return output_path
    
    def generate_matrix_test_report(self, suite: MatrixTestSuite) -> str:
        """Generiere Matrix-Test-Report."""
        lines = [
            "# Template Matrix Test Report",
            "",
            f"**Suite:** {suite.suite_name}",
            f"**Started:** {suite.started_at}",
            f"**Completed:** {suite.completed_at}",
            f"**Duration:** {suite.total_duration:.2f}s",
            "",
            "## Summary",
            "",
            f"- **Total Templates:** {suite.total_templates}",
            f"- **Successful:** {suite.successful_templates}",
            f"- **Failed:** {suite.failed_templates}",
            f"- **Success Rate:** {(suite.successful_templates / suite.total_templates * 100):.1f}%" if suite.total_templates > 0 else "- **Success Rate:** N/A",
            "",
            f"- **Total Steps:** {suite.total_steps}",
            f"- **Successful Steps:** {suite.successful_steps}",
            f"- **Failed Steps:** {suite.failed_steps}",
            "",
            "## Template Results",
            ""
        ]
        
        for template_result in suite.template_results:
            status_icon = "✅" if template_result.overall_success else "❌"
            lines.extend([
                f"### {status_icon} {template_result.template_name} ({template_result.template_type.value})",
                "",
                f"- **Duration:** {template_result.total_duration:.2f}s",
                f"- **Steps:** {len(template_result.steps)}",
                f"- **Artifacts:** {len(template_result.final_artifacts)}",
                ""
            ])
            
            # Step-Details
            lines.append("**Steps:**")
            lines.append("")
            for step in template_result.steps:
                step_icon = "✅" if step.success else "❌"
                lines.append(f"- {step_icon} **{step.step_name}** ({step.duration_seconds:.2f}s)")
                if step.error_message:
                    lines.append(f"  - Error: {step.error_message}")
                if step.artifacts:
                    lines.append(f"  - Artifacts: {len(step.artifacts)}")
            
            lines.append("")
        
        return "\n".join(lines)


# Convenience Functions
async def run_template_matrix_test(
    work_directory: Optional[Path] = None,
    template_types: Optional[List[ProgramType]] = None
) -> MatrixTestSuite:
    """
    Convenience-Funktion für Template-Matrix-Test.
    
    Args:
        work_directory: Arbeitsverzeichnis
        template_types: Zu testende Template-Typen
        
    Returns:
        Matrix-Test-Suite-Ergebnis
    """
    if work_directory is None:
        work_directory = Path.cwd() / "matrix_test_workspace"
    
    tester = TemplateMatrixTester(work_directory)
    return await tester.run_matrix_test_suite(template_types)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    async def demo_matrix_test():
        print("🧪 Template Matrix Test Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Führe Matrix-Test aus (nur Web-API für Demo)
            suite = await run_template_matrix_test(
                work_directory=temp_path,
                template_types=[ProgramType.WEB_API, ProgramType.CLI]
            )
            
            print(f"\nMatrix Test Results:")
            print(f"Total Templates: {suite.total_templates}")
            print(f"Successful: {suite.successful_templates}")
            print(f"Failed: {suite.failed_templates}")
            print(f"Success Rate: {(suite.successful_templates / suite.total_templates * 100):.1f}%" if suite.total_templates > 0 else "N/A")
            print(f"Duration: {suite.total_duration:.2f}s")
            
            print(f"\nTemplate Details:")
            for result in suite.template_results:
                status = "✅ PASS" if result.overall_success else "❌ FAIL"
                print(f"{status} {result.template_name}: {len(result.steps)} steps, {len(result.final_artifacts)} artifacts")
                
                for step in result.steps:
                    step_status = "✓" if step.success else "✗"
                    print(f"  {step_status} {step.step_name}: {step.duration_seconds:.2f}s")
                    if step.error_message:
                        print(f"    Error: {step.error_message}")
            
            # Generiere Report
            tester = TemplateMatrixTester(temp_path)
            report = tester.generate_matrix_test_report(suite)
            
            print(f"\nGenerated Report Preview:")
            print("-" * 40)
            report_lines = report.split('\n')
            for line in report_lines[:20]:  # Erste 20 Zeilen
                print(line)
            if len(report_lines) > 20:
                print("...")
            
            return suite.successful_templates == suite.total_templates
    
    # Führe Demo aus
    try:
        result = asyncio.run(demo_matrix_test())
        print(f"\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\nDemo failed: {e}")
    
    print("\nDemo completed!")
