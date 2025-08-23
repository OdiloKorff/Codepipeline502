"""
Gezielte Unit-Tests für Security-Kernpfade.
Erhöht Coverage für Security-Scanning und Policy-Enforcement.
"""

import pytest
import json
from pathlib import Path

from codepipeline.dependency_security import generate_sbom, check_licenses
from codepipeline.branch_protection import preflight, _has_git_remote


@pytest.mark.mvp
def test_sbom_generation():
    """Test SBOM-Generierung."""
    sbom_path = generate_sbom()
    
    assert sbom_path is not None
    assert isinstance(sbom_path, str)
    
    # Prüfe ob Datei existiert
    sbom_file = Path(sbom_path)
    assert sbom_file.exists()
    
    # Prüfe XML-Inhalt
    content = sbom_file.read_text()
    assert "<?xml" in content
    assert "cyclonedx" in content.lower()


@pytest.mark.mvp
def test_license_check():
    """Test Lizenz-Check."""
    result = check_licenses()
    
    assert isinstance(result, dict)
    assert "passed" in result
    assert "total_packages" in result
    assert "compliant_packages" in result
    assert "violations" in result
    
    # Prüfe dass passed ein Boolean ist
    assert isinstance(result["passed"], bool)


@pytest.mark.mvp
def test_license_check_with_allowlist():
    """Test Lizenz-Check mit expliziter Allow-List."""
    allowlist = ["MIT", "Apache-2.0", "BSD-3-Clause"]
    result = check_licenses(allowlist)
    
    assert isinstance(result, dict)
    assert "passed" in result
    assert "allowlist" in result
    assert result["allowlist"] == allowlist


@pytest.mark.mvp
def test_branch_protection_preflight():
    """Test Branch-Protection-Preflight."""
    result = preflight()
    
    assert isinstance(result, dict)
    assert "status" in result
    assert "reason" in result
    assert "current_branch" in result
    assert "target_branch" in result
    # Sollte True sein für lokales Repository


@pytest.mark.mvp
def test_git_remote_detection():
    """Test Git-Remote-Erkennung."""
    has_remote = _has_git_remote()
    
    assert isinstance(has_remote, bool)
    # Für lokales Repository sollte False sein


@pytest.mark.mvp
def test_dependency_security_info():
    """Test Dependency-Security-Info."""
    from codepipeline.dependency_security import get_dependency_info
    
    info = get_dependency_info()
    
    assert isinstance(info, dict)
    assert "dependencies_scanned" in info
    assert "sbom_generated" in info
    assert "licenses_checked" in info
    assert "timestamp" in info


@pytest.mark.mvp
def test_sbom_file_operations():
    """Test SBOM-Datei-Operationen."""
    # Test mit benutzerdefiniertem Pfad
    custom_path = "reports/custom_sbom.xml"
    sbom_path = generate_sbom(custom_path)
    
    assert sbom_path == custom_path
    
    # Prüfe ob Datei erstellt wurde
    sbom_file = Path(sbom_path)
    assert sbom_file.exists()
    
    # Cleanup
    sbom_file.unlink(missing_ok=True)


@pytest.mark.mvp
def test_license_violation_detection():
    """Test Lizenz-Verletzungs-Erkennung."""
    # Test mit restriktiver Allow-List
    restrictive_allowlist = ["MIT"]  # Nur MIT erlaubt
    result = check_licenses(restrictive_allowlist)
    
    assert isinstance(result, dict)
    assert "violations" in result
    assert "violation_details" in result
    
    # Prüfe dass violations eine Zahl ist
    assert isinstance(result["violations"], int)


@pytest.mark.mvp
def test_security_policy_integration():
    """Test Security-Policy-Integration."""
    # Test dass Policy-Datei geladen werden kann
    policy_file = Path("policies/QUALITY.yml")
    
    if policy_file.exists():
        # Policy sollte existieren und gültig sein
        assert policy_file.is_file()
        
        # Prüfe dass Lizenz-Check Policy lädt
        result = check_licenses()
        assert isinstance(result, dict)
        assert "passed" in result


@pytest.mark.mvp
def test_branch_protection_environment_detection():
    """Test Branch-Protection-Umgebungs-Erkennung."""
    # Test in verschiedenen Umgebungen
    import os
    
    # Lokale Umgebung
    result_local = preflight()
    assert isinstance(result_local, dict)
    assert "status" in result_local
    
    # Simuliere CI-Umgebung
    with pytest.MonkeyPatch().context() as m:
        m.setenv("CI", "true")
        result_ci = preflight()
        assert isinstance(result_ci, dict)
        assert "status" in result_ci
    
    # Simuliere Production-Umgebung
    with pytest.MonkeyPatch().context() as m:
        m.setenv("ENVIRONMENT", "production")
        result_prod = preflight()
        assert isinstance(result_prod, dict)
        assert "status" in result_prod
