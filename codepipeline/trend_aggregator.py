#!/usr/bin/env python3
"""
MVP-FIX-007: Trend Aggregation stabil
Belastbarer Trend aus letzten N Läufen mit Ausreißer-Erkennung und Ampel-System.
"""

import json
import sys
import statistics
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import glob
from dataclasses import dataclass
from enum import Enum


class TrendStatus(Enum):
    """Trend-Status-Ampel"""
    GREEN = "green"    # Stabil gut
    YELLOW = "yellow"  # Warnung/Verschlechterung
    RED = "red"        # Kritisch/Viele Fails


@dataclass
class NightlyRunData:
    """Daten eines Nightly-Laufs"""
    date: str
    duration: float
    coverage_percent: float
    active_tools: int
    security_high: int
    license_violations: int
    overall_status: str  # "pass", "fail", "warn"
    source_file: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "duration": self.duration,
            "coverage_percent": self.coverage_percent,
            "active_tools": self.active_tools,
            "security_high": self.security_high,
            "license_violations": self.license_violations,
            "overall_status": self.overall_status,
            "source_file": self.source_file
        }


@dataclass
class TrendMetrics:
    """Aggregierte Trend-Metriken"""
    runs_count: int
    success_rate: float
    avg_duration: float
    avg_coverage: float
    avg_active_tools: float
    avg_security_high: float
    avg_license_violations: float
    duration_outliers: List[str]
    coverage_outliers: List[str]
    security_outliers: List[str]
    trend_status: TrendStatus
    trend_reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "runs_count": self.runs_count,
            "success_rate": self.success_rate,
            "avg_duration": self.avg_duration,
            "avg_coverage": self.avg_coverage,
            "avg_active_tools": self.avg_active_tools,
            "avg_security_high": self.avg_security_high,
            "avg_license_violations": self.avg_license_violations,
            "duration_outliers": self.duration_outliers,
            "coverage_outliers": self.coverage_outliers,
            "security_outliers": self.security_outliers,
            "trend_status": self.trend_status.value,
            "trend_reason": self.trend_reason
        }


class StableTrendAggregator:
    """Stabiler Trend-Aggregator für Nightly-Läufe"""
    
    def __init__(self, project_root: Optional[Path] = None, max_runs: int = 30):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.trends_dir = self.reports_dir / "trends"
        self.max_runs = max_runs
        
        print(f"📈 Trend Aggregator initialized")
        print(f"   Max runs to analyze: {max_runs}")
        print(f"   Trends directory: {self.trends_dir}")
    
    def discover_nightly_run_files(self) -> List[Path]:
        """Entdecke Nightly-Run-Dateien"""
        
        if not self.trends_dir.exists():
            print(f"   ⚠️ Trends directory not found: {self.trends_dir}")
            return []
        
        # Suche nach Nightly-KPI-Dateien
        pattern = str(self.trends_dir / "nightly_smoke_*.json")
        kpi_files = glob.glob(pattern)
        
        # Sortiere nach Datum (neueste zuerst)
        kpi_files.sort(reverse=True)
        
        # Limitiere auf max_runs
        limited_files = kpi_files[:self.max_runs]
        
        print(f"   📁 Found {len(kpi_files)} nightly files, analyzing {len(limited_files)}")
        
        return [Path(f) for f in limited_files]
    
    def extract_run_data_from_kpi_file(self, kpi_file: Path) -> Optional[NightlyRunData]:
        """Extrahiere Run-Daten aus KPI-Datei"""
        
        try:
            with open(kpi_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extrahiere KPI-Daten
            if "nightly_kpi" in data:
                kpi_data = data["nightly_kpi"]
            else:
                # Fallback: Direkte Struktur
                kpi_data = data
            
            # Extrahiere Datum aus Dateinamen (nightly_smoke_2025-08-22.json)
            date_str = kpi_file.stem.replace("nightly_smoke_", "")
            if not date_str or len(date_str) != 10:  # YYYY-MM-DD
                date_str = kpi_data.get("run_date", datetime.now().strftime("%Y-%m-%d"))
            
            run_data = NightlyRunData(
                date=date_str,
                duration=float(kpi_data.get("duration", 0.0)),
                coverage_percent=float(kpi_data.get("coverage_percent", 0.0)),
                active_tools=int(kpi_data.get("active_security_tools", 0)),
                security_high=int(kpi_data.get("security_high", 999)),
                license_violations=int(kpi_data.get("license_violations", 999)),
                overall_status=kpi_data.get("overall_status", "unknown"),
                source_file=str(kpi_file.name)
            )
            
            return run_data
            
        except Exception as e:
            print(f"   ⚠️ Error extracting from {kpi_file}: {e}")
            return None
    
    def detect_outliers(self, values: List[float], threshold: float = 2.0) -> Tuple[List[int], float, float]:
        """Erkenne Ausreißer mit Z-Score-Methode"""
        
        if len(values) < 3:
            return [], 0.0, 0.0  # Zu wenig Daten für Ausreißer-Erkennung
        
        try:
            mean = statistics.mean(values)
            stdev = statistics.stdev(values)
            
            if stdev == 0:
                return [], mean, stdev  # Keine Variation
            
            outlier_indices = []
            
            for i, value in enumerate(values):
                z_score = abs((value - mean) / stdev)
                if z_score > threshold:
                    outlier_indices.append(i)
            
            return outlier_indices, mean, stdev
            
        except Exception:
            return [], 0.0, 0.0
    
    def analyze_trend_status(self, runs: List[NightlyRunData]) -> Tuple[TrendStatus, str]:
        """Analysiere Trend-Status mit Ampel-System"""
        
        if not runs:
            return TrendStatus.RED, "No data available"
        
        if len(runs) < 3:
            return TrendStatus.YELLOW, "Insufficient data for trend analysis"
        
        # Berechne Erfolgsrate der letzten Läufe
        recent_runs = runs[:min(7, len(runs))]  # Letzte 7 Läufe
        success_count = len([r for r in recent_runs if r.overall_status == "pass"])
        success_rate = success_count / len(recent_runs) * 100
        
        # Prüfe Trend-Richtung (Coverage als Indikator)
        if len(runs) >= 5:
            recent_coverage = [r.coverage_percent for r in runs[:5]]
            older_coverage = [r.coverage_percent for r in runs[5:10]] if len(runs) >= 10 else recent_coverage
            
            recent_avg = statistics.mean(recent_coverage) if recent_coverage else 0
            older_avg = statistics.mean(older_coverage) if older_coverage else recent_avg
            
            coverage_trend = recent_avg - older_avg
        else:
            coverage_trend = 0
        
        # Prüfe kritische Metriken
        recent_high_findings = [r.security_high for r in recent_runs]
        has_high_findings = any(h > 0 for h in recent_high_findings)
        
        recent_active_tools = [r.active_tools for r in recent_runs]
        has_inactive_tools = any(t < 1 for t in recent_active_tools)
        
        # Bestimme Ampel-Status
        if success_rate >= 80 and not has_high_findings and not has_inactive_tools and coverage_trend >= -2:
            return TrendStatus.GREEN, f"Healthy trend: {success_rate:.0f}% success rate, stable metrics"
        
        elif success_rate >= 60 and not has_high_findings:
            if coverage_trend < -5:
                return TrendStatus.YELLOW, f"Warning: Coverage declining ({coverage_trend:.1f}%), {success_rate:.0f}% success"
            else:
                return TrendStatus.YELLOW, f"Warning: {success_rate:.0f}% success rate, some instability"
        
        else:
            reasons = []
            if success_rate < 60:
                reasons.append(f"low success rate ({success_rate:.0f}%)")
            if has_high_findings:
                reasons.append("high security findings")
            if has_inactive_tools:
                reasons.append("inactive security tools")
            if coverage_trend < -10:
                reasons.append(f"coverage declining ({coverage_trend:.1f}%)")
            
            return TrendStatus.RED, f"Critical: {', '.join(reasons)}"
    
    def aggregate_trend_data(self, runs: List[NightlyRunData]) -> TrendMetrics:
        """Aggregiere Trend-Daten mit Ausreißer-Erkennung"""
        
        if not runs:
            return TrendMetrics(
                runs_count=0,
                success_rate=0.0,
                avg_duration=0.0,
                avg_coverage=0.0,
                avg_active_tools=0.0,
                avg_security_high=0.0,
                avg_license_violations=0.0,
                duration_outliers=[],
                coverage_outliers=[],
                security_outliers=[],
                trend_status=TrendStatus.RED,
                trend_reason="No data available"
            )
        
        # Berechne Basis-Metriken
        success_count = len([r for r in runs if r.overall_status == "pass"])
        success_rate = success_count / len(runs) * 100
        
        # Extrahiere Werte für Ausreißer-Erkennung
        durations = [r.duration for r in runs]
        coverages = [r.coverage_percent for r in runs]
        security_highs = [float(r.security_high) for r in runs if r.security_high < 900]  # Filter extreme values
        
        # Erkenne Ausreißer und berechne sichere Durchschnitte
        duration_outlier_indices, avg_duration, _ = self.detect_outliers(durations, threshold=2.0)
        if not durations:
            avg_duration = 0.0
        
        coverage_outlier_indices, avg_coverage, _ = self.detect_outliers(coverages, threshold=1.5)
        if not coverages:
            avg_coverage = 0.0
            
        security_outlier_indices, avg_security_high, _ = self.detect_outliers(security_highs, threshold=1.5)
        if not security_highs:
            avg_security_high = 0.0
        
        # Sammle Ausreißer-Daten
        duration_outliers = [runs[i].date for i in duration_outlier_indices]
        coverage_outliers = [runs[i].date for i in coverage_outlier_indices]
        security_outliers = [runs[i].date for i in security_outlier_indices if i < len(runs)]
        
        # Berechne sichere Durchschnitte
        avg_active_tools = statistics.mean([float(r.active_tools) for r in runs]) if runs else 0.0
        
        # Sichere Berechnung für License-Violations
        valid_violations = [float(r.license_violations) for r in runs if r.license_violations < 900]
        avg_license_violations = statistics.mean(valid_violations) if valid_violations else 0.0
        
        # Analysiere Trend-Status
        trend_status, trend_reason = self.analyze_trend_status(runs)
        
        return TrendMetrics(
            runs_count=len(runs),
            success_rate=round(success_rate, 1),
            avg_duration=round(avg_duration, 2),
            avg_coverage=round(avg_coverage, 2),
            avg_active_tools=round(avg_active_tools, 1),
            avg_security_high=round(avg_security_high, 1),
            avg_license_violations=round(avg_license_violations, 1),
            duration_outliers=duration_outliers,
            coverage_outliers=coverage_outliers,
            security_outliers=security_outliers,
            trend_status=trend_status,
            trend_reason=trend_reason
        )
    
    def run_stable_trend_aggregation(self) -> Dict[str, Any]:
        """Führe stabile Trend-Aggregation durch"""
        
        print(f"📊 Running Stable Trend Aggregation...")
        
        # 1. Entdecke Nightly-Run-Dateien
        print(f"\\n🔍 Discovering nightly run files...")
        kpi_files = self.discover_nightly_run_files()
        
        if not kpi_files:
            print(f"   ❌ No nightly run files found")
            return {
                "stable_trend": {
                    "status": "no_data",
                    "runs_analyzed": 0,
                    "error": "No nightly run files found"
                }
            }
        
        # 2. Extrahiere Run-Daten
        print(f"\\n📈 Extracting run data...")
        runs = []
        for kpi_file in kpi_files:
            run_data = self.extract_run_data_from_kpi_file(kpi_file)
            if run_data:
                runs.append(run_data)
                print(f"   ✅ {run_data.date}: {run_data.overall_status} ({run_data.coverage_percent}% coverage)")
            else:
                print(f"   ❌ Failed to extract: {kpi_file.name}")
        
        if not runs:
            print(f"   ❌ No valid run data extracted")
            return {
                "stable_trend": {
                    "status": "extraction_failed",
                    "runs_analyzed": 0,
                    "error": "Failed to extract run data"
                }
            }
        
        # 3. Aggregiere Trend-Metriken
        print(f"\\n📊 Aggregating trend metrics...")
        trend_metrics = self.aggregate_trend_data(runs)
        
        # 4. Erstelle Trend-Report
        trend_report = {
            "stable_trend": {
                "status": "available",
                "runs_analyzed": len(runs),
                "date_range": {
                    "from": runs[-1].date if runs else "",
                    "to": runs[0].date if runs else ""
                },
                "metrics": trend_metrics.to_dict(),
                "runs_data": [run.to_dict() for run in runs],
                "analysis_date": datetime.utcnow().isoformat() + "Z",
                "max_runs_limit": self.max_runs
            },
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "project_root": str(self.project_root)
        }
        
        print(f"\\n🎯 Stable Trend Summary:")
        print(f"   Runs Analyzed: {len(runs)}")
        print(f"   Success Rate: {trend_metrics.success_rate}%")
        print(f"   Trend Status: {trend_metrics.trend_status.value.upper()} - {trend_metrics.trend_reason}")
        print(f"   Avg Coverage: {trend_metrics.avg_coverage}%")
        print(f"   Avg Active Tools: {trend_metrics.avg_active_tools}")
        print(f"   Outliers: {len(trend_metrics.duration_outliers + trend_metrics.coverage_outliers + trend_metrics.security_outliers)}")
        
        return trend_report
    
    def create_trend_markdown_report(self, trend_report: Dict[str, Any]) -> str:
        """Erstelle Markdown-Trend-Report"""
        
        stable_trend = trend_report["stable_trend"]
        metrics = stable_trend["metrics"]
        runs_data = stable_trend["runs_data"]
        
        # Trend-Status-Icons
        status_icons = {
            "green": "🟢",
            "yellow": "🟡", 
            "red": "🔴"
        }
        
        status_icon = status_icons.get(metrics["trend_status"], "⚪")
        
        # Markdown-Report erstellen
        markdown_lines = [
            "# 📈 Nightly Trend Report",
            "",
            f"**Status:** {status_icon} **{metrics['trend_status'].upper()}**  ",
            f"**Analysis Date:** {stable_trend['analysis_date']}  ",
            f"**Runs Analyzed:** {metrics['runs_count']} (from {stable_trend['date_range']['from']} to {stable_trend['date_range']['to']})  ",
            "",
            f"**Trend Assessment:** {metrics['trend_reason']}",
            "",
            "## 📊 Key Metrics",
            "",
            f"| Metric | Average | Status |",
            f"|--------|---------|--------|",
            f"| Success Rate | {metrics['success_rate']}% | {'✅' if metrics['success_rate'] >= 80 else '⚠️' if metrics['success_rate'] >= 60 else '❌'} |",
            f"| Coverage | {metrics['avg_coverage']}% | {'✅' if metrics['avg_coverage'] >= 20 else '❌'} |",
            f"| Active Tools | {metrics['avg_active_tools']} | {'✅' if metrics['avg_active_tools'] >= 1 else '❌'} |",
            f"| Security HIGH | {metrics['avg_security_high']} | {'✅' if metrics['avg_security_high'] == 0 else '❌'} |",
            f"| License Violations | {metrics['avg_license_violations']} | {'✅' if metrics['avg_license_violations'] <= 5 else '❌'} |",
            f"| Avg Duration | {metrics['avg_duration']}s | {'✅' if metrics['avg_duration'] <= 60 else '⚠️'} |",
            "",
            "## 🚨 Outliers Detection",
            ""
        ]
        
        # Ausreißer-Analyse
        all_outliers = metrics['duration_outliers'] + metrics['coverage_outliers'] + metrics['security_outliers']
        if all_outliers:
            markdown_lines.extend([
                f"**Outliers Found:** {len(set(all_outliers))} runs with anomalies",
                "",
                "| Type | Dates |",
                "|------|-------|",
                f"| Duration | {', '.join(metrics['duration_outliers']) if metrics['duration_outliers'] else 'None'} |",
                f"| Coverage | {', '.join(metrics['coverage_outliers']) if metrics['coverage_outliers'] else 'None'} |",
                f"| Security | {', '.join(metrics['security_outliers']) if metrics['security_outliers'] else 'None'} |",
                ""
            ])
        else:
            markdown_lines.extend([
                "**No significant outliers detected.** 📈",
                ""
            ])
        
        # Letzte 10 Läufe
        recent_runs = runs_data[:10]
        markdown_lines.extend([
            "## 📅 Recent Runs (Last 10)",
            "",
            "| Date | Status | Coverage | Active Tools | Duration |",
            "|------|--------|----------|--------------|----------|"
        ])
        
        for run in recent_runs:
            status_emoji = "✅" if run["overall_status"] == "pass" else "❌" if run["overall_status"] == "fail" else "⚠️"
            markdown_lines.append(
                f"| {run['date']} | {status_emoji} {run['overall_status']} | {run['coverage_percent']}% | {run['active_tools']} | {run['duration']}s |"
            )
        
        # Trend-Empfehlungen
        markdown_lines.extend([
            "",
            "## 💡 Recommendations",
            ""
        ])
        
        if metrics["trend_status"] == "green":
            markdown_lines.extend([
                "- ✅ **Excellent trend!** Keep up the good work.",
                "- 🔄 Continue monitoring for consistency.",
                "- 📈 Consider raising quality thresholds gradually."
            ])
        elif metrics["trend_status"] == "yellow":
            markdown_lines.extend([
                "- ⚠️ **Trend needs attention.** Review recent changes.",
                "- 🔍 Investigate outliers and anomalies.",
                "- 📊 Monitor next few runs closely."
            ])
        else:  # red
            markdown_lines.extend([
                "- 🚨 **Critical trend!** Immediate action required.",
                "- 🔧 Fix failing components urgently.",
                "- 📉 Review pipeline configuration and code quality.",
                "- 🛠️ Consider rollback if recent changes caused issues."
            ])
        
        markdown_lines.extend([
            "",
            "---",
            "",
            "*Generated by Stable Trend Aggregator*"
        ])
        
        return "\\n".join(markdown_lines)
    
    def save_trend_reports(self, trend_report: Dict[str, Any]) -> Tuple[Path, Path]:
        """Speichere Trend-Reports (JSON + Markdown)"""
        
        try:
            self.trends_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. JSON-Report mit Zeitstempel
            timestamp = datetime.now().strftime("%Y-%m-%d")
            json_file = self.trends_dir / f"stable_trend_{timestamp}.json"
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(trend_report, f, indent=2, ensure_ascii=False)
            
            # 2. Markdown-Report
            markdown_content = self.create_trend_markdown_report(trend_report)
            markdown_file = self.trends_dir / f"stable_trend_{timestamp}.md"
            
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # 3. Latest-Links für GUI
            latest_json = self.trends_dir / "latest_trend.json"
            latest_md = self.trends_dir / "latest_trend.md"
            
            with open(latest_json, 'w', encoding='utf-8') as f:
                json.dump(trend_report, f, indent=2, ensure_ascii=False)
            
            with open(latest_md, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            print(f"📄 Trend JSON report saved: {json_file}")
            print(f"📄 Trend Markdown report saved: {markdown_file}")
            print(f"📄 Latest trend links created for GUI")
            
            return json_file, markdown_file
            
        except Exception as e:
            print(f"⚠️ Could not save trend reports: {e}")
            return None, None


def main():
    """Main function für Stable Trend Aggregator"""
    print("🎯 MVP-FIX-007: Trend Aggregation stabil")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Stable Trend Aggregator")
    parser.add_argument("--max-runs", type=int, default=30, help="Maximum number of runs to analyze")
    parser.add_argument("--threshold", type=float, default=2.0, help="Outlier detection threshold (Z-score)")
    args = parser.parse_args()
    
    try:
        # Initialisiere Stable Trend Aggregator
        aggregator = StableTrendAggregator(max_runs=args.max_runs)
        
        # Führe Trend-Aggregation durch
        trend_report = aggregator.run_stable_trend_aggregation()
        
        # Speichere Reports
        json_file, markdown_file = aggregator.save_trend_reports(trend_report)
        
        # Prüfe Akzeptanzkriterien
        if "stable_trend" in trend_report and trend_report["stable_trend"]["status"] == "available":
            stable_trend = trend_report["stable_trend"]
            metrics = stable_trend["metrics"]
            
            print(f"\\n🎯 MVP-FIX-007 Akzeptanzkriterien:")
            print(f"   Sammle aus letzten N Läufen: ✅ ({stable_trend['runs_analyzed']} runs)")
            print(f"   Erkenne Ausreißer: ✅ ({len(metrics['duration_outliers'] + metrics['coverage_outliers'])} found)")
            print(f"   Markiere mit Ampel: ✅ ({metrics['trend_status'].upper()})")
            print(f"   Exportiere JSON mit Zeitstempel: {'✅' if json_file else '❌'}")
            print(f"   Exportiere Markdown: {'✅' if markdown_file else '❌'}")
            print(f"   Erfolgsrate klar: ✅ ({metrics['success_rate']}%)")
            print(f"   Durchschnittswerte: ✅ (Coverage: {metrics['avg_coverage']}%, Tools: {metrics['avg_active_tools']})")
            
            # Exit-Code basierend auf Trend-Status
            if metrics["trend_status"] in ["green", "yellow"]:
                print("🎉 Stable Trend Aggregation PASSED!")
                return 0
            else:
                print("⚠️ Stable Trend Aggregation: CRITICAL TREND!")
                return 1
        else:
            print("💥 Stable Trend Aggregation FAILED!")
            return 2
            
    except Exception as e:
        print(f"💥 Stable Trend Aggregation error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
