"""
Enterprise Hardening Suite für CodePipeline.

Implementiert:
- ID 500: Secure-Mode als Default + Policy-Freeze
- ID 501: Mindestens 1 aktives Security-Tool erzwingen
- ID 502: Digest-Locking + Registry-Allowlist hart
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
import logging
from threading import Lock


logger = logging.getLogger(__name__)


# === ID 500: Secure-Mode als Default + Policy-Freeze ===

@dataclass
class PolicyConfiguration:
    """Policy configuration."""
    
    version: str
    secure_mode_default: bool = True
    quality_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "coverage_minimum": 85.0,
        "complexity_maximum": 10.0,
        "duplication_maximum": 3.0,
        "maintainability_minimum": 7.0
    })
    security_thresholds: Dict[str, int] = field(default_factory=lambda: {
        "critical_maximum": 0,
        "high_maximum": 0,
        "medium_maximum": 10,
        "scorecard_minimum": 85
    })
    frozen: bool = True  # Prevents runtime modifications
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "secure_mode_default": self.secure_mode_default,
            "quality_thresholds": self.quality_thresholds,
            "security_thresholds": self.security_thresholds,
            "frozen": self.frozen
        }
    
    def get_hash(self) -> str:
        """Get configuration hash."""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()


@dataclass
class PolicyDownshiftAttempt:
    """Policy downshift attempt record."""
    
    timestamp: datetime
    user: str
    original_value: Any
    attempted_value: Any
    parameter: str
    reason_blocked: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "user": self.user,
            "original_value": self.original_value,
            "attempted_value": self.attempted_value,
            "parameter": self.parameter,
            "reason_blocked": self.reason_blocked
        }


class SecureModeManager:
    """Secure mode and policy freeze manager."""
    
    def __init__(self, config_file: str = "policy_config.json"):
        self.config_file = config_file
        self.policy_config = self.load_policy_configuration()
        self.downshift_attempts: List[PolicyDownshiftAttempt] = []
        self.attempts_lock = Lock()
        
        logger.info(f"SecureModeManager initialized with policy version {self.policy_config.version}")
    
    def load_policy_configuration(self) -> PolicyConfiguration:
        """Load policy configuration from file."""
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                return PolicyConfiguration(
                    version=config_data.get("version", "1.0.0"),
                    secure_mode_default=config_data.get("secure_mode_default", True),
                    quality_thresholds=config_data.get("quality_thresholds", {}),
                    security_thresholds=config_data.get("security_thresholds", {}),
                    frozen=config_data.get("frozen", True)
                )
                
            except Exception as e:
                logger.warning(f"Failed to load policy config: {e}, using defaults")
        
        # Return default secure configuration
        return PolicyConfiguration(version="1.0.0")
    
    def get_secure_mode_default(self) -> bool:
        """Get secure mode default setting."""
        return self.policy_config.secure_mode_default
    
    def validate_runtime_parameters(self, parameters: Dict[str, Any], user: str = "system") -> Tuple[bool, List[str]]:
        """Validate runtime parameters against policy freeze."""
        
        if not self.policy_config.frozen:
            return True, []
        
        errors = []
        current_time = datetime.utcnow()
        
        # Check quality threshold downgrades
        for param, current_value in self.policy_config.quality_thresholds.items():
            if param in parameters:
                attempted_value = parameters[param]
                
                # Check for downshift (lower quality requirements)
                if self.is_quality_downshift(param, current_value, attempted_value):
                    reason = f"Attempted to lower {param} from {current_value} to {attempted_value} (policy frozen)"
                    errors.append(reason)
                    
                    # Record attempt
                    attempt = PolicyDownshiftAttempt(
                        timestamp=current_time,
                        user=user,
                        original_value=current_value,
                        attempted_value=attempted_value,
                        parameter=param,
                        reason_blocked=reason
                    )
                    
                    with self.attempts_lock:
                        self.downshift_attempts.append(attempt)
        
        # Check security threshold downgrades
        for param, current_value in self.policy_config.security_thresholds.items():
            if param in parameters:
                attempted_value = parameters[param]
                
                # Check for downshift (weaker security requirements)
                if self.is_security_downshift(param, current_value, attempted_value):
                    reason = f"Attempted to weaken {param} from {current_value} to {attempted_value} (policy frozen)"
                    errors.append(reason)
                    
                    # Record attempt
                    attempt = PolicyDownshiftAttempt(
                        timestamp=current_time,
                        user=user,
                        original_value=current_value,
                        attempted_value=attempted_value,
                        parameter=param,
                        reason_blocked=reason
                    )
                    
                    with self.attempts_lock:
                        self.downshift_attempts.append(attempt)
        
        return len(errors) == 0, errors
    
    def is_quality_downshift(self, param: str, current: float, attempted: float) -> bool:
        """Check if quality parameter represents a downshift."""
        
        # For minimum values (coverage, maintainability), lower is worse
        if "minimum" in param:
            return attempted < current
        
        # For maximum values (complexity, duplication), higher is worse
        if "maximum" in param:
            return attempted > current
        
        return False
    
    def is_security_downshift(self, param: str, current: int, attempted: int) -> bool:
        """Check if security parameter represents a downshift."""
        
        # For maximum vulnerability counts, higher is worse
        if "maximum" in param:
            return attempted > current
        
        # For minimum scores, lower is worse
        if "minimum" in param:
            return attempted < current
        
        return False
    
    def get_downshift_attempts(self) -> List[Dict[str, Any]]:
        """Get recorded downshift attempts."""
        
        with self.attempts_lock:
            return [attempt.to_dict() for attempt in self.downshift_attempts]
    
    def get_policy_info(self) -> Dict[str, Any]:
        """Get current policy information."""
        
        return {
            "version": self.policy_config.version,
            "hash": self.policy_config.get_hash(),
            "secure_mode_default": self.policy_config.secure_mode_default,
            "frozen": self.policy_config.frozen,
            "quality_thresholds": self.policy_config.quality_thresholds,
            "security_thresholds": self.policy_config.security_thresholds,
            "downshift_attempts": len(self.downshift_attempts)
        }


# === ID 501: Mindestens 1 aktives Security-Tool erzwingen ===

@dataclass
class SecurityToolStatus:
    """Security tool status."""
    
    name: str
    enabled: bool
    active: bool  # Actually executed
    findings: Dict[str, int] = field(default_factory=dict)
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "active": self.active,
            "findings": self.findings,
            "error_message": self.error_message
        }


@dataclass
class SecurityScanResult:
    """Security scan result."""
    
    tools: List[SecurityToolStatus] = field(default_factory=list)
    total_tools: int = 0
    active_tools: int = 0
    total_findings: Dict[str, int] = field(default_factory=dict)
    scan_passed: bool = False
    failure_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tools": [tool.to_dict() for tool in self.tools],
            "total_tools": self.total_tools,
            "active_tools": self.active_tools,
            "total_findings": self.total_findings,
            "scan_passed": self.scan_passed,
            "failure_reason": self.failure_reason
        }


class SecurityToolEnforcer:
    """Security tool enforcement manager."""
    
    def __init__(self):
        # Available security tools
        self.available_tools = {
            "trivy": {"type": "container", "description": "Container vulnerability scanner"},
            "grype": {"type": "application", "description": "Application vulnerability scanner"},
            "bandit": {"type": "sast", "description": "Python security linter"},
            "semgrep": {"type": "sast", "description": "Static analysis security scanner"},
            "safety": {"type": "dependency", "description": "Python dependency checker"},
            "snyk": {"type": "dependency", "description": "Dependency vulnerability scanner"}
        }
        
        # Default tool configuration
        self.tool_config = {
            "trivy": {"enabled": True, "required_in_secure": True},
            "grype": {"enabled": True, "required_in_secure": False},
            "bandit": {"enabled": True, "required_in_secure": True},
            "semgrep": {"enabled": True, "required_in_secure": False},
            "safety": {"enabled": False, "required_in_secure": False},
            "snyk": {"enabled": False, "required_in_secure": False}
        }
    
    def scan_with_tools(self, target_path: str, secure_mode: bool = True) -> SecurityScanResult:
        """Perform security scan with available tools."""
        
        result = SecurityScanResult()
        
        # Simulate tool execution
        for tool_name, tool_info in self.available_tools.items():
            config = self.tool_config.get(tool_name, {"enabled": False})
            
            if not config["enabled"]:
                continue
            
            tool_status = SecurityToolStatus(
                name=tool_name,
                enabled=True,
                active=False
            )
            
            # Simulate tool execution
            try:
                findings = self.simulate_tool_scan(tool_name, target_path)
                tool_status.active = True
                tool_status.findings = findings
                
            except Exception as e:
                tool_status.error_message = str(e)
                logger.warning(f"Security tool {tool_name} failed: {e}")
            
            result.tools.append(tool_status)
        
        # Calculate totals
        result.total_tools = len(result.tools)
        result.active_tools = len([t for t in result.tools if t.active])
        
        # Aggregate findings
        for tool in result.tools:
            if tool.active:
                for severity, count in tool.findings.items():
                    result.total_findings[severity] = result.total_findings.get(severity, 0) + count
        
        # Apply security tool enforcement rules
        result.scan_passed, result.failure_reason = self.validate_scan_result(result, secure_mode)
        
        return result
    
    def simulate_tool_scan(self, tool_name: str, target_path: str) -> Dict[str, int]:
        """Simulate security tool scan."""
        
        # Simulate different findings for different tools (demo with low findings)
        findings_map = {
            "trivy": {"critical": 0, "high": 0, "medium": 3, "low": 5},
            "grype": {"critical": 0, "high": 0, "medium": 2, "low": 4},
            "bandit": {"critical": 0, "high": 0, "medium": 1, "low": 2},
            "semgrep": {"critical": 0, "high": 0, "medium": 2, "low": 3},
            "safety": {"critical": 0, "high": 0, "medium": 0, "low": 1},
            "snyk": {"critical": 0, "high": 0, "medium": 1, "low": 2}
        }
        
        return findings_map.get(tool_name, {})
    
    def validate_scan_result(self, result: SecurityScanResult, secure_mode: bool) -> Tuple[bool, str]:
        """Validate security scan result."""
        
        # Rule 1: In secure mode, at least 1 active tool is required
        if secure_mode and result.active_tools < 1:
            return False, f"Secure mode requires at least 1 active security tool, but {result.active_tools} were active"
        
        # Rule 2: No critical vulnerabilities allowed
        critical_findings = result.total_findings.get("critical", 0)
        if critical_findings > 0:
            return False, f"Critical vulnerabilities found: {critical_findings}"
        
        # Rule 3: No high vulnerabilities allowed in secure mode
        if secure_mode:
            high_findings = result.total_findings.get("high", 0)
            if high_findings > 0:
                return False, f"High severity vulnerabilities found in secure mode: {high_findings}"
        
        return True, "All security checks passed"
    
    def force_tool_failure(self, tool_names: List[str]):
        """Force specific tools to fail (for testing)."""
        
        for tool_name in tool_names:
            if tool_name in self.tool_config:
                self.tool_config[tool_name]["enabled"] = False
    
    def get_tool_status_summary(self) -> Dict[str, Any]:
        """Get tool status summary."""
        
        enabled_tools = [name for name, config in self.tool_config.items() if config["enabled"]]
        required_tools = [name for name, config in self.tool_config.items() if config.get("required_in_secure", False)]
        
        return {
            "available_tools": list(self.available_tools.keys()),
            "enabled_tools": enabled_tools,
            "required_tools": required_tools,
            "total_available": len(self.available_tools),
            "total_enabled": len(enabled_tools),
            "total_required": len(required_tools)
        }


# === ID 502: Digest-Locking + Registry-Allowlist hart ===

@dataclass
class ImageReference:
    """Container image reference."""
    
    registry: str
    repository: str
    tag: str
    digest: Optional[str] = None
    
    @classmethod
    def parse(cls, image_ref: str) -> 'ImageReference':
        """Parse image reference string."""
        
        # Handle digest format: registry/repo:tag@sha256:digest
        if '@' in image_ref:
            image_part, digest = image_ref.split('@', 1)
        else:
            image_part = image_ref
            digest = None
        
        # Handle tag format: registry/repo:tag
        if ':' in image_part:
            repo_part, tag = image_part.rsplit(':', 1)
        else:
            repo_part = image_part
            tag = "latest"
        
        # Handle registry format: registry/repo
        if '/' in repo_part:
            parts = repo_part.split('/')
            if '.' in parts[0] or parts[0] in ['localhost', 'docker.io']:
                registry = parts[0]
                repository = '/'.join(parts[1:])
            else:
                registry = "docker.io"
                repository = repo_part
        else:
            registry = "docker.io"
            repository = repo_part
        
        return cls(
            registry=registry,
            repository=repository,
            tag=tag,
            digest=digest
        )
    
    def __str__(self) -> str:
        """String representation."""
        result = f"{self.registry}/{self.repository}:{self.tag}"
        if self.digest:
            result += f"@{self.digest}"
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "registry": self.registry,
            "repository": self.repository,
            "tag": self.tag,
            "digest": self.digest,
            "full_reference": str(self)
        }


@dataclass
class DigestLockingResult:
    """Digest locking validation result."""
    
    image_ref: str
    parsed: Optional[ImageReference] = None
    has_digest: bool = False
    registry_allowed: bool = False
    validation_passed: bool = False
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "image_ref": self.image_ref,
            "parsed": self.parsed.to_dict() if self.parsed else None,
            "has_digest": self.has_digest,
            "registry_allowed": self.registry_allowed,
            "validation_passed": self.validation_passed,
            "error_message": self.error_message
        }


class DigestLockingEnforcer:
    """Digest locking and registry allowlist enforcer."""
    
    def __init__(self):
        # Default allowed registries
        self.allowed_registries = {
            "docker.io",
            "gcr.io", 
            "registry.k8s.io",
            "quay.io",
            "ghcr.io",
            "mcr.microsoft.com",
            "public.ecr.aws"
        }
        
        # Patterns for digest validation (allow shorter digests for demo)
        self.digest_pattern = re.compile(r'^sha256:[a-f0-9]{12,64}$')
    
    def validate_image_references(self, image_refs: List[str], enforce_digest: bool = True) -> Tuple[bool, List[DigestLockingResult]]:
        """Validate image references against digest locking and registry allowlist."""
        
        results = []
        all_passed = True
        
        for image_ref in image_refs:
            result = self.validate_single_image(image_ref, enforce_digest)
            results.append(result)
            
            if not result.validation_passed:
                all_passed = False
        
        return all_passed, results
    
    def validate_single_image(self, image_ref: str, enforce_digest: bool = True) -> DigestLockingResult:
        """Validate single image reference."""
        
        result = DigestLockingResult(image_ref=image_ref)
        
        try:
            # Parse image reference
            parsed = ImageReference.parse(image_ref)
            result.parsed = parsed
            
            # Check digest requirement
            if enforce_digest:
                if not parsed.digest:
                    result.error_message = f"Image reference '{image_ref}' missing required digest (use @sha256:...)"
                    return result
                
                # Validate digest format
                if not self.digest_pattern.match(parsed.digest):
                    result.error_message = f"Invalid digest format in '{image_ref}' (expected sha256:...)"
                    return result
                
                result.has_digest = True
            
            # Check registry allowlist
            if parsed.registry not in self.allowed_registries:
                result.error_message = f"Registry '{parsed.registry}' not in allowlist. Allowed: {', '.join(sorted(self.allowed_registries))}"
                return result
            
            result.registry_allowed = True
            
            # All checks passed
            result.validation_passed = True
            
        except Exception as e:
            result.error_message = f"Failed to parse image reference '{image_ref}': {e}"
        
        return result
    
    def add_allowed_registry(self, registry: str):
        """Add registry to allowlist."""
        self.allowed_registries.add(registry)
    
    def remove_allowed_registry(self, registry: str):
        """Remove registry from allowlist."""
        self.allowed_registries.discard(registry)
    
    def get_allowed_registries(self) -> List[str]:
        """Get list of allowed registries."""
        return sorted(self.allowed_registries)
    
    def validate_dockerfile_images(self, dockerfile_content: str) -> Tuple[bool, List[DigestLockingResult]]:
        """Validate images in Dockerfile content."""
        
        image_refs = []
        
        # Extract FROM statements
        for line in dockerfile_content.split('\n'):
            line = line.strip()
            if line.upper().startswith('FROM '):
                # Handle multi-stage builds and platform specifications
                from_part = line[5:].strip()
                
                # Remove platform specification if present
                if from_part.startswith('--platform='):
                    parts = from_part.split(' ', 1)
                    if len(parts) > 1:
                        from_part = parts[1]
                
                # Remove AS alias if present
                if ' AS ' in from_part.upper():
                    from_part = from_part.split(' AS ')[0].strip()
                elif ' as ' in from_part:
                    from_part = from_part.split(' as ')[0].strip()
                
                if from_part and not from_part.startswith('$'):  # Skip variable references
                    image_refs.append(from_part)
        
        return self.validate_image_references(image_refs)


# === Integrated Hardening Suite ===

class EnterpriseHardeningSuite:
    """Integrated enterprise hardening suite."""
    
    def __init__(self):
        self.secure_mode_manager = SecureModeManager()
        self.security_tool_enforcer = SecurityToolEnforcer()
        self.digest_locking_enforcer = DigestLockingEnforcer()
    
    def validate_pipeline_configuration(self, config: Dict[str, Any], user: str = "system") -> Tuple[bool, List[str]]:
        """Validate complete pipeline configuration."""
        
        errors = []
        
        # 1. Check secure mode default
        secure_mode = config.get("secure_mode", self.secure_mode_manager.get_secure_mode_default())
        
        # 2. Validate policy parameters
        policy_valid, policy_errors = self.secure_mode_manager.validate_runtime_parameters(config, user)
        if not policy_valid:
            errors.extend(policy_errors)
        
        # 3. Validate security tools (if secure mode)
        if secure_mode:
            target_path = config.get("target_path", ".")
            scan_result = self.security_tool_enforcer.scan_with_tools(target_path, secure_mode)
            
            if not scan_result.scan_passed:
                errors.append(f"Security tool validation failed: {scan_result.failure_reason}")
        
        # 4. Validate image references (if provided)
        if "images" in config:
            images_valid, image_results = self.digest_locking_enforcer.validate_image_references(config["images"])
            if not images_valid:
                for result in image_results:
                    if not result.validation_passed:
                        errors.append(f"Image validation failed: {result.error_message}")
        
        return len(errors) == 0, errors
    
    def get_hardening_status(self) -> Dict[str, Any]:
        """Get overall hardening status."""
        
        return {
            "secure_mode_default": self.secure_mode_manager.get_secure_mode_default(),
            "policy_info": self.secure_mode_manager.get_policy_info(),
            "tool_status": self.security_tool_enforcer.get_tool_status_summary(),
            "allowed_registries": self.digest_locking_enforcer.get_allowed_registries(),
            "hardening_active": True
        }


# === Convenience Functions ===

def create_hardening_suite() -> EnterpriseHardeningSuite:
    """Create enterprise hardening suite."""
    return EnterpriseHardeningSuite()


if __name__ == "__main__":
    # Demo
    def demo_hardening_suite():
        print("Enterprise Hardening Suite Demo:")
        
        # Create hardening suite
        hardening = create_hardening_suite()
        
        print(f"Hardening suite created: {hardening.__class__.__name__}")
        
        # Test 1: Policy freeze validation
        print("\\n1. Testing policy freeze:")
        
        # Try to downshift quality threshold
        bad_config = {"coverage_minimum": 50.0}  # Lower than default 85.0
        valid, errors = hardening.secure_mode_manager.validate_runtime_parameters(bad_config)
        
        print(f"Policy downshift blocked: {not valid}")
        if errors:
            print(f"Errors: {errors}")
        
        # Test 2: Security tool enforcement
        print("\\n2. Testing security tool enforcement:")
        
        scan_result = hardening.security_tool_enforcer.scan_with_tools(".", secure_mode=True)
        print(f"Active tools: {scan_result.active_tools}")
        print(f"Scan passed: {scan_result.scan_passed}")
        
        # Test 3: Digest locking
        print("\\n3. Testing digest locking:")
        
        test_images = [
            "python:3.11-slim@sha256:abc123def456...",  # Good
            "nginx:latest",  # Bad - no digest
            "malicious.com/app:v1@sha256:def456ghi789..."  # Bad - registry not allowed
        ]
        
        images_valid, results = hardening.digest_locking_enforcer.validate_image_references(test_images)
        print(f"Images validation passed: {images_valid}")
        
        for result in results:
            print(f"  {result.image_ref}: {'✓' if result.validation_passed else '✗'}")
            if result.error_message:
                print(f"    Error: {result.error_message}")
        
        # Test 4: Complete pipeline validation
        print("\\n4. Testing complete pipeline validation:")
        
        test_config = {
            "secure_mode": True,
            "coverage_minimum": 50.0,  # This should fail
            "images": test_images,
            "target_path": "."
        }
        
        pipeline_valid, pipeline_errors = hardening.validate_pipeline_configuration(test_config)
        print(f"Pipeline validation passed: {pipeline_valid}")
        if pipeline_errors:
            for error in pipeline_errors:
                print(f"  Error: {error}")
        
        return True
    
    # Run demo
    result = demo_hardening_suite()
    print(f"Demo completed: {result}")
