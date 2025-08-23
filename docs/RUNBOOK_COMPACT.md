# CodePipeline Runbook (Compact)

**Version**: 1.0 | **Target**: Ops-Teams

## 🚀 Quick Commands

### Standard-Feature-Development
```bash
# Basic Feature
python -m codepipeline.cli feature --spec features/example.json --branch feature/example-001

# High-Security Feature  
python -m codepipeline.cli feature --spec features/secure.json --branch feature/secure --secure

# Dry-Run Test
python -m codepipeline.cli feature --spec features/test.json --branch test/dry --dry-run
```

### Health-Checks
```bash
# System-Status
python -m codepipeline.cli spec validate examples/sample-spec.json

# Secret-Status
python -c "from hardened_secrets_flow import get_secret_manager; print('Secrets:', get_secret_manager().get_cache_status())"

# Pipeline-Status
ls -la pipeline_artifacts/ | grep -E "\.(json|md)$"
```

## 🔧 Configuration

### Required Environment
```bash
export SECRET_OPENAI_API_KEY="sk-..."
export SECRET_GITHUB_TOKEN="ghp_..."
```

### Feature-Spec Template
```json
{
  "id": "FEATURE-XXX",
  "title": "Feature Title", 
  "version": 1,
  "goal": "Clear objective",
  "target_paths": ["src/module/", "tests/module/"],
  "risk_level": "low|medium|high",
  "reviewers": ["team-lead"],
  "model": "gpt-4o-mini",
  "token_budget": 5000,
  "tests": {"coverage_min": 80},
  "hard_musts": ["coverage_threshold"]
}
```

## 🚨 Common Issues & Exit Codes

| Code | Issue | Quick Fix |
|------|-------|-----------|
| 2 | Spec Invalid | Check reviewers (high-risk needs 2+) |
| 3 | Secret Missing | `export SECRET_OPENAI_API_KEY="sk-..."` |
| 4 | Security Fail | Check `bandit_report.json`, fix findings |
| 5 | Coverage Low | Add tests, check `test_report.json` |
| 6 | Sandbox Violation | Verify `target_paths` in spec |
| 7 | Token Exceeded | Increase `token_budget` or optimize prompts |

## 📊 Monitoring

### Key Artifacts
- `qa_scorecard.json`: Overall quality score
- `pipeline_result.json`: Stage-by-stage results
- `bandit_report.json`: Security findings
- `test_report.json`: Coverage and test results
- `sbom.json`: Dependencies and vulnerabilities

### Quick Metrics
```bash
# Success Rate
cat pipeline_artifacts/pipeline_result.json | jq '.success'

# Coverage
cat pipeline_artifacts/test_report.json | jq '.coverage_percentage'

# Security Findings  
cat pipeline_artifacts/bandit_report.json | jq '.results | length'

# Token Usage
python -c "from audit_trail_observability import ObservabilityManager; print(ObservabilityManager('check', ':memory:').get_run_statistics()['total_tokens'])"
```

## 🛠️ Troubleshooting

### Pipeline Stuck/Failed
```bash
# Check last run
tail -20 pipeline_artifacts/*.log

# Force cleanup
rm -rf pipeline_artifacts/
mkdir pipeline_artifacts

# Restart with dry-run
python -m codepipeline.cli feature --spec last-spec.json --branch debug/restart --dry-run
```

### High Memory Usage
```bash
# Check processes
ps aux | grep python | head -5

# Cleanup artifacts
find pipeline_artifacts/ -name "*.json" -mtime +1 -delete

# Restart services
pkill -f codepipeline
```

### Secret Issues
```bash
# Test secret resolution
python -c "
from hardened_secrets_flow import validate_secrets_early
validate_secrets_early('openai_api_key', 'github_token')
print('✅ Secrets OK')
"

# Rotate if compromised
export SECRET_OPENAI_API_KEY="new-key"
export SECRET_GITHUB_TOKEN="new-token"
```

## 📞 Escalation

**P0 (Security/Outage)**: security@company.com, +1-555-ONCALL  
**P1 (Pipeline-Fail)**: devops@company.com  
**P2 (Performance)**: Create GitHub issue  

## 🔄 Maintenance

### Daily
- Check failed runs: `grep -r "FAILURE" pipeline_artifacts/`
- Monitor disk usage: `du -sh pipeline_artifacts/`

### Weekly  
- Rotate secrets if needed
- Clean old artifacts: `find pipeline_artifacts/ -mtime +7 -delete`
- Review performance trends

### Emergency Procedures
```bash
# Complete system reset
pkill -f codepipeline
rm -rf pipeline_artifacts/ audit_trail.db
mkdir pipeline_artifacts
python -m codepipeline.cli spec validate examples/sample-spec.json
```

---
**Compact Runbook v1.0** | For detailed procedures see [RUNBOOK.md](RUNBOOK.md)
