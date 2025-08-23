"""
Finales Enterprise-System Demo.

Vollständige Integration aller produktionsreifen Komponenten:
1. Real Security Scanner (Semgrep/Bandit/Secrets/SCA)
2. Real SBOM & License Gate (CycloneDX, CVE-Scanning, License-Policy)
3. Branch Protection & PR Flow (Required Checks, Draft-PR, Artefakte)
4. Production Prompt Guard, Token Budget Gate, QA Scorecard

Enterprise-ready System für sichere, compliant Code-Generierung mit 
vollständiger CI/CD-Integration und Governance.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Füge aktuelles Verzeichnis zum Python Path hinzu
sys.path.insert(0, str(Path(__file__).parent))

from branch_protection_pr_flow import BranchProtectionPRFlow, QualityGateStatus
from production_prompt_guard import ProductionPromptGuard
from production_qa_scorecard import ProductionQAScorecard
from production_token_budget_gate import ProductionTokenBudgetGate, TokenBudgetPolicy
from real_sbom_license_gate import LicensePolicy, RealSBOMLicenseGate
from real_security_scanner import RealSecurityScanner, SecurityPolicy


def demo_final_enterprise_system():
    """Demonstriere das finale enterprise-ready System."""
    print("🏢 FINALES ENTERPRISE-SYSTEM DEMO")
    print("=" * 80)
    
    # System-Initialisierung
    spec_id = "ENTERPRISE-FINAL-001"
    
    print(f"\n🔧 Enterprise-System-Initialisierung (Spec: {spec_id})")
    
    # 1. Real Security Scanner
    security_policy = SecurityPolicy(
        max_critical=0,
        max_high=0,
        max_medium=3,
        max_low=15
    )
    
    security_scanner = RealSecurityScanner(
        policy=security_policy,
        target_path=".",
        spec_id=spec_id
    )
    
    # 2. Real SBOM & License Gate
    license_policy = LicensePolicy(
        allowed_licenses=["MIT", "BSD-3-Clause", "Apache-2.0", "Python-2.0", "ISC"],
        denied_licenses=["GPL-3.0", "AGPL-3.0"],
        require_license=True
    )
    
    sbom_gate = RealSBOMLicenseGate(
        license_policy=license_policy,
        spec_id=spec_id,
        target_path="."
    )
    
    # 3. Branch Protection & PR Flow
    pr_flow = BranchProtectionPRFlow(
        repo_owner="enterprise-org",
        repo_name="codepipeline",
        spec_id=spec_id,
        github_token=None  # Simuliert für Demo
    )
    
    # 4. Production Guards & Gates (aus vorherigen Demos)
    prompt_guard = ProductionPromptGuard(spec_id=spec_id, strict_mode=True)
    
    token_policy = TokenBudgetPolicy(
        total_budget=20000,
        cost_limit_usd=12.0,
        warning_threshold=0.8
    )
    
    token_gate = ProductionTokenBudgetGate(token_policy, spec_id=spec_id, strict_mode=True)
    
    qa_scorecard = ProductionQAScorecard(spec_id=spec_id)
    
    print("✅ Enterprise-Komponenten initialisiert:")
    print(f"   - Real Security Scanner: {len(security_scanner.policy.__dict__)} Policy-Regeln")
    print(f"   - SBOM License Gate: {len(license_policy.allowed_licenses)} erlaubte Lizenzen")
    print("   - Branch Protection PR Flow: GitHub-Integration")
    print("   - Production Guards: Prompt Guard, Token Budget, QA Scorecard")
    
    # Test 1: Vollständiger Enterprise-Workflow
    print("\n🚀 Test 1: Vollständiger Enterprise-Workflow")
    
    try:
        # 1.1 Security-Scan
        print("🔒 Schritt 1: Real Security-Scan")
        security_results = security_scanner.run_comprehensive_scan()
        security_exit_code = security_scanner.get_exit_code()
        
        print(f"   - Tools ausgeführt: {len(security_results)}")
        print(f"   - Total Findings: {len(security_scanner.all_findings)}")
        print(f"   - Exit Code: {security_exit_code}")
        
        # Speichere Security-Report
        security_report_file = f"enterprise_security_report_{spec_id}.json"
        security_scanner.save_security_report(security_report_file)
        
        # 1.2 SBOM & License-Analyse
        print("📦 Schritt 2: SBOM & License-Analyse")
        sbom_result = sbom_gate.run_comprehensive_analysis()
        
        print(f"   - Dependencies: {sbom_result['summary']['dependencies_count']}")
        print(f"   - Vulnerabilities: {sbom_result['summary']['vulnerabilities_count']}")
        print(f"   - License Violations: {sbom_result['summary']['license_violations_count']}")
        print(f"   - Gate Status: {'✅ PASSED' if sbom_result['gate_passed'] else '❌ FAILED'}")
        
        # Speichere SBOM-Artefakte
        sbom_artifacts = sbom_gate.save_artifacts(f"enterprise_sbom_artifacts_{spec_id}")
        
        # 1.3 Token Budget (simuliere LLM-Calls)
        print("💰 Schritt 3: Token Budget-Tracking")
        
        # Simuliere mehrere LLM-Calls für Feature-Entwicklung
        llm_operations = [
            (1200, 800, "requirements_analysis"),
            (1500, 1000, "code_generation"),
            (800, 600, "test_generation"),
            (600, 400, "documentation"),
            (400, 300, "code_review")
        ]
        
        for prompt_tokens, completion_tokens, operation in llm_operations:
            token_gate.record_token_usage(
                model="gpt-4o-mini",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                operation=operation
            )
        
        token_status = token_gate.get_budget_status()
        token_passed = token_gate.check_gate()
        
        print(f"   - Token-Verbrauch: {token_status.total_tokens_used}/{token_policy.total_budget}")
        print(f"   - Kosten: ${token_status.total_cost_usd:.4f}")
        print(f"   - Gate Status: {'✅ PASSED' if token_passed else '❌ FAILED'}")
        
        # 1.4 QA-Scorecard (simuliere umfassende QA)
        print("📊 Schritt 4: QA-Scorecard")
        
        qa_spec_data = {
            "token_budget": token_policy.total_budget,
            "coverage_min": 85,
            "security_level": "enterprise"
        }
        
        qa_result = qa_scorecard.run_comprehensive_qa(qa_spec_data)
        
        print(f"   - Overall Score: {qa_result.overall_score:.1f}/100")
        print(f"   - Gates: {qa_result.gates_passed}/{qa_result.gates_total}")
        print(f"   - Hard-Must Violations: {len(qa_result.hard_must_violations)}")
        print(f"   - Exit Code: {qa_result.exit_code}")
        
        # Speichere QA-Reports
        qa_reports = qa_scorecard.save_reports(qa_result, f"enterprise_qa_reports_{spec_id}")
        
        # 1.5 Quality Gates für PR-Flow
        print("🎯 Schritt 5: Quality Gates für PR-Flow")
        
        # Konvertiere Ergebnisse zu PR-Flow Quality Gates
        quality_gates = [
            QualityGateStatus(
                name="Security Scan",
                passed=security_exit_code == 0,
                score=max(0, 100 - len(security_scanner.all_findings) * 5),
                details=f"{len(security_scanner.all_findings)} findings, exit code {security_exit_code}",
                artifacts=[security_report_file]
            ),
            QualityGateStatus(
                name="SBOM License Check",
                passed=sbom_result['gate_passed'],
                score=100 if sbom_result['gate_passed'] else 50,
                details=f"{sbom_result['summary']['license_violations_count']} license violations",
                artifacts=list(sbom_artifacts.values())
            ),
            QualityGateStatus(
                name="Token Budget",
                passed=token_passed,
                score=int(100 - token_status.budget_utilization * 100),
                details=f"{token_status.budget_utilization:.1%} budget utilization",
                artifacts=[]
            ),
            QualityGateStatus(
                name="QA Scorecard",
                passed=qa_result.exit_code == 0,
                score=int(qa_result.overall_score),
                details=f"{qa_result.gates_passed}/{qa_result.gates_total} gates passed",
                artifacts=list(qa_reports.values())
            )
        ]
        
        # Füge Quality Gates zum PR-Flow hinzu
        for gate in quality_gates:
            pr_flow.add_quality_gate_result(gate)
        
        # Füge alle Artefakte hinzu
        all_artifacts = {
            "security_report": security_report_file,
            **sbom_artifacts,
            **qa_reports
        }
        
        for artifact_type, artifact_path in all_artifacts.items():
            pr_flow.add_artifact(artifact_type, artifact_path)
        
        print(f"   - Quality Gates: {len(quality_gates)}")
        print(f"   - Artifacts: {len(all_artifacts)}")
        
        # 1.6 Branch Protection & PR-Erstellung
        print("🔀 Schritt 6: Branch Protection & PR-Erstellung")
        
        # Verifiziere Branch Protection
        protection_verified = pr_flow.verify_branch_protection()
        all_gates_green = pr_flow.validate_all_gates_green()
        
        print(f"   - Branch Protection: {'✅ VERIFIED' if protection_verified else '❌ FAILED'}")
        print(f"   - All Gates Green: {'✅ YES' if all_gates_green else '❌ NO'}")
        
        # Erstelle Draft-PR nur wenn alle Gates grün
        if protection_verified and all_gates_green:
            pr_result = pr_flow.create_draft_pr(
                title="Enterprise Feature Implementation with Full Compliance",
                description="Complete enterprise-grade feature implementation with security scanning, SBOM generation, license compliance, and quality gates.",
                changes_summary="Implemented feature with comprehensive security scanning, dependency analysis, license compliance verification, and quality assurance."
            )
            
            print(f"   - PR Creation: {'✅ SUCCESS' if pr_result.success else '❌ FAILED'}")
            if pr_result.success:
                print(f"   - PR Number: #{pr_result.pr_number}")
                print(f"   - Artifacts Linked: {len(pr_result.artifacts_uploaded)}")
                
                # Upload Artifacts zu PR
                pr_flow.upload_artifacts_to_pr(pr_result.pr_number)
            else:
                print(f"   - Error: {pr_result.error_message}")
        else:
            print("   - PR Creation: ❌ BLOCKED (Gates not green or protection not verified)")
    
    except Exception as e:
        print(f"❌ Enterprise-Workflow fehlgeschlagen: {e}")
    
    # Test 2: Enterprise-Compliance-Überprüfung
    print("\n🏛️ Test 2: Enterprise-Compliance-Überprüfung")
    
    compliance_checks = [
        ("Security Scanning", security_exit_code == 0, f"Exit code: {security_exit_code}"),
        ("SBOM Generation", sbom_result['gate_passed'], f"CycloneDX SBOM with {sbom_result['summary']['dependencies_count']} components"),
        ("License Compliance", sbom_result['summary']['license_violations_count'] == 0, f"{sbom_result['summary']['license_violations_count']} violations"),
        ("Vulnerability Scanning", sbom_result['summary']['vulnerabilities_count'] == 0, f"{sbom_result['summary']['vulnerabilities_count']} CVEs"),
        ("Token Budget Control", token_passed, f"{token_status.budget_utilization:.1%} utilization"),
        ("Quality Gates", qa_result.exit_code == 0, f"{qa_result.overall_score:.1f}/100 score"),
        ("Branch Protection", protection_verified, "Required checks enforced"),
        ("Artifact Generation", len(all_artifacts) > 0, f"{len(all_artifacts)} artifacts generated")
    ]
    
    print("📋 Enterprise-Compliance-Status:")
    compliance_passed = 0
    
    for check_name, passed, details in compliance_checks:
        status = "✅ COMPLIANT" if passed else "❌ NON-COMPLIANT"
        print(f"   - {check_name}: {status} ({details})")
        if passed:
            compliance_passed += 1
    
    compliance_percentage = (compliance_passed / len(compliance_checks)) * 100
    
    print(f"\n📊 Enterprise-Compliance-Score: {compliance_percentage:.1f}% ({compliance_passed}/{len(compliance_checks)})")
    
    # Test 3: Governance & Audit-Trail
    print("\n📜 Test 3: Governance & Audit-Trail")
    
    # Erstelle umfassenden Governance-Report
    governance_report = {
        "spec_id": spec_id,
        "timestamp": datetime.now().isoformat(),
        "enterprise_version": "production-v1.0",
        "compliance": {
            "score": compliance_percentage,
            "passed_checks": compliance_passed,
            "total_checks": len(compliance_checks),
            "details": [
                {"check": name, "passed": passed, "details": details}
                for name, passed, details in compliance_checks
            ]
        },
        "security": {
            "scanner_tools": len(security_results),
            "total_findings": len(security_scanner.all_findings),
            "policy_violations": security_exit_code > 0,
            "exit_code": security_exit_code
        },
        "sbom": {
            "format": "CycloneDX",
            "components": sbom_result['summary']['dependencies_count'],
            "vulnerabilities": sbom_result['summary']['vulnerabilities_count'],
            "license_violations": sbom_result['summary']['license_violations_count'],
            "artifacts": list(sbom_artifacts.keys())
        },
        "quality": {
            "overall_score": qa_result.overall_score,
            "gates_passed": qa_result.gates_passed,
            "gates_total": qa_result.gates_total,
            "hard_must_violations": len(qa_result.hard_must_violations),
            "exit_code": qa_result.exit_code
        },
        "token_budget": {
            "budget_limit": token_policy.total_budget,
            "tokens_used": token_status.total_tokens_used,
            "utilization": token_status.budget_utilization,
            "cost_usd": token_status.total_cost_usd,
            "passed": token_passed
        },
        "pr_flow": {
            "branch_protection_verified": protection_verified,
            "quality_gates_green": all_gates_green,
            "pr_created": pr_result.success if 'pr_result' in locals() else False,
            "artifacts_count": len(all_artifacts)
        },
        "audit_trail": {
            "generated_artifacts": list(all_artifacts.keys()),
            "compliance_evidence": [
                "security_scan_report.json",
                "sbom_cyclonedx.json", 
                "license_compliance_report.json",
                "qa_scorecard.json",
                "token_budget_report.json",
                "branch_protection_status.json"
            ]
        }
    }
    
    # Speichere Governance-Report
    governance_file = f"enterprise_governance_report_{spec_id}.json"
    with open(governance_file, 'w', encoding='utf-8') as f:
        json.dump(governance_report, f, indent=2, ensure_ascii=False)
    
    print("📊 Governance-Report generiert:")
    print(f"   - File: {governance_file}")
    print(f"   - Compliance Score: {compliance_percentage:.1f}%")
    print(f"   - Security Findings: {governance_report['security']['total_findings']}")
    print(f"   - SBOM Components: {governance_report['sbom']['components']}")
    print(f"   - QA Score: {governance_report['quality']['overall_score']:.1f}/100")
    print(f"   - Audit Artifacts: {len(governance_report['audit_trail']['generated_artifacts'])}")
    
    # Finale Enterprise-Zusammenfassung
    print("\n🏆 FINALE ENTERPRISE-ZUSAMMENFASSUNG")
    print("=" * 80)
    
    enterprise_features = [
        "✅ Real Security Scanning: Semgrep, Bandit, Safety, Secret-Detection",
        "✅ SBOM Generation: CycloneDX-Format mit CVE-Scanning",
        "✅ License Compliance: Allow/Deny-Lists mit Policy-Enforcement",
        "✅ Branch Protection: Required Checks, PR-Reviews, Force-Push-Schutz",
        "✅ Quality Gates: Umfassende Metriken-Aggregation mit Hard-Must-Regeln",
        "✅ Token Budget: Request/Response-Accounting mit Kosten-Kontrolle",
        "✅ Prompt Guard: Injection-Schutz mit Determinismus-Enforcement",
        "✅ Artifact Management: Vollständige Nachverfolgbarkeit aller Outputs",
        "✅ Governance & Audit: Compliance-Scoring mit Evidence-Generation",
        "✅ CI/CD Integration: Exit-Codes, Status-Checks, Automated-PR-Creation"
    ]
    
    for feature in enterprise_features:
        print(f"  {feature}")
    
    print("\n📊 Enterprise-System-Status:")
    print(f"   - Compliance Score: {compliance_percentage:.1f}%")
    print(f"   - Security Status: {'🟢 SECURE' if security_exit_code == 0 else '🔴 VIOLATIONS'}")
    print(f"   - License Status: {'🟢 COMPLIANT' if sbom_result['summary']['license_violations_count'] == 0 else '🔴 VIOLATIONS'}")
    print(f"   - Quality Status: {'🟢 PASSED' if qa_result.exit_code == 0 else '🔴 FAILED'}")
    print(f"   - Budget Status: {'🟢 WITHIN BUDGET' if token_passed else '🔴 OVER BUDGET'}")
    
    # Bestimme finalen Enterprise-Status
    enterprise_ready = (
        compliance_percentage >= 80.0 and
        security_exit_code == 0 and
        sbom_result['gate_passed'] and
        qa_result.exit_code == 0 and
        token_passed
    )
    
    if enterprise_ready:
        print("\n🎉 ENTERPRISE-SYSTEM VOLLSTÄNDIG PRODUKTIONSREIF!")
        print("   Alle Compliance-, Security- und Quality-Standards erfüllt")
        print("   Bereit für Enterprise-Deployment in regulierten Umgebungen")
        final_exit_code = 0
    else:
        print("\n⚠️  ENTERPRISE-SYSTEM BENÖTIGT NACHBESSERUNGEN")
        print("   Compliance-Score unter 80% oder kritische Violations")
        print("   Manuelle Review und Korrektur erforderlich")
        final_exit_code = 1
    
    return final_exit_code


def main():
    """Hauptfunktion."""
    try:
        start_time = time.time()
        exit_code = demo_final_enterprise_system()
        duration = time.time() - start_time
        
        print(f"\n⏱️  Enterprise-Demo-Laufzeit: {duration:.1f}s")
        print(f"🚪 Final Exit Code: {exit_code}")
        
        return exit_code
        
    except KeyboardInterrupt:
        print("\n⚠️  Enterprise-Demo durch Benutzer abgebrochen")
        return 130
    except Exception as e:
        print(f"\n💥 Unerwarteter Enterprise-Fehler: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
