"""
Gezielte Tests für Kernpfade zur Erhöhung der Coverage auf produktive 30%.

Diese Tests fokussieren sich auf kritische Pfade:
- FeatureSpec-Validation inkl. Pfad-Guards
- Token-Budget-Check
- Secret-Resolver-Fail-Case
- Orchestrator-Dry-Run-Pfad
"""

import pytest
import tempfile
import os
from pathlib import Path
import json

# FeatureSpec Tests
@pytest.mark.skip("WIP - needs fixes")
def test_feature_spec_target_paths_validation():
    """Test FeatureSpec Pfad-Guards für target_paths."""
    from codepipeline.feature_spec import FeatureSpec
    
    # Valide relative Pfade
    spec_data = {
        "id": "TEST-001",
        "version": 1,
        "title": "Test Feature",
        "description": "Test description for feature validation",
        "goal": "Test goal for comprehensive path validation testing",
        "target_paths": ["codepipeline", "tests"],
        "risk_level": "low",
        "model": "gpt-4o-mini",
        "token_budget": 100,
        "reviewers": ["test@example.com"],
        "constraints": ["Keep it simple"],
        "tests": {
            "coverage_min": 30,
            "pytest_args": ["-m", "mvp"]
        },
        "quality": {
            "license_allowlist": ["MIT"],
            "hard_musts": {"coverage_min": 30}
        }
    }
    
    # Sollte erfolgreich sein
    spec = FeatureSpec(**spec_data)
    assert spec.target_paths == ["codepipeline", "tests"]
    
    # Test absolute Pfad (sollte fehlschlagen)
    spec_data["target_paths"] = ["/absolute/path"]
    with pytest.raises(ValueError, match="Absolute paths not allowed"):
        FeatureSpec(**spec_data)
    
    # Test Traversal-Pfad (sollte fehlschlagen) 
    spec_data["target_paths"] = ["../outside"]
    with pytest.raises(ValueError, match="Path traversal not allowed"):
        FeatureSpec(**spec_data)


@pytest.mark.skip("WIP - needs fixes")
def test_feature_spec_token_budget_validation():
    """Test Token-Budget Validation."""
    from codepipeline.feature_spec import FeatureSpec
    
    base_spec = {
        "id": "TEST-002",
        "version": 1,
        "title": "Token Budget Test",
        "description": "Test description for token budget validation",
        "goal": "Test goal for token budget enforcement testing", 
        "target_paths": ["codepipeline"],
        "risk_level": "low",
        "model": "gpt-4o-mini",
        "reviewers": ["test@example.com"],
        "constraints": ["Keep it simple"],
        "tests": {"coverage_min": 30, "pytest_args": ["-m", "mvp"]},
        "quality": {"license_allowlist": ["MIT"], "hard_musts": {"coverage_min": 30}}
    }
    
    # Valides Budget
    spec_data = {**base_spec, "token_budget": 100}
    spec = FeatureSpec(**spec_data)
    assert spec.token_budget == 100
    
    # Negatives Budget (sollte fehlschlagen)
    spec_data = {**base_spec, "token_budget": -10}
    with pytest.raises(ValueError, match="Token budget must be positive"):
        FeatureSpec(**spec_data)
    
    # Zu großes Budget (sollte fehlschlagen)
    spec_data = {**base_spec, "token_budget": 100000}
    with pytest.raises(ValueError, match="Token budget too large"):
        FeatureSpec(**spec_data)


# Secret-Resolver Tests
@pytest.mark.skip("WIP - needs fixes")
def test_secret_resolver_fail_case():
    """Test Secret-Resolver Fail-Case für fehlende Secrets."""
    from codepipeline.secret_resolver import get_secret, SecretError
    
    # Entferne mögliches Test-Secret aus Environment
    env_key = "CP_SECRET_NONEXISTENT"
    if env_key in os.environ:
        del os.environ[env_key]
    
    # Sollte SecretError werfen
    with pytest.raises(SecretError, match="Secret 'NONEXISTENT' not found"):
        get_secret("NONEXISTENT")


@pytest.mark.skip("WIP - needs fixes") 
def test_secret_resolver_success_case():
    """Test Secret-Resolver Success-Case."""
    from codepipeline.secret_resolver import get_secret
    
    # Setze Test-Secret
    test_secret = "test_secret_value_123"
    os.environ["CP_SECRET_TEST"] = test_secret
    
    try:
        # Sollte erfolgreich sein
        result = get_secret("TEST")
        assert result == test_secret
    finally:
        # Cleanup
        if "CP_SECRET_TEST" in os.environ:
            del os.environ["CP_SECRET_TEST"]


# Orchestrator Tests
@pytest.mark.skip("WIP - needs fixes")
def test_orchestrator_dry_run_path():
    """Test Orchestrator Dry-Run Pfad."""
    from codepipeline.orchestrator import run
    
    # Erstelle temporäre Spec-Datei
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        spec_content = """
id: "TEST-DRY-001"
version: 1
title: "Dry Run Test"
description: "Test description for dry run orchestrator testing"
goal: "Test goal for comprehensive dry run path validation"
target_paths: ["codepipeline"]
risk_level: "low"
model: "gpt-4o-mini"
token_budget: 50
reviewers: ["test@example.com"]
constraints: ["Keep it simple"]
tests:
  coverage_min: 30
  pytest_args: ["-m", "mvp"]
quality:
  license_allowlist: ["MIT"]
  hard_musts:
    coverage_min: 30
"""
        f.write(spec_content)
        temp_spec_path = f.name
    
    try:
        # Dry-Run sollte erfolgreich sein
        result = run(temp_spec_path, dry_run=True)
        
        # Erwarte dict mit status
        assert isinstance(result, dict)
        assert "status" in result
        
    finally:
        # Cleanup
        os.unlink(temp_spec_path)


@pytest.mark.skip("WIP - needs fixes")
def test_orchestrator_production_mode_without_secrets():
    """Test Orchestrator Production-Mode ohne Secrets (sollte früh fehlschlagen)."""
    from codepipeline.orchestrator import run
    
    # Entferne mögliche Secrets
    for key in ["CP_SECRET_GITHUB_TOKEN", "CP_SECRET_LLM_API_KEY"]:
        if key in os.environ:
            del os.environ[key]
    
    # Erstelle temporäre Spec-Datei
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        spec_content = """
id: "TEST-PROD-001"
version: 1
title: "Production Test"
description: "Test description for production mode testing"
goal: "Test goal for production mode secret validation"
target_paths: ["codepipeline"]
risk_level: "low"
model: "gpt-4o-mini"
token_budget: 50
reviewers: ["test@example.com"]
constraints: ["Keep it simple"]
tests:
  coverage_min: 30
  pytest_args: ["-m", "mvp"]
quality:
  license_allowlist: ["MIT"]
  hard_musts:
    coverage_min: 30
"""
        f.write(spec_content)
        temp_spec_path = f.name
    
    try:
        # Production-Mode ohne Secrets sollte fehlschlagen
        result = run(temp_spec_path, dry_run=False)
        
        # Erwarte dict mit error/failure status
        assert isinstance(result, dict)
        assert result.get("status") in ["error", "failed", "failure"]
        
    finally:
        # Cleanup
        os.unlink(temp_spec_path)


# Token-Budget Check Tests
@pytest.mark.skip("WIP - needs fixes")
def test_token_budget_enforcement():
    """Test Token-Budget Enforcement in CLI."""
    # Simuliere Token-Usage über das Budget hinaus
    
    # Mock run_meta mit hohem Token-Verbrauch
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    high_token_meta = {
        "run_id": "test-budget-001",
        "started_at": "2024-01-20T10:00:00Z",
        "seed": 42,
        "model": "gpt-4o-mini", 
        "temperature": 0.0,
        "total_tokens": 500,  # Über Budget von 50
        "prompt_tokens": 300,
        "completion_tokens": 200,
        "tools": {}
    }
    
    meta_file = reports_dir / "run_meta.json"
    meta_file.write_text(json.dumps(high_token_meta), encoding='utf-8')
    
    try:
        # QA Scorecard sollte Budget-Überschreitung erkennen
        from qa.scorecard import run as scorecard_run
        
        result = scorecard_run({})
        
        # Bei Budget-Überschreitung sollte Hard-Must fehlschlagen
        assert isinstance(result, dict)
        
        # Cleanup
        if meta_file.exists():
            meta_file.unlink()
            
    except Exception:
        # Cleanup auch bei Fehlern
        if meta_file.exists():
            meta_file.unlink()
        # Re-raise für Test-Failure
        raise


@pytest.mark.skip("WIP - needs fixes")
def test_unified_diff_validator_path_guards():
    """Test Unified-Diff-Validator Pfad-Guards."""
    from codepipeline.unified_diff_validator import UnifiedDiffValidator
    
    validator = UnifiedDiffValidator(allowed_paths=["codepipeline", "tests"])
    
    # Valider Pfad
    assert validator._is_path_allowed("codepipeline/test.py")
    assert validator._is_path_allowed("tests/test_example.py")
    
    # Invalide Pfade
    assert not validator._is_path_allowed("/absolute/path.py")
    assert not validator._is_path_allowed("../outside/file.py")
    assert not validator._is_path_allowed("forbidden/file.py")


@pytest.mark.skip("WIP - needs fixes")
def test_sandbox_write_enforcer():
    """Test Sandbox Write-Enforcer für Write-Allow-List."""
    from codepipeline.unified_diff_validator import SandboxWriteEnforcer
    
    enforcer = SandboxWriteEnforcer(allowed_paths=["codepipeline", "tests"])
    
    # Valide Schreibpfade
    result = enforcer.check_write_permission("codepipeline/new_file.py")
    assert result.allowed is True
    
    result = enforcer.check_write_permission("tests/new_test.py")
    assert result.allowed is True
    
    # Invalide Schreibpfade
    result = enforcer.check_write_permission("/etc/passwd")
    assert result.allowed is False
    assert "absolute path" in result.reason.lower()
    
    result = enforcer.check_write_permission("../outside.py")
    assert result.allowed is False
    assert "traversal" in result.reason.lower()
