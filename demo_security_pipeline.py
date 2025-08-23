#!/usr/bin/env python3
"""
Demo für die Security Scanner Integration in der Pipeline.

Zeigt die Funktionsweise des Security Scanners und die 
Integration in den Feature-Entwicklungsprozess.
"""

import json
import subprocess
import sys
from pathlib import Path


def demo_security_scanner():
    """Demonstriert den Security Scanner."""
    print("🔒 Demo: Security Scanner in Pipeline")
    print("="*60)
    
    print("\n📋 Security Scanner Features:")
    print("✅ Semgrep SAST (Static Application Security Testing)")
    print("✅ Bandit Python Security Scanner")
    print("✅ Secret Scanning (gitleaks/truffleHog/regex)")
    print("✅ Software Composition Analysis (safety/pip-audit)")
    print("✅ License Compliance Check")
    print("✅ Einheitliche JSON-Ausgabe")
    print("✅ Konfigurierbare Schwellwerte (none/low/medium/high)")
    print("✅ Integration in CLI feature-Kommando")
    
    print("\n🎯 Threshold-Verhalten:")
    print("- none: Alle Findings werden ignoriert")
    print("- low: Nur medium/high/critical Findings führen zu Fehlschlag")
    print("- medium: Nur high/critical Findings führen zu Fehlschlag")
    print("- high: Nur critical Findings führen zu Fehlschlag")
    
    print("\n🔍 Verfügbare Tools:")
    tools_status = check_security_tools()
    for tool, status in tools_status.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {tool}")
    
    print("\n📊 JSON-Ausgabefelder:")
    json_fields = [
        "timestamp", "scan_duration_seconds", "threshold", "passed", "exit_code",
        "semgrep", "bandit", "secrets", "dependencies", 
        "findings", "total_findings", "findings_by_severity", "failing_severity"
    ]
    for field in json_fields:
        print(f"  - {field}")
    
    print("\n🧪 Test mit künstlichen Verstößen:")
    
    if Path("test_security_violations").exists():
        print("  📁 Test-Verzeichnis existiert bereits")
        
        # Teste verschiedene Thresholds
        thresholds = ["none", "low", "medium", "high"]
        
        for threshold in thresholds:
            print(f"\n  🔍 Teste Threshold: {threshold}")
            
            cmd = [
                sys.executable, "security_scanner.py",
                "--target", "test_security_violations",
                "--threshold", threshold
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                print(f"    Exit Code: {result.returncode}")
                
                # Parse JSON aus stdout
                lines = result.stdout.strip().split('\n')
                json_start = -1
                for i, line in enumerate(lines):
                    if line.strip().startswith('{'):
                        json_start = i
                        break
                
                if json_start >= 0:
                    json_output = '\n'.join(lines[json_start:])
                    try:
                        data = json.loads(json_output)
                        print(f"    Findings: {data.get('total_findings', 0)}")
                        print(f"    Passed: {data.get('passed', False)}")
                    except json.JSONDecodeError:
                        print("    JSON Parse Error")
                
            except subprocess.TimeoutExpired:
                print("    ❌ Timeout")
            except Exception as e:
                print(f"    ❌ Error: {e}")
    else:
        print("  📁 Erstelle Test-Verzeichnis...")
        subprocess.run([sys.executable, "test_security_violations.py", "--create"])


def check_security_tools():
    """Prüfe Verfügbarkeit der Security Tools."""
    tools = {
        "semgrep": False,
        "bandit": False, 
        "gitleaks": False,
        "trufflehog": False,
        "safety": False,
        "pip-audit": False
    }
    
    for tool in tools.keys():
        try:
            result = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                timeout=5
            )
            tools[tool] = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            tools[tool] = False
    
    return tools


def demo_pipeline_integration():
    """Demonstriert die Pipeline-Integration."""
    print("\n" + "="*60)
    print("🔄 Pipeline Integration")
    print("="*60)
    
    print("\n📋 Erweiterte Feature-Pipeline:")
    print("1. 🔍 Spec laden und validieren")
    print("2. 🛡️  Prompt Guard ausführen")
    print("3. 🤖 LLM Unified Diff erzeugen")
    print("4. 🔒 Patch in Sandbox anwenden")
    print("5. 🔒 Security Scan durchführen ← NEU!")
    print("6. 🔍 QA Gates durchlaufen")
    print("7. 🚀 Branch pushen und Draft PR erstellen")
    
    print("\n🎯 Security Scan Integration:")
    print("- Position: Vor QA Gates, nach Patch-Anwendung")
    print("- Threshold: 'high' bei --secure Flag, sonst 'medium'")
    print("- Bei Fehlschlag: Pipeline stoppt mit Exit Code 5")
    print("- Ergebnis: security_scan_results.json wird gespeichert")
    
    print("\n📄 CLI-Verwendung:")
    print("```bash")
    print("# Standard Security Scan (medium threshold)")
    print("python cli.py feature --spec my-spec.yml --branch my-feature")
    print("")
    print("# Erhöhte Security (high threshold)")
    print("python cli.py feature --spec my-spec.yml --branch my-feature --secure")
    print("```")
    
    print("\n🔒 Security Scan direkt:")
    print("```bash")
    print("# Grundlegender Scan")
    print("python security_scanner.py --target . --threshold medium")
    print("")
    print("# Mit JSON-Output")
    print("python security_scanner.py --target . --threshold high --output security.json")
    print("")
    print("# Verbose Output")
    print("python security_scanner.py --target . --threshold low --verbose")
    print("```")


def demo_json_structure():
    """Zeigt die JSON-Struktur."""
    print("\n" + "="*60)
    print("📄 JSON-Ausgabestruktur")
    print("="*60)
    
    example_json = {
        "timestamp": "2025-08-17T17:00:00.000000",
        "scan_duration_seconds": 1.23,
        "threshold": "medium",
        "passed": False,
        "exit_code": 1,
        "semgrep": {
            "status": "completed",
            "findings_count": 3,
            "raw_data": "..."
        },
        "bandit": {
            "status": "completed", 
            "findings_count": 2,
            "raw_data": "..."
        },
        "secrets": {
            "status": "completed",
            "tool": "regex_secrets",
            "findings_count": 5,
            "raw_data": "..."
        },
        "dependencies": {
            "status": "completed",
            "tools": {
                "safety": {"status": "completed", "findings_count": 1},
                "pip_audit": {"status": "completed", "findings_count": 0},
                "licenses": {"status": "completed", "violations": 0}
            },
            "total_findings": 1
        },
        "findings": [
            {
                "tool": "semgrep",
                "rule_id": "python.lang.security.sql-injection",
                "severity": "high",
                "message": "SQL injection vulnerability detected",
                "file": "app.py",
                "line": 42,
                "cwe": "CWE-89",
                "confidence": "high"
            }
        ],
        "total_findings": 11,
        "findings_by_severity": {
            "none": 0,
            "low": 3,
            "medium": 3,
            "high": 5,
            "critical": 0
        },
        "failing_severity": "high"
    }
    
    print("\n📋 Beispiel JSON-Struktur:")
    print(json.dumps(example_json, indent=2))
    
    print("\n🔍 Wichtige Felder:")
    print("- passed: Boolean - Ob der Scan bestanden wurde")
    print("- exit_code: Integer - Exit Code (0=Pass, >0=Fail)")
    print("- findings: Array - Liste aller Security Findings")
    print("- failing_severity: String - Höchster Schweregrad der Threshold überschreitet")
    print("- findings_by_severity: Object - Anzahl Findings pro Schweregrad")


if __name__ == "__main__":
    print("🚀 Security Scanner Pipeline Demo")
    
    demo_security_scanner()
    demo_pipeline_integration()
    demo_json_structure()
    
    print("\n" + "="*60)
    print("🎉 Demo abgeschlossen!")
    print("="*60)
    print("\n📋 Nächste Schritte:")
    print("1. Installiere Security Tools: pip install semgrep bandit safety")
    print("2. Teste mit künstlichen Verstößen: python test_security_violations.py --test")
    print("3. Integriere in CI/CD Pipeline")
    print("4. Konfiguriere Schwellwerte je nach Projekt-Anforderungen")
    print("\n🔒 Security Scanner ist bereit für den produktiven Einsatz!")
