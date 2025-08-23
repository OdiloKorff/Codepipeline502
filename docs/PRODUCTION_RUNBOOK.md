# 📚 CodePipeline Production Runbook

## 🎯 Übersicht

CodePipeline ist ein vollautomatisiertes Enterprise-System für sichere Code-Generierung mit umfassenden Quality Gates, Security-Scanning und Compliance-Enforcement.

**Version:** 1.0.0  
**Letzte Aktualisierung:** 2024-12-17  

---

## 🚀 Schnellstart

### Minimaler Happy-Path
```bash
# 1. Backend starten
python production_gui_backend.py --start-server

# 2. GUI öffnen
# http://127.0.0.1:8000

# 3. CLI-Alternative
python -m codepipeline.cli feature --spec example-spec.json --branch feature/demo
```

### Systemanforderungen
- **Python:** 3.10+
- **RAM:** 2GB minimum, 4GB empfohlen
- **Disk:** 1GB für Artifacts und Logs
- **Network:** HTTPS-Zugriff zu OpenAI API

---

## 🔧 Startparameter

### GUI-Backend
```bash
python production_gui_backend.py [--start-server]

# Optionen:
--start-server    # Startet FastAPI-Server auf Port 8000
```

### CLI
```bash
python -m codepipeline.cli feature [OPTIONS]

# Required:
--spec PATH       # Pfad zur FeatureSpec (JSON/YAML)

# Optional:
--branch TEXT     # Git-Branch (default: feature/{spec_id})
--secure         # Security-Mode aktivieren (default: True)
--dry-run        # Nur Validierung, keine Änderungen
```

### Weitere Tools
```bash
# Spec-Validierung
python -m codepipeline.cli spec validate SPEC_FILE

# Reproduzierbarkeits-Check
python production_reproducibility_supply_chain.py

# Test-Suite
python production_test_suite_proof_safety.py

# CI-Workflow
python production_central_ci_workflow.py
```

---

## 📋 Policies

### Quality-Policies (`policies/QUALITY.yml`)
```yaml
qa_scorecard:
  coverage_min: 80.0
  linting_max_violations: 0
  security_max_high: 0
  hard_musts: ["test_coverage", "security_scan"]

security:
  max_critical: 0
  max_high: 0
  max_medium: 5
  required_tools: ["bandit", "secret_scan"]

sbom_license:
  allowed_licenses:
    - "MIT"
    - "Apache-2.0" 
    - "BSD-3-Clause"
    - "PSF-2.0"
  max_vulnerabilities: 0

branch_protection:
  required_reviewers: 1
  require_status_checks: true
  enforce_admins: true
```

### Security-Policies
- **Fail-Closed:** System verweigert bei Unsicherheit
- **Zero-Trust:** Alle Eingaben werden validiert
- **Path-Traversal-Schutz:** Keine `../` oder absolute Pfade
- **Secret-Scanning:** Automatische Erkennung von API-Keys, Passwords
- **Network-Isolation:** Kein Netzwerk-Egress in Sandbox

---

## 🚨 Exit-Codes

| Code | Bedeutung | Aktion |
|------|-----------|--------|
| 0 | Erfolg | ✅ Alles OK |
| 1 | Allgemeiner Fehler | 🔍 Logs prüfen |
| 2 | Spec-Validierung fehlgeschlagen | 📝 Spec korrigieren |
| 3 | Security-Gate fehlgeschlagen | 🛡️ Sicherheitsprobleme beheben |
| 4 | QA-Gate fehlgeschlagen | 🧪 Qualitätsprobleme beheben |
| 5 | Token-Budget überschritten | 💰 Budget erhöhen oder Spec kürzen |
| 6 | Branch-Protection verletzt | 🔒 Protection-Rules prüfen |
| 7 | Sandbox-Violation | ⚠️ Gefährliche Operation blockiert |
| 8 | Network-Fehler | 🌐 Verbindung prüfen |
| 124 | Timeout | ⏱️ Längere Timeout-Werte |
| 127 | Tool nicht gefunden | 📦 Dependencies installieren |

---

## 🔍 Logs & Monitoring

### Log-Locations
```
logs/
├── codepipeline.log          # Haupt-Log
├── security-scan.log         # Security-Scanner
├── qa-scorecard.log          # Quality-Gates
└── audit-trail.db            # SQLite Audit-DB
```

### Log-Level
```bash
# Debug-Mode
export CODEPIPELINE_LOG_LEVEL=DEBUG

# Production-Mode
export CODEPIPELINE_LOG_LEVEL=INFO
```

### Health-Checks
```bash
# Backend-Health
curl http://127.0.0.1:8000/api/health

# CLI-Health
python -m codepipeline.cli --help
```

---

## 🛠️ Fehlerbehebung

### Häufige Probleme

#### 1. "ModuleNotFoundError: No module named 'X'"
```bash
# Lösung: Dependencies installieren
pip install -r requirements.txt
pip install fastapi uvicorn pydantic typer
```

#### 2. "SecretNotAvailableError: OPENAI_API_KEY"
```bash
# Lösung: API-Key setzen
export OPENAI_API_KEY="sk-your-key-here"

# Oder in .env-Datei
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

#### 3. "Permission denied" (Windows)
```bash
# Lösung: PowerShell als Administrator
# Oder WSL verwenden
wsl python production_gui_backend.py
```

#### 4. "Port already in use"
```bash
# Lösung: Anderen Port verwenden
uvicorn production_gui_backend:app --host 127.0.0.1 --port 8001
```

#### 5. "Gate failed: security_scan"
```bash
# Lösung: Security-Issues beheben
# 1. Logs prüfen: security-scan.log
# 2. Findings in security-report.json
# 3. Code entsprechend anpassen
```

### Performance-Issues

#### Langsame Runs
1. **Token-Budget reduzieren:** Kleinere Prompts
2. **Parallel-Gates aktivieren:** CI-Config anpassen  
3. **Cache nutzen:** Dependencies cachen
4. **Hardware:** Mehr RAM/CPU

#### Memory-Issues
1. **Artifact-Cleanup:** Alte Runs löschen
2. **Log-Rotation:** Logs regelmäßig archivieren
3. **Database-Cleanup:** Audit-Trail begrenzen

---

## 🔐 Security

### Secret-Management
```bash
# Priorität (höchste zuerst):
# 1. Vault/OIDC (Enterprise)
# 2. Environment Variables
# 3. .env-Datei (Development only)

# Vault-Setup (Enterprise)
export VAULT_ADDR="https://vault.company.com"
export VAULT_TOKEN="hvs.your-token"

# Environment-Setup
export OPENAI_API_KEY="sk-..."
export GITHUB_TOKEN="ghp_..."
```

### Network-Security
```bash
# Firewall-Rules (empfohlen)
# Outbound: nur HTTPS zu OpenAI/GitHub
# Inbound: nur Port 8000/8001 für GUI
```

### File-Permissions
```bash
# Restrictive Permissions
chmod 600 .env
chmod 700 artifacts/
chmod 644 *.py
```

---

## 📊 Metriken & Observability

### Key-Metrics
- **Success-Rate:** Anteil erfolgreicher Runs
- **Gate-Pass-Rate:** Anteil bestandener Gates pro Typ
- **Token-Usage:** Durchschnittlicher Token-Verbrauch
- **Duration:** Durchschnittliche Run-Zeit
- **Error-Rate:** Fehlerverteilung nach Exit-Code

### Monitoring-Setup
```bash
# Audit-Trail-Export
python production_audit_final.py --export

# Metrics-Dashboard
# Grafana/Prometheus-Integration über audit_trail.db
```

---

## 🔄 Wartung

### Regelmäßige Tasks

#### Täglich
```bash
# Log-Check
tail -f logs/codepipeline.log

# Health-Check
curl -f http://127.0.0.1:8000/api/health
```

#### Wöchentlich
```bash
# Artifact-Cleanup (älter als 7 Tage)
find artifacts/ -type f -mtime +7 -delete

# Log-Rotation
logrotate /etc/logrotate.d/codepipeline
```

#### Monatlich
```bash
# Security-Update
pip list --outdated
pip install --upgrade package-name

# Database-Cleanup
sqlite3 audit_trail.db "DELETE FROM runs WHERE start_time < date('now', '-30 days');"
```

### Backup-Strategy
```bash
# Critical Data
tar -czf backup-$(date +%Y%m%d).tar.gz \
  policies/ \
  audit_trail.db \
  .env \
  requirements.txt

# Restore
tar -xzf backup-YYYYMMDD.tar.gz
```

---

## 🚀 Deployment

### Production-Checklist
- [ ] Secrets in Vault/OIDC konfiguriert
- [ ] Policies reviewed und approved
- [ ] Branch-Protection aktiviert
- [ ] Monitoring/Alerting eingerichtet
- [ ] Backup-Strategy implementiert
- [ ] Team-Training abgeschlossen
- [ ] Incident-Response-Plan definiert

### Scaling
```bash
# Horizontal: Mehrere Backend-Instanzen
python production_gui_backend.py --start-server --port 8000
python production_gui_backend.py --start-server --port 8001

# Load-Balancer davor (nginx/HAProxy)
```

---

## 📞 Support

### Eskalation
1. **L1:** Logs prüfen, Standard-Fixes versuchen
2. **L2:** Incident-Playbook befolgen
3. **L3:** Development-Team kontaktieren

### Kontakte
- **Development:** dev-team@company.com
- **Security:** security@company.com  
- **Infrastructure:** ops@company.com

### Dokumentation
- **API-Docs:** http://127.0.0.1:8000/docs
- **GitHub:** https://github.com/company/codepipeline
- **Wiki:** https://wiki.company.com/codepipeline

---

*Dieses Runbook ermöglicht es dritten Personen, ohne weitere Einweisung den Happy-Path durchzuführen und Fails zielgerichtet zu beheben.*
