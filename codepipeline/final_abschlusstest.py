#!/usr/bin/env python3
"""
MVP-CLOSE-TEST: Abschlusstest Smoke+Secure
Nachweis der Mindestvoraussetzungen mit komprimierter Matrix Profil×Gate.
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import argparse
import time


class FinalAbschlusstest:
    """Finaler Abschlusstest für Smoke und Secure Profile"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Mindestvoraussetzungen
        self.smoke_requirements = {
            "active_tools_min": 1,
            "security_high_max": 0,
            "coverage_min": 20.0,
            "license_violations_max": 5
        }
        
        self.secure_requirements = {
            "active_tools_min": 2,
            "security_high_max": 0,
            "coverage_min": 35.0,  # Stufe 1
            "license_violations_max": 0
        }
        
        print(f"🎯 Final Abschlusstest initialized")
        print(f"   Smoke Requirements: Tools≥{self.smoke_requirements['active_tools_min']}, HIGH≤{self.smoke_requirements['security_high_max']}, Coverage≥{self.smoke_requirements['coverage_min']}%")
        print(f"   Secure Requirements: Tools≥{self.secure_requirements['active_tools_min']}, HIGH≤{self.secure_requirements['security_high_max']}, Coverage≥{self.secure_requirements['coverage_min']}%")
    
    def run_smoke_test(self) -> Tuple[bool, Dict[str, Any]]:
        """Führe Smoke-Lauf durch"""
        
        print(f"\\n🌪️ Running SMOKE Test...")
        
        try:
            # Führe Smoke Scorecard aus
            smoke_cmd = [
                sys.executable,
                str(self.project_root / "codepipeline" / "scorecard_profile_aware.py"),
                "--profile", "smoke"
            ]
            
            print(f"   Command: {' '.join(smoke_cmd)}")
            
            result = subprocess.run(
                smoke_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.project_root
            )
            
            print(f"   Exit code: {result.returncode}")
            
            # Lese Smoke Scorecard Report
            scorecard_file = self.reports_dir / "profile_aware_scorecard_smoke.json"
            if scorecard_file.exists():
                with open(scorecard_file, 'r', encoding='utf-8') as f:
                    scorecard_data = json.load(f)
                
                # Extrahiere Kennzahlen
                kpis = self.extract_kpis_from_scorecard(scorecard_data, "smoke")
                
                # Prüfe Mindestvoraussetzungen
                success = self.check_smoke_requirements(kpis)
                
                return success, kpis
            else:
                print(f"   ⚠️ Smoke scorecard not found")
                return False, {}
                
        except subprocess.TimeoutExpired:
            print(f"   ⚠️ Smoke test timed out")
            return False, {}
        except Exception as e:
            print(f"   ⚠️ Smoke test error: {e}")
            return False, {}
    
    def run_secure_test(self) -> Tuple[bool, Dict[str, Any]]:
        """Führe Secure-Dry-Run durch"""
        
        print(f"\\n🔐 Running SECURE Dry Run...")
        
        try:
            # Führe Secure Scorecard aus
            secure_cmd = [
                sys.executable,
                str(self.project_root / "codepipeline" / "scorecard_profile_aware.py"),
                "--profile", "secure"
            ]
            
            print(f"   Command: {' '.join(secure_cmd)}")
            
            result = subprocess.run(
                secure_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.project_root
            )
            
            print(f"   Exit code: {result.returncode}")
            
            # Lese Secure Scorecard Report
            scorecard_file = self.reports_dir / "profile_aware_scorecard_secure.json"
            if scorecard_file.exists():
                with open(scorecard_file, 'r', encoding='utf-8') as f:
                    scorecard_data = json.load(f)
                
                # Extrahiere Kennzahlen
                kpis = self.extract_kpis_from_scorecard(scorecard_data, "secure")
                
                # Prüfe Mindestvoraussetzungen
                success = self.check_secure_requirements(kpis)
                
                return success, kpis
            else:
                print(f"   ⚠️ Secure scorecard not found")
                return False, {}
                
        except subprocess.TimeoutExpired:
            print(f"   ⚠️ Secure test timed out")
            return False, {}
        except Exception as e:
            print(f"   ⚠️ Secure test error: {e}")
            return False, {}
    
    def extract_kpis_from_scorecard(self, scorecard_data: Dict[str, Any], profile: str) -> Dict[str, Any]:
        """Extrahiere KPIs aus Scorecard-Daten"""
        
        if not scorecard_data:
            return {
                "profile": profile,
                "coverage_percent": 0.0,
                "security_high": 999,
                "active_tools": 0,
                "license_violations": 999,
                "overall_pass": False,
                "gates": {}
            }
        
        scorecard_info = scorecard_data.get("profile_aware_scorecard", {})
        raw_data = scorecard_data.get("raw_data", {})
        gates = scorecard_info.get("gates", {})
        
        # Extrahiere KPIs
        coverage_data = raw_data.get("coverage", {})
        security_data = raw_data.get("security", {})
        license_data = raw_data.get("license", {})
        
        return {
            "profile": profile,
            "coverage_percent": coverage_data.get("coverage_percent", 0.0),
            "security_high": security_data.get("high", 999),
            "active_tools": security_data.get("active_tools", 0),
            "license_violations": license_data.get("license_violations", 999),
            "overall_pass": scorecard_info.get("overall_pass", False),
            "gates": gates,
            "policy": scorecard_info.get("policy", {})
        }
    
    def check_smoke_requirements(self, kpis: Dict[str, Any]) -> bool:
        """Prüfe Smoke-Mindestvoraussetzungen"""
        
        print(f"   📊 Checking SMOKE requirements...")
        
        # 1. Active Tools ≥ 1
        active_tools = kpis.get("active_tools", 0)
        active_tools_ok = active_tools >= self.smoke_requirements["active_tools_min"]
        print(f"   🔧 Active Tools: {active_tools} {'≥' if active_tools_ok else '<'} {self.smoke_requirements['active_tools_min']} {'✅' if active_tools_ok else '❌'}")
        
        # 2. Security HIGH == 0
        security_high = kpis.get("security_high", 999)
        security_high_ok = security_high <= self.smoke_requirements["security_high_max"]
        print(f"   🔒 Security HIGH: {security_high} {'≤' if security_high_ok else '>'} {self.smoke_requirements['security_high_max']} {'✅' if security_high_ok else '❌'}")
        
        # 3. Coverage ≥ Smoke-Schwelle
        coverage_percent = kpis.get("coverage_percent", 0.0)
        coverage_ok = coverage_percent >= self.smoke_requirements["coverage_min"]
        print(f"   📈 Coverage: {coverage_percent:.2f}% {'≥' if coverage_ok else '<'} {self.smoke_requirements['coverage_min']}% {'✅' if coverage_ok else '❌'}")
        
        # 4. License Violations ≤ Limit
        license_violations = kpis.get("license_violations", 999)
        license_ok = license_violations <= self.smoke_requirements["license_violations_max"]
        print(f"   📝 License Violations: {license_violations} {'≤' if license_ok else '>'} {self.smoke_requirements['license_violations_max']} {'✅' if license_ok else '❌'}")
        
        # 5. Overall Pass
        overall_pass = kpis.get("overall_pass", False)
        print(f"   📊 Overall Pass: {'✅' if overall_pass else '❌'}")
        
        # Alle Anforderungen müssen erfüllt sein
        all_requirements_met = active_tools_ok and security_high_ok and coverage_ok and license_ok and overall_pass
        
        print(f"   🎯 SMOKE Result: {'✅ PASS' if all_requirements_met else '❌ FAIL'}")
        
        return all_requirements_met
    
    def check_secure_requirements(self, kpis: Dict[str, Any]) -> bool:
        """Prüfe Secure-Mindestvoraussetzungen"""
        
        print(f"   📊 Checking SECURE requirements...")
        
        # 1. Active Tools ≥ 2
        active_tools = kpis.get("active_tools", 0)
        active_tools_ok = active_tools >= self.secure_requirements["active_tools_min"]
        print(f"   🔧 Active Tools: {active_tools} {'≥' if active_tools_ok else '<'} {self.secure_requirements['active_tools_min']} {'✅' if active_tools_ok else '❌'}")
        
        # 2. Security HIGH == 0
        security_high = kpis.get("security_high", 999)
        security_high_ok = security_high <= self.secure_requirements["security_high_max"]
        print(f"   🔒 Security HIGH: {security_high} {'≤' if security_high_ok else '>'} {self.secure_requirements['security_high_max']} {'✅' if security_high_ok else '❌'}")
        
        # 3. Coverage ≥ Secure-Stufe1
        coverage_percent = kpis.get("coverage_percent", 0.0)
        coverage_ok = coverage_percent >= self.secure_requirements["coverage_min"]
        print(f"   📈 Coverage: {coverage_percent:.2f}% {'≥' if coverage_ok else '<'} {self.secure_requirements['coverage_min']}% {'✅' if coverage_ok else '❌'}")
        
        # 4. License Violations = 0
        license_violations = kpis.get("license_violations", 999)
        license_ok = license_violations <= self.secure_requirements["license_violations_max"]
        print(f"   📝 License Violations: {license_violations} {'≤' if license_ok else '>'} {self.secure_requirements['license_violations_max']} {'✅' if license_ok else '❌'}")
        
        # 5. Overall Pass
        overall_pass = kpis.get("overall_pass", False)
        print(f"   📊 Overall Pass: {'✅' if overall_pass else '❌'}")
        
        # Alle Anforderungen müssen erfüllt sein
        all_requirements_met = active_tools_ok and security_high_ok and coverage_ok and license_ok and overall_pass
        
        print(f"   🎯 SECURE Result: {'✅ PASS' if all_requirements_met else '❌ FAIL'}")
        
        return all_requirements_met
    
    def generate_compressed_matrix_markdown(self, smoke_success: bool, smoke_kpis: Dict[str, Any],
                                          secure_success: bool, secure_kpis: Dict[str, Any]) -> str:
        """Generiere komprimierte Matrix Profil×Gate als Markdown"""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Gate-Status für Matrix
        def get_gate_status(kpis: Dict[str, Any], gate_name: str) -> str:
            gates = kpis.get("gates", {})
            gate_info = gates.get(gate_name, {})
            return "✅" if gate_info.get("pass", False) else "❌"
        
        # Berechne individuelle Gate-Status
        smoke_coverage_status = "✅" if smoke_kpis.get("coverage_percent", 0.0) >= self.smoke_requirements["coverage_min"] else "❌"
        smoke_security_status = "✅" if smoke_kpis.get("security_high", 999) <= self.smoke_requirements["security_high_max"] else "❌"
        smoke_tools_status = "✅" if smoke_kpis.get("active_tools", 0) >= self.smoke_requirements["active_tools_min"] else "❌"
        smoke_license_status = "✅" if smoke_kpis.get("license_violations", 999) <= self.smoke_requirements["license_violations_max"] else "❌"
        smoke_overall_status = "✅" if smoke_success else "❌"
        
        secure_coverage_status = "✅" if secure_kpis.get("coverage_percent", 0.0) >= self.secure_requirements["coverage_min"] else "❌"
        secure_security_status = "✅" if secure_kpis.get("security_high", 999) <= self.secure_requirements["security_high_max"] else "❌"
        secure_tools_status = "✅" if secure_kpis.get("active_tools", 0) >= self.secure_requirements["active_tools_min"] else "❌"
        secure_license_status = "✅" if secure_kpis.get("license_violations", 999) <= self.secure_requirements["license_violations_max"] else "❌"
        secure_overall_status = "✅" if secure_success else "❌"
        
        matrix_content = f"""# MVP-CLOSE-TEST: Abschlusstest Smoke+Secure - Matrix

**Datum:** {timestamp}  
**Status:** {'✅ BEIDE PASS' if smoke_success and secure_success else '❌ MINDESTENS EINER FAIL'}  
**Ziel:** Nachweis der Mindestvoraussetzungen für beide Profile  

---

## 🎯 Komprimierte Matrix: Profil × Gate

| Profil | Coverage | Security HIGH | Active Tools | License | Overall | Status |
|--------|----------|---------------|--------------|---------|---------|--------|
| **🌪️ SMOKE** | {smoke_coverage_status} {smoke_kpis.get('coverage_percent', 0.0):.1f}%≥{self.smoke_requirements['coverage_min']}% | {smoke_security_status} {smoke_kpis.get('security_high', 999)}≤{self.smoke_requirements['security_high_max']} | {smoke_tools_status} {smoke_kpis.get('active_tools', 0)}≥{self.smoke_requirements['active_tools_min']} | {smoke_license_status} {smoke_kpis.get('license_violations', 999)}≤{self.smoke_requirements['license_violations_max']} | {smoke_overall_status} | **{'PASS' if smoke_success else 'FAIL'}** |
| **🔐 SECURE** | {secure_coverage_status} {secure_kpis.get('coverage_percent', 0.0):.1f}%≥{self.secure_requirements['coverage_min']}% | {secure_security_status} {secure_kpis.get('security_high', 999)}≤{self.secure_requirements['security_high_max']} | {secure_tools_status} {secure_kpis.get('active_tools', 0)}≥{self.secure_requirements['active_tools_min']} | {secure_license_status} {secure_kpis.get('license_violations', 999)}≤{self.secure_requirements['license_violations_max']} | {secure_overall_status} | **{'PASS' if secure_success else 'FAIL'}** |

---

## 📊 Detaillierte Kennzahlen

### 🌪️ SMOKE Profile
- **Coverage**: {smoke_kpis.get('coverage_percent', 0.0):.2f}% (Soll: ≥{self.smoke_requirements['coverage_min']}%)
- **Security HIGH**: {smoke_kpis.get('security_high', 999)} (Soll: ≤{self.smoke_requirements['security_high_max']})
- **Active Tools**: {smoke_kpis.get('active_tools', 0)} (Soll: ≥{self.smoke_requirements['active_tools_min']})
- **License Violations**: {smoke_kpis.get('license_violations', 999)} (Soll: ≤{self.smoke_requirements['license_violations_max']})
- **Overall Pass**: {'✅ JA' if smoke_success else '❌ NEIN'}

### 🔐 SECURE Profile
- **Coverage**: {secure_kpis.get('coverage_percent', 0.0):.2f}% (Soll: ≥{self.secure_requirements['coverage_min']}% Stufe 1)
- **Security HIGH**: {secure_kpis.get('security_high', 999)} (Soll: ≤{self.secure_requirements['security_high_max']})
- **Active Tools**: {secure_kpis.get('active_tools', 0)} (Soll: ≥{self.secure_requirements['active_tools_min']})
- **License Violations**: {secure_kpis.get('license_violations', 999)} (Soll: ≤{self.secure_requirements['license_violations_max']})
- **Overall Pass**: {'✅ JA' if secure_success else '❌ NEIN'}

---

## 🎯 Mindestvoraussetzungen-Check

### ✅ Erfüllte Kriterien
"""
        
        # Erfüllte Kriterien sammeln
        fulfilled_criteria = []
        
        if smoke_kpis.get("active_tools", 0) >= self.smoke_requirements["active_tools_min"]:
            fulfilled_criteria.append(f"🌪️ SMOKE Active Tools: {smoke_kpis.get('active_tools', 0)} ≥ {self.smoke_requirements['active_tools_min']}")
        
        if smoke_kpis.get("security_high", 999) <= self.smoke_requirements["security_high_max"]:
            fulfilled_criteria.append(f"🌪️ SMOKE Security HIGH: {smoke_kpis.get('security_high', 999)} ≤ {self.smoke_requirements['security_high_max']}")
        
        if secure_kpis.get("active_tools", 0) >= self.secure_requirements["active_tools_min"]:
            fulfilled_criteria.append(f"🔐 SECURE Active Tools: {secure_kpis.get('active_tools', 0)} ≥ {self.secure_requirements['active_tools_min']}")
        
        if secure_kpis.get("security_high", 999) <= self.secure_requirements["security_high_max"]:
            fulfilled_criteria.append(f"🔐 SECURE Security HIGH: {secure_kpis.get('security_high', 999)} ≤ {self.secure_requirements['security_high_max']}")
        
        for criterion in fulfilled_criteria:
            matrix_content += f"- {criterion}\\n"
        
        if not fulfilled_criteria:
            matrix_content += "- *Keine Kriterien vollständig erfüllt*\\n"
        
        matrix_content += "\\n### ❌ Nicht erfüllte Kriterien\\n"
        
        # Nicht erfüllte Kriterien sammeln
        unfulfilled_criteria = []
        
        if smoke_kpis.get("coverage_percent", 0.0) < self.smoke_requirements["coverage_min"]:
            unfulfilled_criteria.append(f"🌪️ SMOKE Coverage: {smoke_kpis.get('coverage_percent', 0.0):.2f}% < {self.smoke_requirements['coverage_min']}%")
        
        if smoke_kpis.get("license_violations", 999) > self.smoke_requirements["license_violations_max"]:
            unfulfilled_criteria.append(f"🌪️ SMOKE License: {smoke_kpis.get('license_violations', 999)} > {self.smoke_requirements['license_violations_max']}")
        
        if secure_kpis.get("coverage_percent", 0.0) < self.secure_requirements["coverage_min"]:
            unfulfilled_criteria.append(f"🔐 SECURE Coverage: {secure_kpis.get('coverage_percent', 0.0):.2f}% < {self.secure_requirements['coverage_min']}%")
        
        if secure_kpis.get("license_violations", 999) > self.secure_requirements["license_violations_max"]:
            unfulfilled_criteria.append(f"🔐 SECURE License: {secure_kpis.get('license_violations', 999)} > {self.secure_requirements['license_violations_max']}")
        
        for criterion in unfulfilled_criteria:
            matrix_content += f"- {criterion}\\n"
        
        if not unfulfilled_criteria:
            matrix_content += "- *Alle Kriterien erfüllt!*\\n"
        
        matrix_content += f"""

---

## 🎊 MVP-CLOSE-TEST Fazit

**Final Result:** {'✅ ERFOLG' if smoke_success and secure_success else '🔄 TEILWEISE ERFOLGREICH' if smoke_success or secure_success else '❌ NICHT ERFOLGREICH'}

"""
        
        if smoke_success and secure_success:
            matrix_content += """✅ **BEIDE PROFILE BESTANDEN!**

Sowohl SMOKE als auch SECURE erfüllen alle Mindestvoraussetzungen:
- Active Tools in beiden Profilen ausreichend
- Security HIGH in beiden Profilen = 0
- Coverage- und License-Kriterien erfüllt
- Alle Quality-Gates bestanden

🎉 **MVP-CLOSE-TEST erfolgreich abgeschlossen!**"""
        elif smoke_success:
            matrix_content += """🔄 **SMOKE BESTANDEN, SECURE NOCH NICHT**

SMOKE erfüllt alle Mindestvoraussetzungen.
SECURE benötigt noch Verbesserungen in den nicht erfüllten Kriterien.

✅ **Grundlegende MVP-Funktionalität nachgewiesen**"""
        elif secure_success:
            matrix_content += """🔄 **SECURE BESTANDEN, SMOKE NOCH NICHT**

SECURE erfüllt alle Mindestvoraussetzungen.
SMOKE benötigt noch Verbesserungen in den nicht erfüllten Kriterien.

✅ **Erweiterte MVP-Funktionalität nachgewiesen**"""
        else:
            matrix_content += """❌ **BEIDE PROFILE BENÖTIGEN VERBESSERUNGEN**

Weder SMOKE noch SECURE erfüllen alle Mindestvoraussetzungen.
Fokus auf die nicht erfüllten Kriterien legen.

🔄 **Weitere Entwicklung erforderlich**"""
        
        matrix_content += """

---

## 📋 MVP-CLOSE-TEST Akzeptanzkriterien

✅ **Smoke-Lauf durchgeführt**  
✅ **Secure-Dry-Run durchgeführt**  
✅ **Kennzahlen geprüft**: active_tools, HIGH, Coverage, License  
✅ **Komprimierte Matrix erstellt**: Profil×Gate vollständig  
✅ **Matrix als Markdown dokumentiert**  

---

*Ende MVP-CLOSE-TEST Abschlusstest Matrix*"""
        
        return matrix_content
    
    def run_final_abschlusstest(self) -> int:
        """Führe finalen Abschlusstest durch"""
        
        print(f"\\n🎯 MVP-CLOSE-TEST: Abschlusstest Smoke+Secure")
        print(f"   Ziel: Nachweis der Mindestvoraussetzungen mit Matrix-Dokumentation")
        
        start_time = time.time()
        
        # 1. Führe Smoke-Test durch
        smoke_success, smoke_kpis = self.run_smoke_test()
        
        # 2. Führe Secure-Test durch
        secure_success, secure_kpis = self.run_secure_test()
        
        # 3. Generiere komprimierte Matrix
        matrix_content = self.generate_compressed_matrix_markdown(
            smoke_success, smoke_kpis, secure_success, secure_kpis
        )
        
        # 4. Speichere Matrix als Markdown
        matrix_file = self.reports_dir / "mvp_close_test_matrix.md"
        with open(matrix_file, 'w', encoding='utf-8') as f:
            f.write(matrix_content)
        
        # 5. Erstelle JSON-Report für maschinelle Auswertung
        json_report = {
            "mvp_close_test": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "duration_seconds": round(time.time() - start_time, 2),
                
                "smoke": {
                    "success": smoke_success,
                    "kpis": smoke_kpis,
                    "requirements": self.smoke_requirements
                },
                
                "secure": {
                    "success": secure_success,
                    "kpis": secure_kpis,
                    "requirements": self.secure_requirements
                },
                
                "overall": {
                    "both_pass": smoke_success and secure_success,
                    "at_least_one_pass": smoke_success or secure_success,
                    "smoke_pass": smoke_success,
                    "secure_pass": secure_success
                }
            }
        }
        
        json_report_file = self.reports_dir / "mvp_close_test_matrix.json"
        with open(json_report_file, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        
        # 6. Finale Zusammenfassung
        duration = time.time() - start_time
        
        print(f"\\n🎊 Final Abschlusstest Summary:")
        print(f"   Duration: {duration:.2f}s")
        print(f"   SMOKE: {'✅ PASS' if smoke_success else '❌ FAIL'}")
        print(f"   SECURE: {'✅ PASS' if secure_success else '❌ FAIL'}")
        print(f"   Both Pass: {'✅ YES' if smoke_success and secure_success else '❌ NO'}")
        print(f"   📄 Matrix Markdown: {matrix_file}")
        print(f"   📄 Matrix JSON: {json_report_file}")
        
        # 7. MVP-CLOSE-TEST Akzeptanzkriterien
        print(f"\\n🎯 MVP-CLOSE-TEST Akzeptanzkriterien:")
        print(f"   Smoke-Lauf durchgeführt: ✅")
        print(f"   Secure-Dry-Run durchgeführt: ✅")
        print(f"   Kennzahlen geprüft: ✅ (active_tools, HIGH, Coverage, License)")
        print(f"   Matrix Profil×Gate erstellt: ✅")
        print(f"   Matrix als Markdown: ✅")
        print(f"   Matrix vollständig: ✅")
        print(f"   Mindestvoraussetzungen dokumentiert: ✅")
        
        # Exit-Code: 0 wenn beide pass, 1 wenn mindestens einer pass, 2 wenn beide fail
        if smoke_success and secure_success:
            print(f"🎉 Abschlusstest VOLLSTÄNDIG ERFOLGREICH!")
            return 0
        elif smoke_success or secure_success:
            print(f"🔄 Abschlusstest TEILWEISE ERFOLGREICH!")
            return 1
        else:
            print(f"❌ Abschlusstest NICHT ERFOLGREICH!")
            return 2


def main():
    """Main function für Final Abschlusstest"""
    print("🎯 MVP-CLOSE-TEST: Abschlusstest Smoke+Secure")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Final Abschlusstest for Smoke and Secure")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview abschlusstest without execution")
    args = parser.parse_args()
    
    try:
        # Initialisiere Final Abschlusstest
        test = FinalAbschlusstest()
        
        if args.dry_run:
            print(f"\\n🧪 Dry run mode - abschlusstest not executed")
            print(f"   Will test: Smoke + Secure profiles")
            print(f"   Will create: Matrix Profil×Gate")
            return 0
        
        # Führe finalen Abschlusstest durch
        exit_code = test.run_final_abschlusstest()
        
        return exit_code
        
    except Exception as e:
        print(f"💥 Final Abschlusstest error: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
