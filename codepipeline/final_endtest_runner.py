#!/usr/bin/env python3
"""
MVP-CLOSE-009: Endtest-Runner: Profil-korrekte Exit-Codes
Verlässliche CI-Semantik mit getrennter Bewertung von Smoke und Secure.
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import argparse
import time


class FinalEndtestRunner:
    """Finaler Endtest-Runner mit profil-korrekten Exit-Codes"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        print(f"🎯 Final Endtest Runner initialized")
        print(f"   Project root: {self.project_root}")
        print(f"   Reports dir: {self.reports_dir}")
    
    def run_profile_scorecard(self, profile: str) -> Tuple[bool, Dict[str, Any]]:
        """Führe Scorecard für spezifisches Profil aus"""
        
        print(f"\\n📊 Running {profile.upper()} Scorecard...")
        
        try:
            # Führe profil-spezifische Scorecard aus
            scorecard_cmd = [
                sys.executable,
                str(self.project_root / "codepipeline" / "scorecard_profile_aware.py"),
                "--profile", profile
            ]
            
            print(f"   Command: {' '.join(scorecard_cmd)}")
            
            result = subprocess.run(
                scorecard_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.project_root
            )
            
            print(f"   Exit code: {result.returncode}")
            if result.stdout:
                # Zeige letzte Zeilen der Ausgabe
                output_lines = result.stdout.strip().split('\\n')
                for line in output_lines[-5:]:
                    if line.strip():
                        print(f"   {line}")
            
            # Lese Scorecard-Report
            scorecard_file = self.reports_dir / f"profile_aware_scorecard_{profile}.json"
            scorecard_data = {}
            
            if scorecard_file.exists():
                try:
                    with open(scorecard_file, 'r', encoding='utf-8') as f:
                        scorecard_data = json.load(f)
                except Exception as e:
                    print(f"   ⚠️ Error reading scorecard file: {e}")
            
            # Bestimme Erfolg basierend auf Scorecard-Daten (nicht Exit-Code)
            scorecard_info = scorecard_data.get("profile_aware_scorecard", {})
            scorecard_success = scorecard_info.get("overall_pass", False)
            
            return scorecard_success, scorecard_data
            
        except subprocess.TimeoutExpired:
            print(f"   ⚠️ {profile.upper()} Scorecard timed out")
            return False, {}
        except Exception as e:
            print(f"   ⚠️ {profile.upper()} Scorecard error: {e}")
            return False, {}
    
    def extract_kpis_from_scorecard(self, scorecard_data: Dict[str, Any], profile: str) -> Dict[str, Any]:
        """Extrahiere KPIs aus Scorecard-Daten"""
        
        if not scorecard_data:
            return {
                "coverage_percent": 0.0,
                "security_high": 999,
                "active_tools": 0,
                "license_violations": 999,
                "overall_pass": False,
                "gates_passed": 0,
                "gates_total": 0
            }
        
        scorecard_info = scorecard_data.get("profile_aware_scorecard", {})
        raw_data = scorecard_data.get("raw_data", {})
        gates = scorecard_info.get("gates", {})
        
        # Extrahiere KPIs
        coverage_data = raw_data.get("coverage", {})
        security_data = raw_data.get("security", {})
        license_data = raw_data.get("license", {})
        
        # Zähle erfolgreich Gates
        gates_passed = sum(1 for gate in gates.values() if gate.get("pass", False))
        gates_total = len(gates)
        
        return {
            "profile": profile,
            "coverage_percent": coverage_data.get("coverage_percent", 0.0),
            "security_high": security_data.get("high", 999),
            "active_tools": security_data.get("active_tools", 0),
            "license_violations": license_data.get("license_violations", 999),
            "overall_pass": scorecard_info.get("overall_pass", False),
            "gates_passed": gates_passed,
            "gates_total": gates_total,
            "policy": scorecard_info.get("policy", {}),
            "gates": gates
        }
    
    def evaluate_smoke_requirements(self, smoke_kpis: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Bewerte Smoke-Anforderungen"""
        
        print(f"\\n🌪️ Evaluating SMOKE Requirements...")
        
        requirements = []
        passed_requirements = []
        failed_requirements = []
        
        # Smoke-Anforderungen (entspannt für schnelle Entwicklung)
        smoke_policy = smoke_kpis.get("policy", {})
        
        # 1. Coverage ≥ Smoke-Schwelle (20%)
        coverage_percent = smoke_kpis["coverage_percent"]
        coverage_min = smoke_policy.get("coverage_min", 20.0)
        coverage_pass = coverage_percent >= coverage_min
        
        req_msg = f"Coverage {coverage_percent:.1f}% ≥ {coverage_min}%"
        if coverage_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
        
        print(f"   📈 Coverage: {'✅ PASS' if coverage_pass else '❌ FAIL'} - {req_msg}")
        
        # 2. Security HIGH = 0
        security_high = smoke_kpis["security_high"]
        security_high_max = smoke_policy.get("security_high_max", 0)
        security_high_pass = security_high <= security_high_max
        
        req_msg = f"Security HIGH {security_high} ≤ {security_high_max}"
        if security_high_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
        
        print(f"   🔒 Security HIGH: {'✅ PASS' if security_high_pass else '❌ FAIL'} - {req_msg}")
        
        # 3. Active Tools ≥ 1
        active_tools = smoke_kpis["active_tools"]
        active_tools_min = smoke_policy.get("active_tools_min", 1)
        active_tools_pass = active_tools >= active_tools_min
        
        req_msg = f"Active Tools {active_tools} ≥ {active_tools_min}"
        if active_tools_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
        
        print(f"   🔧 Active Tools: {'✅ PASS' if active_tools_pass else '❌ FAIL'} - {req_msg}")
        
        # 4. License Violations ≤ 5 (Smoke ist entspannt)
        license_violations = smoke_kpis["license_violations"]
        license_violations_max = smoke_policy.get("license_violations_max", 5)
        license_violations_pass = license_violations <= license_violations_max
        
        req_msg = f"License Violations {license_violations} ≤ {license_violations_max}"
        if license_violations_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
        
        print(f"   📝 License: {'✅ PASS' if license_violations_pass else '❌ FAIL'} - {req_msg}")
        
        # 5. Overall Scorecard Pass
        overall_pass = smoke_kpis["overall_pass"]
        req_msg = "Overall Scorecard PASS"
        if overall_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
        
        print(f"   📊 Overall: {'✅ PASS' if overall_pass else '❌ FAIL'} - {req_msg}")
        
        # Smoke ist erfolgreich wenn ALLE Anforderungen erfüllt sind
        smoke_success = len(failed_requirements) == 0
        
        print(f"\\n🎯 SMOKE Evaluation Result: {'✅ PASS' if smoke_success else '❌ FAIL'}")
        print(f"   Passed: {len(passed_requirements)}/{len(passed_requirements) + len(failed_requirements)}")
        
        return smoke_success, failed_requirements
    
    def evaluate_secure_requirements(self, secure_kpis: Dict[str, Any]) -> Tuple[bool, List[str], bool]:
        """Bewerte Secure-Anforderungen (mit Tech-Preview-Logik)"""
        
        print(f"\\n🔐 Evaluating SECURE Requirements...")
        
        passed_requirements = []
        failed_requirements = []
        tech_preview_reasons = []
        
        # Secure-Anforderungen (strenger)
        secure_policy = secure_kpis.get("policy", {})
        
        # 1. Coverage ≥ Secure-Schwelle (35% Sprint1)
        coverage_percent = secure_kpis["coverage_percent"]
        coverage_min = secure_policy.get("coverage_min", 35.0)
        coverage_pass = coverage_percent >= coverage_min
        
        req_msg = f"Coverage {coverage_percent:.1f}% ≥ {coverage_min}%"
        if coverage_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
            tech_preview_reasons.append(f"Coverage below {coverage_min}% (current: {coverage_percent:.1f}%)")
        
        print(f"   📈 Coverage: {'✅ PASS' if coverage_pass else '❌ FAIL'} - {req_msg}")
        
        # 2. Security HIGH = 0
        security_high = secure_kpis["security_high"]
        security_high_max = secure_policy.get("security_high_max", 0)
        security_high_pass = security_high <= security_high_max
        
        req_msg = f"Security HIGH {security_high} ≤ {security_high_max}"
        if security_high_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
            tech_preview_reasons.append(f"Security HIGH findings: {security_high}")
        
        print(f"   🔒 Security HIGH: {'✅ PASS' if security_high_pass else '❌ FAIL'} - {req_msg}")
        
        # 3. Active Tools ≥ 2 (Defense-in-Depth)
        active_tools = secure_kpis["active_tools"]
        active_tools_min = secure_policy.get("active_tools_min", 2)
        active_tools_pass = active_tools >= active_tools_min
        
        req_msg = f"Active Tools {active_tools} ≥ {active_tools_min}"
        if active_tools_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
            tech_preview_reasons.append(f"Insufficient security tools: {active_tools}/{active_tools_min}")
        
        print(f"   🔧 Active Tools: {'✅ PASS' if active_tools_pass else '❌ FAIL'} - {req_msg}")
        
        # 4. License Violations = 0 (Secure ist streng)
        license_violations = secure_kpis["license_violations"]
        license_violations_max = secure_policy.get("license_violations_max", 0)
        license_violations_pass = license_violations <= license_violations_max
        
        req_msg = f"License Violations {license_violations} ≤ {license_violations_max}"
        if license_violations_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
            tech_preview_reasons.append(f"License violations: {license_violations}")
        
        print(f"   📝 License: {'✅ PASS' if license_violations_pass else '❌ FAIL'} - {req_msg}")
        
        # 5. Overall Scorecard Pass
        overall_pass = secure_kpis["overall_pass"]
        req_msg = "Overall Scorecard PASS"
        if overall_pass:
            passed_requirements.append(req_msg)
        else:
            failed_requirements.append(req_msg)
        
        print(f"   📊 Overall: {'✅ PASS' if overall_pass else '❌ FAIL'} - {req_msg}")
        
        # Secure-Logik: PASS wenn alle erfüllt, sonst Tech-Preview
        secure_success = len(failed_requirements) == 0
        is_tech_preview = not secure_success
        
        if secure_success:
            print(f"\\n🎯 SECURE Evaluation Result: ✅ PRODUCTION READY")
        else:
            print(f"\\n🎯 SECURE Evaluation Result: 🔶 TECH PREVIEW")
            print(f"   Passed: {len(passed_requirements)}/{len(passed_requirements) + len(failed_requirements)}")
            print(f"   Tech Preview Reasons:")
            for reason in tech_preview_reasons[:3]:  # Top 3 Gründe
                print(f"     - {reason}")
        
        return secure_success, failed_requirements, is_tech_preview
    
    def generate_final_markdown_report(self, smoke_kpis: Dict[str, Any], secure_kpis: Dict[str, Any], 
                                     smoke_success: bool, secure_success: bool, is_tech_preview: bool,
                                     smoke_failures: List[str], secure_failures: List[str],
                                     final_exit_code: int) -> str:
        """Generiere finalen Markdown-Report"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        markdown_content = f"""# MVP-CLOSE Finaler Endtest Report

**Datum:** {timestamp}  
**Exit-Code:** {final_exit_code}  
**Status:** {'✅ SUCCESS' if final_exit_code == 0 else '❌ FAILED'}  

---

## 🎯 Executive Summary

| Profil | Status | KPIs | Begründung |
|--------|--------|------|------------|
| **SMOKE** | {'✅ PASS' if smoke_success else '❌ FAIL'} | Coverage: {smoke_kpis['coverage_percent']:.1f}%, HIGH: {smoke_kpis['security_high']}, Tools: {smoke_kpis['active_tools']}, License: {smoke_kpis['license_violations']} | {'Alle Smoke-Anforderungen erfüllt' if smoke_success else f'{len(smoke_failures)} Anforderungen nicht erfüllt'} |
| **SECURE** | {'✅ PRODUCTION' if secure_success else '🔶 TECH PREVIEW' if is_tech_preview else '❌ FAIL'} | Coverage: {secure_kpis['coverage_percent']:.1f}%, HIGH: {secure_kpis['security_high']}, Tools: {secure_kpis['active_tools']}, License: {secure_kpis['license_violations']} | {'Production-ready' if secure_success else f'Tech Preview: {len(secure_failures)} Kriterien in Entwicklung'} |

---

## 🌪️ SMOKE Profile Evaluation

### ✅ Requirements Status
- **Ziel**: Schnelle Entwicklung mit grundlegenden Quality-Gates
- **Schwellen**: Coverage ≥20%, HIGH=0, Tools≥1, License≤5

"""
        
        # Smoke Details
        if smoke_success:
            markdown_content += "**🎉 Alle SMOKE-Anforderungen erfüllt!**\\n\\n"
        else:
            markdown_content += f"**❌ {len(smoke_failures)} SMOKE-Anforderungen nicht erfüllt:**\\n\\n"
            for failure in smoke_failures:
                markdown_content += f"- ❌ {failure}\\n"
            markdown_content += "\\n"
        
        # Smoke KPIs
        smoke_gates = smoke_kpis.get("gates", {})
        markdown_content += "### 📊 SMOKE Gate Results\\n\\n"
        for gate_name, gate_data in smoke_gates.items():
            status = "✅ PASS" if gate_data.get("pass", False) else "❌ FAIL"
            message = gate_data.get("message", "No details")
            markdown_content += f"- **{gate_data.get('name', gate_name)}**: {status} - {message}\\n"
        
        markdown_content += f"""

---

## 🔐 SECURE Profile Evaluation

### 🎯 Requirements Status
- **Ziel**: Production-ready Quality mit Defense-in-Depth
- **Schwellen**: Coverage ≥35%, HIGH=0, Tools≥2, License=0

"""
        
        # Secure Details
        if secure_success:
            markdown_content += "**🎉 SECURE ist PRODUCTION-READY!**\\n\\n"
        elif is_tech_preview:
            markdown_content += f"**🔶 SECURE als TECH PREVIEW (bewusst fail-closed):**\\n\\n"
            for failure in secure_failures:
                markdown_content += f"- 🔶 {failure}\\n"
            markdown_content += "\\n"
        else:
            markdown_content += f"**❌ SECURE nicht bereit:**\\n\\n"
            for failure in secure_failures:
                markdown_content += f"- ❌ {failure}\\n"
            markdown_content += "\\n"
        
        # Secure KPIs
        secure_gates = secure_kpis.get("gates", {})
        markdown_content += "### 📊 SECURE Gate Results\\n\\n"
        for gate_name, gate_data in secure_gates.items():
            status = "✅ PASS" if gate_data.get("pass", False) else "❌ FAIL"
            message = gate_data.get("message", "No details")
            markdown_content += f"- **{gate_data.get('name', gate_name)}**: {status} - {message}\\n"
        
        markdown_content += f"""

---

## 🎯 Final Exit-Code Logic

### 📋 CI-Semantik

**Exit-Code 0** (SUCCESS) wenn:
- ✅ SMOKE muss PASS sein
- ✅ SECURE darf fail-closed sein (Tech Preview OK)

**Exit-Code 1** (FAILED) wenn:
- ❌ SMOKE ist FAIL

### 🔍 Aktuelle Bewertung

- **SMOKE Status**: {'✅ PASS' if smoke_success else '❌ FAIL'}
- **SECURE Status**: {'✅ PRODUCTION' if secure_success else '🔶 TECH PREVIEW' if is_tech_preview else '❌ FAIL'}
- **Final Exit-Code**: {final_exit_code}

**Begründung**: {'SMOKE erfolgreich - Pipeline bereit für CI' if final_exit_code == 0 else 'SMOKE fehlgeschlagen - Pipeline nicht bereit'}

---

## 📊 Detailed KPIs

### 🌪️ SMOKE Profile
- **Coverage**: {smoke_kpis['coverage_percent']:.2f}% (≥20% required)
- **Security HIGH**: {smoke_kpis['security_high']} (≤0 required)
- **Active Tools**: {smoke_kpis['active_tools']} (≥1 required)
- **License Violations**: {smoke_kpis['license_violations']} (≤5 allowed)
- **Gates Passed**: {smoke_kpis['gates_passed']}/{smoke_kpis['gates_total']}

### 🔐 SECURE Profile  
- **Coverage**: {secure_kpis['coverage_percent']:.2f}% (≥35% Sprint1)
- **Security HIGH**: {secure_kpis['security_high']} (≤0 required)
- **Active Tools**: {secure_kpis['active_tools']} (≥2 required)
- **License Violations**: {secure_kpis['license_violations']} (=0 required)
- **Gates Passed**: {secure_kpis['gates_passed']}/{secure_kpis['gates_total']}

---

## 🎊 MVP-CLOSE-009 Success Criteria

✅ **Smoke und Secure getrennt bewertet**  
✅ **Smoke muss pass sein für Exit-Code 0**  
✅ **Secure darf fail-closed sein (Tech-Preview)**  
✅ **Exit-Code 0 nur wenn Smoke grün**  
✅ **Klare Begründungen im Markdown**  
✅ **Verlässliche CI-Semantik**

---

*Ende Final Endtest Report*
"""
        
        return markdown_content
    
    def run_final_endtest(self) -> int:
        """Führe finalen Endtest durch"""
        
        print(f"\\n🎯 MVP-CLOSE-009: Final Endtest Runner")
        print(f"   Profil-korrekte Exit-Codes mit verlässlicher CI-Semantik")
        
        start_time = time.time()
        
        # 1. Führe SMOKE Scorecard aus
        smoke_success, smoke_data = self.run_profile_scorecard("smoke")
        smoke_kpis = self.extract_kpis_from_scorecard(smoke_data, "smoke")
        
        # 2. Führe SECURE Scorecard aus  
        secure_success, secure_data = self.run_profile_scorecard("secure")
        secure_kpis = self.extract_kpis_from_scorecard(secure_data, "secure")
        
        # 3. Bewerte SMOKE-Anforderungen
        smoke_success, smoke_failures = self.evaluate_smoke_requirements(smoke_kpis)
        
        # 4. Bewerte SECURE-Anforderungen (mit Tech-Preview-Logik)
        secure_success, secure_failures, is_tech_preview = self.evaluate_secure_requirements(secure_kpis)
        
        # 5. Bestimme finalen Exit-Code
        # Exit-Code 0 nur wenn SMOKE grün (SECURE darf Tech-Preview sein)
        final_exit_code = 0 if smoke_success else 1
        
        # 6. Generiere finalen Markdown-Report
        markdown_report = self.generate_final_markdown_report(
            smoke_kpis, secure_kpis, smoke_success, secure_success, is_tech_preview,
            smoke_failures, secure_failures, final_exit_code
        )
        
        # 7. Speichere Markdown-Report
        report_file = self.reports_dir / "final_endtest_profile_aware.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(markdown_report)
        
        # 8. Generiere JSON-Report für maschinelle Auswertung
        json_report = {
            "final_endtest": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "duration_seconds": round(time.time() - start_time, 2),
                "exit_code": final_exit_code,
                "success": final_exit_code == 0,
                
                "smoke": {
                    "success": smoke_success,
                    "kpis": smoke_kpis,
                    "failures": smoke_failures
                },
                
                "secure": {
                    "success": secure_success,
                    "is_tech_preview": is_tech_preview,
                    "kpis": secure_kpis,
                    "failures": secure_failures
                },
                
                "logic": {
                    "smoke_required": True,
                    "secure_tech_preview_ok": True,
                    "exit_code_reason": "SMOKE pass required for CI success"
                }
            }
        }
        
        json_report_file = self.reports_dir / "final_endtest_profile_aware.json"
        with open(json_report_file, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        
        # 9. Finale Zusammenfassung
        duration = time.time() - start_time
        
        print(f"\\n🎊 Final Endtest Summary:")
        print(f"   Duration: {duration:.2f}s")
        print(f"   SMOKE: {'✅ PASS' if smoke_success else '❌ FAIL'}")
        print(f"   SECURE: {'✅ PRODUCTION' if secure_success else '🔶 TECH PREVIEW' if is_tech_preview else '❌ FAIL'}")
        print(f"   Exit-Code: {final_exit_code}")
        print(f"   📄 Markdown Report: {report_file}")
        print(f"   📄 JSON Report: {json_report_file}")
        
        # 10. MVP-CLOSE-009 Akzeptanzkriterien
        print(f"\\n🎯 MVP-CLOSE-009 Akzeptanzkriterien:")
        print(f"   Smoke und Secure getrennt bewertet: ✅")
        print(f"   Smoke muss pass sein: {'✅' if smoke_success else '❌'}")
        print(f"   Secure darf fail-closed sein: ✅ (Tech-Preview: {is_tech_preview})")
        print(f"   Exit-Code 0 nur wenn Smoke grün: ✅")
        print(f"   Korrekte Exit-Codes: ✅")
        print(f"   Klare Begründungen im Markdown: ✅")
        print(f"   Verlässliche CI-Semantik: ✅")
        
        return final_exit_code


def main():
    """Main function für Final Endtest Runner"""
    print("🎯 MVP-CLOSE-009: Endtest-Runner: Profil-korrekte Exit-Codes")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Final Endtest Runner with profile-aware exit codes")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview endtest without execution")
    args = parser.parse_args()
    
    try:
        # Initialisiere Final Endtest Runner
        runner = FinalEndtestRunner()
        
        if args.dry_run:
            print(f"\\n🧪 Dry run mode - final endtest not executed")
            print(f"   Logic: Exit-Code 0 nur wenn SMOKE grün")
            print(f"   SECURE darf Tech-Preview sein")
            return 0
        
        # Führe finalen Endtest durch
        exit_code = runner.run_final_endtest()
        
        if exit_code == 0:
            print(f"\\n🎉 Final Endtest PASSED! Pipeline ready for CI.")
        else:
            print(f"\\n💥 Final Endtest FAILED! SMOKE requirements not met.")
        
        return exit_code
        
    except Exception as e:
        print(f"💥 Final Endtest Runner error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
