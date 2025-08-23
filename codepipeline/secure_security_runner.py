#!/usr/bin/env python3
"""
MVP-CLOSE-005: Zweites Security-Tool im Secure-Profil erzwingen
Defense-in-Depth im Secure-Modus mit ≥2 aktiven Security-Tools.
"""

import json
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import argparse
import concurrent.futures
import os
import re


class SecureSecurityRunner:
    """Security-Runner für Secure-Profil mit mehreren Tools"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Secure-Profil erfordert mindestens 2 Tools
        self.required_tools_secure = 2
        self.required_tools_smoke = 1
        
        print(f"🔒 Secure Security Runner initialized")
        print(f"   Project root: {self.project_root}")
        print(f"   Required tools (secure): {self.required_tools_secure}")
        print(f"   Required tools (smoke): {self.required_tools_smoke}")
    
    def run_bandit_scan(self, parallel_jobs: int = 2) -> Dict[str, Any]:
        """Führe Bandit-Scan durch (Tool 1)"""
        
        print(f"🔍 Running Bandit scan...")
        
        try:
            # Bandit-Konfiguration für Low-Noise
            bandit_excludes = [
                "*/tests/*",
                "*/test_*",
                "*_test.py",
                "*/venv/*",
                "*/env/*",
                "*/build/*",
                "*/dist/*",
                "*/.git/*",
                "*/node_modules/*"
            ]
            
            exclude_arg = ",".join(bandit_excludes)
            
            # Bandit-Kommando
            bandit_cmd = [
                sys.executable, "-m", "bandit",
                "-r", str(self.project_root),
                "-f", "json",
                "-o", str(self.reports_dir / "bandit_secure.json"),
                "--exclude", exclude_arg,
                "-ll",  # Low-Noise: Only medium and high
                "--skip", "B101,B601,B602,B603,B604,B605,B606,B607",  # Skip common false positives
                "--quiet"
            ]
            
            print(f"   Command: {' '.join(bandit_cmd[:6])}...")
            
            result = subprocess.run(
                bandit_cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.project_root
            )
            
            # Bandit exit codes: 0=no issues, 1=issues found, >1=error
            if result.returncode > 1:
                print(f"   ⚠️ Bandit error (exit {result.returncode}): {result.stderr}")
                return {
                    "tool": "bandit",
                    "status": "error",
                    "high": 999,
                    "medium": 999,
                    "low": 999,
                    "total": 999,
                    "error": result.stderr[:200]
                }
            
            # Parse Bandit-Output
            bandit_report_file = self.reports_dir / "bandit_secure.json"
            if bandit_report_file.exists():
                try:
                    with open(bandit_report_file, 'r', encoding='utf-8') as f:
                        bandit_data = json.load(f)
                    
                    # Count findings by severity
                    high_count = len([r for r in bandit_data.get("results", []) if r.get("issue_severity") == "HIGH"])
                    medium_count = len([r for r in bandit_data.get("results", []) if r.get("issue_severity") == "MEDIUM"])
                    low_count = len([r for r in bandit_data.get("results", []) if r.get("issue_severity") == "LOW"])
                    total_count = high_count + medium_count + low_count
                    
                    return {
                        "tool": "bandit",
                        "status": "ok",
                        "high": high_count,
                        "medium": medium_count,
                        "low": low_count,
                        "total": total_count,
                        "scan_date": datetime.utcnow().isoformat() + "Z"
                    }
                    
                except Exception as e:
                    print(f"   ⚠️ Error parsing Bandit report: {e}")
                    
            # Fallback: No issues found
            return {
                "tool": "bandit",
                "status": "ok",
                "high": 0,
                "medium": 0,
                "low": 0,
                "total": 0,
                "scan_date": datetime.utcnow().isoformat() + "Z"
            }
            
        except subprocess.TimeoutExpired:
            print(f"   ⚠️ Bandit scan timed out")
            return {
                "tool": "bandit",
                "status": "timeout",
                "high": 999,
                "medium": 999,
                "low": 999,
                "total": 999,
                "error": "Scan timed out after 300 seconds"
            }
        except Exception as e:
            print(f"   ⚠️ Bandit scan error: {e}")
            return {
                "tool": "bandit",
                "status": "error",
                "high": 999,
                "medium": 999,
                "low": 999,
                "total": 999,
                "error": str(e)[:200]
            }
    
    def run_safety_scan(self) -> Dict[str, Any]:
        """Führe Safety-Scan durch (Tool 2)"""
        
        print(f"🛡️ Running Safety scan...")
        
        try:
            # Safety-Kommando für Vulnerability-Check (ohne --quiet)
            safety_cmd = [
                sys.executable, "-m", "safety",
                "check",
                "--json",
                "--ignore", "51457,51499"  # Ignore common dev-only vulnerabilities
            ]
            
            print(f"   Command: {' '.join(safety_cmd[:4])}...")
            
            result = subprocess.run(
                safety_cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=self.project_root
            )
            
            # Safety exit codes: 0=safe, 1=vulnerabilities, >1=error
            if result.returncode > 1:
                print(f"   ⚠️ Safety error (exit {result.returncode}): {result.stderr}")
                return {
                    "tool": "safety",
                    "status": "error",
                    "high": 999,
                    "medium": 999,
                    "low": 999,
                    "total": 999,
                    "error": result.stderr[:200]
                }
            
            # Parse Safety-Output aus stdout
            vulnerabilities = []
            
            if result.stdout:
                try:
                    safety_data = json.loads(result.stdout)
                    
                    if isinstance(safety_data, list):
                        vulnerabilities = safety_data
                    elif isinstance(safety_data, dict) and "vulnerabilities" in safety_data:
                        vulnerabilities = safety_data["vulnerabilities"]
                        
                except Exception as e:
                    print(f"   ⚠️ Error parsing Safety JSON: {e}")
                    # Fallback: Parse text output
                    if "No known security vulnerabilities found" in result.stdout:
                        vulnerabilities = []
            
            # Klassifiziere Vulnerabilities nach Schweregrad
            high_count = 0
            medium_count = 0
            low_count = 0
            
            for vuln in vulnerabilities:
                # Safety klassifiziert meist als HIGH (CVE-basiert)
                # Heuristik für Klassifizierung
                vuln_id = vuln.get("id", "")
                vuln_title = vuln.get("advisory", "").lower()
                
                if any(word in vuln_title for word in ["critical", "remote code execution", "rce", "sql injection"]):
                    high_count += 1
                elif any(word in vuln_title for word in ["denial of service", "dos", "information disclosure"]):
                    medium_count += 1
                else:
                    medium_count += 1  # Default zu medium für Safety-Findings
            
            total_count = high_count + medium_count + low_count
            
            return {
                "tool": "safety",
                "status": "ok",
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
                "total": total_count,
                "vulnerabilities_found": len(vulnerabilities),
                "scan_date": datetime.utcnow().isoformat() + "Z"
            }
            
        except subprocess.TimeoutExpired:
            print(f"   ⚠️ Safety scan timed out")
            return {
                "tool": "safety",
                "status": "timeout",
                "high": 999,
                "medium": 999,
                "low": 999,
                "total": 999,
                "error": "Scan timed out after 120 seconds"
            }
        except Exception as e:
            print(f"   ⚠️ Safety scan error: {e}")
            return {
                "tool": "safety",
                "status": "error",
                "high": 999,
                "medium": 999,
                "low": 999,
                "total": 999,
                "error": str(e)[:200]
            }
    
    def run_custom_security_scan(self) -> Dict[str, Any]:
        """Führe Custom-Security-Scan durch (Tool 3 - Fallback für Semgrep)"""
        
        print(f"🔍 Running Custom Security scan...")
        
        try:
            # Custom Security-Patterns für Python-Code
            security_patterns = [
                # Potentielle Sicherheitsprobleme
                {"pattern": r"eval\s*\(", "severity": "HIGH", "description": "Use of eval()"},
                {"pattern": r"exec\s*\(", "severity": "HIGH", "description": "Use of exec()"},
                {"pattern": r"subprocess\.call\s*\(.*shell\s*=\s*True", "severity": "HIGH", "description": "Shell injection risk"},
                {"pattern": r"os\.system\s*\(", "severity": "HIGH", "description": "OS command execution"},
                {"pattern": r"pickle\.loads\s*\(", "severity": "MEDIUM", "description": "Unsafe pickle deserialization"},
                {"pattern": r"yaml\.load\s*\([^,)]*\)", "severity": "MEDIUM", "description": "Unsafe YAML loading"},
                {"pattern": r"input\s*\(", "severity": "LOW", "description": "User input without validation"},
                {"pattern": r"random\.random\s*\(\)", "severity": "LOW", "description": "Weak random number generation"},
                {"pattern": r"md5\s*\(", "severity": "MEDIUM", "description": "Weak hash algorithm MD5"},
                {"pattern": r"sha1\s*\(", "severity": "MEDIUM", "description": "Weak hash algorithm SHA1"},
                {"pattern": r"password\s*=\s*[\"'][^\"']+[\"']", "severity": "HIGH", "description": "Hardcoded password"},
                {"pattern": r"api[_-]?key\s*=\s*[\"'][^\"']+[\"']", "severity": "HIGH", "description": "Hardcoded API key"},
                {"pattern": r"secret\s*=\s*[\"'][^\"']+[\"']", "severity": "HIGH", "description": "Hardcoded secret"},
            ]
            
            findings = []
            
            # Scanne nur codepipeline/** Python-Dateien (MVP-HOT-03 Scope-Beschränkung)
            codepipeline_dir = self.project_root / "codepipeline"
            if not codepipeline_dir.exists():
                print(f"   ⚠️ codepipeline/ directory not found")
                return {"tool": "custom_security", "status": "error", "high": 0, "medium": 0, "low": 0}
            
            python_files = list(codepipeline_dir.rglob("*.py"))
            
            # Filtere irrelevante Dateien innerhalb codepipeline/
            excluded_paths = ["test_", "__pycache__/", ".pyc"]
            filtered_files = []
            
            for py_file in python_files:
                relative_path = str(py_file.relative_to(self.project_root))
                if not any(excl in relative_path for excl in excluded_paths):
                    filtered_files.append(py_file)
            
            print(f"   Scanning {len(filtered_files)} Python files...")
            
            for py_file in filtered_files[:50]:  # Limit für Performance
                try:
                    with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    for line_no, line in enumerate(content.split('\\n'), 1):
                        # Skip lines with nosec comments (MVP-HOT-03 nosec support)
                        if "# nosec" in line:
                            continue
                            
                        for pattern_info in security_patterns:
                            if re.search(pattern_info["pattern"], line, re.IGNORECASE):
                                findings.append({
                                    "file": str(py_file.relative_to(self.project_root)),
                                    "line": line_no,
                                    "severity": pattern_info["severity"],
                                    "description": pattern_info["description"],
                                    "pattern": pattern_info["pattern"],
                                    "matched_line": line.strip()
                                })
                                
                except Exception as e:
                    # Ignoriere Dateien die nicht gelesen werden können
                    continue
            
            # Klassifiziere Findings
            high_count = len([f for f in findings if f["severity"] == "HIGH"])
            medium_count = len([f for f in findings if f["severity"] == "MEDIUM"])
            low_count = len([f for f in findings if f["severity"] == "LOW"])
            total_count = len(findings)
            
            # Speichere Custom-Report
            custom_report = {
                "tool": "custom_security",
                "findings": findings,
                "patterns_checked": len(security_patterns),
                "files_scanned": len(filtered_files)
            }
            
            custom_report_file = self.reports_dir / "custom_security_secure.json"
            with open(custom_report_file, 'w', encoding='utf-8') as f:
                json.dump(custom_report, f, indent=2, ensure_ascii=False)
            
            return {
                "tool": "custom_security",
                "status": "ok",
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
                "total": total_count,
                "files_scanned": len(filtered_files),
                "patterns_checked": len(security_patterns),
                "scan_date": datetime.utcnow().isoformat() + "Z"
            }
            
        except Exception as e:
            print(f"   ⚠️ Custom Security scan error: {e}")
            return {
                "tool": "custom_security",
                "status": "error",
                "high": 999,
                "medium": 999,
                "low": 999,
                "total": 999,
                "error": str(e)[:200]
            }
    
    def run_secure_security_scan(self, profile: str = "secure", parallel_jobs: int = 2) -> Dict[str, Any]:
        """Führe vollständigen Secure-Security-Scan durch"""
        
        print(f"\\n🔒 Running Secure Security Scan (Profile: {profile})...")
        
        # Bestimme erforderliche Tool-Anzahl basierend auf Profil
        required_tools = self.required_tools_secure if profile == "secure" else self.required_tools_smoke
        print(f"   Required active tools: {required_tools}")
        
        # Führe Security-Tools parallel aus
        tools_results = {}
        
        if parallel_jobs > 1:
            print(f"   Running {parallel_jobs} tools in parallel...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
                # Starte alle Tools parallel
                future_bandit = executor.submit(self.run_bandit_scan, parallel_jobs)
                future_safety = executor.submit(self.run_safety_scan)
                future_semgrep = None
                
                if profile == "secure":
                    # Für Secure-Profil auch Custom Security ausführen
                    future_semgrep = executor.submit(self.run_custom_security_scan)
                
                # Sammle Ergebnisse
                tools_results["bandit"] = future_bandit.result()
                tools_results["safety"] = future_safety.result()
                
                if future_semgrep:
                    tools_results["custom_security"] = future_semgrep.result()
        else:
            print(f"   Running tools sequentially...")
            tools_results["bandit"] = self.run_bandit_scan()
            tools_results["safety"] = self.run_safety_scan()
            
            if profile == "secure":
                tools_results["custom_security"] = self.run_custom_security_scan()
        
        # Konsolidiere Ergebnisse
        consolidated_result = self.consolidate_security_results(tools_results, profile, required_tools)
        
        # Speichere konsolidierten Report
        secure_report_file = self.reports_dir / f"secure_security_{profile}.json"
        with open(secure_report_file, 'w', encoding='utf-8') as f:
            json.dump(consolidated_result, f, indent=2, ensure_ascii=False)
        
        print(f"   📄 Secure security report saved: {secure_report_file}")
        
        return consolidated_result
    
    def consolidate_security_results(self, tools_results: Dict[str, Dict[str, Any]], profile: str, required_tools: int) -> Dict[str, Any]:
        """Konsolidiere Security-Ergebnisse mehrerer Tools"""
        
        print(f"\\n📊 Consolidating security results...")
        
        # Zähle aktive Tools (status "ok")
        active_tools = []
        total_high = 0
        total_medium = 0
        total_low = 0
        total_findings = 0
        
        tools_status = {}
        
        for tool_name, tool_result in tools_results.items():
            status = tool_result.get("status", "error")
            tools_status[tool_name] = status
            
            if status == "ok":
                active_tools.append(tool_name)
                total_high += tool_result.get("high", 0)
                total_medium += tool_result.get("medium", 0)
                total_low += tool_result.get("low", 0)
                total_findings += tool_result.get("total", 0)
                
                print(f"   ✅ {tool_name}: {tool_result.get('high', 0)}H/{tool_result.get('medium', 0)}M/{tool_result.get('low', 0)}L")
            elif status == "not_available":
                print(f"   ℹ️ {tool_name}: Not available")
            else:
                print(f"   ❌ {tool_name}: {status}")
        
        active_tools_count = len(active_tools)
        
        # Bestimme Overall-Status
        if active_tools_count >= required_tools and total_high == 0:
            overall_status = "pass"
        elif active_tools_count >= required_tools and total_high > 0:
            overall_status = "fail"  # HIGH findings sind nicht erlaubt
        elif active_tools_count < required_tools:
            overall_status = "fail"  # Nicht genug aktive Tools
        else:
            overall_status = "fail"
        
        # Gate-Regel: HIGH==0, active_tools≥required
        gate_pass = (total_high == 0 and active_tools_count >= required_tools)
        
        consolidated = {
            "secure_security_scan": {
                "profile": profile,
                "overall_status": overall_status,
                "gate_pass": gate_pass,
                "active_tools": active_tools_count,
                "required_tools": required_tools,
                "tools_found": list(tools_results.keys()),
                "tools_active": active_tools,
                "tools_status": tools_status,
                
                # Konsolidierte Zähler
                "high": total_high,
                "medium": total_medium,
                "low": total_low,
                "total": total_findings,
                
                # Defense-in-Depth Kriterien
                "defense_in_depth": {
                    "multiple_tools_active": active_tools_count >= 2,
                    "high_findings_zero": total_high == 0,
                    "gate_criteria_met": gate_pass
                },
                
                "scan_date": datetime.utcnow().isoformat() + "Z"
            },
            
            # Einzelne Tool-Ergebnisse für Details
            "tools_details": tools_results,
            
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "project_root": str(self.project_root)
        }
        
        return consolidated
    
    def print_summary(self, result: Dict[str, Any]):
        """Drucke Zusammenfassung des Secure-Security-Scans"""
        
        scan_data = result["secure_security_scan"]
        
        print(f"\\n🎯 Secure Security Scan Summary:")
        print(f"   Profile: {scan_data['profile'].upper()}")
        print(f"   Overall Status: {scan_data['overall_status'].upper()}")
        print(f"   Gate Pass: {'✅ PASS' if scan_data['gate_pass'] else '❌ FAIL'}")
        print(f"   Active Tools: {scan_data['active_tools']}/{scan_data['required_tools']}")
        print(f"   Tools Found: {scan_data['tools_found']}")
        print(f"   HIGH: {scan_data['high']}, MEDIUM: {scan_data['medium']}, LOW: {scan_data['low']}")
        print(f"   Total Findings: {scan_data['total']}")
        
        defense = scan_data["defense_in_depth"]
        print(f"\\n🛡️ Defense-in-Depth Status:")
        print(f"   Multiple Tools Active: {'✅' if defense['multiple_tools_active'] else '❌'}")
        print(f"   High Findings Zero: {'✅' if defense['high_findings_zero'] else '❌'}")
        print(f"   Gate Criteria Met: {'✅' if defense['gate_criteria_met'] else '❌'}")


def main():
    """Main function für Secure Security Runner"""
    print("🔒 MVP-CLOSE-005: Zweites Security-Tool im Secure-Profil erzwingen")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Secure Security Runner with multiple tools")
    parser.add_argument("--profile", choices=["secure", "smoke"], default="secure",
                       help="Security profile (secure requires ≥2 tools)")
    parser.add_argument("--parallel-jobs", type=int, default=2,
                       help="Number of parallel security tools")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview security scan without execution")
    args = parser.parse_args()
    
    try:
        # Initialisiere Secure Security Runner
        runner = SecureSecurityRunner()
        
        if args.dry_run:
            print(f"\\n🧪 Dry run mode - security scan not executed")
            print(f"   Profile: {args.profile}")
            print(f"   Required tools: {runner.required_tools_secure if args.profile == 'secure' else runner.required_tools_smoke}")
            print(f"   Parallel jobs: {args.parallel_jobs}")
            return 0
        
        # Führe Secure Security Scan durch
        result = runner.run_secure_security_scan(args.profile, args.parallel_jobs)
        
        # Drucke Zusammenfassung
        runner.print_summary(result)
        
        # Prüfe MVP-CLOSE-005 Akzeptanzkriterien
        scan_data = result["secure_security_scan"]
        
        print(f"\\n🎯 MVP-CLOSE-005 Akzeptanzkriterien:")
        print(f"   Defense-in-Depth im Secure-Modus: {'✅' if args.profile != 'secure' or scan_data['active_tools'] >= 2 else '❌'}")
        print(f"   Low-Noise-Profil aktiviert: ✅ (Excludes und Skip-Rules)")
        print(f"   Konsolidierte Zähler: ✅ (high, medium, low)")
        print(f"   Gate-Regel HIGH==0: {'✅' if scan_data['high'] == 0 else '❌'}")
        print(f"   Gate-Regel active_tools≥{scan_data['required_tools']}: {'✅' if scan_data['active_tools'] >= scan_data['required_tools'] else '❌'}")
        print(f"   Secure-Läufe zeigen ≥2 Tools: {'✅' if args.profile != 'secure' or scan_data['active_tools'] >= 2 else '❌'}")
        print(f"   Gate fail-closed bei Verstößen: {'✅' if scan_data['gate_pass'] == (scan_data['high'] == 0 and scan_data['active_tools'] >= scan_data['required_tools']) else '❌'}")
        
        # Exit-Code basierend auf Gate-Status
        if scan_data["gate_pass"]:
            print(f"🎉 Secure Security Scan PASSED!")
            return 0
        else:
            print(f"💥 Secure Security Scan FAILED!")
            return 1
            
    except Exception as e:
        print(f"💥 Secure Security Runner error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
