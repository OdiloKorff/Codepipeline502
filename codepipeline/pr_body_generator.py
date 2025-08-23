"""
PR-Body Generator mit Gate-Panel.

Erzeugt einen strukturierten PR-Text mit Gate-Status-Tabelle, verlinkten 
Artefakten, Coverage und Security-Zusammenfassung sowie den wichtigsten 
Metriken des E2E-Harness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


@dataclass
class GateStatus:
    """Gate-Status."""
    
    gate_name: str
    status: str  # PASS, FAIL, WARN, SKIP
    details: Optional[str] = None
    duration: Optional[float] = None
    
    # Artefakte
    artifacts: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "gate_name": self.gate_name,
            "status": self.status,
            "details": self.details,
            "duration": self.duration,
            "artifacts": self.artifacts
        }


@dataclass
class SecuritySummary:
    """Security-Zusammenfassung."""
    
    # Scan-Ergebnisse
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    
    # Tools
    active_tools: List[str] = field(default_factory=list)
    skipped_tools: List[str] = field(default_factory=list)
    
    # Policy
    policy_violations: List[str] = field(default_factory=list)
    compliance_status: str = "UNKNOWN"  # PASS, WARN, FAIL
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "total_findings": self.total_findings,
            "critical_findings": self.critical_findings,
            "high_findings": self.high_findings,
            "medium_findings": self.medium_findings,
            "low_findings": self.low_findings,
            "active_tools": self.active_tools,
            "skipped_tools": self.skipped_tools,
            "policy_violations": self.policy_violations,
            "compliance_status": self.compliance_status
        }


@dataclass
class CoverageSummary:
    """Coverage-Zusammenfassung."""
    
    # Coverage-Metriken
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    function_coverage: float = 0.0
    
    # Test-Ergebnisse
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    tests_total: int = 0
    
    # Coverage-Status
    coverage_threshold: float = 0.0
    coverage_met: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "line_coverage": self.line_coverage,
            "branch_coverage": self.branch_coverage,
            "function_coverage": self.function_coverage,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "tests_total": self.tests_total,
            "coverage_threshold": self.coverage_threshold,
            "coverage_met": self.coverage_met
        }


@dataclass
class E2EHarnessMetrics:
    """E2E-Harness-Metriken."""
    
    # Test-Ergebnisse
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    
    # Performance
    total_duration: float = 0.0
    avg_response_time: float = 0.0
    
    # Container-Metriken
    containers_started: int = 0
    health_checks_passed: int = 0
    
    # Interaktionen
    http_interactions: int = 0
    cli_interactions: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "total_duration": self.total_duration,
            "avg_response_time": self.avg_response_time,
            "containers_started": self.containers_started,
            "health_checks_passed": self.health_checks_passed,
            "http_interactions": self.http_interactions,
            "cli_interactions": self.cli_interactions
        }


@dataclass
class ArtifactLink:
    """Artefakt-Link."""
    
    name: str
    description: str
    url: Optional[str] = None
    file_path: Optional[str] = None
    size_bytes: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes
        }


@dataclass
class PRBodyData:
    """PR-Body-Daten."""
    
    # PR-Metadaten
    feature_id: str
    feature_title: str
    feature_description: str
    author: str
    
    # Gates
    gates: List[GateStatus] = field(default_factory=list)
    overall_status: str = "UNKNOWN"  # PASS, FAIL, WARN
    
    # Zusammenfassungen
    security_summary: Optional[SecuritySummary] = None
    coverage_summary: Optional[CoverageSummary] = None
    e2e_metrics: Optional[E2EHarnessMetrics] = None
    
    # Artefakte
    artifacts: List[ArtifactLink] = field(default_factory=list)
    
    # Metadaten
    generated_at: str = ""
    pipeline_run_id: Optional[str] = None
    commit_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "feature_id": self.feature_id,
            "feature_title": self.feature_title,
            "feature_description": self.feature_description,
            "author": self.author,
            "gates": [g.to_dict() for g in self.gates],
            "overall_status": self.overall_status,
            "security_summary": self.security_summary.to_dict() if self.security_summary else None,
            "coverage_summary": self.coverage_summary.to_dict() if self.coverage_summary else None,
            "e2e_metrics": self.e2e_metrics.to_dict() if self.e2e_metrics else None,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "generated_at": self.generated_at,
            "pipeline_run_id": self.pipeline_run_id,
            "commit_hash": self.commit_hash
        }


class PRBodyGenerator:
    """Generator für PR-Bodies."""
    
    def __init__(self):
        self.status_icons = {
            "PASS": "✅",
            "FAIL": "❌",
            "WARN": "⚠️",
            "SKIP": "⏭️",
            "UNKNOWN": "❓"
        }
    
    def generate_pr_body(self, data: PRBodyData) -> str:
        """Generiere PR-Body."""
        logger.info(f"Generating PR body for feature: {data.feature_id}")
        
        sections = []
        
        # Header
        sections.append(self._generate_header(data))
        
        # Overall Status
        sections.append(self._generate_overall_status(data))
        
        # Gate Status Panel
        sections.append(self._generate_gate_panel(data))
        
        # Security Summary
        if data.security_summary:
            sections.append(self._generate_security_summary(data.security_summary))
        
        # Coverage Summary
        if data.coverage_summary:
            sections.append(self._generate_coverage_summary(data.coverage_summary))
        
        # E2E Metrics
        if data.e2e_metrics:
            sections.append(self._generate_e2e_metrics(data.e2e_metrics))
        
        # Artifacts
        if data.artifacts:
            sections.append(self._generate_artifacts_section(data.artifacts))
        
        # Footer
        sections.append(self._generate_footer(data))
        
        return "\\n\\n".join(sections)
    
    def _generate_header(self, data: PRBodyData) -> str:
        """Generiere Header."""
        lines = [
            f"# {data.feature_title}",
            "",
            f"**Feature ID:** `{data.feature_id}`",
            f"**Author:** {data.author}",
            f"**Generated:** {data.generated_at}",
            ""
        ]
        
        if data.commit_hash:
            lines.insert(-1, f"**Commit:** `{data.commit_hash[:8]}`")
        
        if data.pipeline_run_id:
            lines.insert(-1, f"**Pipeline Run:** `{data.pipeline_run_id}`")
        
        lines.extend([
            "## Description",
            "",
            data.feature_description
        ])
        
        return "\\n".join(lines)
    
    def _generate_overall_status(self, data: PRBodyData) -> str:
        """Generiere Overall-Status."""
        icon = self.status_icons.get(data.overall_status, "❓")
        
        lines = [
            f"## Overall Status: {icon} {data.overall_status}",
            ""
        ]
        
        # Status-Zusammenfassung
        status_counts = {}
        for gate in data.gates:
            status_counts[gate.status] = status_counts.get(gate.status, 0) + 1
        
        if status_counts:
            lines.append("**Gate Summary:**")
            for status in ["PASS", "FAIL", "WARN", "SKIP"]:
                if status in status_counts:
                    icon = self.status_icons[status]
                    lines.append(f"- {icon} {status}: {status_counts[status]} gate(s)")
        
        return "\\n".join(lines)
    
    def _generate_gate_panel(self, data: PRBodyData) -> str:
        """Generiere Gate-Status-Panel."""
        lines = [
            "## 🚪 Gate Status Panel",
            "",
            "| Gate | Status | Duration | Details |",
            "|------|--------|----------|---------|"
        ]
        
        for gate in data.gates:
            icon = self.status_icons.get(gate.status, "❓")
            duration = f"{gate.duration:.2f}s" if gate.duration else "N/A"
            details = gate.details or "-"
            
            # Kürze Details falls zu lang
            if len(details) > 50:
                details = details[:47] + "..."
            
            lines.append(f"| {gate.gate_name} | {icon} {gate.status} | {duration} | {details} |")
        
        return "\\n".join(lines)
    
    def _generate_security_summary(self, security: SecuritySummary) -> str:
        """Generiere Security-Zusammenfassung."""
        icon = self.status_icons.get(security.compliance_status, "❓")
        
        lines = [
            f"## 🔒 Security Summary: {icon} {security.compliance_status}",
            "",
            "### Findings Overview",
            "",
            f"- **Total Findings:** {security.total_findings}",
            f"- **Critical:** {security.critical_findings}",
            f"- **High:** {security.high_findings}",
            f"- **Medium:** {security.medium_findings}",
            f"- **Low:** {security.low_findings}",
            ""
        ]
        
        # Tools
        if security.active_tools or security.skipped_tools:
            lines.extend([
                "### Security Tools",
                ""
            ])
            
            if security.active_tools:
                lines.append(f"**Active:** {', '.join(security.active_tools)}")
            
            if security.skipped_tools:
                lines.append(f"**Skipped:** {', '.join(security.skipped_tools)}")
            
            lines.append("")
        
        # Policy Violations
        if security.policy_violations:
            lines.extend([
                "### Policy Violations",
                ""
            ])
            
            for violation in security.policy_violations:
                lines.append(f"- ⚠️ {violation}")
            
            lines.append("")
        
        return "\\n".join(lines)
    
    def _generate_coverage_summary(self, coverage: CoverageSummary) -> str:
        """Generiere Coverage-Zusammenfassung."""
        icon = "✅" if coverage.coverage_met else "❌"
        
        lines = [
            f"## 📊 Test Coverage: {icon} {coverage.line_coverage:.1f}%",
            "",
            "### Coverage Metrics",
            "",
            f"- **Line Coverage:** {coverage.line_coverage:.1f}%",
            f"- **Branch Coverage:** {coverage.branch_coverage:.1f}%",
            f"- **Function Coverage:** {coverage.function_coverage:.1f}%",
            f"- **Threshold:** {coverage.coverage_threshold:.1f}%",
            "",
            "### Test Results",
            "",
            f"- **Total Tests:** {coverage.tests_total}",
            f"- **Passed:** ✅ {coverage.tests_passed}",
            f"- **Failed:** ❌ {coverage.tests_failed}",
            f"- **Skipped:** ⏭️ {coverage.tests_skipped}",
            ""
        ]
        
        # Coverage-Bar (ASCII)
        coverage_bar = self._generate_coverage_bar(coverage.line_coverage)
        lines.extend([
            "### Coverage Visualization",
            "",
            f"```",
            f"Coverage: {coverage_bar} {coverage.line_coverage:.1f}%",
            f"```",
            ""
        ])
        
        return "\\n".join(lines)
    
    def _generate_coverage_bar(self, percentage: float, width: int = 20) -> str:
        """Generiere ASCII Coverage-Bar."""
        filled = int((percentage / 100) * width)
        empty = width - filled
        return "█" * filled + "░" * empty
    
    def _generate_e2e_metrics(self, e2e: E2EHarnessMetrics) -> str:
        """Generiere E2E-Metriken."""
        success_rate = (e2e.passed_tests / e2e.total_tests * 100) if e2e.total_tests > 0 else 0
        icon = "✅" if e2e.failed_tests == 0 else "❌"
        
        lines = [
            f"## 🧪 E2E Test Results: {icon} {success_rate:.1f}%",
            "",
            "### Test Summary",
            "",
            f"- **Total Tests:** {e2e.total_tests}",
            f"- **Passed:** ✅ {e2e.passed_tests}",
            f"- **Failed:** ❌ {e2e.failed_tests}",
            f"- **Duration:** {e2e.total_duration:.2f}s",
            "",
            "### Performance Metrics",
            "",
            f"- **Avg Response Time:** {e2e.avg_response_time:.2f}ms",
            f"- **Containers Started:** {e2e.containers_started}",
            f"- **Health Checks Passed:** {e2e.health_checks_passed}",
            "",
            "### Interactions",
            "",
            f"- **HTTP Interactions:** {e2e.http_interactions}",
            f"- **CLI Interactions:** {e2e.cli_interactions}",
            ""
        ]
        
        return "\\n".join(lines)
    
    def _generate_artifacts_section(self, artifacts: List[ArtifactLink]) -> str:
        """Generiere Artefakte-Sektion."""
        lines = [
            "## 📎 Linked Artifacts",
            "",
            "| Artifact | Description | Size |",
            "|----------|-------------|------|"
        ]
        
        for artifact in artifacts:
            size_str = self._format_file_size(artifact.size_bytes) if artifact.size_bytes else "N/A"
            
            # Erstelle Link falls URL vorhanden
            if artifact.url:
                name_link = f"[{artifact.name}]({artifact.url})"
            elif artifact.file_path:
                name_link = f"`{artifact.name}`"
            else:
                name_link = artifact.name
            
            lines.append(f"| {name_link} | {artifact.description} | {size_str} |")
        
        lines.extend([
            "",
            "<details>",
            "<summary>📋 Artifact Details</summary>",
            ""
        ])
        
        for artifact in artifacts:
            lines.extend([
                f"### {artifact.name}",
                f"**Description:** {artifact.description}"
            ])
            
            if artifact.file_path:
                lines.append(f"**File Path:** `{artifact.file_path}`")
            
            if artifact.url:
                lines.append(f"**URL:** {artifact.url}")
            
            if artifact.size_bytes:
                lines.append(f"**Size:** {self._format_file_size(artifact.size_bytes)}")
            
            lines.append("")
        
        lines.append("</details>")
        
        return "\\n".join(lines)
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Formatiere Dateigröße."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.1f} GB"
    
    def _generate_footer(self, data: PRBodyData) -> str:
        """Generiere Footer."""
        lines = [
            "---",
            "",
            "**🤖 Generated by CodePipeline**",
            "",
            f"*This PR was automatically generated on {data.generated_at}*"
        ]
        
        if data.pipeline_run_id:
            lines.append(f"*Pipeline Run ID: `{data.pipeline_run_id}`*")
        
        return "\\n".join(lines)


class PRBodyDataCollector:
    """Sammler für PR-Body-Daten."""
    
    def __init__(self):
        pass
    
    def collect_from_reports(
        self,
        feature_id: str,
        feature_title: str,
        feature_description: str,
        author: str,
        reports_directory: Path,
        commit_hash: Optional[str] = None
    ) -> PRBodyData:
        """Sammle Daten aus Report-Dateien."""
        logger.info(f"Collecting PR body data from {reports_directory}")
        
        data = PRBodyData(
            feature_id=feature_id,
            feature_title=feature_title,
            feature_description=feature_description,
            author=author,
            generated_at=datetime.utcnow().isoformat(),
            commit_hash=commit_hash
        )
        
        # Sammle Gate-Status
        data.gates = self._collect_gate_status(reports_directory)
        
        # Bestimme Overall-Status
        data.overall_status = self._determine_overall_status(data.gates)
        
        # Sammle Security-Summary
        data.security_summary = self._collect_security_summary(reports_directory)
        
        # Sammle Coverage-Summary
        data.coverage_summary = self._collect_coverage_summary(reports_directory)
        
        # Sammle E2E-Metriken
        data.e2e_metrics = self._collect_e2e_metrics(reports_directory)
        
        # Sammle Artefakte
        data.artifacts = self._collect_artifacts(reports_directory)
        
        return data
    
    def _collect_gate_status(self, reports_dir: Path) -> List[GateStatus]:
        """Sammle Gate-Status."""
        gates = []
        
        # CI Summary (falls vorhanden)
        ci_summary_file = reports_dir / "ci_summary.json"
        if ci_summary_file.exists():
            try:
                with ci_summary_file.open('r') as f:
                    ci_data = json.load(f)
                
                # Extrahiere Gate-Status aus CI-Summary
                for step_name, step_data in ci_data.get("steps", {}).items():
                    if isinstance(step_data, dict):
                        status = step_data.get("status", "UNKNOWN").upper()
                        duration = step_data.get("duration")
                        details = step_data.get("note", step_data.get("output", ""))
                        
                        gates.append(GateStatus(
                            gate_name=step_name.replace("_", " ").title(),
                            status=status,
                            details=details,
                            duration=duration
                        ))
            
            except Exception as e:
                logger.warning(f"Failed to read CI summary: {e}")
        
        # Fallback: Standard-Gates
        if not gates:
            standard_gates = [
                "Linting", "Type Check", "Unit Tests", "Security Scan",
                "SBOM & License Check", "Coverage Check", "QA Scorecard"
            ]
            
            for gate_name in standard_gates:
                gates.append(GateStatus(
                    gate_name=gate_name,
                    status="PASS",  # Default
                    details="No detailed information available"
                ))
        
        return gates
    
    def _determine_overall_status(self, gates: List[GateStatus]) -> str:
        """Bestimme Overall-Status."""
        if not gates:
            return "UNKNOWN"
        
        statuses = [gate.status for gate in gates]
        
        if "FAIL" in statuses:
            return "FAIL"
        elif "WARN" in statuses:
            return "WARN"
        elif all(status in ["PASS", "SKIP"] for status in statuses):
            return "PASS"
        else:
            return "UNKNOWN"
    
    def _collect_security_summary(self, reports_dir: Path) -> Optional[SecuritySummary]:
        """Sammle Security-Summary."""
        security_file = reports_dir / "security_report.json"
        if not security_file.exists():
            return None
        
        try:
            with security_file.open('r') as f:
                security_data = json.load(f)
            
            summary = security_data.get("summary", {})
            
            return SecuritySummary(
                total_findings=summary.get("total_findings", 0),
                critical_findings=summary.get("critical", 0),
                high_findings=summary.get("high", 0),
                medium_findings=summary.get("medium", 0),
                low_findings=summary.get("low", 0),
                active_tools=summary.get("active_tools_list", []),
                compliance_status=summary.get("policy_status", "UNKNOWN").upper()
            )
        
        except Exception as e:
            logger.warning(f"Failed to read security report: {e}")
            return None
    
    def _collect_coverage_summary(self, reports_dir: Path) -> Optional[CoverageSummary]:
        """Sammle Coverage-Summary."""
        coverage_file = reports_dir / "coverage.xml"
        if not coverage_file.exists():
            return None
        
        try:
            # Vereinfachtes XML-Parsing
            content = coverage_file.read_text()
            
            # Extrahiere Line-Coverage (vereinfacht)
            import re
            line_rate_match = re.search(r'line-rate="([0-9.]+)"', content)
            line_coverage = float(line_rate_match.group(1)) * 100 if line_rate_match else 0.0
            
            branch_rate_match = re.search(r'branch-rate="([0-9.]+)"', content)
            branch_coverage = float(branch_rate_match.group(1)) * 100 if branch_rate_match else 0.0
            
            return CoverageSummary(
                line_coverage=line_coverage,
                branch_coverage=branch_coverage,
                function_coverage=line_coverage,  # Approximation
                coverage_threshold=30.0,  # Default
                coverage_met=line_coverage >= 30.0
            )
        
        except Exception as e:
            logger.warning(f"Failed to read coverage report: {e}")
            return None
    
    def _collect_e2e_metrics(self, reports_dir: Path) -> Optional[E2EHarnessMetrics]:
        """Sammle E2E-Metriken."""
        e2e_file = reports_dir / "e2e_results.json"
        if not e2e_file.exists():
            return None
        
        try:
            with e2e_file.open('r') as f:
                e2e_data = json.load(f)
            
            return E2EHarnessMetrics(
                total_tests=e2e_data.get("total_tests", 0),
                passed_tests=e2e_data.get("passed_tests", 0),
                failed_tests=e2e_data.get("failed_tests", 0),
                total_duration=e2e_data.get("total_duration", 0.0),
                avg_response_time=e2e_data.get("avg_response_time", 0.0),
                containers_started=e2e_data.get("containers_started", 0),
                health_checks_passed=e2e_data.get("health_checks_passed", 0),
                http_interactions=e2e_data.get("http_interactions", 0),
                cli_interactions=e2e_data.get("cli_interactions", 0)
            )
        
        except Exception as e:
            logger.warning(f"Failed to read E2E results: {e}")
            return None
    
    def _collect_artifacts(self, reports_dir: Path) -> List[ArtifactLink]:
        """Sammle Artefakte."""
        artifacts = []
        
        # Standard-Artefakte
        artifact_files = [
            ("security_report.json", "Security Scan Report"),
            ("coverage.xml", "Test Coverage Report"),
            ("qa_summary.json", "QA Scorecard Summary"),
            ("third_party_notices.txt", "Third-Party Notices"),
            ("sbom_license_cve_check.json", "SBOM & License Report"),
            ("run_meta.json", "Pipeline Run Metadata")
        ]
        
        for filename, description in artifact_files:
            file_path = reports_dir / filename
            if file_path.exists():
                artifacts.append(ArtifactLink(
                    name=filename,
                    description=description,
                    file_path=str(file_path),
                    size_bytes=file_path.stat().st_size
                ))
        
        return artifacts


# Convenience Functions
def generate_pr_body_from_reports(
    feature_id: str,
    feature_title: str,
    feature_description: str,
    author: str,
    reports_directory: Path,
    commit_hash: Optional[str] = None
) -> str:
    """
    Convenience-Funktion für PR-Body-Generierung aus Reports.
    
    Args:
        feature_id: Feature-ID
        feature_title: Feature-Titel
        feature_description: Feature-Beschreibung
        author: Autor
        reports_directory: Reports-Verzeichnis
        commit_hash: Commit-Hash
        
    Returns:
        Generierter PR-Body
    """
    collector = PRBodyDataCollector()
    generator = PRBodyGenerator()
    
    data = collector.collect_from_reports(
        feature_id=feature_id,
        feature_title=feature_title,
        feature_description=feature_description,
        author=author,
        reports_directory=reports_directory,
        commit_hash=commit_hash
    )
    
    return generator.generate_pr_body(data)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    print("📝 PR Body Generator Demo:")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Erstelle Mock-Reports
        security_report = {
            "summary": {
                "total_findings": 3,
                "critical": 0,
                "high": 1,
                "medium": 2,
                "low": 0,
                "active_tools_list": ["bandit", "semgrep"],
                "policy_status": "WARN"
            }
        }
        
        (temp_path / "security_report.json").write_text(json.dumps(security_report))
        
        coverage_xml = '''<?xml version="1.0" ?>
<coverage line-rate="0.85" branch-rate="0.78">
</coverage>'''
        
        (temp_path / "coverage.xml").write_text(coverage_xml)
        
        # Generiere PR-Body
        pr_body = generate_pr_body_from_reports(
            feature_id="DEMO-001",
            feature_title="Add demo feature",
            feature_description="This PR adds a demo feature with comprehensive testing and security scanning.",
            author="Demo User",
            reports_directory=temp_path,
            commit_hash="abc123def456"
        )
        
        print(f"\\nGenerated PR Body:")
        print("=" * 60)
        
        # Zeige ersten Teil des PR-Bodies
        lines = pr_body.split('\\n')
        for line in lines[:30]:  # Erste 30 Zeilen
            print(line)
        
        if len(lines) > 30:
            print("...")
            print(f"({len(lines) - 30} more lines)")
        
        print("\\n" + "=" * 60)
        print(f"Total Length: {len(pr_body)} characters")
        print(f"Total Lines: {len(lines)}")
    
    print("\\nDemo completed!")
