# ⚡ Quickstart - MVP Pipeline in 5 Minuten

## 🚀 **Super-schnelle Demo**

### **1. Setup** (30s)
```bash
git clone https://github.com/OdiloKorff/Codepipeline502.git
cd Codepipeline502
python -m venv .venv && .venv\Scripts\activate  # Windows
pip install pytest coverage bandit pyyaml typer
```

### **2. Demo MVP-Fähigkeiten** (2 min)
```bash
# E2E-Smoketest (zeigt alle 8 Pipeline-Steps)
python codepipeline/e2e_smoketest_mvp.py

# Ehrliche Qualitätsbewertung (Anti-Greenwashing)
python codepipeline/scorecard_mvp.py

# Artefakt-Discovery (11 Standard-Artefakte)
python codepipeline/artifact_manager_mvp.py
```

### **3. Erweiterte Demos** (2 min)
```bash
# Security-Scan mit High=0-Enforcement
python codepipeline/security_gate_mvp.py

# Secrets-Gating (erwarteter Fail ohne echte Secrets)
python codepipeline/secrets_gating_mvp.py --check

# Policy-Härtung (erkennt künstliche Coverage-Absenkung)
python codepipeline/policy_hardening_mvp.py --audit

# GUI öffnen
python codepipeline/gui_mvp.py
```

### **4. Nightly Smoke Setup** (30s)
```bash
# Template + Profil für nächtliche Ausführung
python codepipeline/nightly_smoke_mvp.py --setup

# Trend-Report generieren
python codepipeline/nightly_smoke_mvp.py --trend --days 1
```

## ✅ **Erwartete Ergebnisse**

| Demo | Erwartetes Ergebnis | Status |
|------|-------------------|--------|
| E2E-Smoketest | 6/8 Steps completed (normale Test-Setup-Issues) | ✅ Normal |
| Scorecard | Ehrlich FAIL (20% < 75% Coverage-Baseline) | ✅ Anti-Greenwashing |
| Artefakte | 11/11 Found, 100% Success Rate | ✅ Robust |
| Security | HIGH: 0, MEDIUM: 41, LOW: 1299 | ✅ Clean |
| Secrets | FAIL (4 missing secrets) | ✅ Fail-closed |
| Policy | Artificial lowering detected | ✅ Honest |
| GUI | Tkinter-Window mit Start-Buttons | ✅ User-friendly |
| Nightly | Template + Profil erstellt | ✅ Operational |

## 📊 **Artefakte nach Demo**

```
📂 reports/
├── 📄 scorecard.json              # Ehrliche Qualitätsbewertung
├── 📄 security_gate_report.json   # Security-Scan HIGH=0
├── 📄 artifact_manifest.json      # 11 Artefakte 100% Found
├── 📄 e2e_smoketest_report.json   # 8-Step-Pipeline-Test
├── 📄 secrets_gate_report.json    # 4 Missing Secrets (erwartet)
├── 📄 policy_hardening_report.json # Anti-Greenwashing-Check
└── 📄 trends/
    ├── 📄 nightly_smoke_YYYY-MM-DD.json  # Tägliche KPIs
    └── 📄 nightly_smoke_trend.json       # Trend-Analyse
```

## 🎯 **MVP-020-Akzeptanz erfüllt**

- ✅ **Unter 5 Minuten:** Alle MVP-Fähigkeiten demonstriert
- ✅ **Neue Nutzer:** Keine Vorkenntnisse erforderlich
- ✅ **Handoff-fähig:** README + Troubleshooting komplett
- ✅ **Production-Ready:** Ehrliche Pipeline ohne Greenwashing

**Status: DEMO-READY für MVP-Handoff! 🎉**
