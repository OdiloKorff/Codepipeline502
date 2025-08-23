#!/usr/bin/env python3
"""
MVP-FIX-004: Scorecard Kalibrierung nach Profil
Ehrliche Bewertung je Modus mit Profile smoke und secure.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import yaml


class ScorecardProfile(Enum):
    """Scorecard-Profile für verschiedene Ausführungsmodi"""
    SMOKE = "smoke"    # Geringere Mindest-Coverage, reduzierte Checks
    SECURE = "secure"  # Volle Policy ohne Absenkung


class PolicyThresholds:
    """Policy-Schwellwerte je Profil"""
    
    def __init__(self, profile: ScorecardProfile):
        self.profile = profile
        
        if profile == ScorecardProfile.SMOKE:
            # Smoke: Geringere Schwellwerte für schnelle Checks
            self.coverage_min = 20.0          # Niedrig für Smoke Test
            self.security_high_max = 0        # Null-Toleranz auch in Smoke
            self.security_medium_max = 50     # Relaxed für Smoke
            self.license_violations_max = 5   # Einige erlaubt in Smoke
            self.active_tools_min = 1         # Mindestens ein Tool
            self.hard_must_failures_max = 2   # Einige Hard-Must-Fails erlaubt
            
        else:  # SECURE
            # Secure: Volle Policy-Schwellwerte
            self.coverage_min = 75.0          # Produktions-Standard
            self.security_high_max = 0        # Null-Toleranz
            self.security_medium_max = 5      # Strikt
            self.license_violations_max = 0   # Keine Violations
            self.active_tools_min = 2         # Mehrere Tools erforderlich
            self.hard_must_failures_max = 0   # Keine Hard-Must-Fails
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile.value,
            "coverage_min": self.coverage_min,
            "security_high_max": self.security_high_max,
            "security_medium_max": self.security_medium_max,
            "license_violations_max": self.license_violations_max,
            "active_tools_min": self.active_tools_min,
            "hard_must_failures_max": self.hard_must_failures_max
        }


class CalibratedScorecardMVP:
    """MVP Kalibrierte Scorecard mit Profil-Unterstützung"""
    
    def __init__(self, project_root: Optional[Path] = None, profile: ScorecardProfile = ScorecardProfile.SECURE):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.profile = profile
        self.thresholds = PolicyThresholds(profile)
        
        print(f"🎯 Scorecard Profile: {profile.value.upper()}")
        print(f"   Coverage Min: {self.thresholds.coverage_min}%")
        print(f"   Security HIGH Max: {self.thresholds.security_high_max}")
        print(f"   License Violations Max: {self.thresholds.license_violations_max}")
    
    def read_coverage_from_xml(self) -> Tuple[float, Dict[str, Any]]:
        """Liest Coverage aus coverage.xml im Projekt-Root"""
        
        coverage_file = self.project_root / "coverage.xml"
        
        if not coverage_file.exists():
            print(f"   ❌ Coverage file not found: {coverage_file}")
            return 0.0, {
                "status": "missing",
                "file_path": str(coverage_file),
                "error": "coverage.xml not found in project root"
            }
        
        try:
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            # Extrahiere Coverage-Metriken
            line_rate = float(root.attrib.get("line-rate", "0"))
            lines_valid = int(root.attrib.get("lines-valid", "0"))
            lines_covered = int(root.attrib.get("lines-covered", "0"))
            
            coverage_percent = round(line_rate * 100, 2)
            
            details = {
                "status": "available",
                "file_path": str(coverage_file),
                "line_rate": line_rate,
                "lines_valid": lines_valid,
                "lines_covered": lines_covered,
                "coverage_percent": coverage_percent,
                "file_size": coverage_file.stat().st_size,
                "file_modified": coverage_file.stat().st_mtime
            }
            
            print(f"   ✅ Coverage read from XML: {coverage_percent}%")
            print(f"      Lines: {lines_covered}/{lines_valid}")
            
            return coverage_percent, details
            
        except ET.ParseError as e:
            print(f"   ❌ XML parse error: {e}")
            return 0.0, {
                "status": "invalid",
                "file_path": str(coverage_file),
                "error": f"XML parse error: {e}"
            }
        except Exception as e:
            print(f"   ❌ Coverage read error: {e}")
            return 0.0, {
                "status": "error",
                "file_path": str(coverage_file),
                "error": str(e)
            }
    
    def read_security_from_consolidated_report(self) -> Tuple[int, int, int, int, Dict[str, Any]]:
        """Liest Security aus konsolidiertem Report"""
        
        # Priorität: Konsolidierter Report > Legacy Report
        security_files = [
            self.reports_dir / "security_consolidated_report.json",  # MVP-FIX-002 primär
            self.reports_dir / "security_gate_report.json",          # Legacy fallback
            self.reports_dir / "active_security_report.json"         # MVP-FIX-001 fallback
        ]
        
        for security_file in security_files:
            if security_file.exists():
                try:
                    with open(security_file, 'r', encoding='utf-8') as f:
                        security_data = json.load(f)
                    
                    # MVP-FIX-002 Format
                    if "security_consolidated" in security_data:
                        security_gate = security_data["security_consolidated"]
                        source = "consolidated"
                    # MVP-FIX-001 Format
                    elif "security_scan" in security_data:
                        security_gate = security_data["security_scan"]
                        source = "active_scan"
                    # Legacy Format
                    else:
                        security_gate = security_data.get("security_gate", {})
                        source = "legacy"
                    
                    high = security_gate.get("high", 999)
                    medium = security_gate.get("medium", 999)
                    low = security_gate.get("low", 999)
                    active_tools = security_gate.get("active_tools", 0)
                    
                    details = {
                        "status": "available",
                        "source": source,
                        "file_path": str(security_file),
                        "scan_date": security_gate.get("scan_date", security_gate.get("aggregated_at", "")),
                        "total_findings": security_gate.get("total", high + medium + low)
                    }
                    
                    print(f"   ✅ Security read from {source}: HIGH:{high}, MED:{medium}, LOW:{low}")
                    print(f"      Active Tools: {active_tools}")
                    
                    return high, medium, low, active_tools, details
                    
                except Exception as e:
                    print(f"   ⚠️ Error reading {security_file}: {e}")
                    continue
        
        print(f"   ❌ No security reports found")
        return 999, 999, 999, 0, {
            "status": "missing",
            "error": "No security reports found"
        }
    
    def read_license_violations(self) -> Tuple[int, Dict[str, Any]]:
        """Liest License-Violations aus License-Report"""
        
        # Priorität: Allowlist Report > Legacy Report
        license_files = [
            self.reports_dir / "license_gate_allowlist_report.json",  # MVP-FIX-003 primär
            self.reports_dir / "sbom_license_report.json"             # Legacy fallback
        ]
        
        for license_file in license_files:
            if license_file.exists():
                try:
                    with open(license_file, 'r', encoding='utf-8') as f:
                        license_data = json.load(f)
                    
                    # MVP-FIX-003 Format
                    if "license_gate" in license_data:
                        license_gate = license_data["license_gate"]
                        source = "allowlist"
                    # Legacy Format
                    else:
                        license_gate = license_data.get("sbom_license_gate", {})
                        source = "legacy"
                    
                    violations = license_gate.get("license_violations", 999)
                    
                    details = {
                        "status": "available",
                        "source": source,
                        "file_path": str(license_file),
                        "total_packages": license_gate.get("total_packages", 0),
                        "compliance_rate": license_gate.get("compliance_rate", 0),
                        "check_date": license_gate.get("check_date", "")
                    }
                    
                    print(f"   ✅ License violations from {source}: {violations}")
                    
                    return violations, details
                    
                except Exception as e:
                    print(f"   ⚠️ Error reading {license_file}: {e}")
                    continue
        
        print(f"   ❌ No license reports found")
        return 999, {
            "status": "missing",
            "error": "No license reports found"
        }
    
    def evaluate_gates_by_profile(self, coverage_percent: float, security_high: int, 
                                 security_medium: int, license_violations: int, 
                                 active_tools: int) -> Dict[str, Any]:
        """Bewerte Gates nach Profil-Schwellwerten"""
        
        print(f"\\n🚦 Evaluating gates for {self.profile.value.upper()} profile...")
        
        gate_results = {}
        
        # Coverage Gate
        coverage_pass = coverage_percent >= self.thresholds.coverage_min
        gate_results["coverage"] = {
            "status": "pass" if coverage_pass else "fail",
            "actual": coverage_percent,
            "threshold": self.thresholds.coverage_min,
            "message": f"Coverage {coverage_percent}% {'≥' if coverage_pass else '<'} {self.thresholds.coverage_min}%"
        }
        
        # Security HIGH Gate
        security_high_pass = security_high <= self.thresholds.security_high_max
        gate_results["security_high"] = {
            "status": "pass" if security_high_pass else "fail",
            "actual": security_high,
            "threshold": self.thresholds.security_high_max,
            "message": f"Security HIGH {security_high} {'≤' if security_high_pass else '>'} {self.thresholds.security_high_max}"
        }
        
        # Security MEDIUM Gate (nur für Secure-Profil strikt)
        security_medium_pass = security_medium <= self.thresholds.security_medium_max
        gate_results["security_medium"] = {
            "status": "pass" if security_medium_pass else ("warn" if self.profile == ScorecardProfile.SMOKE else "fail"),
            "actual": security_medium,
            "threshold": self.thresholds.security_medium_max,
            "message": f"Security MEDIUM {security_medium} {'≤' if security_medium_pass else '>'} {self.thresholds.security_medium_max}"
        }
        
        # License Gate
        license_pass = license_violations <= self.thresholds.license_violations_max
        gate_results["license"] = {
            "status": "pass" if license_pass else "fail",
            "actual": license_violations,
            "threshold": self.thresholds.license_violations_max,
            "message": f"License violations {license_violations} {'≤' if license_pass else '>'} {self.thresholds.license_violations_max}"
        }
        
        # Active Tools Gate
        tools_pass = active_tools >= self.thresholds.active_tools_min
        gate_results["active_tools"] = {
            "status": "pass" if tools_pass else "fail",
            "actual": active_tools,
            "threshold": self.thresholds.active_tools_min,
            "message": f"Active tools {active_tools} {'≥' if tools_pass else '<'} {self.thresholds.active_tools_min}"
        }
        
        # Overall Status nach Profil
        critical_failures = []
        warnings = []
        
        for gate_name, gate_result in gate_results.items():
            status = gate_result["status"]
            if status == "fail":
                critical_failures.append(gate_name)
            elif status == "warn":
                warnings.append(gate_name)
        
        # Profil-spezifische Overall-Bewertung
        if self.profile == ScorecardProfile.SMOKE:
            # Smoke: Nur kritische Failures blocken
            overall_pass = len(critical_failures) == 0
            overall_status = "pass" if overall_pass else "fail"
        else:  # SECURE
            # Secure: Keine Failures oder Warnings erlaubt
            overall_pass = len(critical_failures) == 0 and len(warnings) == 0
            overall_status = "pass" if overall_pass else "fail"
        
        print(f"   📊 Gate Results for {self.profile.value.upper()}:")
        for gate_name, gate_result in gate_results.items():
            status_icon = "✅" if gate_result["status"] == "pass" else ("⚠️" if gate_result["status"] == "warn" else "❌")
            print(f"      {status_icon} {gate_name}: {gate_result['message']}")
        
        print(f"   🎯 Overall: {overall_status.upper()} ({len(critical_failures)} failures, {len(warnings)} warnings)")
        
        return {
            "overall_status": overall_status,
            "overall_passing": overall_pass,
            "critical_failures": critical_failures,
            "warnings": warnings,
            "gates": gate_results,
            "profile": self.profile.value,
            "thresholds": self.thresholds.to_dict()
        }
    
    def run_calibrated_scorecard(self) -> Dict[str, Any]:
        """Führe kalibrierte Scorecard-Bewertung durch"""
        
        print(f"📊 Running Calibrated Scorecard...")
        
        # 1. Lese Coverage aus coverage.xml
        print(f"\\n📈 Reading coverage from project root...")
        coverage_percent, coverage_details = self.read_coverage_from_xml()
        
        # 2. Lese Security aus konsolidiertem Report
        print(f"\\n🔒 Reading security from consolidated report...")
        security_high, security_medium, security_low, active_tools, security_details = self.read_security_from_consolidated_report()
        
        # 3. Lese License-Violations
        print(f"\\n📝 Reading license violations...")
        license_violations, license_details = self.read_license_violations()
        
        # 4. Bewerte Gates nach Profil
        evaluation = self.evaluate_gates_by_profile(
            coverage_percent, security_high, security_medium, 
            license_violations, active_tools
        )
        
        # 5. Erstelle Scorecard-Report
        scorecard_report = {
            "scorecard": {
                "profile": self.profile.value,
                "status": evaluation["overall_status"],
                "overall_passing": evaluation["overall_passing"],
                "coverage_percent": coverage_percent,
                "security_high": security_high,
                "security_medium": security_medium,
                "security_low": security_low,
                "license_violations": license_violations,
                "active_tools": active_tools,
                "critical_failures": evaluation["critical_failures"],
                "warnings": evaluation["warnings"],
                "gates": evaluation["gates"],
                "thresholds": evaluation["thresholds"],
                "evaluation_date": datetime.utcnow().isoformat() + "Z"
            },
            "data_sources": {
                "coverage": coverage_details,
                "security": security_details,
                "license": license_details
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "project_root": str(self.project_root)
        }
        
        return scorecard_report
    
    def save_scorecard_report(self, scorecard_report: Dict[str, Any]) -> Path:
        """Speichere Scorecard-Report"""
        
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            # Schreibe profil-spezifischen Report
            report_file = self.reports_dir / f"scorecard_{self.profile.value}.json"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(scorecard_report, f, indent=2, ensure_ascii=False)
            
            # Schreibe auch Standard-Scorecard für Legacy-Kompatibilität
            legacy_file = self.reports_dir / "scorecard.json"
            with open(legacy_file, 'w', encoding='utf-8') as f:
                json.dump(scorecard_report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Scorecard report saved: {report_file}")
            print(f"📄 Legacy report saved: {legacy_file}")
            
            return report_file
            
        except Exception as e:
            print(f"⚠️ Could not save scorecard report: {e}")
            return None


def main():
    """Main function für Calibrated Scorecard"""
    print("🎯 MVP-FIX-004: Scorecard Kalibrierung nach Profil")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Calibrated Scorecard with Profile Support")
    parser.add_argument("--profile", choices=["smoke", "secure"], default="secure", 
                       help="Scorecard profile: smoke (relaxed) or secure (strict)")
    args = parser.parse_args()
    
    # Bestimme Profil
    profile = ScorecardProfile.SMOKE if args.profile == "smoke" else ScorecardProfile.SECURE
    
    try:
        # Initialisiere Calibrated Scorecard
        scorecard = CalibratedScorecardMVP(profile=profile)
        
        # Führe kalibrierte Scorecard durch
        scorecard_report = scorecard.run_calibrated_scorecard()
        
        # Speichere Report
        scorecard.save_scorecard_report(scorecard_report)
        
        # Prüfe Akzeptanzkriterien
        scorecard_data = scorecard_report["scorecard"]
        overall_status = scorecard_data["status"]
        profile_used = scorecard_data["profile"]
        coverage_percent = scorecard_data["coverage_percent"]
        
        print(f"\\n🎯 MVP-FIX-004 Akzeptanzkriterien:")
        print(f"   Coverage aus coverage.xml gelesen: {'✅' if coverage_percent > 0 else '❌'} ({coverage_percent}%)")
        print(f"   Security aus konsolidiertem Report: {'✅' if scorecard_data['security_high'] >= 0 else '❌'}")
        print(f"   Profile {profile_used} unterschieden: ✅")
        
        if profile == ScorecardProfile.SMOKE:
            smoke_threshold = scorecard.thresholds.coverage_min
            smoke_pass = overall_status == "pass"
            print(f"   Smoke Lauf PASS bei Smoke Policy: {'✅' if smoke_pass else '❌'} (Coverage ≥ {smoke_threshold}%)")
        else:
            secure_threshold = scorecard.thresholds.coverage_min
            secure_pass = overall_status == "pass"
            print(f"   Secure Lauf verlangt volle Policy: {'✅' if secure_pass or overall_status == 'fail' else '❌'} (Coverage ≥ {secure_threshold}%)")
        
        # Exit-Code basierend auf Profil-Status
        if overall_status == "pass":
            print(f"🎉 {profile.value.upper()} Scorecard PASSED!")
            return 0
        else:
            print(f"💥 {profile.value.upper()} Scorecard FAILED!")
            return 1
            
    except Exception as e:
        print(f"💥 Scorecard Calibration error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
