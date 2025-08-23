"""
Telemetry-Dashboard für Generator-Runs.

Erfasst Metriken pro Programmgenerator-Run: Dauer, Token, aktive Scanner,
Coverage, Erfolgsquote. Stellt eine kompakte Ansicht bereit und exportiert
als Artefakt.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

from .telemetry import RunMeta


logger = logging.getLogger(__name__)


@dataclass
class GeneratorRunMetrics:
    """Generator-Run-Metriken."""
    
    # Run-Identifikation
    run_id: str
    started_at: str
    completed_at: str
    
    # Basis-Metriken
    duration_seconds: float
    success: bool
    template_type: str
    
    # Token-Metriken
    token_prompt: int = 0
    token_completion: int = 0
    total_tokens: int = 0
    
    # Scanner-Metriken
    active_scanners: List[str] = field(default_factory=list)
    security_findings: int = 0
    
    # Quality-Metriken
    coverage_percent: float = 0.0
    quality_score: float = 0.0
    
    # Build-Metriken
    build_success: bool = False
    container_success: bool = False
    e2e_success: bool = False
    
    # Artefakt-Metriken
    artifacts_created: int = 0
    artifacts_signed: int = 0
    
    # Fehler-Informationen
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "template_type": self.template_type,
            "token_prompt": self.token_prompt,
            "token_completion": self.token_completion,
            "total_tokens": self.total_tokens,
            "active_scanners": self.active_scanners,
            "security_findings": self.security_findings,
            "coverage_percent": self.coverage_percent,
            "quality_score": self.quality_score,
            "build_success": self.build_success,
            "container_success": self.container_success,
            "e2e_success": self.e2e_success,
            "artifacts_created": self.artifacts_created,
            "artifacts_signed": self.artifacts_signed,
            "error_message": self.error_message
        }


@dataclass
class DashboardSummary:
    """Dashboard-Zusammenfassung."""
    
    # Zeitraum
    period_start: str
    period_end: str
    
    # Gesamt-Statistiken
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    
    # Durchschnittswerte
    avg_duration_seconds: float = 0.0
    avg_tokens_per_run: float = 0.0
    avg_coverage_percent: float = 0.0
    avg_quality_score: float = 0.0
    
    # Template-Statistiken
    template_stats: Dict[str, int] = field(default_factory=dict)
    
    # Scanner-Statistiken
    scanner_usage: Dict[str, int] = field(default_factory=dict)
    
    # Trend-Daten
    daily_runs: List[Tuple[str, int]] = field(default_factory=list)  # (date, count)
    success_trend: List[Tuple[str, float]] = field(default_factory=list)  # (date, success_rate)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.success_rate,
            "avg_duration_seconds": self.avg_duration_seconds,
            "avg_tokens_per_run": self.avg_tokens_per_run,
            "avg_coverage_percent": self.avg_coverage_percent,
            "avg_quality_score": self.avg_quality_score,
            "template_stats": self.template_stats,
            "scanner_usage": self.scanner_usage,
            "daily_runs": self.daily_runs,
            "success_trend": self.success_trend
        }


class TelemetryDatabase:
    """Telemetrie-Datenbank."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
    
    def _init_database(self):
        """Initialisiere Datenbank."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS generator_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    template_type TEXT NOT NULL,
                    token_prompt INTEGER DEFAULT 0,
                    token_completion INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    active_scanners TEXT DEFAULT '[]',
                    security_findings INTEGER DEFAULT 0,
                    coverage_percent REAL DEFAULT 0.0,
                    quality_score REAL DEFAULT 0.0,
                    build_success BOOLEAN DEFAULT FALSE,
                    container_success BOOLEAN DEFAULT FALSE,
                    e2e_success BOOLEAN DEFAULT FALSE,
                    artifacts_created INTEGER DEFAULT 0,
                    artifacts_signed INTEGER DEFAULT 0,
                    error_message TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_started_at ON generator_runs(started_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_template_type ON generator_runs(template_type)
            """)
    
    def store_run_metrics(self, metrics: GeneratorRunMetrics):
        """Speichere Run-Metriken."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO generator_runs (
                    run_id, started_at, completed_at, duration_seconds, success, template_type,
                    token_prompt, token_completion, total_tokens, active_scanners, security_findings,
                    coverage_percent, quality_score, build_success, container_success, e2e_success,
                    artifacts_created, artifacts_signed, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.run_id,
                metrics.started_at,
                metrics.completed_at,
                metrics.duration_seconds,
                metrics.success,
                metrics.template_type,
                metrics.token_prompt,
                metrics.token_completion,
                metrics.total_tokens,
                json.dumps(metrics.active_scanners),
                metrics.security_findings,
                metrics.coverage_percent,
                metrics.quality_score,
                metrics.build_success,
                metrics.container_success,
                metrics.e2e_success,
                metrics.artifacts_created,
                metrics.artifacts_signed,
                metrics.error_message
            ))
    
    def get_runs(
        self,
        limit: Optional[int] = None,
        template_type: Optional[str] = None,
        since: Optional[str] = None
    ) -> List[GeneratorRunMetrics]:
        """Hole Generator-Runs."""
        query = "SELECT * FROM generator_runs"
        params = []
        conditions = []
        
        if template_type:
            conditions.append("template_type = ?")
            params.append(template_type)
        
        if since:
            conditions.append("started_at >= ?")
            params.append(since)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY started_at DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            runs = []
            for row in cursor.fetchall():
                runs.append(GeneratorRunMetrics(
                    run_id=row["run_id"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    duration_seconds=row["duration_seconds"],
                    success=bool(row["success"]),
                    template_type=row["template_type"],
                    token_prompt=row["token_prompt"] or 0,
                    token_completion=row["token_completion"] or 0,
                    total_tokens=row["total_tokens"] or 0,
                    active_scanners=json.loads(row["active_scanners"] or "[]"),
                    security_findings=row["security_findings"] or 0,
                    coverage_percent=row["coverage_percent"] or 0.0,
                    quality_score=row["quality_score"] or 0.0,
                    build_success=bool(row["build_success"]),
                    container_success=bool(row["container_success"]),
                    e2e_success=bool(row["e2e_success"]),
                    artifacts_created=row["artifacts_created"] or 0,
                    artifacts_signed=row["artifacts_signed"] or 0,
                    error_message=row["error_message"]
                ))
            
            return runs
    
    def get_run_count(self) -> int:
        """Hole Anzahl Runs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM generator_runs")
            return cursor.fetchone()[0]


class TelemetryCollector:
    """Telemetrie-Sammler."""
    
    def __init__(self, database: TelemetryDatabase):
        self.database = database
    
    def collect_from_run_meta(
        self,
        run_meta: RunMeta,
        template_type: str,
        success: bool,
        additional_metrics: Optional[Dict[str, Any]] = None
    ) -> GeneratorRunMetrics:
        """Sammle Metriken aus RunMeta."""
        # Berechne Dauer
        started_dt = datetime.fromisoformat(run_meta.started_at.replace('Z', '+00:00'))
        completed_dt = datetime.utcnow()
        duration = (completed_dt - started_dt).total_seconds()
        
        # Erstelle Metriken
        metrics = GeneratorRunMetrics(
            run_id=run_meta.run_id,
            started_at=run_meta.started_at,
            completed_at=completed_dt.isoformat(),
            duration_seconds=duration,
            success=success,
            template_type=template_type,
            token_prompt=run_meta.token_prompt,
            token_completion=run_meta.token_completion,
            total_tokens=run_meta.total_tokens,
            active_scanners=run_meta.tools.copy()
        )
        
        # Zusätzliche Metriken
        if additional_metrics:
            metrics.security_findings = additional_metrics.get("security_findings", 0)
            metrics.coverage_percent = additional_metrics.get("coverage_percent", 0.0)
            metrics.quality_score = additional_metrics.get("quality_score", 0.0)
            metrics.build_success = additional_metrics.get("build_success", False)
            metrics.container_success = additional_metrics.get("container_success", False)
            metrics.e2e_success = additional_metrics.get("e2e_success", False)
            metrics.artifacts_created = additional_metrics.get("artifacts_created", 0)
            metrics.artifacts_signed = additional_metrics.get("artifacts_signed", 0)
            metrics.error_message = additional_metrics.get("error_message")
        
        return metrics
    
    def collect_from_directory(
        self,
        run_directory: Path,
        template_type: str,
        success: bool
    ) -> Optional[GeneratorRunMetrics]:
        """Sammle Metriken aus Run-Verzeichnis."""
        # Lade RunMeta
        run_meta_path = run_directory / "reports" / "run_meta.json"
        if not run_meta_path.exists():
            logger.warning(f"No run_meta.json found in {run_directory}")
            return None
        
        try:
            with run_meta_path.open('r') as f:
                run_meta_data = json.load(f)
            
            # Erstelle RunMeta-Objekt
            run_meta = RunMeta(
                run_id=run_meta_data["run_id"],
                started_at=run_meta_data["started_at"],
                seed=run_meta_data.get("seed", 0),
                model=run_meta_data.get("model", "unknown"),
                temperature=run_meta_data.get("temperature", 0.0),
                token_prompt=run_meta_data.get("token_prompt", 0),
                token_completion=run_meta_data.get("token_completion", 0),
                tools=run_meta_data.get("tools", [])
            )
            
            # Sammle zusätzliche Metriken
            additional_metrics = self._collect_additional_metrics(run_directory)
            
            return self.collect_from_run_meta(run_meta, template_type, success, additional_metrics)
            
        except Exception as e:
            logger.error(f"Failed to collect metrics from {run_directory}: {e}")
            return None
    
    def _collect_additional_metrics(self, run_directory: Path) -> Dict[str, Any]:
        """Sammle zusätzliche Metriken aus Run-Verzeichnis."""
        metrics = {}
        reports_dir = run_directory / "reports"
        
        # Security-Metriken
        security_report_path = reports_dir / "security_report.json"
        if security_report_path.exists():
            try:
                with security_report_path.open('r') as f:
                    security_data = json.load(f)
                
                summary = security_data.get("summary", {})
                metrics["security_findings"] = summary.get("total_findings", 0)
                
            except Exception as e:
                logger.debug(f"Failed to read security report: {e}")
        
        # Coverage-Metriken
        coverage_path = reports_dir / "coverage.xml"
        if coverage_path.exists():
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(coverage_path)
                root = tree.getroot()
                
                line_rate = root.get("line-rate", "0.0")
                metrics["coverage_percent"] = float(line_rate) * 100
                
            except Exception as e:
                logger.debug(f"Failed to read coverage report: {e}")
        
        # QA-Scorecard-Metriken
        qa_summary_path = reports_dir / "qa_summary.json"
        if qa_summary_path.exists():
            try:
                with qa_summary_path.open('r') as f:
                    qa_data = json.load(f)
                
                metrics["quality_score"] = qa_data.get("overall_score", 0.0)
                
            except Exception as e:
                logger.debug(f"Failed to read QA summary: {e}")
        
        # Artefakt-Zählung
        artifacts = list(run_directory.rglob("*.whl")) + list(run_directory.rglob("*.tar.gz"))
        metrics["artifacts_created"] = len(artifacts)
        
        signatures = list(run_directory.rglob("*.sig"))
        metrics["artifacts_signed"] = len(signatures)
        
        # Build-Status aus Logs (vereinfacht)
        metrics["build_success"] = len(artifacts) > 0
        metrics["container_success"] = any("container" in str(f) for f in run_directory.rglob("*"))
        metrics["e2e_success"] = (reports_dir / "e2e_report.json").exists()
        
        return metrics


class TelemetryDashboard:
    """Telemetrie-Dashboard."""
    
    def __init__(self, database: TelemetryDatabase):
        self.database = database
        self.collector = TelemetryCollector(database)
    
    def generate_summary(
        self,
        days: int = 30,
        template_type: Optional[str] = None
    ) -> DashboardSummary:
        """Generiere Dashboard-Zusammenfassung."""
        # Berechne Zeitraum
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Hole Runs
        runs = self.database.get_runs(
            template_type=template_type,
            since=start_date.isoformat()
        )
        
        summary = DashboardSummary(
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            total_runs=len(runs)
        )
        
        if not runs:
            return summary
        
        # Basis-Statistiken
        successful_runs = [r for r in runs if r.success]
        summary.successful_runs = len(successful_runs)
        summary.failed_runs = summary.total_runs - summary.successful_runs
        summary.success_rate = (summary.successful_runs / summary.total_runs) * 100
        
        # Durchschnittswerte
        durations = [r.duration_seconds for r in runs]
        tokens = [r.total_tokens for r in runs if r.total_tokens > 0]
        coverages = [r.coverage_percent for r in runs if r.coverage_percent > 0]
        qualities = [r.quality_score for r in runs if r.quality_score > 0]
        
        summary.avg_duration_seconds = statistics.mean(durations) if durations else 0.0
        summary.avg_tokens_per_run = statistics.mean(tokens) if tokens else 0.0
        summary.avg_coverage_percent = statistics.mean(coverages) if coverages else 0.0
        summary.avg_quality_score = statistics.mean(qualities) if qualities else 0.0
        
        # Template-Statistiken
        for run in runs:
            template = run.template_type
            summary.template_stats[template] = summary.template_stats.get(template, 0) + 1
        
        # Scanner-Statistiken
        for run in runs:
            for scanner in run.active_scanners:
                summary.scanner_usage[scanner] = summary.scanner_usage.get(scanner, 0) + 1
        
        # Trend-Daten
        summary.daily_runs = self._calculate_daily_runs(runs)
        summary.success_trend = self._calculate_success_trend(runs)
        
        return summary
    
    def _calculate_daily_runs(self, runs: List[GeneratorRunMetrics]) -> List[Tuple[str, int]]:
        """Berechne tägliche Run-Anzahl."""
        daily_counts = {}
        
        for run in runs:
            try:
                date = datetime.fromisoformat(run.started_at.replace('Z', '+00:00')).date()
                date_str = date.isoformat()
                daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
            except Exception:
                continue
        
        return sorted(daily_counts.items())
    
    def _calculate_success_trend(self, runs: List[GeneratorRunMetrics]) -> List[Tuple[str, float]]:
        """Berechne Erfolgsquote-Trend."""
        daily_success = {}
        
        for run in runs:
            try:
                date = datetime.fromisoformat(run.started_at.replace('Z', '+00:00')).date()
                date_str = date.isoformat()
                
                if date_str not in daily_success:
                    daily_success[date_str] = {"total": 0, "successful": 0}
                
                daily_success[date_str]["total"] += 1
                if run.success:
                    daily_success[date_str]["successful"] += 1
                    
            except Exception:
                continue
        
        # Berechne Erfolgsquoten
        success_rates = []
        for date_str, counts in daily_success.items():
            success_rate = (counts["successful"] / counts["total"]) * 100 if counts["total"] > 0 else 0
            success_rates.append((date_str, success_rate))
        
        return sorted(success_rates)
    
    def generate_html_dashboard(self, summary: DashboardSummary) -> str:
        """Generiere HTML-Dashboard."""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generator Telemetry Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #3498db; }}
        .stat-label {{ color: #7f8c8d; margin-top: 5px; }}
        .chart-container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .template-stats {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .template-badge {{ background: #3498db; color: white; padding: 5px 10px; border-radius: 15px; font-size: 0.9em; }}
        .success-rate {{ color: #27ae60; }}
        .failure-rate {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔬 Generator Telemetry Dashboard</h1>
            <p>Period: {summary.period_start[:10]} to {summary.period_end[:10]}</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{summary.total_runs}</div>
                <div class="stat-label">Total Runs</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-value success-rate">{summary.success_rate:.1f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-value">{summary.avg_duration_seconds:.1f}s</div>
                <div class="stat-label">Avg Duration</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-value">{summary.avg_tokens_per_run:.0f}</div>
                <div class="stat-label">Avg Tokens/Run</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-value">{summary.avg_coverage_percent:.1f}%</div>
                <div class="stat-label">Avg Coverage</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-value">{summary.avg_quality_score:.1f}</div>
                <div class="stat-label">Avg Quality Score</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h3>Template Usage</h3>
            <div class="template-stats">
"""
        
        for template, count in summary.template_stats.items():
            html += f'                <div class="template-badge">{template}: {count}</div>\n'
        
        html += """
            </div>
        </div>
        
        <div class="chart-container">
            <h3>Scanner Usage</h3>
            <div class="template-stats">
"""
        
        for scanner, count in summary.scanner_usage.items():
            html += f'                <div class="template-badge">{scanner}: {count}</div>\n'
        
        html += f"""
            </div>
        </div>
        
        <div class="chart-container">
            <h3>Daily Run Trend</h3>
            <p>Recent activity: {len(summary.daily_runs)} days with runs</p>
        </div>
        
        <div class="chart-container">
            <h3>Success Rate Trend</h3>
            <p>Latest success rate: {summary.success_trend[-1][1]:.1f}% (last recorded day)</p>
        </div>
        
        <div class="chart-container">
            <h3>Export</h3>
            <p>Dashboard generated at: {datetime.utcnow().isoformat()}</p>
            <p>Total data points: {summary.total_runs} runs</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def export_dashboard_artifacts(self, output_dir: Path) -> List[Path]:
        """Exportiere Dashboard-Artefakte."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        artifacts = []
        
        # Generiere Summary
        summary = self.generate_summary()
        
        # JSON-Export
        json_path = output_dir / "telemetry_summary.json"
        with json_path.open('w') as f:
            json.dump(summary.to_dict(), f, indent=2)
        artifacts.append(json_path)
        
        # HTML-Dashboard
        html_path = output_dir / "telemetry_dashboard.html"
        html_content = self.generate_html_dashboard(summary)
        html_path.write_text(html_content, encoding='utf-8')
        artifacts.append(html_path)
        
        # CSV-Export der letzten Runs
        csv_path = output_dir / "recent_runs.csv"
        recent_runs = self.database.get_runs(limit=100)
        self._export_runs_to_csv(recent_runs, csv_path)
        artifacts.append(csv_path)
        
        logger.info(f"Exported {len(artifacts)} dashboard artifacts to {output_dir}")
        return artifacts
    
    def _export_runs_to_csv(self, runs: List[GeneratorRunMetrics], csv_path: Path):
        """Exportiere Runs zu CSV."""
        import csv
        
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                "run_id", "started_at", "duration_seconds", "success", "template_type",
                "total_tokens", "active_scanners", "coverage_percent", "quality_score",
                "build_success", "container_success", "e2e_success", "artifacts_created"
            ])
            
            # Daten
            for run in runs:
                writer.writerow([
                    run.run_id,
                    run.started_at,
                    run.duration_seconds,
                    run.success,
                    run.template_type,
                    run.total_tokens,
                    ','.join(run.active_scanners),
                    run.coverage_percent,
                    run.quality_score,
                    run.build_success,
                    run.container_success,
                    run.e2e_success,
                    run.artifacts_created
                ])


# Convenience Functions
def create_telemetry_dashboard(db_path: Optional[Path] = None) -> TelemetryDashboard:
    """
    Convenience-Funktion für Telemetry-Dashboard-Erstellung.
    
    Args:
        db_path: Pfad zur Telemetrie-Datenbank
        
    Returns:
        Telemetry-Dashboard-Instanz
    """
    if db_path is None:
        db_path = Path.cwd() / "reports" / "telemetry.db"
    
    database = TelemetryDatabase(db_path)
    return TelemetryDashboard(database)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    def demo_telemetry_dashboard():
        print("📊 Telemetry Dashboard Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Erstelle Dashboard
            dashboard = create_telemetry_dashboard(temp_path / "telemetry.db")
            
            # Erstelle Demo-Daten
            demo_runs = [
                GeneratorRunMetrics(
                    run_id=f"run_{i}",
                    started_at=(datetime.utcnow() - timedelta(days=i)).isoformat(),
                    completed_at=(datetime.utcnow() - timedelta(days=i, hours=-1)).isoformat(),
                    duration_seconds=300 + i * 10,
                    success=i % 4 != 0,  # 75% Erfolgsquote
                    template_type=["WEB_API", "CLI", "WORKER", "BATCH_JOB"][i % 4],
                    total_tokens=100 + i * 20,
                    active_scanners=["bandit", "semgrep"][:i % 2 + 1],
                    coverage_percent=70.0 + i * 2,
                    quality_score=80.0 + i * 1.5,
                    build_success=True,
                    container_success=i % 3 != 0,
                    e2e_success=i % 2 == 0,
                    artifacts_created=3 + i % 3,
                    artifacts_signed=2 + i % 2
                )
                for i in range(10)
            ]
            
            # Speichere Demo-Daten
            for run_metrics in demo_runs:
                dashboard.database.store_run_metrics(run_metrics)
            
            print(f"Created {len(demo_runs)} demo runs")
            
            # Generiere Summary
            summary = dashboard.generate_summary(days=30)
            
            print(f"\\nDashboard Summary:")
            print(f"  Total Runs: {summary.total_runs}")
            print(f"  Success Rate: {summary.success_rate:.1f}%")
            print(f"  Avg Duration: {summary.avg_duration_seconds:.1f}s")
            print(f"  Avg Tokens: {summary.avg_tokens_per_run:.0f}")
            print(f"  Avg Coverage: {summary.avg_coverage_percent:.1f}%")
            print(f"  Avg Quality: {summary.avg_quality_score:.1f}")
            
            print(f"\\nTemplate Stats:")
            for template, count in summary.template_stats.items():
                print(f"  {template}: {count}")
            
            print(f"\\nScanner Usage:")
            for scanner, count in summary.scanner_usage.items():
                print(f"  {scanner}: {count}")
            
            # Exportiere Artefakte
            artifacts = dashboard.export_dashboard_artifacts(temp_path / "dashboard_export")
            
            print(f"\\nExported Artifacts:")
            for artifact in artifacts:
                print(f"  ✓ {artifact.name} ({artifact.stat().st_size} bytes)")
            
            return len(artifacts) > 0 and summary.total_runs > 0
    
    # Führe Demo aus
    try:
        result = demo_telemetry_dashboard()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
    
    print("\\nDemo completed!")
