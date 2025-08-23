#!/usr/bin/env python3
import sys, json
report = {
 'semgrep': {'high': 0, 'medium': 0, 'low': 0, 'status': 'skip'},
 'bandit': {'high': 0, 'medium': 0, 'low': 0, 'status': 'skip'},
 'gitleaks': {'findings': 0, 'status': 'skip'},
 'pip_audit': {'vulns': 0, 'status': 'skip'}
}
if len(sys.argv) >= 3 and sys.argv[1] == '--out-json':
 with open(sys.argv[2], 'w', encoding='utf-8') as f:
  json.dump(report, f)
print(json.dumps(report))
sys.exit(0)
