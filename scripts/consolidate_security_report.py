#!/usr/bin/env python3
"""
SEC-201: Security-Report Konsolidierung
Erstellt konsolidierten Security-Report aus Bandit-Rohreport.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


def load_bandit_report(bandit_file: Path) -> Dict[str, Any]:
    """Lade Bandit-Rohreport"""
    if not bandit_file.exists():
        raise FileNotFoundError(f"Bandit report not found: {bandit_file}")
    
    with open(bandit_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_bandit_findings(bandit_data: Dict[str, Any]) -> Dict[str, int]:
    """Analysiere Bandit-Findings und zähle nach Severity"""
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    
    for result in bandit_data.get("results", []):
        severity = result.get("issue_severity", "").lower()
        if severity in severity_counts:
            severity_counts[severity] += 1
    
    return severity_counts


def get_high_findings_details(bandit_data: Dict[str, Any]) -> list:
    """Extrahiere Details zu HIGH-Findings"""
    high_findings = []
    
    for result in bandit_data.get("results", []):
        if result.get("issue_severity", "").lower() == "high":
            high_findings.append({
                "rule_id": result.get("test_id", "unknown"),
                "filename": result.get("filename", "unknown"),
                "line_number": result.get("line_number", 0),
                "issue_text": result.get("issue_text", "")
            })
    
    return high_findings


def create_consolidated_security_report(
    bandit_file: Path, 
    output_file: Path,
    enforce_zero_high: bool = True
) -> Dict[str, Any]:
    """Erstelle konsolidierten Security-Report"""
    
    try:
        # Lade Bandit-Report
        bandit_data = load_bandit_report(bandit_file)
        
        # Analysiere Findings
        severity_counts = analyze_bandit_findings(bandit_data)
        high_findings = get_high_findings_details(bandit_data)
        
        # Berechne Totals
        total_findings = sum(severity_counts.values())
        
        # Bestimme Status
        status = "ok" if severity_counts["high"] == 0 else "fail"
        
        # Erstelle konsolidierten Report
        consolidated_report = {
            "bandit": {
                "status": status,
                "high": severity_counts["high"],
                "medium": severity_counts["medium"], 
                "low": severity_counts["low"],
                "total": total_findings,
                "active_tools": 1,  # Bandit ist aktiv
                "scan_date": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        # Füge High-Finding-Details hinzu falls vorhanden
        if high_findings:
            consolidated_report["bandit"]["high_findings"] = high_findings
        
        # Schreibe konsolidierten Report
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(consolidated_report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Konsolidierter Security-Report erstellt: {output_file}")
        print(f"📊 Status: {status}")
        print(f"📈 Findings: HIGH={severity_counts['high']}, MEDIUM={severity_counts['medium']}, LOW={severity_counts['low']}")
        print(f"🔧 Active Tools: 1 (Bandit)")
        
        # Erzwinge Zero-High falls aktiviert
        if enforce_zero_high and severity_counts["high"] > 0:
            print(f"\n❌ SECURITY GATE FAILURE: {severity_counts['high']} HIGH findings detected!")
            print("📋 HIGH findings that must be fixed:")
            for i, finding in enumerate(high_findings, 1):
                print(f"  {i}. {finding['rule_id']} in {finding['filename']}:{finding['line_number']}")
                print(f"     {finding['issue_text']}")
            
            raise SystemExit(1)
        
        return consolidated_report
        
    except Exception as e:
        print(f"❌ Error creating consolidated security report: {e}")
        raise


def main():
    """Main function"""
    project_root = Path(__file__).parent.parent
    bandit_file = project_root / "reports" / "bandit_raw_scan.json"
    output_file = project_root / "reports" / "security_report.json"
    
    try:
        report = create_consolidated_security_report(
            bandit_file=bandit_file,
            output_file=output_file,
            enforce_zero_high=True
        )
        
        print(f"\n🎯 Security Gate Status: {'PASS' if report['bandit']['status'] == 'ok' else 'FAIL'}")
        return 0
        
    except SystemExit as e:
        return e.code
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
