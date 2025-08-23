# 🎓 CodePipeline Production Onboarding

## 🎯 Willkommen

Dieses Dokument führt neue Team-Mitglieder durch die Einrichtung und den Betrieb des CodePipeline Production Systems. Nach diesem Onboarding können Sie selbstständig Features entwickeln, Quality Gates konfigurieren und Incidents beheben.

**Zielgruppe:** Neue Entwickler, Ops-Engineers, QA-Engineers  
**Geschätzte Dauer:** 2-3 Stunden  
**Voraussetzungen:** Python-Grundkenntnisse, Git-Erfahrung

---

## ✅ Pre-Flight-Checklist

Bevor Sie starten, stellen Sie sicher, dass Sie haben:

- [ ] **Laptop/Workstation** mit Admin-Rechten
- [ ] **Python 3.10+** installiert (`python --version`)
- [ ] **Git** installiert und konfiguriert
- [ ] **Code-Editor** (VS Code, PyCharm, etc.)
- [ ] **Zugang zu Unternehmens-Systemen** (VPN, Slack, Email)
- [ ] **Mentor/Buddy** für Fragen identifiziert

---

## 🚀 Schritt 1: System-Setup (30 min)

### 1.1 Repository-Clone
```bash
# Clone Repository
git clone https://github.com/company/codepipeline.git
cd codepipeline

# Überprüfe Branch
git branch -a
git checkout main
```

### 1.2 Python-Environment
```bash
# Virtual Environment erstellen (empfohlen)
python -m venv venv

# Aktivieren
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt

# Zusätzliche GUI-Dependencies
pip install fastapi uvicorn websockets
```

### 1.3 Grundlegende Verifikation
```bash
# CLI-Test
python -m codepipeline.cli --help

# Import-Test
python -c "import codepipeline; print('✅ Import OK')"

# Health-Check
python -c "
import sys
print(f'Python: {sys.version}')
print('✅ Environment ready')
"
```

---

## 🔐 Schritt 2: Secrets-Setup (20 min)

### 2.1 OpenAI-API-Key

#### Option A: Unternehmens-Key (Empfohlen)
```bash
# Kontaktiere IT/Security für Enterprise-Key
# Key wird über Vault/OIDC bereitgestellt

# Vault-Setup (Enterprise)
export VAULT_ADDR="https://vault.company.com"
vault auth -method=oidc
vault kv get secret/codepipeline/openai
```

#### Option B: Development-Key (Fallback)
```bash
# Persönlichen OpenAI-Account erstellen: https://platform.openai.com
# API-Key generieren (sk-...)

# Environment-Variable setzen
export OPENAI_API_KEY="sk-your-key-here"

# Oder .env-Datei erstellen (nur Development!)
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

### 2.2 GitHub-Token (Optional)
```bash
# GitHub Personal Access Token erstellen
# Settings > Developer settings > Personal access tokens

export GITHUB_TOKEN="ghp_your-token-here"
# Oder in .env-Datei
echo "GITHUB_TOKEN=ghp_your-token-here" >> .env
```

### 2.3 Secret-Validierung
```bash
# Test OpenAI-Connection
python -c "
import os
from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
models = client.models.list()
print(f'✅ OpenAI connected: {len(models.data)} models available')
"

# Test Secret-Manager
python -c "
from app_secrets import ensure_env
try:
    key = ensure_env('OPENAI_API_KEY')
    print('✅ Secret-Manager OK')
except Exception as e:
    print(f'❌ Secret-Manager Error: {e}')
"
```

---

## 📋 Schritt 3: Policies-Konfiguration (15 min)

### 3.1 Quality-Policies verstehen
```bash
# Default-Policies anzeigen
cat policies/QUALITY.yml

# Oder in Python
python -c "
import yaml
with open('policies/QUALITY.yml') as f:
    policies = yaml.safe_load(f)
print('Quality Policies:')
for key, value in policies.items():
    print(f'  {key}: {value}')
"
```

### 3.2 Team-spezifische Anpassungen
```bash
# Backup erstellen
cp policies/QUALITY.yml policies/QUALITY.yml.backup

# Editor öffnen
code policies/QUALITY.yml
# Oder: vim policies/QUALITY.yml
```

**Typische Anpassungen für neue Teams:**
```yaml
# Weniger strenge Anfangswerte
qa_scorecard:
  coverage_min: 70.0        # Start niedriger
  linting_max_violations: 5 # Toleriere einige Violations

security:
  max_high: 2              # Weniger streng am Anfang
  max_medium: 10
```

### 3.3 Policy-Validierung
```bash
# Policy-Syntax prüfen
python -c "
import yaml
try:
    with open('policies/QUALITY.yml') as f:
        policies = yaml.safe_load(f)
    print('✅ Policies valid')
except Exception as e:
    print(f'❌ Policy error: {e}')
"
```

---

## 🧪 Schritt 4: Happy-Path-Test (20 min)

### 4.1 Erste Feature-Spec erstellen
```bash
# Beispiel-Spec erstellen
cat > onboarding-spec.json << 'EOF'
{
  "id": "ONBOARDING-001",
  "title": "Mein erstes CodePipeline Feature",
  "version": 1,
  "goal": "Implementiere eine einfache Hallo-Welt-Funktion",
  "description": "Dies ist mein erstes Feature zum Lernen",
  "target_paths": ["src/onboarding/"],
  "constraints": ["Nur sichere Operationen", "Keine externen Dependencies"],
  "risk_level": "low",
  "reviewers": [],
  "model": "gpt-4o-mini",
  "token_budget": 1000,
  "tests": {
    "coverage_min": 75.0,
    "pytest_args": ["-v"]
  },
  "quality": {
    "linting_enabled": true,
    "type_checking_enabled": false
  },
  "hard_musts": ["test_coverage"]
}
EOF
```

### 4.2 Spec-Validierung
```bash
# Spec validieren
python -m codepipeline.cli spec validate onboarding-spec.json

# Erwartete Ausgabe:
# ✅ Spec validation successful
# ID: ONBOARDING-001
# Risk Level: low
# Target Paths: ['src/onboarding/']
```

### 4.3 Dry-Run-Test
```bash
# Erstelle Zielverzeichnis
mkdir -p src/onboarding

# Dry-Run (keine echten Änderungen)
python -m codepipeline.cli feature \
  --spec onboarding-spec.json \
  --branch feature/onboarding-test \
  --dry-run

# Erwartete Ausgabe:
# 🔍 Dry-Run-Modus aktiviert
# ✅ Spec-Validierung erfolgreich
# ✅ Prompt-Guard bestanden
# ✅ LLM-Diff generiert
# ✅ Sandbox-Validierung erfolgreich
# 🏁 Dry-Run abgeschlossen
```

---

## 🖥️ Schritt 5: GUI-Setup (15 min)

### 5.1 Backend starten
```bash
# Terminal 1: Backend starten
python production_gui_backend.py --start-server

# Erwartete Ausgabe:
# 🖥️ Production GUI-Backend initialisiert
# 🚀 Starting GUI-Backend-Server...
# 🌐 URL: http://127.0.0.1:8000
# 📡 API Docs: http://127.0.0.1:8000/docs
```

### 5.2 GUI-Test
```bash
# Browser öffnen
# Windows:
start http://127.0.0.1:8000
# Mac:
open http://127.0.0.1:8000
# Linux:
xdg-open http://127.0.0.1:8000

# Oder manuell: http://127.0.0.1:8000
```

### 5.3 GUI-Funktionen testen
1. **Dashboard:** Sollte leer sein (keine Runs)
2. **Neuer Run:** 
   - Spec aus `onboarding-spec.json` kopieren
   - "Spec validieren" klicken → ✅ Grün
   - "Run starten" klicken
3. **Run-Detail:** 
   - Run in Tabelle anklicken
   - Gates sollten nacheinander durchlaufen
   - Artifacts sollten erscheinen

---

## 🔍 Schritt 6: Monitoring & Debugging (20 min)

### 6.1 Log-Locations kennenlernen
```bash
# Log-Verzeichnis
ls -la logs/

# Haupt-Log (falls vorhanden)
tail -f logs/codepipeline.log

# Oder Console-Output vom Backend beobachten
# (Terminal wo Backend läuft)
```

### 6.2 Health-Checks
```bash
# API-Health
curl http://127.0.0.1:8000/api/health

# System-Health
python -c "
import psutil
print(f'CPU: {psutil.cpu_percent()}%')
print(f'Memory: {psutil.virtual_memory().percent}%')
print(f'Disk: {psutil.disk_usage(\".\").percent}%')
"
```

### 6.3 Debugging-Tools
```bash
# Audit-Trail (falls SQLite-DB existiert)
ls -la audit_trail.db
sqlite3 audit_trail.db "SELECT * FROM runs LIMIT 5;"

# Artifacts
ls -la artifacts/

# Process-Monitoring
ps aux | grep python | grep codepipeline
```

---

## 📚 Schritt 7: Dokumentation & Ressourcen (10 min)

### 7.1 Wichtige Dokumentation
- **Production Runbook:** `docs/PRODUCTION_RUNBOOK.md`
- **Incident Playbook:** `docs/INCIDENT_PLAYBOOK_PRODUCTION.md`
- **API-Dokumentation:** http://127.0.0.1:8000/docs
- **Code-Dokumentation:** Inline-Comments in `.py`-Dateien

### 7.2 Nützliche Commands
```bash
# Alle verfügbaren CLI-Commands
python -m codepipeline.cli --help

# Modul-Struktur verstehen
find codepipeline/ -name "*.py" | head -10

# Tests ausführen (falls vorhanden)
python -m pytest tests/ -v

# Linting
python -m ruff check .

# Type-Checking
python -m mypy . --ignore-missing-imports
```

### 7.3 Team-Ressourcen
- **Slack:** #codepipeline-support, #codepipeline-dev
- **Wiki:** https://wiki.company.com/codepipeline
- **GitHub Issues:** https://github.com/company/codepipeline/issues
- **Team-Meetings:** Jeden Montag 10:00, Raum 42

---

## ✅ Onboarding-Verifikation

Nach Abschluss sollten Sie können:

### Grundlegende Funktionen
- [ ] **CLI:** Feature-Spec validieren und Dry-Run ausführen
- [ ] **GUI:** Backend starten und Runs über GUI starten
- [ ] **Secrets:** OpenAI-API-Key konfiguriert und getestet
- [ ] **Policies:** Quality-Policies verstehen und anpassen

### Operationelle Fähigkeiten
- [ ] **Logs:** Logs finden und interpretieren
- [ ] **Health-Checks:** System-Status prüfen
- [ ] **Debugging:** Grundlegende Debugging-Schritte
- [ ] **Incidents:** Runbook und Playbook-Location kennen

### Team-Integration
- [ ] **Mentor:** Ersten erfolgreichen Run mit Mentor durchgeführt
- [ ] **Code-Review:** Ersten Policy-Change reviewed
- [ ] **Kommunikation:** Slack-Channels und Team-Kontakte bekannt
- [ ] **Dokumentation:** Wissen wo Hilfe zu finden ist

---

## 🆘 Häufige Onboarding-Probleme

### Problem: "ModuleNotFoundError"
```bash
# Lösung: Virtual Environment aktivieren
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Dependencies neu installieren
pip install -r requirements.txt
```

### Problem: "SecretNotAvailableError"
```bash
# Lösung: API-Key setzen
export OPENAI_API_KEY="sk-your-key-here"

# Test
python -c "import os; print('Key:', os.getenv('OPENAI_API_KEY', 'NOT SET')[:10] + '...')"
```

### Problem: "Port already in use"
```bash
# Lösung: Anderen Port verwenden
python production_gui_backend.py --start-server --port 8001

# Oder laufenden Prozess beenden
pkill -f production_gui_backend
```

### Problem: GUI zeigt "API nicht verfügbar"
```bash
# Lösung: Backend-Status prüfen
curl http://127.0.0.1:8000/api/health

# Backend neu starten
pkill -f production_gui_backend
python production_gui_backend.py --start-server
```

---

## 🎯 Nächste Schritte

Nach erfolgreichem Onboarding:

### Woche 1
- [ ] **Erstes echtes Feature** entwickeln (mit Mentor)
- [ ] **Code-Review** für Policy-Änderung einreichen  
- [ ] **Team-Meeting** teilnehmen
- [ ] **Dokumentation** einen Verbesserungsvorschlag machen

### Woche 2-4
- [ ] **Incident-Response** (Simulation) durchführen
- [ ] **Monitoring-Dashboard** einrichten (falls vorhanden)
- [ ] **Advanced-Features** erkunden (Reproducibility, Audit-Trail)
- [ ] **Team-Knowledge-Sharing** Session halten

### Langfristig
- [ ] **Mentor** für neue Team-Mitglieder werden
- [ ] **System-Improvements** vorschlagen und implementieren
- [ ] **Best-Practices** dokumentieren und teilen

---

## 📞 Support & Kontakte

### Bei Problemen während Onboarding
1. **Mentor/Buddy:** [Name] - [email] - [Slack]
2. **Team-Lead:** [Name] - [email] - [Slack]  
3. **IT-Support:** it-support@company.com
4. **Slack:** #codepipeline-onboarding

### Feedback zum Onboarding-Prozess
- **Onboarding-Survey:** https://forms.company.com/onboarding-codepipeline
- **Verbesserungsvorschläge:** onboarding@company.com
- **Dokumentation-Updates:** PR gegen `docs/ONBOARDING_PRODUCTION.md`

---

**🎉 Herzlichen Glückwunsch! Sie sind jetzt bereit, mit CodePipeline Production zu arbeiten!**

*Dieses Onboarding ermöglicht es dritten Personen, ohne weitere Einweisung Secrets und Policies einzurichten und das System produktiv zu nutzen.*
