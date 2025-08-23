"""
GUI Security Suite für CodePipeline.

Implementiert:
- ID 418: GUI – Sicherheit & Hygiene
- ID 419: GUI – Artefakte & sichere Downloads
- ID 420: Nightly Secure E2E via GUI mit KPI-Export
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import app_secrets
import time
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
import logging
from threading import Lock
import tempfile

# Security imports (would be installed in real implementation)
try:
    import jwt
    from passlib.context import CryptContext
    JWT_AVAILABLE = True
except ImportError:
    # Mock for demo purposes
    class jwt:
        @staticmethod
        def encode(payload, key, algorithm='HS256'): return "mock_token"
        @staticmethod
        def decode(token, key, algorithms=['HS256']): return {"sub": "user"}
    
    class CryptContext:
        def __init__(self, schemes): pass
        def hash(self, password): return "hashed_password"
        def verify(self, password, hash): return True
    
    JWT_AVAILABLE = False


logger = logging.getLogger(__name__)


# === ID 418: GUI – Sicherheit & Hygiene ===

@dataclass
class AuthToken:
    """Authentication token."""
    
    token: str
    user_id: str
    expires_at: datetime
    permissions: Set[str] = field(default_factory=set)
    
    def is_valid(self) -> bool:
        """Check if token is still valid."""
        return datetime.utcnow() < self.expires_at
    
    def has_permission(self, permission: str) -> bool:
        """Check if token has specific permission."""
        return permission in self.permissions


@dataclass
class RateLimitInfo:
    """Rate limit information."""
    
    requests: List[datetime] = field(default_factory=list)
    blocked_until: Optional[datetime] = None
    
    def is_blocked(self) -> bool:
        """Check if currently blocked."""
        if self.blocked_until and datetime.utcnow() < self.blocked_until:
            return True
        return False
    
    def add_request(self) -> bool:
        """Add request and check if within limits."""
        now = datetime.utcnow()
        
        # Clean old requests (older than 1 minute)
        self.requests = [req for req in self.requests if now - req < timedelta(minutes=1)]
        
        # Check rate limit (60 requests per minute)
        if len(self.requests) >= 60:
            self.blocked_until = now + timedelta(minutes=5)  # Block for 5 minutes
            return False
        
        self.requests.append(now)
        return True


class SecurityManager:
    """GUI security manager."""
    
    def __init__(self):
        self.secret_key = os.environ.get('GUI_SECRET_KEY', secrets.token_urlsafe(32))
        self.tokens: Dict[str, AuthToken] = {}
        self.rate_limits: Dict[str, RateLimitInfo] = {}
        self.csrf_tokens: Dict[str, datetime] = {}
        self.tokens_lock = Lock()
        
        # Password context for secure hashing
        self.pwd_context = CryptContext(schemes=["bcrypt"])
        
        # Sensitive patterns to redact from logs
        self.sensitive_patterns = [
            r'token["\s]*[:=]["\s]*([^"\s,}]+)',
            r'password["\s]*[:=]["\s]*([^"\s,}]+)',
            r'secret["\s]*[:=]["\s]*([^"\s,}]+)',
            r'key["\s]*[:=]["\s]*([^"\s,}]+)',
            r'Authorization:\s*Bearer\s+([^\s]+)',
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub tokens
            r'sk-[a-zA-Z0-9]{48}',   # OpenAI tokens
        ]
    
    def generate_token(self, user_id: str, permissions: Set[str] = None) -> str:
        """Generate authentication token."""
        
        if permissions is None:
            permissions = {"read", "write"}
        
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        payload = {
            "sub": user_id,
            "exp": int(expires_at.timestamp()),
            "permissions": list(permissions),
            "iat": int(datetime.utcnow().timestamp())
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        
        # Store token info
        with self.tokens_lock:
            auth_token = AuthToken(
                token=token,
                user_id=user_id,
                expires_at=expires_at,
                permissions=permissions
            )
            self.tokens[token] = auth_token
        
        logger.info(f"Generated token for user: {user_id}")
        return token
    
    def validate_token(self, token: str) -> Optional[AuthToken]:
        """Validate authentication token."""
        
        if not token:
            return None
        
        try:
            # Decode JWT
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            
            with self.tokens_lock:
                if token in self.tokens:
                    auth_token = self.tokens[token]
                    if auth_token.is_valid():
                        return auth_token
                    else:
                        # Remove expired token
                        del self.tokens[token]
            
            return None
            
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            return None
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check rate limit for client IP."""
        
        if client_ip not in self.rate_limits:
            self.rate_limits[client_ip] = RateLimitInfo()
        
        rate_info = self.rate_limits[client_ip]
        
        if rate_info.is_blocked():
            return False
        
        return rate_info.add_request()
    
    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token."""
        
        csrf_token = secrets.token_urlsafe(32)
        self.csrf_tokens[csrf_token] = datetime.utcnow() + timedelta(hours=1)
        
        return csrf_token
    
    def validate_csrf_token(self, csrf_token: str) -> bool:
        """Validate CSRF token."""
        
        if csrf_token not in self.csrf_tokens:
            return False
        
        expires_at = self.csrf_tokens[csrf_token]
        if datetime.utcnow() > expires_at:
            del self.csrf_tokens[csrf_token]
            return False
        
        return True
    
    def redact_secrets_from_logs(self, log_message: str) -> str:
        """Redact sensitive information from log messages."""
        
        import re
        
        redacted = log_message
        
        for pattern in self.sensitive_patterns:
            try:
                redacted = re.sub(pattern, lambda m: m.group(0).replace(m.group(1), "***REDACTED***"), redacted, flags=re.IGNORECASE)
            except IndexError:
                # If pattern doesn't have a capture group, replace the whole match
                redacted = re.sub(pattern, "***REDACTED***", redacted, flags=re.IGNORECASE)
        
        return redacted
    
    def validate_request_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Server-side validation of request data."""
        
        errors = []
        
        # Check for required fields based on request type
        if 'prompt' in data:
            if not data['prompt'] or not isinstance(data['prompt'], str):
                errors.append("Prompt is required and must be a string")
            elif len(data['prompt']) > 10000:
                errors.append("Prompt too long (max 10000 characters)")
        
        if 'template_type' in data:
            valid_templates = ['cli', 'web-api', 'worker', 'batch']
            if data['template_type'] and data['template_type'] not in valid_templates:
                errors.append(f"Invalid template type. Valid options: {', '.join(valid_templates)}")
        
        if 'deploy_profile' in data:
            valid_profiles = ['development', 'staging', 'production']
            if data['deploy_profile'] and data['deploy_profile'] not in valid_profiles:
                errors.append(f"Invalid deploy profile. Valid options: {', '.join(valid_profiles)}")
        
        # Check for injection attempts
        dangerous_patterns = ['<script', 'javascript:', 'eval(', 'exec(', '${', '#{']
        for key, value in data.items():
            if isinstance(value, str):
                for pattern in dangerous_patterns:
                    if pattern.lower() in value.lower():
                        errors.append(f"Potentially dangerous content detected in {key}")
                        break
        
        return len(errors) == 0, errors


# === ID 419: GUI – Artefakte & sichere Downloads ===

@dataclass
class ArtifactInfo:
    """Artifact information."""
    
    name: str
    path: str
    size: int
    content_type: str
    checksum: str
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "size": self.size,
            "content_type": self.content_type,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat()
        }


class SecureArtifactManager:
    """Secure artifact download manager."""
    
    def __init__(self):
        # Allowed content types for downloads
        self.allowed_content_types = {
            'application/json',
            'application/xml',
            'text/plain',
            'text/csv',
            'text/html',
            'text/markdown',
            'application/zip',
            'application/gzip',
            'application/x-tar',
            'application/pdf',
            'application/octet-stream'  # For binary artifacts
        }
        
        # File extension to content type mapping
        self.extension_content_types = {
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.txt': 'text/plain',
            '.csv': 'text/csv',
            '.html': 'text/html',
            '.md': 'text/markdown',
            '.zip': 'application/zip',
            '.gz': 'application/gzip',
            '.tar': 'application/x-tar',
            '.pdf': 'application/pdf',
            '.log': 'text/plain',
            '.yaml': 'text/plain',
            '.yml': 'text/plain'
        }
        
        # Maximum file size for downloads (100MB)
        self.max_file_size = 100 * 1024 * 1024
        
        self.artifacts: Dict[str, ArtifactInfo] = {}
        self.artifacts_lock = Lock()
    
    def register_artifact(self, run_id: str, artifact_name: str, artifact_path: str) -> bool:
        """Register artifact for secure download."""
        
        if not os.path.exists(artifact_path):
            logger.error(f"Artifact file not found: {artifact_path}")
            return False
        
        try:
            # Get file info
            file_size = os.path.getsize(artifact_path)
            
            # Check file size
            if file_size > self.max_file_size:
                logger.error(f"Artifact too large: {file_size} bytes (max {self.max_file_size})")
                return False
            
            # Determine content type
            content_type = self.get_content_type(artifact_path)
            if not content_type:
                logger.error(f"Unsupported file type for artifact: {artifact_path}")
                return False
            
            # Calculate checksum
            checksum = self.calculate_checksum(artifact_path)
            
            # Create artifact info
            artifact_info = ArtifactInfo(
                name=artifact_name,
                path=artifact_path,
                size=file_size,
                content_type=content_type,
                checksum=checksum,
                created_at=datetime.utcnow()
            )
            
            # Store artifact info
            artifact_key = f"{run_id}/{artifact_name}"
            with self.artifacts_lock:
                self.artifacts[artifact_key] = artifact_info
            
            logger.info(f"Registered artifact: {artifact_key} ({file_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register artifact: {e}")
            return False
    
    def get_content_type(self, file_path: str) -> Optional[str]:
        """Get content type for file."""
        
        # Get from extension first
        ext = Path(file_path).suffix.lower()
        if ext in self.extension_content_types:
            content_type = self.extension_content_types[ext]
        else:
            # Use mimetypes
            content_type, _ = mimetypes.guess_type(file_path)
        
        # Check if allowed
        if content_type and content_type in self.allowed_content_types:
            return content_type
        
        return None
    
    def calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file."""
        
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def get_artifact_info(self, run_id: str, artifact_name: str) -> Optional[ArtifactInfo]:
        """Get artifact information."""
        
        artifact_key = f"{run_id}/{artifact_name}"
        
        with self.artifacts_lock:
            return self.artifacts.get(artifact_key)
    
    def validate_download_request(self, run_id: str, artifact_name: str, token: AuthToken) -> Tuple[bool, str]:
        """Validate download request."""
        
        # Check permissions
        if not token.has_permission("read"):
            return False, "Insufficient permissions"
        
        # Get artifact info
        artifact_info = self.get_artifact_info(run_id, artifact_name)
        if not artifact_info:
            return False, "Artifact not found"
        
        # Check if file still exists
        if not os.path.exists(artifact_info.path):
            return False, "Artifact file not found"
        
        # Verify checksum
        current_checksum = self.calculate_checksum(artifact_info.path)
        if current_checksum != artifact_info.checksum:
            return False, "Artifact integrity check failed"
        
        return True, "OK"
    
    async def stream_artifact(self, artifact_info: ArtifactInfo, chunk_size: int = 8192):
        """Stream artifact content for download."""
        
        try:
            with open(artifact_info.path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    
                    # Allow other tasks to run
                    await asyncio.sleep(0)
                    
        except Exception as e:
            logger.error(f"Error streaming artifact: {e}")
            raise


# === ID 420: Nightly Secure E2E via GUI mit KPI-Export ===

@dataclass
class NightlyRunResult:
    """Result of nightly run."""
    
    run_id: str
    spec: Dict[str, Any]
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"
    
    # Pipeline results
    coverage_percentage: float = 0.0
    scorecard_score: int = 0
    scorecard_passed: bool = False
    active_security_tools: List[str] = field(default_factory=list)
    pr_url: str = ""
    pr_number: Optional[int] = None
    
    # Artifacts
    artifacts: Dict[str, str] = field(default_factory=dict)
    
    # Error information
    error_message: str = ""
    
    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "spec": self.spec,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "duration_minutes": self.duration_minutes,
            "coverage_percentage": self.coverage_percentage,
            "scorecard_score": self.scorecard_score,
            "scorecard_passed": self.scorecard_passed,
            "active_security_tools": self.active_security_tools,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "artifacts": self.artifacts,
            "error_message": self.error_message
        }


class NightlyAutomationManager:
    """Nightly secure E2E automation via GUI."""
    
    def __init__(self, gui_backend, security_manager: SecurityManager, artifact_manager: SecureArtifactManager):
        self.gui_backend = gui_backend
        self.security_manager = security_manager
        self.artifact_manager = artifact_manager
        
        # Test specifications for nightly runs
        self.test_specs = [
            {
                "name": "Simple Web API",
                "prompt": "Create a REST API for user management with authentication and health endpoint",
                "template_type": "web-api",
                "deploy_profile": "development",
                "secure_mode": True
            },
            {
                "name": "CLI Tool",
                "prompt": "Build a CLI tool for file processing with validation and logging",
                "template_type": "cli",
                "deploy_profile": "development", 
                "secure_mode": True
            },
            {
                "name": "Background Worker",
                "prompt": "Develop a background worker for data processing with queue management",
                "template_type": "worker",
                "deploy_profile": "development",
                "secure_mode": True
            }
        ]
        
        self.nightly_results: List[NightlyRunResult] = []
        self.results_lock = Lock()
    
    async def run_nightly_automation(self) -> str:
        """Run nightly secure E2E automation."""
        
        logger.info("Starting nightly secure E2E automation")
        
        # Generate system token for automation
        system_token = self.security_manager.generate_token("system", {"read", "write", "admin"})
        auth_token = self.security_manager.validate_token(system_token)
        
        if not auth_token:
            logger.error("Failed to generate system token")
            return "Failed to generate system token"
        
        results = []
        
        for spec in self.test_specs:
            try:
                logger.info(f"Running nightly test: {spec['name']}")
                
                # Run secure E2E test
                result = await self.run_secure_e2e_test(spec, auth_token)
                results.append(result)
                
                # Wait between runs
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Nightly test failed for {spec['name']}: {e}")
                
                # Create failed result
                failed_result = NightlyRunResult(
                    run_id=f"failed_{spec['name'].lower().replace(' ', '_')}",
                    spec=spec,
                    start_time=datetime.utcnow(),
                    end_time=datetime.utcnow(),
                    status="failed",
                    error_message=str(e)
                )
                results.append(failed_result)
        
        # Store results
        with self.results_lock:
            self.nightly_results.extend(results)
        
        # Generate KPI report
        kpi_report = self.generate_kpi_report(results)
        
        # Save report
        report_path = self.save_kpi_report(kpi_report)
        
        logger.info(f"Nightly automation completed. Report saved to: {report_path}")
        
        return report_path
    
    async def run_secure_e2e_test(self, spec: Dict[str, Any], auth_token: AuthToken) -> NightlyRunResult:
        """Run single secure E2E test."""
        
        start_time = datetime.utcnow()
        
        result = NightlyRunResult(
            run_id=f"nightly_{spec['name'].lower().replace(' ', '_')}_{int(start_time.timestamp())}",
            spec=spec,
            start_time=start_time
        )
        
        try:
            # Step 1: Validate spec via GUI
            is_valid, errors = self.security_manager.validate_request_data(spec)
            if not is_valid:
                raise Exception(f"Spec validation failed: {', '.join(errors)}")
            
            logger.info(f"Spec validation passed for {spec['name']}")
            
            # Step 2: Start secure run via GUI backend
            run_response = await self.start_gui_run(spec, auth_token)
            if not run_response.get('success'):
                raise Exception(f"Failed to start run: {run_response.get('error')}")
            
            actual_run_id = run_response['run_id']
            result.run_id = actual_run_id
            
            logger.info(f"Started secure run: {actual_run_id}")
            
            # Step 3: Wait for completion
            run_result = await self.wait_for_completion(actual_run_id, timeout_minutes=30)
            if not run_result:
                raise Exception("Run did not complete within timeout")
            
            # Step 4: Validate results
            if run_result['status'] != 'success':
                raise Exception(f"Run failed with status: {run_result['status']}")
            
            # Step 5: Check security requirements
            security_check = self.validate_security_requirements(run_result)
            if not security_check['passed']:
                raise Exception(f"Security requirements not met: {security_check['reason']}")
            
            # Step 6: Collect results
            result.end_time = datetime.utcnow()
            result.status = "success"
            result.coverage_percentage = run_result.get('coverage_percentage', 0.0)
            result.scorecard_score = run_result.get('scorecard_score', 0)
            result.scorecard_passed = run_result.get('scorecard_score', 0) >= 85
            result.active_security_tools = run_result.get('active_security_tools', [])
            result.pr_url = run_result.get('pr_url', "")
            result.artifacts = run_result.get('artifacts', {})
            
            # Extract PR number from URL
            if result.pr_url:
                import re
                pr_match = re.search(r'/pull/(\d+)', result.pr_url)
                if pr_match:
                    result.pr_number = int(pr_match.group(1))
            
            logger.info(f"Secure E2E test completed successfully: {spec['name']}")
            
        except Exception as e:
            result.end_time = datetime.utcnow()
            result.status = "failed"
            result.error_message = str(e)
            
            logger.error(f"Secure E2E test failed for {spec['name']}: {e}")
        
        return result
    
    async def start_gui_run(self, spec: Dict[str, Any], auth_token: AuthToken) -> Dict[str, Any]:
        """Start run via GUI backend."""
        
        try:
            # Simulate GUI API call
            import uuid
            from codepipeline.gui_backend_api import PipelineRun, RunStatus
            
            run_id = str(uuid.uuid4())
            
            # Create pipeline run
            pipeline_run = PipelineRun(
                run_id=run_id,
                spec=spec,
                status=RunStatus.PENDING,
                created_at=datetime.utcnow(),
                template_type=spec.get('template_type', 'auto-detect'),
                deploy_profile=spec.get('deploy_profile', 'development')
            )
            
            # Store in backend
            self.gui_backend.runs[run_id] = pipeline_run
            
            # Start execution
            await self.gui_backend.orchestrator.execute_pipeline(run_id)
            
            return {"success": True, "run_id": run_id}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def wait_for_completion(self, run_id: str, timeout_minutes: int = 30) -> Optional[Dict[str, Any]]:
        """Wait for run completion."""
        
        start_time = datetime.utcnow()
        timeout = timedelta(minutes=timeout_minutes)
        
        while datetime.utcnow() - start_time < timeout:
            # Check run status
            if run_id in self.gui_backend.runs:
                run = self.gui_backend.runs[run_id]
                
                if run.status.value in ['success', 'failed', 'cancelled']:
                    return run.to_dict()
            
            # Wait before next check
            await asyncio.sleep(10)
        
        return None
    
    def validate_security_requirements(self, run_result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate security requirements."""
        
        # Check for at least one active security tool
        active_tools = run_result.get('active_security_tools', [])
        if len(active_tools) < 1:
            return {"passed": False, "reason": "No active security tools"}
        
        # Check scorecard pass
        scorecard_score = run_result.get('scorecard_score', 0)
        if scorecard_score < 85:
            return {"passed": False, "reason": f"Scorecard score too low: {scorecard_score}"}
        
        # Check PR creation
        pr_url = run_result.get('pr_url', "")
        if not pr_url:
            return {"passed": False, "reason": "No draft PR created"}
        
        return {"passed": True, "reason": "All requirements met"}
    
    def generate_kpi_report(self, results: List[NightlyRunResult]) -> str:
        """Generate KPI report in Markdown format."""
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Calculate metrics
        total_runs = len(results)
        successful_runs = len([r for r in results if r.status == "success"])
        failed_runs = total_runs - successful_runs
        success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0
        
        avg_duration = sum(r.duration_minutes for r in results) / len(results) if results else 0
        avg_coverage = sum(r.coverage_percentage for r in results if r.coverage_percentage > 0) / len([r for r in results if r.coverage_percentage > 0]) if any(r.coverage_percentage > 0 for r in results) else 0
        avg_scorecard = sum(r.scorecard_score for r in results if r.scorecard_score > 0) / len([r for r in results if r.scorecard_score > 0]) if any(r.scorecard_score > 0 for r in results) else 0
        
        # Collect all security tools
        all_tools = set()
        for result in results:
            all_tools.update(result.active_security_tools)
        
        # Generate report
        report = f"""# Nightly Secure E2E Test Report

**Generated:** {timestamp}

## Summary

| Metric | Value | Status |
|--------|-------|--------|
| Total Runs | {total_runs} | ℹ️ |
| Successful Runs | {successful_runs} | {"✅" if successful_runs > 0 else "❌"} |
| Failed Runs | {failed_runs} | {"❌" if failed_runs > 0 else "✅"} |
| Success Rate | {success_rate:.1f}% | {"✅" if success_rate >= 80 else "⚠️" if success_rate >= 50 else "❌"} |
| Average Duration | {avg_duration:.1f} min | {"✅" if avg_duration <= 15 else "⚠️" if avg_duration <= 30 else "❌"} |
| Average Coverage | {avg_coverage:.1f}% | {"✅" if avg_coverage >= 80 else "⚠️" if avg_coverage >= 60 else "❌"} |
| Average Scorecard | {avg_scorecard:.0f} | {"✅" if avg_scorecard >= 85 else "⚠️" if avg_scorecard >= 70 else "❌"} |
| Active Security Tools | {len(all_tools)} | {"✅" if len(all_tools) >= 3 else "⚠️" if len(all_tools) >= 1 else "❌"} |

## Security Tools Used

{', '.join(sorted(all_tools)) if all_tools else 'None'}

## Individual Run Results

"""
        
        for result in results:
            status_icon = "✅" if result.status == "success" else "❌"
            scorecard_icon = "✅" if result.scorecard_passed else "❌"
            coverage_icon = "✅" if result.coverage_percentage >= 80 else "⚠️" if result.coverage_percentage >= 60 else "❌"
            
            report += f"""### {result.spec['name']} {status_icon}

- **Run ID:** `{result.run_id}`
- **Status:** {result.status.upper()}
- **Duration:** {result.duration_minutes:.1f} minutes
- **Coverage:** {result.coverage_percentage:.1f}% {coverage_icon}
- **Scorecard:** {result.scorecard_score}/100 {scorecard_icon}
- **Security Tools:** {', '.join(result.active_security_tools) if result.active_security_tools else 'None'}
- **PR:** {f"[#{result.pr_number}]({result.pr_url})" if result.pr_url else "Not created"}
- **Artifacts:** {len(result.artifacts)} files

"""
            
            if result.error_message:
                report += f"**Error:** {result.error_message}\n\n"
        
        report += f"""## Recommendations

"""
        
        if success_rate < 80:
            report += "- ⚠️ Success rate is below 80%. Investigate failing tests.\n"
        
        if avg_coverage < 80:
            report += "- ⚠️ Average coverage is below 80%. Review test coverage.\n"
        
        if avg_scorecard < 85:
            report += "- ⚠️ Average scorecard score is below 85. Review security practices.\n"
        
        if len(all_tools) < 3:
            report += "- ⚠️ Less than 3 security tools active. Consider enabling more scanners.\n"
        
        if avg_duration > 20:
            report += "- ⚠️ Average duration exceeds 20 minutes. Consider pipeline optimization.\n"
        
        if not any(result.pr_url for result in results):
            report += "- ❌ No PRs were created. Check PR automation.\n"
        
        report += f"""
---

*Report generated by CodePipeline Nightly Automation*  
*Timestamp: {timestamp}*
"""
        
        return report
    
    def save_kpi_report(self, report: str) -> str:
        """Save KPI report to file."""
        
        # Create reports directory
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"nightly_kpi_report_{timestamp}.md"
        report_path = reports_dir / filename
        
        # Write report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return str(report_path)


# === Convenience Functions ===

def create_security_manager() -> SecurityManager:
    """Create security manager."""
    return SecurityManager()


def create_artifact_manager() -> SecureArtifactManager:
    """Create artifact manager."""
    return SecureArtifactManager()


def create_nightly_automation(gui_backend, security_manager: SecurityManager, artifact_manager: SecureArtifactManager) -> NightlyAutomationManager:
    """Create nightly automation manager."""
    return NightlyAutomationManager(gui_backend, security_manager, artifact_manager)


if __name__ == "__main__":
    # Demo
    def demo_security_suite():
        print("GUI Security Suite Demo:")
        
        # Create security manager
        security_manager = create_security_manager()
        
        # Generate token
        token = security_manager.generate_token("demo_user", {"read", "write"})
        print(f"Generated token: {token[:20]}...")
        
        # Validate token
        auth_token = security_manager.validate_token(token)
        print(f"Token validation: {auth_token is not None}")
        
        # Check rate limit
        rate_ok = security_manager.check_rate_limit("127.0.0.1")
        print(f"Rate limit check: {rate_ok}")
        
        # Generate CSRF token
        csrf_token = security_manager.generate_csrf_token("session_123")
        print(f"CSRF token: {csrf_token[:20]}...")
        
        # Redact secrets
        log_message = "User login with token: sk-abc123def456ghi789 and password: secret123"
        redacted = security_manager.redact_secrets_from_logs(log_message)
        print(f"Redacted log: {redacted}")
        
        # Validate request
        valid, errors = security_manager.validate_request_data({
            "prompt": "Create a web API",
            "template_type": "web-api"
        })
        print(f"Request validation: {valid} (errors: {errors})")
        
        # Create artifact manager
        artifact_manager = create_artifact_manager()
        
        # Test artifact registration
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"test": "data"}')
            temp_path = f.name
        
        registered = artifact_manager.register_artifact("test_run", "test.json", temp_path)
        print(f"Artifact registration: {registered}")
        
        # Get artifact info
        artifact_info = artifact_manager.get_artifact_info("test_run", "test.json")
        print(f"Artifact info: {artifact_info.name if artifact_info else None}")
        
        # Clean up
        os.unlink(temp_path)
        
        return True
    
    # Run demo
    result = demo_security_suite()
    print(f"Demo completed: {result}")
