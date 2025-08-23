"""
Vollständige QA-Pipeline Demo mit allen Gates.

Demonstriert das Zusammenspiel aller implementierten Gates:
- Token Budget Gate
- Coverage Threshold Gate  
- Security Scanner mit Baselines
- SBOM & License Policy Gate
- Static Analysis Baselines
- QA Scorecard Integration
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Füge aktuelles Verzeichnis zum Python Path hinzu
sys.path.insert(0, str(Path(__file__).parent))

from coverage_threshold_gate import CoverageResult, CoverageThresholdGate
from feature_spec import FeatureSpec
from sbom_license_gate import Dependency, SBOMLicenseGate
from static_analysis_baselines import StaticAnalysisBaselines
from token_budget_gate import TokenBudgetGate, TokenUsage


def demo_complete_qa_pipeline():
    """Demonstriere eine vollständige QA-Pipeline mit allen Gates."""
    print("🏗️  VOLLSTÄNDIGE QA-PIPELINE DEMO")
    print("=" * 70)
    
    # Lade Feature-Spec
    print("\n📋 1. Feature-Spec laden")
    try:
        spec = FeatureSpec.from_file("test-feature-spec.yml")
        print(f"✅ Spec geladen: {spec.id} - {spec.title}")
        print(f"📊 Token Budget: {spec.token_budget}")
        print(f"📈 Coverage Min: {spec.tests.coverage_min}%")
    except Exception as e:
        print(f"⚠️  Fallback: Verwende Demo-Spec ({e})")
        # Fallback für Demo
        class DemoSpec:
            id = "COMPLETE-001"
            title = "Complete QA Pipeline Demo"
            token_budget = 8000
            class tests:
                coverage_min = 85
        spec = DemoSpec()
    
    # Initialisiere alle Gates
    print("\n🎯 2. Gates initialisieren")
    
    # Token Budget Gate
    token_gate = TokenBudgetGate(budget_limit=spec.token_budget, spec_id=spec.id)
    print(f"✅ Token Budget Gate: {spec.token_budget} Tokens")
    
    # Coverage Threshold Gate
    coverage_gate = CoverageThresholdGate(threshold_percent=spec.tests.coverage_min, spec_id=spec.id)
    print(f"✅ Coverage Threshold Gate: {spec.tests.coverage_min}%")
    
    # SBOM & License Policy Gate
    sbom_gate = SBOMLicenseGate(spec_id=spec.id)
    print(f"✅ SBOM License Gate: {len(sbom_gate.allowed_licenses)} erlaubte Lizenzen")
    
    # Static Analysis Baselines
    baselines = StaticAnalysisBaselines(spec_id=spec.id)
    baselines.set_active_profile("cicd")
    print(f"✅ Static Analysis Baselines: {baselines.active_profile} Profil")
    
    # Simuliere LLM-Workflow
    print("\n🤖 3. LLM-Workflow simulieren")
    
    # Mehrere LLM-Calls
    llm_calls = [
        TokenUsage(2000, 1500, 3500, "gpt-4o-mini", datetime.now().isoformat()),
        TokenUsage(1800, 1200, 3000, "gpt-4o-mini", datetime.now().isoformat()),
        TokenUsage(1000, 500, 1500, "gpt-4o-mini", datetime.now().isoformat()),
    ]
    
    total_tokens = 0
    for i, usage in enumerate(llm_calls, 1):
        token_gate.record_usage(usage)
        total_tokens += usage.total_tokens
        print(f"📞 LLM Call {i}: {usage.total_tokens} Tokens")
    
    print(f"📊 Gesamt Token-Verbrauch: {total_tokens}/{spec.token_budget}")
    
    # Simuliere Code-Generierung und Tests
    print("\n🧪 4. Code-Generierung & Tests simulieren")
    
    # Simuliere Coverage-Ergebnis
    coverage_result = CoverageResult(
        total_coverage=88.5,  # Über dem Threshold
        line_coverage=88.5,
        branch_coverage=85.0,
        files_count=25,
        lines_total=2000,
        lines_covered=1770,
        threshold_met=True,
        threshold_value=spec.tests.coverage_min,
        raw_report="Coverage: 88.5% - Tests passed"
    )
    coverage_gate.last_result = coverage_result
    print(f"📈 Coverage: {coverage_result.total_coverage}% (Threshold: {spec.tests.coverage_min}%)")
    
    # Simuliere SBOM-Generierung
    print("\n📦 5. SBOM & License Policy prüfen")
    
    # Simuliere Dependencies (mit einer problematischen Lizenz)
    sbom_gate.dependencies = [
        Dependency("requests", "2.31.0", "Apache-2.0"),
        Dependency("pydantic", "2.5.0", "MIT"),
        Dependency("typer", "0.9.0", "MIT"),
        Dependency("structlog", "24.1.0", "MIT"),
        Dependency("problematic-lib", "1.0.0", "GPL-3.0"),  # Verboten!
    ]
    
    license_ok = sbom_gate.check_license_policy()
    vuln_ok = sbom_gate.check_vulnerabilities()
    
    print(f"📋 Dependencies: {len(sbom_gate.dependencies)}")
    print(f"📜 License Policy: {'✅ PASSED' if license_ok else '❌ FAILED'}")
    print(f"🔍 Vulnerabilities: {'✅ PASSED' if vuln_ok else '❌ FAILED'}")
    
    if sbom_gate.license_violations:
        print("⚠️  License Violations:")
        for violation in sbom_gate.license_violations:
            print(f"   - {violation.dependency}: {violation.license} ({violation.violation_type})")
    
    # Simuliere Static Analysis
    print("\n🔍 6. Static Analysis mit Baselines")
    
    analysis_results = baselines.run_analysis_with_profile()
    baseline_compliant = baselines.check_baseline_compliance()
    
    print(f"📊 Findings: {analysis_results['total_findings']}")
    print(f"⚠️  High-Severity: {analysis_results['high_severity_count']}")
    print(f"📏 Baseline Compliance: {'✅ PASSED' if baseline_compliant else '❌ FAILED'}")
    
    # Gate-Prüfungen
    print("\n🔍 7. Gate-Prüfungen")
    
    token_passed = token_gate.check_gate()
    coverage_passed = coverage_gate.check_gate()
    sbom_passed = license_ok and vuln_ok
    baseline_passed = baseline_compliant
    
    gates_status = [
        ("Token Budget", token_passed),
        ("Coverage Threshold", coverage_passed),
        ("SBOM & License Policy", sbom_passed),
        ("Static Analysis Baselines", baseline_passed),
    ]
    
    for gate_name, passed in gates_status:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"🎯 {gate_name}: {status}")
    
    all_gates_passed = all(passed for _, passed in gates_status)
    
    # QA-Zusammenfassung generieren
    print("\n📋 8. Umfassende QA-Zusammenfassung")
    
    qa_sections = [
        token_gate.generate_qa_summary_section(),
        coverage_gate.generate_qa_summary_section(),
        sbom_gate.generate_qa_summary_section(),
        baselines.generate_qa_summary_section(),
    ]
    
    # Berechne Gesamt-Score
    total_score = sum(section["score"] for section in qa_sections) / len(qa_sections)
    
    qa_report = {
        "spec_id": spec.id,
        "timestamp": datetime.now().isoformat(),
        "pipeline_version": "complete-v1.0",
        "gates": qa_sections,
        "summary": {
            "overall_passed": all_gates_passed,
            "overall_score": round(total_score, 1),
            "gates_passed": sum(1 for _, passed in gates_status if passed),
            "gates_total": len(gates_status),
            "token_utilization": token_gate.get_usage_summary()["budget_utilization_percent"],
            "coverage_achieved": coverage_result.total_coverage,
            "dependencies_count": len(sbom_gate.dependencies),
            "license_violations": len(sbom_gate.license_violations),
            "security_findings": analysis_results["total_findings"],
            "high_severity_findings": analysis_results["high_severity_count"]
        },
        "pr_checks": [
            coverage_gate.generate_pr_status(),
            {
                "state": "success" if sbom_passed else "failure",
                "description": f"SBOM & Licenses: {len(sbom_gate.license_violations)} violations",
                "context": "ci/sbom-license-policy"
            },
            {
                "state": "success" if baseline_passed else "failure", 
                "description": f"Static Analysis: {analysis_results['high_severity_count']} high-severity",
                "context": "ci/static-analysis-baseline"
            }
        ],
        "artifacts": {
            "qa_scorecard": "qa_scorecard_complete.json",
            "sbom": "sbom_complete.json",
            "security_scan": "security_scan_complete.json",
            "coverage_report": "coverage_complete.xml"
        }
    }
    
    print(f"📊 Gesamt-Status: {'✅ PASSED' if all_gates_passed else '❌ FAILED'}")
    print(f"🏆 Gesamt-Score: {total_score:.1f}/100")
    print(f"🎯 Gates: {sum(1 for _, passed in gates_status if passed)}/{len(gates_status)} bestanden")
    
    # Detaillierte Fehler-Analyse
    if not all_gates_passed:
        print("\n❌ FEHLGESCHLAGENE GATES:")
        for gate_name, passed in gates_status:
            if not passed:
                print(f"   - {gate_name}")
                if gate_name == "SBOM & License Policy":
                    print(f"     Grund: {len(sbom_gate.license_violations)} Lizenz-Verletzungen")
                elif gate_name == "Static Analysis Baselines":
                    print(f"     Grund: {analysis_results['high_severity_count']} High-Severity Findings")
    
    # Reports speichern
    print("\n💾 9. Reports & Artefakte speichern")
    
    # Hauptreport
    with open("qa_pipeline_complete_report.json", "w", encoding="utf-8") as f:
        json.dump(qa_report, f, indent=2, ensure_ascii=False)
    print("✅ Haupt-Report: qa_pipeline_complete_report.json")
    
    # SBOM-Artefakte
    sbom_artifacts = sbom_gate.generate_artifacts("complete_pipeline_artifacts")
    print(f"✅ SBOM-Artefakte: {list(sbom_artifacts.keys())}")
    
    # Markdown-Report
    markdown_report = generate_complete_markdown_report(qa_report)
    with open("qa_pipeline_complete_report.md", "w", encoding="utf-8") as f:
        f.write(markdown_report)
    print("✅ Markdown-Report: qa_pipeline_complete_report.md")
    
    # Exit Code bestimmen
    exit_code = 0 if all_gates_passed else 1
    print("\n🚪 10. Pipeline-Ergebnis")
    
    if all_gates_passed:
        print("🎉 PIPELINE ERFOLGREICH ABGESCHLOSSEN!")
        print(f"   - Alle {len(gates_status)} Gates bestanden")
        print(f"   - Gesamt-Score: {total_score:.1f}/100")
        print("   - Bereit für Production-Deployment")
    else:
        print("💥 PIPELINE FEHLGESCHLAGEN!")
        print(f"   - {len(gates_status) - sum(1 for _, passed in gates_status if passed)}/{len(gates_status)} Gates fehlgeschlagen")
        print("   - Manuelle Überprüfung erforderlich")
        print("   - PR wird blockiert")
    
    print(f"\n🚪 Exit Code: {exit_code}")
    return exit_code


def generate_complete_markdown_report(qa_report: dict) -> str:
    """Generiere umfassenden Markdown-Report."""
    
    status_emoji = "🎉" if qa_report["summary"]["overall_passed"] else "💥"
    status_text = "ERFOLGREICH" if qa_report["summary"]["overall_passed"] else "FEHLGESCHLAGEN"
    
    markdown = f"""# 🏗️ Vollständige QA-Pipeline Report

**Spec ID:** {qa_report["spec_id"]}  
**Timestamp:** {qa_report["timestamp"]}  
**Pipeline Version:** {qa_report["pipeline_version"]}  
**Status:** {status_emoji} {status_text}  
**Gesamt-Score:** {qa_report["summary"]["overall_score"]}/100  
**Gates:** {qa_report["summary"]["gates_passed"]}/{qa_report["summary"]["gates_total"]} bestanden  

## 📊 Zusammenfassung

| Metrik | Wert | Status |
|--------|------|---------|
| Token-Nutzung | {qa_report["summary"]["token_utilization"]}% | {'✅' if qa_report["summary"]["token_utilization"] <= 100 else '❌'} |
| Code Coverage | {qa_report["summary"]["coverage_achieved"]}% | {'✅' if qa_report["summary"]["coverage_achieved"] >= 80 else '❌'} |
| Dependencies | {qa_report["summary"]["dependencies_count"]} | ℹ️ |
| Lizenz-Verletzungen | {qa_report["summary"]["license_violations"]} | {'✅' if qa_report["summary"]["license_violations"] == 0 else '❌'} |
| Security Findings | {qa_report["summary"]["security_findings"]} | ℹ️ |
| High-Severity Findings | {qa_report["summary"]["high_severity_findings"]} | {'✅' if qa_report["summary"]["high_severity_findings"] == 0 else '❌'} |

## 🎯 Gate-Ergebnisse

"""
    
    for gate in qa_report["gates"]:
        gate_emoji = "✅" if gate["passed"] else "❌"
        gate_status = "PASSED" if gate["passed"] else "FAILED"
        
        markdown += f"""### {gate["name"]} - {gate_emoji} {gate_status}

**Score:** {gate["score"]}/100  
"""
        
        if gate.get("details"):
            markdown += "**Details:**\n"
            for key, value in gate["details"].items():
                markdown += f"- **{key}**: {value}\n"
        
        if gate.get("error_message"):
            markdown += f"**❌ Fehler:** {gate['error_message']}\n"
        
        markdown += "\n"
    
    # PR Checks
    markdown += "## 🔍 PR Status Checks\n\n"
    for check in qa_report["pr_checks"]:
        check_emoji = "✅" if check["state"] == "success" else "❌"
        markdown += f"- {check_emoji} **{check['context']}**: {check['description']}\n"
    
    # Artefakte
    markdown += "\n## 📄 Generierte Artefakte\n\n"
    for artifact_type, artifact_path in qa_report["artifacts"].items():
        markdown += f"- **{artifact_type}**: `{artifact_path}`\n"
    
    return markdown


if __name__ == "__main__":
    exit_code = demo_complete_qa_pipeline()
    sys.exit(exit_code)
