"""
Integriertes Demo für alle QA Gates.

Demonstriert das Zusammenspiel aller implementierten Gates:
- Token Budget Gate
- Coverage Threshold Gate  
- Security Scanner
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
from token_budget_gate import TokenBudgetGate, TokenUsage


def demo_integrated_qa_pipeline():
    """Demonstriere eine vollständige QA-Pipeline mit allen Gates."""
    print("🏗️  Integrierte QA-Pipeline Demo")
    print("=" * 60)
    
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
            id = "DEMO-001"
            title = "Demo Feature"
            token_budget = 5000
            class tests:
                coverage_min = 80
        spec = DemoSpec()
    
    # Initialisiere Gates
    print("\n🎯 2. Gates initialisieren")
    token_gate = TokenBudgetGate(budget_limit=spec.token_budget, spec_id=spec.id)
    coverage_gate = CoverageThresholdGate(threshold_percent=spec.tests.coverage_min, spec_id=spec.id)
    
    print(f"✅ Token Budget Gate: {spec.token_budget} Tokens")
    print(f"✅ Coverage Threshold Gate: {spec.tests.coverage_min}%")
    
    # Simuliere LLM-Calls mit Token-Verbrauch
    print("\n🤖 3. LLM-Calls simulieren")
    
    # Call 1: Erfolgreicher Call
    usage1 = TokenUsage(
        prompt_tokens=1500,
        completion_tokens=800,
        total_tokens=2300,
        model="gpt-4o-mini",
        timestamp=datetime.now().isoformat()
    )
    token_gate.record_usage(usage1)
    print(f"📞 LLM Call 1: {usage1.total_tokens} Tokens")
    
    # Call 2: Größerer Call
    usage2 = TokenUsage(
        prompt_tokens=2000,
        completion_tokens=1200,
        total_tokens=3200,
        model="gpt-4o-mini",
        timestamp=datetime.now().isoformat()
    )
    token_gate.record_usage(usage2)
    print(f"📞 LLM Call 2: {usage2.total_tokens} Tokens")
    
    total_tokens = usage1.total_tokens + usage2.total_tokens
    print(f"📊 Gesamt Token-Verbrauch: {total_tokens}/{spec.token_budget}")
    
    # Simuliere Coverage-Analyse
    print("\n📊 4. Coverage-Analyse simulieren")
    
    # Erstelle simuliertes Coverage-Ergebnis
    coverage_result = CoverageResult(
        total_coverage=85.0,  # Über dem Threshold
        line_coverage=85.0,
        branch_coverage=82.0,
        files_count=20,
        lines_total=1500,
        lines_covered=1275,
        threshold_met=True,
        threshold_value=spec.tests.coverage_min,
        raw_report="Coverage: 85% - All tests passed"
    )
    coverage_gate.last_result = coverage_result
    print(f"📈 Coverage: {coverage_result.total_coverage}% (Threshold: {spec.tests.coverage_min}%)")
    
    # Gate-Prüfungen
    print("\n🔍 5. Gate-Prüfungen")
    
    token_passed = token_gate.check_gate()
    coverage_passed = coverage_gate.check_gate()
    
    print(f"🎯 Token Budget Gate: {'✅ PASSED' if token_passed else '❌ FAILED'}")
    print(f"📊 Coverage Gate: {'✅ PASSED' if coverage_passed else '❌ FAILED'}")
    
    # QA-Zusammenfassung generieren
    print("\n📋 6. QA-Zusammenfassung")
    
    token_summary = token_gate.generate_qa_summary_section()
    coverage_summary = coverage_gate.generate_qa_summary_section()
    
    qa_report = {
        "spec_id": spec.id,
        "timestamp": datetime.now().isoformat(),
        "gates": [
            token_summary,
            coverage_summary
        ],
        "overall_passed": token_passed and coverage_passed,
        "overall_score": (token_summary["score"] + coverage_summary["score"]) / 2,
        "pr_checks": [
            coverage_gate.generate_pr_status()
        ]
    }
    
    print(f"📊 Gesamt-Status: {'✅ PASSED' if qa_report['overall_passed'] else '❌ FAILED'}")
    print(f"🏆 Gesamt-Score: {qa_report['overall_score']:.1f}")
    
    # JSON-Report speichern
    print("\n💾 7. Reports speichern")
    
    with open("integrated_qa_report.json", "w") as f:
        json.dump(qa_report, f, indent=2)
    print("✅ JSON-Report: integrated_qa_report.json")
    
    # Markdown-Report generieren
    markdown_report = generate_markdown_report(qa_report)
    with open("integrated_qa_report.md", "w", encoding="utf-8") as f:
        f.write(markdown_report)
    print("✅ Markdown-Report: integrated_qa_report.md")
    
    # Exit Code basierend auf Gates
    exit_code = 0 if qa_report['overall_passed'] else 1
    print(f"\n🚪 8. Exit Code: {exit_code}")
    
    if not qa_report['overall_passed']:
        print("❌ Pipeline FEHLGESCHLAGEN:")
        if not token_passed:
            print("   - Token Budget überschritten")
        if not coverage_passed:
            print("   - Coverage Threshold unterschritten")
    else:
        print("✅ Pipeline ERFOLGREICH abgeschlossen!")
    
    return exit_code


def generate_markdown_report(qa_report: dict) -> str:
    """Generiere Markdown-Report aus QA-Daten."""
    
    status_emoji = "✅" if qa_report["overall_passed"] else "❌"
    status_text = "PASSED" if qa_report["overall_passed"] else "FAILED"
    
    markdown = f"""# QA Pipeline Report

**Spec ID:** {qa_report["spec_id"]}  
**Timestamp:** {qa_report["timestamp"]}  
**Overall Status:** {status_emoji} {status_text}  
**Overall Score:** {qa_report["overall_score"]:.1f}/100  

## Gate Results

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
                markdown += f"- {key}: {value}\n"
        
        if gate.get("error_message"):
            markdown += f"**Error:** {gate['error_message']}\n"
        
        markdown += "\n"
    
    # PR Checks
    if qa_report.get("pr_checks"):
        markdown += "## PR Status Checks\n\n"
        for check in qa_report["pr_checks"]:
            check_emoji = "✅" if check["state"] == "success" else "❌"
            markdown += f"- {check_emoji} **{check['context']}**: {check['description']}\n"
    
    return markdown


if __name__ == "__main__":
    exit_code = demo_integrated_qa_pipeline()
    sys.exit(exit_code)
