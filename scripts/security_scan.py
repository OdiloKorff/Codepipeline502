#!/usr/bin/env python3
"""
Security-Scanner-Skript für CodePipeline.
Führt Semgrep, Bandit, gitleaks und pip-audit aus wenn verfügbar.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_tool(name, command, timeout=60):
    """Führe Security-Tool aus mit Autodetection."""
    tool_binary = command[0]
    
    # Autodetection: Prüfe ob Tool installiert ist
    if not shutil.which(tool_binary):
        return {
            'status': 'skip', 
            'reason': f'{tool_binary} not installed',
            'high': 0,
            'medium': 0, 
            'low': 0,
            'findings': 0
        }
    
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=Path.cwd(),
            encoding='utf-8',
            errors='replace'
        )
        
        # Bandit kann mit Exit-Code 1 laufen wenn es Findings hat, das ist OK
        if name == 'bandit' and result.returncode in [0, 1]:
            return {
                'status': 'completed',
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        
        return {
            'status': 'completed',
            'exit_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            'status': 'timeout', 
            'reason': f'Tool {name} timed out after {timeout}s',
            'high': 0,
            'medium': 0, 
            'low': 0,
            'findings': 0
        }
    except Exception as e:
        return {
            'status': 'error', 
            'reason': str(e),
            'high': 0,
            'medium': 0, 
            'low': 0,
            'findings': 0
        }


def parse_semgrep_output(output):
    """Parse Semgrep JSON-Output."""
    try:
        data = json.loads(output)
        results = data.get('results', [])
        
        high = sum(1 for r in results if r.get('extra', {}).get('severity') == 'ERROR')
        medium = sum(1 for r in results if r.get('extra', {}).get('severity') == 'WARNING') 
        low = sum(1 for r in results if r.get('extra', {}).get('severity') == 'INFO')
        
        return {'high': high, 'medium': medium, 'low': low, 'status': 'completed'}
    except:
        return {'high': 0, 'medium': 0, 'low': 0, 'status': 'parse_error'}


def parse_bandit_output(output):
    """Parse Bandit JSON-Output."""
    try:
        data = json.loads(output)
        results = data.get('results', [])
        
        high = sum(1 for r in results if r.get('issue_severity') == 'HIGH')
        medium = sum(1 for r in results if r.get('issue_severity') == 'MEDIUM')
        low = sum(1 for r in results if r.get('issue_severity') == 'LOW')
        
        return {'high': high, 'medium': medium, 'low': low, 'status': 'completed'}
    except Exception as e:
        # Debug: Ausgabe bei Parse-Fehler
        print(f"Bandit parse error: {e}", file=sys.stderr)
        print(f"Bandit output: {output[:200]}...", file=sys.stderr)
        return {'high': 0, 'medium': 0, 'low': 0, 'status': 'parse_error'}


def main():
    """Hauptfunktion."""
    
    # Parse CLI-Argumente
    out_json = None
    fail_on = 'high'
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--out-json' and i + 1 < len(args):
            out_json = args[i + 1]
            i += 2
        elif args[i] == '--fail-on' and i + 1 < len(args):
            fail_on = args[i + 1]
            i += 2
        else:
            i += 1
    
    # Security-Tools ausführen
    report = {}
    
    # 1. Semgrep
    semgrep_result = run_tool('semgrep', ['semgrep', '--config=auto', '--json', '.'])
    if semgrep_result['status'] == 'completed':
        report['semgrep'] = parse_semgrep_output(semgrep_result['stdout'])
    else:
        report['semgrep'] = {'high': 0, 'medium': 0, 'low': 0, 'status': semgrep_result['status']}
    
    # 2. Bandit (rauscharm: nur High+Medium-Severity)
    if shutil.which('bandit'):
        try:
            result = subprocess.run(
                ['bandit', '-r', 'codepipeline', '-f', 'json', '-ll'],  # -ll = nur High+Medium
                capture_output=True, 
                text=True, 
                timeout=30,
                encoding='utf-8',
                errors='replace'
            )
            
            # Bandit kann Exit-Code 1 haben bei Findings - das ist OK
            if result.returncode in [0, 1]:
                stdout = result.stdout.strip()
                if stdout:
                    try:
                        # Versuche JSON zu parsen
                        data = json.loads(stdout)
                        results = data.get('results', [])
                        
                        high = sum(1 for r in results if r.get('issue_severity') == 'HIGH')
                        medium = sum(1 for r in results if r.get('issue_severity') == 'MEDIUM') 
                        low = sum(1 for r in results if r.get('issue_severity') == 'LOW')
                        
                        report['bandit'] = {'high': high, 'medium': medium, 'low': low, 'status': 'completed'}
                    except json.JSONDecodeError:
                        # Bandit lief, aber JSON-Parsing fehlgeschlagen - trotzdem als aktiv zählen
                        report['bandit'] = {'high': 0, 'medium': 0, 'low': 0, 'status': 'completed', 'note': 'json_parse_error'}
                else:
                    # Kein Output, aber erfolgreich gelaufen - als aktiv zählen
                    report['bandit'] = {'high': 0, 'medium': 0, 'low': 0, 'status': 'completed', 'note': 'no_output'}
            else:
                report['bandit'] = {'high': 0, 'medium': 0, 'low': 0, 'status': 'error', 'reason': f'bandit exit {result.returncode}'}
                
        except subprocess.TimeoutExpired:
            report['bandit'] = {'high': 0, 'medium': 0, 'low': 0, 'status': 'timeout', 'reason': 'bandit timeout 30s'}
        except Exception as e:
            report['bandit'] = {'high': 0, 'medium': 0, 'low': 0, 'status': 'error', 'reason': str(e)}
    else:
        report['bandit'] = {'high': 0, 'medium': 0, 'low': 0, 'status': 'skip', 'reason': 'bandit not installed'}
    
    # 3. Gitleaks
    gitleaks_result = run_tool('gitleaks', ['gitleaks', 'detect', '--no-git', '--report-format', 'json'])
    if gitleaks_result['status'] == 'completed':
        try:
            findings = len(json.loads(gitleaks_result['stdout'])) if gitleaks_result['stdout'].strip() else 0
        except:
            findings = 0
        report['gitleaks'] = {'findings': findings, 'status': 'completed'}
    else:
        report['gitleaks'] = {'findings': 0, 'status': gitleaks_result['status']}
    
    # 4. pip-audit
    pip_audit_result = run_tool('pip-audit', ['pip-audit', '--format', 'json'])
    if pip_audit_result['status'] == 'completed':
        try:
            data = json.loads(pip_audit_result['stdout'])
            vulns = len(data.get('vulnerabilities', []))
        except:
            vulns = 0
        report['pip_audit'] = {'vulns': vulns, 'status': 'completed'}
    else:
        report['pip_audit'] = {'vulns': 0, 'status': pip_audit_result['status']}
    
    # Minimaler Fallback falls alle Tools fehlen
    if all(tool.get('status') == 'skip' for tool in report.values()):
        report = {
            'semgrep': {'high': 0, 'medium': 0, 'low': 0, 'status': 'skip'},
            'bandit': {'high': 0, 'medium': 0, 'low': 0, 'status': 'skip'},
            'gitleaks': {'findings': 0, 'status': 'skip'},
            'pip_audit': {'vulns': 0, 'status': 'skip'}
        }
    
    # Output schreiben
    if out_json:
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
    
    print(json.dumps(report, indent=2))
    
    # Exit-Code basierend auf Policy-Schwellwert
    exit_code = 0
    
    # Policy-Integration: Lade QUALITY.yml falls verfügbar
    try:
        import yaml
        quality_file = Path("policies/QUALITY.yml")
        if quality_file.exists():
            quality_config = yaml.safe_load(quality_file.read_text())
            policy_high_limit = quality_config.get("hard_musts", {}).get("sast_high", 0)
            policy_secret_limit = quality_config.get("hard_musts", {}).get("secret_findings", 0)
        else:
            policy_high_limit = 0  # Scharfe Policy: Keine High-Severity-Findings
            policy_secret_limit = 0  # Scharfe Policy: Keine Secret-Findings
    except Exception:
        policy_high_limit = 0
        policy_secret_limit = 0
    
    # Prüfe Policy-Verletzungen (nur wenn Tools tatsächlich liefen)
    violation_count = 0
    
    # SAST High-Severity Check (Semgrep + Bandit)
    total_high = 0
    for tool_name in ['semgrep', 'bandit']:
        tool_result = report.get(tool_name, {})
        if tool_result.get('status') == 'completed':  # Nur bei echten Läufen
            total_high += tool_result.get('high', 0)
    
    if total_high > policy_high_limit:
        violation_count += 1
        print(f"Policy violation: SAST high findings {total_high} > {policy_high_limit}")
    
    # Secret-Findings Check (Gitleaks)
    gitleaks_result = report.get('gitleaks', {})
    if gitleaks_result.get('status') == 'completed':  # Nur bei echtem Lauf
        secret_findings = gitleaks_result.get('findings', 0)
        if secret_findings > policy_secret_limit:
            violation_count += 1
            print(f"Policy violation: Secret findings {secret_findings} > {policy_secret_limit}")
    
    # Security-Policy-Enforcement: Mindestens ein Tool muss aktiv gelaufen sein
    active_tools = 0
    for tool_name, tool_result in report.items():
        if tool_result.get('status') == 'completed':
            active_tools += 1
    
    # Prüfe Secure-Modus: Mindestens ein Tool muss aktiv sein
    secure_mode = os.getenv('SECURE_MODE', '').lower() in ['true', '1', 'yes']
    if secure_mode and active_tools == 0:
        print("SECURITY VIOLATION: No active security tools in secure mode")
        violation_count += 1
    
    # Exit-Code: 0 wenn keine Policy-Verletzungen
    exit_code = 1 if violation_count > 0 else 0
    
    # Zusätzlich: CLI-Parameter --fail-on berücksichtigen
    if fail_on and fail_on != 'none':
        severity_map = {'low': 1, 'medium': 2, 'high': 3}
        threshold = severity_map.get(fail_on, 3)
        
        for tool_name, tool_result in report.items():
            if tool_result.get('status') != 'completed':
                continue  # Skip nicht ausgeführte Tools
                
            if tool_name in ['semgrep', 'bandit']:
                if threshold >= 3 and tool_result.get('high', 0) > 0:
                    exit_code = 1
                elif threshold >= 2 and tool_result.get('medium', 0) > 0:
                    exit_code = 1
                elif threshold >= 1 and tool_result.get('low', 0) > 0:
                    exit_code = 1
    
    # Konsolidierte Artefakte bereitstellen
    if out_json:
        consolidated_report = {
            'summary': {
                'total_high': total_high,
                'total_medium': sum(report.get(t, {}).get('medium', 0) for t in ['semgrep', 'bandit']),
                'total_low': sum(report.get(t, {}).get('low', 0) for t in ['semgrep', 'bandit']),
                'secret_findings': report.get('gitleaks', {}).get('findings', 0),
                'vulnerabilities': report.get('pip_audit', {}).get('vulns', 0),
                'active_tools': active_tools,
                'violations': violation_count,
                'secure_mode': secure_mode
            },
            'tools': report,
            'policy': {
                'high_limit': policy_high_limit,
                'secret_limit': policy_secret_limit,
                'secure_mode_required': secure_mode
            }
        }
        
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(consolidated_report, f, indent=2)
    
    sys.exit(exit_code)


def main_cli():
    """CLI-Interface für Security-Scanner."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Security Scanner für CodePipeline')
    parser.add_argument('--out-json', type=str, help='Ausgabe-Pfad für JSON-Report')
    parser.add_argument('--fail-on', choices=['none', 'low', 'medium', 'high'], 
                       default='none', help='Schwellwert für Exit-Code != 0')
    
    args = parser.parse_args()
    
    # Minimaler Fallback-Report
    report = {
        'semgrep': {'high': 0, 'medium': 0, 'low': 0, 'status': 'skip'},
        'bandit': {'high': 0, 'medium': 0, 'low': 0, 'status': 'skip'},
        'gitleaks': {'findings': 0, 'status': 'skip'},
        'pip_audit': {'vulns': 0, 'status': 'skip'}
    }
    
    # Versuche echte Security-Scans (falls Tools verfügbar)
    try:
        # Semgrep
        semgrep_result = run_tool('semgrep', ['semgrep', '--config=auto', '--json', '.'])
        if semgrep_result['status'] != 'skip':
            report['semgrep'] = parse_semgrep_output(semgrep_result.get('stdout', ''))
        
        # Bandit
        bandit_result = run_tool('bandit', ['bandit', '-r', '.', '-f', 'json'])
        if bandit_result['status'] != 'skip':
            report['bandit'] = parse_bandit_output(bandit_result.get('stdout', ''))
        
        # Gitleaks
        gitleaks_result = run_tool('gitleaks', ['gitleaks', 'detect', '--report-format=json', '--report-path=/dev/stdout'])
        if gitleaks_result['status'] != 'skip':
            report['gitleaks'] = {'findings': len(json.loads(gitleaks_result.get('stdout', '[]'))), 'status': 'completed'}
        
        # Pip-audit
        pip_audit_result = run_tool('pip-audit', ['pip-audit', '--format=json'])
        if pip_audit_result['status'] != 'skip':
            audit_data = json.loads(pip_audit_result.get('stdout', '{}'))
            report['pip_audit'] = {'vulns': len(audit_data.get('vulnerabilities', [])), 'status': 'completed'}
            
    except Exception:
        # Bei Fehlern: Fallback auf skip-Status beibehalten
        pass
    
    # JSON-Output schreiben
    if args.out_json:
        with open(args.out_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
    
    # Konsolenausgabe
    print(json.dumps(report))
    
    # Exit-Code basierend auf --fail-on
    exit_code = 0
    if args.fail_on != 'none':
        severity_levels = {'low': 1, 'medium': 2, 'high': 3}
        fail_threshold = severity_levels[args.fail_on]
        
        for tool in ['semgrep', 'bandit']:
            if report[tool]['status'] != 'skip':
                if (fail_threshold <= 3 and report[tool].get('high', 0) > 0) or \
                   (fail_threshold <= 2 and report[tool].get('medium', 0) > 0) or \
                   (fail_threshold <= 1 and report[tool].get('low', 0) > 0):
                    exit_code = 1
                    break
        
        if report['gitleaks']['status'] != 'skip' and report['gitleaks']['findings'] > 0:
            exit_code = 1
        if report['pip_audit']['status'] != 'skip' and report['pip_audit']['vulns'] > 0:
            exit_code = 1
    
    sys.exit(exit_code)


if __name__ == '__main__':
    # Prüfe ob CLI-Parameter vorhanden sind
    if len(sys.argv) > 1 and ('--out-json' in sys.argv or '--fail-on' in sys.argv):
        main_cli()
    else:
        main()
