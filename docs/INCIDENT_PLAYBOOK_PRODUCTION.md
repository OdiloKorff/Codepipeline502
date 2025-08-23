# 🚨 CodePipeline Incident Playbook

## 🎯 Übersicht

Dieses Playbook beschreibt die systematische Behandlung von Incidents im CodePipeline Production System. Ziel ist die schnelle Wiederherstellung des Service und die Vermeidung von Wiederholungen.

**Zielgruppe:** Operations, Support, Development  
**Aktualisiert:** 2024-12-17

---

## 🚦 Incident-Klassifikation

| Severity | Beschreibung | Response-Zeit | Beispiele |
|----------|--------------|---------------|-----------|
| **P0 - Critical** | System komplett down | 15 min | Backend nicht erreichbar, kompletter Ausfall |
| **P1 - High** | Funktionalität stark beeinträchtigt | 1 Stunde | Alle Runs schlagen fehl, Security-Gates broken |
| **P2 - Medium** | Einzelne Features betroffen | 4 Stunden | Einzelne Gates instabil, Performance-Probleme |
| **P3 - Low** | Minor Issues, Workaround vorhanden | 24 Stunden | UI-Glitches, Log-Warnings |

---

## 🔍 Incident-Response-Prozess

### Phase 1: Detection & Initial Response (0-15 min)

#### 1.1 Incident-Erkennung
```bash
# Health-Check
curl -f http://127.0.0.1:8000/api/health

# Log-Check
tail -100 logs/codepipeline.log | grep -i error

# Process-Check
ps aux | grep python | grep codepipeline
```

#### 1.2 Initial Assessment
- **Impact:** Wie viele User/Runs betroffen?
- **Scope:** Welche Komponenten betroffen?
- **Urgency:** Business-Impact einschätzen

#### 1.3 Immediate Actions
```bash
# 1. Service-Status dokumentieren
echo "$(date): Incident detected - $(description)" >> incidents.log

# 2. Stakeholder benachrichtigen (bei P0/P1)
# Slack: #codepipeline-alerts
# Email: ops-team@company.com

# 3. War-Room etablieren (bei P0)
```

### Phase 2: Investigation (15 min - 1 hour)

#### 2.1 Data Collection
```bash
# System-Status
df -h                    # Disk-Space
free -m                  # Memory
top                      # CPU/Processes

# Application-Logs
tail -500 logs/codepipeline.log
grep -i "error\|exception\|failed" logs/*.log

# Database-Status
sqlite3 audit_trail.db ".schema"
sqlite3 audit_trail.db "SELECT COUNT(*) FROM runs WHERE status='failed' AND start_time > datetime('now', '-1 hour');"

# Network-Status
netstat -tulpn | grep :8000
curl -I http://127.0.0.1:8000/api/health
```

#### 2.2 Root-Cause-Analysis
```bash
# Recent Changes
git log --oneline --since="24 hours ago"

# Configuration-Drift
diff policies/QUALITY.yml policies/QUALITY.yml.backup

# Resource-Usage
iostat 1 5
vmstat 1 5
```

### Phase 3: Mitigation (1-4 hours)

#### 3.1 Immediate Fixes
Siehe spezifische Incident-Kategorien unten.

#### 3.2 Workarounds
```bash
# Fallback auf CLI-Mode
python -m codepipeline.cli feature --spec spec.json --dry-run

# Reduced-Functionality-Mode
export CODEPIPELINE_SAFE_MODE=true
```

### Phase 4: Resolution & Recovery

#### 4.1 Fix-Deployment
```bash
# Code-Fix
git pull origin main
pip install -r requirements.txt

# Restart-Services
pkill -f "production_gui_backend"
python production_gui_backend.py --start-server &

# Verification
curl http://127.0.0.1:8000/api/health
```

#### 4.2 Monitoring
```bash
# 15-Minuten-Monitoring nach Fix
watch -n 60 'curl -s http://127.0.0.1:8000/api/health | jq'
```

---

## 🎯 Spezifische Incident-Kategorien

### 🚨 Backend-Outage (P0)

#### Symptome
- GUI nicht erreichbar (HTTP 503/Connection refused)
- API-Endpoints returnen Errors
- Runs können nicht gestartet werden

#### Diagnose
```bash
# 1. Process-Check
ps aux | grep production_gui_backend
systemctl status codepipeline  # falls systemd

# 2. Port-Check
netstat -tulpn | grep :8000
lsof -i :8000

# 3. Log-Analysis
tail -100 logs/codepipeline.log
journalctl -u codepipeline --since "10 minutes ago"
```

#### Fixes
```bash
# Quick-Fix: Service-Restart
pkill -f production_gui_backend
python production_gui_backend.py --start-server &

# Persistent-Fix: Systemd-Service
systemctl restart codepipeline
systemctl enable codepipeline

# Emergency-Fix: Different-Port
python production_gui_backend.py --start-server --port 8001
```

### 🛡️ Security-Gate-Failures (P1)

#### Symptome
- Alle/viele Runs schlagen bei Security-Scan fehl
- False-Positives in Security-Reports
- Security-Tools nicht verfügbar

#### Diagnose
```bash
# 1. Tool-Availability
which bandit semgrep safety
bandit --version
semgrep --version

# 2. Recent-Runs-Analysis
sqlite3 audit_trail.db "SELECT gate_results FROM runs WHERE start_time > datetime('now', '-1 hour');"

# 3. Policy-Check
cat policies/QUALITY.yml | grep -A 10 security
```

#### Fixes
```bash
# 1. Tool-Installation
pip install bandit semgrep safety

# 2. Policy-Adjustment (temporary)
cp policies/QUALITY.yml policies/QUALITY.yml.backup
# Edit QUALITY.yml: Increase security.max_high temporarily

# 3. Baseline-Update
python production_security_scanner.py --update-baselines

# 4. Emergency-Bypass (P0 only)
export CODEPIPELINE_SKIP_SECURITY=true  # DANGEROUS!
```

### 🧪 QA-Gate-Failures (P1)

#### Symptome
- Coverage-Gate schlägt fehl obwohl Tests laufen
- Linting-Errors durch neue Rules
- Type-Checking-Failures

#### Diagnose
```bash
# 1. Tool-Status
python -m pytest --version
python -m ruff --version  
python -m mypy --version

# 2. Coverage-Analysis
python -m pytest --cov=. --cov-report=term
coverage report

# 3. Config-Check
cat pyproject.toml | grep -A 20 "\[tool.ruff"
cat mypy.ini
```

#### Fixes
```bash
# 1. Quick-Coverage-Fix
# Temporär niedrigere Schwelle
export CODEPIPELINE_COVERAGE_MIN=70

# 2. Linting-Fix
python -m ruff check . --fix

# 3. Type-Check-Fix
python -m mypy . --ignore-missing-imports

# 4. Emergency-Skip (P0 only)
export CODEPIPELINE_SKIP_QA=true  # DANGEROUS!
```

### 💰 Token-Budget-Exhaustion (P2)

#### Symptome
- Runs schlagen mit "Token budget exceeded" fehl
- OpenAI-API-Rate-Limits erreicht
- Hohe API-Kosten

#### Diagnose
```bash
# 1. Token-Usage-Analysis
sqlite3 audit_trail.db "SELECT AVG(json_extract(metrics, '$.token_usage')) FROM runs WHERE start_time > datetime('now', '-24 hours');"

# 2. API-Key-Status
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/usage

# 3. Spec-Analysis
find . -name "*.json" -exec jq '.token_budget' {} \;
```

#### Fixes
```bash
# 1. Emergency-Budget-Increase
# Edit Specs: Increase token_budget temporär

# 2. Model-Downgrade
# Edit Specs: "gpt-4o-mini" statt "gpt-4o"

# 3. Prompt-Optimization
# Kürzere Prompts, weniger Context

# 4. Rate-Limit-Handling
export OPENAI_API_RETRY_DELAY=60  # Seconds between retries
```

### 🔐 Secret-Management-Issues (P1)

#### Symptome
- "SecretNotAvailableError" bei Run-Start
- Authentication-Failures mit External-APIs
- Expired-Tokens

#### Diagnose
```bash
# 1. Secret-Availability
echo $OPENAI_API_KEY | cut -c1-10  # First 10 chars only
echo $GITHUB_TOKEN | cut -c1-10

# 2. Vault-Status (Enterprise)
vault status
vault auth -method=oidc

# 3. Token-Validation
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

#### Fixes
```bash
# 1. Environment-Fix
export OPENAI_API_KEY="sk-new-key-here"
export GITHUB_TOKEN="ghp_new-token-here"

# 2. Vault-Refresh (Enterprise)
vault write -method=oidc auth/oidc/login role=codepipeline

# 3. .env-File-Fix (Development)
echo "OPENAI_API_KEY=sk-new-key" > .env
echo "GITHUB_TOKEN=ghp-new-token" >> .env

# 4. Service-Restart (nach Secret-Update)
pkill -f production_gui_backend
python production_gui_backend.py --start-server &
```

### 🗄️ Database-Issues (P2)

#### Symptome
- SQLite-Errors in Logs
- Audit-Trail nicht verfügbar
- "Database is locked" Errors

#### Diagnose
```bash
# 1. Database-Status
sqlite3 audit_trail.db ".schema"
sqlite3 audit_trail.db "PRAGMA integrity_check;"

# 2. File-Permissions
ls -la audit_trail.db*
lsof audit_trail.db

# 3. Disk-Space
df -h .
```

#### Fixes
```bash
# 1. Database-Repair
sqlite3 audit_trail.db "VACUUM;"
sqlite3 audit_trail.db "REINDEX;"

# 2. Lock-Resolution
fuser audit_trail.db  # Kill locking processes
rm -f audit_trail.db-wal audit_trail.db-shm

# 3. Permission-Fix
chmod 664 audit_trail.db
chown codepipeline:codepipeline audit_trail.db

# 4. Emergency-Backup-Restore
cp audit_trail.db.backup audit_trail.db
```

---

## 📋 Post-Incident-Review

### Immediate Actions (within 24h)
1. **Incident-Summary** erstellen
2. **Timeline** dokumentieren  
3. **Root-Cause** bestätigen
4. **Temporary-Fixes** in permanent Fixes umwandeln

### Follow-up Actions (within 1 week)
1. **Process-Improvements** identifizieren
2. **Monitoring-Gaps** schließen
3. **Documentation** aktualisieren
4. **Team-Training** bei Bedarf

### Template: Incident-Report
```markdown
# Incident Report: [INCIDENT-ID]

## Summary
- **Date:** YYYY-MM-DD HH:MM
- **Duration:** X hours Y minutes  
- **Severity:** P0/P1/P2/P3
- **Impact:** X users affected, Y runs failed

## Timeline
- HH:MM - Incident detected
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix deployed
- HH:MM - Service restored

## Root Cause
[Detailed technical explanation]

## Resolution
[What was done to fix it]

## Prevention
[How to prevent this in the future]

## Action Items
- [ ] Action 1 (Owner: Name, Due: Date)
- [ ] Action 2 (Owner: Name, Due: Date)
```

---

## 🔧 Tools & Commands

### Emergency-Toolkit
```bash
# Quick-Status-Script
#!/bin/bash
echo "=== CodePipeline Health Check ==="
echo "Backend: $(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health)"
echo "Disk: $(df -h . | tail -1 | awk '{print $5}')"
echo "Memory: $(free -m | grep Mem | awk '{print ($3/$2)*100"%"}')"
echo "Recent Errors: $(tail -100 logs/codepipeline.log | grep -c ERROR)"
echo "Active Runs: $(ps aux | grep -c python.*codepipeline)"
```

### Monitoring-Commands
```bash
# Real-time-Log-Monitoring
tail -f logs/codepipeline.log | grep --color=always -E "(ERROR|CRITICAL|Exception)"

# Performance-Monitoring  
watch -n 5 'ps aux | grep python | head -10'

# Database-Monitoring
watch -n 10 'sqlite3 audit_trail.db "SELECT status, COUNT(*) FROM runs WHERE start_time > datetime(\"now\", \"-1 hour\") GROUP BY status;"'
```

---

## 📞 Escalation-Matrix

| Incident-Type | L1 (0-30min) | L2 (30min-2h) | L3 (2h+) |
|---------------|--------------|---------------|----------|
| **Backend-Down** | Ops-Team | Dev-Lead | CTO |
| **Security-Issues** | Security-Team | CISO | Legal |
| **Data-Loss** | DBA | Dev-Lead + Legal | CEO |
| **Performance** | Ops-Team | Dev-Team | Dev-Lead |

### Kontakte
- **Ops-Team:** ops@company.com, +49-123-456789
- **Dev-Team:** dev@company.com, Slack: #dev-urgent  
- **Security:** security@company.com, +49-123-456790
- **Management:** management@company.com

---

*Dieses Playbook ermöglicht es, geblockte Gates und typische Failures zielgerichtet zu beheben und die Service-Verfügbarkeit schnell wiederherzustellen.*
