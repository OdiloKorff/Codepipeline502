"""
Ultimate GUI Suite für CodePipeline.

Implementiert:
- BL-015: GUI: sichere Artefakt-Downloads & Live-Logs
- BL-016: Remote-CI Required-Checks an Scorecard koppeln
- BL-017: GUI-Start als Standard-Entry (Single Frontdoor)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator, Union
import logging

try:
    from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
    from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None
    HTTPException = None
    StreamingResponse = None


logger = logging.getLogger(__name__)


# === BL-015: GUI: sichere Artefakt-Downloads & Live-Logs ===

@dataclass
class ArtifactDownloadRequest:
    """Artifact download request."""
    
    artifact_id: str
    artifact_type: str  # qa, sbom, security, coverage, run_meta
    run_id: str
    
    user_agent: str = ""
    client_ip: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "run_id": self.run_id,
            "user_agent": self.user_agent,
            "client_ip": self.client_ip,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ArtifactDownloadResult:
    """Artifact download result."""
    
    success: bool = False
    file_path: Optional[str] = None
    content_type: str = ""
    file_size: int = 0
    
    error_message: str = ""
    security_blocked: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "file_path": self.file_path,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "error_message": self.error_message,
            "security_blocked": self.security_blocked
        }


@dataclass
class LiveLogEntry:
    """Live log entry."""
    
    timestamp: datetime
    level: str  # INFO, WARN, ERROR, DEBUG
    message: str
    source: str = ""
    run_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "source": self.source,
            "run_id": self.run_id
        }


class SecureArtifactDownloader:
    """Secure artifact downloader with content-type whitelist."""
    
    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Content-type whitelist for security
        self.allowed_content_types = {
            # Text formats
            "text/plain": [".txt", ".log"],
            "text/xml": [".xml"],
            "application/xml": [".xml"],
            "application/json": [".json"],
            "text/csv": [".csv"],
            "text/markdown": [".md"],
            
            # Archive formats
            "application/zip": [".zip"],
            "application/gzip": [".gz"],
            "application/x-tar": [".tar"],
            
            # Report formats
            "application/pdf": [".pdf"],
            "text/html": [".html", ".htm"],
            
            # SBOM formats
            "application/spdx+json": [".spdx.json"],
            "application/vnd.cyclonedx+json": [".cdx.json"]
        }
        
        # Maximum file size for streaming (100MB)
        self.max_stream_size = 100 * 1024 * 1024
        
        # Secret patterns for redaction
        self.secret_patterns = [
            r"password['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"token['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"key['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"secret['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"api[_-]?key['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
            r"access[_-]?token['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]"
        ]
    
    def validate_artifact_request(self, request: ArtifactDownloadRequest) -> ArtifactDownloadResult:
        """Validate artifact download request."""
        
        result = ArtifactDownloadResult()
        
        try:
            # 1. Find artifact file
            artifact_path = self._find_artifact_file(request)
            if not artifact_path:
                result.error_message = f"Artifact not found: {request.artifact_type} for run {request.run_id}"
                return result
            
            # 2. Check file size
            file_size = artifact_path.stat().st_size
            result.file_size = file_size
            
            if file_size > self.max_stream_size:
                result.error_message = f"File too large for download: {file_size} bytes (max: {self.max_stream_size})"
                return result
            
            # 3. Determine and validate content type
            content_type = self._get_content_type(artifact_path)
            if not self._is_content_type_allowed(content_type, artifact_path.suffix):
                result.security_blocked = True
                result.error_message = f"Content type not allowed: {content_type}"
                return result
            
            # 4. Success
            result.success = True
            result.file_path = str(artifact_path)
            result.content_type = content_type
            
            logger.info(f"Artifact download validated: {request.artifact_type} ({file_size} bytes, {content_type})")
            
        except Exception as e:
            result.error_message = f"Validation error: {e}"
            logger.error(f"Artifact validation failed: {e}")
        
        return result
    
    def _find_artifact_file(self, request: ArtifactDownloadRequest) -> Optional[Path]:
        """Find artifact file."""
        
        # Look for artifact in run directory
        run_dir = self.artifacts_dir / request.run_id
        if not run_dir.exists():
            return None
        
        # Artifact type to file patterns
        artifact_patterns = {
            "qa": ["qa_summary.json", "qa_report.json", "quality.json"],
            "sbom": ["sbom.json", "software_bill_of_materials.json", "*.spdx.json", "*.cdx.json"],
            "security": ["security_report.json", "security_consolidated.json", "security.json"],
            "coverage": ["coverage.xml", "coverage.json", "coverage_report.xml"],
            "run_meta": ["run_meta.json", "pipeline_meta.json", "metadata.json"]
        }
        
        patterns = artifact_patterns.get(request.artifact_type, [request.artifact_type])
        
        for pattern in patterns:
            if "*" in pattern:
                # Glob pattern
                matches = list(run_dir.glob(pattern))
                if matches:
                    return matches[0]
            else:
                # Direct file
                file_path = run_dir / pattern
                if file_path.exists():
                    return file_path
        
        return None
    
    def _get_content_type(self, file_path: Path) -> str:
        """Get content type for file."""
        
        # Use mimetypes to guess
        content_type, _ = mimetypes.guess_type(str(file_path))
        
        if content_type:
            return content_type
        
        # Fallback based on extension
        suffix = file_path.suffix.lower()
        
        fallback_types = {
            ".json": "application/json",
            ".xml": "application/xml",
            ".txt": "text/plain",
            ".log": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".html": "text/html",
            ".pdf": "application/pdf",
            ".zip": "application/zip"
        }
        
        return fallback_types.get(suffix, "application/octet-stream")
    
    def _is_content_type_allowed(self, content_type: str, file_suffix: str) -> bool:
        """Check if content type is allowed."""
        
        if content_type in self.allowed_content_types:
            allowed_extensions = self.allowed_content_types[content_type]
            return file_suffix.lower() in allowed_extensions
        
        return False
    
    async def stream_artifact(self, result: ArtifactDownloadResult) -> AsyncGenerator[bytes, None]:
        """Stream artifact file."""
        
        if not result.success or not result.file_path:
            yield b"Error: Invalid artifact"
            return
        
        try:
            file_path = Path(result.file_path)
            
            # Stream file in chunks
            chunk_size = 8192
            
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    
                    # Small delay to prevent overwhelming
                    await asyncio.sleep(0.001)
        
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"Error streaming file: {e}".encode()


class LiveLogViewer:
    """Live log viewer with backlog protection."""
    
    def __init__(self, max_entries: int = 1000, max_entry_size: int = 1024):
        self.max_entries = max_entries
        self.max_entry_size = max_entry_size
        
        self.log_entries: List[LiveLogEntry] = []
        self.subscribers: Dict[str, asyncio.Queue] = {}
        self.lock = threading.Lock()
        
        # Secret redaction patterns
        self.secret_patterns = [
            (r"password['\"]?\s*[:=]\s*['\"]?([^'\"\\s]+)['\"]?", "password=***"),
            (r"token['\"]?\s*[:=]\s*['\"]?([^'\"\\s]+)['\"]?", "token=***"),
            (r"key['\"]?\s*[:=]\s*['\"]?([^'\"\\s]+)['\"]?", "key=***"),
            (r"secret['\"]?\s*[:=]\s*['\"]?([^'\"\\s]+)['\"]?", "secret=***"),
            (r"api[_-]?key['\"]?\s*[:=]\s*['\"]?([^'\"\\s]+)['\"]?", "api_key=***"),
            (r"Bearer\s+([A-Za-z0-9\-_.]+)", "Bearer ***"),
            (r"Basic\s+([A-Za-z0-9+/=]+)", "Basic ***")
        ]
    
    def add_log_entry(self, level: str, message: str, source: str = "", run_id: str = ""):
        """Add log entry with secret redaction."""
        
        # Redact secrets
        redacted_message = self._redact_secrets(message)
        
        # Truncate if too long
        if len(redacted_message) > self.max_entry_size:
            redacted_message = redacted_message[:self.max_entry_size - 3] + "..."
        
        entry = LiveLogEntry(
            timestamp=datetime.utcnow(),
            level=level,
            message=redacted_message,
            source=source,
            run_id=run_id
        )
        
        with self.lock:
            # Add to log entries
            self.log_entries.append(entry)
            
            # Maintain max entries (backlog protection)
            if len(self.log_entries) > self.max_entries:
                self.log_entries = self.log_entries[-self.max_entries:]
            
            # Notify subscribers
            self._notify_subscribers(entry)
    
    def _redact_secrets(self, message: str) -> str:
        """Redact secrets from message."""
        
        redacted = message
        
        for pattern, replacement in self.secret_patterns:
            redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
        
        return redacted
    
    def _notify_subscribers(self, entry: LiveLogEntry):
        """Notify subscribers of new log entry."""
        
        for subscriber_id, queue in list(self.subscribers.items()):
            try:
                # Non-blocking put
                if queue.qsize() < 100:  # Prevent queue overflow
                    queue.put_nowait(entry)
                else:
                    # Remove slow subscriber
                    logger.warning(f"Removing slow log subscriber: {subscriber_id}")
                    del self.subscribers[subscriber_id]
            except Exception as e:
                logger.warning(f"Failed to notify subscriber {subscriber_id}: {e}")
                if subscriber_id in self.subscribers:
                    del self.subscribers[subscriber_id]
    
    def subscribe_to_logs(self, subscriber_id: str = None) -> Tuple[str, asyncio.Queue]:
        """Subscribe to live logs."""
        
        if not subscriber_id:
            subscriber_id = str(uuid.uuid4())
        
        queue = asyncio.Queue(maxsize=200)
        
        with self.lock:
            self.subscribers[subscriber_id] = queue
        
        logger.info(f"New log subscriber: {subscriber_id}")
        return subscriber_id, queue
    
    def unsubscribe_from_logs(self, subscriber_id: str):
        """Unsubscribe from live logs."""
        
        with self.lock:
            if subscriber_id in self.subscribers:
                del self.subscribers[subscriber_id]
                logger.info(f"Log subscriber removed: {subscriber_id}")
    
    def get_recent_logs(self, limit: int = 100, run_id: str = None) -> List[Dict[str, Any]]:
        """Get recent log entries."""
        
        with self.lock:
            entries = self.log_entries[-limit:] if limit else self.log_entries
            
            if run_id:
                entries = [e for e in entries if e.run_id == run_id]
            
            return [entry.to_dict() for entry in entries]
    
    async def stream_logs(self, subscriber_id: str) -> AsyncGenerator[str, None]:
        """Stream logs to subscriber."""
        
        if subscriber_id not in self.subscribers:
            yield "data: {\"error\": \"Invalid subscriber\"}\n\n"
            return
        
        queue = self.subscribers[subscriber_id]
        
        try:
            while subscriber_id in self.subscribers:
                try:
                    # Wait for new log entry
                    entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Send as Server-Sent Event
                    data = json.dumps(entry.to_dict())
                    yield f"data: {data}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield "data: {\"keepalive\": true}\n\n"
                
                except Exception as e:
                    logger.error(f"Log streaming error: {e}")
                    break
        
        finally:
            self.unsubscribe_from_logs(subscriber_id)


# === BL-016: Remote-CI Required-Checks an Scorecard koppeln ===

@dataclass
class RemoteCIWorkflow:
    """Remote CI workflow configuration."""
    
    name: str
    trigger_events: List[str] = field(default_factory=lambda: ["pull_request", "push"])
    required_checks: List[str] = field(default_factory=lambda: ["scorecard"])
    
    workflow_file: str = ".github/workflows/scorecard.yml"
    artifacts_publish: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "trigger_events": self.trigger_events,
            "required_checks": self.required_checks,
            "workflow_file": self.workflow_file,
            "artifacts_publish": self.artifacts_publish
        }


@dataclass
class RequiredCheckResult:
    """Required check result."""
    
    check_name: str
    status: str  # success, failure, pending
    conclusion: str = ""  # success, failure, neutral, cancelled, skipped, timed_out, action_required
    
    output_title: str = ""
    output_summary: str = ""
    details_url: str = ""
    
    artifacts: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_name": self.check_name,
            "status": self.status,
            "conclusion": self.conclusion,
            "output_title": self.output_title,
            "output_summary": self.output_summary,
            "details_url": self.details_url,
            "artifacts": self.artifacts
        }


class RemoteCIIntegration:
    """Remote CI integration with required checks."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.workflows_dir = project_root / ".github" / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_scorecard_workflow(self) -> RemoteCIWorkflow:
        """Generate minimal scorecard workflow."""
        
        workflow = RemoteCIWorkflow(
            name="Scorecard Required Check",
            trigger_events=["pull_request", "push"],
            required_checks=["scorecard"]
        )
        
        # Generate workflow YAML
        workflow_content = f'''name: {workflow.name}

on:
  pull_request:
    branches: [ main, master, develop ]
  push:
    branches: [ main, master, develop ]

jobs:
  scorecard:
    runs-on: ubuntu-latest
    name: Scorecard Gate
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .
        
    - name: Run Scorecard
      id: scorecard
      run: |
        python -m codepipeline.scorecard --secure-mode --output-format json > scorecard_result.json
        echo "result=$(cat scorecard_result.json)" >> $GITHUB_OUTPUT
        
    - name: Check Scorecard Result
      run: |
        SCORECARD_STATUS=$(python -c "import json; print(json.load(open('scorecard_result.json'))['overall_status'])")
        if [ "$SCORECARD_STATUS" != "pass" ]; then
          echo "❌ Scorecard failed: $SCORECARD_STATUS"
          exit 1
        else
          echo "✅ Scorecard passed: $SCORECARD_STATUS"
        fi
        
    - name: Upload Artifacts
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: scorecard-artifacts
        path: |
          scorecard_result.json
          qa_summary.json
          security_report.json
          coverage.xml
          run_meta.json
        retention-days: 30
        
    - name: Comment PR
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v7
      with:
        script: |
          const fs = require('fs');
          const scorecardResult = JSON.parse(fs.readFileSync('scorecard_result.json', 'utf8'));
          
          const status = scorecardResult.overall_status === 'pass' ? '✅ PASS' : '❌ FAIL';
          const coverage = scorecardResult.coverage_percent || 'N/A';
          const activeTools = scorecardResult.active_security_tools || 0;
          
          const comment = `## 📊 Scorecard Result: ${{status}}
          
          **Coverage**: ${{coverage}}%
          **Active Security Tools**: ${{activeTools}}
          **Policy Version**: ${{scorecardResult.policy_version || 'N/A'}}
          
          ### Artifacts
          - [QA Summary](../actions/runs/${{github.run_id}}/artifacts)
          - [Security Report](../actions/runs/${{github.run_id}}/artifacts)  
          - [Coverage Report](../actions/runs/${{github.run_id}}/artifacts)
          - [Run Metadata](../actions/runs/${{github.run_id}}/artifacts)
          
          *Generated by CodePipeline Scorecard*`;
          
          github.rest.issues.createComment({{
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: comment
          }});
'''
        
        # Write workflow file
        workflow_file = self.workflows_dir / "scorecard.yml"
        with open(workflow_file, 'w', encoding='utf-8') as f:
            f.write(workflow_content)
        
        workflow.workflow_file = str(workflow_file.relative_to(self.project_root))
        
        logger.info(f"Generated scorecard workflow: {workflow_file}")
        return workflow
    
    def simulate_required_check(self, scorecard_result: Dict[str, Any]) -> RequiredCheckResult:
        """Simulate required check based on scorecard result."""
        
        overall_status = scorecard_result.get("overall_status", "fail")
        
        if overall_status == "pass":
            check_result = RequiredCheckResult(
                check_name="scorecard",
                status="completed",
                conclusion="success",
                output_title="✅ Scorecard Passed",
                output_summary=f"Coverage: {scorecard_result.get('coverage_percent', 'N/A')}%, Active Tools: {scorecard_result.get('active_security_tools', 0)}"
            )
        else:
            violations = scorecard_result.get("policy_violations", [])
            violation_summary = "; ".join(violations[:3]) if violations else "Policy violations detected"
            
            check_result = RequiredCheckResult(
                check_name="scorecard",
                status="completed",
                conclusion="failure",
                output_title="❌ Scorecard Failed",
                output_summary=f"Violations: {violation_summary}"
            )
        
        # Add artifact links
        check_result.artifacts = [
            "scorecard_result.json",
            "qa_summary.json", 
            "security_report.json",
            "coverage.xml",
            "run_meta.json"
        ]
        
        return check_result
    
    def generate_branch_protection_config(self) -> Dict[str, Any]:
        """Generate branch protection configuration."""
        
        return {
            "required_status_checks": {
                "strict": True,
                "contexts": ["scorecard"]
            },
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews": True
            },
            "restrictions": None,
            "allow_force_pushes": False,
            "allow_deletions": False
        }


# === BL-017: GUI-Start als Standard-Entry (Single Frontdoor) ===

@dataclass
class GUIServerConfig:
    """GUI server configuration."""
    
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    
    static_dir: Optional[str] = None
    artifacts_dir: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
            "static_dir": self.static_dir,
            "artifacts_dir": self.artifacts_dir
        }


class SingleFrontdoorGUI:
    """Single frontdoor GUI application."""
    
    def __init__(self, config: GUIServerConfig, project_root: Path):
        self.config = config
        self.project_root = project_root
        
        # Initialize components
        self.artifact_downloader = SecureArtifactDownloader(
            artifacts_dir=Path(config.artifacts_dir) if config.artifacts_dir else project_root / "artifacts"
        )
        self.log_viewer = LiveLogViewer()
        self.ci_integration = RemoteCIIntegration(project_root)
        
        # FastAPI app
        if FASTAPI_AVAILABLE:
            self.app = self._create_fastapi_app()
        else:
            self.app = None
            logger.warning("FastAPI not available - GUI disabled")
    
    def _create_fastapi_app(self) -> FastAPI:
        """Create FastAPI application."""
        
        app = FastAPI(
            title="CodePipeline GUI",
            description="Ultimate CodePipeline Web Interface",
            version="1.0.0"
        )
        
        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
        
        # Health endpoint
        @app.get("/health")
        async def health():
            return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
        
        # Artifact download endpoints
        @app.get("/api/artifacts/{run_id}/{artifact_type}")
        async def download_artifact(run_id: str, artifact_type: str, request: Request):
            download_request = ArtifactDownloadRequest(
                artifact_id=f"{run_id}_{artifact_type}",
                artifact_type=artifact_type,
                run_id=run_id,
                user_agent=request.headers.get("user-agent", ""),
                client_ip=request.client.host
            )
            
            result = self.artifact_downloader.validate_artifact_request(download_request)
            
            if not result.success:
                if result.security_blocked:
                    raise HTTPException(status_code=403, detail=result.error_message)
                else:
                    raise HTTPException(status_code=404, detail=result.error_message)
            
            # Stream file
            return StreamingResponse(
                self.artifact_downloader.stream_artifact(result),
                media_type=result.content_type,
                headers={
                    "Content-Disposition": f"attachment; filename={artifact_type}_{run_id}",
                    "Content-Length": str(result.file_size)
                }
            )
        
        # Live logs endpoints
        @app.get("/api/logs/recent")
        async def get_recent_logs(limit: int = 100, run_id: str = None):
            logs = self.log_viewer.get_recent_logs(limit=limit, run_id=run_id)
            return {"logs": logs}
        
        @app.get("/api/logs/stream")
        async def stream_logs(request: Request):
            subscriber_id, _ = self.log_viewer.subscribe_to_logs()
            
            async def event_stream():
                try:
                    async for event in self.log_viewer.stream_logs(subscriber_id):
                        yield event
                except Exception as e:
                    logger.error(f"Log streaming error: {e}")
                    yield f"data: {{\"error\": \"Stream error: {e}\"}}\n\n"
            
            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        
        # Runs API endpoints (basic)
        @app.get("/api/runs")
        async def list_runs():
            # Simulate run list
            return {
                "runs": [
                    {
                        "id": "run_001",
                        "status": "completed",
                        "created_at": "2024-01-01T10:00:00Z",
                        "duration": 120,
                        "scorecard_status": "pass"
                    },
                    {
                        "id": "run_002", 
                        "status": "running",
                        "created_at": "2024-01-01T11:00:00Z",
                        "duration": 45,
                        "scorecard_status": "pending"
                    }
                ]
            }
        
        @app.post("/api/runs")
        async def create_run(run_spec: dict):
            # Simulate run creation
            run_id = f"run_{int(time.time())}"
            
            # Add log entry
            self.log_viewer.add_log_entry(
                level="INFO",
                message=f"Started new run: {run_id}",
                source="api",
                run_id=run_id
            )
            
            return {
                "run_id": run_id,
                "status": "created",
                "spec": run_spec
            }
        
        # Static files (if configured)
        if self.config.static_dir and Path(self.config.static_dir).exists():
            app.mount("/", StaticFiles(directory=self.config.static_dir, html=True), name="static")
        
        return app
    
    def start_server(self, background: bool = False) -> Optional[threading.Thread]:
        """Start GUI server."""
        
        if not FASTAPI_AVAILABLE:
            logger.error("Cannot start GUI server: FastAPI not available")
            return None
        
        def run_server():
            try:
                uvicorn.run(
                    self.app,
                    host=self.config.host,
                    port=self.config.port,
                    log_level="info" if self.config.debug else "warning"
                )
            except Exception as e:
                logger.error(f"GUI server failed: {e}")
        
        if background:
            thread = threading.Thread(target=run_server, daemon=True)
            thread.start()
            return thread
        else:
            run_server()
            return None
    
    def get_server_url(self) -> str:
        """Get server URL."""
        return f"http://{self.config.host}:{self.config.port}"
    
    def check_health(self) -> bool:
        """Check server health."""
        try:
            import requests
            response = requests.get(f"{self.get_server_url()}/health", timeout=5)
            return response.status_code == 200
        except:
            return False


def create_default_static_files(static_dir: Path):
    """Create default static files for GUI."""
    
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Create index.html
    index_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodePipeline GUI</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .button { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 3px; cursor: pointer; }
        .button:hover { background: #2980b9; }
        .logs { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 3px; height: 400px; overflow-y: auto; font-family: monospace; font-size: 14px; }
        .log-entry { margin-bottom: 5px; }
        .log-info { color: #3498db; }
        .log-warn { color: #f39c12; }
        .log-error { color: #e74c3c; }
        .artifact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .artifact-card { background: #ecf0f1; padding: 15px; border-radius: 3px; text-align: center; }
        .artifact-link { color: #3498db; text-decoration: none; font-weight: bold; }
        .artifact-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 CodePipeline GUI</h1>
            <p>Ultimate Enterprise-Grade Pipeline Management Interface</p>
        </div>
        
        <div class="card">
            <h2>📊 Pipeline Dashboard</h2>
            <div id="runs-list">
                <p>Loading runs...</p>
            </div>
            <button class="button" onclick="createNewRun()">Create New Run</button>
        </div>
        
        <div class="card">
            <h2>📁 Artifacts</h2>
            <div class="artifact-grid">
                <div class="artifact-card">
                    <h3>QA Summary</h3>
                    <a href="/api/artifacts/run_001/qa" class="artifact-link">Download</a>
                </div>
                <div class="artifact-card">
                    <h3>Security Report</h3>
                    <a href="/api/artifacts/run_001/security" class="artifact-link">Download</a>
                </div>
                <div class="artifact-card">
                    <h3>SBOM</h3>
                    <a href="/api/artifacts/run_001/sbom" class="artifact-link">Download</a>
                </div>
                <div class="artifact-card">
                    <h3>Coverage</h3>
                    <a href="/api/artifacts/run_001/coverage" class="artifact-link">Download</a>
                </div>
                <div class="artifact-card">
                    <h3>Run Metadata</h3>
                    <a href="/api/artifacts/run_001/run_meta" class="artifact-link">Download</a>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>📜 Live Logs</h2>
            <div id="logs" class="logs">
                <div class="log-entry log-info">[INFO] GUI started successfully</div>
                <div class="log-entry log-info">[INFO] Waiting for pipeline runs...</div>
            </div>
        </div>
    </div>
    
    <script>
        // Load runs
        async function loadRuns() {
            try {
                const response = await fetch('/api/runs');
                const data = await response.json();
                
                const runsList = document.getElementById('runs-list');
                runsList.innerHTML = data.runs.map(run => 
                    `<div style="margin-bottom: 10px; padding: 10px; background: #ecf0f1; border-radius: 3px;">
                        <strong>Run ${run.id}</strong> - Status: ${run.status} - Duration: ${run.duration}s
                    </div>`
                ).join('');
            } catch (error) {
                console.error('Failed to load runs:', error);
            }
        }
        
        // Create new run
        async function createNewRun() {
            const spec = {
                prompt: "Create a simple web API",
                template: "python-api",
                secure_mode: true
            };
            
            try {
                const response = await fetch('/api/runs', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(spec)
                });
                const data = await response.json();
                
                alert(`Created run: ${data.run_id}`);
                loadRuns();
            } catch (error) {
                console.error('Failed to create run:', error);
                alert('Failed to create run');
            }
        }
        
        // Live logs
        function connectLogs() {
            const eventSource = new EventSource('/api/logs/stream');
            const logsContainer = document.getElementById('logs');
            
            eventSource.onmessage = function(event) {
                try {
                    const logData = JSON.parse(event.data);
                    
                    if (logData.keepalive) return;
                    
                    const logEntry = document.createElement('div');
                    logEntry.className = `log-entry log-${logData.level.toLowerCase()}`;
                    logEntry.textContent = `[${logData.level}] ${logData.message}`;
                    
                    logsContainer.appendChild(logEntry);
                    logsContainer.scrollTop = logsContainer.scrollHeight;
                    
                    // Keep only last 100 entries
                    while (logsContainer.children.length > 100) {
                        logsContainer.removeChild(logsContainer.firstChild);
                    }
                } catch (error) {
                    console.error('Log parsing error:', error);
                }
            };
            
            eventSource.onerror = function(error) {
                console.error('Log stream error:', error);
                setTimeout(connectLogs, 5000); // Reconnect after 5s
            };
        }
        
        // Initialize
        loadRuns();
        connectLogs();
        
        // Refresh runs every 30s
        setInterval(loadRuns, 30000);
    </script>
</body>
</html>'''
    
    with open(static_dir / "index.html", 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    logger.info(f"Created default static files in {static_dir}")


# === Integration Functions ===

def create_ultimate_gui_suite(project_root: Path, config: Optional[GUIServerConfig] = None) -> SingleFrontdoorGUI:
    """Create ultimate GUI suite."""
    
    if not config:
        config = GUIServerConfig()
    
    # Create static files if directory specified
    if config.static_dir:
        static_dir = Path(config.static_dir)
        if not static_dir.exists():
            create_default_static_files(static_dir)
    
    gui = SingleFrontdoorGUI(config, project_root)
    
    return gui


def start_gui_server(project_root: Path, host: str = "127.0.0.1", port: int = 8000, background: bool = True) -> Tuple[SingleFrontdoorGUI, Optional[threading.Thread]]:
    """Start GUI server with default configuration."""
    
    # Prepare directories
    static_dir = project_root / "gui" / "static"
    artifacts_dir = project_root / "artifacts"
    
    config = GUIServerConfig(
        host=host,
        port=port,
        static_dir=str(static_dir),
        artifacts_dir=str(artifacts_dir)
    )
    
    gui = create_ultimate_gui_suite(project_root, config)
    thread = gui.start_server(background=background)
    
    return gui, thread


def main_gui_entry():
    """Main GUI entry point."""
    
    print("🚀 Starting CodePipeline GUI (Single Frontdoor)...")
    
    project_root = Path(".")
    gui, thread = start_gui_server(project_root)
    
    if thread:
        print(f"✅ GUI Server started: {gui.get_server_url()}")
        print(f"📊 Dashboard: {gui.get_server_url()}/")
        print(f"💾 Health: {gui.get_server_url()}/health")
        print("")
        print("Environment Variables:")
        print("  CODEPIPELINE_HOST=127.0.0.1")
        print("  CODEPIPELINE_PORT=8000")
        print("  CODEPIPELINE_DEBUG=false")
        print("")
        print("Press Ctrl+C to stop...")
        
        try:
            thread.join()
        except KeyboardInterrupt:
            print("\n👋 GUI Server stopped")
    else:
        print("❌ Failed to start GUI server")


if __name__ == "__main__":
    main_gui_entry()
