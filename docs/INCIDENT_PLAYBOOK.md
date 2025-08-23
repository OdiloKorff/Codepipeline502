# CodePipeline Incident Playbook

**Version**: 1.0  
**Letzte Aktualisierung**: 2025-01-17  
**Zielgruppe**: SRE, DevOps, On-Call Engineers

## 🚨 Incident Response Overview

Dieses Playbook beschreibt strukturierte Prozeduren für häufige CodePipeline-Incidents. Ziel ist schnelle Wiederherstellung und systematische Root-Cause-Analyse.

### Incident-Kategorien

- **P0 - Critical**: Security-Breach, System-Outage
- **P1 - High**: Pipeline-Failures, Data-Loss
- **P2 - Medium**: Performance-Degradation, Config-Issues
- **P3 - Low**: Minor-Bugs, Enhancement-Requests

---

## 🔥 P0 - Critical Incidents

### Security-Breach (Secret-Leakage)

**Symptome:**
- Secret-Werte in Logs sichtbar
- Unauthorized API-Access
- Audit-Trail zeigt verdächtige Secret-Zugriffe

**Sofortmaßnahmen (0-15 min):**
```bash
# 1. Betroffene Secrets identifizieren
grep -r "sk-" pipeline_artifacts/
grep -r "ghp_" pipeline_artifacts/

# 2. Secrets sofort rotieren
# OpenAI API Key
export SECRET_OPENAI_API_KEY="NEW_KEY"

# GitHub Token
export SECRET_GITHUB_TOKEN="NEW_TOKEN"

# 3. Betroffene Services neustarten
systemctl restart codepipeline
```

**Untersuchung (15-60 min):**
```bash
# Audit-Trail analysieren
python -c "
from audit_trail_observability import ObservabilityManager
mgr = ObservabilityManager('INCIDENT-001', 'audit_trail.db')
audit_log = mgr.db.get_runs(limit=100)
print('Recent runs:', len(audit_log))
"

# Secret-Access-Log prüfen
python -c "
from hardened_secrets_flow import get_secret_manager
mgr = get_secret_manager('INCIDENT-ANALYSIS')
audit = mgr.get_access_audit_log()
for entry in audit[-20:]:
    print(f'{entry[\"timestamp\"]}: {entry[\"key\"]} -> {entry[\"action\"]}')
"
```

**Wiederherstellung:**
- Alle Secrets rotiert ✅
- Logs bereinigt ✅
- Monitoring-Alerts konfiguriert ✅

### System-Outage (Pipeline nicht erreichbar)

**Symptome:**
- CLI-Commands schlagen fehl
- API-Timeouts
- Health-Checks fehlgeschlagen

**Sofortmaßnahmen:**
```bash
# 1. System-Status prüfen
python -m codepipeline.cli spec validate examples/sample-spec.json

# 2. Dependencies prüfen
pip check
python --version

# 3. Disk-Space prüfen
df -h
du -sh pipeline_artifacts/

# 4. Memory-Usage prüfen
free -m
ps aux | grep python | head -10
```

**Service-Neustart:**
```bash
# Graceful restart
pkill -TERM -f codepipeline
sleep 5
pkill -KILL -f codepipeline

# Service neu starten
python -m codepipeline.cli feature --spec examples/sample-spec.json --dry-run
```

---

## ⚠️ P1 - High Priority Incidents

### Pipeline-Failure (Alle Runs fehlschlagen)

**Symptome:**
- Exit-Code != 0 bei allen Runs
- QA-Scorecard zeigt 0/100
- Keine PR-Erstellung

**Diagnose:**
```bash
# 1. Letzte Pipeline-Artifacts prüfen
ls -la pipeline_artifacts/
cat pipeline_artifacts/pipeline_result.json | jq '.success'

# 2. Stage-wise Analyse
cat pipeline_artifacts/qa_scorecard.json | jq '.stages'

# 3. Logs analysieren
tail -100 pipeline_artifacts/*.log
```

**Häufige Ursachen & Fixes:**

**Linting-Failures:**
```bash
# Violations prüfen
cat pipeline_artifacts/lint_report.json

# Quick-Fix für Demo
python -m ruff check --fix .
```

**Test-Failures:**
```bash
# Test-Report analysieren
cat pipeline_artifacts/test_report.json

# Coverage prüfen
python -m pytest --cov=. --cov-report=term
```

**Security-Failures:**
```bash
# Security-Report prüfen
cat pipeline_artifacts/bandit_report.json

# Findings analysieren
python -m bandit -r . -f json | jq '.results[].issue_text'
```

### Token-Budget-Exceeded (Exit 7)

**Symptome:**
- "Token budget exceeded" in Logs
- LLM-Calls werden abgebrochen
- Hohe Cost-Alerts

**Sofortmaßnahmen:**
```bash
# 1. Aktueller Token-Verbrauch
python -c "
from audit_trail_observability import ObservabilityManager
mgr = ObservabilityManager('TOKEN-CHECK', ':memory:')
stats = mgr.get_run_statistics()
print(f'Total tokens: {stats[\"total_tokens\"]:,}')
print(f'Total cost: ${stats[\"total_cost_usd\"]:.4f}')
"

# 2. Budget temporär erhöhen
python -m codepipeline.cli feature \
  --spec features/current.json \
  --branch feature/emergency-fix \
  --token-budget 20000
```

**Budget-Optimierung:**
- Prompt-Templates kürzen
- Model auf gpt-4o-mini wechseln
- Batch-Processing implementieren

---

## 📊 P2 - Medium Priority Incidents

### Performance-Degradation

**Symptome:**
- Pipeline-Laufzeit > 10 Minuten
- High Memory-Usage
- Slow Response-Times

**Performance-Analyse:**
```bash
# 1. Pipeline-Timing analysieren
cat pipeline_artifacts/pipeline_result.json | jq '.executions[] | {stage, duration}'

# 2. Memory-Profiling
python -c "
import psutil
process = psutil.Process()
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB')
print(f'CPU: {process.cpu_percent()}%')
"

# 3. Disk-I/O prüfen
iostat -x 1 5
```

**Optimierungsmaßnahmen:**
- Artifacts-Cleanup: `rm -rf old_pipeline_artifacts/`
- Cache-Optimierung: Secret-Cache-TTL reduzieren
- Parallelisierung: Concurrent-Operations erhöhen

### Configuration-Issues

**Symptome:**
- Unexpected behavior
- Policy-Violations
- Integration-Failures

**Config-Validation:**
```bash
# 1. Spec-Validation
python -m codepipeline.cli spec validate features/*.json

# 2. Policy-Check
cat policies/QUALITY.yml | yq '.coverage.minimum'

# 3. Environment-Check
env | grep SECRET_ | wc -l
echo "Secrets configured: $(env | grep SECRET_ | wc -l)"
```

---

## 🔧 P3 - Low Priority Incidents

### Minor-Performance-Issues

**Standard-Optimierungen:**
```bash
# Artifacts-Cleanup
find pipeline_artifacts/ -name "*.json" -mtime +7 -delete

# Log-Rotation
find . -name "*.log" -size +100M -delete

# Dependency-Cleanup
pip-autoremove -y
```

### Enhancement-Requests

**Feature-Request-Process:**
1. GitHub-Issue erstellen
2. Technical-Design-Document
3. Implementation-Plan
4. Testing-Strategy

---

## 📋 Incident-Response-Checkliste

### Incident-Start
- [ ] Incident-Severity bestimmt (P0-P3)
- [ ] Incident-Commander benannt
- [ ] Communication-Channel erstellt (#incident-YYYYMMDD-HHmm)
- [ ] Stakeholder informiert

### Investigation
- [ ] Initial-Assessment durchgeführt
- [ ] Logs/Metrics gesammelt
- [ ] Timeline erstellt
- [ ] Hypothesis entwickelt

### Resolution
- [ ] Workaround implementiert
- [ ] Root-Cause identifiziert
- [ ] Permanent-Fix deployed
- [ ] Verification durchgeführt

### Post-Incident
- [ ] Incident-Report erstellt
- [ ] Lessons-Learned-Session
- [ ] Process-Improvements implementiert
- [ ] Documentation aktualisiert

---

## 📞 Eskalations-Kontakte

**Immediate Response (P0):**
- Security-Team: security@company.com
- On-Call-Engineer: +1-555-ONCALL

**Business Hours (P1-P2):**
- DevOps-Team: devops@company.com
- Engineering-Lead: tech-lead@company.com

**Non-Urgent (P3):**
- Support-Ticket: support@company.com
- GitHub-Issues: https://github.com/company/codepipeline/issues

---

## 📚 Useful Commands Cheatsheet

```bash
# Quick Health-Check
python -m codepipeline.cli spec validate examples/sample-spec.json

# Emergency Pipeline-Run
python -m codepipeline.cli feature --spec emergency.json --dry-run

# Audit-Trail-Export
python -c "
from audit_trail_observability import ObservabilityManager
mgr = ObservabilityManager('EXPORT', 'audit_trail.db')
stats = mgr.get_run_statistics()
print('Export ready:', stats['total_runs'] > 0)
"

# Secret-Status-Check
python -c "
from hardened_secrets_flow import get_secret_manager
mgr = get_secret_manager('HEALTH-CHECK')
status = mgr.get_cache_status()
print(f'Cached secrets: {status[\"total_secrets\"]}')
"

# Performance-Check
python unified_cicd_pipeline.py | grep "Performance:"
```

---

**📝 Playbook-Version:** 1.0  
**🔄 Nächste Review:** 2025-04-17  
**✍️ Autor:** SRE-Team
