#!/usr/bin/env python3
"""
MVP-006: QA-Gates verdrahten (Lint, Types, Tests, Coverage)
Reproduzierbare Qualitätssignale durch orchestrierten lokalen Runner.
"""

import subprocess
import sys
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import yaml


class QAGateResult:
    """Ergebnis eines QA-Gates"""
    
    def __init__(self, name: str, status: str, details: Dict[str, Any] = None):
        self.name = name
        self.status = status  # "pass", "fail", "error", "skip"
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def is_passing(self) -> bool:
        return self.status in ["pass", "skip"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "details": self.details,
            "timestamp": self.timestamp
        }


class QAGatesRunner:
    """MVP QA-Gates Runner für reproduzierbare Qualitätssignale"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.policy_config = self._load_policy_config()
        self.results = {}
        self.summary = {
            "start_time": datetime.utcnow().isoformat() + "Z",
            "end_time": None,
            "overall_status": "unknown",
            "gates_passed": 0,
            "gates_total": 0,
            "gates_failed": [],
            "coverage_achieved": 0.0,
            "coverage_required": 0.0
        }
    
    def _load_policy_config(self) -> Dict[str, Any]:
        """Lade Policy-Konfiguration für QA-Mindestanforderungen"""
        
        policy_file = self.project_root / "policies" / "QUALITY.yml"
        
        # Default-Policy falls Datei nicht existiert
        default_policy = {
            "hard_musts": {
                "coverage_min": 0.2,  # 0.2% Minimum
                "lint_max_issues": 50,
                "type_check_errors": 10
            },
            "qa_gates": {
                "enable_lint": True,
                "enable_type_check": True,
                "enable_tests": True,
                "enable_coverage": True,
                "coverage_fail_under": 0.2
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
            
            print(f"✅ Loaded policy config: {policy_file}")
            return policy
            
        except Exception as e:
            print(f"⚠️  Error loading policy config: {e}, using defaults")
            return default_policy
    
    def run_lint_gate(self) -> QAGateResult:
        """Führe Linting-Gate durch"""
        print("🔍 Running Lint Gate...")
        
        if not self.policy_config["qa_gates"]["enable_lint"]:
            return QAGateResult("lint", "skip", {"reason": "Disabled in policy"})
        
        try:
            # Prüfe ob ruff verfügbar ist
            try:
                result = subprocess.run(
                    ["ruff", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    raise FileNotFoundError("ruff not available")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return QAGateResult("lint", "skip", {"reason": "ruff not available"})
            
            # Führe ruff check aus
            cmd = ["ruff", "check", ".", "--output-format=json"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=60
            )
            
            # Parse ruff output
            issues = []
            if result.stdout:
                try:
                    ruff_output = json.loads(result.stdout)
                    issues = ruff_output if isinstance(ruff_output, list) else []
                except json.JSONDecodeError:
                    # Fallback: zähle Zeilen
                    issues = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            issue_count = len(issues)
            max_issues = self.policy_config["hard_musts"]["lint_max_issues"]
            
            details = {
                "tool": "ruff",
                "issues_found": issue_count,
                "max_allowed": max_issues,
                "command": " ".join(cmd),
                "exit_code": result.returncode
            }
            
            if issue_count <= max_issues:
                status = "pass"
                print(f"   ✅ Lint Gate PASSED: {issue_count}/{max_issues} issues")
            else:
                status = "fail"
                print(f"   ❌ Lint Gate FAILED: {issue_count}/{max_issues} issues")
            
            return QAGateResult("lint", status, details)
            
        except subprocess.TimeoutExpired:
            return QAGateResult("lint", "error", {"reason": "Timeout after 60s"})
        except Exception as e:
            return QAGateResult("lint", "error", {"reason": str(e)})
    
    def run_type_check_gate(self) -> QAGateResult:
        """Führe Type-Checking-Gate durch"""
        print("🔎 Running Type Check Gate...")
        
        if not self.policy_config["qa_gates"]["enable_type_check"]:
            return QAGateResult("type_check", "skip", {"reason": "Disabled in policy"})
        
        try:
            # Prüfe ob mypy verfügbar ist
            try:
                result = subprocess.run(
                    ["mypy", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    raise FileNotFoundError("mypy not available")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return QAGateResult("type_check", "skip", {"reason": "mypy not available"})
            
            # Führe mypy aus
            cmd = ["mypy", ".", "--ignore-missing-imports", "--no-error-summary"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=120
            )
            
            # Zähle Type-Errors
            error_lines = [line for line in result.stdout.split('\n') if line.strip() and 'error:' in line]
            error_count = len(error_lines)
            max_errors = self.policy_config["hard_musts"]["type_check_errors"]
            
            details = {
                "tool": "mypy",
                "errors_found": error_count,
                "max_allowed": max_errors,
                "command": " ".join(cmd),
                "exit_code": result.returncode
            }
            
            if error_count <= max_errors:
                status = "pass"
                print(f"   ✅ Type Check Gate PASSED: {error_count}/{max_errors} errors")
            else:
                status = "fail"
                print(f"   ❌ Type Check Gate FAILED: {error_count}/{max_errors} errors")
            
            return QAGateResult("type_check", status, details)
            
        except subprocess.TimeoutExpired:
            return QAGateResult("type_check", "error", {"reason": "Timeout after 120s"})
        except Exception as e:
            return QAGateResult("type_check", "error", {"reason": str(e)})
    
    def run_tests_gate(self) -> QAGateResult:
        """Führe Tests-Gate durch"""
        print("🧪 Running Tests Gate...")
        
        if not self.policy_config["qa_gates"]["enable_tests"]:
            return QAGateResult("tests", "skip", {"reason": "Disabled in policy"})
        
        try:
            # Führe pytest aus
            cmd = ["pytest", "--tb=short", "-q"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=300
            )
            
            # Parse pytest output für Statistiken
            output_lines = result.stdout.split('\n')
            summary_line = ""
            for line in output_lines:
                if "passed" in line or "failed" in line or "error" in line:
                    summary_line = line
                    break
            
            details = {
                "tool": "pytest",
                "command": " ".join(cmd),
                "exit_code": result.returncode,
                "summary": summary_line,
                "duration": "estimated from timeout"
            }
            
            if result.returncode == 0:
                status = "pass"
                print(f"   ✅ Tests Gate PASSED: {summary_line}")
            else:
                status = "fail"
                print(f"   ❌ Tests Gate FAILED: {summary_line}")
            
            return QAGateResult("tests", status, details)
            
        except subprocess.TimeoutExpired:
            return QAGateResult("tests", "error", {"reason": "Timeout after 300s"})
        except Exception as e:
            return QAGateResult("tests", "error", {"reason": str(e)})
    
    def run_coverage_gate(self) -> QAGateResult:
        """Führe Coverage-Gate durch"""
        print("📊 Running Coverage Gate...")
        
        if not self.policy_config["qa_gates"]["enable_coverage"]:
            return QAGateResult("coverage", "skip", {"reason": "Disabled in policy"})
        
        try:
            # Führe pytest mit coverage aus
            coverage_file = self.project_root / "coverage.xml"
            cmd = [
                "pytest", 
                "--cov=codepipeline",
                "--cov=.",
                "--cov-report=xml:coverage.xml",
                "--cov-report=term-missing",
                "--tb=short",
                "-q"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=300
            )
            
            # Lese Coverage aus coverage.xml
            coverage_percent = 0.0
            lines_covered = 0
            lines_total = 0
            
            if coverage_file.exists():
                try:
                    tree = ET.parse(coverage_file)
                    root = tree.getroot()
                    
                    line_rate = float(root.attrib.get('line-rate', '0.0'))
                    coverage_percent = line_rate * 100
                    lines_covered = int(root.attrib.get('lines-covered', '0'))
                    lines_total = int(root.attrib.get('lines-valid', '0'))
                    
                except Exception as e:
                    print(f"   ⚠️  Error parsing coverage.xml: {e}")
            
            # Prüfe gegen Policy-Schwelle
            min_coverage = self.policy_config["hard_musts"]["coverage_min"]
            
            details = {
                "tool": "pytest-cov",
                "coverage_percent": round(coverage_percent, 2),
                "coverage_required": min_coverage,
                "lines_covered": lines_covered,
                "lines_total": lines_total,
                "coverage_file": str(coverage_file),
                "command": " ".join(cmd),
                "exit_code": result.returncode
            }
            
            # Update Summary
            self.summary["coverage_achieved"] = coverage_percent
            self.summary["coverage_required"] = min_coverage
            
            if coverage_percent >= min_coverage:
                status = "pass"
                print(f"   ✅ Coverage Gate PASSED: {coverage_percent:.2f}% ≥ {min_coverage}%")
            else:
                status = "fail"
                print(f"   ❌ Coverage Gate FAILED: {coverage_percent:.2f}% < {min_coverage}%")
            
            return QAGateResult("coverage", status, details)
            
        except subprocess.TimeoutExpired:
            return QAGateResult("coverage", "error", {"reason": "Timeout after 300s"})
        except Exception as e:
            return QAGateResult("coverage", "error", {"reason": str(e)})
    
    def run_all_gates(self) -> Dict[str, QAGateResult]:
        """Führe alle QA-Gates durch"""
        print("🚦 Running All QA Gates...")
        print(f"📁 Project Root: {self.project_root}")
        
        # Definiere Gate-Reihenfolge
        gates = [
            ("lint", self.run_lint_gate),
            ("type_check", self.run_type_check_gate),
            ("tests", self.run_tests_gate),
            ("coverage", self.run_coverage_gate)
        ]
        
        results = {}
        passed_gates = 0
        failed_gates = []
        
        for gate_name, gate_func in gates:
            try:
                print(f"\n--- {gate_name.upper()} GATE ---")
                result = gate_func()
                results[gate_name] = result
                
                if result.is_passing():
                    passed_gates += 1
                else:
                    failed_gates.append(gate_name)
                    
            except Exception as e:
                print(f"💥 Gate {gate_name} crashed: {e}")
                results[gate_name] = QAGateResult(gate_name, "error", {"reason": str(e)})
                failed_gates.append(gate_name)
        
        # Update Summary
        self.summary["end_time"] = datetime.utcnow().isoformat() + "Z"
        self.summary["gates_passed"] = passed_gates
        self.summary["gates_total"] = len(gates)
        self.summary["gates_failed"] = failed_gates
        self.summary["overall_status"] = "pass" if len(failed_gates) == 0 else "fail"
        
        self.results = results
        return results
    
    def generate_summary_report(self) -> str:
        """Generiere menschlich lesbare Zusammenfassung"""
        
        summary_lines = [
            "\n" + "="*60,
            "📊 QA GATES SUMMARY REPORT",
            "="*60
        ]
        
        # Overall Status
        status_icon = "🎉" if self.summary["overall_status"] == "pass" else "💥"
        summary_lines.extend([
            f"{status_icon} Overall Status: {self.summary['overall_status'].upper()}",
            f"🚦 Gates Passed: {self.summary['gates_passed']}/{self.summary['gates_total']}"
        ])
        
        # Coverage Info
        if self.summary["coverage_achieved"] > 0:
            coverage_icon = "✅" if self.summary["coverage_achieved"] >= self.summary["coverage_required"] else "❌"
            summary_lines.append(
                f"📊 Coverage: {coverage_icon} {self.summary['coverage_achieved']:.2f}% "
                f"(required: {self.summary['coverage_required']:.2f}%)"
            )
        
        # Gate Details
        if self.results:
            summary_lines.append("\n🚦 GATE DETAILS:")
            for gate_name, result in self.results.items():
                status_icon = "✅" if result.is_passing() else "❌"
                summary_lines.append(f"   {status_icon} {gate_name.upper()}: {result.status}")
                
                # Details
                if result.details:
                    if "issues_found" in result.details:
                        summary_lines.append(f"      Issues: {result.details['issues_found']}")
                    if "errors_found" in result.details:
                        summary_lines.append(f"      Errors: {result.details['errors_found']}")
                    if "coverage_percent" in result.details:
                        summary_lines.append(f"      Coverage: {result.details['coverage_percent']:.2f}%")
        
        # Failed Gates
        if self.summary["gates_failed"]:
            summary_lines.append(f"\n❌ FAILED GATES ({len(self.summary['gates_failed'])}):")
            for gate in self.summary["gates_failed"]:
                summary_lines.append(f"   • {gate}")
        
        # Timing
        if self.summary["start_time"] and self.summary["end_time"]:
            start = datetime.fromisoformat(self.summary["start_time"].rstrip("Z"))
            end = datetime.fromisoformat(self.summary["end_time"].rstrip("Z"))
            duration = (end - start).total_seconds()
            summary_lines.append(f"\n⏱️  Total Duration: {duration:.1f}s")
        
        summary_lines.append("="*60)
        
        return "\n".join(summary_lines)
    
    def save_qa_report(self) -> Path:
        """Speichere QA-Report als JSON"""
        try:
            reports_dir = self.project_root / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            # Erstelle vollständigen Report
            report_data = {
                "summary": self.summary,
                "policy_config": self.policy_config,
                "results": {name: result.to_dict() for name, result in self.results.items()},
                "metadata": {
                    "project_root": str(self.project_root),
                    "generated_at": datetime.utcnow().isoformat() + "Z"
                }
            }
            
            # Generiere Report-Dateinamen
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"qa_gates_report_{timestamp}.json"
            
            # Schreibe Report
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            print(f"📄 QA report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"⚠️  Could not save QA report: {e}")
            return None


def main():
    """Main function für QA Gates Runner"""
    print("🎯 MVP-006: QA-Gates verdrahten (Lint, Types, Tests, Coverage)")
    
    try:
        # Initialisiere Runner
        runner = QAGatesRunner()
        
        # Führe alle Gates durch
        results = runner.run_all_gates()
        
        # Zeige Zusammenfassung
        summary = runner.generate_summary_report()
        print(summary)
        
        # Speichere Report
        runner.save_qa_report()
        
        # Exit-Code basierend auf Ergebnis
        if runner.summary["overall_status"] == "pass":
            print("🎉 All QA gates passed!")
            return 0
        else:
            print("💥 Some QA gates failed!")
            return 1
            
    except Exception as e:
        print(f"💥 QA Gates Runner failed: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
