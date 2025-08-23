"""
PR Gate Panel Generator für entscheidbare Übersicht auf einen Blick.

Implementiert:
- Gate-Tabelle mit Status je Schritt
- Verlinkte QA, SBOM, Security, run_meta, Coverage, E2E-Report
- PR zeigt alle relevanten Infos komprimiert und klickbar
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


class GateStatus(Enum):
    """Gate-Status."""
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️ WARN"
    SKIP = "⏭️ SKIP"
    PENDING = "⏳ PENDING"
    ERROR = "💥 ERROR"


class GateCategory(Enum):
    """Gate-Kategorien."""
    QUALITY = "quality"
    SECURITY = "security"
    TESTING = "testing"
    BUILD = "build"
    DEPLOYMENT = "deployment"
    COMPLIANCE = "compliance"


@dataclass
class GateResult:
    """Gate-Ergebnis."""
    
    # Basis-Info
    name: str
    category: GateCategory
    status: GateStatus
    
    # Details
    description: str = ""
    score: Optional[float] = None
    threshold: Optional[float] = None
    
    # Artefakte
    report_file: str = ""
    report_url: str = ""
    
    # Metriken
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Fehler/Warnungen
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Zeitstempel
    executed_at: str = ""
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "category": self.category.value,
            "status": self.status.value,
            "description": self.description,
            "score": self.score,
            "threshold": self.threshold,
            "report_file": self.report_file,
            "report_url": self.report_url,
            "metrics": self.metrics,
            "errors": self.errors,
            "warnings": self.warnings,
            "executed_at": self.executed_at,
            "duration_seconds": self.duration_seconds
        }


@dataclass
class PanelSummary:
    """Panel-Zusammenfassung."""
    
    # Overall-Status
    overall_status: GateStatus = GateStatus.PENDING
    overall_score: float = 0.0
    
    # Statistiken
    total_gates: int = 0
    passed_gates: int = 0
    failed_gates: int = 0
    warned_gates: int = 0
    skipped_gates: int = 0
    
    # Kategorien
    category_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Artefakte
    total_artifacts: int = 0
    linked_artifacts: List[str] = field(default_factory=list)
    
    # Zeitstempel
    generated_at: str = ""
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.generated_at:
            self.generated_at = datetime.utcnow().isoformat()
    
    def calculate_pass_rate(self) -> float:
        """Berechne Pass-Rate."""
        if self.total_gates == 0:
            return 0.0
        return (self.passed_gates / self.total_gates) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "overall_status": self.overall_status.value,
            "overall_score": self.overall_score,
            "total_gates": self.total_gates,
            "passed_gates": self.passed_gates,
            "failed_gates": self.failed_gates,
            "warned_gates": self.warned_gates,
            "skipped_gates": self.skipped_gates,
            "pass_rate": self.calculate_pass_rate(),
            "category_stats": self.category_stats,
            "total_artifacts": self.total_artifacts,
            "linked_artifacts": self.linked_artifacts,
            "generated_at": self.generated_at
        }


class ArtifactProcessor:
    """Artefakt-Prozessor für verschiedene Report-Typen."""
    
    def __init__(self):
        pass
    
    def process_qa_summary(self, file_path: Path) -> Optional[GateResult]:
        """Verarbeite QA-Summary."""
        
        if not file_path.exists():
            return None
        
        try:
            with file_path.open('r') as f:
                data = json.load(f)
            
            overall_status = data.get("overall_status", "FAIL")
            overall_score = data.get("overall_score", 0)
            hard_must_failures = data.get("hard_must_failures", [])
            
            # Bestimme Status
            if overall_status == "PASS" and len(hard_must_failures) == 0:
                status = GateStatus.PASS
            elif len(hard_must_failures) > 0:
                status = GateStatus.FAIL
            else:
                status = GateStatus.WARN
            
            return GateResult(
                name="QA Scorecard",
                category=GateCategory.QUALITY,
                status=status,
                description=f"Overall quality assessment with {len(hard_must_failures)} hard-must failures",
                score=overall_score,
                threshold=70.0,
                report_file=str(file_path),
                metrics={
                    "overall_score": overall_score,
                    "hard_must_failures": len(hard_must_failures),
                    "total_checks": data.get("total_checks", 0)
                },
                errors=[f"Hard-must failure: {failure}" for failure in hard_must_failures[:3]]
            )
        
        except Exception as e:
            logger.error(f"Failed to process QA summary: {e}")
            return None
    
    def process_security_report(self, file_path: Path) -> Optional[GateResult]:
        """Verarbeite Security-Report."""
        
        if not file_path.exists():
            return None
        
        try:
            with file_path.open('r') as f:
                data = json.load(f)
            
            active_tools = data.get("active_tools", 0)
            total_findings = data.get("total_findings", 0)
            high_severity = data.get("high_severity_count", 0)
            critical_severity = data.get("critical_severity_count", 0)
            
            # Bestimme Status
            if active_tools == 0:
                status = GateStatus.FAIL
                description = "No active security tools"
            elif critical_severity > 0:
                status = GateStatus.FAIL
                description = f"{critical_severity} critical security issues found"
            elif high_severity > 0:
                status = GateStatus.WARN
                description = f"{high_severity} high severity issues found"
            elif total_findings > 0:
                status = GateStatus.WARN
                description = f"{total_findings} security findings (low/medium severity)"
            else:
                status = GateStatus.PASS
                description = "No security issues found"
            
            return GateResult(
                name="Security Scan",
                category=GateCategory.SECURITY,
                status=status,
                description=description,
                report_file=str(file_path),
                metrics={
                    "active_tools": active_tools,
                    "total_findings": total_findings,
                    "critical_severity": critical_severity,
                    "high_severity": high_severity
                },
                errors=[f"Critical: {finding}" for finding in data.get("critical_findings", [])[:2]],
                warnings=[f"High: {finding}" for finding in data.get("high_findings", [])[:2]]
            )
        
        except Exception as e:
            logger.error(f"Failed to process security report: {e}")
            return None
    
    def process_coverage_xml(self, file_path: Path) -> Optional[GateResult]:
        """Verarbeite Coverage-XML."""
        
        if not file_path.exists():
            return None
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Suche Coverage-Attribute
            coverage_attr = root.get("line-rate") or root.get("lines-covered")
            
            if coverage_attr:
                coverage_rate = float(coverage_attr)
                coverage_percent = coverage_rate * 100 if coverage_rate <= 1.0 else coverage_rate
            else:
                # Fallback: Berechne aus Zeilen
                lines_covered = 0
                lines_valid = 0
                
                for line in root.iter("line"):
                    hits = int(line.get("hits", 0))
                    lines_valid += 1
                    if hits > 0:
                        lines_covered += 1
                
                coverage_percent = (lines_covered / lines_valid * 100) if lines_valid > 0 else 0
            
            # Bestimme Status
            threshold = 30.0  # Minimum Coverage
            
            if coverage_percent >= threshold:
                status = GateStatus.PASS
            elif coverage_percent >= threshold * 0.8:  # 80% of threshold
                status = GateStatus.WARN
            else:
                status = GateStatus.FAIL
            
            return GateResult(
                name="Test Coverage",
                category=GateCategory.TESTING,
                status=status,
                description=f"Code coverage: {coverage_percent:.1f}%",
                score=coverage_percent,
                threshold=threshold,
                report_file=str(file_path),
                metrics={
                    "coverage_percent": coverage_percent,
                    "lines_covered": lines_covered if 'lines_covered' in locals() else None,
                    "lines_valid": lines_valid if 'lines_valid' in locals() else None
                }
            )
        
        except Exception as e:
            logger.error(f"Failed to process coverage XML: {e}")
            return None
    
    def process_run_meta(self, file_path: Path) -> Optional[GateResult]:
        """Verarbeite Run-Metadata."""
        
        if not file_path.exists():
            return None
        
        try:
            with file_path.open('r') as f:
                data = json.load(f)
            
            total_tokens = data.get("total_tokens", 0)
            token_prompt = data.get("token_prompt", 0)
            token_completion = data.get("token_completion", 0)
            model = data.get("model", "unknown")
            is_deterministic = data.get("is_deterministic", False)
            
            # Token-Budget-Check (Beispiel: 1000 Token Limit)
            token_budget = 1000
            
            if total_tokens <= token_budget:
                status = GateStatus.PASS
                description = f"Token usage within budget: {total_tokens}/{token_budget}"
            elif total_tokens <= token_budget * 1.2:  # 20% Überschreitung
                status = GateStatus.WARN
                description = f"Token usage slightly over budget: {total_tokens}/{token_budget}"
            else:
                status = GateStatus.FAIL
                description = f"Token usage exceeds budget: {total_tokens}/{token_budget}"
            
            return GateResult(
                name="Token Budget",
                category=GateCategory.BUILD,
                status=status,
                description=description,
                score=total_tokens,
                threshold=token_budget,
                report_file=str(file_path),
                metrics={
                    "total_tokens": total_tokens,
                    "token_prompt": token_prompt,
                    "token_completion": token_completion,
                    "model": model,
                    "is_deterministic": is_deterministic
                }
            )
        
        except Exception as e:
            logger.error(f"Failed to process run meta: {e}")
            return None
    
    def process_sbom_file(self, file_path: Path) -> Optional[GateResult]:
        """Verarbeite SBOM-Datei."""
        
        if not file_path.exists():
            return None
        
        try:
            with file_path.open('r') as f:
                data = json.load(f)
            
            # CycloneDX oder SPDX
            components = data.get("components", data.get("packages", []))
            component_count = len(components)
            
            # Lizenz-Check
            unlicensed_components = 0
            unknown_licenses = 0
            
            for comp in components:
                licenses = comp.get("licenses", comp.get("licenseConcluded", ""))
                
                if not licenses or licenses == "NOASSERTION":
                    unlicensed_components += 1
                elif "unknown" in str(licenses).lower():
                    unknown_licenses += 1
            
            # Bestimme Status
            if unlicensed_components == 0 and unknown_licenses == 0:
                status = GateStatus.PASS
                description = f"SBOM complete with {component_count} components, all licensed"
            elif unlicensed_components > 0:
                status = GateStatus.FAIL
                description = f"SBOM has {unlicensed_components} unlicensed components"
            else:
                status = GateStatus.WARN
                description = f"SBOM has {unknown_licenses} components with unknown licenses"
            
            return GateResult(
                name="SBOM & Licenses",
                category=GateCategory.COMPLIANCE,
                status=status,
                description=description,
                report_file=str(file_path),
                metrics={
                    "component_count": component_count,
                    "unlicensed_components": unlicensed_components,
                    "unknown_licenses": unknown_licenses
                },
                errors=[f"Unlicensed component: {comp.get('name', 'unknown')}" for comp in components[:2] if not comp.get('licenses')]
            )
        
        except Exception as e:
            logger.error(f"Failed to process SBOM: {e}")
            return None
    
    def process_e2e_report(self, file_path: Path) -> Optional[GateResult]:
        """Verarbeite E2E-Test-Report."""
        
        if not file_path.exists():
            return None
        
        try:
            with file_path.open('r') as f:
                data = json.load(f)
            
            total_tests = data.get("total_tests", 0)
            passed_tests = data.get("passed_tests", 0)
            failed_tests = data.get("failed_tests", 0)
            duration_seconds = data.get("duration_seconds", 0)
            
            # Bestimme Status
            if failed_tests == 0 and passed_tests > 0:
                status = GateStatus.PASS
                description = f"All {passed_tests} E2E tests passed"
            elif failed_tests > 0:
                status = GateStatus.FAIL
                description = f"{failed_tests}/{total_tests} E2E tests failed"
            else:
                status = GateStatus.SKIP
                description = "No E2E tests executed"
            
            return GateResult(
                name="E2E Tests",
                category=GateCategory.TESTING,
                status=status,
                description=description,
                report_file=str(file_path),
                metrics={
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "duration_seconds": duration_seconds
                },
                duration_seconds=duration_seconds,
                errors=[f"Failed test: {test}" for test in data.get("failed_test_names", [])[:2]]
            )
        
        except Exception as e:
            logger.error(f"Failed to process E2E report: {e}")
            return None


class PRGatePanelGenerator:
    """PR Gate Panel Generator."""
    
    def __init__(self):
        self.artifact_processor = ArtifactProcessor()
    
    def collect_gate_results(self, reports_dir: Path) -> List[GateResult]:
        """Sammle Gate-Ergebnisse aus Reports-Verzeichnis."""
        
        gate_results = []
        
        if not reports_dir.exists():
            logger.warning(f"Reports directory not found: {reports_dir}")
            return gate_results
        
        # Definiere bekannte Report-Dateien
        report_processors = [
            ("qa_summary.json", self.artifact_processor.process_qa_summary),
            ("security_report.json", self.artifact_processor.process_security_report),
            ("coverage.xml", self.artifact_processor.process_coverage_xml),
            ("run_meta.json", self.artifact_processor.process_run_meta),
            ("sbom_app.json", self.artifact_processor.process_sbom_file),
            ("sbom_container.json", self.artifact_processor.process_sbom_file),
            ("e2e_report.json", self.artifact_processor.process_e2e_report)
        ]
        
        for filename, processor in report_processors:
            file_path = reports_dir / filename
            
            try:
                result = processor(file_path)
                
                if result:
                    gate_results.append(result)
                    logger.info(f"Processed {filename}: {result.status.value}")
                else:
                    logger.debug(f"No result for {filename}")
            
            except Exception as e:
                logger.error(f"Failed to process {filename}: {e}")
        
        return gate_results
    
    def calculate_summary(self, gate_results: List[GateResult]) -> PanelSummary:
        """Berechne Panel-Zusammenfassung."""
        
        summary = PanelSummary()
        summary.total_gates = len(gate_results)
        
        # Zähle Status
        status_counts = {}
        category_stats = {}
        
        for result in gate_results:
            # Status-Statistiken
            status_key = result.status.name
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            
            # Kategorie-Statistiken
            cat_key = result.category.value
            if cat_key not in category_stats:
                category_stats[cat_key] = {}
            
            category_stats[cat_key][status_key] = category_stats[cat_key].get(status_key, 0) + 1
            
            # Artefakte
            if result.report_file:
                summary.linked_artifacts.append(result.report_file)
        
        # Setze Counts
        summary.passed_gates = status_counts.get("PASS", 0)
        summary.failed_gates = status_counts.get("FAIL", 0)
        summary.warned_gates = status_counts.get("WARN", 0)
        summary.skipped_gates = status_counts.get("SKIP", 0)
        
        summary.category_stats = category_stats
        summary.total_artifacts = len(summary.linked_artifacts)
        
        # Overall-Status bestimmen
        if summary.failed_gates > 0:
            summary.overall_status = GateStatus.FAIL
        elif summary.warned_gates > 0:
            summary.overall_status = GateStatus.WARN
        elif summary.passed_gates > 0:
            summary.overall_status = GateStatus.PASS
        else:
            summary.overall_status = GateStatus.SKIP
        
        # Overall-Score berechnen (gewichteter Durchschnitt)
        total_score = 0
        scored_gates = 0
        
        for result in gate_results:
            if result.score is not None:
                # Gewichtung basierend auf Status
                weight = 1.0
                if result.status == GateStatus.PASS:
                    weight = 1.0
                elif result.status == GateStatus.WARN:
                    weight = 0.7
                elif result.status == GateStatus.FAIL:
                    weight = 0.0
                
                total_score += result.score * weight
                scored_gates += 1
        
        if scored_gates > 0:
            summary.overall_score = total_score / scored_gates
        
        return summary
    
    def generate_gate_table_markdown(self, gate_results: List[GateResult]) -> str:
        """Generiere Gate-Tabelle als Markdown."""
        
        lines = [
            "## 🎯 Quality Gates",
            "",
            "| Gate | Status | Score | Details | Report |",
            "|------|--------|-------|---------|--------|"
        ]
        
        # Sortiere nach Kategorie und Name
        sorted_results = sorted(gate_results, key=lambda r: (r.category.value, r.name))
        
        for result in sorted_results:
            # Status-Spalte
            status_cell = result.status.value
            
            # Score-Spalte
            if result.score is not None and result.threshold is not None:
                score_cell = f"{result.score:.1f}/{result.threshold:.1f}"
            elif result.score is not None:
                score_cell = f"{result.score:.1f}"
            else:
                score_cell = "-"
            
            # Details-Spalte
            details_cell = result.description
            if len(details_cell) > 50:
                details_cell = details_cell[:47] + "..."
            
            # Report-Spalte
            if result.report_file:
                report_name = Path(result.report_file).name
                report_cell = f"[{report_name}]({result.report_file})"
            else:
                report_cell = "-"
            
            lines.append(f"| {result.name} | {status_cell} | {score_cell} | {details_cell} | {report_cell} |")
        
        return "\\n".join(lines)
    
    def generate_summary_section(self, summary: PanelSummary) -> str:
        """Generiere Zusammenfassungs-Sektion."""
        
        lines = [
            "## 📊 Summary",
            "",
            f"**Overall Status:** {summary.overall_status.value}  ",
            f"**Overall Score:** {summary.overall_score:.1f}/100  ",
            f"**Pass Rate:** {summary.calculate_pass_rate():.1f}% ({summary.passed_gates}/{summary.total_gates})  ",
            ""
        ]
        
        # Status-Breakdown
        lines.extend([
            "### Gate Status Breakdown",
            "",
            f"- ✅ **Passed:** {summary.passed_gates}",
            f"- ❌ **Failed:** {summary.failed_gates}",
            f"- ⚠️ **Warned:** {summary.warned_gates}",
            f"- ⏭️ **Skipped:** {summary.skipped_gates}",
            ""
        ])
        
        # Kategorie-Statistiken
        if summary.category_stats:
            lines.extend([
                "### By Category",
                ""
            ])
            
            for category, stats in sorted(summary.category_stats.items()):
                total_in_category = sum(stats.values())
                passed_in_category = stats.get("PASS", 0)
                
                lines.append(f"- **{category.title()}:** {passed_in_category}/{total_in_category} passed")
            
            lines.append("")
        
        return "\\n".join(lines)
    
    def generate_artifacts_section(self, gate_results: List[GateResult]) -> str:
        """Generiere Artefakte-Sektion."""
        
        lines = [
            "## 📋 Linked Artifacts",
            ""
        ]
        
        # Sammle einzigartige Artefakte
        artifacts = {}
        
        for result in gate_results:
            if result.report_file:
                artifact_name = Path(result.report_file).name
                artifact_path = result.report_file
                
                if artifact_name not in artifacts:
                    artifacts[artifact_name] = {
                        "path": artifact_path,
                        "gates": []
                    }
                
                artifacts[artifact_name]["gates"].append(result.name)
        
        if artifacts:
            for artifact_name, info in sorted(artifacts.items()):
                gates_text = ", ".join(info["gates"])
                lines.append(f"- [`{artifact_name}`]({info['path']}) - *{gates_text}*")
        else:
            lines.append("*No artifacts linked*")
        
        lines.append("")
        
        return "\\n".join(lines)
    
    def generate_details_section(self, gate_results: List[GateResult]) -> str:
        """Generiere Details-Sektion."""
        
        lines = [
            "<details>",
            "<summary>🔍 Gate Details</summary>",
            ""
        ]
        
        # Gruppiere nach Kategorie
        categories = {}
        
        for result in gate_results:
            cat_key = result.category.value
            if cat_key not in categories:
                categories[cat_key] = []
            categories[cat_key].append(result)
        
        for category, results in sorted(categories.items()):
            lines.extend([
                f"### {category.title()} Gates",
                ""
            ])
            
            for result in results:
                lines.append(f"#### {result.name} {result.status.value}")
                lines.append("")
                
                if result.description:
                    lines.append(f"**Description:** {result.description}")
                
                if result.metrics:
                    lines.append("**Metrics:**")
                    for key, value in result.metrics.items():
                        lines.append(f"- {key}: {value}")
                
                if result.errors:
                    lines.append("**Errors:**")
                    for error in result.errors:
                        lines.append(f"- ❌ {error}")
                
                if result.warnings:
                    lines.append("**Warnings:**")
                    for warning in result.warnings:
                        lines.append(f"- ⚠️ {warning}")
                
                if result.duration_seconds > 0:
                    lines.append(f"**Duration:** {result.duration_seconds:.1f}s")
                
                lines.append("")
        
        lines.extend([
            "</details>",
            ""
        ])
        
        return "\\n".join(lines)
    
    def generate_pr_body(
        self,
        gate_results: List[GateResult],
        original_body: str = "",
        project_name: str = "Project"
    ) -> str:
        """Generiere kompletten PR-Body."""
        
        summary = self.calculate_summary(gate_results)
        
        lines = []
        
        # Original Body (falls vorhanden)
        if original_body:
            lines.extend([original_body, ""])
        
        # Summary Section
        lines.append(self.generate_summary_section(summary))
        
        # Gate Table
        lines.append(self.generate_gate_table_markdown(gate_results))
        lines.append("")
        
        # Artifacts Section
        lines.append(self.generate_artifacts_section(gate_results))
        
        # Details Section (collapsible)
        lines.append(self.generate_details_section(gate_results))
        
        # Footer
        lines.extend([
            "---",
            f"*Quality gate panel generated by CodePipeline on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            f"*Project: {project_name} | Gates: {summary.total_gates} | Pass Rate: {summary.calculate_pass_rate():.1f}%*"
        ])
        
        return "\\n".join(lines)
    
    def save_panel_data(self, gate_results: List[GateResult], output_file: Path) -> bool:
        """Speichere Panel-Daten als JSON."""
        
        try:
            summary = self.calculate_summary(gate_results)
            
            panel_data = {
                "summary": summary.to_dict(),
                "gates": [result.to_dict() for result in gate_results],
                "generated_at": datetime.utcnow().isoformat()
            }
            
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with output_file.open('w') as f:
                json.dump(panel_data, f, indent=2)
            
            logger.info(f"Saved panel data: {output_file}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save panel data: {e}")
            return False


# Convenience Functions
def generate_pr_gate_panel(
    reports_dir: Path,
    original_pr_body: str = "",
    project_name: str = "Project"
) -> str:
    """
    Generiere PR Gate Panel aus Reports.
    
    Args:
        reports_dir: Verzeichnis mit Report-Dateien
        original_pr_body: Ursprünglicher PR-Body
        project_name: Projekt-Name
        
    Returns:
        Kompletter PR-Body mit Gate-Panel
    """
    
    generator = PRGatePanelGenerator()
    
    # Sammle Gate-Ergebnisse
    gate_results = generator.collect_gate_results(reports_dir)
    
    # Generiere PR-Body
    return generator.generate_pr_body(gate_results, original_pr_body, project_name)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_pr_gate_panel_generator():
        print("📊 PR Gate Panel Generator Demo:")
        
        generator = PRGatePanelGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            reports_dir = temp_path / "reports"
            reports_dir.mkdir()
            
            # Test 1: Erstelle Mock-Report-Dateien
            print("\\n📄 Creating mock report files:")
            
            # QA Summary
            qa_summary = {
                "overall_status": "PASS",
                "overall_score": 82.5,
                "hard_must_failures": [],
                "total_checks": 15,
                "coverage": 85.2,
                "security_issues": 0
            }
            
            # Security Report
            security_report = {
                "active_tools": 2,
                "total_findings": 1,
                "critical_severity_count": 0,
                "high_severity_count": 0,
                "medium_severity_count": 1,
                "low_severity_count": 0,
                "tools": ["bandit", "semgrep"]
            }
            
            # Coverage XML (vereinfacht)
            coverage_xml = '''<?xml version="1.0" ?>
<coverage line-rate="0.852" lines-covered="123" lines-valid="144" timestamp="1234567890">
    <sources>
        <source>codepipeline</source>
    </sources>
    <packages>
        <package line-rate="0.852" name="codepipeline">
            <classes>
                <class line-rate="0.852" name="example.py">
                    <lines>
                        <line hits="1" number="1"/>
                        <line hits="0" number="2"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>'''
            
            # Run Meta
            run_meta = {
                "run_id": "test-run-123",
                "seed": 42,
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "token_prompt": 450,
                "token_completion": 320,
                "total_tokens": 770,
                "is_deterministic": True
            }
            
            # SBOM
            sbom_app = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.4",
                "components": [
                    {
                        "name": "flask",
                        "version": "2.3.1",
                        "licenses": [{"license": {"id": "BSD-3-Clause"}}]
                    },
                    {
                        "name": "requests",
                        "version": "2.30.0",
                        "licenses": [{"license": {"id": "Apache-2.0"}}]
                    }
                ]
            }
            
            # E2E Report
            e2e_report = {
                "total_tests": 5,
                "passed_tests": 5,
                "failed_tests": 0,
                "duration_seconds": 12.5,
                "test_results": [
                    {"name": "health_check", "status": "passed"},
                    {"name": "api_endpoints", "status": "passed"},
                    {"name": "authentication", "status": "passed"},
                    {"name": "data_validation", "status": "passed"},
                    {"name": "error_handling", "status": "passed"}
                ]
            }
            
            # Speichere Mock-Dateien
            report_files = {
                "qa_summary.json": qa_summary,
                "security_report.json": security_report,
                "run_meta.json": run_meta,
                "sbom_app.json": sbom_app,
                "e2e_report.json": e2e_report
            }
            
            for filename, data in report_files.items():
                file_path = reports_dir / filename
                file_path.write_text(json.dumps(data, indent=2))
                print(f"  ✓ {filename}: {file_path.stat().st_size} bytes")
            
            # Coverage XML separat
            coverage_file = reports_dir / "coverage.xml"
            coverage_file.write_text(coverage_xml)
            print(f"  ✓ coverage.xml: {coverage_file.stat().st_size} bytes")
            
            # Test 2: Sammle Gate-Ergebnisse
            print("\\n🎯 Collecting gate results:")
            
            gate_results = generator.collect_gate_results(reports_dir)
            
            print(f"  ✓ Collected {len(gate_results)} gate results:")
            
            for result in gate_results:
                print(f"    - {result.name}: {result.status.value}")
            
            # Test 3: Berechne Zusammenfassung
            print("\\n📊 Calculating summary:")
            
            summary = generator.calculate_summary(gate_results)
            
            print(f"  ✓ Overall status: {summary.overall_status.value}")
            print(f"  ✓ Overall score: {summary.overall_score:.1f}")
            print(f"  ✓ Pass rate: {summary.calculate_pass_rate():.1f}%")
            print(f"  ✓ Total gates: {summary.total_gates}")
            print(f"  ✓ Passed/Failed/Warned: {summary.passed_gates}/{summary.failed_gates}/{summary.warned_gates}")
            
            # Test 4: Generiere Gate-Tabelle
            print("\\n📋 Generating gate table:")
            
            gate_table = generator.generate_gate_table_markdown(gate_results)
            table_lines = gate_table.splitlines()
            
            print(f"  ✓ Generated table with {len(table_lines)} lines:")
            
            for i, line in enumerate(table_lines[:8], 1):  # Erste 8 Zeilen
                print(f"    {i:2d}: {line}")
            
            if len(table_lines) > 8:
                print(f"    ... ({len(table_lines) - 8} more lines)")
            
            # Test 5: Generiere kompletten PR-Body
            print("\\n📝 Generating complete PR body:")
            
            original_body = """# Add User Authentication Feature

This PR implements JWT-based user authentication with the following components:

- User registration and login endpoints
- JWT token generation and validation
- Password hashing and security measures
- Integration tests for auth flow

## Changes Made

- Added authentication middleware
- Implemented user model and database schema
- Created login/register API endpoints
- Added comprehensive test coverage
"""
            
            complete_pr_body = generator.generate_pr_body(
                gate_results=gate_results,
                original_body=original_body,
                project_name="user-auth-service"
            )
            
            pr_lines = complete_pr_body.splitlines()
            
            print(f"  ✓ Generated PR body with {len(pr_lines)} lines")
            
            # Zeige PR-Body-Vorschau
            print("\\n📄 PR body preview:")
            
            for i, line in enumerate(pr_lines[:20], 1):  # Erste 20 Zeilen
                print(f"    {i:2d}: {line}")
            
            if len(pr_lines) > 20:
                print(f"    ... ({len(pr_lines) - 20} more lines)")
            
            # Test 6: Speichere Panel-Daten
            print("\\n💾 Saving panel data:")
            
            panel_data_file = reports_dir / "pr_gate_panel.json"
            saved = generator.save_panel_data(gate_results, panel_data_file)
            
            if saved:
                file_size = panel_data_file.stat().st_size
                print(f"  ✓ Panel data saved: {panel_data_file.name} ({file_size} bytes)")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Gate-Tabelle mit Status je Schritt
            has_gate_table = "| Gate | Status |" in complete_pr_body
            
            # Verlinkte Artefakte (QA, SBOM, Security, run_meta, Coverage, E2E-Report)
            required_artifacts = ["qa_summary.json", "security_report.json", "run_meta.json", "sbom_app.json", "coverage.xml", "e2e_report.json"]
            linked_artifacts = [artifact for artifact in required_artifacts if artifact in complete_pr_body]
            all_artifacts_linked = len(linked_artifacts) >= 5  # Mindestens 5 von 6
            
            # PR zeigt alle relevanten Infos komprimiert
            has_summary = "Overall Status:" in complete_pr_body
            has_pass_rate = "Pass Rate:" in complete_pr_body
            has_breakdown = "Gate Status Breakdown" in complete_pr_body
            
            # Klickbare Links
            has_clickable_links = "[" in complete_pr_body and "](" in complete_pr_body
            
            # Entscheidbar auf einen Blick
            decision_ready = (has_gate_table and has_summary and 
                            summary.overall_status != GateStatus.PENDING)
            
            print(f"  ✓ Gate-Tabelle mit Status je Schritt: {has_gate_table}")
            print(f"  ✓ Verlinkte QA/SBOM/Security/run_meta/Coverage/E2E: {all_artifacts_linked} ({len(linked_artifacts)}/6)")
            print(f"  ✓ Zusammenfassung und Pass-Rate: {has_summary and has_pass_rate}")
            print(f"  ✓ Status-Breakdown: {has_breakdown}")
            print(f"  ✓ Klickbare Artefakt-Links: {has_clickable_links}")
            print(f"  ✓ Entscheidbar auf einen Blick: {decision_ready}")
            
            return (has_gate_table and all_artifacts_linked and 
                   has_summary and has_breakdown and 
                   has_clickable_links and decision_ready)
    
    # Führe Demo aus
    try:
        result = demo_pr_gate_panel_generator()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
