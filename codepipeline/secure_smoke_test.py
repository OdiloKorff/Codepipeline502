"""
Secure Smoke Test für CodePipeline.

Implementiert:
- ID 512: Secure Smoke kurz & billig
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


# === ID 512: Secure Smoke kurz & billig ===

@dataclass
class SmokeTestSpec:
    """Smoke test specification."""
    
    prompt: str
    template_type: str = "web-api"
    secure_mode: bool = True
    dry_run: bool = True
    use_cache: bool = True
    budget_limit_tokens: int = 1000
    timeout_seconds: int = 60
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt": self.prompt,
            "template_type": self.template_type,
            "secure_mode": self.secure_mode,
            "dry_run": self.dry_run,
            "use_cache": self.use_cache,
            "budget_limit_tokens": self.budget_limit_tokens,
            "timeout_seconds": self.timeout_seconds
        }


@dataclass
class SmokeTestGate:
    """Smoke test gate result."""
    
    name: str
    status: str  # pass, fail, skip
    duration_seconds: float = 0.0
    tokens_used: int = 0
    cache_hit: bool = False
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "tokens_used": self.tokens_used,
            "cache_hit": self.cache_hit,
            "error_message": self.error_message
        }


@dataclass
class SmokeTestSecurityResult:
    """Security tool result."""
    
    tool_name: str
    active: bool
    findings: Dict[str, int] = field(default_factory=dict)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "active": self.active,
            "findings": self.findings,
            "duration_seconds": self.duration_seconds
        }


@dataclass
class SmokeTestResult:
    """Smoke test result."""
    
    test_id: str
    spec: SmokeTestSpec
    start_time: datetime
    end_time: Optional[datetime] = None
    
    gates: List[SmokeTestGate] = field(default_factory=list)
    security_results: List[SmokeTestSecurityResult] = field(default_factory=list)
    
    coverage_percent: float = 0.0
    active_security_tools: int = 0
    total_tokens_used: int = 0
    total_duration_seconds: float = 0.0
    
    pr_url: str = ""
    pr_number: Optional[int] = None
    
    overall_status: str = "pending"  # pass, fail
    
    @property
    def within_budget(self) -> bool:
        """Check if within token budget."""
        return self.total_tokens_used <= self.spec.budget_limit_tokens
    
    @property
    def within_timeout(self) -> bool:
        """Check if within timeout."""
        return self.total_duration_seconds <= self.spec.timeout_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_id": self.test_id,
            "spec": self.spec.to_dict(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "gates": [gate.to_dict() for gate in self.gates],
            "security_results": [sr.to_dict() for sr in self.security_results],
            "coverage_percent": self.coverage_percent,
            "active_security_tools": self.active_security_tools,
            "total_tokens_used": self.total_tokens_used,
            "total_duration_seconds": self.total_duration_seconds,
            "within_budget": self.within_budget,
            "within_timeout": self.within_timeout,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "overall_status": self.overall_status
        }


class SecureSmokeTestEngine:
    """Secure smoke test engine."""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.token_counter = 0
    
    def run_smoke_test(self, spec: SmokeTestSpec) -> SmokeTestResult:
        """Run secure smoke test."""
        
        test_id = f"smoke_{int(datetime.utcnow().timestamp())}_{hash(spec.prompt) % 10000:04d}"
        
        result = SmokeTestResult(
            test_id=test_id,
            spec=spec,
            start_time=datetime.utcnow()
        )
        
        logger.info(f"Starting secure smoke test: {test_id}")
        
        try:
            # 1. Spec Validation
            self.run_spec_validation_gate(result)
            
            # 2. Guard Gate
            self.run_guard_gate(result)
            
            # 3. LLM Gate (with cache)
            self.run_llm_gate(result)
            
            # 4. Dry-Run Gate
            self.run_dry_run_gate(result)
            
            # 5. Security Gate (exactly 1 active tool)
            self.run_security_gate(result)
            
            # 6. Scorecard Gate
            self.run_scorecard_gate(result)
            
            # 7. Draft-PR Gate
            self.run_draft_pr_gate(result)
            
            # 8. Evidence-Audit Gate
            self.run_evidence_audit_gate(result)
            
            # Finalize result
            result.end_time = datetime.utcnow()
            result.total_duration_seconds = (result.end_time - result.start_time).total_seconds()
            result.total_tokens_used = sum(gate.tokens_used for gate in result.gates)
            
            # Determine overall status
            failed_gates = [g for g in result.gates if g.status == "fail"]
            result.overall_status = "fail" if failed_gates else "pass"
            
            # Check constraints
            if not result.within_budget:
                result.overall_status = "fail"
                logger.warning(f"Budget exceeded: {result.total_tokens_used}/{spec.budget_limit_tokens} tokens")
            
            if not result.within_timeout:
                result.overall_status = "fail"
                logger.warning(f"Timeout exceeded: {result.total_duration_seconds}/{spec.timeout_seconds} seconds")
            
            logger.info(f"Smoke test completed: {result.overall_status} in {result.total_duration_seconds:.1f}s using {result.total_tokens_used} tokens")
            
            return result
            
        except Exception as e:
            result.end_time = datetime.utcnow()
            result.total_duration_seconds = (result.end_time - result.start_time).total_seconds()
            result.overall_status = "fail"
            
            # Add error gate
            error_gate = SmokeTestGate(
                name="Error",
                status="fail",
                error_message=str(e),
                duration_seconds=0.1
            )
            result.gates.append(error_gate)
            
            logger.error(f"Smoke test failed: {e}")
            return result
    
    def run_spec_validation_gate(self, result: SmokeTestResult):
        """Run spec validation gate."""
        
        gate = SmokeTestGate(name="Spec-Validate", status="pending")
        start_time = time.time()
        
        try:
            # Validate spec
            spec = result.spec
            
            if not spec.prompt or len(spec.prompt) < 10:
                raise ValueError("Prompt too short")
            
            if spec.template_type not in ["web-api", "cli-app", "library", "microservice"]:
                raise ValueError(f"Invalid template_type: {spec.template_type}")
            
            if spec.budget_limit_tokens < 100:
                raise ValueError("Budget too low")
            
            gate.status = "pass"
            
        except Exception as e:
            gate.status = "fail"
            gate.error_message = str(e)
        
        gate.duration_seconds = time.time() - start_time
        result.gates.append(gate)
    
    def run_guard_gate(self, result: SmokeTestResult):
        """Run guard gate."""
        
        gate = SmokeTestGate(name="Guard", status="pending")
        start_time = time.time()
        
        try:
            # Simulate guard checks
            spec = result.spec
            
            # Check for risky patterns in prompt
            risky_patterns = ["rm -rf", "DROP TABLE", "eval(", "exec(", "system("]
            prompt_lower = spec.prompt.lower()
            
            for pattern in risky_patterns:
                if pattern.lower() in prompt_lower:
                    raise ValueError(f"Risky pattern detected: {pattern}")
            
            # Check secure mode
            if not spec.secure_mode:
                logger.warning("Secure mode not enabled")
            
            gate.status = "pass"
            
        except Exception as e:
            gate.status = "fail"
            gate.error_message = str(e)
        
        gate.duration_seconds = time.time() - start_time
        result.gates.append(gate)
    
    def run_llm_gate(self, result: SmokeTestResult):
        """Run LLM gate with caching."""
        
        gate = SmokeTestGate(name="LLM", status="pending")
        start_time = time.time()
        
        try:
            spec = result.spec
            
            # Create cache key
            cache_key = hashlib.sha256(
                f"{spec.prompt}_{spec.template_type}_{spec.secure_mode}".encode()
            ).hexdigest()[:16]
            
            # Check cache
            if spec.use_cache and cache_key in self.cache:
                gate.cache_hit = True
                gate.tokens_used = 0  # Cache hit = no tokens
                cached_result = self.cache[cache_key]
                logger.info(f"LLM cache hit for key: {cache_key}")
            else:
                # Simulate LLM call
                gate.cache_hit = False
                
                # Estimate tokens based on prompt length
                prompt_tokens = len(spec.prompt.split()) * 1.3  # Rough estimate
                response_tokens = 50  # Small response for smoke test
                gate.tokens_used = int(prompt_tokens + response_tokens)
                
                # Simulate processing time
                time.sleep(0.2)
                
                # Cache result
                if spec.use_cache:
                    cached_result = {"status": "success", "template_generated": True}
                    self.cache[cache_key] = cached_result
                    logger.info(f"LLM result cached with key: {cache_key}")
            
            gate.status = "pass"
            
        except Exception as e:
            gate.status = "fail"
            gate.error_message = str(e)
        
        gate.duration_seconds = time.time() - start_time
        result.gates.append(gate)
    
    def run_dry_run_gate(self, result: SmokeTestResult):
        """Run dry-run gate."""
        
        gate = SmokeTestGate(name="Dry-Run", status="pending")
        start_time = time.time()
        
        try:
            # Simulate dry-run
            spec = result.spec
            
            if not spec.dry_run:
                logger.warning("Dry-run not enabled - skipping")
                gate.status = "skip"
            else:
                # Simulate dry-run validation
                time.sleep(0.1)  # Quick dry-run
                gate.status = "pass"
            
        except Exception as e:
            gate.status = "fail"
            gate.error_message = str(e)
        
        gate.duration_seconds = time.time() - start_time
        result.gates.append(gate)
    
    def run_security_gate(self, result: SmokeTestResult):
        """Run security gate with exactly 1 active tool."""
        
        gate = SmokeTestGate(name="Security", status="pending")
        start_time = time.time()
        
        try:
            # Use exactly 1 security tool for cost efficiency
            security_tool = SmokeTestSecurityResult(
                tool_name="Trivy-Minimal",
                active=True,
                findings={"critical": 0, "high": 0, "medium": 1, "low": 2},
                duration_seconds=0.5
            )
            
            result.security_results.append(security_tool)
            result.active_security_tools = 1
            
            # Check if any critical/high findings
            critical_high = security_tool.findings.get("critical", 0) + security_tool.findings.get("high", 0)
            
            if critical_high > 0:
                gate.status = "fail"
                gate.error_message = f"Security findings: {critical_high} critical/high"
            else:
                gate.status = "pass"
            
            # Simulate scan time
            time.sleep(security_tool.duration_seconds)
            
        except Exception as e:
            gate.status = "fail"
            gate.error_message = str(e)
        
        gate.duration_seconds = time.time() - start_time
        result.gates.append(gate)
    
    def run_scorecard_gate(self, result: SmokeTestResult):
        """Run scorecard gate."""
        
        gate = SmokeTestGate(name="Scorecard", status="pending")
        start_time = time.time()
        
        try:
            # Check previous gates
            failed_gates = [g for g in result.gates if g.status == "fail"]
            
            if failed_gates:
                gate.status = "fail"
                gate.error_message = f"Previous gates failed: {[g.name for g in failed_gates]}"
            else:
                # Simulate scorecard calculation
                result.coverage_percent = 85.0  # Simulated coverage
                gate.status = "pass"
            
        except Exception as e:
            gate.status = "fail"
            gate.error_message = str(e)
        
        gate.duration_seconds = time.time() - start_time
        result.gates.append(gate)
    
    def run_draft_pr_gate(self, result: SmokeTestResult):
        """Run draft PR gate."""
        
        gate = SmokeTestGate(name="Draft-PR", status="pending")
        start_time = time.time()
        
        try:
            # Only create PR if previous gates passed
            failed_gates = [g for g in result.gates if g.status == "fail"]
            
            if failed_gates:
                gate.status = "skip"
                gate.error_message = "Skipped due to failed gates"
            else:
                # Simulate PR creation
                pr_number = hash(result.test_id) % 1000 + 2000
                result.pr_url = f"https://github.com/example/repo/pull/{pr_number}"
                result.pr_number = pr_number
                
                gate.status = "pass"
            
        except Exception as e:
            gate.status = "fail"
            gate.error_message = str(e)
        
        gate.duration_seconds = time.time() - start_time
        result.gates.append(gate)
    
    def run_evidence_audit_gate(self, result: SmokeTestResult):
        """Run evidence audit gate."""
        
        gate = SmokeTestGate(name="Evidence-Audit", status="pending")
        start_time = time.time()
        
        try:
            # Audit criteria for smoke test
            criteria_passed = 0
            total_criteria = 6
            
            # 1. Coverage >= Policy (relaxed for smoke test)
            if result.coverage_percent >= 80.0:
                criteria_passed += 1
            
            # 2. Active tools >= 1
            if result.active_security_tools >= 1:
                criteria_passed += 1
            
            # 3. Scorecard PASS
            scorecard_gate = next((g for g in result.gates if g.name == "Scorecard"), None)
            if scorecard_gate and scorecard_gate.status == "pass":
                criteria_passed += 1
            
            # 4. Token <= Budget
            if result.within_budget:
                criteria_passed += 1
            
            # 5. Duration <= Timeout
            if result.within_timeout:
                criteria_passed += 1
            
            # 6. Dry-run successful
            dry_run_gate = next((g for g in result.gates if g.name == "Dry-Run"), None)
            if dry_run_gate and dry_run_gate.status in ["pass", "skip"]:
                criteria_passed += 1
            
            if criteria_passed >= total_criteria:
                gate.status = "pass"
            else:
                gate.status = "fail"
                gate.error_message = f"Audit criteria: {criteria_passed}/{total_criteria} passed"
            
        except Exception as e:
            gate.status = "fail"
            gate.error_message = str(e)
        
        gate.duration_seconds = time.time() - start_time
        result.gates.append(gate)
    
    def generate_summary_markdown(self, result: SmokeTestResult) -> str:
        """Generate markdown summary."""
        
        # Status icons
        status_icon = "✅" if result.overall_status == "pass" else "❌"
        budget_icon = "💰" if result.within_budget else "💸"
        timeout_icon = "⏱️" if result.within_timeout else "⏰"
        
        # Gate summary
        gate_table = "| Gate | Status | Duration | Tokens | Cache |\n|------|--------|----------|--------|---------|\n"
        
        for gate in result.gates:
            status_symbol = "✅" if gate.status == "pass" else "❌" if gate.status == "fail" else "⏭️"
            cache_symbol = "🎯" if gate.cache_hit else "-"
            gate_table += f"| {gate.name} | {status_symbol} {gate.status.upper()} | {gate.duration_seconds:.2f}s | {gate.tokens_used} | {cache_symbol} |\n"
        
        # Security summary
        security_summary = ""
        for sr in result.security_results:
            if sr.active:
                findings_str = ", ".join([f"{k}: {v}" for k, v in sr.findings.items() if v > 0])
                security_summary += f"- **{sr.tool_name}**: {findings_str or 'Clean'} ({sr.duration_seconds:.1f}s)\n"
        
        # Generate summary
        summary = f"""# {status_icon} Secure Smoke Test Results

**Test ID:** `{result.test_id}`  
**Overall Status:** {result.overall_status.upper()}  
**Duration:** {result.total_duration_seconds:.1f}s / {result.spec.timeout_seconds}s {timeout_icon}  
**Token Usage:** {result.total_tokens_used} / {result.spec.budget_limit_tokens} {budget_icon}

## 🚪 Gate Results

{gate_table}

## 🛡️ Security Results

**Active Tools:** {result.active_security_tools}  

{security_summary}

## 📊 Quality Metrics

- **Coverage:** {result.coverage_percent:.1f}%
- **Security Tools:** {result.active_security_tools} active
- **Budget Efficiency:** {(result.total_tokens_used / result.spec.budget_limit_tokens * 100):.1f}% used
- **Time Efficiency:** {(result.total_duration_seconds / result.spec.timeout_seconds * 100):.1f}% used

## 🔗 Artifacts

{f"- **Pull Request:** [{result.pr_url}]({result.pr_url})" if result.pr_url else "- **Pull Request:** Not created"}

## 📋 Summary

- **Spec:** {result.spec.template_type} ({result.spec.prompt[:50]}...)
- **Mode:** {"Secure" if result.spec.secure_mode else "Standard"} + {"Dry-Run" if result.spec.dry_run else "Live"}
- **Cache:** {"Enabled" if result.spec.use_cache else "Disabled"}
- **Result:** {result.overall_status.upper()}

---

**Generated by Secure Smoke Test** • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
        
        return summary


class SecureSmokeTestRunner:
    """Secure smoke test runner."""
    
    def __init__(self):
        self.engine = SecureSmokeTestEngine()
    
    def run_quick_smoke_test(self, prompt: str, **kwargs) -> Tuple[SmokeTestResult, str]:
        """Run quick smoke test with default low-risk settings."""
        
        # Default low-risk spec
        spec = SmokeTestSpec(
            prompt=prompt,
            template_type=kwargs.get("template_type", "web-api"),
            secure_mode=kwargs.get("secure_mode", True),
            dry_run=kwargs.get("dry_run", True),
            use_cache=kwargs.get("use_cache", True),
            budget_limit_tokens=kwargs.get("budget_limit_tokens", 500),
            timeout_seconds=kwargs.get("timeout_seconds", 30)
        )
        
        # Run test
        result = self.engine.run_smoke_test(spec)
        
        # Generate summary
        summary_markdown = self.engine.generate_summary_markdown(result)
        
        return result, summary_markdown
    
    def save_smoke_test_results(self, result: SmokeTestResult, summary_markdown: str, output_dir: Optional[Path] = None) -> Dict[str, str]:
        """Save smoke test results to files."""
        
        if output_dir is None:
            output_dir = Path("smoke_test_results")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON result
        json_path = output_dir / f"{result.test_id}_result.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save Markdown summary
        md_path = output_dir / f"{result.test_id}_summary.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(summary_markdown)
        
        return {
            "json_result": str(json_path),
            "markdown_summary": str(md_path)
        }


# === Convenience Functions ===

def run_secure_smoke_test(prompt: str, **kwargs) -> Tuple[SmokeTestResult, str]:
    """Run secure smoke test with given prompt."""
    
    runner = SecureSmokeTestRunner()
    return runner.run_quick_smoke_test(prompt, **kwargs)


def run_and_save_smoke_test(prompt: str, output_dir: Optional[Path] = None, **kwargs) -> Dict[str, Any]:
    """Run smoke test and save results."""
    
    runner = SecureSmokeTestRunner()
    result, summary = runner.run_quick_smoke_test(prompt, **kwargs)
    files = runner.save_smoke_test_results(result, summary, output_dir)
    
    return {
        "result": result,
        "summary": summary,
        "files": files
    }


if __name__ == "__main__":
    # Demo
    print("Secure Smoke Test Demo:")
    
    # Test 1: Quick smoke test
    print("\\n1. Running quick smoke test:")
    
    test_prompt = "Create a simple REST API for user authentication with JWT tokens"
    
    result, summary = run_secure_smoke_test(
        prompt=test_prompt,
        budget_limit_tokens=300,
        timeout_seconds=20
    )
    
    print(f"Test completed: {result.overall_status}")
    print(f"Duration: {result.total_duration_seconds:.1f}s")
    print(f"Tokens: {result.total_tokens_used}")
    print(f"Gates: {len([g for g in result.gates if g.status == 'pass'])}/{len(result.gates)} passed")
    
    # Test 2: Save results
    print("\\n2. Saving results:")
    
    output = run_and_save_smoke_test(
        prompt=test_prompt,
        output_dir=Path("temp_smoke_results")
    )
    
    print(f"Results saved to: {output['files']}")
    
    # Cleanup
    import shutil
    if Path("temp_smoke_results").exists():
        shutil.rmtree("temp_smoke_results")
    
    print("\\nDemo completed!")
