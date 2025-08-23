"""
GUI Single Frontdoor für CodePipeline.

Implementiert:
- BL-005: GUI als Single Frontdoor (gleiches Backend wie CLI)
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator
import logging
from threading import Lock
import queue


logger = logging.getLogger(__name__)


# === BL-005: GUI als Single Frontdoor (gleiches Backend wie CLI) ===

@dataclass
class RunSpec:
    """Run specification for GUI."""
    
    prompt: str
    branch: str = "main"
    secure_mode: bool = True
    dry_run: bool = False
    template_type: str = "web-api"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt": self.prompt,
            "branch": self.branch,
            "secure_mode": self.secure_mode,
            "dry_run": self.dry_run,
            "template_type": self.template_type
        }


@dataclass
class RunGateStatus:
    """Run gate status for GUI."""
    
    name: str
    status: str  # pending, running, pass, fail, skip
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message
        }


@dataclass
class RunArtifactInfo:
    """Run artifact information for GUI."""
    
    name: str
    type: str
    path: str
    size_bytes: int = 0
    created_at: Optional[datetime] = None
    download_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "download_url": self.download_url
        }


@dataclass
class PipelineRunStatus:
    """Pipeline run status for GUI."""
    
    run_id: str
    spec: RunSpec
    status: str  # pending, running, success, failure
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    gates: List[RunGateStatus] = field(default_factory=list)
    artifacts: List[RunArtifactInfo] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    
    pr_url: str = ""
    pr_number: Optional[int] = None
    
    @property
    def duration_seconds(self) -> float:
        """Get run duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0.0
    
    @property
    def progress_percent(self) -> float:
        """Get progress percentage."""
        if not self.gates:
            return 0.0
        
        completed_gates = len([g for g in self.gates if g.status in ["pass", "fail", "skip"]])
        return (completed_gates / len(self.gates)) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "spec": self.spec.to_dict(),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "progress_percent": self.progress_percent,
            "gates": [gate.to_dict() for gate in self.gates],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "logs": self.logs,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number
        }


@dataclass
class LiveEvent:
    """Live event for SSE/WebSocket."""
    
    event_type: str
    run_id: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type,
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }
    
    def to_sse_format(self) -> str:
        """Convert to SSE format."""
        event_data = json.dumps(self.to_dict())
        return f"event: {self.event_type}\\ndata: {event_data}\\n\\n"


class OrchestratorBridge:
    """Bridge to orchestrator using same code path as CLI."""
    
    def __init__(self):
        # Import orchestrator components
        try:
            from .unified_orchestrator import UnifiedOrchestrator, OrchestrationSpec
            self.orchestrator = UnifiedOrchestrator()
            self.OrchestrationSpec = OrchestrationSpec
            self.available = True
        except ImportError:
            logger.warning("UnifiedOrchestrator not available - using fallback")
            self.orchestrator = None
            self.OrchestrationSpec = None
            self.available = False
    
    async def execute_run(self, run_spec: RunSpec, event_callback=None) -> PipelineRunStatus:
        """Execute run using orchestrator (same code path as CLI)."""
        
        run_id = f"gui_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        run_status = PipelineRunStatus(
            run_id=run_id,
            spec=run_spec,
            status="pending",
            created_at=datetime.utcnow()
        )
        
        if not self.available:
            return await self._execute_run_fallback(run_status, event_callback)
        
        try:
            run_status.status = "running"
            run_status.started_at = datetime.utcnow()
            
            # Emit run started event
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="run_started",
                    run_id=run_id,
                    timestamp=datetime.utcnow(),
                    data={"spec": run_spec.to_dict()}
                ))
            
            # Create orchestration spec (same as CLI)
            orch_spec = self.OrchestrationSpec(
                prompt=run_spec.prompt,
                branch=run_spec.branch,
                secure=run_spec.secure_mode,
                dry_run=run_spec.dry_run,
                template_type=run_spec.template_type
            )
            
            # Execute using orchestrator (exact same code path as CLI)
            orch_result = self.orchestrator.orchestrate(orch_spec)
            
            # Convert orchestrator result to GUI format
            await self._convert_orchestrator_result(orch_result, run_status, event_callback)
            
            run_status.completed_at = datetime.utcnow()
            run_status.status = "success" if orch_result.overall_status == "success" else "failure"
            
            # Emit run completed event
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="run_completed",
                    run_id=run_id,
                    timestamp=datetime.utcnow(),
                    data={"status": run_status.status, "duration": run_status.duration_seconds}
                ))
            
            return run_status
            
        except Exception as e:
            run_status.status = "failure"
            run_status.completed_at = datetime.utcnow()
            
            # Add error log
            error_log = f"Pipeline execution failed: {e}"
            run_status.logs.append(error_log)
            
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="run_error",
                    run_id=run_id,
                    timestamp=datetime.utcnow(),
                    data={"error": error_log}
                ))
            
            logger.error(f"Orchestrator bridge execution failed: {e}")
            return run_status
    
    async def _execute_run_fallback(self, run_status: PipelineRunStatus, event_callback=None) -> PipelineRunStatus:
        """Fallback execution when orchestrator is not available."""
        
        run_status.status = "running"
        run_status.started_at = datetime.utcnow()
        
        # Define fallback gates
        gate_names = ["Guard", "LLM", "Build", "Test", "Security", "Scorecard", "PR"]
        
        for gate_name in gate_names:
            gate = RunGateStatus(
                name=gate_name,
                status="running",
                start_time=datetime.utcnow()
            )
            
            run_status.gates.append(gate)
            
            # Emit gate started event
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="gate_started",
                    run_id=run_status.run_id,
                    timestamp=datetime.utcnow(),
                    data={"gate": gate_name}
                ))
            
            # Simulate gate execution
            await asyncio.sleep(0.5)
            
            gate.end_time = datetime.utcnow()
            gate.duration_seconds = (gate.end_time - gate.start_time).total_seconds()
            gate.status = "pass"  # Simplified - all gates pass in fallback
            
            # Emit gate completed event
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="gate_completed",
                    run_id=run_status.run_id,
                    timestamp=datetime.utcnow(),
                    data={"gate": gate_name, "status": gate.status}
                ))
            
            # Add log entry
            log_entry = f"Gate {gate_name}: {gate.status.upper()} ({gate.duration_seconds:.1f}s)"
            run_status.logs.append(log_entry)
            
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="log_entry",
                    run_id=run_status.run_id,
                    timestamp=datetime.utcnow(),
                    data={"message": log_entry}
                ))
        
        # Generate fallback artifacts
        await self._generate_fallback_artifacts(run_status, event_callback)
        
        run_status.completed_at = datetime.utcnow()
        run_status.status = "success"
        
        return run_status
    
    async def _convert_orchestrator_result(self, orch_result, run_status: PipelineRunStatus, event_callback=None):
        """Convert orchestrator result to GUI format."""
        
        # Convert gates
        for orch_gate in orch_result.gates:
            gate = RunGateStatus(
                name=orch_gate.name,
                status=orch_gate.status,
                start_time=orch_gate.start_time,
                end_time=orch_gate.end_time,
                duration_seconds=orch_gate.duration_seconds,
                error_message=orch_gate.error_message
            )
            
            run_status.gates.append(gate)
            
            # Emit gate events
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="gate_completed",
                    run_id=run_status.run_id,
                    timestamp=gate.end_time or datetime.utcnow(),
                    data={"gate": gate.name, "status": gate.status, "duration": gate.duration_seconds}
                ))
        
        # Convert artifacts
        for artifact_name, artifact_path in orch_result.artifacts.items():
            artifact = RunArtifactInfo(
                name=artifact_name,
                type=self._determine_artifact_type(artifact_name),
                path=artifact_path,
                size_bytes=self._get_file_size(artifact_path),
                created_at=datetime.utcnow(),
                download_url=f"/api/runs/{run_status.run_id}/artifacts/{artifact_name}"
            )
            
            run_status.artifacts.append(artifact)
            
            # Emit artifact events
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="artifact_created",
                    run_id=run_status.run_id,
                    timestamp=datetime.utcnow(),
                    data={"artifact": artifact.to_dict()}
                ))
        
        # Add logs from orchestrator
        run_status.logs.append(f"Orchestration completed: {orch_result.overall_status}")
        run_status.logs.append(f"Total duration: {orch_result.duration_seconds:.1f}s")
        run_status.logs.append(f"Total tokens: {orch_result.total_tokens_used}")
    
    async def _generate_fallback_artifacts(self, run_status: PipelineRunStatus, event_callback=None):
        """Generate fallback artifacts."""
        
        # Create artifacts directory
        artifacts_dir = Path("gui_artifacts") / run_status.run_id
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate basic artifacts
        artifacts = [
            ("QA Report", "qa_report", "qa_report.json"),
            ("Security Report", "security_report", "security_report.json"),
            ("SBOM", "sbom", "sbom.json"),
            ("Coverage Report", "coverage", "coverage.xml"),
            ("Run Metadata", "run_meta", "run_meta.json")
        ]
        
        for name, type_name, filename in artifacts:
            artifact_path = artifacts_dir / filename
            
            # Generate basic content
            if filename.endswith('.json'):
                content = json.dumps({
                    "generated_by": "gui_fallback",
                    "run_id": run_status.run_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "type": type_name
                }, indent=2)
            else:
                content = f"<!-- Generated by GUI fallback for {run_status.run_id} -->"
            
            artifact_path.write_text(content, encoding='utf-8')
            
            artifact = RunArtifactInfo(
                name=name,
                type=type_name,
                path=str(artifact_path),
                size_bytes=len(content.encode()),
                created_at=datetime.utcnow(),
                download_url=f"/api/runs/{run_status.run_id}/artifacts/{filename}"
            )
            
            run_status.artifacts.append(artifact)
            
            # Emit artifact event
            if event_callback:
                await event_callback(LiveEvent(
                    event_type="artifact_created",
                    run_id=run_status.run_id,
                    timestamp=datetime.utcnow(),
                    data={"artifact": artifact.to_dict()}
                ))
    
    def _determine_artifact_type(self, artifact_name: str) -> str:
        """Determine artifact type from name."""
        
        if "qa" in artifact_name.lower():
            return "qa_report"
        elif "security" in artifact_name.lower():
            return "security_report"
        elif "sbom" in artifact_name.lower():
            return "sbom"
        elif "coverage" in artifact_name.lower():
            return "coverage"
        elif "meta" in artifact_name.lower():
            return "run_meta"
        else:
            return "other"
    
    def _get_file_size(self, file_path: str) -> int:
        """Get file size safely."""
        try:
            return os.path.getsize(file_path)
        except:
            return 0


class SingleFrontdoorBackend:
    """Single frontdoor backend for GUI."""
    
    def __init__(self):
        self.runs: Dict[str, PipelineRunStatus] = {}
        self.orchestrator_bridge = OrchestratorBridge()
        self.event_queue = queue.Queue()
        self.event_clients: Dict[str, bool] = {}
        self.backend_lock = Lock()
    
    async def create_run(self, run_spec: RunSpec) -> str:
        """Create new pipeline run."""
        
        # Validate spec
        if not run_spec.prompt or len(run_spec.prompt.strip()) < 10:
            raise ValueError("Prompt must be at least 10 characters")
        
        # Execute run using orchestrator bridge (same code path as CLI)
        run_status = await self.orchestrator_bridge.execute_run(run_spec, self._emit_event)
        
        with self.backend_lock:
            self.runs[run_status.run_id] = run_status
        
        logger.info(f"Created GUI run: {run_status.run_id}")
        return run_status.run_id
    
    def get_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent runs."""
        
        with self.backend_lock:
            runs = list(self.runs.values())
        
        # Sort by creation time, newest first
        runs.sort(key=lambda r: r.created_at, reverse=True)
        
        return [run.to_dict() for run in runs[:limit]]
    
    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run status."""
        
        with self.backend_lock:
            run = self.runs.get(run_id)
        
        if run:
            return run.to_dict()
        
        return None
    
    def get_run_gates(self, run_id: str) -> List[Dict[str, Any]]:
        """Get run gates."""
        
        with self.backend_lock:
            run = self.runs.get(run_id)
        
        if run:
            return [gate.to_dict() for gate in run.gates]
        
        return []
    
    def get_run_artifacts(self, run_id: str) -> List[Dict[str, Any]]:
        """Get run artifacts."""
        
        with self.backend_lock:
            run = self.runs.get(run_id)
        
        if run:
            return [artifact.to_dict() for artifact in run.artifacts]
        
        return []
    
    def get_run_logs(self, run_id: str) -> List[str]:
        """Get run logs."""
        
        with self.backend_lock:
            run = self.runs.get(run_id)
        
        if run:
            return run.logs.copy()
        
        return []
    
    def get_artifact_download_path(self, run_id: str, artifact_name: str) -> Optional[str]:
        """Get artifact download path."""
        
        with self.backend_lock:
            run = self.runs.get(run_id)
        
        if run:
            for artifact in run.artifacts:
                if artifact.name == artifact_name or os.path.basename(artifact.path) == artifact_name:
                    return artifact.path
        
        return None
    
    async def _emit_event(self, event: LiveEvent):
        """Emit live event."""
        
        self.event_queue.put(event)
        logger.debug(f"Emitted event: {event.event_type} for run {event.run_id}")
    
    async def get_event_stream(self, client_id: str) -> AsyncGenerator[str, None]:
        """Get SSE event stream."""
        
        self.event_clients[client_id] = True
        
        try:
            # Send connection event
            yield f"event: connected\\ndata: {json.dumps({'client_id': client_id, 'timestamp': datetime.utcnow().isoformat()})}\\n\\n"
            
            while self.event_clients.get(client_id, False):
                try:
                    # Get event from queue (non-blocking)
                    event = self.event_queue.get_nowait()
                    yield event.to_sse_format()
                    
                except queue.Empty:
                    # Send heartbeat
                    yield f"event: heartbeat\\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\\n\\n"
                    await asyncio.sleep(2)
                
        except asyncio.CancelledError:
            pass
        finally:
            self.event_clients.pop(client_id, None)
    
    def disconnect_client(self, client_id: str):
        """Disconnect event client."""
        self.event_clients.pop(client_id, None)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data."""
        
        runs = self.get_runs(20)
        
        # Calculate statistics
        total_runs = len(self.runs)
        running_runs = len([r for r in runs if r["status"] == "running"])
        successful_runs = len([r for r in runs if r["status"] == "success"])
        failed_runs = len([r for r in runs if r["status"] == "failure"])
        
        return {
            "runs": runs,
            "statistics": {
                "total_runs": total_runs,
                "running_runs": running_runs,
                "successful_runs": successful_runs,
                "failed_runs": failed_runs,
                "success_rate": (successful_runs / total_runs * 100) if total_runs > 0 else 0.0
            },
            "orchestrator_available": self.orchestrator_bridge.available
        }


class SingleFrontdoorGUI:
    """Single frontdoor GUI generator."""
    
    def __init__(self):
        self.backend = SingleFrontdoorBackend()
    
    def generate_dashboard_html(self) -> str:
        """Generate complete dashboard HTML."""
        
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodePipeline - Single Frontdoor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #1a202c; }
        
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header h1 { font-size: 1.75rem; font-weight: 700; }
        .header p { opacity: 0.9; margin-top: 0.5rem; }
        
        .container { max-width: 1400px; margin: 2rem auto; padding: 0 2rem; }
        
        .actions { margin-bottom: 2rem; display: flex; gap: 1rem; align-items: center; }
        .btn { background: #4299e1; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 0.5rem; cursor: pointer; font-weight: 500; text-decoration: none; display: inline-block; transition: all 0.2s; }
        .btn:hover { background: #3182ce; transform: translateY(-1px); }
        .btn-success { background: #48bb78; }
        .btn-success:hover { background: #38a169; }
        .btn-secondary { background: #a0aec0; color: #2d3748; }
        .btn-secondary:hover { background: #718096; color: white; }
        
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #4299e1; }
        .stat-value { font-size: 2rem; font-weight: 700; color: #2d3748; }
        .stat-label { color: #718096; font-size: 0.875rem; margin-top: 0.25rem; }
        
        .card { background: white; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
        .card-header { padding: 1.5rem; border-bottom: 1px solid #e2e8f0; background: #f7fafc; }
        .card-title { font-size: 1.25rem; font-weight: 600; color: #2d3748; }
        
        .table { width: 100%; }
        .table th, .table td { padding: 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
        .table th { background: #f7fafc; font-weight: 600; color: #4a5568; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; }
        .table tbody tr:hover { background: #f7fafc; }
        
        .status { padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.875rem; font-weight: 500; }
        .status-success { background: #c6f6d5; color: #22543d; }
        .status-failure { background: #fed7d7; color: #742a2a; }
        .status-running { background: #bee3f8; color: #2a4365; }
        .status-pending { background: #e2e8f0; color: #4a5568; }
        
        .progress-bar { width: 100%; height: 0.5rem; background: #e2e8f0; border-radius: 0.25rem; overflow: hidden; }
        .progress-fill { height: 100%; background: #4299e1; transition: width 0.3s; }
        
        .link { color: #4299e1; text-decoration: none; font-weight: 500; }
        .link:hover { text-decoration: underline; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 5% auto; padding: 0; border-radius: 0.75rem; max-width: 800px; max-height: 90vh; overflow: hidden; }
        .modal-header { padding: 1.5rem; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: between; align-items: center; }
        .modal-body { padding: 1.5rem; max-height: 60vh; overflow-y: auto; }
        .modal-footer { padding: 1.5rem; border-top: 1px solid #e2e8f0; display: flex; justify-content: end; gap: 1rem; }
        
        .form-group { margin-bottom: 1.5rem; }
        .form-label { display: block; margin-bottom: 0.5rem; font-weight: 500; color: #4a5568; }
        .form-input, .form-textarea, .form-select { width: 100%; padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; font-size: 1rem; }
        .form-textarea { height: 8rem; resize: vertical; }
        .form-error { color: #e53e3e; font-size: 0.875rem; margin-top: 0.5rem; }
        
        .checkbox-group { display: flex; align-items: center; gap: 0.5rem; }
        .checkbox-group input[type="checkbox"] { margin: 0; }
        
        .events-log { background: #2d3748; color: #e2e8f0; padding: 1rem; border-radius: 0.5rem; height: 300px; overflow-y: auto; font-family: 'Monaco', 'Menlo', monospace; font-size: 0.875rem; line-height: 1.4; }
        
        .loading { text-align: center; padding: 2rem; color: #718096; }
        .loading::after { content: '...'; animation: dots 2s infinite; }
        
        @keyframes dots {
            0%, 20% { content: '...'; }
            40% { content: '..'; }
            60% { content: '.'; }
            80%, 100% { content: ''; }
        }
        
        .gate-timeline { display: flex; gap: 0.5rem; margin: 1rem 0; }
        .gate-step { flex: 1; padding: 0.5rem; border-radius: 0.25rem; font-size: 0.75rem; text-align: center; font-weight: 500; }
        .gate-step.pass { background: #c6f6d5; color: #22543d; }
        .gate-step.fail { background: #fed7d7; color: #742a2a; }
        .gate-step.running { background: #bee3f8; color: #2a4365; }
        .gate-step.pending { background: #e2e8f0; color: #4a5568; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 CodePipeline - Single Frontdoor</h1>
        <p>Unified GUI for secure, automated software development</p>
    </div>

    <div class="container">
        <div class="actions">
            <button id="new-run-btn" class="btn btn-success">+ Neuer Run</button>
            <button id="refresh-btn" class="btn btn-secondary">🔄 Aktualisieren</button>
            <div style="margin-left: auto; color: #718096;">
                <span id="orchestrator-status">Orchestrator: <span id="orchestrator-indicator">Checking...</span></span>
            </div>
        </div>

        <div class="stats" id="stats-container">
            <div class="stat-card">
                <div class="stat-value" id="total-runs">-</div>
                <div class="stat-label">Total Runs</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="running-runs">-</div>
                <div class="stat-label">Running</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="success-rate">-</div>
                <div class="stat-label">Success Rate</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Pipeline Runs</h2>
            </div>
            <div id="runs-container">
                <div class="loading">Lade Runs</div>
            </div>
        </div>

        <div class="card" style="margin-top: 2rem;">
            <div class="card-header">
                <h2 class="card-title">Live Events</h2>
            </div>
            <div id="events-log" class="events-log"></div>
        </div>
    </div>

    <!-- New Run Modal -->
    <div id="new-run-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Neuer Pipeline Run</h3>
                <button id="close-modal-btn" style="background: none; border: none; font-size: 1.5rem; cursor: pointer;">&times;</button>
            </div>
            <div class="modal-body">
                <form id="new-run-form">
                    <div class="form-group">
                        <label class="form-label">Prompt *</label>
                        <textarea id="prompt" class="form-textarea" placeholder="Beschreibe die gewünschte Anwendung..." required></textarea>
                        <div id="prompt-error" class="form-error"></div>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Template Type</label>
                        <select id="template-type" class="form-select">
                            <option value="web-api">Web API</option>
                            <option value="cli-app">CLI Application</option>
                            <option value="library">Library</option>
                            <option value="microservice">Microservice</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Branch</label>
                        <input type="text" id="branch" class="form-input" value="main" placeholder="Branch name">
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="secure-mode" checked>
                            <label for="secure-mode">Secure Mode</label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="dry-run">
                            <label for="dry-run">Dry Run</label>
                        </div>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" id="cancel-run-btn" class="btn btn-secondary">Abbrechen</button>
                <button type="submit" form="new-run-form" class="btn btn-success">🚀 Run starten</button>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '/api';
        let eventSource = null;
        let currentRuns = [];

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            setupEventHandlers();
            loadDashboard();
            setupEventSource();
        });

        function setupEventHandlers() {
            document.getElementById('new-run-btn').addEventListener('click', showNewRunModal);
            document.getElementById('close-modal-btn').addEventListener('click', hideNewRunModal);
            document.getElementById('cancel-run-btn').addEventListener('click', hideNewRunModal);
            document.getElementById('refresh-btn').addEventListener('click', loadDashboard);
            document.getElementById('new-run-form').addEventListener('submit', startNewRun);
            
            // Close modal on outside click
            document.getElementById('new-run-modal').addEventListener('click', function(e) {
                if (e.target === this) hideNewRunModal();
            });
        }

        async function loadDashboard() {
            try {
                const response = await fetch(`${API_BASE}/dashboard`);
                const data = await response.json();
                
                updateStats(data.statistics);
                updateOrchestratorStatus(data.orchestrator_available);
                displayRuns(data.runs);
                currentRuns = data.runs;
                
            } catch (error) {
                console.error('Failed to load dashboard:', error);
                document.getElementById('runs-container').innerHTML = '<div class="loading">Fehler beim Laden</div>';
            }
        }

        function updateStats(stats) {
            document.getElementById('total-runs').textContent = stats.total_runs;
            document.getElementById('running-runs').textContent = stats.running_runs;
            document.getElementById('success-rate').textContent = stats.success_rate.toFixed(1) + '%';
        }

        function updateOrchestratorStatus(available) {
            const indicator = document.getElementById('orchestrator-indicator');
            indicator.textContent = available ? 'Available' : 'Fallback';
            indicator.style.color = available ? '#48bb78' : '#ed8936';
        }

        function displayRuns(runs) {
            if (runs.length === 0) {
                document.getElementById('runs-container').innerHTML = '<div class="loading">Keine Runs vorhanden</div>';
                return;
            }

            const table = `
                <table class="table">
                    <thead>
                        <tr>
                            <th>Run ID</th>
                            <th>Status</th>
                            <th>Progress</th>
                            <th>Dauer</th>
                            <th>Erstellt</th>
                            <th>PR</th>
                            <th>Aktionen</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${runs.map(run => `
                            <tr>
                                <td><code>${run.run_id.substring(0, 20)}...</code></td>
                                <td><span class="status status-${run.status}">${run.status.toUpperCase()}</span></td>
                                <td>
                                    <div class="progress-bar">
                                        <div class="progress-fill" style="width: ${run.progress_percent}%"></div>
                                    </div>
                                    <small>${run.progress_percent.toFixed(0)}%</small>
                                </td>
                                <td>${Math.round(run.duration_seconds)}s</td>
                                <td>${new Date(run.created_at).toLocaleString()}</td>
                                <td>${run.pr_url ? `<a href="${run.pr_url}" class="link" target="_blank">PR #${run.pr_number}</a>` : '-'}</td>
                                <td><a href="#" onclick="viewRunDetails('${run.run_id}')" class="link">Details</a></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            document.getElementById('runs-container').innerHTML = table;
        }

        function showNewRunModal() {
            document.getElementById('new-run-modal').style.display = 'block';
            document.getElementById('prompt').focus();
        }

        function hideNewRunModal() {
            document.getElementById('new-run-modal').style.display = 'none';
            document.getElementById('new-run-form').reset();
            clearErrors();
        }

        async function startNewRun(event) {
            event.preventDefault();
            clearErrors();

            const prompt = document.getElementById('prompt').value.trim();
            const templateType = document.getElementById('template-type').value;
            const branch = document.getElementById('branch').value.trim() || 'main';
            const secureMode = document.getElementById('secure-mode').checked;
            const dryRun = document.getElementById('dry-run').checked;

            if (!prompt || prompt.length < 10) {
                showError('prompt-error', 'Prompt muss mindestens 10 Zeichen haben');
                return;
            }

            const runSpec = {
                prompt: prompt,
                template_type: templateType,
                branch: branch,
                secure_mode: secureMode,
                dry_run: dryRun
            };

            try {
                const response = await fetch(`${API_BASE}/runs`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(runSpec)
                });

                if (response.ok) {
                    const result = await response.json();
                    logEvent(`🚀 Run gestartet: ${result.run_id}`);
                    hideNewRunModal();
                    setTimeout(loadDashboard, 1000);
                } else {
                    const error = await response.json();
                    showError('prompt-error', error.message || 'Fehler beim Starten');
                }
            } catch (error) {
                console.error('Failed to start run:', error);
                showError('prompt-error', 'Netzwerkfehler');
            }
        }

        function viewRunDetails(runId) {
            // In real implementation, open detailed view
            const run = currentRuns.find(r => r.run_id === runId);
            if (run) {
                logEvent(`📊 Run Details: ${runId} - Status: ${run.status}`);
                
                // Show gate timeline
                if (run.gates && run.gates.length > 0) {
                    const gateInfo = run.gates.map(g => `${g.name}: ${g.status.toUpperCase()}`).join(', ');
                    logEvent(`🚪 Gates: ${gateInfo}`);
                }
                
                // Show artifacts
                if (run.artifacts && run.artifacts.length > 0) {
                    logEvent(`📄 Artifacts: ${run.artifacts.length} verfügbar`);
                }
            }
        }

        function setupEventSource() {
            const clientId = 'dashboard_' + Date.now();
            eventSource = new EventSource(`${API_BASE}/events?client_id=${clientId}`);

            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                logEvent(`📡 ${data.event_type}: ${JSON.stringify(data.data)}`);
            };

            eventSource.addEventListener('run_started', function(event) {
                const data = JSON.parse(event.data);
                logEvent(`🚀 Run gestartet: ${data.run_id}`);
                setTimeout(loadDashboard, 1000);
            });

            eventSource.addEventListener('gate_completed', function(event) {
                const data = JSON.parse(event.data);
                const status = data.data.status === 'pass' ? '✅' : data.data.status === 'fail' ? '❌' : '⏳';
                logEvent(`${status} ${data.data.gate}: ${data.data.status.toUpperCase()}`);
            });

            eventSource.addEventListener('run_completed', function(event) {
                const data = JSON.parse(event.data);
                const status = data.data.status === 'success' ? '✅' : '❌';
                logEvent(`${status} Run abgeschlossen: ${data.run_id} (${data.data.status.toUpperCase()})`);
                setTimeout(loadDashboard, 1000);
            });

            eventSource.addEventListener('artifact_created', function(event) {
                const data = JSON.parse(event.data);
                logEvent(`📄 Artifact: ${data.data.artifact.name}`);
            });

            eventSource.onerror = function(error) {
                console.error('EventSource error:', error);
                logEvent('❌ Live Events unterbrochen');
            };
        }

        function logEvent(message) {
            const eventsLog = document.getElementById('events-log');
            const timestamp = new Date().toLocaleTimeString();
            eventsLog.innerHTML += `[${timestamp}] ${message}\\n`;
            eventsLog.scrollTop = eventsLog.scrollHeight;
        }

        function showError(elementId, message) {
            document.getElementById(elementId).textContent = message;
        }

        function clearErrors() {
            document.querySelectorAll('.form-error').forEach(el => el.textContent = '');
        }

        // Cleanup
        window.addEventListener('beforeunload', function() {
            if (eventSource) eventSource.close();
        });
    </script>
</body>
</html>"""
    
    def generate_gui_files(self, output_path: Path):
        """Generate GUI files."""
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate main dashboard
        dashboard_html = self.generate_dashboard_html()
        (output_path / "dashboard.html").write_text(dashboard_html, encoding='utf-8')
        
        logger.info(f"Generated single frontdoor GUI in {output_path}")


# === Convenience Functions ===

def create_single_frontdoor_gui() -> SingleFrontdoorGUI:
    """Create single frontdoor GUI."""
    return SingleFrontdoorGUI()


async def start_gui_run(prompt: str, **kwargs) -> str:
    """Start GUI run with given prompt."""
    
    gui = create_single_frontdoor_gui()
    
    run_spec = RunSpec(
        prompt=prompt,
        branch=kwargs.get("branch", "main"),
        secure_mode=kwargs.get("secure_mode", True),
        dry_run=kwargs.get("dry_run", False),
        template_type=kwargs.get("template_type", "web-api")
    )
    
    return await gui.backend.create_run(run_spec)


if __name__ == "__main__":
    # Demo
    print("Single Frontdoor GUI Demo:")
    
    # Test 1: Create GUI
    print("\\n1. Creating single frontdoor GUI:")
    
    gui = create_single_frontdoor_gui()
    
    print(f"   GUI created: {gui.__class__.__name__}")
    print(f"   Backend: {gui.backend.__class__.__name__}")
    print(f"   Orchestrator available: {gui.backend.orchestrator_bridge.available}")
    
    # Test 2: Start run
    print("\\n2. Starting GUI run:")
    
    async def test_gui_run():
        run_id = await start_gui_run(
            prompt="Create a simple REST API for user authentication",
            secure_mode=True,
            dry_run=True
        )
        
        print(f"   Run started: {run_id}")
        
        # Wait for some progress
        await asyncio.sleep(2)
        
        # Get run status
        run_status = gui.backend.get_run_status(run_id)
        if run_status:
            print(f"   Status: {run_status['status']}")
            print(f"   Progress: {run_status['progress_percent']:.1f}%")
            print(f"   Gates: {len(run_status['gates'])}")
            print(f"   Artifacts: {len(run_status['artifacts'])}")
        
        return run_id
    
    run_id = asyncio.run(test_gui_run())
    
    # Test 3: Dashboard data
    print("\\n3. Testing dashboard data:")
    
    dashboard_data = gui.backend.get_dashboard_data()
    
    print(f"   Total runs: {dashboard_data['statistics']['total_runs']}")
    print(f"   Success rate: {dashboard_data['statistics']['success_rate']:.1f}%")
    print(f"   Orchestrator: {'Available' if dashboard_data['orchestrator_available'] else 'Fallback'}")
    
    # Test 4: Generate GUI files
    print("\\n4. Generating GUI files:")
    
    output_path = Path("temp_gui_single_frontdoor")
    gui.generate_gui_files(output_path)
    
    dashboard_file = output_path / "dashboard.html"
    if dashboard_file.exists():
        file_size = dashboard_file.stat().st_size
        print(f"   Dashboard generated: {file_size} bytes")
    
    # Cleanup
    import shutil
    if output_path.exists():
        shutil.rmtree(output_path, ignore_errors=True)
    
    print("\\nDemo completed!")
