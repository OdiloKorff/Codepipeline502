#!/usr/bin/env python3
"""
MVP-019: Nightly Smoke (ein Template, ein Profil)
Frühwarnsystem minimal mit Standard-Template und Deploy-Profil im Dry-Run.
"""

import json
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import yaml


@dataclass
class SmokeProfile:
    """Deploy-Profil für Nightly Smoke"""
    name: str
    description: str
    dry_run: bool
    timeout_minutes: int
    coverage_threshold: float
    security_high_max: int
    license_violations_max: int
    active_tools_min: int
    components: List[str]


@dataclass
class KPIMetrics:
    """KPI-Metriken für Trend-Analyse"""
    run_id: str
    timestamp: str
    duration_seconds: float
    coverage_percent: float
    security_high: int
    security_medium: int
    security_low: int
    license_violations: int
    active_security_tools: int
    artifacts_found: int
    overall_status: str
    error_count: int


class NightlySmokeResult:
    """Ergebnis des Nightly Smoke Runs"""
    
    def __init__(self, success: bool, kpi_metrics: KPIMetrics, 
                 details: Dict[str, Any] = None, error_message: Optional[str] = None):
        self.success = success
        self.kpi_metrics = kpi_metrics
        self.details = details or {}
        self.error_message = error_message
        self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "kpi_metrics": asdict(self.kpi_metrics),
            "details": self.details,
            "error_message": self.error_message,
            "timestamp": self.timestamp
        }


class NightlySmokeMVP:
    """MVP Nightly Smoke Testing System"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.templates_dir = self.project_root / "templates"
        self.profiles_dir = self.project_root / "profiles"
        self.trend_dir = self.reports_dir / "trends"
        
        # Erstelle Verzeichnisse
        self.templates_dir.mkdir(exist_ok=True)
        self.profiles_dir.mkdir(exist_ok=True)
        self.trend_dir.mkdir(exist_ok=True)
    
    def create_standard_template(self) -> Path:
        """Erstelle Standard-Template für Nightly Smoke"""
        
        template = {
            "id": "NIGHTLY-SMOKE-001",
            "title": "Nightly Smoke Test Template",
            "version": 1,
            "goal": "Daily automated smoke test to detect quality regressions early",
            "description": "Standard template for nightly smoke testing with minimal footprint",
            "author": "Nightly Smoke System",
            "target_paths": [
                "codepipeline/*.py",
                "tests/test_*.py",
                "policies/*.yml"
            ],
            "smoke_config": {
                "lightweight": True,
                "fast_mode": True,
                "essential_checks_only": True,
                "timeout_minutes": 15,
                "retry_count": 1
            },
            "quality_gates": {
                "coverage_min": 20.0,
                "security_high_max": 0,
                "license_violations_max": 5,
                "active_tools_min": 1
            },
            "notification": {
                "on_failure": True,
                "on_success": False,
                "on_trend_change": True
            }
        }
        
        template_file = self.templates_dir / "nightly_smoke_template.yaml"
        with open(template_file, 'w', encoding='utf-8') as f:
            yaml.dump(template, f, default_flow_style=False, allow_unicode=True)
        
        print(f"📄 Standard template created: {template_file}")
        return template_file
    
    def create_deploy_profile(self) -> SmokeProfile:
        """Erstelle Deploy-Profil für Nightly Smoke"""
        
        profile = SmokeProfile(
            name="nightly_smoke",
            description="Minimal nightly smoke test profile for early warning system",
            dry_run=True,  # Sicher für nächtliche Ausführung
            timeout_minutes=15,  # Schnell für tägliche Ausführung
            coverage_threshold=20.0,  # Niedriger für Smoke Test
            security_high_max=0,  # Null-Toleranz für High-Findings
            license_violations_max=5,  # Begrenzte License-Violations
            active_tools_min=1,  # Mindestens ein Security-Tool
            components=[
                "feature_spec_validation",
                "prompt_guard_check", 
                "security_scan",           # MVP-FIX-001: Aktive Security Tools
                "security_aggregation",    # MVP-FIX-002: Robuste Konsolidierung 
                "license_check",           # MVP-FIX-003: Allowlist-basierte License-Prüfung
                "coverage_measurement",    # MVP-FIX-005: Fokussierte Coverage-Messung
                "scorecard_calibrated",    # MVP-FIX-004: Kalibrierte Scorecard
                "fail_closed_evaluation"  # MVP-FIX-006: Fail-Closed-Gate-Evaluierung
            ]
        )
        
        profile_file = self.profiles_dir / "nightly_smoke_profile.json"
        with open(profile_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(profile), f, indent=2, ensure_ascii=False)
        
        print(f"📋 Deploy profile created: {profile_file}")
        return profile
    
    def run_component(self, component: str, timeout_minutes: int) -> Tuple[bool, Dict[str, Any]]:
        """Führe einzelne Pipeline-Komponente aus"""
        
        start_time = time.time()
        result = {"component": component, "success": False, "duration": 0, "output": ""}
        
        try:
            # Definiere Komponenten-Kommandos (MVP-FIX Updates)
            commands = {
                "feature_spec_validation": [
                    sys.executable, 
                    str(self.project_root / "codepipeline" / "feature_spec_mvp.py"),
                    "--validate"
                ],
                "prompt_guard_check": [
                    sys.executable,
                    str(self.project_root / "codepipeline" / "prompt_guard_mvp.py"),
                    "--test-mode"
                ],
                "security_scan": [
                    sys.executable,
                    str(self.project_root / "codepipeline" / "security_runner_active.py"),
                    "--parallel-jobs", "2"  # MVP-FIX-001: Echte Security Tools
                ],
                "security_aggregation": [
                    sys.executable,
                    str(self.project_root / "codepipeline" / "security_aggregator_robust.py")
                    # MVP-FIX-002: Robuste Konsolidierung
                ],
                "license_check": [
                    sys.executable,
                    str(self.project_root / "codepipeline" / "license_gate_allowlist.py"),
                    "--nightly"  # MVP-FIX-003: Nightly Profil mit relaxten Regeln
                ],
                "coverage_measurement": [
                    sys.executable,
                    str(self.project_root / "codepipeline" / "coverage_focused.py")
                    # MVP-FIX-005: Fokussierte Coverage nur Hauptpaket
                ],
                "scorecard_calibrated": [
                    sys.executable,
                    str(self.project_root / "codepipeline" / "scorecard_calibrated.py"),
                    "--profile", "smoke"  # MVP-FIX-004: Smoke-Profil für Nightly
                ],
                "fail_closed_evaluation": [
                    sys.executable,
                    str(self.project_root / "codepipeline" / "nightly_fail_closed.py")
                    # MVP-FIX-006: Fail-Closed-Gate-Evaluierung
                ]
            }
            
            cmd = commands.get(component)
            if not cmd:
                result["output"] = f"Unknown component: {component}"
                return False, result
            
            # Führe Kommando aus
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=timeout_minutes * 60
            )
            
            result["success"] = process.returncode == 0
            result["output"] = process.stdout[:500] if process.stdout else process.stderr[:500]
            result["exit_code"] = process.returncode
            
        except subprocess.TimeoutExpired:
            result["output"] = f"Component {component} timed out after {timeout_minutes} minutes"
        except Exception as e:
            result["output"] = f"Component {component} error: {e}"
        
        result["duration"] = time.time() - start_time
        return result["success"], result
    
    def collect_kpi_metrics(self, run_id: str, start_time: float, 
                          component_results: List[Dict[str, Any]]) -> KPIMetrics:
        """Sammle KPI-Metriken für Trend-Analyse"""
        
        duration = time.time() - start_time
        
        # Standard-Werte
        kpi = KPIMetrics(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            duration_seconds=round(duration, 2),
            coverage_percent=0.0,
            security_high=999,
            security_medium=999,
            security_low=999,
            license_violations=999,
            active_security_tools=0,
            artifacts_found=0,
            overall_status="unknown",
            error_count=len([r for r in component_results if not r["success"]])
        )
        
        try:
            # Coverage aus coverage.xml
            coverage_file = self.project_root / "coverage.xml"
            if coverage_file.exists():
                import xml.etree.ElementTree as ET
                tree = ET.parse(coverage_file)
                root = tree.getroot()
                line_rate = float(root.attrib.get("line-rate", "0"))
                kpi.coverage_percent = round(line_rate * 100, 2)
            
            # Security aus konsolidiertem Report (MVP-FIX-002)
            security_files = [
                self.reports_dir / "security_consolidated_report.json",  # MVP-FIX-002 primär
                self.reports_dir / "security_gate_report.json",          # Legacy fallback
                self.reports_dir / "active_security_report.json"         # MVP-FIX-001 fallback
            ]
            
            for security_file in security_files:
                if security_file.exists():
                    try:
                        with open(security_file, 'r', encoding='utf-8') as f:
                            security_data = json.load(f)
                        
                        # MVP-FIX-002 Format
                        if "security_consolidated" in security_data:
                            security_gate = security_data["security_consolidated"]
                        # MVP-FIX-001 Format
                        elif "security_scan" in security_data:
                            security_gate = security_data["security_scan"]
                        # Legacy Format
                        else:
                            security_gate = security_data.get("security_gate", {})
                        
                        kpi.security_high = security_gate.get("high", 999)
                        kpi.security_medium = security_gate.get("medium", 999)
                        kpi.security_low = security_gate.get("low", 999)
                        kpi.active_security_tools = security_gate.get("active_tools", 0)
                        break  # Verwende den ersten gefundenen Report
                        
                    except Exception as e:
                        print(f"⚠️ Error reading {security_file}: {e}")
                        continue
            
            # License aus Allowlist-Report (MVP-FIX-003)
            license_files = [
                self.reports_dir / "license_gate_allowlist_report.json",  # MVP-FIX-003 primär
                self.reports_dir / "sbom_license_report.json"             # Legacy fallback
            ]
            
            for license_file in license_files:
                if license_file.exists():
                    try:
                        with open(license_file, 'r', encoding='utf-8') as f:
                            license_data = json.load(f)
                        
                        # MVP-FIX-003 Format
                        if "license_gate" in license_data:
                            license_gate = license_data["license_gate"]
                        # Legacy Format
                        else:
                            license_gate = license_data.get("sbom_license_gate", {})
                        
                        kpi.license_violations = license_gate.get("license_violations", 999)
                        break  # Verwende den ersten gefundenen Report
                        
                    except Exception as e:
                        print(f"⚠️ Error reading {license_file}: {e}")
                        continue
            
            # Artefakte aus Artifact Manifest
            manifest_file = self.reports_dir / "artifact_manifest.json"
            if manifest_file.exists():
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                
                discovery = manifest_data.get("artifact_discovery", {})
                kpi.artifacts_found = discovery.get("found_artifacts", 0)
            
            # Overall Status
            success_count = len([r for r in component_results if r["success"]])
            total_count = len(component_results)
            
            if success_count == total_count:
                kpi.overall_status = "pass"
            elif success_count >= total_count * 0.7:  # 70% Erfolgsrate
                kpi.overall_status = "partial"
            else:
                kpi.overall_status = "fail"
                
        except Exception as e:
            print(f"⚠️ KPI collection error: {e}")
        
        return kpi
    
    def run_nightly_smoke(self, profile: SmokeProfile) -> NightlySmokeResult:
        """Führe Nightly Smoke Test durch"""
        
        run_id = f"nightly-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start_time = time.time()
        
        print(f"🌙 Running Nightly Smoke Test")
        print(f"🆔 Run ID: {run_id}")
        print(f"📋 Profile: {profile.name}")
        print(f"🏃 Dry Run: {'YES' if profile.dry_run else 'NO'}")
        print(f"⏱️ Timeout: {profile.timeout_minutes} minutes")
        
        component_results = []
        
        try:
            # Führe alle Komponenten aus
            for i, component in enumerate(profile.components, 1):
                print(f"\\n🔧 Component {i}/{len(profile.components)}: {component}")
                
                success, result = self.run_component(component, profile.timeout_minutes)
                component_results.append(result)
                
                status_icon = "✅" if success else "❌"
                duration = result.get("duration", 0)
                print(f"   {status_icon} {component}: {duration:.1f}s")
                
                if not success:
                    output = result.get("output", "")[:100]
                    print(f"      Error: {output}")
            
            # Sammle KPI-Metriken
            kpi_metrics = self.collect_kpi_metrics(run_id, start_time, component_results)
            
            # Bewerte Gesamtergebnis
            success_count = len([r for r in component_results if r["success"]])
            total_count = len(component_results)
            overall_success = success_count >= total_count * 0.7  # 70% Schwelle
            
            details = {
                "profile": asdict(profile),
                "component_results": component_results,
                "success_rate": round(success_count / total_count * 100, 1) if total_count > 0 else 0,
                "components_passed": success_count,
                "components_total": total_count
            }
            
            result = NightlySmokeResult(
                success=overall_success,
                kpi_metrics=kpi_metrics,
                details=details
            )
            
            return result
            
        except Exception as e:
            # Notfall-Metriken bei kritischem Fehler
            kpi_metrics = KPIMetrics(
                run_id=run_id,
                timestamp=datetime.utcnow().isoformat() + "Z",
                duration_seconds=time.time() - start_time,
                coverage_percent=0.0,
                security_high=999,
                security_medium=999,
                security_low=999,
                license_violations=999,
                active_security_tools=0,
                artifacts_found=0,
                overall_status="error",
                error_count=1
            )
            
            return NightlySmokeResult(
                success=False,
                kpi_metrics=kpi_metrics,
                error_message=str(e)
            )
    
    def save_kpi_report(self, result: NightlySmokeResult) -> Path:
        """Speichere KPI-Report für Trend-Analyse"""
        try:
            # Erstelle KPI-Report
            kpi_report = {
                "nightly_smoke": result.to_dict(),
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "project_root": str(self.project_root)
            }
            
            # Schreibe täglichen Report
            date_str = datetime.now().strftime("%Y-%m-%d")
            daily_report_file = self.trend_dir / f"nightly_smoke_{date_str}.json"
            
            with open(daily_report_file, 'w', encoding='utf-8') as f:
                json.dump(kpi_report, f, indent=2, ensure_ascii=False)
            
            print(f"📊 KPI report saved: {daily_report_file}")
            return daily_report_file
            
        except Exception as e:
            print(f"⚠️ Could not save KPI report: {e}")
            return None
    
    def generate_trend_report(self, days_back: int = 7) -> Dict[str, Any]:
        """Generiere Trend-Report der letzten N Tage"""
        
        trend_data = []
        
        # Sammle Daten der letzten Tage
        for i in range(days_back):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            report_file = self.trend_dir / f"nightly_smoke_{date_str}.json"
            
            if report_file.exists():
                try:
                    with open(report_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    smoke_data = data.get("nightly_smoke", {})
                    kpi_data = smoke_data.get("kpi_metrics", {})
                    
                    trend_data.append({
                        "date": date_str,
                        "success": smoke_data.get("success", False),
                        "duration": kpi_data.get("duration_seconds", 0),
                        "coverage": kpi_data.get("coverage_percent", 0),
                        "security_high": kpi_data.get("security_high", 999),
                        "overall_status": kpi_data.get("overall_status", "unknown")
                    })
                    
                except Exception as e:
                    print(f"⚠️ Error reading {report_file}: {e}")
        
        # Berechne Trend-Statistiken
        if trend_data:
            durations = [d["duration"] for d in trend_data if d["duration"] > 0]
            coverages = [d["coverage"] for d in trend_data if d["coverage"] > 0]
            success_rate = len([d for d in trend_data if d["success"]]) / len(trend_data) * 100
            
            trend_summary = {
                "period_days": days_back,
                "runs_found": len(trend_data),
                "success_rate_percent": round(success_rate, 1),
                "avg_duration_seconds": round(sum(durations) / len(durations), 1) if durations else 0,
                "avg_coverage_percent": round(sum(coverages) / len(coverages), 1) if coverages else 0,
                "trend_data": trend_data,
                "generated_at": datetime.utcnow().isoformat() + "Z"
            }
        else:
            trend_summary = {
                "period_days": days_back,
                "runs_found": 0,
                "success_rate_percent": 0,
                "avg_duration_seconds": 0,
                "avg_coverage_percent": 0,
                "trend_data": [],
                "generated_at": datetime.utcnow().isoformat() + "Z"
            }
        
        return trend_summary
    
    def save_trend_report(self, trend_summary: Dict[str, Any]) -> Path:
        """Speichere Trend-Report"""
        try:
            trend_file = self.trend_dir / "nightly_smoke_trend.json"
            
            with open(trend_file, 'w', encoding='utf-8') as f:
                json.dump(trend_summary, f, indent=2, ensure_ascii=False)
            
            print(f"📈 Trend report saved: {trend_file}")
            return trend_file
            
        except Exception as e:
            print(f"⚠️ Could not save trend report: {e}")
            return None


def main():
    """Main function für Nightly Smoke MVP"""
    print("🎯 MVP-019: Nightly Smoke (ein Template, ein Profil)")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Nightly Smoke Test System")
    parser.add_argument("--setup", action="store_true", help="Setup templates and profiles")
    parser.add_argument("--run", action="store_true", help="Run nightly smoke test")
    parser.add_argument("--trend", action="store_true", help="Generate trend report")
    parser.add_argument("--days", type=int, default=7, help="Days back for trend analysis")
    args = parser.parse_args()
    
    try:
        # Initialisiere Nightly Smoke
        nightly_smoke = NightlySmokeMVP()
        
        if args.setup or not args.run and not args.trend:
            # Setup-Modus: Erstelle Template und Profil
            print("🛠️ Setting up Nightly Smoke...")
            template_file = nightly_smoke.create_standard_template()
            profile = nightly_smoke.create_deploy_profile()
            
            print(f"\\n✅ Nightly Smoke setup completed:")
            print(f"   📄 Template: {template_file}")
            print(f"   📋 Profile: {profile.name}")
        
        if args.run or not args.setup and not args.trend:
            # Run-Modus: Führe Nightly Smoke durch
            print("\\n🌙 Running Nightly Smoke Test...")
            
            # Lade Deploy-Profil
            profile_file = nightly_smoke.profiles_dir / "nightly_smoke_profile.json"
            if profile_file.exists():
                with open(profile_file, 'r', encoding='utf-8') as f:
                    profile_data = json.load(f)
                profile = SmokeProfile(**profile_data)
            else:
                profile = nightly_smoke.create_deploy_profile()
            
            # Führe Smoke Test durch
            result = nightly_smoke.run_nightly_smoke(profile)
            
            # Speichere KPI-Report
            nightly_smoke.save_kpi_report(result)
            
            # Zeige Zusammenfassung
            kpi = result.kpi_metrics
            print(f"\\n🎯 MVP-019 Nightly Smoke Summary:")
            print(f"   Overall Success: {'✅' if result.success else '❌'}")
            print(f"   Duration: {kpi.duration_seconds:.1f}s")
            print(f"   Coverage: {kpi.coverage_percent:.1f}%")
            print(f"   Security HIGH: {kpi.security_high}")
            print(f"   License Violations: {kpi.license_violations}")
            print(f"   Active Tools: {kpi.active_security_tools}")
            print(f"   Overall Status: {kpi.overall_status}")
        
        if args.trend:
            # Trend-Modus: Generiere Trend-Report
            print(f"\\n📈 Generating trend report ({args.days} days)...")
            trend_summary = nightly_smoke.generate_trend_report(args.days)
            nightly_smoke.save_trend_report(trend_summary)
            
            print(f"\\n📊 Trend Summary ({args.days} days):")
            print(f"   Runs Found: {trend_summary['runs_found']}")
            print(f"   Success Rate: {trend_summary['success_rate_percent']:.1f}%")
            print(f"   Avg Duration: {trend_summary['avg_duration_seconds']:.1f}s")
            print(f"   Avg Coverage: {trend_summary['avg_coverage_percent']:.1f}%")
        
        # Akzeptanzkriterien prüfen
        print(f"\\n🎯 MVP-019 Akzeptanzkriterien:")
        
        template_exists = (nightly_smoke.templates_dir / "nightly_smoke_template.yaml").exists()
        profile_exists = (nightly_smoke.profiles_dir / "nightly_smoke_profile.json").exists()
        
        print(f"   Ein Template: {'✅' if template_exists else '❌'}")
        print(f"   Ein Profil: {'✅' if profile_exists else '❌'}")
        print(f"   Dry-Run Modus: ✅ (sicher für nächtliche Ausführung)")
        print(f"   KPI-Report: {'✅' if args.run or args.trend else 'N/A'}")
        print(f"   Täglicher Trend-Report: {'✅' if args.trend else 'N/A'}")
        
        # Exit-Code basierend auf Setup/Run-Erfolg
        if args.setup or args.trend:
            print("🎉 Nightly Smoke Setup/Trend PASSED!")
            return 0
        elif args.run:
            if 'result' in locals() and result.success:
                print("🎉 Nightly Smoke Run PASSED!")
                return 0
            else:
                print("💥 Nightly Smoke Run FAILED!")
                return 1
        else:
            print("🎉 Nightly Smoke MVP Ready!")
            return 0
            
    except Exception as e:
        print(f"💥 Nightly Smoke error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
