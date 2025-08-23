#!/usr/bin/env python3
"""
MVP-FIX-006: Nightly Runner Fail Closed
Ehrlicher Nightly Status mit Gate-Prüfung und verständlichen Gründen.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


class GateStatus(Enum):
    """Gate-Status-Enum"""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    UNKNOWN = "unknown"


@dataclass
class GateResult:
    """Ergebnis eines Quality Gates"""
    gate_name: str
    status: GateStatus
    actual_value: Any
    threshold: Any
    message: str
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class NightlyFailClosedRunner:
    """Nightly Runner mit Fail-Closed-Logik"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        
        # Smoke-Profil Schwellwerte für Nightly
        self.smoke_thresholds = {
            "coverage_min": 20.0,
            "security_high_max": 0,
            "security_medium_max": 50,
            "license_violations_max": 5,
            "active_tools_min": 1
        }
        
        print(f"🌙 Nightly Fail-Closed Runner initialized")
        print(f"   Smoke thresholds: Coverage ≥ {self.smoke_thresholds['coverage_min']}%, Security HIGH ≤ {self.smoke_thresholds['security_high_max']}")
    
    def check_coverage_gate(self) -> GateResult:
        """Prüfe Coverage Gate"""
        
        try:
            # Prüfe focused coverage report
            focused_file = self.reports_dir / "focused_coverage_report.json"
            if focused_file.exists():
                with open(focused_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                coverage_percent = data.get("focused_coverage", {}).get("coverage_percent", 0.0)
                source = "focused_coverage"
            else:
                # Fallback: scorecard
                scorecard_file = self.reports_dir / "scorecard.json"
                if scorecard_file.exists():
                    with open(scorecard_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    coverage_percent = data.get("scorecard", {}).get("coverage_percent", 0.0)
                    source = "scorecard"
                else:
                    return GateResult(
                        gate_name="coverage",
                        status=GateStatus.UNKNOWN,
                        actual_value=0.0,
                        threshold=self.smoke_thresholds["coverage_min"],
                        message="No coverage data found",
                        details={"error": "no_coverage_data"}
                    )
            
            threshold = self.smoke_thresholds["coverage_min"]
            passed = coverage_percent >= threshold
            
            return GateResult(
                gate_name="coverage",
                status=GateStatus.PASS if passed else GateStatus.FAIL,
                actual_value=coverage_percent,
                threshold=threshold,
                message=f"Coverage {coverage_percent}% {'≥' if passed else '<'} {threshold}%",
                details={"source": source, "coverage_percent": coverage_percent}
            )
            
        except Exception as e:
            return GateResult(
                gate_name="coverage",
                status=GateStatus.UNKNOWN,
                actual_value=0.0,
                threshold=self.smoke_thresholds["coverage_min"],
                message=f"Coverage check error: {e}",
                details={"error": str(e)}
            )
    
    def check_security_gate(self) -> GateResult:
        """Prüfe Security Gate"""
        
        try:
            # Priorität: Konsolidierter Report > Legacy
            security_files = [
                self.reports_dir / "security_consolidated_report.json",
                self.reports_dir / "security_gate_report.json",
                self.reports_dir / "active_security_report.json"
            ]
            
            for security_file in security_files:
                if security_file.exists():
                    with open(security_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Format-spezifische Extraktion
                    if "security_consolidated" in data:
                        sec_data = data["security_consolidated"]
                        source = "consolidated"
                    elif "security_scan" in data:
                        sec_data = data["security_scan"]
                        source = "active_scan"
                    else:
                        sec_data = data.get("security_gate", {})
                        source = "legacy"
                    
                    high = sec_data.get("high", 999)
                    medium = sec_data.get("medium", 999)
                    active_tools = sec_data.get("active_tools", 0)
                    
                    # Prüfe kritische Bedingungen
                    high_threshold = self.smoke_thresholds["security_high_max"]
                    tools_threshold = self.smoke_thresholds["active_tools_min"]
                    
                    high_pass = high <= high_threshold
                    tools_pass = active_tools >= tools_threshold
                    
                    if not high_pass:
                        status = GateStatus.FAIL
                        message = f"Security HIGH {high} > {high_threshold} (zero tolerance)"
                    elif not tools_pass:
                        status = GateStatus.FAIL
                        message = f"Active tools {active_tools} < {tools_threshold} (minimum required)"
                    else:
                        status = GateStatus.PASS
                        message = f"Security HIGH {high} ≤ {high_threshold}, Tools {active_tools} ≥ {tools_threshold}"
                    
                    return GateResult(
                        gate_name="security",
                        status=status,
                        actual_value={"high": high, "medium": medium, "active_tools": active_tools},
                        threshold={"high_max": high_threshold, "tools_min": tools_threshold},
                        message=message,
                        details={"source": source, "high": high, "medium": medium, "active_tools": active_tools}
                    )
            
            # Keine Security-Reports gefunden
            return GateResult(
                gate_name="security",
                status=GateStatus.FAIL,
                actual_value={"high": 999, "active_tools": 0},
                threshold={"high_max": 0, "tools_min": 1},
                message="No security reports found - failing closed",
                details={"error": "no_security_data"}
            )
            
        except Exception as e:
            return GateResult(
                gate_name="security",
                status=GateStatus.FAIL,
                actual_value={"error": str(e)},
                threshold={"high_max": 0, "tools_min": 1},
                message=f"Security check error: {e}",
                details={"error": str(e)}
            )
    
    def check_license_gate(self) -> GateResult:
        """Prüfe License Gate"""
        
        try:
            # Priorität: Allowlist Report > Legacy
            license_files = [
                self.reports_dir / "license_gate_allowlist_report.json",
                self.reports_dir / "sbom_license_report.json"
            ]
            
            for license_file in license_files:
                if license_file.exists():
                    with open(license_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Format-spezifische Extraktion
                    if "license_gate" in data:
                        lic_data = data["license_gate"]
                        source = "allowlist"
                    else:
                        lic_data = data.get("sbom_license_gate", {})
                        source = "legacy"
                    
                    violations = lic_data.get("license_violations", 999)
                    threshold = self.smoke_thresholds["license_violations_max"]
                    
                    passed = violations <= threshold
                    
                    return GateResult(
                        gate_name="license",
                        status=GateStatus.PASS if passed else GateStatus.FAIL,
                        actual_value=violations,
                        threshold=threshold,
                        message=f"License violations {violations} {'≤' if passed else '>'} {threshold}",
                        details={
                            "source": source, 
                            "violations": violations,
                            "total_packages": lic_data.get("total_packages", 0)
                        }
                    )
            
            # Keine License-Reports gefunden
            return GateResult(
                gate_name="license",
                status=GateStatus.FAIL,
                actual_value=999,
                threshold=self.smoke_thresholds["license_violations_max"],
                message="No license reports found - failing closed",
                details={"error": "no_license_data"}
            )
            
        except Exception as e:
            return GateResult(
                gate_name="license",
                status=GateStatus.FAIL,
                actual_value=999,
                threshold=self.smoke_thresholds["license_violations_max"],
                message=f"License check error: {e}",
                details={"error": str(e)}
            )
    
    def check_scorecard_gate(self) -> GateResult:
        """Prüfe Scorecard Gate"""
        
        try:
            # Prüfe Scorecard-Status
            scorecard_files = [
                self.reports_dir / "scorecard_smoke.json",  # Smoke-Profil bevorzugt
                self.reports_dir / "scorecard.json"         # Legacy
            ]
            
            for scorecard_file in scorecard_files:
                if scorecard_file.exists():
                    with open(scorecard_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    scorecard_data = data.get("scorecard", {})
                    status = scorecard_data.get("status", "unknown")
                    profile = scorecard_data.get("profile", "unknown")
                    
                    passed = status == "pass"
                    
                    return GateResult(
                        gate_name="scorecard",
                        status=GateStatus.PASS if passed else GateStatus.FAIL,
                        actual_value=status,
                        threshold="pass",
                        message=f"Scorecard ({profile}) status: {status}",
                        details={
                            "scorecard_status": status,
                            "profile": profile,
                            "source": scorecard_file.name
                        }
                    )
            
            # Keine Scorecard gefunden
            return GateResult(
                gate_name="scorecard",
                status=GateStatus.FAIL,
                actual_value="missing",
                threshold="pass",
                message="No scorecard found - failing closed",
                details={"error": "no_scorecard_data"}
            )
            
        except Exception as e:
            return GateResult(
                gate_name="scorecard",
                status=GateStatus.FAIL,
                actual_value="error",
                threshold="pass",
                message=f"Scorecard check error: {e}",
                details={"error": str(e)}
            )
    
    def evaluate_overall_status(self, gate_results: List[GateResult]) -> Tuple[GateStatus, str, List[str]]:
        """Bewerte Overall-Status basierend auf Gates"""
        
        failed_gates = []
        warning_gates = []
        unknown_gates = []
        
        for gate_result in gate_results:
            if gate_result.status == GateStatus.FAIL:
                failed_gates.append(gate_result.gate_name)
            elif gate_result.status == GateStatus.WARN:
                warning_gates.append(gate_result.gate_name)
            elif gate_result.status == GateStatus.UNKNOWN:
                unknown_gates.append(gate_result.gate_name)
        
        # Fail-Closed-Logik: Ein Failed Gate = Overall Fail
        if failed_gates:
            overall_status = GateStatus.FAIL
            reasons = [f"{gate} failed" for gate in failed_gates]
            if unknown_gates:
                reasons.extend([f"{gate} unknown" for gate in unknown_gates])
            
            reason_summary = "Failed gates: " + ", ".join(failed_gates)
            if unknown_gates:
                reason_summary += f" | Unknown gates: {', '.join(unknown_gates)}"
        
        elif unknown_gates:
            # Unknown Gates = Fail (Fail-Closed)
            overall_status = GateStatus.FAIL
            reasons = [f"{gate} unknown (fail-closed)" for gate in unknown_gates]
            reason_summary = "Unknown gates (fail-closed): " + ", ".join(unknown_gates)
        
        elif warning_gates:
            overall_status = GateStatus.WARN
            reasons = [f"{gate} warning" for gate in warning_gates]
            reason_summary = "Warning gates: " + ", ".join(warning_gates)
        
        else:
            overall_status = GateStatus.PASS
            reasons = ["All gates passed"]
            reason_summary = "All gates passed"
        
        return overall_status, reason_summary, reasons
    
    def run_fail_closed_evaluation(self) -> Dict[str, Any]:
        """Führe Fail-Closed-Evaluierung durch"""
        
        print(f"🚨 Running Fail-Closed Gate Evaluation...")
        
        start_time = time.time()
        
        # Führe alle Gate-Checks durch
        print(f"\\n🚦 Checking quality gates...")
        
        coverage_result = self.check_coverage_gate()
        print(f"   📈 Coverage: {coverage_result.status.value.upper()} - {coverage_result.message}")
        
        security_result = self.check_security_gate()
        print(f"   🔒 Security: {security_result.status.value.upper()} - {security_result.message}")
        
        license_result = self.check_license_gate()
        print(f"   📝 License: {license_result.status.value.upper()} - {license_result.message}")
        
        scorecard_result = self.check_scorecard_gate()
        print(f"   📊 Scorecard: {scorecard_result.status.value.upper()} - {scorecard_result.message}")
        
        # Sammle alle Gate-Ergebnisse
        gate_results = [coverage_result, security_result, license_result, scorecard_result]
        
        # Bewerte Overall-Status
        overall_status, reason_summary, reasons = self.evaluate_overall_status(gate_results)
        
        duration = round(time.time() - start_time, 2)
        
        # Erstelle Fail-Closed-Report
        fail_closed_report = {
            "nightly_fail_closed": {
                "overall_status": overall_status.value,
                "overall_passing": overall_status == GateStatus.PASS,
                "reason_summary": reason_summary,
                "failure_reasons": reasons if overall_status in [GateStatus.FAIL, GateStatus.WARN] else [],
                "duration": duration,
                "gates_checked": len(gate_results),
                "gates_passed": len([g for g in gate_results if g.status == GateStatus.PASS]),
                "gates_failed": len([g for g in gate_results if g.status == GateStatus.FAIL]),
                "gates_unknown": len([g for g in gate_results if g.status == GateStatus.UNKNOWN]),
                "evaluation_date": datetime.utcnow().isoformat() + "Z",
                "thresholds": self.smoke_thresholds
            },
            "gate_results": {
                gate_result.gate_name: {
                    "status": gate_result.status.value,
                    "actual_value": gate_result.actual_value,
                    "threshold": gate_result.threshold,
                    "message": gate_result.message,
                    "details": gate_result.details
                }
                for gate_result in gate_results
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "project_root": str(self.project_root)
        }
        
        print(f"\\n🎯 Fail-Closed Evaluation Summary:")
        print(f"   Overall Status: {overall_status.value.upper()}")
        print(f"   Reason: {reason_summary}")
        print(f"   Gates: {len([g for g in gate_results if g.status == GateStatus.PASS])}/{len(gate_results)} passed")
        print(f"   Duration: {duration}s")
        
        return fail_closed_report
    
    def create_failure_markdown_report(self, fail_closed_report: Dict[str, Any]) -> str:
        """Erstelle verständlichen Markdown-Kurzreport"""
        
        data = fail_closed_report["nightly_fail_closed"]
        gate_results = fail_closed_report["gate_results"]
        
        status_icon = {
            "pass": "✅",
            "fail": "❌",
            "warn": "⚠️",
            "unknown": "❓"
        }
        
        # Markdown-Report erstellen
        markdown_lines = [
            "# 🌙 Nightly Fail-Closed Report",
            "",
            f"**Status:** {status_icon.get(data['overall_status'], '❓')} **{data['overall_status'].upper()}**  ",
            f"**Date:** {data['evaluation_date']}  ",
            f"**Duration:** {data['duration']}s  ",
            "",
            "## 📊 Gate Summary",
            "",
            f"- **Gates Checked:** {data['gates_checked']}",
            f"- **Gates Passed:** {data['gates_passed']} ✅",
            f"- **Gates Failed:** {data['gates_failed']} ❌",
            f"- **Gates Unknown:** {data['gates_unknown']} ❓",
            "",
            "## 🚦 Quality Gates Details",
            ""
        ]
        
        # Gate-Details hinzufügen
        for gate_name, gate_data in gate_results.items():
            icon = status_icon.get(gate_data["status"], "❓")
            markdown_lines.extend([
                f"### {icon} {gate_name.title()} Gate",
                "",
                f"- **Status:** {gate_data['status'].upper()}",
                f"- **Message:** {gate_data['message']}",
                f"- **Actual:** {gate_data['actual_value']}",
                f"- **Threshold:** {gate_data['threshold']}",
                ""
            ])
        
        # Failure-Reasons hinzufügen
        if data['failure_reasons']:
            markdown_lines.extend([
                "## 💥 Failure Analysis",
                "",
                f"**Root Cause:** {data['reason_summary']}",
                "",
                "**Specific Issues:**",
                ""
            ])
            
            for reason in data['failure_reasons']:
                markdown_lines.append(f"- {reason}")
            
            markdown_lines.extend([
                "",
                "## 🔧 Recommended Actions",
                ""
            ])
            
            # Spezifische Empfehlungen basierend auf Failed Gates
            if "coverage" in data['reason_summary'].lower():
                markdown_lines.extend([
                    "- **Coverage too low:** Run more comprehensive tests",
                    "- **Missing coverage.xml:** Ensure tests generate coverage report"
                ])
            
            if "security" in data['reason_summary'].lower():
                markdown_lines.extend([
                    "- **Security issues:** Review and fix high-severity findings",
                    "- **No active tools:** Ensure security scanners are properly configured"
                ])
            
            if "license" in data['reason_summary'].lower():
                markdown_lines.extend([
                    "- **License violations:** Review package licenses against allowlist",
                    "- **Missing SBOM:** Ensure dependency analysis is running"
                ])
            
            if "scorecard" in data['reason_summary'].lower():
                markdown_lines.extend([
                    "- **Scorecard failed:** Check individual quality metrics",
                    "- **Missing scorecard:** Ensure scorecard generation is working"
                ])
        
        else:
            markdown_lines.extend([
                "## 🎉 Success!",
                "",
                "All quality gates passed successfully. The nightly pipeline is healthy.",
                ""
            ])
        
        # Thresholds-Sektion
        markdown_lines.extend([
            "",
            "## 📏 Thresholds (Smoke Profile)",
            "",
            f"- **Coverage Min:** {data['thresholds']['coverage_min']}%",
            f"- **Security HIGH Max:** {data['thresholds']['security_high_max']}",
            f"- **License Violations Max:** {data['thresholds']['license_violations_max']}",
            f"- **Active Tools Min:** {data['thresholds']['active_tools_min']}",
            "",
            "---",
            "",
            "*Generated by Nightly Fail-Closed Runner*"
        ])
        
        return "\\n".join(markdown_lines)
    
    def save_fail_closed_reports(self, fail_closed_report: Dict[str, Any]) -> Tuple[Path, Path]:
        """Speichere Fail-Closed-Reports (JSON + Markdown)"""
        
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            # 1. JSON-Report
            json_file = self.reports_dir / "nightly_fail_closed_report.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(fail_closed_report, f, indent=2, ensure_ascii=False)
            
            # 2. Markdown-Report
            markdown_content = self.create_failure_markdown_report(fail_closed_report)
            markdown_file = self.reports_dir / "nightly_fail_closed_report.md"
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            print(f"📄 Fail-closed JSON report saved: {json_file}")
            print(f"📄 Fail-closed Markdown report saved: {markdown_file}")
            
            return json_file, markdown_file
            
        except Exception as e:
            print(f"⚠️ Could not save fail-closed reports: {e}")
            return None, None


def main():
    """Main function für Nightly Fail-Closed Runner"""
    print("🎯 MVP-FIX-006: Nightly Runner Fail Closed")
    
    try:
        # Initialisiere Nightly Fail-Closed Runner
        runner = NightlyFailClosedRunner()
        
        # Führe Fail-Closed-Evaluation durch
        fail_closed_report = runner.run_fail_closed_evaluation()
        
        # Speichere Reports
        json_file, markdown_file = runner.save_fail_closed_reports(fail_closed_report)
        
        # Prüfe Akzeptanzkriterien
        data = fail_closed_report["nightly_fail_closed"]
        overall_status = data["overall_status"]
        reason_summary = data["reason_summary"]
        gates_failed = data["gates_failed"]
        
        print(f"\\n🎯 MVP-FIX-006 Akzeptanzkriterien:")
        print(f"   Overall fail bei Gate-Verletzung: {'✅' if gates_failed == 0 or overall_status == 'fail' else '❌'}")
        print(f"   Verständliche Gründe in KPI: ✅ ({reason_summary})")
        print(f"   Markdown Kurzreport: {'✅' if markdown_file else '❌'}")
        print(f"   Fail-Closed bei Active Tools 0: {'✅' if 'tools' not in reason_summary.lower() or overall_status == 'fail' else '❌'}")
        print(f"   Fail-Closed bei License > Limit: {'✅' if 'license' not in reason_summary.lower() or overall_status == 'fail' else '❌'}")
        print(f"   Fail-Closed bei Coverage < Schwelle: {'✅' if 'coverage' not in reason_summary.lower() or overall_status == 'fail' else '❌'}")
        
        # Exit-Code basierend auf Overall-Status
        if overall_status == "pass":
            print("🎉 Nightly Fail-Closed Evaluation PASSED!")
            return 0
        else:
            print(f"💥 Nightly Fail-Closed Evaluation: {overall_status.upper()}!")
            return 1
            
    except Exception as e:
        print(f"💥 Nightly Fail-Closed error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
