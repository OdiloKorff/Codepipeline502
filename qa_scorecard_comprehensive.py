"""
Comprehensive QA Scorecard für CodePipeline.

Aggregiert alle Qualitäts- und Sicherheits-Inputs zu einer finalen Bewertung:
- Test-Coverage
- Linting (pylint, flake8)
- Type Checking (mypy)
- Static Analysis (Semgrep, Bandit)
- Secret Scanning
- Dependency Vulnerabilities
- License Policy
- Token Budget

Erzeugt JSON- und Markdown-Artefakte mit passed/failed Entscheidung.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

# Optional imports für Gate-Integration
try:
    from coverage_threshold_gate import CoverageThresholdGate
    from token_budget_gate import TokenBudgetGate
    GATES_AVAILABLE = True
except ImportError:
    GATES_AVAILABLE = False


class QAInput(BaseModel):
    """Einzelner QA-Input mit Metadaten."""
    name: str = Field(..., description="Name des QA-Inputs")
    value: float = Field(..., description="Numerischer Wert")
    weight: float = Field(..., description="Gewichtung für Score-Berechnung")
    passed: bool = Field(..., description="Ob dieser Input bestanden wurde")
    details: Dict[str, Any] = Field(default_factory=dict, description="Zusätzliche Details")
    hard_must: bool = Field(default=False, description="Ob dies ein Hard-Must-Kriterium ist")
    failure_reason: Optional[str] = Field(None, description="Grund für Fehlschlag")


class QAScorecardResult(BaseModel):
    """Gesamtergebnis der QA Scorecard."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    passed: bool = Field(..., description="Finale passed/failed Entscheidung")
    total_score: float = Field(..., description="Gesamt-Score (0-100)")
    score_threshold: float = Field(..., description="Erforderlicher Score-Schwellwert")
    
    # Einzelne Inputs
    inputs: List[QAInput] = Field(default_factory=list)
    
    # Hard Must Failures
    hard_must_failures: List[str] = Field(default_factory=list)
    
    # Zusammenfassung
    summary: Dict[str, Any] = Field(default_factory=dict)
    
    # Exit Code für Orchestrator
    exit_code: int = Field(..., description="Exit Code (0=Pass, 1=Fail)")


class ComprehensiveQAScorecard:
    """Umfassende QA Scorecard mit allen Inputs."""
    
    def __init__(self, config_path: str = "policies/QUALITY.yml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.inputs: List[QAInput] = []
    
    def _load_config(self) -> Dict[str, Any]:
        """Lade QA-Konfiguration."""
        if not self.config_path.exists():
            # Fallback-Konfiguration
            return {
                "hard_musts": {
                    "coverage_min": 80,
                    "tests_green": True,
                    "sast_high": 0,
                    "secret_findings": 0,
                    "budget_max": 50,
                    "type_errors": 0,
                    "lint_errors": 0
                },
                "score_threshold": 85,
                "weights": {
                    "coverage": 25,
                    "tests": 25,
                    "static": 15,
                    "sast": 15,
                    "secrets": 10,
                    "dependencies": 10,
                    "licenses": 10,
                    "types": 3,
                    "linting": 2
                },
                "licenses": {
                    "allow": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "MPL-2.0"],
                    "deny": ["GPL-3.0", "AGPL-3.0", "SSPL"]
                }
            }
        
        return yaml.safe_load(self.config_path.read_text())
    
    def run_comprehensive_scorecard(self) -> QAScorecardResult:
        """Führe komplette QA Scorecard aus."""
        print("📊 Starte umfassende QA Scorecard...")
        
        # Sammle alle Inputs
        self._collect_test_coverage()
        self._collect_test_results()
        self._collect_linting_results()
        self._collect_type_checking_results()
        self._collect_static_analysis_results()
        self._collect_secret_scan_results()
        self._collect_dependency_vulnerabilities()
        self._collect_license_compliance()
        self._collect_token_budget()
        
        # Berechne Gesamtscore
        total_score = self._calculate_total_score()
        
        # Prüfe Hard Musts
        hard_must_failures = self._check_hard_musts()
        
        # Finale Entscheidung
        passed = len(hard_must_failures) == 0 and total_score >= self.config["score_threshold"]
        exit_code = 0 if passed else 1
        
        # Erstelle Ergebnis
        result = QAScorecardResult(
            passed=passed,
            total_score=total_score,
            score_threshold=self.config["score_threshold"],
            inputs=self.inputs,
            hard_must_failures=hard_must_failures,
            summary=self._create_summary(),
            exit_code=exit_code
        )
        
        return result
    
    def _collect_test_coverage(self) -> None:
        """Sammle Test-Coverage Daten."""
        coverage_file = Path("coverage.xml")
        coverage = 0.0
        
        if coverage_file.exists():
            try:
                root = ET.parse(coverage_file).getroot()
                lines_valid = int(root.get("lines-valid", "0") or 0)
                lines_covered = int(root.get("lines-covered", "0") or 0)
                coverage = (lines_covered / max(1, lines_valid)) * 100 if lines_valid else 0.0
            except Exception as e:
                print(f"⚠️  Coverage XML Parse Error: {e}")
        
        hard_must = coverage < self.config["hard_musts"]["coverage_min"]
        
        self.inputs.append(QAInput(
            name="test_coverage",
            value=coverage,
            weight=self.config["weights"]["coverage"],
            passed=coverage >= self.config["hard_musts"]["coverage_min"],
            details={
                "coverage_percent": coverage,
                "threshold": self.config["hard_musts"]["coverage_min"],
                "file_found": coverage_file.exists()
            },
            hard_must=True,
            failure_reason=f"Coverage {coverage:.1f}% < {self.config['hard_musts']['coverage_min']}%" if hard_must else None
        ))
    
    def _collect_test_results(self) -> None:
        """Sammle Test-Ergebnisse."""
        tests_green = os.getenv("TESTS_GREEN", "false").lower() == "true"
        
        self.inputs.append(QAInput(
            name="test_results",
            value=1.0 if tests_green else 0.0,
            weight=self.config["weights"]["tests"],
            passed=tests_green,
            details={
                "tests_green": tests_green,
                "environment_variable": "TESTS_GREEN"
            },
            hard_must=True,
            failure_reason="Tests not green" if not tests_green else None
        ))
    
    def _collect_linting_results(self) -> None:
        """Sammle Linting-Ergebnisse."""
        # Versuche verschiedene Linter
        lint_score = 1.0
        lint_errors = 0
        lint_details = {}
        
        # pylint
        try:
            result = subprocess.run(
                ["pylint", "--output-format=json", ".", "--exit-zero"],
                capture_output=True, text=True, timeout=60
            )
            if result.stdout.strip():
                pylint_data = json.loads(result.stdout)
                errors = sum(1 for msg in pylint_data if msg.get("type") == "error")
                lint_errors += errors
                lint_details["pylint"] = {"errors": errors, "total_messages": len(pylint_data)}
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            lint_details["pylint"] = {"status": "not_available"}
        
        # flake8
        try:
            result = subprocess.run(
                ["flake8", ".", "--count", "--select=E9,F63,F7,F82"],
                capture_output=True, text=True, timeout=60
            )
            flake8_errors = result.returncode
            lint_errors += flake8_errors
            lint_details["flake8"] = {"errors": flake8_errors}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            lint_details["flake8"] = {"status": "not_available"}
        
        # Berechne Score basierend auf Fehlern
        if lint_errors > 0:
            lint_score = max(0.0, 1.0 - (lint_errors * 0.1))  # 10% Abzug pro Fehler
        
        hard_must_fail = lint_errors > self.config["hard_musts"].get("lint_errors", 10)
        
        self.inputs.append(QAInput(
            name="linting",
            value=lint_score,
            weight=self.config["weights"].get("linting", 2),
            passed=not hard_must_fail,
            details=lint_details,
            hard_must=True,
            failure_reason=f"Lint errors {lint_errors} > threshold" if hard_must_fail else None
        ))
    
    def _collect_type_checking_results(self) -> None:
        """Sammle Type-Checking Ergebnisse."""
        type_score = 1.0
        type_errors = 0
        type_details = {}
        
        # mypy
        try:
            result = subprocess.run(
                ["mypy", ".", "--no-error-summary"],
                capture_output=True, text=True, timeout=120
            )
            
            # Zähle Fehler in mypy Output
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                type_errors = sum(1 for line in lines if ': error:' in line)
            
            type_details["mypy"] = {
                "errors": type_errors,
                "return_code": result.returncode
            }
            
        except (FileNotFoundError, subprocess.TimeoutExpired):
            type_details["mypy"] = {"status": "not_available"}
        
        # Berechne Score
        if type_errors > 0:
            type_score = max(0.0, 1.0 - (type_errors * 0.05))  # 5% Abzug pro Fehler
        
        hard_must_fail = type_errors > self.config["hard_musts"].get("type_errors", 5)
        
        self.inputs.append(QAInput(
            name="type_checking",
            value=type_score,
            weight=self.config["weights"].get("types", 3),
            passed=not hard_must_fail,
            details=type_details,
            hard_must=True,
            failure_reason=f"Type errors {type_errors} > threshold" if hard_must_fail else None
        ))
    
    def _collect_static_analysis_results(self) -> None:
        """Sammle Static Analysis Ergebnisse."""
        # Versuche Security Scan Ergebnisse zu laden
        security_file = Path("security_scan_results.json")
        sast_score = 1.0
        sast_details = {"high": 0, "medium": 0, "low": 0}
        
        if security_file.exists():
            try:
                with open(security_file, 'r') as f:
                    security_data = json.load(f)
                
                # Extrahiere SAST Findings
                findings_by_severity = security_data.get("findings_by_severity", {})
                sast_details = {
                    "high": findings_by_severity.get("high", 0),
                    "medium": findings_by_severity.get("medium", 0),
                    "low": findings_by_severity.get("low", 0),
                    "total": security_data.get("total_findings", 0)
                }
                
                # Berechne SAST Score
                high_findings = sast_details["high"]
                med_findings = sast_details["medium"] 
                low_findings = sast_details["low"]
                
                sast_score = max(0.0, 1.0 - (high_findings * 0.5 + med_findings * 0.2 + low_findings * 0.05))
                
            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️  Security scan results parse error: {e}")
        
        hard_must_fail = sast_details["high"] > self.config["hard_musts"]["sast_high"]
        
        self.inputs.append(QAInput(
            name="static_analysis",
            value=sast_score,
            weight=self.config["weights"].get("sast", 15),
            passed=not hard_must_fail,
            details=sast_details,
            hard_must=True,
            failure_reason=f"SAST high findings {sast_details['high']} > {self.config['hard_musts']['sast_high']}" if hard_must_fail else None
        ))
    
    def _collect_secret_scan_results(self) -> None:
        """Sammle Secret Scanning Ergebnisse."""
        # Aus Security Scan oder separaten Files
        secret_findings = 0
        secret_details = {}
        
        # Versuche aus security_scan_results.json
        security_file = Path("security_scan_results.json")
        if security_file.exists():
            try:
                with open(security_file, 'r') as f:
                    security_data = json.load(f)
                
                # Zähle Secret Findings
                for finding in security_data.get("findings", []):
                    if finding.get("tool", "").startswith(("gitleaks", "trufflehog", "regex_secrets")):
                        secret_findings += 1
                
                secret_details = {
                    "source": "security_scan_results.json",
                    "total_secret_findings": secret_findings
                }
                
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Fallback: gitleaks.json
        if secret_findings == 0:
            gitleaks_file = Path("gitleaks.json")
            if gitleaks_file.exists():
                try:
                    data = json.loads(gitleaks_file.read_text())
                    secret_findings = len(data) if isinstance(data, list) else 0
                    secret_details = {"source": "gitleaks.json", "findings": secret_findings}
                except (json.JSONDecodeError, KeyError):
                    pass
        
        hard_must_fail = secret_findings > self.config["hard_musts"]["secret_findings"]
        
        self.inputs.append(QAInput(
            name="secret_scanning",
            value=1.0 if secret_findings == 0 else 0.0,
            weight=self.config["weights"].get("secrets", 10),
            passed=not hard_must_fail,
            details=secret_details,
            hard_must=True,
            failure_reason=f"Secret findings {secret_findings} > {self.config['hard_musts']['secret_findings']}" if hard_must_fail else None
        ))
    
    def _collect_dependency_vulnerabilities(self) -> None:
        """Sammle Dependency Vulnerability Daten."""
        vuln_count = 0
        vuln_details = {}
        
        # Aus Security Scan
        security_file = Path("security_scan_results.json")
        if security_file.exists():
            try:
                with open(security_file, 'r') as f:
                    security_data = json.load(f)
                
                deps_data = security_data.get("dependencies", {})
                vuln_count = deps_data.get("total_findings", 0)
                vuln_details = {
                    "source": "security_scan_results.json",
                    "vulnerabilities": vuln_count,
                    "tools": list(deps_data.get("tools", {}).keys())
                }
                
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Score: 1.0 wenn keine Vulns, sonst abgestuft
        vuln_score = 1.0 if vuln_count == 0 else max(0.0, 1.0 - (vuln_count * 0.1))
        
        self.inputs.append(QAInput(
            name="dependency_vulnerabilities",
            value=vuln_score,
            weight=self.config["weights"].get("dependencies", 10),
            passed=vuln_count == 0,
            details=vuln_details,
            hard_must=False  # Nicht hard must, aber wichtig für Score
        ))
    
    def _collect_license_compliance(self) -> None:
        """Sammle License Compliance Daten."""
        license_violations = 0
        license_details = {}
        
        # Aus Security Scan
        security_file = Path("security_scan_results.json")
        if security_file.exists():
            try:
                with open(security_file, 'r') as f:
                    security_data = json.load(f)
                
                deps_data = security_data.get("dependencies", {})
                tools_data = deps_data.get("tools", {})
                license_data = tools_data.get("licenses", {})
                license_violations = license_data.get("violations", 0)
                
                license_details = {
                    "source": "security_scan_results.json",
                    "violations": license_violations,
                    "total_packages": license_data.get("total_packages", 0)
                }
                
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Fallback: licenses.json
        if license_violations == 0:
            license_file = Path("licenses.json")
            if license_file.exists():
                try:
                    data = json.loads(license_file.read_text())
                    allow = set(self.config["licenses"]["allow"])
                    deny = set(self.config["licenses"]["deny"])
                    
                    for pkg in data:
                        lic = (pkg.get("License", "") or pkg.get("license", "")).replace(" ", "")
                        if lic in deny or (allow and lic not in allow):
                            license_violations += 1
                    
                    license_details = {
                        "source": "licenses.json",
                        "violations": license_violations,
                        "total_packages": len(data)
                    }
                    
                except (json.JSONDecodeError, KeyError):
                    pass
        
        self.inputs.append(QAInput(
            name="license_compliance",
            value=1.0 if license_violations == 0 else 0.0,
            weight=self.config["weights"].get("licenses", 10),
            passed=license_violations == 0,
            details=license_details,
            hard_must=False
        ))
    
    def _collect_token_budget(self) -> None:
        """Sammle Token Budget Informationen."""
        # Token Budget aus Environment oder Config
        token_budget_used = float(os.getenv("TOKEN_BUDGET_USED", "0"))
        token_budget_limit = float(os.getenv("TOKEN_BUDGET_LIMIT", "10000"))
        
        if token_budget_limit > 0:
            token_ratio = token_budget_used / token_budget_limit
            token_score = max(0.0, 1.0 - token_ratio)
        else:
            token_score = 1.0
            token_ratio = 0.0
        
        budget_exceeded = token_budget_used > token_budget_limit
        
        self.inputs.append(QAInput(
            name="token_budget",
            value=token_score,
            weight=2,  # Kleines Gewicht
            passed=not budget_exceeded,
            details={
                "used": token_budget_used,
                "limit": token_budget_limit,
                "ratio": token_ratio,
                "exceeded": budget_exceeded
            },
            hard_must=False
        ))
    
    def _calculate_total_score(self) -> float:
        """Berechne Gesamtscore aus allen Inputs."""
        total_score = 0.0
        total_weight = 0.0
        
        for input_item in self.inputs:
            weighted_score = input_item.value * input_item.weight
            total_score += weighted_score
            total_weight += input_item.weight
        
        # Normalisiere auf 0-100 Skala
        if total_weight > 0:
            normalized_score = (total_score / total_weight) * 100
        else:
            normalized_score = 0.0
        
        return round(normalized_score, 1)
    
    def _check_hard_musts(self) -> List[str]:
        """Prüfe alle Hard Must Kriterien."""
        failures = []
        
        for input_item in self.inputs:
            if input_item.hard_must and not input_item.passed:
                if input_item.failure_reason:
                    failures.append(input_item.failure_reason)
                else:
                    failures.append(f"{input_item.name} failed")
        
        return failures
    
    def _create_summary(self) -> Dict[str, Any]:
        """Erstelle Zusammenfassung der Ergebnisse."""
        summary = {
            "total_inputs": len(self.inputs),
            "passed_inputs": sum(1 for i in self.inputs if i.passed),
            "failed_inputs": sum(1 for i in self.inputs if not i.passed),
            "hard_must_inputs": sum(1 for i in self.inputs if i.hard_must),
            "hard_must_failures": len(self._check_hard_musts())
        }
        
        # Kategorien-Breakdown
        categories = {}
        for input_item in self.inputs:
            categories[input_item.name] = {
                "score": input_item.value,
                "weight": input_item.weight,
                "passed": input_item.passed,
                "hard_must": input_item.hard_must
            }
        
        summary["categories"] = categories
        return summary
    
    def generate_json_artifact(self, result: QAScorecardResult, output_path: str = "qa_scorecard.json") -> Path:
        """Generiere JSON-Artefakt."""
        output_file = Path(output_path)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
        
        print(f"📄 JSON-Artefakt gespeichert: {output_file}")
        return output_file
    
    def generate_markdown_artifact(self, result: QAScorecardResult, output_path: str = "qa_scorecard.md") -> Path:
        """Generiere Markdown-Artefakt."""
        output_file = Path(output_path)
        
        # Erstelle Markdown-Inhalt
        md_content = f"""# QA Scorecard Report

**Timestamp:** {result.timestamp}  
**Result:** {"✅ PASSED" if result.passed else "❌ FAILED"}  
**Score:** {result.total_score}/{result.score_threshold}  
**Exit Code:** {result.exit_code}

## Summary

- **Total Score:** {result.total_score} / {result.score_threshold}
- **Inputs Evaluated:** {result.summary['total_inputs']}
- **Passed:** {result.summary['passed_inputs']}
- **Failed:** {result.summary['failed_inputs']}
- **Hard Must Failures:** {len(result.hard_must_failures)}

## Hard Must Requirements

"""
        
        if result.hard_must_failures:
            md_content += "❌ **FAILED Hard Must Requirements:**\n\n"
            for failure in result.hard_must_failures:
                md_content += f"- {failure}\n"
        else:
            md_content += "✅ **All Hard Must Requirements Passed**\n"
        
        md_content += "\n## Detailed Results\n\n"
        
        # Tabelle mit allen Inputs
        md_content += "| Input | Score | Weight | Status | Hard Must | Details |\n"
        md_content += "|-------|-------|--------|--------|-----------|----------|\n"
        
        for input_item in result.inputs:
            status = "✅ Pass" if input_item.passed else "❌ Fail"
            hard_must = "Yes" if input_item.hard_must else "No"
            score_display = f"{input_item.value:.2f}"
            
            # Erstelle Details-String
            details_str = ""
            if input_item.failure_reason:
                details_str = input_item.failure_reason
            elif input_item.details:
                key_details = []
                for k, v in input_item.details.items():
                    if isinstance(v, (int, float, str, bool)):
                        key_details.append(f"{k}: {v}")
                details_str = "; ".join(key_details[:3])  # Limitiere auf 3 Details
            
            md_content += f"| {input_item.name} | {score_display} | {input_item.weight} | {status} | {hard_must} | {details_str} |\n"
        
        # Kategorien-Details
        md_content += "\n## Category Breakdown\n\n"
        
        categories = result.summary.get("categories", {})
        for name, data in categories.items():
            status_icon = "✅" if data["passed"] else "❌"
            hard_must_text = " (Hard Must)" if data["hard_must"] else ""
            
            md_content += f"### {status_icon} {name.replace('_', ' ').title()}{hard_must_text}\n\n"
            md_content += f"- **Score:** {data['score']:.2f}\n"
            md_content += f"- **Weight:** {data['weight']}\n"
            md_content += f"- **Status:** {'Passed' if data['passed'] else 'Failed'}\n\n"
        
        # Recommendations
        md_content += "\n## Recommendations\n\n"
        
        if not result.passed:
            md_content += "### To Pass QA Scorecard:\n\n"
            
            if result.hard_must_failures:
                md_content += "**Fix Hard Must Failures:**\n"
                for failure in result.hard_must_failures:
                    md_content += f"- {failure}\n"
                md_content += "\n"
            
            if result.total_score < result.score_threshold:
                score_gap = result.score_threshold - result.total_score
                md_content += f"**Improve Score by {score_gap:.1f} points:**\n"
                
                # Finde Inputs mit niedrigsten Scores
                failed_inputs = [i for i in result.inputs if not i.passed or i.value < 0.8]
                failed_inputs.sort(key=lambda x: x.value * x.weight)  # Sortiere nach gewichtetem Impact
                
                for input_item in failed_inputs[:3]:  # Top 3 Verbesserungsvorschläge
                    md_content += f"- Improve {input_item.name} (current: {input_item.value:.2f}, weight: {input_item.weight})\n"
        else:
            md_content += "🎉 **All requirements met!** Great job on maintaining high code quality.\n"
        
        # Footer
        md_content += f"\n---\n\n*Generated by Comprehensive QA Scorecard at {result.timestamp}*\n"
        
        # Schreibe Markdown-Datei
        output_file.write_text(md_content, encoding='utf-8')
        
        print(f"📄 Markdown-Artefakt gespeichert: {output_file}")
        return output_file


def main():
    """CLI Entry Point für QA Scorecard."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive QA Scorecard")
    parser.add_argument("--config", default="policies/QUALITY.yml", help="Config file path")
    parser.add_argument("--json-output", default="qa_scorecard.json", help="JSON output file")
    parser.add_argument("--markdown-output", default="qa_scorecard.md", help="Markdown output file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Erstelle Scorecard
    scorecard = ComprehensiveQAScorecard(config_path=args.config)
    
    # Führe Bewertung aus
    result = scorecard.run_comprehensive_scorecard()
    
    # Generiere Artefakte
    scorecard.generate_json_artifact(result, args.json_output)
    scorecard.generate_markdown_artifact(result, args.markdown_output)
    
    # Console Output
    print("\n" + "="*60)
    print("📊 QA SCORECARD ERGEBNIS")
    print("="*60)
    print(f"Result: {'✅ PASSED' if result.passed else '❌ FAILED'}")
    print(f"Score: {result.total_score} / {result.score_threshold}")
    print(f"Inputs: {result.summary['passed_inputs']}/{result.summary['total_inputs']} passed")
    
    if result.hard_must_failures:
        print(f"\n❌ Hard Must Failures ({len(result.hard_must_failures)}):")
        for failure in result.hard_must_failures:
            print(f"  - {failure}")
    
    if args.verbose:
        print("\n📋 Input Details:")
        for input_item in result.inputs:
            status = "✅" if input_item.passed else "❌"
            hard_must = " (Hard Must)" if input_item.hard_must else ""
            print(f"  {status} {input_item.name}: {input_item.value:.2f} (weight: {input_item.weight}){hard_must}")
    
    # Exit mit entsprechendem Code
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
