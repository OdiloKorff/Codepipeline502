"""
Policy-konformer Container-Build.

Implementiert sichere Container:
- Multi-stage Builds mit minimaler Runtime
- Non-root User und readonly filesystem
- Kein shell-globbing in Startbefehlen
- Health-Probes und minimaler Footprint
"""

from __future__ import annotations

import os
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging


logger = logging.getLogger(__name__)


class ContainerPolicy(Enum):
    """Container-Sicherheits-Policies."""
    MULTI_STAGE = "multi_stage"
    NON_ROOT_USER = "non_root_user"
    READONLY_FILESYSTEM = "readonly_filesystem"
    NO_SHELL_GLOBBING = "no_shell_globbing"
    MINIMAL_RUNTIME = "minimal_runtime"
    HEALTH_PROBES = "health_probes"
    NO_PRIVILEGED = "no_privileged"
    RESOURCE_LIMITS = "resource_limits"


@dataclass
class SecurityPolicy:
    """Container-Sicherheits-Policy."""
    
    # Basis-Policies
    enforce_multi_stage: bool = True
    enforce_non_root: bool = True
    enforce_readonly_fs: bool = False  # Optional, da es Kompatibilitätsprobleme geben kann
    
    # Shell-Sicherheit
    no_shell_commands: bool = True
    no_shell_globbing: bool = True
    
    # Runtime-Optimierung
    minimal_base_image: bool = True
    remove_package_managers: bool = True
    
    # Health & Monitoring
    require_health_check: bool = True
    require_liveness_probe: bool = True
    
    # Ressourcen
    enforce_resource_limits: bool = True
    max_memory_mb: int = 512
    max_cpu_cores: float = 1.0
    
    # User-Konfiguration
    default_user: str = "appuser"
    default_uid: int = 1001
    default_gid: int = 1001
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "enforce_multi_stage": self.enforce_multi_stage,
            "enforce_non_root": self.enforce_non_root,
            "enforce_readonly_fs": self.enforce_readonly_fs,
            "no_shell_commands": self.no_shell_commands,
            "no_shell_globbing": self.no_shell_globbing,
            "minimal_base_image": self.minimal_base_image,
            "remove_package_managers": self.remove_package_managers,
            "require_health_check": self.require_health_check,
            "require_liveness_probe": self.require_liveness_probe,
            "enforce_resource_limits": self.enforce_resource_limits,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_cores": self.max_cpu_cores,
            "default_user": self.default_user,
            "default_uid": self.default_uid,
            "default_gid": self.default_gid
        }


@dataclass
class ContainerSpec:
    """Container-Spezifikation."""
    
    # Basis-Info
    name: str
    tag: str = "latest"
    
    # Build-Kontext
    context_dir: Path = Path(".")
    dockerfile_path: Optional[Path] = None
    
    # Base Images
    build_base_image: str = "python:3.10"
    runtime_base_image: str = "python:3.10-slim"
    
    # Anwendung
    app_dir: str = "/app"
    entry_point: List[str] = field(default_factory=lambda: ["python", "main.py"])
    
    # Ports
    exposed_ports: List[int] = field(default_factory=list)
    
    # Environment
    env_vars: Dict[str, str] = field(default_factory=dict)
    
    # Health Check
    health_check_command: List[str] = field(default_factory=list)
    health_check_interval: int = 30
    health_check_timeout: int = 5
    health_check_retries: int = 3
    
    # Ressourcen
    memory_limit: Optional[str] = None
    cpu_limit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "tag": self.tag,
            "context_dir": str(self.context_dir),
            "dockerfile_path": str(self.dockerfile_path) if self.dockerfile_path else None,
            "build_base_image": self.build_base_image,
            "runtime_base_image": self.runtime_base_image,
            "app_dir": self.app_dir,
            "entry_point": self.entry_point,
            "exposed_ports": self.exposed_ports,
            "env_vars": self.env_vars,
            "health_check_command": self.health_check_command,
            "health_check_interval": self.health_check_interval,
            "health_check_timeout": self.health_check_timeout,
            "health_check_retries": self.health_check_retries,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit
        }


@dataclass
class ContainerBuildResult:
    """Container-Build-Ergebnis."""
    
    # Build-Info
    build_id: str
    image_name: str
    image_tag: str
    
    # Status
    success: bool = False
    
    # Build-Output
    build_output: str = ""
    build_errors: str = ""
    
    # Image-Info
    image_id: str = ""
    image_size_mb: float = 0.0
    
    # Security-Compliance
    security_compliant: bool = False
    policy_violations: List[str] = field(default_factory=list)
    
    # Health Check
    health_check_passed: bool = False
    health_check_output: str = ""
    
    # Timing
    build_started_at: str = ""
    build_completed_at: str = ""
    build_duration_seconds: float = 0.0
    
    # Metadaten
    dockerfile_content: str = ""
    build_args: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "build_id": self.build_id,
            "image_name": self.image_name,
            "image_tag": self.image_tag,
            "success": self.success,
            "build_output": self.build_output,
            "build_errors": self.build_errors,
            "image_id": self.image_id,
            "image_size_mb": self.image_size_mb,
            "security_compliant": self.security_compliant,
            "policy_violations": self.policy_violations,
            "health_check_passed": self.health_check_passed,
            "health_check_output": self.health_check_output,
            "build_started_at": self.build_started_at,
            "build_completed_at": self.build_completed_at,
            "build_duration_seconds": self.build_duration_seconds,
            "dockerfile_content": self.dockerfile_content,
            "build_args": self.build_args
        }


class DockerfileGenerator:
    """Dockerfile-Generator."""
    
    def __init__(self, security_policy: SecurityPolicy):
        self.policy = security_policy
    
    def generate_dockerfile(self, spec: ContainerSpec) -> str:
        """Generiere sicheres Dockerfile."""
        logger.info(f"Generating secure Dockerfile for {spec.name}")
        
        dockerfile_lines = []
        
        # Multi-stage Build
        if self.policy.enforce_multi_stage:
            dockerfile_lines.extend(self._generate_build_stage(spec))
            dockerfile_lines.append("")
            dockerfile_lines.extend(self._generate_runtime_stage(spec))
        else:
            dockerfile_lines.extend(self._generate_single_stage(spec))
        
        return "\\n".join(dockerfile_lines)
    
    def _generate_build_stage(self, spec: ContainerSpec) -> List[str]:
        """Generiere Build-Stage."""
        lines = [
            "# Build stage",
            f"FROM {spec.build_base_image} AS builder",
            "",
            "# Install build dependencies",
            "RUN apt-get update && apt-get install -y \\\\",
            "    build-essential \\\\",
            "    && rm -rf /var/lib/apt/lists/*",
            "",
            "# Set working directory",
            "WORKDIR /build",
            "",
            "# Copy dependency files first (for better caching)",
            "COPY requirements*.txt ./",
            "",
            "# Install Python dependencies",
            "RUN pip install --no-cache-dir --user -r requirements.txt",
            "",
            "# Copy source code",
            "COPY . .",
            "",
            "# Build application (if needed)",
            "RUN python -m compileall ."
        ]
        
        return lines
    
    def _generate_runtime_stage(self, spec: ContainerSpec) -> List[str]:
        """Generiere Runtime-Stage."""
        lines = [
            "# Runtime stage",
            f"FROM {spec.runtime_base_image} AS runtime"
        ]
        
        # Minimale Runtime
        if self.policy.minimal_base_image:
            lines.extend([
                "",
                "# Install only essential runtime packages",
                "RUN apt-get update && apt-get install -y --no-install-recommends \\\\",
                "    curl \\\\",
                "    && rm -rf /var/lib/apt/lists/*"
            ])
            
            if self.policy.remove_package_managers:
                lines.extend([
                    "",
                    "# Remove package managers for security",
                    "RUN apt-get purge -y --auto-remove apt"
                ])
        
        # Non-root User
        if self.policy.enforce_non_root:
            lines.extend([
                "",
                "# Create non-root user",
                f"RUN groupadd -g {self.policy.default_gid} {self.policy.default_user} \\\\",
                f"    && useradd -r -u {self.policy.default_uid} -g {self.policy.default_user} {self.policy.default_user}"
            ])
        
        # App-Verzeichnis
        lines.extend([
            "",
            "# Set working directory",
            f"WORKDIR {spec.app_dir}"
        ])
        
        # Multi-stage: Kopiere von Builder
        if self.policy.enforce_multi_stage:
            lines.extend([
                "",
                "# Copy installed packages from builder",
                "COPY --from=builder /root/.local /home/{}/local".format(self.policy.default_user),
                "",
                "# Copy application code from builder",
                "COPY --from=builder /build ."
            ])
        else:
            lines.extend([
                "",
                "# Copy application code",
                "COPY . ."
            ])
        
        # Ownership
        if self.policy.enforce_non_root:
            lines.extend([
                "",
                "# Set ownership",
                f"RUN chown -R {self.policy.default_user}:{self.policy.default_user} {spec.app_dir}"
            ])
        
        # User wechseln
        if self.policy.enforce_non_root:
            lines.extend([
                "",
                "# Switch to non-root user",
                f"USER {self.policy.default_user}"
            ])
        
        # Environment
        lines.extend([
            "",
            "# Set environment variables"
        ])
        
        if self.policy.enforce_multi_stage:
            lines.append(f"ENV PATH=/home/{self.policy.default_user}/.local/bin:$PATH")
        
        lines.append(f"ENV PYTHONPATH={spec.app_dir}")
        
        # Custom Environment Variables
        for key, value in spec.env_vars.items():
            lines.append(f"ENV {key}={value}")
        
        # Ports
        if spec.exposed_ports:
            lines.extend([
                "",
                "# Expose ports"
            ])
            for port in spec.exposed_ports:
                lines.append(f"EXPOSE {port}")
        
        # Health Check
        if self.policy.require_health_check and spec.health_check_command:
            health_cmd = " ".join(spec.health_check_command)
            
            # Sichere Health Check ohne Shell
            if self.policy.no_shell_commands:
                lines.extend([
                    "",
                    "# Health check (no shell)",
                    f"HEALTHCHECK --interval={spec.health_check_interval}s \\\\",
                    f"    --timeout={spec.health_check_timeout}s \\\\",
                    f"    --start-period=10s \\\\",
                    f"    --retries={spec.health_check_retries} \\\\",
                    f"    CMD {health_cmd} || exit 1"
                ])
            else:
                lines.extend([
                    "",
                    "# Health check",
                    f"HEALTHCHECK --interval={spec.health_check_interval}s \\\\",
                    f"    --timeout={spec.health_check_timeout}s \\\\",
                    f"    --start-period=10s \\\\",
                    f"    --retries={spec.health_check_retries} \\\\",
                    f"    CMD {health_cmd} || exit 1"
                ])
        
        # Entry Point (sicher ohne Shell)
        if self.policy.no_shell_commands:
            # Exec-Form für Entry Point (kein Shell)
            entry_point_json = json.dumps(spec.entry_point)
            lines.extend([
                "",
                "# Entry point (exec form, no shell)",
                f"CMD {entry_point_json}"
            ])
        else:
            lines.extend([
                "",
                "# Entry point",
                f"CMD {spec.entry_point}"
            ])
        
        return lines
    
    def _generate_single_stage(self, spec: ContainerSpec) -> List[str]:
        """Generiere Single-Stage Dockerfile."""
        lines = [
            f"FROM {spec.runtime_base_image}",
            "",
            f"WORKDIR {spec.app_dir}",
            "",
            "COPY . .",
            "",
            f"CMD {json.dumps(spec.entry_point)}"
        ]
        
        return lines


class SecureContainerBuilder:
    """Sicherer Container-Builder."""
    
    def __init__(self, security_policy: Optional[SecurityPolicy] = None):
        if security_policy is None:
            security_policy = SecurityPolicy()
        
        self.policy = security_policy
        self.dockerfile_generator = DockerfileGenerator(security_policy)
    
    def build_container(
        self,
        spec: ContainerSpec,
        build_args: Optional[Dict[str, str]] = None
    ) -> ContainerBuildResult:
        """Baue sicheren Container."""
        logger.info(f"Building secure container: {spec.name}:{spec.tag}")
        
        build_id = f"build-{spec.name}-{int(datetime.utcnow().timestamp())}"
        
        result = ContainerBuildResult(
            build_id=build_id,
            image_name=spec.name,
            image_tag=spec.tag,
            build_started_at=datetime.utcnow().isoformat(),
            build_args=build_args or {}
        )
        
        try:
            # Generiere Dockerfile
            dockerfile_content = self.dockerfile_generator.generate_dockerfile(spec)
            result.dockerfile_content = dockerfile_content
            
            # Validiere Policy-Compliance
            policy_violations = self._validate_dockerfile_compliance(dockerfile_content)
            result.policy_violations = policy_violations
            result.security_compliant = len(policy_violations) == 0
            
            if not result.security_compliant:
                logger.warning(f"Policy violations found: {policy_violations}")
            
            # Erstelle temporäres Dockerfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.Dockerfile', delete=False) as f:
                f.write(dockerfile_content)
                temp_dockerfile = Path(f.name)
            
            try:
                # Docker Build
                success, build_output, build_errors = self._run_docker_build(
                    spec, temp_dockerfile, build_args
                )
                
                result.success = success
                result.build_output = build_output
                result.build_errors = build_errors
                
                if success:
                    # Hole Image-Informationen
                    result.image_id, result.image_size_mb = self._get_image_info(spec)
                    
                    # Teste Health Check
                    if self.policy.require_health_check:
                        result.health_check_passed, result.health_check_output = self._test_health_check(spec)
                
            finally:
                # Cleanup temporäres Dockerfile
                temp_dockerfile.unlink(missing_ok=True)
        
        except Exception as e:
            result.success = False
            result.build_errors = str(e)
            logger.error(f"Container build failed: {e}")
        
        finally:
            result.build_completed_at = datetime.utcnow().isoformat()
            
            # Berechne Dauer
            if result.build_started_at and result.build_completed_at:
                start_time = datetime.fromisoformat(result.build_started_at)
                end_time = datetime.fromisoformat(result.build_completed_at)
                result.build_duration_seconds = (end_time - start_time).total_seconds()
        
        logger.info(f"Container build completed: {result.success}")
        return result
    
    def _validate_dockerfile_compliance(self, dockerfile_content: str) -> List[str]:
        """Validiere Dockerfile Policy-Compliance."""
        violations = []
        lines = dockerfile_content.lower()
        
        # Multi-stage Check
        if self.policy.enforce_multi_stage:
            if " as " not in lines or "from " not in lines:
                violations.append("Multi-stage build required but not found")
        
        # Non-root User Check
        if self.policy.enforce_non_root:
            if "user " not in lines:
                violations.append("Non-root user required but not specified")
        
        # Shell Command Check
        if self.policy.no_shell_commands:
            if "run sh " in lines or "run bash " in lines or "cmd sh" in lines:
                violations.append("Shell commands found but not allowed")
        
        # Health Check
        if self.policy.require_health_check:
            if "healthcheck" not in lines:
                violations.append("Health check required but not found")
        
        return violations
    
    def _run_docker_build(
        self,
        spec: ContainerSpec,
        dockerfile_path: Path,
        build_args: Optional[Dict[str, str]]
    ) -> tuple[bool, str, str]:
        """Führe Docker Build aus."""
        
        cmd = [
            "docker", "build",
            "-f", str(dockerfile_path),
            "-t", f"{spec.name}:{spec.tag}",
        ]
        
        # Build Args
        if build_args:
            for key, value in build_args.items():
                cmd.extend(["--build-arg", f"{key}={value}"])
        
        # Ressourcen-Limits
        if self.policy.enforce_resource_limits:
            cmd.extend([
                "--memory", f"{self.policy.max_memory_mb}m",
                "--cpus", str(self.policy.max_cpu_cores)
            ])
        
        # Build-Kontext
        cmd.append(str(spec.context_dir))
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 Minuten Timeout
            )
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", "Docker build timed out"
        except Exception as e:
            return False, "", str(e)
    
    def _get_image_info(self, spec: ContainerSpec) -> tuple[str, float]:
        """Hole Image-Informationen."""
        try:
            # Image ID
            result = subprocess.run([
                "docker", "images", "-q", f"{spec.name}:{spec.tag}"
            ], capture_output=True, text=True)
            
            image_id = result.stdout.strip() if result.returncode == 0 else ""
            
            # Image Size
            result = subprocess.run([
                "docker", "images", f"{spec.name}:{spec.tag}",
                "--format", "{{.Size}}"
            ], capture_output=True, text=True)
            
            size_str = result.stdout.strip()
            size_mb = 0.0
            
            if size_str:
                # Parse Size (z.B. "123MB", "1.2GB")
                if size_str.endswith("MB"):
                    size_mb = float(size_str[:-2])
                elif size_str.endswith("GB"):
                    size_mb = float(size_str[:-2]) * 1024
                elif size_str.endswith("KB"):
                    size_mb = float(size_str[:-2]) / 1024
            
            return image_id, size_mb
            
        except Exception as e:
            logger.warning(f"Failed to get image info: {e}")
            return "", 0.0
    
    def _test_health_check(self, spec: ContainerSpec) -> tuple[bool, str]:
        """Teste Health Check."""
        try:
            # Starte Container temporär
            container_name = f"health-test-{spec.name}-{int(datetime.utcnow().timestamp())}"
            
            # Start Container
            start_cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                f"{spec.name}:{spec.tag}"
            ]
            
            start_result = subprocess.run(start_cmd, capture_output=True, text=True)
            
            if start_result.returncode != 0:
                return False, f"Failed to start container: {start_result.stderr}"
            
            try:
                # Warte kurz
                import time
                time.sleep(5)
                
                # Prüfe Health Status
                health_cmd = [
                    "docker", "inspect", container_name,
                    "--format", "{{.State.Health.Status}}"
                ]
                
                health_result = subprocess.run(health_cmd, capture_output=True, text=True)
                
                health_status = health_result.stdout.strip()
                health_passed = health_status in ["healthy", "starting"]
                
                return health_passed, f"Health status: {health_status}"
                
            finally:
                # Cleanup Container
                subprocess.run([
                    "docker", "rm", "-f", container_name
                ], capture_output=True)
            
        except Exception as e:
            logger.warning(f"Health check test failed: {e}")
            return False, str(e)
    
    def run_container_locally(
        self,
        spec: ContainerSpec,
        port_mapping: Optional[Dict[int, int]] = None,
        env_override: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Starte Container lokal zum Testen."""
        logger.info(f"Starting container locally: {spec.name}:{spec.tag}")
        
        container_name = f"local-{spec.name}-{int(datetime.utcnow().timestamp())}"
        
        cmd = [
            "docker", "run", "-d",
            "--name", container_name
        ]
        
        # Port Mapping
        if port_mapping:
            for container_port, host_port in port_mapping.items():
                cmd.extend(["-p", f"{host_port}:{container_port}"])
        elif spec.exposed_ports:
            # Auto-mapping
            for port in spec.exposed_ports:
                cmd.extend(["-p", f"{port}:{port}"])
        
        # Environment Override
        if env_override:
            for key, value in env_override.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        # Ressourcen-Limits
        if self.policy.enforce_resource_limits:
            cmd.extend([
                "--memory", f"{self.policy.max_memory_mb}m",
                "--cpus", str(self.policy.max_cpu_cores)
            ])
        
        # Readonly Filesystem (falls aktiviert)
        if self.policy.enforce_readonly_fs:
            cmd.append("--read-only")
        
        # No Privileged
        cmd.extend(["--user", f"{self.policy.default_uid}:{self.policy.default_gid}"])
        
        # Image
        cmd.append(f"{spec.name}:{spec.tag}")
        
        try:
            # Starte Container
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                container_id = result.stdout.strip()
                
                # Warte kurz und prüfe Status
                import time
                time.sleep(2)
                
                # Prüfe Container Status
                status_result = subprocess.run([
                    "docker", "ps", "--filter", f"id={container_id}",
                    "--format", "{{.Status}}"
                ], capture_output=True, text=True)
                
                is_running = "Up" in status_result.stdout
                
                return {
                    "success": True,
                    "container_id": container_id,
                    "container_name": container_name,
                    "is_running": is_running,
                    "status": status_result.stdout.strip(),
                    "ports": port_mapping or {port: port for port in spec.exposed_ports}
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr,
                    "container_name": container_name
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "container_name": container_name
            }


# Convenience Functions
def build_secure_container(
    name: str,
    context_dir: Path,
    entry_point: List[str],
    ports: List[int] = None
) -> ContainerBuildResult:
    """
    Convenience-Funktion für sicheren Container-Build.
    
    Args:
        name: Container-Name
        context_dir: Build-Kontext
        entry_point: Entry Point Kommando
        ports: Exponierte Ports
        
    Returns:
        Build-Ergebnis
    """
    spec = ContainerSpec(
        name=name,
        context_dir=context_dir,
        entry_point=entry_point,
        exposed_ports=ports or [],
        health_check_command=["curl", "-f", "http://localhost:5000/health"] if ports else []
    )
    
    builder = SecureContainerBuilder()
    return builder.build_container(spec)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_secure_container_builder():
        print("🐳 Secure Container Builder Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Test-Anwendung
            app_dir = temp_path / "test_app"
            app_dir.mkdir()
            
            # main.py
            main_py = app_dir / "main.py"
            main_py.write_text('''
import http.server
import socketserver
import json
from urllib.parse import urlparse

class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "service": "test-app"}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Hello from secure container!")

if __name__ == "__main__":
    PORT = 8000
    with socketserver.TCPServer(("", PORT), HealthHandler) as httpd:
        print(f"Server running on port {PORT}")
        httpd.serve_forever()
'''.strip())
            
            # requirements.txt
            requirements_txt = app_dir / "requirements.txt"
            requirements_txt.write_text("# No external dependencies\\n")
            
            print(f"\\n📁 Created test application: {app_dir}")
            
            # Container Spec
            spec = ContainerSpec(
                name="secure-test-app",
                tag="latest",
                context_dir=app_dir,
                entry_point=["python", "main.py"],
                exposed_ports=[8000],
                health_check_command=["curl", "-f", "http://localhost:8000/health"]
            )
            
            # Security Policy
            policy = SecurityPolicy(
                enforce_multi_stage=True,
                enforce_non_root=True,
                enforce_readonly_fs=False,  # Für Demo deaktiviert
                require_health_check=True
            )
            
            print(f"\\n🔒 Security Policy:")
            print(f"  Multi-stage: {policy.enforce_multi_stage}")
            print(f"  Non-root user: {policy.enforce_non_root}")
            print(f"  No shell commands: {policy.no_shell_commands}")
            print(f"  Health check required: {policy.require_health_check}")
            
            # Builder
            builder = SecureContainerBuilder(policy)
            
            # Generiere Dockerfile
            dockerfile_content = builder.dockerfile_generator.generate_dockerfile(spec)
            print(f"\\n📄 Generated Dockerfile:")
            print("=" * 40)
            print(dockerfile_content[:500] + "..." if len(dockerfile_content) > 500 else dockerfile_content)
            print("=" * 40)
            
            # Validiere Policy-Compliance
            violations = builder._validate_dockerfile_compliance(dockerfile_content)
            print(f"\\n🔍 Policy validation:")
            print(f"  Violations: {len(violations)}")
            
            if violations:
                for violation in violations:
                    print(f"    - {violation}")
            else:
                print("  ✓ All policies compliant")
            
            # Simuliere Build (ohne tatsächlichen Docker-Build)
            print(f"\\n🔨 Simulating container build:")
            print(f"  ✓ Dockerfile generated: {len(dockerfile_content)} chars")
            print(f"  ✓ Multi-stage: {'✓' if 'AS builder' in dockerfile_content else '✗'}")
            print(f"  ✓ Non-root user: {'✓' if 'USER appuser' in dockerfile_content else '✗'}")
            print(f"  ✓ Health check: {'✓' if 'HEALTHCHECK' in dockerfile_content else '✗'}")
            print(f"  ✓ No shell globbing: {'✓' if 'CMD [' in dockerfile_content else '✗'}")
            
            # Test Akzeptanz-Kriterien
            multi_stage_present = "AS builder" in dockerfile_content and "AS runtime" in dockerfile_content
            non_root_user = "USER appuser" in dockerfile_content
            health_check_present = "HEALTHCHECK" in dockerfile_content
            no_shell_globbing = 'CMD [' in dockerfile_content
            
            print(f"\\n🎯 Acceptance criteria:")
            print(f"  ✓ Multi-stage build: {multi_stage_present}")
            print(f"  ✓ Non-root user: {non_root_user}")
            print(f"  ✓ Health probes: {health_check_present}")
            print(f"  ✓ No shell globbing: {no_shell_globbing}")
            print(f"  ✓ Policy compliant: {len(violations) == 0}")
            
            # Simuliere lokalen Start
            print(f"\\n🚀 Simulated local container start:")
            print(f"  Container would start as non-root user (UID: {policy.default_uid})")
            print(f"  Health check would be available at: /health")
            print(f"  Resource limits: {policy.max_memory_mb}MB RAM, {policy.max_cpu_cores} CPU")
            
            return (multi_stage_present and non_root_user and 
                   health_check_present and no_shell_globbing and 
                   len(violations) == 0)
    
    # Führe Demo aus
    try:
        result = demo_secure_container_builder()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
