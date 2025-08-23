# CodePipeline Development Guide

## Schnellstart

```bash
# 1. Projekt klonen und in Verzeichnis wechseln
cd Codepipeline502

# 2. Python-Umgebung aktivieren (falls vorhanden)
# source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows

# 3. Hauptpaket installieren (development mode)
pip install -e .

# 4. Entwicklungstools installieren (optional)
pip install -r requirements-dev.txt
```

## Lokaler CI-Test

```bash
# Vollständiger lokaler CI-Lauf
python scripts/local_ci_all_tests.py

# Einzelne Schritte testen
python -m pytest tests/test_basic.py tests/test_feature_spec.py
python -m codepipeline.cli feature --spec feature_spec.yaml --dry-run
```

## Entwicklungstools

### Core Tools (empfohlen)
- **pytest**: Test Runner - `pip install pytest pytest-cov`
- **ruff**: Python Linter - `pip install ruff`
- **mypy**: Type Checker - `pip install mypy`

### Security Tools (optional)
- **bandit**: Python Security Scanner - `pip install bandit`
- **semgrep**: Static Analysis - siehe [Installation](https://semgrep.dev/docs/getting-started/)
- **gitleaks**: Secret Scanner - siehe [Releases](https://github.com/gitleaks/gitleaks/releases)
- **pip-audit**: Dependency Scanner - `pip install pip-audit`

### Tool-Status im lokalen CI

| Tool | Status | Bedeutung |
|------|--------|-----------|
| `pass` | ✅ | Tool erfolgreich ausgeführt |
| `skip` | ⚠️ | Tool nicht installiert (zulässig) |
| `fail` | ❌ | Tool-Fehler (sollte behoben werden) |

**Wichtig**: Der lokale CI kann mit `overall: pass` abschließen, auch wenn einzelne Tools `skip` Status haben. Nur `fail` Status sollte vermieden werden.

## MVP-Konfiguration

Das System ist für MVP-Entwicklung optimiert:

- **Linting**: Fokus auf kritische Dateien (`codepipeline/api/**/*.py`)
- **Tests**: Nur stabile MVP-Tests (`test_basic.py`, `test_feature_spec.py`)
- **Coverage**: Minimum 10% (aktuell ~22%)
- **Security**: Baseline-Scans ohne strenge Enforcement

## Projektstruktur

```
Codepipeline502/
├── codepipeline/           # Hauptpaket
│   ├── api/               # API-Module
│   ├── cli.py             # CLI-Interface
│   └── feature_spec.py    # Feature-Spezifikation
├── qa/                    # Quality Assurance
│   └── scorecard.py       # QA-Scorecard
├── scripts/               # Utility-Skripte
│   ├── local_ci_all_tests.py
│   └── security_scan.py
├── tests/                 # Test-Suite
├── policies/              # QA-Policies
├── reports/               # CI-Reports
├── feature_spec.yaml      # Pilot-Spezifikation
├── requirements-dev.txt   # Development Dependencies
└── pyproject.toml         # Projekt-Konfiguration
```

## Troubleshooting

### Häufige Probleme

1. **`ModuleNotFoundError: No module named 'codepipeline'`**
   ```bash
   # PYTHONPATH setzen
   export PYTHONPATH=.        # Linux/Mac
   $env:PYTHONPATH="."        # Windows PowerShell
   ```

2. **Unicode-Fehler bei ruff**
   - Bereits in `local_ci_all_tests.py` behandelt
   - Verwendet `encoding='utf-8', errors='replace'`

3. **Test-Failures**
   - MVP-Tests sind auf Pydantic v2 angepasst
   - Bei Problemen: `python -m pytest tests/test_basic.py -v`

4. **CLI-Warnings**
   - RuntimeWarnings bei CLI-Ausführung sind normal
   - Beeinträchtigen nicht die Funktionalität

### Support

Bei Problemen:
1. Lokalen CI ausführen: `python scripts/local_ci_all_tests.py`
2. Reports prüfen: `reports/local_ci_summary.json`
3. Einzelne Tools testen: `ruff check .`, `pytest -v`

## Nächste Schritte

- [ ] Vollständige Pipeline-Implementierung
- [ ] Integration mit externen Services
- [ ] Erweiterte Security-Scans
- [ ] Performance-Optimierungen
