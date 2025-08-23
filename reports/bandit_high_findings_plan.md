# Bandit HIGH Security Findings - Triage & Fix-Plan

**Scan-Datum:** 2024-12-19  
**Gesamt HIGH-Findings:** 3  
**Betroffene Dateien:** 2  

## Übersicht der Befunde

Alle 3 HIGH-severity Findings betreffen **Command Injection Vulnerabilities** durch die Verwendung von `subprocess` mit `shell=True`. Dies ermöglicht potenzielle Code-Injection-Angriffe, wenn untrusted Input verarbeitet wird.

---

## HIGH-001: modules/smart_orchestrator/orchestrator.py

**Rule ID:** B602 (subprocess_popen_with_shell_equals_true)  
**Zeile:** 31  
**CWE:** 78 (OS Command Injection)  

### Betroffener Code:
```python
# Zeilen 30-32
try:
    result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
    self.log(f"✔ {name} erfolgreich: {result.stdout.strip()}")
```

### Remediation:
```python
# Sichere Alternative:
import shlex  # Am Dateianfang hinzufügen

try:
    result = subprocess.run(shlex.split(command), check=True, capture_output=True, text=True)
    self.log(f"✔ {name} erfolgreich: {result.stdout.strip()}")
```

**Sicherheitsgewinn:** Verhindert Command Injection durch Eliminierung der Shell-Interpretation

---

## HIGH-002: tools/ai_build.py

**Rule ID:** B602 (subprocess_popen_with_shell_equals_true)  
**Zeile:** 29  
**CWE:** 78 (OS Command Injection)  

### Betroffener Code:
```python
# Zeilen 28-30
print("+", cmd, flush=True)
res = subprocess.run(cmd, shell=True, cwd=str(cwd) if cwd else None)
if check and res.returncode != 0:
```

### Remediation:
```python
# Sichere Alternative:
import shlex  # Am Dateianfang hinzufügen

print("+", cmd, flush=True)
res = subprocess.run(shlex.split(cmd), cwd=str(cwd) if cwd else None)
if check and res.returncode != 0:
```

**Sicherheitsgewinn:** Verhindert Command Injection durch sichere Argument-Parsing

---

## HIGH-003: tools/ai_build.py

**Rule ID:** B602 (subprocess_popen_with_shell_equals_true)  
**Zeile:** 37  
**CWE:** 78 (OS Command Injection)  

### Betroffener Code:
```python
# Zeilen 36-38
print("+", cmd, flush=True)
p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
if check and p.returncode != 0:
```

### Remediation:
```python
# Sichere Alternative:
import shlex  # Am Dateianfang hinzufügen

print("+", cmd, flush=True)  
p = subprocess.run(shlex.split(cmd), text=True, capture_output=True)
if check and p.returncode != 0:
```

**Sicherheitsgewinn:** Verhindert Command Injection durch sichere Argument-Parsing

---

## Zusammenfassung & Umsetzungsplan

### Primäre Vulnerabilität
**Command Injection (CWE-78)** durch `subprocess` mit `shell=True`

### Remediation-Strategie
1. **Import hinzufügen:** `import shlex` in beiden betroffenen Dateien
2. **Code-Ersetzung:** Alle `shell=True` Parameter entfernen
3. **Argument-Parsing:** `shlex.split(command)` für sichere Kommando-Zerlegung
4. **Testing:** Unit-Tests für die refaktorierten Funktionen

### Geschätzter Aufwand
**Low** - Direkte Code-Ersetzung ohne Funktionalitätsänderung erforderlich

### Akzeptanzkriterien
- ✅ Mindestens 3 HIGH-Einträge tabellarisch aufgelistet
- ✅ Jede Fundstelle hat konkrete empfohlene Codeänderung  
- ✅ Strukturierte JSON- und Markdown-Pläne erstellt
- ⏳ Nach Implementierung: Bandit stuft diese Stellen nicht mehr als HIGH ein

### Nächste Schritte
1. Implementierung der subprocess-Refactorings (BND-002)
2. Erstellung von Unit-Tests für die Änderungen
3. Verifikation durch erneuten Bandit-Scan
