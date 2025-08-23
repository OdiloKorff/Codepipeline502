"""
Telemetry Dashboard für Generator-Runs.

Implementiert:
- Erfassung von Dauer, Token, aktive Scanner, Coverage, Erfolgsquote, Kosten
- Kompakte Ansicht mit Trends und KPIs
- Export als Artefakt mit verschiedenen Formaten
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging


logger = logging.getLogger(__name__)


class RunStatus(Enum):
    """Run-Status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class MetricType(Enum):
    """Metrik-Typen."""
    DURATION = "duration"
    TOKENS = "tokens"
    COVERAGE = "coverage"
    COST = "cost"
    SECURITY_SCORE = "security_score"
    QUALITY_SCORE = "quality_score"
    COUNT = "count"


@dataclass
class RunMetrics:
    """Run-Metriken."""
    
    # Run-Info
    run_id: str
    timestamp: str
    status: RunStatus
    
    # Dauer
    duration_seconds: float = 0.0
    duration_breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Token-Verbrauch
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    token_cost_usd: float = 0.0
    
    # Scanner & Qualität
    active_scanners: List[str] = field(default_factory=list)
    scanner_count: int = 0
    coverage_percentage: float = 0.0
    security_score: float = 0.0
    quality_score: float = 0.0
    
    # Erfolgsquote
    total_gates: int = 0
    passed_gates: int = 0
    failed_gates: int = 0
    success_rate: float = 0.0
    
    # Komponenten-Details
    component_metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Kosten-Breakdown
    cost_breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Artefakte
    artifacts_generated: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        
        # Berechne abgeleitete Metriken
        self.scanner_count = len(self.active_scanners)
        
        if self.total_gates > 0:
            self.success_rate = (self.passed_gates / self.total_gates) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "duration_seconds": self.duration_seconds,
            "duration_breakdown": self.duration_breakdown,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "token_cost_usd": self.token_cost_usd,
            "active_scanners": self.active_scanners,
            "scanner_count": self.scanner_count,
            "coverage_percentage": self.coverage_percentage,
            "security_score": self.security_score,
            "quality_score": self.quality_score,
            "total_gates": self.total_gates,
            "passed_gates": self.passed_gates,
            "failed_gates": self.failed_gates,
            "success_rate": self.success_rate,
            "component_metrics": self.component_metrics,
            "cost_breakdown": self.cost_breakdown,
            "artifacts_generated": self.artifacts_generated
        }


@dataclass
class TrendData:
    """Trend-Daten."""
    
    metric_name: str
    time_series: List[Tuple[str, float]]  # (timestamp, value)
    trend_direction: str = "stable"  # up, down, stable
    trend_percentage: float = 0.0
    average_value: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    
    def calculate_trend(self):
        """Berechne Trend."""
        
        if len(self.time_series) < 2:
            self.trend_direction = "stable"
            return
        
        values = [value for _, value in self.time_series]
        
        self.average_value = sum(values) / len(values)
        self.min_value = min(values)
        self.max_value = max(values)
        
        # Einfacher Trend: erste Hälfte vs zweite Hälfte
        mid_point = len(values) // 2
        first_half = sum(values[:mid_point]) / mid_point if mid_point > 0 else 0
        second_half = sum(values[mid_point:]) / (len(values) - mid_point) if len(values) > mid_point else 0
        
        if second_half > first_half * 1.05:  # 5% Schwelle
            self.trend_direction = "up"
            self.trend_percentage = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
        elif second_half < first_half * 0.95:  # 5% Schwelle
            self.trend_direction = "down"
            self.trend_percentage = ((first_half - second_half) / first_half * 100) if first_half > 0 else 0
        else:
            self.trend_direction = "stable"
            self.trend_percentage = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        return {
            "metric_name": self.metric_name,
            "time_series": self.time_series,
            "trend_direction": self.trend_direction,
            "trend_percentage": self.trend_percentage,
            "average_value": self.average_value,
            "min_value": self.min_value,
            "max_value": self.max_value
        }


class TelemetryDatabase:
    """SQLite-basierte Telemetry-Datenbank."""
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path.cwd() / "telemetry" / "dashboard.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self):
        """Initialisiere Datenbank."""
        
        with sqlite3.connect(self.db_path) as conn:
            # Runs-Tabelle
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_seconds REAL,
                    total_tokens INTEGER,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    token_cost_usd REAL,
                    scanner_count INTEGER,
                    coverage_percentage REAL,
                    security_score REAL,
                    quality_score REAL,
                    total_gates INTEGER,
                    passed_gates INTEGER,
                    failed_gates INTEGER,
                    success_rate REAL,
                    raw_data TEXT
                )
            """)
            
            # Metriken-Tabelle
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    metric_type TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    timestamp TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                )
            """)
            
            # Indizes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_run_id ON metrics(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(metric_type)")
            
            conn.commit()
    
    def store_run_metrics(self, metrics: RunMetrics) -> bool:
        """Speichere Run-Metriken."""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Speichere Haupt-Run-Daten
                conn.execute("""
                    INSERT OR REPLACE INTO runs 
                    (run_id, timestamp, status, duration_seconds, total_tokens, 
                     prompt_tokens, completion_tokens, token_cost_usd, scanner_count,
                     coverage_percentage, security_score, quality_score,
                     total_gates, passed_gates, failed_gates, success_rate, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metrics.run_id,
                    metrics.timestamp,
                    metrics.status.value,
                    metrics.duration_seconds,
                    metrics.total_tokens,
                    metrics.prompt_tokens,
                    metrics.completion_tokens,
                    metrics.token_cost_usd,
                    metrics.scanner_count,
                    metrics.coverage_percentage,
                    metrics.security_score,
                    metrics.quality_score,
                    metrics.total_gates,
                    metrics.passed_gates,
                    metrics.failed_gates,
                    metrics.success_rate,
                    json.dumps(metrics.to_dict())
                ))
                
                # Lösche alte Metriken für diesen Run
                conn.execute("DELETE FROM metrics WHERE run_id = ?", (metrics.run_id,))
                
                # Speichere einzelne Metriken
                metric_inserts = []
                
                # Duration-Breakdown
                for component, duration in metrics.duration_breakdown.items():
                    metric_inserts.append((metrics.run_id, "duration", f"duration_{component}", duration, metrics.timestamp))
                
                # Cost-Breakdown
                for component, cost in metrics.cost_breakdown.items():
                    metric_inserts.append((metrics.run_id, "cost", f"cost_{component}", cost, metrics.timestamp))
                
                # Component-Metriken
                for component, component_data in metrics.component_metrics.items():
                    if isinstance(component_data, dict):
                        for metric_name, value in component_data.items():
                            if isinstance(value, (int, float)):
                                metric_inserts.append((metrics.run_id, "component", f"{component}_{metric_name}", value, metrics.timestamp))
                
                # Basis-Metriken
                basic_metrics = [
                    ("tokens", "total_tokens", metrics.total_tokens),
                    ("tokens", "prompt_tokens", metrics.prompt_tokens),
                    ("tokens", "completion_tokens", metrics.completion_tokens),
                    ("cost", "total_cost", metrics.token_cost_usd),
                    ("coverage", "coverage_percentage", metrics.coverage_percentage),
                    ("quality", "security_score", metrics.security_score),
                    ("quality", "quality_score", metrics.quality_score),
                    ("count", "scanner_count", metrics.scanner_count),
                    ("count", "success_rate", metrics.success_rate)
                ]
                
                for metric_type, metric_name, value in basic_metrics:
                    metric_inserts.append((metrics.run_id, metric_type, metric_name, value, metrics.timestamp))
                
                if metric_inserts:
                    conn.executemany("""
                        INSERT INTO metrics (run_id, metric_type, metric_name, metric_value, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """, metric_inserts)
                
                conn.commit()
            
            logger.info(f"Stored telemetry data for run {metrics.run_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to store telemetry data: {e}")
            return False
    
    def get_recent_runs(self, limit: int = 50) -> List[RunMetrics]:
        """Hole neueste Runs."""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("""
                    SELECT * FROM runs
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                
                runs = []
                
                for row in cursor.fetchall():
                    try:
                        raw_data = json.loads(row['raw_data']) if row['raw_data'] else {}
                        
                        metrics = RunMetrics(
                            run_id=row['run_id'],
                            timestamp=row['timestamp'],
                            status=RunStatus(row['status']),
                            duration_seconds=row['duration_seconds'] or 0.0,
                            total_tokens=row['total_tokens'] or 0,
                            prompt_tokens=row['prompt_tokens'] or 0,
                            completion_tokens=row['completion_tokens'] or 0,
                            token_cost_usd=row['token_cost_usd'] or 0.0,
                            scanner_count=row['scanner_count'] or 0,
                            coverage_percentage=row['coverage_percentage'] or 0.0,
                            security_score=row['security_score'] or 0.0,
                            quality_score=row['quality_score'] or 0.0,
                            total_gates=row['total_gates'] or 0,
                            passed_gates=row['passed_gates'] or 0,
                            failed_gates=row['failed_gates'] or 0,
                            success_rate=row['success_rate'] or 0.0,
                            duration_breakdown=raw_data.get('duration_breakdown', {}),
                            cost_breakdown=raw_data.get('cost_breakdown', {}),
                            component_metrics=raw_data.get('component_metrics', {}),
                            active_scanners=raw_data.get('active_scanners', []),
                            artifacts_generated=raw_data.get('artifacts_generated', [])
                        )
                        
                        runs.append(metrics)
                    
                    except Exception as e:
                        logger.warning(f"Failed to deserialize run {row['run_id']}: {e}")
                        continue
                
                return runs
        
        except Exception as e:
            logger.error(f"Failed to get recent runs: {e}")
            return []
    
    def get_trend_data(self, metric_name: str, days: int = 30) -> TrendData:
        """Hole Trend-Daten für Metrik."""
        
        try:
            since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT timestamp, metric_value
                    FROM metrics
                    WHERE metric_name = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                """, (metric_name, since_date))
                
                time_series = [(row[0], row[1]) for row in cursor.fetchall()]
                
                trend_data = TrendData(
                    metric_name=metric_name,
                    time_series=time_series
                )
                
                trend_data.calculate_trend()
                
                return trend_data
        
        except Exception as e:
            logger.error(f"Failed to get trend data for {metric_name}: {e}")
            return TrendData(metric_name=metric_name, time_series=[])
    
    def get_summary_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Hole Zusammenfassungs-Statistiken."""
        
        try:
            since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Basis-Statistiken
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_runs,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_runs,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
                        AVG(duration_seconds) as avg_duration,
                        SUM(total_tokens) as total_tokens,
                        SUM(token_cost_usd) as total_cost,
                        AVG(coverage_percentage) as avg_coverage,
                        AVG(security_score) as avg_security_score,
                        AVG(quality_score) as avg_quality_score,
                        AVG(success_rate) as avg_success_rate
                    FROM runs
                    WHERE timestamp >= ?
                """, (since_date,))
                
                stats_row = cursor.fetchone()
                
                # Top-Scanner
                cursor = conn.execute("""
                    SELECT metric_name, COUNT(*) as usage_count
                    FROM metrics
                    WHERE metric_type = 'component' AND metric_name LIKE '%_scanner_%'
                      AND timestamp >= ?
                    GROUP BY metric_name
                    ORDER BY usage_count DESC
                    LIMIT 10
                """, (since_date,))
                
                top_scanners = dict(cursor.fetchall())
                
                # Kosten-Breakdown
                cursor = conn.execute("""
                    SELECT metric_name, SUM(metric_value) as total_cost
                    FROM metrics
                    WHERE metric_type = 'cost' AND timestamp >= ?
                    GROUP BY metric_name
                    ORDER BY total_cost DESC
                """, (since_date,))
                
                cost_breakdown = dict(cursor.fetchall())
                
                return {
                    "period_days": days,
                    "total_runs": stats_row['total_runs'] or 0,
                    "successful_runs": stats_row['successful_runs'] or 0,
                    "failed_runs": stats_row['failed_runs'] or 0,
                    "success_rate": (stats_row['successful_runs'] / stats_row['total_runs'] * 100) if stats_row['total_runs'] > 0 else 0,
                    "avg_duration_seconds": stats_row['avg_duration'] or 0,
                    "total_tokens": stats_row['total_tokens'] or 0,
                    "total_cost_usd": stats_row['total_cost'] or 0,
                    "avg_coverage": stats_row['avg_coverage'] or 0,
                    "avg_security_score": stats_row['avg_security_score'] or 0,
                    "avg_quality_score": stats_row['avg_quality_score'] or 0,
                    "avg_gate_success_rate": stats_row['avg_success_rate'] or 0,
                    "top_scanners": top_scanners,
                    "cost_breakdown": cost_breakdown
                }
        
        except Exception as e:
            logger.error(f"Failed to get summary statistics: {e}")
            return {}


class DashboardRenderer:
    """Dashboard-Renderer für verschiedene Ausgabeformate."""
    
    def __init__(self):
        pass
    
    def render_compact_view(self, runs: List[RunMetrics], summary: Dict[str, Any], trends: Dict[str, TrendData]) -> str:
        """Rendere kompakte Dashboard-Ansicht."""
        
        lines = []
        
        # Header
        lines.append("📊 TELEMETRY DASHBOARD")
        lines.append("=" * 50)
        
        # Summary
        lines.append(f"\\n🎯 SUMMARY ({summary.get('period_days', 30)} days):")
        lines.append(f"  • Total Runs: {summary.get('total_runs', 0)}")
        lines.append(f"  • Success Rate: {summary.get('success_rate', 0):.1f}%")
        lines.append(f"  • Avg Duration: {summary.get('avg_duration_seconds', 0):.1f}s")
        lines.append(f"  • Total Tokens: {summary.get('total_tokens', 0):,}")
        lines.append(f"  • Total Cost: ${summary.get('total_cost_usd', 0):.2f}")
        lines.append(f"  • Avg Coverage: {summary.get('avg_coverage', 0):.1f}%")
        lines.append(f"  • Avg Security Score: {summary.get('avg_security_score', 0):.1f}")
        
        # Trends
        if trends:
            lines.append("\\n📈 TRENDS:")
            for metric_name, trend_data in trends.items():
                direction_icon = {"up": "📈", "down": "📉", "stable": "➡️"}[trend_data.trend_direction]
                lines.append(f"  • {metric_name}: {direction_icon} {trend_data.trend_direction} ({trend_data.trend_percentage:+.1f}%)")
        
        # Recent Runs
        lines.append(f"\\n🏃 RECENT RUNS (last {min(10, len(runs))}):")
        lines.append("  ID       | Status  | Duration | Tokens | Coverage | Success")
        lines.append("  ---------|---------|----------|--------|----------|--------")
        
        for run in runs[:10]:
            status_icon = {"success": "✅", "failed": "❌", "partial": "⚠️", "cancelled": "🚫"}[run.status.value]
            lines.append(f"  {run.run_id[:8]} | {status_icon:<7} | {run.duration_seconds:6.1f}s | {run.total_tokens:6} | {run.coverage_percentage:6.1f}% | {run.success_rate:6.1f}%")
        
        # Top Scanners
        if summary.get('top_scanners'):
            lines.append("\\n🔍 TOP SCANNERS:")
            for scanner, count in list(summary['top_scanners'].items())[:5]:
                lines.append(f"  • {scanner}: {count} uses")
        
        # Cost Breakdown
        if summary.get('cost_breakdown'):
            lines.append("\\n💰 COST BREAKDOWN:")
            for component, cost in list(summary['cost_breakdown'].items())[:5]:
                lines.append(f"  • {component}: ${cost:.2f}")
        
        return "\\n".join(lines)
    
    def render_html_dashboard(self, runs: List[RunMetrics], summary: Dict[str, Any], trends: Dict[str, TrendData]) -> str:
        """Rendere HTML-Dashboard."""
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Generator Telemetry Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ color: #333; border-bottom: 2px solid #007acc; padding-bottom: 10px; }}
                .summary {{ background: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background: white; border-radius: 3px; min-width: 120px; text-align: center; }}
                .trends {{ margin: 20px 0; }}
                .trend-up {{ color: green; }}
                .trend-down {{ color: red; }}
                .trend-stable {{ color: gray; }}
                .runs-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .runs-table th, .runs-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .runs-table th {{ background-color: #f2f2f2; }}
                .status-success {{ color: green; }}
                .status-failed {{ color: red; }}
                .status-partial {{ color: orange; }}
                .status-cancelled {{ color: gray; }}
            </style>
        </head>
        <body>
            <h1 class="header">📊 Generator Telemetry Dashboard</h1>
            
            <div class="summary">
                <h2>Summary ({summary.get('period_days', 30)} days)</h2>
                <div class="metric">
                    <strong>{summary.get('total_runs', 0)}</strong><br>
                    Total Runs
                </div>
                <div class="metric">
                    <strong>{summary.get('success_rate', 0):.1f}%</strong><br>
                    Success Rate
                </div>
                <div class="metric">
                    <strong>{summary.get('avg_duration_seconds', 0):.1f}s</strong><br>
                    Avg Duration
                </div>
                <div class="metric">
                    <strong>{summary.get('total_tokens', 0):,}</strong><br>
                    Total Tokens
                </div>
                <div class="metric">
                    <strong>${summary.get('total_cost_usd', 0):.2f}</strong><br>
                    Total Cost
                </div>
                <div class="metric">
                    <strong>{summary.get('avg_coverage', 0):.1f}%</strong><br>
                    Avg Coverage
                </div>
            </div>
            
            <div class="trends">
                <h2>📈 Trends</h2>
        """
        
        for metric_name, trend_data in trends.items():
            trend_class = f"trend-{trend_data.trend_direction}"
            html += f'<p class="{trend_class}"><strong>{metric_name}:</strong> {trend_data.trend_direction} ({trend_data.trend_percentage:+.1f}%)</p>'
        
        html += """
            </div>
            
            <div class="runs">
                <h2>🏃 Recent Runs</h2>
                <table class="runs-table">
                    <tr>
                        <th>Run ID</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Tokens</th>
                        <th>Coverage</th>
                        <th>Success Rate</th>
                        <th>Timestamp</th>
                    </tr>
        """
        
        for run in runs[:15]:
            status_class = f"status-{run.status.value}"
            html += f"""
                    <tr>
                        <td>{run.run_id[:12]}</td>
                        <td class="{status_class}">{run.status.value}</td>
                        <td>{run.duration_seconds:.1f}s</td>
                        <td>{run.total_tokens:,}</td>
                        <td>{run.coverage_percentage:.1f}%</td>
                        <td>{run.success_rate:.1f}%</td>
                        <td>{run.timestamp[:19]}</td>
                    </tr>
            """
        
        html += """
                </table>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def render_csv_export(self, runs: List[RunMetrics]) -> str:
        """Rendere CSV-Export."""
        
        lines = []
        
        # Header
        lines.append("run_id,timestamp,status,duration_seconds,total_tokens,prompt_tokens,completion_tokens,token_cost_usd,scanner_count,coverage_percentage,security_score,quality_score,success_rate")
        
        # Daten
        for run in runs:
            lines.append(f"{run.run_id},{run.timestamp},{run.status.value},{run.duration_seconds},{run.total_tokens},{run.prompt_tokens},{run.completion_tokens},{run.token_cost_usd},{run.scanner_count},{run.coverage_percentage},{run.security_score},{run.quality_score},{run.success_rate}")
        
        return "\\n".join(lines)


class TelemetryDashboard:
    """Haupt-Telemetry-Dashboard."""
    
    def __init__(self, db_path: Path = None):
        self.database = TelemetryDatabase(db_path)
        self.renderer = DashboardRenderer()
    
    def record_run_metrics(self, metrics: RunMetrics) -> bool:
        """Erfasse Run-Metriken."""
        return self.database.store_run_metrics(metrics)
    
    def generate_dashboard(self, days: int = 30, run_limit: int = 50) -> Dict[str, Any]:
        """Generiere Dashboard-Daten."""
        
        # Hole Daten
        recent_runs = self.database.get_recent_runs(run_limit)
        summary = self.database.get_summary_statistics(days)
        
        # Hole Trend-Daten für wichtige Metriken
        key_metrics = ["total_tokens", "coverage_percentage", "success_rate", "total_cost", "security_score"]
        trends = {}
        
        for metric in key_metrics:
            trends[metric] = self.database.get_trend_data(metric, days)
        
        # Rendere verschiedene Formate
        compact_view = self.renderer.render_compact_view(recent_runs, summary, trends)
        html_dashboard = self.renderer.render_html_dashboard(recent_runs, summary, trends)
        csv_export = self.renderer.render_csv_export(recent_runs)
        
        return {
            "summary": summary,
            "recent_runs": [run.to_dict() for run in recent_runs],
            "trends": {name: trend.to_dict() for name, trend in trends.items()},
            "compact_view": compact_view,
            "html_dashboard": html_dashboard,
            "csv_export": csv_export,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def export_dashboard_artifacts(self, output_dir: Path = None) -> List[str]:
        """Exportiere Dashboard als Artefakte."""
        
        if output_dir is None:
            output_dir = Path.cwd() / "reports" / "telemetry"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        dashboard_data = self.generate_dashboard()
        exported_files = []
        
        try:
            # Compact View (Text)
            compact_file = output_dir / "dashboard_compact.txt"
            compact_file.write_text(dashboard_data["compact_view"], encoding='utf-8')
            exported_files.append(str(compact_file))
            
            # HTML Dashboard
            html_file = output_dir / "dashboard.html"
            html_file.write_text(dashboard_data["html_dashboard"], encoding='utf-8')
            exported_files.append(str(html_file))
            
            # CSV Export
            csv_file = output_dir / "runs_export.csv"
            csv_file.write_text(dashboard_data["csv_export"], encoding='utf-8')
            exported_files.append(str(csv_file))
            
            # JSON Data
            json_file = output_dir / "dashboard_data.json"
            json_file.write_text(json.dumps(dashboard_data, indent=2), encoding='utf-8')
            exported_files.append(str(json_file))
            
            logger.info(f"Exported {len(exported_files)} dashboard artifacts to {output_dir}")
            
        except Exception as e:
            logger.error(f"Failed to export dashboard artifacts: {e}")
        
        return exported_files


# Convenience Functions
def create_telemetry_dashboard(db_path: Path = None) -> TelemetryDashboard:
    """
    Erstelle Telemetry Dashboard.
    
    Args:
        db_path: Datenbank-Pfad
        
    Returns:
        Telemetry Dashboard
    """
    
    return TelemetryDashboard(db_path)


def record_generator_run(
    dashboard: TelemetryDashboard,
    run_id: str,
    status: str,
    duration_seconds: float,
    tokens: Dict[str, int],
    quality_metrics: Dict[str, float],
    scanners: List[str],
    gates: Dict[str, int],
    costs: Dict[str, float] = None,
    artifacts: List[str] = None
) -> bool:
    """
    Erfasse Generator-Run.
    
    Args:
        dashboard: Dashboard
        run_id: Run-ID
        status: Status
        duration_seconds: Dauer
        tokens: Token-Daten
        quality_metrics: Qualitäts-Metriken
        scanners: Aktive Scanner
        gates: Gate-Statistiken
        costs: Kosten-Aufschlüsselung
        artifacts: Generierte Artefakte
        
    Returns:
        Erfolg
    """
    
    if costs is None:
        costs = {}
    
    if artifacts is None:
        artifacts = []
    
    try:
        run_status = RunStatus(status)
    except ValueError:
        run_status = RunStatus.FAILED
    
    metrics = RunMetrics(
        run_id=run_id,
        timestamp=datetime.utcnow().isoformat(),
        status=run_status,
        duration_seconds=duration_seconds,
        total_tokens=tokens.get('total', 0),
        prompt_tokens=tokens.get('prompt', 0),
        completion_tokens=tokens.get('completion', 0),
        token_cost_usd=costs.get('tokens', 0.0),
        active_scanners=scanners,
        coverage_percentage=quality_metrics.get('coverage', 0.0),
        security_score=quality_metrics.get('security_score', 0.0),
        quality_score=quality_metrics.get('quality_score', 0.0),
        total_gates=gates.get('total', 0),
        passed_gates=gates.get('passed', 0),
        failed_gates=gates.get('failed', 0),
        cost_breakdown=costs,
        artifacts_generated=artifacts
    )
    
    return dashboard.record_run_metrics(metrics)


if __name__ == "__main__":
    # Demo
    import tempfile
    import random
    
    def demo_telemetry_dashboard():
        print("📊 Telemetry Dashboard Demo:")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test 1: Erstelle Dashboard
            print("\\n🚀 Creating telemetry dashboard:")
            
            dashboard = create_telemetry_dashboard(temp_path / "dashboard.db")
            
            print(f"  ✓ Database path: {dashboard.database.db_path.name}")
            print(f"  ✓ Renderer ready")
            
            # Test 2: Simuliere mehrere Runs
            print("\\n📈 Simulating generator runs:")
            
            run_data = [
                {"status": "success", "duration": 45.2, "coverage": 85.5, "security": 78.0, "tokens": 1200},
                {"status": "success", "duration": 38.7, "coverage": 92.1, "security": 82.5, "tokens": 980},
                {"status": "failed", "duration": 15.3, "coverage": 45.2, "security": 60.0, "tokens": 450},
                {"status": "success", "duration": 52.1, "coverage": 88.7, "security": 85.2, "tokens": 1450},
                {"status": "partial", "duration": 33.8, "coverage": 76.3, "security": 71.8, "tokens": 890},
                {"status": "success", "duration": 41.5, "coverage": 94.2, "security": 89.1, "tokens": 1100},
                {"status": "success", "duration": 47.9, "coverage": 87.4, "security": 83.6, "tokens": 1320}
            ]
            
            recorded_runs = []
            
            for i, data in enumerate(run_data, 1):
                run_id = f"run_{i:03d}_{random.randint(1000, 9999)}"
                
                success = record_generator_run(
                    dashboard,
                    run_id=run_id,
                    status=data["status"],
                    duration_seconds=data["duration"],
                    tokens={
                        "total": data["tokens"],
                        "prompt": int(data["tokens"] * 0.3),
                        "completion": int(data["tokens"] * 0.7)
                    },
                    quality_metrics={
                        "coverage": data["coverage"],
                        "security_score": data["security"],
                        "quality_score": (data["coverage"] + data["security"]) / 2
                    },
                    scanners=["bandit", "semgrep", "safety"] if data["status"] == "success" else ["bandit"],
                    gates={
                        "total": 8,
                        "passed": 8 if data["status"] == "success" else (6 if data["status"] == "partial" else 3),
                        "failed": 0 if data["status"] == "success" else (2 if data["status"] == "partial" else 5)
                    },
                    costs={
                        "tokens": data["tokens"] * 0.0001,
                        "scanners": 0.05,
                        "total": data["tokens"] * 0.0001 + 0.05
                    },
                    artifacts=["source.py", "tests.py", "dockerfile", "sbom.json"] if data["status"] == "success" else []
                )
                
                if success:
                    recorded_runs.append(run_id)
                    print(f"  ✓ Run {i}: {run_id} ({data['status']}) - {data['duration']:.1f}s")
            
            print(f"  ✓ Recorded {len(recorded_runs)} runs successfully")
            
            # Test 3: Generiere Dashboard
            print("\\n📊 Generating dashboard:")
            
            dashboard_data = dashboard.generate_dashboard(days=30, run_limit=20)
            
            print(f"  ✓ Summary data: {len(dashboard_data['summary'])} metrics")
            print(f"  ✓ Recent runs: {len(dashboard_data['recent_runs'])}")
            print(f"  ✓ Trends: {len(dashboard_data['trends'])} metrics")
            print(f"  ✓ Compact view: {len(dashboard_data['compact_view'])} chars")
            print(f"  ✓ HTML dashboard: {len(dashboard_data['html_dashboard'])} chars")
            print(f"  ✓ CSV export: {len(dashboard_data['csv_export'])} chars")
            
            # Test 4: Zeige Compact View
            print("\\n📋 Dashboard compact view (preview):")
            
            compact_lines = dashboard_data["compact_view"].split("\\n")
            for line in compact_lines[:15]:  # Erste 15 Zeilen
                print(f"  {line}")
            
            if len(compact_lines) > 15:
                print(f"  ... ({len(compact_lines) - 15} more lines)")
            
            # Test 5: Exportiere Artefakte
            print("\\n💾 Exporting dashboard artifacts:")
            
            exported_files = dashboard.export_dashboard_artifacts(temp_path / "reports")
            
            for file_path in exported_files:
                file_size = Path(file_path).stat().st_size
                print(f"  ✓ {Path(file_path).name}: {file_size} bytes")
            
            # Test 6: Trend-Analyse
            print("\\n📈 Trend analysis:")
            
            for metric_name, trend_data in dashboard_data["trends"].items():
                direction = trend_data["trend_direction"]
                percentage = trend_data["trend_percentage"]
                
                direction_icon = {"up": "📈", "down": "📉", "stable": "➡️"}[direction]
                print(f"  {direction_icon} {metric_name}: {direction} ({percentage:+.1f}%)")
            
            # Test Akzeptanz-Kriterien
            print("\\n🎯 Acceptance criteria:")
            
            # Erfassung von Dauer, Token, Scanner, Coverage, Erfolgsquote, Kosten
            summary = dashboard_data["summary"]
            metrics_captured = all([
                summary.get("avg_duration_seconds", 0) > 0,
                summary.get("total_tokens", 0) > 0,
                len(summary.get("top_scanners", {})) > 0,
                summary.get("avg_coverage", 0) > 0,
                summary.get("success_rate", 0) >= 0,
                summary.get("total_cost_usd", 0) > 0
            ])
            
            # Kompakte Ansicht gerendert
            compact_view_rendered = len(dashboard_data["compact_view"]) > 100
            
            # Export als Artefakt
            artifacts_exported = len(exported_files) >= 4  # Text, HTML, CSV, JSON
            
            # Dashboard zeigt letzte Runs mit Kennzahlen
            shows_recent_runs = len(dashboard_data["recent_runs"]) > 0
            
            # Trends verfügbar
            trends_available = len(dashboard_data["trends"]) > 0
            
            print(f"  ✓ Erfassung von Dauer/Token/Scanner/Coverage/Erfolgsquote/Kosten: {metrics_captured}")
            print(f"  ✓ Kompakte Ansicht gerendert: {compact_view_rendered}")
            print(f"  ✓ Export als Artefakt: {artifacts_exported}")
            print(f"  ✓ Dashboard zeigt letzte Runs mit Kennzahlen: {shows_recent_runs}")
            print(f"  ✓ Trends verfügbar: {trends_available}")
            
            return (metrics_captured and compact_view_rendered and 
                   artifacts_exported and shows_recent_runs and trends_available)
    
    # Führe Demo aus
    try:
        result = demo_telemetry_dashboard()
        print(f"\\nDemo completed successfully: {result}")
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
