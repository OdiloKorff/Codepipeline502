import logging

"""Semgrep integration for static code analysis."""
import subprocess
import sys


class SemgrepAnalyzer:
    def __init__(self, config=None):
        self.config = config or {}

    def run_scan(self, path='.'):
        cmd = ['semgrep', '--config', 'p/owasp', '--config', 'p/python-security', path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        findings = result.stdout
        severity = self._parse_severity(findings)
        if severity == 'HIGH':
            logging.info('High severity findings detected. Failing pipeline.')
            sys.exit(1)
        logging.info('Scan completed with no high severity findings.')
        return findings

    def _parse_severity(self, findings_output):
        # Simplified parser: look for 'severity: ERROR' as HIGH
        if 'severity: ERROR' in findings_output:
            return 'HIGH'
        return 'LOW'
