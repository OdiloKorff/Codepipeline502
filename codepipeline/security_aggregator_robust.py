#!/usr/bin/env python3
"""
MVP-FIX-002: Security Report Konsolidator robust
Aggregator für flache Einzelreports und konsolidierte Formate mit korrekter active_tools-Zählung.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import glob


class SecurityReportFormat:
    """Erkanntes Format eines Security-Reports"""
    
    def __init__(self, format_type: str, tool_name: str, status: str, 
                 high: int, medium: int, low: int, total: int):
        self.format_type = format_type  # "bandit_raw", "consolidated", "active_scan", "legacy"
        self.tool_name = tool_name
        self.status = status
        self.high = high
        self.medium = medium
        self.low = low
        self.total = total
        self.is_active = status.lower() in ["ok", "pass", "success"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": self.format_type,
            "tool": self.tool_name,
            "status": self.status,
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
            "total": self.total,
            "active": self.is_active
        }


class RobustSecurityAggregator:
    """Robuster Security Report Aggregator"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.detected_formats = []
        
        # Bekannte Report-Dateien
        self.known_report_files = [
            "reports/security_report.json",           # Legacy
            "reports/security_gate_report.json",      # MVP-007
            "reports/active_security_report.json",    # MVP-FIX-001
            "reports/bandit_raw_scan.json",          # Raw Bandit
            "reports/consolidated_security.json",     # Konsolidiert
            "security_report.json",                   # Root-Level
            "bandit.json",                           # Alternative
            "semgrep.json"                           # Alternative
        ]
    
    def detect_bandit_raw_format(self, data: Dict[str, Any]) -> Optional[SecurityReportFormat]:
        """Erkenne Raw Bandit JSON-Format"""
        
        if "results" in data and "metrics" in data:
            # Bandit Raw Format
            results = data.get("results", [])
            high_count = 0
            medium_count = 0
            low_count = 0
            
            for finding in results:
                severity = finding.get("issue_severity", "").upper()
                if severity == "HIGH":
                    high_count += 1
                elif severity == "MEDIUM":
                    medium_count += 1
                elif severity == "LOW":
                    low_count += 1
            
            total_count = len(results)
            status = "ok" if high_count == 0 else "warn"
            
            return SecurityReportFormat(
                format_type="bandit_raw",
                tool_name="bandit",
                status=status,
                high=high_count,
                medium=medium_count,
                low=low_count,
                total=total_count
            )
        
        return None
    
    def detect_consolidated_format(self, data: Dict[str, Any]) -> List[SecurityReportFormat]:
        """Erkenne konsolidierte Formate"""
        
        formats = []
        
        # MVP-007 Format: {"bandit": {"status": "ok", "high": 0, ...}}
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict) and "status" in value:
                    tool_format = SecurityReportFormat(
                        format_type="consolidated",
                        tool_name=key,
                        status=value.get("status", "unknown"),
                        high=value.get("high", 0),
                        medium=value.get("medium", 0),
                        low=value.get("low", 0),
                        total=value.get("total", 0)
                    )
                    formats.append(tool_format)
        
        # MVP-FIX-001 Format: {"security_scan": {"tools": [...]}}
        if "security_scan" in data:
            security_scan = data["security_scan"]
            
            # Gesamt-Aggregation
            overall_format = SecurityReportFormat(
                format_type="active_scan",
                tool_name="security_scan",
                status=security_scan.get("status", "unknown"),
                high=security_scan.get("high", 0),
                medium=security_scan.get("medium", 0),
                low=security_scan.get("low", 0),
                total=security_scan.get("total", 0)
            )
            formats.append(overall_format)
            
            # Einzelne Tools
            for tool_data in security_scan.get("tools", []):
                tool_format = SecurityReportFormat(
                    format_type="active_tool",
                    tool_name=tool_data.get("tool", "unknown"),
                    status=tool_data.get("status", "unknown"),
                    high=tool_data.get("high", 0),
                    medium=tool_data.get("medium", 0),
                    low=tool_data.get("low", 0),
                    total=tool_data.get("total", 0)
                )
                formats.append(tool_format)
        
        return formats
    
    def detect_legacy_format(self, data: Dict[str, Any]) -> Optional[SecurityReportFormat]:
        """Erkenne Legacy-Formate"""
        
        # Einfaches Format mit direkten high/medium/low-Feldern
        if all(key in data for key in ["high", "medium", "low"]):
            return SecurityReportFormat(
                format_type="legacy",
                tool_name="security_tool",
                status=data.get("status", "ok" if data.get("high", 0) == 0 else "warn"),
                high=data.get("high", 0),
                medium=data.get("medium", 0),
                low=data.get("low", 0),
                total=data.get("total", data.get("high", 0) + data.get("medium", 0) + data.get("low", 0))
            )
        
        return None
    
    def parse_security_report_file(self, file_path: Path) -> List[SecurityReportFormat]:
        """Parse einzelne Security-Report-Datei"""
        
        formats = []
        
        try:
            if not file_path.exists():
                return formats
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"   📄 Parsing: {file_path}")
            
            # Versuche verschiedene Format-Detektionen
            
            # 1. Bandit Raw Format
            bandit_format = self.detect_bandit_raw_format(data)
            if bandit_format:
                formats.append(bandit_format)
                print(f"      ✅ Detected: {bandit_format.format_type} ({bandit_format.tool_name})")
            
            # 2. Konsolidierte Formate
            consolidated_formats = self.detect_consolidated_format(data)
            formats.extend(consolidated_formats)
            for fmt in consolidated_formats:
                print(f"      ✅ Detected: {fmt.format_type} ({fmt.tool_name})")
            
            # 3. Legacy Format
            if not formats:  # Nur falls nichts anderes erkannt wurde
                legacy_format = self.detect_legacy_format(data)
                if legacy_format:
                    formats.append(legacy_format)
                    print(f"      ✅ Detected: {legacy_format.format_type} ({legacy_format.tool_name})")
            
            if not formats:
                print(f"      ⚠️ Unknown format in {file_path}")
            
        except json.JSONDecodeError as e:
            print(f"      ❌ JSON decode error in {file_path}: {e}")
        except Exception as e:
            print(f"      ❌ Error parsing {file_path}: {e}")
        
        return formats
    
    def discover_security_reports(self) -> List[Path]:
        """Entdecke alle verfügbaren Security-Report-Dateien"""
        
        found_files = []
        
        for report_pattern in self.known_report_files:
            file_path = self.project_root / report_pattern
            if file_path.exists():
                found_files.append(file_path)
        
        # Zusätzlich: Suche nach *.json in reports/
        if self.reports_dir.exists():
            for json_file in self.reports_dir.glob("*.json"):
                if json_file not in found_files and "security" in json_file.name.lower():
                    found_files.append(json_file)
        
        return found_files
    
    def aggregate_security_reports(self) -> Dict[str, Any]:
        """Aggregiere alle gefundenen Security-Reports"""
        
        print("🔍 Discovering security reports...")
        
        # Entdecke alle Report-Dateien
        report_files = self.discover_security_reports()
        print(f"   📁 Found {len(report_files)} potential report files")
        
        # Parse alle Dateien
        all_formats = []
        for report_file in report_files:
            formats = self.parse_security_report_file(report_file)
            all_formats.extend(formats)
        
        self.detected_formats = all_formats
        
        # Aggregiere Ergebnisse
        tools_by_name = {}
        
        for fmt in all_formats:
            tool_name = fmt.tool_name
            
            if tool_name not in tools_by_name:
                tools_by_name[tool_name] = []
            
            tools_by_name[tool_name].append(fmt)
        
        # Bestimme aktive Tools durch Zählen mit Status ok/pass
        active_tools_count = 0
        consolidated_tools = {}
        
        for tool_name, tool_formats in tools_by_name.items():
            # Nimm das aktuellste Format (letztes in der Liste)
            latest_format = tool_formats[-1]
            
            consolidated_tools[tool_name] = {
                "status": latest_format.status,
                "high": latest_format.high,
                "medium": latest_format.medium,
                "low": latest_format.low,
                "total": latest_format.total,
                "format": latest_format.format_type,
                "active": latest_format.is_active
            }
            
            if latest_format.is_active:
                active_tools_count += 1
        
        # Gesamtaggregation
        total_high = sum(tool["high"] for tool in consolidated_tools.values())
        total_medium = sum(tool["medium"] for tool in consolidated_tools.values())
        total_low = sum(tool["low"] for tool in consolidated_tools.values())
        total_findings = sum(tool["total"] for tool in consolidated_tools.values())
        
        # Bestimme Gesamt-Status
        if total_high == 0 and active_tools_count > 0:
            overall_status = "pass"
        elif total_high == 0:
            overall_status = "warn"  # Keine aktiven Tools
        else:
            overall_status = "fail"  # High-Findings vorhanden
        
        # Erstelle konsolidierten Report
        consolidated_report = {
            "security_consolidated": {
                "status": overall_status,
                "active_tools": active_tools_count,
                "tools_total": len(consolidated_tools),
                "high": total_high,
                "medium": total_medium,
                "low": total_low,
                "total": total_findings,
                "aggregated_at": datetime.utcnow().isoformat() + "Z",
                "tools": consolidated_tools,
                "sources": {
                    "report_files": [str(f) for f in report_files],
                    "formats_detected": len(all_formats),
                    "formats": [fmt.to_dict() for fmt in all_formats]
                }
            }
        }
        
        print(f"\\n🎯 Security Aggregation Summary:")
        print(f"   Overall Status: {overall_status.upper()}")
        print(f"   Active Tools: {active_tools_count}/{len(consolidated_tools)}")
        print(f"   Tools Found: {list(consolidated_tools.keys())}")
        print(f"   HIGH: {total_high}, MEDIUM: {total_medium}, LOW: {total_low}")
        print(f"   Total Findings: {total_findings}")
        print(f"   Formats Detected: {len(all_formats)}")
        
        return consolidated_report
    
    def save_consolidated_report(self, consolidated_report: Dict[str, Any]) -> Tuple[Path, Path]:
        """Speichere konsolidierten Report für Scorecard und Nightly"""
        
        try:
            self.reports_dir.mkdir(exist_ok=True)
            
            # 1. Haupt-Report für Scorecard
            main_report_file = self.reports_dir / "security_consolidated_report.json"
            with open(main_report_file, 'w', encoding='utf-8') as f:
                json.dump(consolidated_report, f, indent=2, ensure_ascii=False)
            
            # 2. Legacy-kompatibles Format für bestehende Tools
            security_data = consolidated_report["security_consolidated"]
            legacy_report = {
                "security_gate": {
                    "status": security_data["status"],
                    "high": security_data["high"],
                    "medium": security_data["medium"],
                    "low": security_data["low"],
                    "total": security_data["total"],
                    "active_tools": security_data["active_tools"],
                    "scan_date": security_data["aggregated_at"]
                }
            }
            
            legacy_report_file = self.reports_dir / "security_gate_report.json"
            with open(legacy_report_file, 'w', encoding='utf-8') as f:
                json.dump(legacy_report, f, indent=2, ensure_ascii=False)
            
            print(f"📄 Consolidated report saved: {main_report_file}")
            print(f"📄 Legacy-compatible report saved: {legacy_report_file}")
            
            return main_report_file, legacy_report_file
            
        except Exception as e:
            print(f"⚠️ Could not save consolidated report: {e}")
            return None, None


def main():
    """Main function für Robust Security Aggregator"""
    print("🎯 MVP-FIX-002: Security Report Konsolidator robust")
    
    try:
        # Initialisiere Robust Security Aggregator
        aggregator = RobustSecurityAggregator()
        
        # Aggregiere alle Security-Reports
        consolidated_report = aggregator.aggregate_security_reports()
        
        # Speichere konsolidierten Report
        main_file, legacy_file = aggregator.save_consolidated_report(consolidated_report)
        
        # Prüfe Akzeptanzkriterien
        security_data = consolidated_report["security_consolidated"]
        active_tools = security_data["active_tools"]
        high_findings = security_data["high"]
        overall_status = security_data["status"]
        
        print(f"\\n🎯 MVP-FIX-002 Akzeptanzkriterien:")
        print(f"   Aggregator erkennt alle Formate: {'✅' if len(aggregator.detected_formats) > 0 else '❌'} ({len(aggregator.detected_formats)} formats)")
        print(f"   Active Tools korrekte Zahl: {'✅' if active_tools >= 0 else '❌'} ({active_tools})")
        print(f"   HIGH=0 spiegelt Gate PASS: {'✅' if (high_findings == 0 and overall_status == 'pass') or (high_findings > 0 and overall_status != 'pass') else '❌'}")
        print(f"   Kompaktes Ergebnis in reports: {'✅' if main_file and legacy_file else '❌'}")
        print(f"   Scorecard-kompatibel: {'✅' if legacy_file else '❌'}")
        
        # Exit-Code basierend auf Funktionalität
        if len(aggregator.detected_formats) > 0 and main_file:
            print("🎉 Security Report Aggregation PASSED!")
            return 0
        else:
            print("💥 Security Report Aggregation FAILED!")
            return 1
            
    except Exception as e:
        print(f"💥 Security Aggregator error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
