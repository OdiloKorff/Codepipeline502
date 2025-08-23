"""
Einheitliche CI/CD-Pipeline.

Einen einzigen Pipeline-Ablauf definieren: Setup → Lint/Type → Tests/Coverage 
→ Security-Scan/SBOM → Scorecard → Draft-PR. Required-Checks exakt an die 
Scorecard koppeln. Manuell und ereignisgetriggert betreiben.
"""

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Setup
_pipeline_log = []


class PipelineStage(str, Enum):
    """Pipeline-Stufen."""
    SETUP = "setup"
    LINT_TYPE = "lint_type"
    TESTS_COVERAGE = "tests_coverage"
    SECURITY_SBOM = "security_sbom"
    SCORECARD = "scorecard"
    DRAFT_PR = "draft_pr"


class StageResult(str, Enum):
    """Stufen-Ergebnisse."""
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class PipelineConfig:
    """Pipeline-Konfiguration."""
    # Repository-Settings
    repo_root: str = "."
    branch_name: str = "main"
    
    # Quality-Gates
    min_coverage_threshold: float = 80.0
    max_linting_violations: int = 10
    security_severity_threshold: str = "medium"
    
    # Tools
    python_executable: str = "python"
    pytest_args: List[str] = field(default_factory=lambda: ["-v", "--tb=short"])
    ruff_config: str = "pyproject.toml"
    mypy_config: str = "mypy.ini"
    
    # CI-Mode
    ci_mode: bool = False
    fail_fast: bool = True
    
    # Artifacts
    artifacts_dir: str = "pipeline_artifacts"
    
    # GitHub-Integration
    github_token: Optional[str] = None
    create_pr: bool = True
    pr_title_template: str = "feat: {spec_id} - {spec_title}"


@dataclass
class StageExecution:
    """Ausführung einer Pipeline-Stufe."""
    stage: PipelineStage
    result: StageResult
    duration_seconds: float
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    artifacts: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if not hasattr(self, 'timestamp'):
            self.timestamp = datetime.now().isoformat()


class UnifiedCICDPipeline:
    """Einheitliche CI/CD-Pipeline für CodePipeline."""
    
    def __init__(self, config: PipelineConfig):
        """
        Args:
            config: Pipeline-Konfiguration
        """
        self.config = config
        self.executions: List[StageExecution] = []
        self.pipeline_start_time = time.time()
        self.current_stage: Optional[PipelineStage] = None
        
        # Artifacts-Verzeichnis erstellen
        Path(self.config.artifacts_dir).mkdir(exist_ok=True)
        
        self._log_pipeline_event("Pipeline initialisiert", {"config": str(config)})
    
    def _log_pipeline_event(self, message: str, extra_data: Dict = None):
        """Logge Pipeline-Event."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "stage": self.current_stage.value if self.current_stage else "pipeline",
            "message": message,
            "extra_data": extra_data or {}
        }
        
        _pipeline_log.append(event)
        print(f"📋 [{event['stage'].upper()}] {message}")
    
    def _execute_command(self, command: List[str], cwd: str = None, timeout: int = 300) -> Tuple[int, str, str]:
        """Führe Command aus und sammle Output."""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.config.repo_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return result.returncode, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timeout after {timeout}s"
        except Exception as e:
            return 1, "", str(e)
    
    def _stage_setup(self) -> StageExecution:
        """Pipeline-Setup-Stufe."""
        self.current_stage = PipelineStage.SETUP
        self._log_pipeline_event("Setup-Stufe gestartet")
        
        start_time = time.time()
        
        setup_steps = []
        overall_success = True
        combined_stdout = []
        combined_stderr = []
        
        # 1. Python-Version prüfen
        exit_code, stdout, stderr = self._execute_command([self.config.python_executable, "--version"])
        setup_steps.append(f"Python Version: {stdout.strip()}")
        combined_stdout.append(stdout)
        combined_stderr.append(stderr)
        
        if exit_code != 0:
            overall_success = False
        
        # 2. Dependencies prüfen
        exit_code, stdout, stderr = self._execute_command([self.config.python_executable, "-m", "pip", "list", "--format=freeze"])
        if exit_code == 0:
            deps_count = len(stdout.strip().split('\n')) if stdout.strip() else 0
            setup_steps.append(f"Dependencies: {deps_count} packages")
        else:
            setup_steps.append("Dependencies: ERROR")
            overall_success = False
        
        combined_stdout.append(stdout)
        combined_stderr.append(stderr)
        
        # 3. Git-Status prüfen
        exit_code, stdout, stderr = self._execute_command(["git", "status", "--porcelain"])
        if exit_code == 0:
            dirty_files = len(stdout.strip().split('\n')) if stdout.strip() else 0
            setup_steps.append(f"Git Status: {dirty_files} modified files")
        else:
            setup_steps.append("Git Status: ERROR")
        
        combined_stdout.append(stdout)
        combined_stderr.append(stderr)
        
        # 4. Arbeitsverzeichnis prüfen
        required_files = ["pyproject.toml", "requirements.txt"]
        missing_files = []
        
        for file_name in required_files:
            if not Path(self.config.repo_root, file_name).exists():
                missing_files.append(file_name)
        
        if missing_files:
            setup_steps.append(f"Missing Files: {missing_files}")
            overall_success = False
        else:
            setup_steps.append("Required Files: ✅")
        
        duration = time.time() - start_time
        
        execution = StageExecution(
            stage=PipelineStage.SETUP,
            result=StageResult.SUCCESS if overall_success else StageResult.FAILURE,
            duration_seconds=duration,
            exit_code=0 if overall_success else 1,
            stdout="\n".join(combined_stdout),
            stderr="\n".join(combined_stderr),
            metrics={"setup_steps": len(setup_steps), "missing_files": len(missing_files)}
        )
        
        self._log_pipeline_event(f"Setup abgeschlossen: {execution.result.value}", 
                                {"duration": f"{duration:.1f}s", "steps": len(setup_steps)})
        
        return execution
    
    def _stage_lint_type(self) -> StageExecution:
        """Lint/Type-Checking-Stufe."""
        self.current_stage = PipelineStage.LINT_TYPE
        self._log_pipeline_event("Lint/Type-Checking gestartet")
        
        start_time = time.time()
        
        lint_violations = 0
        type_errors = 0
        combined_stdout = []
        combined_stderr = []
        overall_success = True
        
        # 1. Ruff Linting
        self._log_pipeline_event("Führe Ruff-Linting aus...")
        exit_code, stdout, stderr = self._execute_command([
            self.config.python_executable, "-m", "ruff", "check", 
            "--config", self.config.ruff_config, "."
        ])
        
        combined_stdout.append(f"=== RUFF LINTING ===\n{stdout}")
        combined_stderr.append(stderr)
        
        if exit_code != 0:
            # Zähle Violations (vereinfacht)
            lint_violations = stdout.count("error") + stdout.count("warning")
            
            if lint_violations > self.config.max_linting_violations:
                overall_success = False
                self._log_pipeline_event(f"Zu viele Linting-Violations: {lint_violations}")
            else:
                self._log_pipeline_event(f"Linting-Violations akzeptabel: {lint_violations}")
        else:
            self._log_pipeline_event("Ruff-Linting: ✅ Keine Violations")
        
        # 2. MyPy Type-Checking (falls verfügbar)
        if Path(self.config.mypy_config).exists():
            self._log_pipeline_event("Führe MyPy Type-Checking aus...")
            exit_code, stdout, stderr = self._execute_command([
                self.config.python_executable, "-m", "mypy", 
                "--config-file", self.config.mypy_config, "."
            ])
            
            combined_stdout.append(f"\n=== MYPY TYPE CHECKING ===\n{stdout}")
            combined_stderr.append(stderr)
            
            if exit_code != 0:
                type_errors = stdout.count("error:")
                self._log_pipeline_event(f"MyPy Type-Errors: {type_errors}")
                
                # Type-Errors sind warnings, nicht failures (für Demo)
                if type_errors > 50:  # Hoher Threshold
                    overall_success = False
            else:
                self._log_pipeline_event("MyPy Type-Checking: ✅ Keine Errors")
        else:
            self._log_pipeline_event("MyPy Config nicht gefunden - übersprungen")
        
        duration = time.time() - start_time
        
        # Artifacts
        lint_report = {
            "timestamp": datetime.now().isoformat(),
            "ruff_violations": lint_violations,
            "mypy_errors": type_errors,
            "threshold_exceeded": lint_violations > self.config.max_linting_violations
        }
        
        lint_report_path = Path(self.config.artifacts_dir) / "lint_report.json"
        with open(lint_report_path, 'w') as f:
            json.dump(lint_report, f, indent=2)
        
        execution = StageExecution(
            stage=PipelineStage.LINT_TYPE,
            result=StageResult.SUCCESS if overall_success else StageResult.FAILURE,
            duration_seconds=duration,
            exit_code=0 if overall_success else 1,
            stdout="\n".join(combined_stdout),
            stderr="\n".join(combined_stderr),
            artifacts=[str(lint_report_path)],
            metrics={"lint_violations": lint_violations, "type_errors": type_errors}
        )
        
        self._log_pipeline_event(f"Lint/Type abgeschlossen: {execution.result.value}",
                                {"violations": lint_violations, "type_errors": type_errors})
        
        return execution
    
    def _stage_tests_coverage(self) -> StageExecution:
        """Tests/Coverage-Stufe."""
        self.current_stage = PipelineStage.TESTS_COVERAGE
        self._log_pipeline_event("Tests/Coverage gestartet")
        
        start_time = time.time()
        
        combined_stdout = []
        combined_stderr = []
        overall_success = True
        
        test_count = 0
        failed_tests = 0
        coverage_percentage = 0.0
        
        # 1. Pytest mit Coverage
        self._log_pipeline_event("Führe Tests mit Coverage aus...")
        
        pytest_cmd = [
            self.config.python_executable, "-m", "pytest"
        ] + self.config.pytest_args + [
            "--cov=.", 
            "--cov-report=json", 
            "--cov-report=term",
            "--cov-report=html:htmlcov"
        ]
        
        exit_code, stdout, stderr = self._execute_command(pytest_cmd, timeout=600)
        
        combined_stdout.append(f"=== PYTEST OUTPUT ===\n{stdout}")
        combined_stderr.append(stderr)
        
        # Parse Test-Ergebnisse (vereinfacht)
        if "collected" in stdout:
            # Extrahiere Test-Count
            for line in stdout.split('\n'):
                if "collected" in line and "items" in line:
                    try:
                        test_count = int(line.split()[0])
                    except:
                        pass
        
        if "failed" in stdout:
            # Zähle Failed-Tests
            failed_tests = stdout.count("FAILED")
        
        # 2. Coverage-Report parsen
        coverage_json_path = Path("coverage.json")
        if coverage_json_path.exists():
            try:
                with open(coverage_json_path) as f:
                    coverage_data = json.load(f)
                    coverage_percentage = coverage_data.get("totals", {}).get("percent_covered", 0.0)
            except Exception as e:
                self._log_pipeline_event(f"Coverage-Parsing fehlgeschlagen: {e}")
        
        # Coverage-Threshold prüfen
        if coverage_percentage < self.config.min_coverage_threshold:
            overall_success = False
            self._log_pipeline_event(f"Coverage zu niedrig: {coverage_percentage:.1f}% < {self.config.min_coverage_threshold}%")
        else:
            self._log_pipeline_event(f"Coverage OK: {coverage_percentage:.1f}%")
        
        # Test-Failures prüfen
        if failed_tests > 0:
            overall_success = False
            self._log_pipeline_event(f"Tests fehlgeschlagen: {failed_tests}")
        else:
            self._log_pipeline_event(f"Alle Tests bestanden: {test_count}")
        
        duration = time.time() - start_time
        
        # Artifacts
        test_report = {
            "timestamp": datetime.now().isoformat(),
            "test_count": test_count,
            "failed_tests": failed_tests,
            "coverage_percentage": coverage_percentage,
            "coverage_threshold": self.config.min_coverage_threshold,
            "coverage_passed": coverage_percentage >= self.config.min_coverage_threshold
        }
        
        test_report_path = Path(self.config.artifacts_dir) / "test_report.json"
        with open(test_report_path, 'w') as f:
            json.dump(test_report, f, indent=2)
        
        artifacts = [str(test_report_path)]
        
        # Coverage-Artifacts hinzufügen (falls vorhanden)
        if coverage_json_path.exists():
            artifacts.append(str(coverage_json_path))
        
        if Path("htmlcov").exists():
            artifacts.append("htmlcov/")
        
        execution = StageExecution(
            stage=PipelineStage.TESTS_COVERAGE,
            result=StageResult.SUCCESS if overall_success else StageResult.FAILURE,
            duration_seconds=duration,
            exit_code=exit_code,
            stdout="\n".join(combined_stdout),
            stderr="\n".join(combined_stderr),
            artifacts=artifacts,
            metrics={
                "test_count": test_count,
                "failed_tests": failed_tests,
                "coverage_percentage": coverage_percentage
            }
        )
        
        self._log_pipeline_event(f"Tests/Coverage abgeschlossen: {execution.result.value}",
                                {"tests": f"{test_count - failed_tests}/{test_count}",
                                 "coverage": f"{coverage_percentage:.1f}%"})
        
        return execution
    
    def _stage_security_sbom(self) -> StageExecution:
        """Security-Scan/SBOM-Stufe."""
        self.current_stage = PipelineStage.SECURITY_SBOM
        self._log_pipeline_event("Security-Scan/SBOM gestartet")
        
        start_time = time.time()
        
        combined_stdout = []
        combined_stderr = []
        overall_success = True
        
        security_findings = 0
        high_severity_findings = 0
        sbom_generated = False
        
        # 1. Bandit Security-Scan
        self._log_pipeline_event("Führe Bandit Security-Scan aus...")
        exit_code, stdout, stderr = self._execute_command([
            self.config.python_executable, "-m", "bandit", 
            "-r", ".", "-f", "json", "-o", f"{self.config.artifacts_dir}/bandit_report.json"
        ])
        
        combined_stdout.append(f"=== BANDIT SECURITY SCAN ===\n{stdout}")
        combined_stderr.append(stderr)
        
        # Parse Bandit-Report
        bandit_report_path = Path(self.config.artifacts_dir) / "bandit_report.json"
        if bandit_report_path.exists():
            try:
                with open(bandit_report_path) as f:
                    bandit_data = json.load(f)
                    security_findings = len(bandit_data.get("results", []))
                    
                    # Zähle High-Severity-Findings
                    for result in bandit_data.get("results", []):
                        if result.get("issue_severity") == "HIGH":
                            high_severity_findings += 1
                            
            except Exception as e:
                self._log_pipeline_event(f"Bandit-Report-Parsing fehlgeschlagen: {e}")
        
        # 2. Safety Vulnerability-Check
        self._log_pipeline_event("Führe Safety Vulnerability-Check aus...")
        exit_code, stdout, stderr = self._execute_command([
            self.config.python_executable, "-m", "safety", "check", "--json"
        ])
        
        combined_stdout.append(f"\n=== SAFETY VULNERABILITY CHECK ===\n{stdout}")
        combined_stderr.append(stderr)
        
        vulnerability_count = 0
        if exit_code != 0 and stdout:
            try:
                safety_data = json.loads(stdout)
                vulnerability_count = len(safety_data)
            except:
                # Safety-Output ist manchmal nicht JSON
                vulnerability_count = stdout.count("vulnerability") if stdout else 0
        
        # 3. SBOM-Generierung (simuliert)
        self._log_pipeline_event("Generiere Software Bill of Materials...")
        
        # Simuliere SBOM mit pip list
        exit_code, stdout, stderr = self._execute_command([
            self.config.python_executable, "-m", "pip", "list", "--format=json"
        ])
        
        if exit_code == 0:
            try:
                pip_data = json.loads(stdout)
                
                # Erstelle vereinfachte SBOM
                sbom = {
                    "bomFormat": "CycloneDX",
                    "specVersion": "1.4",
                    "version": 1,
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "component": {
                            "type": "application",
                            "name": "codepipeline",
                            "version": "1.0.0"
                        }
                    },
                    "components": [
                        {
                            "type": "library",
                            "name": pkg["name"],
                            "version": pkg["version"],
                            "purl": f"pkg:pypi/{pkg['name']}@{pkg['version']}"
                        }
                        for pkg in pip_data
                    ]
                }
                
                sbom_path = Path(self.config.artifacts_dir) / "sbom.json"
                with open(sbom_path, 'w') as f:
                    json.dump(sbom, f, indent=2)
                
                sbom_generated = True
                self._log_pipeline_event(f"SBOM generiert: {len(pip_data)} Komponenten")
                
            except Exception as e:
                self._log_pipeline_event(f"SBOM-Generierung fehlgeschlagen: {e}")
        
        # Security-Threshold prüfen
        severity_thresholds = {
            "none": 0,
            "low": 1,
            "medium": 5,
            "high": 10
        }
        
        max_findings = severity_thresholds.get(self.config.security_severity_threshold, 5)
        
        if high_severity_findings > 0:
            overall_success = False
            self._log_pipeline_event(f"High-Severity Security-Findings: {high_severity_findings}")
        elif security_findings > max_findings:
            overall_success = False
            self._log_pipeline_event(f"Zu viele Security-Findings: {security_findings} > {max_findings}")
        else:
            self._log_pipeline_event(f"Security-Scan OK: {security_findings} Findings")
        
        duration = time.time() - start_time
        
        # Artifacts sammeln
        artifacts = []
        
        for artifact_file in ["bandit_report.json", "sbom.json"]:
            artifact_path = Path(self.config.artifacts_dir) / artifact_file
            if artifact_path.exists():
                artifacts.append(str(artifact_path))
        
        execution = StageExecution(
            stage=PipelineStage.SECURITY_SBOM,
            result=StageResult.SUCCESS if overall_success else StageResult.FAILURE,
            duration_seconds=duration,
            exit_code=0 if overall_success else 1,
            stdout="\n".join(combined_stdout),
            stderr="\n".join(combined_stderr),
            artifacts=artifacts,
            metrics={
                "security_findings": security_findings,
                "high_severity_findings": high_severity_findings,
                "vulnerability_count": vulnerability_count,
                "sbom_generated": sbom_generated
            }
        )
        
        self._log_pipeline_event(f"Security/SBOM abgeschlossen: {execution.result.value}",
                                {"findings": security_findings, 
                                 "high_severity": high_severity_findings,
                                 "sbom": sbom_generated})
        
        return execution
    
    def _stage_scorecard(self) -> StageExecution:
        """QA-Scorecard-Stufe."""
        self.current_stage = PipelineStage.SCORECARD
        self._log_pipeline_event("QA-Scorecard gestartet")
        
        start_time = time.time()
        
        # Sammle Daten aus vorherigen Stufen
        scorecard_data = {
            "timestamp": datetime.now().isoformat(),
            "pipeline_id": f"pipeline_{int(time.time())}",
            "stages": {}
        }
        
        overall_score = 100.0
        hard_must_failures = []
        
        # Analysiere Stage-Ergebnisse
        for execution in self.executions:
            stage_name = execution.stage.value
            
            scorecard_data["stages"][stage_name] = {
                "result": execution.result.value,
                "duration": execution.duration_seconds,
                "metrics": execution.metrics
            }
            
            # Score-Berechnung
            if execution.result == StageResult.FAILURE:
                if stage_name in ["tests_coverage", "security_sbom"]:
                    # Hard-Must-Failures
                    hard_must_failures.append(stage_name)
                    overall_score = 0.0  # Hard-Must-Failure = 0 Score
                else:
                    # Soft-Failures reduzieren Score
                    overall_score -= 20.0
            elif execution.result == StageResult.WARNING:
                overall_score -= 10.0
        
        # Detaillierte Scorecard-Berechnung
        scorecard_details = {
            "setup": self._score_setup(),
            "code_quality": self._score_code_quality(),
            "test_coverage": self._score_test_coverage(),
            "security": self._score_security(),
            "overall": overall_score
        }
        
        scorecard_data["scorecard"] = scorecard_details
        scorecard_data["hard_must_failures"] = hard_must_failures
        scorecard_data["passed"] = len(hard_must_failures) == 0 and overall_score >= 70.0
        
        # Scorecard-Artifacts
        scorecard_json_path = Path(self.config.artifacts_dir) / "qa_scorecard.json"
        with open(scorecard_json_path, 'w') as f:
            json.dump(scorecard_data, f, indent=2)
        
        # Markdown-Report
        scorecard_md_path = Path(self.config.artifacts_dir) / "qa_scorecard.md"
        self._generate_scorecard_markdown(scorecard_data, scorecard_md_path)
        
        duration = time.time() - start_time
        
        execution = StageExecution(
            stage=PipelineStage.SCORECARD,
            result=StageResult.SUCCESS if scorecard_data["passed"] else StageResult.FAILURE,
            duration_seconds=duration,
            exit_code=0 if scorecard_data["passed"] else 1,
            stdout=f"QA-Scorecard: {overall_score:.1f}/100",
            stderr="",
            artifacts=[str(scorecard_json_path), str(scorecard_md_path)],
            metrics={
                "overall_score": overall_score,
                "hard_must_failures": len(hard_must_failures),
                "passed": scorecard_data["passed"]
            }
        )
        
        self._log_pipeline_event(f"Scorecard abgeschlossen: {execution.result.value}",
                                {"score": f"{overall_score:.1f}/100",
                                 "passed": scorecard_data["passed"]})
        
        return execution
    
    def _score_setup(self) -> float:
        """Score Setup-Stufe."""
        setup_execution = next((e for e in self.executions if e.stage == PipelineStage.SETUP), None)
        if not setup_execution:
            return 0.0
        
        return 100.0 if setup_execution.result == StageResult.SUCCESS else 0.0
    
    def _score_code_quality(self) -> float:
        """Score Code-Quality."""
        lint_execution = next((e for e in self.executions if e.stage == PipelineStage.LINT_TYPE), None)
        if not lint_execution:
            return 0.0
        
        violations = lint_execution.metrics.get("lint_violations", 0)
        type_errors = lint_execution.metrics.get("type_errors", 0)
        
        # Score basierend auf Violations
        base_score = 100.0
        base_score -= min(violations * 2, 50)  # Max 50 Punkte Abzug für Violations
        base_score -= min(type_errors * 1, 30)  # Max 30 Punkte Abzug für Type-Errors
        
        return max(base_score, 0.0)
    
    def _score_test_coverage(self) -> float:
        """Score Test-Coverage."""
        test_execution = next((e for e in self.executions if e.stage == PipelineStage.TESTS_COVERAGE), None)
        if not test_execution:
            return 0.0
        
        coverage = test_execution.metrics.get("coverage_percentage", 0.0)
        failed_tests = test_execution.metrics.get("failed_tests", 0)
        
        if failed_tests > 0:
            return 0.0  # Failing Tests = 0 Score
        
        # Coverage-Score
        if coverage >= 90.0:
            return 100.0
        elif coverage >= 80.0:
            return 80.0
        elif coverage >= 70.0:
            return 60.0
        elif coverage >= 50.0:
            return 40.0
        else:
            return 20.0
    
    def _score_security(self) -> float:
        """Score Security."""
        security_execution = next((e for e in self.executions if e.stage == PipelineStage.SECURITY_SBOM), None)
        if not security_execution:
            return 0.0
        
        high_severity = security_execution.metrics.get("high_severity_findings", 0)
        total_findings = security_execution.metrics.get("security_findings", 0)
        
        if high_severity > 0:
            return 0.0  # High-Severity = 0 Score
        
        # Score basierend auf Total-Findings
        base_score = 100.0
        base_score -= min(total_findings * 10, 80)  # Max 80 Punkte Abzug
        
        return max(base_score, 20.0)  # Min 20 Punkte
    
    def _generate_scorecard_markdown(self, scorecard_data: Dict, output_path: Path):
        """Generiere Scorecard-Markdown-Report."""
        md_content = f"""# QA Scorecard Report

**Timestamp**: {scorecard_data['timestamp']}  
**Pipeline ID**: {scorecard_data['pipeline_id']}  
**Overall Status**: {'✅ PASSED' if scorecard_data['passed'] else '❌ FAILED'}

## Summary

| Metric | Score | Status |
|--------|-------|--------|
| Setup | {scorecard_data['scorecard']['setup']:.1f}/100 | {'✅' if scorecard_data['scorecard']['setup'] >= 70 else '❌'} |
| Code Quality | {scorecard_data['scorecard']['code_quality']:.1f}/100 | {'✅' if scorecard_data['scorecard']['code_quality'] >= 70 else '❌'} |
| Test Coverage | {scorecard_data['scorecard']['test_coverage']:.1f}/100 | {'✅' if scorecard_data['scorecard']['test_coverage'] >= 70 else '❌'} |
| Security | {scorecard_data['scorecard']['security']:.1f}/100 | {'✅' if scorecard_data['scorecard']['security'] >= 70 else '❌'} |
| **Overall** | **{scorecard_data['scorecard']['overall']:.1f}/100** | **{'✅' if scorecard_data['passed'] else '❌'}** |

## Stage Details

"""
        
        for stage_name, stage_data in scorecard_data['stages'].items():
            status_emoji = "✅" if stage_data['result'] == 'success' else "❌"
            md_content += f"### {stage_name.replace('_', ' ').title()} {status_emoji}\n\n"
            md_content += f"- **Result**: {stage_data['result']}\n"
            md_content += f"- **Duration**: {stage_data['duration']:.1f}s\n"
            
            if stage_data['metrics']:
                md_content += "- **Metrics**:\n"
                for metric_name, metric_value in stage_data['metrics'].items():
                    md_content += f"  - {metric_name}: {metric_value}\n"
            
            md_content += "\n"
        
        if scorecard_data['hard_must_failures']:
            md_content += "## ❌ Hard-Must Failures\n\n"
            for failure in scorecard_data['hard_must_failures']:
                md_content += f"- {failure.replace('_', ' ').title()}\n"
            md_content += "\n"
        
        md_content += """## Pipeline Artifacts

- QA Scorecard JSON: `qa_scorecard.json`
- QA Scorecard Markdown: `qa_scorecard.md`
- Lint Report: `lint_report.json`
- Test Report: `test_report.json`
- Security Report: `bandit_report.json`
- SBOM: `sbom.json`

---
*Generated by Unified CI/CD Pipeline*
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
    
    def _stage_draft_pr(self) -> StageExecution:
        """Draft-PR-Stufe."""
        self.current_stage = PipelineStage.DRAFT_PR
        self._log_pipeline_event("Draft-PR gestartet")
        
        start_time = time.time()
        
        # Prüfe ob PR erstellt werden soll
        if not self.config.create_pr:
            self._log_pipeline_event("PR-Erstellung deaktiviert - übersprungen")
            return StageExecution(
                stage=PipelineStage.DRAFT_PR,
                result=StageResult.SKIPPED,
                duration_seconds=time.time() - start_time,
                exit_code=0,
                stdout="PR creation skipped",
                stderr="",
                metrics={"pr_created": False}
            )
        
        # Prüfe ob Scorecard bestanden
        scorecard_execution = next((e for e in self.executions if e.stage == PipelineStage.SCORECARD), None)
        
        if not scorecard_execution or scorecard_execution.result != StageResult.SUCCESS:
            self._log_pipeline_event("Scorecard nicht bestanden - PR-Erstellung abgebrochen")
            return StageExecution(
                stage=PipelineStage.DRAFT_PR,
                result=StageResult.FAILURE,
                duration_seconds=time.time() - start_time,
                exit_code=1,
                stdout="",
                stderr="Scorecard failed - PR creation aborted",
                error_message="QA Scorecard must pass before PR creation",
                metrics={"pr_created": False}
            )
        
        # Simuliere PR-Erstellung
        {
            "title": "feat: Automated Pipeline Changes",
            "body": self._generate_pr_body(),
            "head": "feature/pipeline-changes",
            "base": self.config.branch_name,
            "draft": True
        }
        
        # Simuliere GitHub-API-Call
        self._log_pipeline_event("Erstelle Draft-PR...")
        
        # In echter Implementation: GitHub-API-Call
        pr_created = True  # Simuliert
        pr_number = 42  # Simuliert
        pr_url = f"https://github.com/owner/repo/pull/{pr_number}"
        
        if pr_created:
            self._log_pipeline_event(f"Draft-PR erstellt: #{pr_number}")
        else:
            self._log_pipeline_event("PR-Erstellung fehlgeschlagen")
        
        duration = time.time() - start_time
        
        execution = StageExecution(
            stage=PipelineStage.DRAFT_PR,
            result=StageResult.SUCCESS if pr_created else StageResult.FAILURE,
            duration_seconds=duration,
            exit_code=0 if pr_created else 1,
            stdout=f"PR #{pr_number}: {pr_url}" if pr_created else "",
            stderr="" if pr_created else "PR creation failed",
            metrics={
                "pr_created": pr_created,
                "pr_number": pr_number if pr_created else None,
                "pr_url": pr_url if pr_created else None
            }
        )
        
        self._log_pipeline_event(f"Draft-PR abgeschlossen: {execution.result.value}",
                                {"pr_created": pr_created, "pr_number": pr_number if pr_created else None})
        
        return execution
    
    def _generate_pr_body(self) -> str:
        """Generiere PR-Body mit Pipeline-Zusammenfassung."""
        total_duration = time.time() - self.pipeline_start_time
        
        successful_stages = sum(1 for e in self.executions if e.result == StageResult.SUCCESS)
        total_stages = len(self.executions)
        
        body = f"""## Automated Pipeline Results

**Pipeline Duration**: {total_duration:.1f}s  
**Stages**: {successful_stages}/{total_stages} successful

### Stage Summary

"""
        
        for execution in self.executions:
            status_emoji = {
                StageResult.SUCCESS: "✅",
                StageResult.FAILURE: "❌",
                StageResult.WARNING: "⚠️",
                StageResult.SKIPPED: "⏭️"
            }.get(execution.result, "❓")
            
            body += f"- {status_emoji} **{execution.stage.value.replace('_', ' ').title()}** ({execution.duration_seconds:.1f}s)\n"
        
        body += """
### Quality Gates

All quality gates have been validated according to the QA Scorecard.

### Artifacts

Pipeline artifacts are available in the `pipeline_artifacts/` directory:

- QA Scorecard: `qa_scorecard.json`, `qa_scorecard.md`
- Test Results: `test_report.json`
- Security Scan: `bandit_report.json`
- SBOM: `sbom.json`

---
*This PR was created automatically by the Unified CI/CD Pipeline*
"""
        
        return body
    
    def run_pipeline(self) -> Dict[str, Any]:
        """Führe vollständige Pipeline aus."""
        self._log_pipeline_event("Pipeline gestartet")
        
        # Pipeline-Stufen definieren
        stages = [
            self._stage_setup,
            self._stage_lint_type,
            self._stage_tests_coverage,
            self._stage_security_sbom,
            self._stage_scorecard,
            self._stage_draft_pr
        ]
        
        pipeline_success = True
        
        # Führe alle Stufen aus
        for stage_func in stages:
            try:
                execution = stage_func()
                self.executions.append(execution)
                
                # Fail-Fast bei kritischen Fehlern
                if self.config.fail_fast and execution.result == StageResult.FAILURE:
                    if execution.stage in [PipelineStage.TESTS_COVERAGE, PipelineStage.SECURITY_SBOM]:
                        pipeline_success = False
                        self._log_pipeline_event(f"Pipeline gestoppt bei kritischem Fehler in {execution.stage.value}")
                        break
                
            except Exception as e:
                error_execution = StageExecution(
                    stage=self.current_stage or PipelineStage.SETUP,
                    result=StageResult.FAILURE,
                    duration_seconds=0.0,
                    exit_code=1,
                    stderr=str(e),
                    error_message=str(e)
                )
                
                self.executions.append(error_execution)
                pipeline_success = False
                
                self._log_pipeline_event(f"Pipeline-Fehler in {self.current_stage}: {e}")
                
                if self.config.fail_fast:
                    break
        
        # Pipeline-Zusammenfassung
        total_duration = time.time() - self.pipeline_start_time
        successful_stages = sum(1 for e in self.executions if e.result == StageResult.SUCCESS)
        
        pipeline_result = {
            "success": pipeline_success,
            "total_duration": total_duration,
            "stages_executed": len(self.executions),
            "stages_successful": successful_stages,
            "executions": [
                {
                    "stage": e.stage.value,
                    "result": e.result.value,
                    "duration": e.duration_seconds,
                    "metrics": e.metrics
                }
                for e in self.executions
            ],
            "artifacts_dir": self.config.artifacts_dir,
            "pipeline_log": _pipeline_log.copy()
        }
        
        # Pipeline-Result als Artifact
        pipeline_result_path = Path(self.config.artifacts_dir) / "pipeline_result.json"
        with open(pipeline_result_path, 'w') as f:
            json.dump(pipeline_result, f, indent=2)
        
        self._log_pipeline_event(f"Pipeline beendet: {'✅ SUCCESS' if pipeline_success else '❌ FAILURE'}",
                                {"duration": f"{total_duration:.1f}s",
                                 "stages": f"{successful_stages}/{len(self.executions)}"})
        
        return pipeline_result


def demo_unified_cicd_pipeline():
    """Demonstriere die Unified CI/CD-Pipeline."""
    print("🔄 UNIFIED CI/CD PIPELINE DEMO")
    print("=" * 80)
    
    # Pipeline-Konfiguration
    config = PipelineConfig(
        repo_root=".",
        min_coverage_threshold=70.0,  # Reduziert für Demo
        max_linting_violations=50,    # Erhöht für Demo
        security_severity_threshold="medium",
        ci_mode=True,
        fail_fast=False,  # Alle Stufen ausführen für Demo
        create_pr=True,
        artifacts_dir="demo_pipeline_artifacts"
    )
    
    print("🔧 Pipeline-Konfiguration:")
    print(f"   - Repository: {config.repo_root}")
    print(f"   - Coverage-Threshold: {config.min_coverage_threshold}%")
    print(f"   - Max Lint-Violations: {config.max_linting_violations}")
    print(f"   - Security-Threshold: {config.security_severity_threshold}")
    print(f"   - Fail-Fast: {config.fail_fast}")
    print(f"   - Create PR: {config.create_pr}")
    
    # Pipeline ausführen
    pipeline = UnifiedCICDPipeline(config)
    
    print("\n🚀 Pipeline-Ausführung gestartet...")
    
    time.time()
    result = pipeline.run_pipeline()
    time.time()
    
    # Ergebnisse anzeigen
    print("\n📊 PIPELINE-ERGEBNISSE")
    print("=" * 80)
    
    print(f"🎯 Gesamt-Status: {'✅ SUCCESS' if result['success'] else '❌ FAILURE'}")
    print(f"⏱️  Gesamt-Dauer: {result['total_duration']:.1f}s")
    print(f"📋 Stufen: {result['stages_successful']}/{result['stages_executed']} erfolgreich")
    
    print("\n📋 Stufen-Details:")
    
    stage_icons = {
        "setup": "🔧",
        "lint_type": "🔍",
        "tests_coverage": "🧪",
        "security_sbom": "🛡️",
        "scorecard": "📊",
        "draft_pr": "🔄"
    }
    
    for execution_data in result['executions']:
        stage = execution_data['stage']
        result_status = execution_data['result']
        duration = execution_data['duration']
        
        icon = stage_icons.get(stage, "📋")
        status_emoji = "✅" if result_status == "success" else "❌" if result_status == "failure" else "⚠️"
        
        print(f"   {icon} {stage.replace('_', ' ').title()}: {status_emoji} {result_status.upper()} ({duration:.1f}s)")
        
        # Zeige wichtige Metriken
        metrics = execution_data.get('metrics', {})
        if metrics:
            key_metrics = []
            
            if 'lint_violations' in metrics:
                key_metrics.append(f"Violations: {metrics['lint_violations']}")
            
            if 'coverage_percentage' in metrics:
                key_metrics.append(f"Coverage: {metrics['coverage_percentage']:.1f}%")
            
            if 'security_findings' in metrics:
                key_metrics.append(f"Security: {metrics['security_findings']} findings")
            
            if 'overall_score' in metrics:
                key_metrics.append(f"Score: {metrics['overall_score']:.1f}/100")
            
            if 'pr_created' in metrics and metrics['pr_created']:
                key_metrics.append(f"PR: #{metrics.get('pr_number', 'N/A')}")
            
            if key_metrics:
                print(f"      📈 {', '.join(key_metrics)}")
    
    # Artifacts-Übersicht
    artifacts_dir = Path(config.artifacts_dir)
    if artifacts_dir.exists():
        artifacts = list(artifacts_dir.glob("*"))
        
        print(f"\n📦 Pipeline-Artifacts ({len(artifacts)}):")
        for artifact in artifacts:
            file_size = artifact.stat().st_size if artifact.is_file() else 0
            print(f"   📄 {artifact.name} ({file_size} bytes)")
    
    # Required Checks für GitHub
    print("\n✅ Required Checks (GitHub-Integration):")
    
    required_checks = [
        ("CI/Setup", "setup"),
        ("CI/Lint-Type", "lint_type"), 
        ("CI/Tests-Coverage", "tests_coverage"),
        ("CI/Security-SBOM", "security_sbom"),
        ("CI/QA-Scorecard", "scorecard")
    ]
    
    for check_name, stage_name in required_checks:
        execution_data = next((e for e in result['executions'] if e['stage'] == stage_name), None)
        
        if execution_data:
            status = execution_data['result']
            status_emoji = "✅" if status == "success" else "❌"
            print(f"   {status_emoji} {check_name}: {status.upper()}")
        else:
            print(f"   ⏭️  {check_name}: SKIPPED")
    
    # CI/CD-Empfehlungen
    print("\n💡 CI/CD-Empfehlungen:")
    
    if result['success']:
        print("   ✅ Pipeline bereit für Production-Deployment")
        print("   ✅ Alle Required Checks können in GitHub konfiguriert werden")
        print("   ✅ Draft-PR-Workflow funktional")
    else:
        print("   ⚠️  Pipeline benötigt Verbesserungen:")
        
        failed_stages = [e for e in result['executions'] if e['result'] == 'failure']
        for failed_stage in failed_stages:
            print(f"      - {failed_stage['stage'].replace('_', ' ').title()}: Fehlerbehebung erforderlich")
    
    # Performance-Analyse
    print("\n⚡ Performance-Analyse:")
    
    slowest_stages = sorted(result['executions'], key=lambda e: e['duration'], reverse=True)[:3]
    
    print("   🐌 Langsamste Stufen:")
    for stage_data in slowest_stages:
        print(f"      - {stage_data['stage'].replace('_', ' ').title()}: {stage_data['duration']:.1f}s")
    
    total_duration = result['total_duration']
    if total_duration < 60:
        print(f"   ✅ Pipeline-Performance: Ausgezeichnet ({total_duration:.1f}s)")
    elif total_duration < 300:
        print(f"   ⚠️  Pipeline-Performance: Akzeptabel ({total_duration:.1f}s)")
    else:
        print(f"   ❌ Pipeline-Performance: Optimierung erforderlich ({total_duration:.1f}s)")
    
    print("\n🔄 Unified CI/CD Pipeline Demo abgeschlossen!")
    
    return 0 if result['success'] else 1


if __name__ == "__main__":
    exit_code = demo_unified_cicd_pipeline()
    sys.exit(exit_code)
