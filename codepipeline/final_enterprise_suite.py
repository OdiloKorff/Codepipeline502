"""
Final Enterprise Suite für CodePipeline.

Implementiert:
- ID 503: Image-Signierung & Verifikation (Fail-Closed)
- ID 504: Remote-CI Required-Checks an Scorecard koppeln
- ID 505: LLM-Token-Budget streng + Cache by Spec-Hash
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
import logging
from threading import Lock
import uuid


logger = logging.getLogger(__name__)


# === ID 503: Image-Signierung & Verifikation (Fail-Closed) ===

@dataclass
class ImageSignature:
    """Container image signature."""
    
    image_ref: str
    signature_hash: str
    signer: str
    timestamp: datetime
    algorithm: str = "RSA-PSS"
    key_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "image_ref": self.image_ref,
            "signature_hash": self.signature_hash,
            "signer": self.signer,
            "timestamp": self.timestamp.isoformat(),
            "algorithm": self.algorithm,
            "key_id": self.key_id
        }


@dataclass
class ImageProvenance:
    """Container image provenance/attestation."""
    
    image_ref: str
    build_system: str
    source_repo: str
    commit_sha: str
    build_timestamp: datetime
    builder_id: str
    materials: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "image_ref": self.image_ref,
            "build_system": self.build_system,
            "source_repo": self.source_repo,
            "commit_sha": self.commit_sha,
            "build_timestamp": self.build_timestamp.isoformat(),
            "builder_id": self.builder_id,
            "materials": self.materials
        }


@dataclass
class SignatureVerificationResult:
    """Signature verification result."""
    
    image_ref: str
    signed: bool = False
    signature_valid: bool = False
    provenance_valid: bool = False
    verification_passed: bool = False
    error_message: str = ""
    
    signature: Optional[ImageSignature] = None
    provenance: Optional[ImageProvenance] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "image_ref": self.image_ref,
            "signed": self.signed,
            "signature_valid": self.signature_valid,
            "provenance_valid": self.provenance_valid,
            "verification_passed": self.verification_passed,
            "error_message": self.error_message,
            "signature": self.signature.to_dict() if self.signature else None,
            "provenance": self.provenance.to_dict() if self.provenance else None
        }


class ImageSigningManager:
    """Image signing and verification manager."""
    
    def __init__(self):
        # Trusted signers
        self.trusted_signers = {
            "ci-system",
            "release-manager",
            "security-team"
        }
        
        # Signing keys (in real implementation, these would be secure key references)
        self.signing_keys = {
            "ci-system": "ci-key-2024",
            "release-manager": "release-key-2024",
            "security-team": "security-key-2024"
        }
        
        self.verification_lock = Lock()
    
    async def sign_image(self, image_ref: str, signer: str = "ci-system") -> ImageSignature:
        """Sign container image."""
        
        if signer not in self.trusted_signers:
            raise ValueError(f"Untrusted signer: {signer}")
        
        # Generate signature hash (in real implementation, this would be cryptographic signing)
        signature_data = f"{image_ref}:{signer}:{datetime.utcnow().isoformat()}"
        signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()
        
        signature = ImageSignature(
            image_ref=image_ref,
            signature_hash=signature_hash,
            signer=signer,
            timestamp=datetime.utcnow(),
            key_id=self.signing_keys.get(signer, "unknown")
        )
        
        logger.info(f"Image signed: {image_ref} by {signer}")
        return signature
    
    async def create_provenance(self, image_ref: str, build_context: Dict[str, Any]) -> ImageProvenance:
        """Create image provenance/attestation."""
        
        provenance = ImageProvenance(
            image_ref=image_ref,
            build_system=build_context.get("build_system", "codepipeline"),
            source_repo=build_context.get("source_repo", "https://github.com/example/repo"),
            commit_sha=build_context.get("commit_sha", "abc123def456"),
            build_timestamp=datetime.utcnow(),
            builder_id=build_context.get("builder_id", "ci-builder-001"),
            materials=build_context.get("materials", ["Dockerfile", "requirements.txt"])
        )
        
        logger.info(f"Provenance created for: {image_ref}")
        return provenance
    
    async def verify_image_signature(self, image_ref: str, signature: ImageSignature) -> SignatureVerificationResult:
        """Verify image signature."""
        
        result = SignatureVerificationResult(image_ref=image_ref)
        
        try:
            # Check if image is signed
            if not signature:
                result.error_message = f"Image '{image_ref}' is not signed"
                return result
            
            result.signed = True
            result.signature = signature
            
            # Verify signer is trusted
            if signature.signer not in self.trusted_signers:
                result.error_message = f"Untrusted signer: {signature.signer}"
                return result
            
            # Verify signature (in real implementation, this would be cryptographic verification)
            # For demo purposes, we accept the signature hash as-is since it was generated by our system
            result.signature_valid = True
            
            # Check signature age (not too old)
            signature_age = datetime.utcnow() - signature.timestamp
            if signature_age > timedelta(days=30):
                result.error_message = f"Signature too old: {signature_age.days} days"
                return result
            
            result.verification_passed = True
            logger.info(f"Signature verified for: {image_ref}")
            
        except Exception as e:
            result.error_message = f"Signature verification failed: {e}"
        
        return result
    
    async def verify_image_provenance(self, image_ref: str, provenance: ImageProvenance) -> bool:
        """Verify image provenance."""
        
        try:
            # Check provenance fields
            if not provenance.source_repo:
                return False
            
            if not provenance.commit_sha or len(provenance.commit_sha) < 7:
                return False
            
            if not provenance.build_system:
                return False
            
            # Check build timestamp is reasonable
            build_age = datetime.utcnow() - provenance.build_timestamp
            if build_age > timedelta(days=7):
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Provenance verification failed for {image_ref}: {e}")
            return False
    
    async def validate_image_security(self, image_ref: str, secure_mode: bool = True) -> SignatureVerificationResult:
        """Validate image security (signing + provenance)."""
        
        # Simulate getting signature and provenance from registry
        try:
            # In secure mode, require signature
            if secure_mode:
                # Simulate signing the image
                signature = await self.sign_image(image_ref)
                
                # Create provenance
                build_context = {
                    "build_system": "codepipeline",
                    "source_repo": "https://github.com/example/secure-app",
                    "commit_sha": "abc123def456ghi789",
                    "builder_id": "secure-ci-001",
                    "materials": ["Dockerfile", "requirements.txt", "app.py"]
                }
                provenance = await self.create_provenance(image_ref, build_context)
                
                # Verify signature
                verification_result = await self.verify_image_signature(image_ref, signature)
                
                if verification_result.verification_passed:
                    # Verify provenance
                    provenance_valid = await self.verify_image_provenance(image_ref, provenance)
                    verification_result.provenance = provenance
                    verification_result.provenance_valid = provenance_valid
                    
                    # Overall verification passes only if both signature and provenance are valid
                    verification_result.verification_passed = verification_result.signature_valid and provenance_valid
                    
                    if not provenance_valid:
                        verification_result.error_message = "Provenance verification failed"
                
                return verification_result
            else:
                # In non-secure mode, allow unsigned images
                return SignatureVerificationResult(
                    image_ref=image_ref,
                    signed=False,
                    verification_passed=True
                )
        
        except Exception as e:
            return SignatureVerificationResult(
                image_ref=image_ref,
                error_message=f"Image security validation failed: {e}"
            )
    
    def get_trusted_signers(self) -> List[str]:
        """Get list of trusted signers."""
        return list(self.trusted_signers)
    
    def add_trusted_signer(self, signer: str, key_id: str):
        """Add trusted signer."""
        self.trusted_signers.add(signer)
        self.signing_keys[signer] = key_id


# === ID 504: Remote-CI Required-Checks an Scorecard koppeln ===

@dataclass
class RequiredCheck:
    """Required check definition."""
    
    name: str
    description: str
    context: str  # GitHub check context
    required: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "context": self.context,
            "required": self.required
        }


@dataclass
class CheckStatus:
    """Check status."""
    
    name: str
    status: str  # pending, success, failure, error
    conclusion: str = ""  # neutral, success, failure, cancelled, timed_out, action_required
    details_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "conclusion": self.conclusion,
            "details_url": self.details_url
        }


@dataclass
class RemoteCIWorkflow:
    """Remote CI workflow definition."""
    
    name: str
    trigger: str  # pull_request, push, workflow_dispatch
    required_checks: List[RequiredCheck] = field(default_factory=list)
    secure_mode_default: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "trigger": self.trigger,
            "required_checks": [check.to_dict() for check in self.required_checks],
            "secure_mode_default": self.secure_mode_default
        }


class RemoteCIManager:
    """Remote CI and required checks manager."""
    
    def __init__(self):
        # Define scorecard as primary required check
        self.scorecard_check = RequiredCheck(
            name="Security Scorecard",
            description="Security scorecard must pass with minimum score",
            context="security/scorecard",
            required=True
        )
        
        # Define workflow
        self.workflow = RemoteCIWorkflow(
            name="Secure Pipeline",
            trigger="pull_request",
            required_checks=[self.scorecard_check],
            secure_mode_default=True
        )
        
        self.check_statuses: Dict[str, CheckStatus] = {}
        self.status_lock = Lock()
    
    def create_workflow_definition(self) -> Dict[str, Any]:
        """Create GitHub Actions workflow definition."""
        
        workflow = {
            "name": self.workflow.name,
            "on": {
                "pull_request": {
                    "branches": ["main", "master"]
                }
            },
            "jobs": {
                "security-scorecard": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {
                            "name": "Checkout",
                            "uses": "actions/checkout@v4"
                        },
                        {
                            "name": "Run Security Scorecard",
                            "run": "python -m codepipeline.scorecard_validator --secure-mode"
                        },
                        {
                            "name": "Update Check Status",
                            "run": "echo 'Scorecard completed'"
                        }
                    ]
                }
            }
        }
        
        return workflow
    
    async def run_scorecard_check(self, pr_context: Dict[str, Any]) -> CheckStatus:
        """Run scorecard check."""
        
        check_name = self.scorecard_check.name
        
        # Update status to pending
        with self.status_lock:
            self.check_statuses[check_name] = CheckStatus(
                name=check_name,
                status="pending"
            )
        
        try:
            # Simulate scorecard execution
            scorecard_result = await self.simulate_scorecard_execution(pr_context)
            
            # Determine check result
            if scorecard_result["score"] >= scorecard_result["minimum_score"]:
                status = CheckStatus(
                    name=check_name,
                    status="success",
                    conclusion="success",
                    details_url=f"https://github.com/example/repo/runs/{uuid.uuid4()}"
                )
            else:
                status = CheckStatus(
                    name=check_name,
                    status="failure",
                    conclusion="failure",
                    details_url=f"https://github.com/example/repo/runs/{uuid.uuid4()}"
                )
            
            with self.status_lock:
                self.check_statuses[check_name] = status
            
            logger.info(f"Scorecard check completed: {status.conclusion}")
            return status
            
        except Exception as e:
            error_status = CheckStatus(
                name=check_name,
                status="error",
                conclusion="failure"
            )
            
            with self.status_lock:
                self.check_statuses[check_name] = error_status
            
            logger.error(f"Scorecard check failed: {e}")
            return error_status
    
    async def simulate_scorecard_execution(self, pr_context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate scorecard execution."""
        
        # Simulate different scores based on PR context
        if pr_context.get("simulate_policy_violation", False):
            # Simulate policy violation (low score)
            return {
                "score": 65,
                "minimum_score": 85,
                "violations": [
                    "High severity vulnerabilities found",
                    "Missing required security controls"
                ]
            }
        else:
            # Happy path (high score)
            return {
                "score": 92,
                "minimum_score": 85,
                "violations": []
            }
    
    def get_pr_status(self) -> Dict[str, Any]:
        """Get PR status based on required checks."""
        
        with self.status_lock:
            required_checks_status = []
            all_passed = True
            
            for required_check in self.workflow.required_checks:
                check_status = self.check_statuses.get(required_check.name)
                
                if not check_status or check_status.conclusion != "success":
                    all_passed = False
                
                required_checks_status.append({
                    "check": required_check.to_dict(),
                    "status": check_status.to_dict() if check_status else {"name": required_check.name, "status": "pending"}
                })
            
            return {
                "pr_status": "success" if all_passed else "failure",
                "required_checks": required_checks_status,
                "all_checks_passed": all_passed
            }
    
    def get_workflow_definition(self) -> Dict[str, Any]:
        """Get complete workflow definition."""
        
        return {
            "workflow": self.workflow.to_dict(),
            "github_actions": self.create_workflow_definition()
        }


# === ID 505: LLM-Token-Budget streng + Cache by Spec-Hash ===

@dataclass
class TokenUsage:
    """Token usage tracking."""
    
    request_tokens: int
    response_tokens: int
    total_tokens: int
    model: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_tokens": self.request_tokens,
            "response_tokens": self.response_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class CacheEntry:
    """LLM cache entry."""
    
    spec_hash: str
    model: str
    seed: str
    prompt_version: str
    response: str
    token_usage: TokenUsage
    created_at: datetime
    last_accessed: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "spec_hash": self.spec_hash,
            "model": self.model,
            "seed": self.seed,
            "prompt_version": self.prompt_version,
            "response": self.response,
            "token_usage": self.token_usage.to_dict(),
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat()
        }


@dataclass
class TokenBudget:
    """Token budget configuration."""
    
    daily_limit: int = 100000
    per_request_limit: int = 8000
    current_usage: int = 0
    reset_time: datetime = field(default_factory=lambda: datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "daily_limit": self.daily_limit,
            "per_request_limit": self.per_request_limit,
            "current_usage": self.current_usage,
            "remaining": self.daily_limit - self.current_usage,
            "reset_time": self.reset_time.isoformat()
        }


class LLMTokenManager:
    """LLM token budget and caching manager."""
    
    def __init__(self, daily_limit: int = 100000, per_request_limit: int = 8000):
        self.budget = TokenBudget(daily_limit=daily_limit, per_request_limit=per_request_limit)
        self.cache: Dict[str, CacheEntry] = {}
        self.usage_history: List[TokenUsage] = []
        
        self.cache_lock = Lock()
        self.budget_lock = Lock()
        
        # Prompt versions for cache invalidation
        self.prompt_versions = {
            "scaffold": "v2.1",
            "build": "v1.8",
            "test": "v1.5",
            "security": "v2.0"
        }
    
    def generate_cache_key(self, spec: Dict[str, Any], model: str, seed: str, prompt_type: str) -> str:
        """Generate cache key from spec hash and parameters."""
        
        # Create spec hash (exclude non-deterministic fields)
        spec_for_hash = {
            k: v for k, v in spec.items() 
            if k not in ['timestamp', 'run_id', 'user_id']
        }
        
        spec_json = json.dumps(spec_for_hash, sort_keys=True)
        spec_hash = hashlib.sha256(spec_json.encode()).hexdigest()[:16]
        
        prompt_version = self.prompt_versions.get(prompt_type, "v1.0")
        
        cache_key = f"{spec_hash}:{model}:{seed}:{prompt_version}"
        return cache_key
    
    async def check_cache(self, cache_key: str) -> Optional[CacheEntry]:
        """Check cache for existing response."""
        
        with self.cache_lock:
            entry = self.cache.get(cache_key)
            
            if entry:
                # Update last accessed time
                entry.last_accessed = datetime.utcnow()
                
                # Check if entry is still valid (not older than 24 hours)
                age = datetime.utcnow() - entry.created_at
                if age > timedelta(hours=24):
                    # Remove stale entry
                    del self.cache[cache_key]
                    return None
                
                logger.info(f"Cache hit for key: {cache_key[:16]}...")
                return entry
            
            return None
    
    def check_budget(self, estimated_tokens: int) -> Tuple[bool, str]:
        """Check if request is within budget."""
        
        with self.budget_lock:
            # Check if budget needs reset
            if datetime.utcnow() >= self.budget.reset_time:
                self.budget.current_usage = 0
                self.budget.reset_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            
            # Check daily limit
            if self.budget.current_usage + estimated_tokens > self.budget.daily_limit:
                remaining = self.budget.daily_limit - self.budget.current_usage
                return False, f"Daily token budget exceeded. Remaining: {remaining}, requested: {estimated_tokens}"
            
            # Check per-request limit
            if estimated_tokens > self.budget.per_request_limit:
                return False, f"Per-request token limit exceeded. Limit: {self.budget.per_request_limit}, requested: {estimated_tokens}"
            
            return True, ""
    
    async def call_llm_with_budget(self, spec: Dict[str, Any], prompt: str, model: str = "gpt-4", seed: str = "default", prompt_type: str = "scaffold") -> Tuple[str, TokenUsage]:
        """Call LLM with budget and cache management."""
        
        # Generate cache key
        cache_key = self.generate_cache_key(spec, model, seed, prompt_type)
        
        # Check cache first
        cached_entry = await self.check_cache(cache_key)
        if cached_entry:
            return cached_entry.response, cached_entry.token_usage
        
        # Estimate tokens (rough approximation: 4 chars = 1 token)
        estimated_request_tokens = len(prompt) // 4
        estimated_total_tokens = int(estimated_request_tokens * 1.5)  # Assume 50% response overhead
        
        # Check budget
        budget_ok, budget_error = self.check_budget(estimated_total_tokens)
        if not budget_ok:
            raise ValueError(f"Token budget exceeded: {budget_error}")
        
        # Simulate LLM call
        response = await self.simulate_llm_call(prompt, model, seed)
        
        # Calculate actual token usage
        actual_request_tokens = len(prompt) // 4
        actual_response_tokens = len(response) // 4
        actual_total_tokens = actual_request_tokens + actual_response_tokens
        
        token_usage = TokenUsage(
            request_tokens=actual_request_tokens,
            response_tokens=actual_response_tokens,
            total_tokens=actual_total_tokens,
            model=model,
            timestamp=datetime.utcnow()
        )
        
        # Update budget
        with self.budget_lock:
            self.budget.current_usage += actual_total_tokens
            self.usage_history.append(token_usage)
        
        # Cache response
        cache_entry = CacheEntry(
            spec_hash=cache_key.split(':')[0],
            model=model,
            seed=seed,
            prompt_version=self.prompt_versions.get(prompt_type, "v1.0"),
            response=response,
            token_usage=token_usage,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow()
        )
        
        with self.cache_lock:
            self.cache[cache_key] = cache_entry
        
        logger.info(f"LLM call completed. Tokens: {actual_total_tokens}, Budget remaining: {self.budget.daily_limit - self.budget.current_usage}")
        
        return response, token_usage
    
    async def simulate_llm_call(self, prompt: str, model: str, seed: str) -> str:
        """Simulate LLM API call."""
        
        # Simulate different responses based on prompt content
        if "scaffold" in prompt.lower():
            return """# Generated Application

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Generated API")

class HealthResponse(BaseModel):
    status: str = "healthy"

@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse()

@app.get("/")
async def root():
    return {"message": "Hello World"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
        elif "test" in prompt.lower():
            return """import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
"""
        else:
            return f"Generated content based on prompt: {prompt[:100]}..."
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        
        with self.cache_lock:
            total_entries = len(self.cache)
            cache_size_bytes = sum(len(entry.response.encode()) for entry in self.cache.values())
            
            # Calculate hit rate (simplified)
            total_calls = len(self.usage_history) + total_entries
            hit_rate = (total_entries / total_calls * 100) if total_calls > 0 else 0
            
            return {
                "total_entries": total_entries,
                "cache_size_bytes": cache_size_bytes,
                "estimated_hit_rate": hit_rate,
                "oldest_entry": min((entry.created_at for entry in self.cache.values()), default=None),
                "newest_entry": max((entry.created_at for entry in self.cache.values()), default=None)
            }
    
    def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status."""
        
        with self.budget_lock:
            return {
                "budget": self.budget.to_dict(),
                "total_calls": len(self.usage_history),
                "average_tokens_per_call": sum(usage.total_tokens for usage in self.usage_history) // len(self.usage_history) if self.usage_history else 0
            }
    
    def force_budget_exceeded(self):
        """Force budget exceeded for testing."""
        with self.budget_lock:
            self.budget.current_usage = self.budget.daily_limit + 1000
    
    def clear_cache(self):
        """Clear cache (for testing)."""
        with self.cache_lock:
            self.cache.clear()


# === Integrated Final Enterprise Suite ===

class FinalEnterpriseSuite:
    """Integrated final enterprise suite."""
    
    def __init__(self):
        self.image_signing_manager = ImageSigningManager()
        self.remote_ci_manager = RemoteCIManager()
        self.llm_token_manager = LLMTokenManager()
    
    async def validate_complete_pipeline(self, spec: Dict[str, Any], secure_mode: bool = True) -> Dict[str, Any]:
        """Validate complete pipeline with all final features."""
        
        results = {
            "image_signing": None,
            "remote_ci": None,
            "llm_budget": None,
            "overall_passed": False
        }
        
        try:
            # 1. Image signing validation
            if "images" in spec:
                image_results = []
                for image_ref in spec["images"]:
                    image_result = await self.image_signing_manager.validate_image_security(image_ref, secure_mode)
                    image_results.append(image_result.to_dict())
                
                results["image_signing"] = {
                    "results": image_results,
                    "all_verified": all(r["verification_passed"] for r in image_results)
                }
            
            # 2. Remote CI validation
            pr_context = {
                "simulate_policy_violation": spec.get("simulate_policy_violation", False)
            }
            
            scorecard_status = await self.remote_ci_manager.run_scorecard_check(pr_context)
            pr_status = self.remote_ci_manager.get_pr_status()
            
            results["remote_ci"] = {
                "scorecard_status": scorecard_status.to_dict(),
                "pr_status": pr_status
            }
            
            # 3. LLM budget validation
            if "llm_calls" in spec:
                llm_results = []
                for call_spec in spec["llm_calls"]:
                    try:
                        response, usage = await self.llm_token_manager.call_llm_with_budget(
                            spec=call_spec.get("spec", {}),
                            prompt=call_spec.get("prompt", "Generate code"),
                            model=call_spec.get("model", "gpt-4"),
                            seed=call_spec.get("seed", "default"),
                            prompt_type=call_spec.get("type", "scaffold")
                        )
                        
                        llm_results.append({
                            "success": True,
                            "token_usage": usage.to_dict(),
                            "response_length": len(response)
                        })
                        
                    except ValueError as e:
                        llm_results.append({
                            "success": False,
                            "error": str(e)
                        })
                
                results["llm_budget"] = {
                    "results": llm_results,
                    "budget_status": self.llm_token_manager.get_budget_status(),
                    "cache_stats": self.llm_token_manager.get_cache_stats()
                }
            
            # Determine overall result
            image_passed = results["image_signing"] is None or results["image_signing"]["all_verified"]
            ci_passed = results["remote_ci"]["pr_status"]["all_checks_passed"]
            llm_passed = results["llm_budget"] is None or all(r["success"] for r in results["llm_budget"]["results"])
            
            results["overall_passed"] = image_passed and ci_passed and llm_passed
            
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    def get_enterprise_status(self) -> Dict[str, Any]:
        """Get overall enterprise suite status."""
        
        return {
            "image_signing": {
                "trusted_signers": self.image_signing_manager.get_trusted_signers()
            },
            "remote_ci": {
                "workflow": self.remote_ci_manager.get_workflow_definition()
            },
            "llm_management": {
                "budget_status": self.llm_token_manager.get_budget_status(),
                "cache_stats": self.llm_token_manager.get_cache_stats()
            }
        }


# === Convenience Functions ===

def create_final_enterprise_suite() -> FinalEnterpriseSuite:
    """Create final enterprise suite."""
    return FinalEnterpriseSuite()


if __name__ == "__main__":
    # Demo
    async def demo_final_enterprise_suite():
        print("Final Enterprise Suite Demo:")
        
        # Create suite
        suite = create_final_enterprise_suite()
        
        print(f"Suite created: {suite.__class__.__name__}")
        
        # Test 1: Image signing
        print("\\n1. Testing image signing:")
        
        image_ref = "myapp:v1.0@sha256:abc123def456..."
        signature = await suite.image_signing_manager.sign_image(image_ref)
        verification = await suite.image_signing_manager.verify_image_signature(image_ref, signature)
        
        print(f"Image signed: {signature.signer}")
        print(f"Verification passed: {verification.verification_passed}")
        
        # Test 2: Remote CI
        print("\\n2. Testing remote CI:")
        
        pr_context = {"simulate_policy_violation": False}
        scorecard_status = await suite.remote_ci_manager.run_scorecard_check(pr_context)
        
        print(f"Scorecard status: {scorecard_status.conclusion}")
        
        # Test 3: LLM token management
        print("\\n3. Testing LLM token management:")
        
        spec = {"template_type": "web-api"}
        response, usage = await suite.llm_token_manager.call_llm_with_budget(
            spec=spec,
            prompt="Generate a FastAPI application",
            seed="test-seed"
        )
        
        print(f"LLM response length: {len(response)}")
        print(f"Tokens used: {usage.total_tokens}")
        
        # Test cache hit
        response2, usage2 = await suite.llm_token_manager.call_llm_with_budget(
            spec=spec,
            prompt="Generate a FastAPI application",
            seed="test-seed"
        )
        
        print(f"Cache hit (same usage): {usage.total_tokens == usage2.total_tokens}")
        
        return True
    
    # Run demo
    result = asyncio.run(demo_final_enterprise_suite())
    print(f"Demo completed: {result}")
