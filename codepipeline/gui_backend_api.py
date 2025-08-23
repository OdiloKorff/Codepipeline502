"""
GUI Backend API für CodePipeline Management.

Implementiert:
- ID 412: GUI Backend – Runs API & Orchestrator-Bridge
- ID 413: GUI Backend – Live-Events (SSE/WebSocket)
- ID 414: GUI Frontend – Dashboard (Backend-Support)
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
import logging
from threading import Thread, Lock
import queue
import zipfile
import io

# FastAPI imports (would be installed in real implementation)
try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
    from fastapi.responses import StreamingResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    # Mock for demo purposes
    class FastAPI:
        def __init__(self, **kwargs): pass
        def get(self, path): return lambda f: f
        def post(self, path): return lambda f: f
        def put(self, path): return lambda f: f
        def delete(self, path): return lambda f: f
        def add_middleware(self, *args, **kwargs): pass
    
    class HTTPException(Exception):
        def __init__(self, status_code, detail): 
            self.status_code = status_code
            self.detail = detail
    
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class BackgroundTasks:
        def add_task(self, func, *args): pass
    
    class Request: pass
    class StreamingResponse: pass
    class FileResponse: pass
    class CORSMiddleware: pass
    
    def uvicorn_run(*args, **kwargs): pass
    uvicorn = type('uvicorn', (), {'run': uvicorn_run})()
    
    FASTAPI_AVAILABLE = False


logger = logging.getLogger(__name__)


# === ID 412: GUI Backend – Runs API & Orchestrator-Bridge ===

class RunStatus(Enum):
    """Run status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GateStatus(Enum):
    """Gate status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class GateResult:
    """Gate execution result."""
    
    gate_name: str
    status: GateStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Gate-specific data
    details: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "details": self.details,
            "artifacts": self.artifacts,
            "logs": self.logs
        }


@dataclass
class PipelineRun:
    """Pipeline run."""
    
    run_id: str
    spec: Dict[str, Any]
    status: RunStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Run metadata
    template_type: str = ""
    deploy_profile: str = ""
    commit_sha: str = ""
    pr_number: Optional[int] = None
    pr_url: str = ""
    
    # Gates and results
    gates: Dict[str, GateResult] = field(default_factory=dict)
    
    # Artifacts and logs
    artifacts: Dict[str, str] = field(default_factory=dict)  # name -> path
    log_entries: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metrics
    coverage_percentage: float = 0.0
    scorecard_score: int = 0
    active_security_tools: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        """Get run duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "spec": self.spec,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "template_type": self.template_type,
            "deploy_profile": self.deploy_profile,
            "commit_sha": self.commit_sha,
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "gates": {name: gate.to_dict() for name, gate in self.gates.items()},
            "artifacts": self.artifacts,
            "log_entries": self.log_entries,
            "coverage_percentage": self.coverage_percentage,
            "scorecard_score": self.scorecard_score,
            "active_security_tools": self.active_security_tools
        }


# Pydantic models for API
class RunSpecModel(BaseModel):
    """Run specification model."""
    
    prompt: str
    template_type: Optional[str] = None
    deploy_profile: Optional[str] = None
    secure_mode: bool = True
    seed: Optional[str] = None


class RunFilterModel(BaseModel):
    """Run filter model."""
    
    status: Optional[str] = None
    template_type: Optional[str] = None
    deploy_profile: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0


# === ID 413: GUI Backend – Live-Events (SSE/WebSocket) ===

@dataclass
class LiveEvent:
    """Live event."""
    
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
        """Convert to Server-Sent Events format."""
        data = json.dumps(self.to_dict())
        return f"event: {self.event_type}\\ndata: {data}\\n\\n"


class EventBroadcaster:
    """Event broadcaster for live updates."""
    
    def __init__(self):
        self.clients: Dict[str, queue.Queue] = {}
        self.lock = Lock()
    
    def add_client(self, client_id: str) -> queue.Queue:
        """Add client for live updates."""
        with self.lock:
            client_queue = queue.Queue(maxsize=100)
            self.clients[client_id] = client_queue
            return client_queue
    
    def remove_client(self, client_id: str):
        """Remove client."""
        with self.lock:
            self.clients.pop(client_id, None)
    
    def broadcast_event(self, event: LiveEvent):
        """Broadcast event to all clients."""
        with self.lock:
            dead_clients = []
            
            for client_id, client_queue in self.clients.items():
                try:
                    client_queue.put_nowait(event)
                except queue.Full:
                    # Client queue full, remove client
                    dead_clients.append(client_id)
            
            # Remove dead clients
            for client_id in dead_clients:
                self.clients.pop(client_id, None)
    
    def get_client_count(self) -> int:
        """Get number of connected clients."""
        with self.lock:
            return len(self.clients)


# === Main Backend Class ===

class CodePipelineBackend:
    """CodePipeline GUI Backend."""
    
    def __init__(self):
        self.app = FastAPI(title="CodePipeline Backend", version="1.0.0")
        
        # CORS middleware
        if FASTAPI_AVAILABLE:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        
        # Data storage (in production, use database)
        self.runs: Dict[str, PipelineRun] = {}
        self.runs_lock = Lock()
        
        # Event broadcasting
        self.event_broadcaster = EventBroadcaster()
        
        # Orchestrator bridge (would import real orchestrator)
        self.orchestrator = MockOrchestrator(self)
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes."""
        
        @self.app.get("/api/runs")
        async def get_runs(
            status: Optional[str] = None,
            template_type: Optional[str] = None,
            deploy_profile: Optional[str] = None,
            limit: int = 50,
            offset: int = 0
        ):
            """Get runs with optional filtering."""
            
            with self.runs_lock:
                runs = list(self.runs.values())
            
            # Apply filters
            if status:
                runs = [r for r in runs if r.status.value == status]
            if template_type:
                runs = [r for r in runs if r.template_type == template_type]
            if deploy_profile:
                runs = [r for r in runs if r.deploy_profile == deploy_profile]
            
            # Sort by created_at descending
            runs.sort(key=lambda r: r.created_at, reverse=True)
            
            # Apply pagination
            total = len(runs)
            runs = runs[offset:offset + limit]
            
            return {
                "runs": [run.to_dict() for run in runs],
                "total": total,
                "limit": limit,
                "offset": offset
            }
        
        @self.app.post("/api/runs")
        async def create_run(spec: RunSpecModel, background_tasks: BackgroundTasks):
            """Create new pipeline run."""
            
            run_id = str(uuid.uuid4())
            
            # Create run
            pipeline_run = PipelineRun(
                run_id=run_id,
                spec=spec.__dict__,
                status=RunStatus.PENDING,
                created_at=datetime.utcnow(),
                template_type=spec.template_type or "auto-detect",
                deploy_profile=spec.deploy_profile or "development"
            )
            
            # Store run
            with self.runs_lock:
                self.runs[run_id] = pipeline_run
            
            # Start run in background
            background_tasks.add_task(self._execute_run, run_id)
            
            # Broadcast event
            self.event_broadcaster.broadcast_event(LiveEvent(
                event_type="run_created",
                run_id=run_id,
                timestamp=datetime.utcnow(),
                data={"status": "pending"}
            ))
            
            return {"run_id": run_id, "status": "created"}
        
        @self.app.get("/api/runs/{run_id}")
        async def get_run(run_id: str):
            """Get run details."""
            
            with self.runs_lock:
                if run_id not in self.runs:
                    raise HTTPException(status_code=404, detail="Run not found")
                
                run = self.runs[run_id]
            
            return run.to_dict()
        
        @self.app.post("/api/runs/{run_id}/cancel")
        async def cancel_run(run_id: str):
            """Cancel running pipeline."""
            
            with self.runs_lock:
                if run_id not in self.runs:
                    raise HTTPException(status_code=404, detail="Run not found")
                
                run = self.runs[run_id]
                if run.status == RunStatus.RUNNING:
                    run.status = RunStatus.CANCELLED
                    run.completed_at = datetime.utcnow()
            
            # Broadcast event
            self.event_broadcaster.broadcast_event(LiveEvent(
                event_type="run_cancelled",
                run_id=run_id,
                timestamp=datetime.utcnow(),
                data={"status": "cancelled"}
            ))
            
            return {"status": "cancelled"}
        
        @self.app.post("/api/spec/validate")
        async def validate_spec(spec: RunSpecModel):
            """Validate run specification."""
            
            errors = []
            warnings = []
            
            # Validate prompt
            if not spec.prompt.strip():
                errors.append("Prompt cannot be empty")
            
            if len(spec.prompt) < 10:
                warnings.append("Prompt is very short, consider adding more details")
            
            # Validate template type
            valid_templates = ["cli", "web-api", "worker", "batch"]
            if spec.template_type and spec.template_type not in valid_templates:
                errors.append(f"Invalid template type. Valid options: {', '.join(valid_templates)}")
            
            # Validate deploy profile
            valid_profiles = ["development", "staging", "production"]
            if spec.deploy_profile and spec.deploy_profile not in valid_profiles:
                errors.append(f"Invalid deploy profile. Valid options: {', '.join(valid_profiles)}")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings
            }
        
        @self.app.get("/api/runs/{run_id}/artifacts")
        async def get_run_artifacts(run_id: str):
            """Get run artifacts list."""
            
            with self.runs_lock:
                if run_id not in self.runs:
                    raise HTTPException(status_code=404, detail="Run not found")
                
                run = self.runs[run_id]
            
            artifacts = []
            for name, path in run.artifacts.items():
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    artifacts.append({
                        "name": name,
                        "size": size,
                        "download_url": f"/api/runs/{run_id}/artifacts/{name}/download"
                    })
            
            return {"artifacts": artifacts}
        
        @self.app.get("/api/runs/{run_id}/artifacts/{artifact_name}/download")
        async def download_artifact(run_id: str, artifact_name: str):
            """Download run artifact."""
            
            with self.runs_lock:
                if run_id not in self.runs:
                    raise HTTPException(status_code=404, detail="Run not found")
                
                run = self.runs[run_id]
            
            if artifact_name not in run.artifacts:
                raise HTTPException(status_code=404, detail="Artifact not found")
            
            artifact_path = run.artifacts[artifact_name]
            if not os.path.exists(artifact_path):
                raise HTTPException(status_code=404, detail="Artifact file not found")
            
            return FileResponse(artifact_path, filename=artifact_name)
        
        @self.app.get("/api/runs/{run_id}/logs")
        async def get_run_logs(run_id: str, limit: int = 100, offset: int = 0):
            """Get run logs."""
            
            with self.runs_lock:
                if run_id not in self.runs:
                    raise HTTPException(status_code=404, detail="Run not found")
                
                run = self.runs[run_id]
            
            total = len(run.log_entries)
            logs = run.log_entries[offset:offset + limit]
            
            return {
                "logs": logs,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        
        @self.app.get("/api/runs/{run_id}/events")
        async def stream_run_events(run_id: str, request: Request):
            """Stream run events via Server-Sent Events."""
            
            client_id = str(uuid.uuid4())
            client_queue = self.event_broadcaster.add_client(client_id)
            
            async def event_generator():
                try:
                    # Send initial connection event
                    yield f"event: connected\\ndata: {{\"client_id\": \"{client_id}\"}}\\n\\n"
                    
                    while True:
                        try:
                            # Get event from queue (with timeout)
                            event = client_queue.get(timeout=30)
                            
                            # Filter events for this run
                            if event.run_id == run_id or event.event_type == "heartbeat":
                                yield event.to_sse_format()
                        
                        except queue.Empty:
                            # Send heartbeat
                            heartbeat = LiveEvent(
                                event_type="heartbeat",
                                run_id="",
                                timestamp=datetime.utcnow()
                            )
                            yield heartbeat.to_sse_format()
                        
                        except Exception as e:
                            logger.error(f"Event stream error: {e}")
                            break
                
                finally:
                    self.event_broadcaster.remove_client(client_id)
            
            return StreamingResponse(event_generator(), media_type="text/plain")
        
        @self.app.get("/api/dashboard/metrics")
        async def get_dashboard_metrics():
            """Get dashboard metrics."""
            
            with self.runs_lock:
                runs = list(self.runs.values())
            
            if not runs:
                return {
                    "total_runs": 0,
                    "success_rate": 0.0,
                    "avg_duration": 0.0,
                    "coverage_median": 0.0,
                    "active_scanners": 0,
                    "recent_runs": []
                }
            
            # Calculate metrics
            total_runs = len(runs)
            successful_runs = len([r for r in runs if r.status == RunStatus.SUCCESS])
            success_rate = successful_runs / total_runs if total_runs > 0 else 0.0
            
            # Average duration (completed runs only)
            completed_runs = [r for r in runs if r.completed_at]
            avg_duration = sum(r.duration_seconds for r in completed_runs) / len(completed_runs) if completed_runs else 0.0
            
            # Coverage median
            coverages = [r.coverage_percentage for r in runs if r.coverage_percentage > 0]
            coverage_median = sorted(coverages)[len(coverages) // 2] if coverages else 0.0
            
            # Active scanners (unique)
            all_scanners = set()
            for run in runs:
                all_scanners.update(run.active_security_tools)
            
            # Recent runs (last 10)
            recent_runs = sorted(runs, key=lambda r: r.created_at, reverse=True)[:10]
            
            return {
                "total_runs": total_runs,
                "success_rate": success_rate,
                "avg_duration": avg_duration,
                "coverage_median": coverage_median,
                "active_scanners": len(all_scanners),
                "recent_runs": [run.to_dict() for run in recent_runs]
            }
    
    async def _execute_run(self, run_id: str):
        """Execute pipeline run (background task)."""
        
        # Delegate to orchestrator
        await self.orchestrator.execute_pipeline(run_id)
    
    def add_log_entry(self, run_id: str, level: str, message: str, gate: str = ""):
        """Add log entry to run."""
        
        with self.runs_lock:
            if run_id in self.runs:
                log_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": level,
                    "message": message,
                    "gate": gate
                }
                self.runs[run_id].log_entries.append(log_entry)
        
        # Broadcast log event
        self.event_broadcaster.broadcast_event(LiveEvent(
            event_type="log_entry",
            run_id=run_id,
            timestamp=datetime.utcnow(),
            data={"level": level, "message": message, "gate": gate}
        ))
    
    def update_gate_status(self, run_id: str, gate_name: str, status: GateStatus, details: Dict[str, Any] = None):
        """Update gate status."""
        
        with self.runs_lock:
            if run_id in self.runs:
                run = self.runs[run_id]
                
                if gate_name not in run.gates:
                    run.gates[gate_name] = GateResult(gate_name=gate_name, status=status)
                
                gate = run.gates[gate_name]
                gate.status = status
                
                if status == GateStatus.RUNNING and not gate.start_time:
                    gate.start_time = datetime.utcnow()
                elif status in [GateStatus.PASSED, GateStatus.FAILED] and gate.start_time:
                    gate.end_time = datetime.utcnow()
                    gate.duration_seconds = (gate.end_time - gate.start_time).total_seconds()
                
                if details:
                    gate.details.update(details)
        
        # Broadcast gate event
        self.event_broadcaster.broadcast_event(LiveEvent(
            event_type="gate_updated",
            run_id=run_id,
            timestamp=datetime.utcnow(),
            data={"gate_name": gate_name, "status": status.value, "details": details or {}}
        ))
    
    def add_artifact(self, run_id: str, artifact_name: str, artifact_path: str):
        """Add artifact to run."""
        
        with self.runs_lock:
            if run_id in self.runs:
                self.runs[run_id].artifacts[artifact_name] = artifact_path
        
        # Broadcast artifact event
        self.event_broadcaster.broadcast_event(LiveEvent(
            event_type="artifact_added",
            run_id=run_id,
            timestamp=datetime.utcnow(),
            data={"artifact_name": artifact_name}
        ))
    
    def run_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Run backend server."""
        
        if FASTAPI_AVAILABLE:
            uvicorn.run(self.app, host=host, port=port)
        else:
            logger.warning("FastAPI not available, running in mock mode")
            print(f"Mock backend server running on {host}:{port}")


# === Mock Orchestrator (Bridge to CLI) ===

class MockOrchestrator:
    """Mock orchestrator that bridges to CLI functionality."""
    
    def __init__(self, backend: CodePipelineBackend):
        self.backend = backend
    
    async def execute_pipeline(self, run_id: str):
        """Execute pipeline (mock implementation)."""
        
        # Update run status
        with self.backend.runs_lock:
            if run_id in self.backend.runs:
                run = self.backend.runs[run_id]
                run.status = RunStatus.RUNNING
                run.started_at = datetime.utcnow()
        
        # Broadcast start event
        self.backend.event_broadcaster.broadcast_event(LiveEvent(
            event_type="run_started",
            run_id=run_id,
            timestamp=datetime.utcnow(),
            data={"status": "running"}
        ))
        
        try:
            # Simulate pipeline gates
            gates = [
                "scaffold", "build", "test", "security", 
                "sbom", "container", "deploy", "validate"
            ]
            
            for gate_name in gates:
                # Start gate
                self.backend.add_log_entry(run_id, "INFO", f"Starting {gate_name} gate", gate_name)
                self.backend.update_gate_status(run_id, gate_name, GateStatus.RUNNING)
                
                # Simulate work
                await asyncio.sleep(1)  # Simulate gate execution
                
                # Complete gate (most gates pass)
                if gate_name == "security" and run_id.endswith("fail"):
                    # Simulate security failure
                    self.backend.update_gate_status(run_id, gate_name, GateStatus.FAILED, {
                        "error": "High severity security findings detected"
                    })
                    self.backend.add_log_entry(run_id, "ERROR", f"{gate_name} gate failed", gate_name)
                    raise Exception("Security gate failed")
                else:
                    self.backend.update_gate_status(run_id, gate_name, GateStatus.PASSED, {
                        "duration": 1.0
                    })
                    self.backend.add_log_entry(run_id, "INFO", f"{gate_name} gate passed", gate_name)
                
                # Add some artifacts
                if gate_name in ["build", "container", "sbom"]:
                    artifact_name = f"{gate_name}_output.zip"
                    artifact_path = self._create_mock_artifact(artifact_name)
                    self.backend.add_artifact(run_id, artifact_name, artifact_path)
            
            # Success
            with self.backend.runs_lock:
                if run_id in self.backend.runs:
                    run = self.backend.runs[run_id]
                    run.status = RunStatus.SUCCESS
                    run.completed_at = datetime.utcnow()
                    run.coverage_percentage = 87.5
                    run.scorecard_score = 92
                    run.active_security_tools = ["trivy", "grype", "bandit", "semgrep"]
                    run.pr_url = f"https://github.com/example/repo/pull/{run_id[:8]}"
            
            self.backend.event_broadcaster.broadcast_event(LiveEvent(
                event_type="run_completed",
                run_id=run_id,
                timestamp=datetime.utcnow(),
                data={"status": "success"}
            ))
            
        except Exception as e:
            # Failure
            with self.backend.runs_lock:
                if run_id in self.backend.runs:
                    run = self.backend.runs[run_id]
                    run.status = RunStatus.FAILED
                    run.completed_at = datetime.utcnow()
            
            self.backend.add_log_entry(run_id, "ERROR", f"Pipeline failed: {e}")
            
            self.backend.event_broadcaster.broadcast_event(LiveEvent(
                event_type="run_failed",
                run_id=run_id,
                timestamp=datetime.utcnow(),
                data={"status": "failed", "error": str(e)}
            ))
    
    def _create_mock_artifact(self, artifact_name: str) -> str:
        """Create mock artifact file."""
        
        temp_dir = Path(tempfile.gettempdir()) / "codepipeline_artifacts"
        temp_dir.mkdir(exist_ok=True)
        
        artifact_path = temp_dir / artifact_name
        
        # Create a simple zip file with mock content
        with zipfile.ZipFile(artifact_path, 'w') as zf:
            zf.writestr("README.txt", f"This is a mock {artifact_name} artifact")
            zf.writestr("metadata.json", json.dumps({
                "artifact_type": artifact_name.split('_')[0],
                "created_at": datetime.utcnow().isoformat(),
                "size": "mock"
            }))
        
        return str(artifact_path)


# === Convenience Functions ===

def create_backend() -> CodePipelineBackend:
    """Create CodePipeline backend."""
    return CodePipelineBackend()


def run_backend_server(host: str = "0.0.0.0", port: int = 8000):
    """Run backend server."""
    backend = create_backend()
    backend.run_server(host, port)


if __name__ == "__main__":
    # Demo
    def demo_backend():
        print("CodePipeline Backend Demo:")
        
        # Create backend
        backend = create_backend()
        
        print(f"Backend created with {len(backend.runs)} runs")
        print(f"Event broadcaster has {backend.event_broadcaster.get_client_count()} clients")
        
        # Create mock run
        import asyncio
        
        async def create_demo_run():
            # Simulate API call
            spec = RunSpecModel(
                prompt="Create a simple web API",
                template_type="web-api",
                deploy_profile="development"
            )
            
            run_id = str(uuid.uuid4())
            pipeline_run = PipelineRun(
                run_id=run_id,
                spec=spec.__dict__,
                status=RunStatus.PENDING,
                created_at=datetime.utcnow(),
                template_type="web-api",
                deploy_profile="development"
            )
            
            backend.runs[run_id] = pipeline_run
            
            print(f"Created demo run: {run_id}")
            
            # Execute pipeline
            await backend.orchestrator.execute_pipeline(run_id)
            
            # Check results
            final_run = backend.runs[run_id]
            print(f"Run completed with status: {final_run.status.value}")
            print(f"Gates: {len(final_run.gates)}")
            print(f"Artifacts: {len(final_run.artifacts)}")
            print(f"Log entries: {len(final_run.log_entries)}")
            
            return final_run.status == RunStatus.SUCCESS
        
        # Run demo
        try:
            result = asyncio.run(create_demo_run())
            print(f"Demo completed successfully: {result}")
            return result
        except Exception as e:
            print(f"Demo failed: {e}")
            return False
    
    # Run demo
    demo_backend()
