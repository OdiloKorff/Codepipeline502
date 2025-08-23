#!/usr/bin/env python3
"""
SCORE-401: Scorecard-Integration kalibrieren
Aktualisiert die Scorecard für korrekte Artefakt-Integration.
"""

import json
import sys
from pathlib import Path


def update_scorecard_for_consolidated_security():
    """Aktualisiert qa/scorecard.py für konsolidierten Security-Report"""
    
    scorecard_file = Path("qa/scorecard.py")
    if not scorecard_file.exists():
        print(f"❌ Scorecard file not found: {scorecard_file}")
        return False
    
    # Lese aktuelle Scorecard
    content = scorecard_file.read_text(encoding='utf-8')
    
    # Füge Funktion für konsolidierten Security-Report hinzu
    consolidated_security_function = '''
def consolidated_security_findings(path: Path) -> dict:
    """Read consolidated security report (replaces semgrep for now)"""
    if not path.exists():
        return {"high": 0, "med": 0, "low": 0, "active_tools": 0, "status": "missing"}
    try:
        data = json.loads(path.read_text())
        bandit_data = data.get("bandit", {})
        return {
            "high": bandit_data.get("high", 0),
            "med": bandit_data.get("medium", 0), 
            "low": bandit_data.get("low", 0),
            "active_tools": bandit_data.get("active_tools", 0),
            "status": bandit_data.get("status", "unknown")
        }
    except Exception:
        return {"high": 999, "med": 0, "low": 0, "active_tools": 0, "status": "error"}
'''
    
    # Suche nach der semgrep_findings Funktion und füge die neue Funktion davor ein
    if "def semgrep_findings" in content:
        content = content.replace(
            "def semgrep_findings",
            consolidated_security_function + "\n\ndef semgrep_findings"
        )
    else:
        # Füge vor main() ein
        content = content.replace(
            "def main():",
            consolidated_security_function + "\n\ndef main():"
        )
    
    # Aktualisiere main() Funktion für konsolidierten Security-Report
    old_sem_line = 'sem = semgrep_findings(Path("semgrep.json"))'
    new_sem_line = '''# Try consolidated security report first, fallback to semgrep
    consolidated_sec = consolidated_security_findings(Path("reports/security_report.json"))
    if consolidated_sec["status"] in ["ok", "fail"]:
        sem = consolidated_sec
        print(f"📊 Using consolidated security report: {consolidated_sec['active_tools']} active tools")
    else:
        sem = semgrep_findings(Path("semgrep.json"))
        print("📊 Using semgrep fallback")'''
    
    if old_sem_line in content:
        content = content.replace(old_sem_line, new_sem_line)
    
    # Aktualisiere Hard-Must für aktive Tools
    old_sast_check = 'if sem["high"] > hard["sast_high"]:'
    new_sast_check = '''if sem["high"] > hard["sast_high"]:
        hard_fail.append(f"SAST high={sem['high']} > {hard['sast_high']}")
    # Check for active security tools
    if sem.get("active_tools", 0) < 1:'''
    
    if old_sast_check in content and "active_tools" not in content:
        content = content.replace(
            old_sast_check + '\n        hard_fail.append(f"SAST high={sem[\'high\']} > {hard[\'sast_high\']}")',
            new_sast_check + '\n        hard_fail.append("No active security tools detected")'
        )
    
    # Schreibe aktualisierte Scorecard
    scorecard_file.write_text(content, encoding='utf-8')
    print(f"✅ Updated scorecard for consolidated security report")
    return True


def verify_scorecard_integration():
    """Verifiziert dass die Scorecard-Integration korrekt funktioniert"""
    print("🔍 Verifying scorecard integration...")
    
    # Prüfe Coverage-Datei
    coverage_file = Path("coverage.xml")
    if coverage_file.exists():
        print(f"✅ Coverage report found: {coverage_file}")
    else:
        print(f"❌ Coverage report missing: {coverage_file}")
        return False
    
    # Prüfe Security-Report
    security_file = Path("reports/security_report.json")
    if security_file.exists():
        print(f"✅ Security report found: {security_file}")
        
        # Validiere Security-Report Format
        try:
            with open(security_file, 'r') as f:
                security_data = json.load(f)
            
            bandit_data = security_data.get("bandit", {})
            required_fields = ["status", "high", "medium", "low", "active_tools"]
            
            for field in required_fields:
                if field not in bandit_data:
                    print(f"❌ Missing field in security report: {field}")
                    return False
            
            print(f"✅ Security report format valid")
            print(f"   Status: {bandit_data['status']}")
            print(f"   HIGH: {bandit_data['high']}")
            print(f"   Active Tools: {bandit_data['active_tools']}")
            
        except Exception as e:
            print(f"❌ Error reading security report: {e}")
            return False
    else:
        print(f"❌ Security report missing: {security_file}")
        return False
    
    # Prüfe QUALITY.yml
    quality_file = Path("policies/QUALITY.yml")
    if quality_file.exists():
        print(f"✅ Quality policy found: {quality_file}")
    else:
        print(f"❌ Quality policy missing: {quality_file}")
        return False
    
    print("✅ All scorecard integration checks passed")
    return True


def main():
    """Main function"""
    print("🎯 SCORE-401: Scorecard-Integration kalibrieren")
    
    # 1. Update Scorecard
    if not update_scorecard_for_consolidated_security():
        return 1
    
    # 2. Verify Integration
    if not verify_scorecard_integration():
        return 1
    
    print("✅ Scorecard integration calibrated successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
