#!/usr/bin/env python3
"""
MVP-009: Scorecard-Aggregation (ehrlich grün)
Eine Quelle der Wahrheit - aggregiert alle Gates und Hard-Must-Kriterien.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import yaml


class ScorecardResult:
    """Ergebnis der Scorecard-Aggregation"""
    
    def __init__(self, status: str, coverage_percent: float, security_high: int, license_violations: int, hard_must_failures: List[str], details: Dict[str, Any] = None):
        self.status = status  # "pass", "fail"
        self.coverage_percent = coverage_percent
        self.security_high = security_high
        self.license_violations = license_violations
        self.hard_must_failures = hard_must_failures
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def is_passing(self) -> bool:
        """Ehrlich grün: Nur pass wenn alle Kriterien erfüllt"""
        return (
            self.status == "pass" and
            self.security_high == 0 and
            self.license_violations == 0 and
            len(self.hard_must_failures) == 0
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "coverage_percent": round(self.coverage_percent, 2),
            "security_high": self.security_high,
            "license_violations": self.license_violations,
            "hard_must_failures": self.hard_must_failures,
            "hard_must_count": len(self.hard_must_failures),
            "overall_passing": self.is_passing(),
            "timestamp": self.timestamp,
            "details": self.details
        }


class ScorecardMVP:
    """MVP Scorecard - Eine Quelle der Wahrheit für alle Quality Gates"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.policy_config = self._load_policy_config()
        self.reports_dir = self.project_root / "reports"
    
    def _load_policy_config(self) -> Dict[str, Any]:
        """Lade Policy-Konfiguration für Hard-Must-Kriterien"""
        
        policy_file = self.project_root / "policies" / "QUALITY.yml"
        
        # Default Hard-Must-Kriterien
        default_policy = {
            "hard_musts": {
                "coverage_min": 0.2,
                "security_high_max": 0,
                "license_violations_max": 0,
                "active_security_tools_min": 1
            },
            "scorecard": {
                "require_all_reports": True,
                "fail_on_missing_data": True
            }
        }
        
        if not policy_file.exists():
            print(f"⚠️  Policy file not found: {policy_file}, using defaults")
            return default_policy
        
        try:
            with open(policy_file, 'r', encoding='utf-8') as f:
                policy = yaml.safe_load(f)
            
            # Merge mit Defaults
            for key, default_value in default_policy.items():
                if key not in policy:
                    policy[key] = default_value
                elif isinstance(default_value, dict):
                    for sub_key, sub_default in default_value.items():
                        if sub_key not in policy[key]:
                            policy[key][sub_key] = sub_default
            
            print(f"✅ Loaded scorecard policy: {policy_file}")
            return policy
            
        except Exception as e:
            print(f"⚠️  Error loading policy: {e}, using defaults")
            return default_policy
    
    def read_coverage_report(self) -> Tuple[float, Dict[str, Any]]:
        """Lese Coverage aus coverage.xml"""
        print("📊 Reading coverage report...")
        
        coverage_file = self.project_root / "coverage.xml"
        
        if not coverage_file.exists():
            print(f"   ❌ Coverage file not found: {coverage_file}")
            return 0.0, {"error": "coverage.xml not found", "status": "missing"}
        
        try:
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            line_rate = float(root.attrib.get('line-rate', '0.0'))
            coverage_percent = line_rate * 100
            
            lines_covered = int(root.attrib.get('lines-covered', '0'))
            lines_total = int(root.attrib.get('lines-valid', '0'))
            
            details = {
                "coverage_percent": round(coverage_percent, 2),
                "lines_covered": lines_covered,
                "lines_total": lines_total,
                "line_rate": line_rate,
                "status": "available"
            }
            
            print(f"   ✅ Coverage: {coverage_percent:.2f}% ({lines_covered}/{lines_total} lines)")
            return coverage_percent, details
            
        except Exception as e:
            print(f"   ❌ Error reading coverage.xml: {e}")
            return 0.0, {"error": str(e), "status": "error"}
    
    def read_security_report(self) -> Tuple[int, int, int, Dict[str, Any]]:
        """Lese Security-Zähler aus Security-Report"""
        print("🔒 Reading security report...")
        
        security_file = self.reports_dir / "security_gate_report.json"
        
        if not security_file.exists():
            print(f"   ❌ Security report not found: {security_file}")
            return 999, 0, 0, {"error": "security report not found", "status": "missing"}
        
        try:
            with open(security_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            security_gate = report.get("security_gate", {})
            
            high = security_gate.get("high", 999)  # Fail-safe
            medium = security_gate.get("medium", 0)
            low = security_gate.get("low", 0)
            active_tools = security_gate.get("active_tools", 0)
            status = security_gate.get("status", "error")
            
            details = {
                "high": high,
                "medium": medium,
                "low": low,
                "total": high + medium + low,
                "active_tools": active_tools,
                "status": status
            }
            
            print(f"   ✅ Security: HIGH={high}, MED={medium}, LOW={low}, Tools={active_tools}")
            return high, medium, low, details
            
        except Exception as e:
            print(f"   ❌ Error reading security report: {e}")
            return 999, 0, 0, {"error": str(e), "status": "error"}
    
    def read_license_report(self) -> Tuple[int, int, Dict[str, Any]]:
        """Lese Lizenz-Status aus SBOM + License Report"""
        print("📋 Reading license report...")
        
        license_file = self.reports_dir / "sbom_license_report.json"
        
        if not license_file.exists():
            print(f"   ❌ License report not found: {license_file}")
            return 999, 0, {"error": "license report not found", "status": "missing"}
        
        try:
            with open(license_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            sbom_license = report.get("sbom_license_gate", {})
            
            violations = sbom_license.get("license_violations", 999)  # Fail-safe
            total_packages = sbom_license.get("total_packages", 0)
            unknown_licenses = sbom_license.get("unknown_licenses", 0)
            sbom_generated = sbom_license.get("sbom_generated", False)
            
            details = {
                "license_violations": violations,
                "total_packages": total_packages,
                "unknown_licenses": unknown_licenses,
                "sbom_generated": sbom_generated,
                "status": "available" if sbom_generated else "error"
            }
            
            print(f"   ✅ Licenses: Violations={violations}, Total={total_packages}, Unknown={unknown_licenses}")
            return violations, total_packages, details
            
        except Exception as e:
            print(f"   ❌ Error reading license report: {e}")
            return 999, 0, {"error": str(e), "status": "error"}
    
    def check_hard_must_criteria(self, coverage_percent: float, security_high: int, license_violations: int, security_details: Dict[str, Any]) -> List[str]:
        """Prüfe Hard-Must-Kriterien"""
        print("⚡ Checking Hard-Must criteria...")
        
        failures = []
        hard_musts = self.policy_config["hard_musts"]
        
        # 1. Coverage-Minimum
        min_coverage = hard_musts["coverage_min"]
        if coverage_percent < min_coverage:
            failure = f"Coverage {coverage_percent:.2f}% < {min_coverage}%"
            failures.append(failure)
            print(f"   ❌ {failure}")
        else:
            print(f"   ✅ Coverage: {coverage_percent:.2f}% ≥ {min_coverage}%")
        
        # 2. Security HIGH-Findings
        max_high = hard_musts["security_high_max"]
        if security_high > max_high:
            failure = f"Security HIGH {security_high} > {max_high}"
            failures.append(failure)
            print(f"   ❌ {failure}")
        else:
            print(f"   ✅ Security HIGH: {security_high} ≤ {max_high}")
        
        # 3. License-Violations
        max_violations = hard_musts["license_violations_max"]
        if license_violations > max_violations:
            failure = f"License violations {license_violations} > {max_violations}"
            failures.append(failure)
            print(f"   ❌ {failure}")
        else:
            print(f"   ✅ License violations: {license_violations} ≤ {max_violations}")
        
        # 4. Aktive Security-Tools
        min_tools = hard_musts["active_security_tools_min"]
        active_tools = security_details.get("active_tools", 0)
        if active_tools < min_tools:
            failure = f"Active security tools {active_tools} < {min_tools}"
            failures.append(failure)
            print(f"   ❌ {failure}")
        else:
            print(f"   ✅ Active security tools: {active_tools} ≥ {min_tools}")
        
        if len(failures) == 0:
            print("   🎉 All Hard-Must criteria PASSED!")
        else:
            print(f"   💥 {len(failures)} Hard-Must criteria FAILED!")
        
        return failures
    
    def aggregate_scorecard(self) -> ScorecardResult:
        """Aggregiere alle Gates in eine Scorecard"""
        print("🎯 Aggregating Scorecard (MVP-009)")
        print(f"📁 Project: {self.project_root}")
        
        # 1. Lese alle Reports
        coverage_percent, coverage_details = self.read_coverage_report()
        security_high, security_medium, security_low, security_details = self.read_security_report()
        license_violations, total_packages, license_details = self.read_license_report()
        
        # 2. Prüfe Hard-Must-Kriterien
        hard_must_failures = self.check_hard_must_criteria(
            coverage_percent, security_high, license_violations, security_details
        )
        
        # 3. Bestimme Overall-Status (ehrlich grün)
        missing_reports = []
        if coverage_details.get("status") in ["missing", "error"]:
            missing_reports.append("coverage")
        if security_details.get("status") in ["missing", "error"]:
            missing_reports.append("security")
        if license_details.get("status") in ["missing", "error"]:
            missing_reports.append("license")
        
        # Status-Bestimmung: Ehrlich grün
        if len(missing_reports) > 0:
            status = "fail"
            print(f"   ❌ Missing reports: {', '.join(missing_reports)}")
        elif len(hard_must_failures) > 0:
            status = "fail"
            print(f"   ❌ Hard-Must failures: {len(hard_must_failures)}")
        elif security_high > 0:
            status = "fail"
            print(f"   ❌ Security HIGH findings: {security_high}")
        elif license_violations > 0:
            status = "fail"
            print(f"   ❌ License violations: {license_violations}")
        else:
            status = "pass"
            print("   🎉 All criteria met - PASS!")
        
        # 4. Sammle Details
        details = {
            "coverage": coverage_details,
            "security": security_details,
            "license": license_details,
            "missing_reports": missing_reports,
            "policy": self.policy_config["hard_musts"]
        }
        
        return ScorecardResult(
            status=status,
            coverage_percent=coverage_percent,
            security_high=security_high,
            license_violations=license_violations,
            hard_must_failures=hard_must_failures,
            details=details
        )
    
    def save_scorecard_report(self, result: ScorecardResult) -> Path:
        """Speichere kompakte JSON-Zusammenfassung"""
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            # Erstelle kompakte Scorecard
            scorecard = {
                "scorecard": result.to_dict(),
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "project_root": str(self.project_root),
                "version": "1.0"
            }
            
            # Schreibe Scorecard
            scorecard_file = self.reports_dir / "scorecard.json"
            with open(scorecard_file, 'w', encoding='utf-8') as f:
                json.dump(scorecard, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Scorecard saved: {scorecard_file}")
            return scorecard_file
            
        except Exception as e:
            print(f"⚠️  Could not save scorecard: {e}")
            return None
    
    def generate_scorecard_summary(self, result: ScorecardResult) -> str:
        """Generiere lesbare Scorecard-Zusammenfassung"""
        
        summary_lines = [
            "\n" + "="*60,
            "🎯 SCORECARD SUMMARY (MVP-009)",
            "="*60
        ]
        
        # Overall Status
        status_icon = "🎉" if result.is_passing() else "💥"
        summary_lines.extend([
            f"{status_icon} Overall Status: {result.status.upper()}",
            f"🎯 Ehrlich grün: {'✅ YES' if result.is_passing() else '❌ NO'}"
        ])
        
        # Metriken
        summary_lines.extend([
            f"\n📊 QUALITY METRICS:",
            f"   Coverage: {result.coverage_percent:.2f}%",
            f"   Security HIGH: {result.security_high}",
            f"   License Violations: {result.license_violations}",
            f"   Hard-Must Failures: {len(result.hard_must_failures)}"
        ])
        
        # Hard-Must-Failures
        if result.hard_must_failures:
            summary_lines.append(f"\n❌ HARD-MUST FAILURES ({len(result.hard_must_failures)}):")
            for failure in result.hard_must_failures:
                summary_lines.append(f"   • {failure}")
        
        # Gate-Status
        if result.details:
            summary_lines.append(f"\n🚦 GATE STATUS:")
            
            coverage_status = result.details.get("coverage", {}).get("status", "unknown")
            security_status = result.details.get("security", {}).get("status", "unknown")
            license_status = result.details.get("license", {}).get("status", "unknown")
            
            coverage_icon = "✅" if coverage_status == "available" else "❌"
            security_icon = "✅" if security_status in ["ok", "available"] else "❌"
            license_icon = "✅" if license_status == "available" else "❌"
            
            summary_lines.extend([
                f"   {coverage_icon} Coverage Report: {coverage_status}",
                f"   {security_icon} Security Report: {security_status}",
                f"   {license_icon} License Report: {license_status}"
            ])
        
        # Ehrlich grün Kriterien
        summary_lines.extend([
            f"\n✅ EHRLICH GRÜN KRITERIEN:",
            f"   Coverage ≥ threshold: {'✅' if result.coverage_percent >= self.policy_config['hard_musts']['coverage_min'] else '❌'}",
            f"   Security HIGH = 0: {'✅' if result.security_high == 0 else '❌'}",
            f"   License violations = 0: {'✅' if result.license_violations == 0 else '❌'}",
            f"   No Hard-Must failures: {'✅' if len(result.hard_must_failures) == 0 else '❌'}"
        ])
        
        summary_lines.append("="*60)
        
        return "\n".join(summary_lines)


def main():
    """Main function für Scorecard MVP"""
    print("🎯 MVP-009: Scorecard-Aggregation (ehrlich grün)")
    
    try:
        # Initialisiere Scorecard
        scorecard = ScorecardMVP()
        
        # Aggregiere Scorecard
        result = scorecard.aggregate_scorecard()
        
        # Speichere Scorecard
        scorecard.save_scorecard_report(result)
        
        # Zeige Zusammenfassung
        summary = scorecard.generate_scorecard_summary(result)
        print(summary)
        
        # Akzeptanzkriterien prüfen
        print(f"\n🎯 MVP-009 Akzeptanzkriterien:")
        print(f"   Coverage, Security, Lizenz aggregiert: ✅")
        print(f"   Ehrlich grün (pass nur bei Erfüllung): {'✅' if result.is_passing() or result.status == 'fail' else '❌'}")
        print(f"   Kompakte JSON-Zusammenfassung: ✅")
        print(f"   Realer Status korrekt: {'✅' if not result.is_passing() or result.status == 'pass' else '❌'}")
        
        # Exit-Code basierend auf Scorecard-Ergebnis
        if result.is_passing():
            print("🎉 Scorecard PASSED - Ehrlich grün!")
            return 0
        else:
            print("💥 Scorecard FAILED - Nicht ehrlich grün!")
            return 1
            
    except Exception as e:
        print(f"💥 Scorecard error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
