#!/usr/bin/env python3
"""
CI-301: CI-Gesamtlauf robust machen
Lokaler Test- und Analyse-Runner mit korrekter Artefakt-Erkennung.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List


class CIRunner:
    """Robuster CI-Runner für lokale Tests und Analyse"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.coverage_file = self.project_root / "coverage.xml"
        self.security_file = self.project_root / "reports" / "security_report.json"
        self.qa_summary_file = self.project_root / "qa_summary.json"
        
        self.results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "coverage": {},
            "security": {},
            "overall_status": "unknown",
            "errors": [],
            "warnings": []
        }
    
    def check_coverage_report(self) -> Dict[str, Any]:
        """Lese Coverage-Report aus Projekt-Root"""
        print("📊 Checking Coverage Report...")
        
        if not self.coverage_file.exists():
            error_msg = f"❌ Coverage report not found: {self.coverage_file}"
            print(error_msg)
            self.results["errors"].append(error_msg)
            return {
                "status": "error",
                "coverage_percent": 0.0,
                "error": "Coverage report not found"
            }
        
        try:
            # Parse XML Coverage Report
            tree = ET.parse(self.coverage_file)
            root = tree.getroot()
            
            # Extrahiere line-rate aus coverage Element
            line_rate = float(root.attrib.get('line-rate', '0.0'))
            coverage_percent = line_rate * 100
            
            # Extrahiere weitere Metriken
            lines_covered = int(root.attrib.get('lines-covered', '0'))
            lines_valid = int(root.attrib.get('lines-valid', '0'))
            
            coverage_data = {
                "status": "ok",
                "coverage_percent": round(coverage_percent, 2),
                "line_rate": line_rate,
                "lines_covered": lines_covered,
                "lines_valid": lines_valid,
                "source_file": str(self.coverage_file)
            }
            
            print(f"✅ Coverage: {coverage_percent:.2f}% ({lines_covered}/{lines_valid} lines)")
            return coverage_data
            
        except Exception as e:
            error_msg = f"❌ Error parsing coverage report: {e}"
            print(error_msg)
            self.results["errors"].append(error_msg)
            return {
                "status": "error",
                "coverage_percent": 0.0,
                "error": str(e)
            }
    
    def check_security_report(self) -> Dict[str, Any]:
        """Lese konsolidierten Security-Report"""
        print("🔒 Checking Security Report...")
        
        if not self.security_file.exists():
            error_msg = f"❌ Security report not found: {self.security_file}"
            print(error_msg)
            self.results["errors"].append(error_msg)
            return {
                "status": "error",
                "high": 999,  # Fail-safe: Assume high findings if report missing
                "active_tools": 0,
                "error": "Security report not found"
            }
        
        try:
            with open(self.security_file, 'r', encoding='utf-8') as f:
                security_data = json.load(f)
            
            # Extrahiere Bandit-Daten
            bandit_data = security_data.get("bandit", {})
            
            security_result = {
                "status": bandit_data.get("status", "unknown"),
                "high": bandit_data.get("high", 0),
                "medium": bandit_data.get("medium", 0),
                "low": bandit_data.get("low", 0),
                "total": bandit_data.get("total", 0),
                "active_tools": bandit_data.get("active_tools", 0),
                "scan_date": bandit_data.get("scan_date", "unknown"),
                "source_file": str(self.security_file)
            }
            
            print(f"✅ Security: {security_result['status'].upper()} "
                  f"(H:{security_result['high']}, M:{security_result['medium']}, L:{security_result['low']})")
            print(f"🔧 Active Tools: {security_result['active_tools']}")
            
            return security_result
            
        except Exception as e:
            error_msg = f"❌ Error parsing security report: {e}"
            print(error_msg)
            self.results["errors"].append(error_msg)
            return {
                "status": "error", 
                "high": 999,
                "active_tools": 0,
                "error": str(e)
            }
    
    def validate_quality_gates(self, coverage_data: Dict[str, Any], security_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validiere Quality Gates mit fail-closed Verhalten"""
        print("🚦 Validating Quality Gates...")
        
        gates = {
            "coverage_gate": {"status": "unknown", "threshold": 0.2},
            "security_gate": {"status": "unknown", "threshold": 0},
            "active_tools_gate": {"status": "unknown", "threshold": 1}
        }
        
        failures = []
        
        # Coverage Gate
        coverage_percent = coverage_data.get("coverage_percent", 0.0)
        coverage_threshold = gates["coverage_gate"]["threshold"]
        
        if coverage_data.get("status") == "error":
            gates["coverage_gate"]["status"] = "fail"
            failures.append(f"Coverage report error: {coverage_data.get('error', 'unknown')}")
        elif coverage_percent >= coverage_threshold:
            gates["coverage_gate"]["status"] = "pass"
        else:
            gates["coverage_gate"]["status"] = "fail"
            failures.append(f"Coverage {coverage_percent:.2f}% < {coverage_threshold}%")
        
        # Security Gate - Fail-closed
        security_high = security_data.get("high", 999)
        security_threshold = gates["security_gate"]["threshold"]
        
        if security_data.get("status") == "error":
            gates["security_gate"]["status"] = "fail"
            failures.append(f"Security report error: {security_data.get('error', 'unknown')}")
        elif security_high <= security_threshold:
            gates["security_gate"]["status"] = "pass"
        else:
            gates["security_gate"]["status"] = "fail"
            failures.append(f"Security HIGH findings: {security_high} > {security_threshold}")
        
        # Active Tools Gate
        active_tools = security_data.get("active_tools", 0)
        tools_threshold = gates["active_tools_gate"]["threshold"]
        
        if active_tools >= tools_threshold:
            gates["active_tools_gate"]["status"] = "pass"
        else:
            gates["active_tools_gate"]["status"] = "fail"
            failures.append(f"Active security tools: {active_tools} < {tools_threshold}")
        
        # Overall Status
        all_passed = all(gate["status"] == "pass" for gate in gates.values())
        overall_status = "pass" if all_passed else "fail"
        
        # Output
        for gate_name, gate_data in gates.items():
            status_icon = "✅" if gate_data["status"] == "pass" else "❌"
            print(f"{status_icon} {gate_name}: {gate_data['status'].upper()}")
        
        if failures:
            print(f"\n❌ Quality Gate Failures ({len(failures)}):")
            for i, failure in enumerate(failures, 1):
                print(f"  {i}. {failure}")
        
        return {
            "overall_status": overall_status,
            "gates": gates,
            "failures": failures,
            "all_passed": all_passed
        }
    
    def create_qa_summary(self, coverage_data: Dict[str, Any], security_data: Dict[str, Any], gates_result: Dict[str, Any]) -> Dict[str, Any]:
        """Erstelle QA-Zusammenfassung"""
        print("📋 Creating QA Summary...")
        
        qa_summary = {
            "timestamp": self.results["timestamp"],
            "overall_status": gates_result["overall_status"],
            "passed": gates_result["all_passed"],
            
            # Coverage Metrics
            "coverage": {
                "percent": coverage_data.get("coverage_percent", 0.0),
                "lines_covered": coverage_data.get("lines_covered", 0),
                "lines_valid": coverage_data.get("lines_valid", 0),
                "status": coverage_data.get("status", "unknown")
            },
            
            # Security Metrics
            "security": {
                "status": security_data.get("status", "unknown"),
                "high": security_data.get("high", 0),
                "medium": security_data.get("medium", 0),
                "low": security_data.get("low", 0),
                "total": security_data.get("total", 0),
                "active_tools": security_data.get("active_tools", 0)
            },
            
            # Gates
            "gates": gates_result["gates"],
            "failures": gates_result["failures"],
            
            # Metadata
            "artifacts": {
                "coverage_report": str(self.coverage_file) if self.coverage_file.exists() else None,
                "security_report": str(self.security_file) if self.security_file.exists() else None
            },
            "errors": self.results["errors"],
            "warnings": self.results["warnings"]
        }
        
        # Schreibe QA-Summary
        try:
            with open(self.qa_summary_file, 'w', encoding='utf-8') as f:
                json.dump(qa_summary, f, indent=2, ensure_ascii=False)
            print(f"✅ QA Summary written to: {self.qa_summary_file}")
        except Exception as e:
            error_msg = f"❌ Error writing QA summary: {e}"
            print(error_msg)
            qa_summary["errors"].append(error_msg)
        
        return qa_summary
    
    def run(self) -> int:
        """Führe vollständigen CI-Lauf durch"""
        print("🚀 Starting CI Runner...")
        print(f"📁 Project Root: {self.project_root}")
        
        try:
            # 1. Check Coverage Report
            coverage_data = self.check_coverage_report()
            self.results["coverage"] = coverage_data
            
            # 2. Check Security Report  
            security_data = self.check_security_report()
            self.results["security"] = security_data
            
            # 3. Validate Quality Gates
            gates_result = self.validate_quality_gates(coverage_data, security_data)
            self.results.update(gates_result)
            
            # 4. Create QA Summary
            qa_summary = self.create_qa_summary(coverage_data, security_data, gates_result)
            
            # 5. Final Status
            overall_status = gates_result["overall_status"]
            self.results["overall_status"] = overall_status
            
            print(f"\n🎯 CI Runner Result: {overall_status.upper()}")
            
            if overall_status == "pass":
                print("✅ All quality gates passed!")
                return 0
            else:
                print(f"❌ Quality gates failed: {len(gates_result['failures'])} issues")
                return 1
                
        except Exception as e:
            print(f"💥 CI Runner failed with unexpected error: {e}")
            return 2


def main():
    """Main function"""
    runner = CIRunner()
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
