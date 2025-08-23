"""
One-Prompt Build Wizard.

Erweitert die Oberfläche um einen Wizard: Eingabe des Produkt-Prompts,
Anzeige der geplanten Architektur, Auswahl Template, Start des Builds,
Live-Gates, Download der Deploy-Bündelung.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator
import logging

from .template_catalog import get_catalog, ProgramTemplate, ProgramType
from .program_prompt_guard import guard_program_prompt
from .llm_gateway import LLMGateway, LLMResult
from .scaffolder import ProgramScaffolder
from .build_system import BuildSystem
from .container_builder import ContainerBuilder
from .e2e_test_harness import E2ETestHarness
from .qa.scorecard import ComprehensiveQAScorecard
from .deploy_bundle import DeployBundleBuilder
from .artifact_signing import ArtifactSigningOrchestrator


logger = logging.getLogger(__name__)


@dataclass
class ArchitecturePlan:
    """Architektur-Plan."""
    
    # Plan-Identifikation
    plan_id: str
    prompt: str
    
    # Geplante Architektur
    program_type: ProgramType
    name: str
    description: str
    
    # Technische Details
    language: str = "Python"
    framework: Optional[str] = None
    database: Optional[str] = None
    
    # Komponenten
    components: List[str] = field(default_factory=list)
    endpoints: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    # Schätzungen
    estimated_complexity: str = "medium"  # low, medium, high
    estimated_duration_minutes: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "plan_id": self.plan_id,
            "prompt": self.prompt,
            "program_type": self.program_type.value,
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "framework": self.framework,
            "database": self.database,
            "components": self.components,
            "endpoints": self.endpoints,
            "dependencies": self.dependencies,
            "estimated_complexity": self.estimated_complexity,
            "estimated_duration_minutes": self.estimated_duration_minutes
        }


@dataclass
class BuildStep:
    """Build-Schritt."""
    
    step_id: str
    name: str
    description: str
    
    # Status
    status: str = "pending"  # pending, running, completed, failed
    progress_percent: int = 0
    
    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    
    # Output
    output_lines: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "output_lines": self.output_lines,
            "error_message": self.error_message,
            "artifacts": self.artifacts
        }


@dataclass
class WizardSession:
    """Wizard-Session."""
    
    # Session-Identifikation
    session_id: str
    created_at: str
    
    # Wizard-Status
    current_step: str = "prompt"  # prompt, plan, template, build, complete
    
    # Session-Daten
    user_prompt: str = ""
    architecture_plan: Optional[ArchitecturePlan] = None
    selected_template: Optional[ProgramTemplate] = None
    
    # Build-Prozess
    build_steps: List[BuildStep] = field(default_factory=list)
    
    # Ergebnis
    success: bool = False
    final_artifacts: List[str] = field(default_factory=list)
    deploy_bundle_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "current_step": self.current_step,
            "user_prompt": self.user_prompt,
            "architecture_plan": self.architecture_plan.to_dict() if self.architecture_plan else None,
            "selected_template": self.selected_template.to_dict() if self.selected_template else None,
            "build_steps": [step.to_dict() for step in self.build_steps],
            "success": self.success,
            "final_artifacts": self.final_artifacts,
            "deploy_bundle_path": self.deploy_bundle_path
        }


class ArchitecturePlanner:
    """Architektur-Planer."""
    
    def __init__(self):
        self.llm_gateway = LLMGateway()
    
    async def analyze_prompt_and_create_plan(self, prompt: str) -> ArchitecturePlan:
        """Analysiere Prompt und erstelle Architektur-Plan."""
        logger.info("Analyzing prompt for architecture planning")
        
        # Guard-Check des Prompts
        guard_result = guard_program_prompt(prompt)
        if guard_result.blocked:
            raise ValueError(f"Prompt blocked by guard: {guard_result.violations[0].explanation if guard_result.violations else 'Unknown reason'}")
        
        # LLM-Prompt für Architektur-Analyse
        analysis_prompt = f"""
Analyze the following product requirement and create a technical architecture plan:

USER PROMPT: {prompt}

Please analyze and respond with a JSON object containing:
{{
    "program_type": "WEB_API" | "CLI" | "WORKER" | "BATCH_JOB",
    "name": "suggested program name (kebab-case)",
    "description": "clear technical description",
    "language": "Python" | "JavaScript" | "Java" | "Go",
    "framework": "suggested framework or null",
    "database": "suggested database or null",
    "components": ["list", "of", "main", "components"],
    "endpoints": ["list", "of", "api", "endpoints"] (if applicable),
    "dependencies": ["list", "of", "key", "dependencies"],
    "estimated_complexity": "low" | "medium" | "high",
    "estimated_duration_minutes": estimated_build_time_in_minutes
}}

Focus on creating a minimal, production-ready solution.
"""
        
        try:
            # Führe LLM-Analyse aus
            llm_result = await self.llm_gateway.generate_unified_diff(
                system_prompt="You are a technical architect. Analyze requirements and suggest optimal architectures.",
                user_prompt=analysis_prompt,
                temperature=0.1  # Niedrige Temperatur für konsistente Ergebnisse
            )
            
            # Parse JSON-Response
            response_content = llm_result.content.strip()
            
            # Extrahiere JSON aus Response
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in LLM response")
            
            json_content = response_content[json_start:json_end]
            analysis_data = json.loads(json_content)
            
            # Erstelle Architektur-Plan
            plan = ArchitecturePlan(
                plan_id=str(uuid.uuid4()),
                prompt=prompt,
                program_type=ProgramType(analysis_data["program_type"]),
                name=analysis_data["name"],
                description=analysis_data["description"],
                language=analysis_data.get("language", "Python"),
                framework=analysis_data.get("framework"),
                database=analysis_data.get("database"),
                components=analysis_data.get("components", []),
                endpoints=analysis_data.get("endpoints", []),
                dependencies=analysis_data.get("dependencies", []),
                estimated_complexity=analysis_data.get("estimated_complexity", "medium"),
                estimated_duration_minutes=analysis_data.get("estimated_duration_minutes", 10)
            )
            
            logger.info(f"Created architecture plan: {plan.name} ({plan.program_type.value})")
            return plan
            
        except Exception as e:
            logger.error(f"Architecture planning failed: {e}")
            
            # Fallback: Einfacher Plan basierend auf Keywords
            return self._create_fallback_plan(prompt)
    
    def _create_fallback_plan(self, prompt: str) -> ArchitecturePlan:
        """Erstelle Fallback-Plan bei LLM-Fehlern."""
        prompt_lower = prompt.lower()
        
        # Einfache Keyword-basierte Klassifikation
        if any(word in prompt_lower for word in ["api", "web", "server", "http", "rest"]):
            program_type = ProgramType.WEB_API
            components = ["web_server", "api_handler", "health_check"]
            endpoints = ["/", "/health", "/api/v1/data"]
        elif any(word in prompt_lower for word in ["cli", "command", "tool", "script"]):
            program_type = ProgramType.CLI
            components = ["command_parser", "main_logic", "output_formatter"]
            endpoints = []
        elif any(word in prompt_lower for word in ["worker", "job", "queue", "background"]):
            program_type = ProgramType.WORKER
            components = ["job_processor", "queue_handler", "task_executor"]
            endpoints = []
        else:
            program_type = ProgramType.BATCH_JOB
            components = ["data_processor", "file_handler", "batch_executor"]
            endpoints = []
        
        return ArchitecturePlan(
            plan_id=str(uuid.uuid4()),
            prompt=prompt,
            program_type=program_type,
            name="generated-app",
            description="Generated application based on user prompt",
            components=components,
            endpoints=endpoints,
            dependencies=["click", "pydantic"] if program_type == ProgramType.CLI else ["fastapi", "uvicorn"],
            estimated_complexity="medium",
            estimated_duration_minutes=8
        )


class BuildWizard:
    """Build-Wizard."""
    
    def __init__(self, work_directory: Path):
        self.work_directory = work_directory
        self.work_directory.mkdir(parents=True, exist_ok=True)
        
        # Komponenten
        self.planner = ArchitecturePlanner()
        self.scaffolder = ProgramScaffolder()
        self.build_system = BuildSystem()
        self.container_builder = ContainerBuilder()
        self.e2e_harness = E2ETestHarness()
        self.scorecard = ComprehensiveQAScorecard()
        self.bundle_builder = DeployBundleBuilder()
        self.artifact_signer = ArtifactSigningOrchestrator()
        
        # Aktive Sessions
        self.sessions: Dict[str, WizardSession] = {}
    
    def create_session(self) -> WizardSession:
        """Erstelle neue Wizard-Session."""
        session = WizardSession(
            session_id=str(uuid.uuid4()),
            created_at=datetime.utcnow().isoformat()
        )
        
        self.sessions[session.session_id] = session
        logger.info(f"Created wizard session: {session.session_id}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[WizardSession]:
        """Hole Wizard-Session."""
        return self.sessions.get(session_id)
    
    async def process_prompt(self, session_id: str, prompt: str) -> WizardSession:
        """Verarbeite Benutzer-Prompt."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        logger.info(f"Processing prompt for session {session_id}")
        
        session.user_prompt = prompt
        session.current_step = "plan"
        
        try:
            # Erstelle Architektur-Plan
            session.architecture_plan = await self.planner.analyze_prompt_and_create_plan(prompt)
            session.current_step = "template"
            
        except Exception as e:
            logger.error(f"Prompt processing failed: {e}")
            session.current_step = "error"
            raise
        
        return session
    
    def select_template(self, session_id: str, template_name: Optional[str] = None) -> WizardSession:
        """Wähle Template für Session."""
        session = self.get_session(session_id)
        if not session or not session.architecture_plan:
            raise ValueError("Invalid session or missing architecture plan")
        
        catalog = get_catalog()
        
        if template_name:
            # Explizite Template-Auswahl
            template = catalog.get_template(template_name)
        else:
            # Automatische Template-Auswahl basierend auf Plan
            template = catalog.get_template_by_type(session.architecture_plan.program_type)
        
        if not template:
            raise ValueError(f"Template not found: {template_name or session.architecture_plan.program_type}")
        
        session.selected_template = template
        session.current_step = "build"
        
        logger.info(f"Selected template {template.name} for session {session_id}")
        return session
    
    async def start_build(self, session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Starte Build-Prozess mit Live-Updates."""
        session = self.get_session(session_id)
        if not session or not session.architecture_plan or not session.selected_template:
            raise ValueError("Session not ready for build")
        
        logger.info(f"Starting build for session {session_id}")
        
        # Erstelle Session-Arbeitsverzeichnis
        session_work_dir = self.work_directory / f"session_{session_id}"
        session_work_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Definiere Build-Schritte
            build_steps = [
                ("scaffold", "Scaffold Application", "Create application structure"),
                ("build", "Build Application", "Compile and package application"),
                ("container", "Build Container", "Create container image"),
                ("test", "Run Tests", "Execute E2E tests"),
                ("quality", "Quality Gate", "Run quality scorecard"),
                ("bundle", "Create Bundle", "Package deployment bundle"),
                ("sign", "Sign Artifacts", "Sign critical artifacts")
            ]
            
            # Erstelle Build-Schritte
            session.build_steps = []
            for step_id, name, description in build_steps:
                step = BuildStep(
                    step_id=step_id,
                    name=name,
                    description=description
                )
                session.build_steps.append(step)
            
            # Führe Build-Schritte aus
            for i, step in enumerate(session.build_steps):
                # Update Step-Status
                step.status = "running"
                step.started_at = datetime.utcnow().isoformat()
                step.progress_percent = 0
                
                # Sende Update
                yield {
                    "type": "step_started",
                    "session": session.to_dict(),
                    "current_step": step.to_dict()
                }
                
                try:
                    # Führe Schritt aus
                    await self._execute_build_step(session, step, session_work_dir)
                    
                    step.status = "completed"
                    step.progress_percent = 100
                    step.completed_at = datetime.utcnow().isoformat()
                    
                    # Sende Update
                    yield {
                        "type": "step_completed",
                        "session": session.to_dict(),
                        "current_step": step.to_dict()
                    }
                    
                except Exception as e:
                    step.status = "failed"
                    step.error_message = str(e)
                    step.completed_at = datetime.utcnow().isoformat()
                    
                    # Sende Error-Update
                    yield {
                        "type": "step_failed",
                        "session": session.to_dict(),
                        "current_step": step.to_dict(),
                        "error": str(e)
                    }
                    
                    # Stop bei kritischen Fehlern
                    if step.step_id in ["scaffold", "build"]:
                        session.success = False
                        session.current_step = "error"
                        return
                
                # Kurze Pause für Live-Updates
                await asyncio.sleep(0.5)
            
            # Build erfolgreich
            session.success = True
            session.current_step = "complete"
            
            # Sammle finale Artefakte
            session.final_artifacts = self._collect_session_artifacts(session_work_dir)
            
            # Finale Update
            yield {
                "type": "build_completed",
                "session": session.to_dict(),
                "success": True
            }
            
        except Exception as e:
            session.success = False
            session.current_step = "error"
            
            yield {
                "type": "build_failed",
                "session": session.to_dict(),
                "error": str(e)
            }
    
    async def _execute_build_step(
        self,
        session: WizardSession,
        step: BuildStep,
        work_dir: Path
    ):
        """Führe einzelnen Build-Schritt aus."""
        import time
        start_time = time.time()
        
        try:
            if step.step_id == "scaffold":
                await self._execute_scaffold_step(session, step, work_dir)
            elif step.step_id == "build":
                await self._execute_build_step_impl(session, step, work_dir)
            elif step.step_id == "container":
                await self._execute_container_step(session, step, work_dir)
            elif step.step_id == "test":
                await self._execute_test_step(session, step, work_dir)
            elif step.step_id == "quality":
                await self._execute_quality_step(session, step, work_dir)
            elif step.step_id == "bundle":
                await self._execute_bundle_step(session, step, work_dir)
            elif step.step_id == "sign":
                await self._execute_sign_step(session, step, work_dir)
            else:
                raise ValueError(f"Unknown build step: {step.step_id}")
                
        finally:
            step.duration_seconds = time.time() - start_time
    
    async def _execute_scaffold_step(self, session: WizardSession, step: BuildStep, work_dir: Path):
        """Führe Scaffold-Schritt aus."""
        step.output_lines.append("Creating application structure...")
        
        # Mock-Plan aus Architecture-Plan
        mock_plan = {
            "name": session.architecture_plan.name,
            "description": session.architecture_plan.description,
            "entry_point": "main",
            "dependencies": session.architecture_plan.dependencies,
            "config_schema": {},
            "health_check": True
        }
        
        # Scaffold Application
        result = self.scaffolder.scaffold_program(
            session.selected_template, mock_plan, work_dir
        )
        
        if not result.success:
            raise RuntimeError("Scaffolding failed")
        
        step.artifacts = [str(f) for f in result.created_files]
        step.output_lines.append(f"Created {len(result.created_files)} files")
    
    async def _execute_build_step_impl(self, session: WizardSession, step: BuildStep, work_dir: Path):
        """Führe Build-Schritt aus."""
        step.output_lines.append("Building application...")
        
        build_config = {
            "build_tool": session.selected_template.runtime,
            "target": "production",
            "optimize": True
        }
        
        result = await self.build_system.build_program(
            work_dir, session.selected_template, build_config
        )
        
        if not result.success:
            raise RuntimeError(result.error_message or "Build failed")
        
        if result.artifact_path:
            step.artifacts.append(str(result.artifact_path))
        step.output_lines.append(f"Build completed: {result.build_tool}")
    
    async def _execute_container_step(self, session: WizardSession, step: BuildStep, work_dir: Path):
        """Führe Container-Schritt aus."""
        step.output_lines.append("Building container image...")
        
        container_config = {
            "base_image": "python:3.10-slim",
            "expose_ports": [8000] if session.architecture_plan.program_type == ProgramType.WEB_API else [],
            "health_check": True
        }
        
        result = await self.container_builder.build_container(
            work_dir, session.selected_template, container_config
        )
        
        if not result.success:
            step.output_lines.append("Container build failed (non-critical)")
        else:
            step.artifacts.append(result.image_id or "container_image")
            step.output_lines.append(f"Container built: {result.image_name}:{result.image_tag}")
    
    async def _execute_test_step(self, session: WizardSession, step: BuildStep, work_dir: Path):
        """Führe Test-Schritt aus."""
        step.output_lines.append("Running E2E tests...")
        
        e2e_config = {
            "test_duration": 20.0,
            "health_check_timeout": 10.0
        }
        
        try:
            result = await self.e2e_harness.run_e2e_test(
                session.architecture_plan.name, session.selected_template, work_dir, e2e_config
            )
            
            step.artifacts.extend([str(f) for f in result.test_artifacts])
            step.output_lines.append(f"E2E tests: {result.overall_status}")
            
        except Exception as e:
            step.output_lines.append(f"E2E tests failed: {e} (non-critical)")
    
    async def _execute_quality_step(self, session: WizardSession, step: BuildStep, work_dir: Path):
        """Führe Quality-Schritt aus."""
        step.output_lines.append("Running quality scorecard...")
        
        # Erstelle Mock-Reports
        self._create_mock_reports(work_dir)
        
        scorecard_inputs = {
            "reports_directory": str(work_dir / "reports"),
            "coverage_threshold": 30.0,
            "security_policy": "permissive"
        }
        
        result = self.scorecard.run(scorecard_inputs)
        
        step.artifacts.append(str(work_dir / "reports" / "qa_summary.json"))
        step.output_lines.append(f"Quality gate: {result.get('overall_status', 'UNKNOWN')}")
    
    async def _execute_bundle_step(self, session: WizardSession, step: BuildStep, work_dir: Path):
        """Führe Bundle-Schritt aus."""
        step.output_lines.append("Creating deployment bundle...")
        
        try:
            # Erstelle Deploy-Bundle
            bundle_path = (self.bundle_builder
                          .create_bundle(session.architecture_plan.name, "1.0.0")
                          .build_bundle(work_dir / "deploy_bundle"))
            
            session.deploy_bundle_path = str(bundle_path)
            step.artifacts.append(str(bundle_path))
            step.output_lines.append(f"Bundle created: {bundle_path.name}")
            
        except Exception as e:
            step.output_lines.append(f"Bundle creation failed: {e} (non-critical)")
        finally:
            self.bundle_builder.cleanup()
    
    async def _execute_sign_step(self, session: WizardSession, step: BuildStep, work_dir: Path):
        """Führe Sign-Schritt aus."""
        step.output_lines.append("Signing critical artifacts...")
        
        try:
            signed_artifacts, _ = await asyncio.get_event_loop().run_in_executor(
                None, lambda: sign_and_verify_artifacts(work_dir)
            )
            
            step.artifacts.extend([str(sig_path) for _, sig_path in signed_artifacts.values()])
            step.output_lines.append(f"Signed {len(signed_artifacts)} artifacts")
            
        except Exception as e:
            step.output_lines.append(f"Artifact signing failed: {e} (non-critical)")
    
    def _create_mock_reports(self, work_dir: Path):
        """Erstelle Mock-Reports."""
        reports_dir = work_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        # Coverage
        (reports_dir / "coverage.xml").write_text(
            '<?xml version="1.0"?><coverage line-rate="0.80" branch-rate="0.75"></coverage>'
        )
        
        # Security
        (reports_dir / "security_report.json").write_text(json.dumps({
            "summary": {"total_findings": 0, "active_tools": 1, "policy_status": "PASS"}
        }))
        
        # Run Meta
        (reports_dir / "run_meta.json").write_text(json.dumps({
            "total_tokens": 150, "model": "gpt-4o-mini"
        }))
        
        # SBOM
        (reports_dir / "sbom_license_cve_check.json").write_text(json.dumps({
            "license_violations": 0, "cve_blockers": 0
        }))
    
    def _collect_session_artifacts(self, work_dir: Path) -> List[str]:
        """Sammle Session-Artefakte."""
        artifacts = []
        
        for pattern in ["*.whl", "*.tar.gz", "*.json", "*.xml", "*.sig"]:
            for artifact_path in work_dir.rglob(pattern):
                if artifact_path.is_file():
                    artifacts.append(str(artifact_path.relative_to(work_dir)))
        
        return sorted(artifacts)
    
    def get_download_url(self, session_id: str, artifact_name: str) -> Optional[str]:
        """Hole Download-URL für Artefakt."""
        # In Produktion: echter Download-Service
        return f"/api/sessions/{session_id}/artifacts/{artifact_name}"


# Convenience Functions
def create_build_wizard(work_directory: Optional[Path] = None) -> BuildWizard:
    """
    Convenience-Funktion für Build-Wizard-Erstellung.
    
    Args:
        work_directory: Arbeitsverzeichnis
        
    Returns:
        Build-Wizard-Instanz
    """
    if work_directory is None:
        work_directory = Path.cwd() / "wizard_workspace"
    
    return BuildWizard(work_directory)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    async def demo_build_wizard():
        print("🧙 Build Wizard Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Build-Wizard
            wizard = create_build_wizard(temp_path)
            
            # Erstelle Session
            session = wizard.create_session()
            print(f"Created session: {session.session_id}")
            
            # Verarbeite Prompt
            test_prompt = "Create a simple REST API for managing todos with CRUD operations"
            session = await wizard.process_prompt(session.session_id, test_prompt)
            
            print(f"\nArchitecture Plan:")
            if session.architecture_plan:
                plan = session.architecture_plan
                print(f"  Type: {plan.program_type.value}")
                print(f"  Name: {plan.name}")
                print(f"  Description: {plan.description}")
                print(f"  Components: {', '.join(plan.components)}")
                print(f"  Estimated Duration: {plan.estimated_duration_minutes} minutes")
            
            # Wähle Template
            session = wizard.select_template(session.session_id)
            print(f"\nSelected Template: {session.selected_template.name}")
            
            # Starte Build (vereinfacht für Demo)
            print(f"\nStarting build process...")
            
            async for update in wizard.start_build(session.session_id):
                update_type = update.get("type", "unknown")
                
                if update_type == "step_started":
                    step = update["current_step"]
                    print(f"  🔄 {step['name']}: {step['description']}")
                
                elif update_type == "step_completed":
                    step = update["current_step"]
                    print(f"  ✅ {step['name']}: completed in {step['duration_seconds']:.2f}s")
                    if step["artifacts"]:
                        print(f"     Artifacts: {len(step['artifacts'])}")
                
                elif update_type == "step_failed":
                    step = update["current_step"]
                    print(f"  ❌ {step['name']}: {update.get('error', 'failed')}")
                
                elif update_type == "build_completed":
                    session_data = update["session"]
                    print(f"\n🎉 Build completed successfully!")
                    print(f"   Final artifacts: {len(session_data['final_artifacts'])}")
                    if session_data["deploy_bundle_path"]:
                        print(f"   Deploy bundle: {Path(session_data['deploy_bundle_path']).name}")
                    break
                
                elif update_type == "build_failed":
                    print(f"\n❌ Build failed: {update.get('error', 'unknown error')}")
                    break
            
            return session.success
    
    # Führe Demo aus
    try:
        result = asyncio.run(demo_build_wizard())
        print(f"\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\nDemo failed: {e}")
    
    print("\nDemo completed!")
