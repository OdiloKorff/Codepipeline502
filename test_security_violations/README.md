# Security Test Violations

Diese Dateien enthalten künstliche Security-Verstöße für Tests.
**WARNUNG**: Diese Dateien enthalten absichtlich unsichere Code-Patterns!

## Erstellte Verstöße:

- **sql_injection**: vulnerable_sql.py
- **hardcoded_secrets**: vulnerable_secrets.py
- **command_injection**: vulnerable_commands.py
- **weak_crypto**: vulnerable_crypto.py
- **path_traversal**: vulnerable_paths.py
- **insecure_deserialization**: vulnerable_deserialization.py

## Verwendung:

```bash
# Teste Security Scanner
python security_scanner.py --target test_security_violations --threshold medium --verbose

# Teste verschiedene Thresholds
python security_scanner.py --target test_security_violations --threshold high --output results.json
```

## Erwartete Ergebnisse:

- **SQL Injection**: Semgrep/Bandit sollten unsichere SQL-Queries finden
- **Hardcoded Secrets**: Secret Scanner sollte API Keys und Passwörter finden
- **Command Injection**: Bandit sollte os.system() und subprocess Probleme finden
- **Weak Crypto**: Bandit sollte MD5, DES und schwache Zufallsgeneratoren finden
- **Path Traversal**: Semgrep sollte unsichere Pfad-Operationen finden
- **Insecure Deserialization**: Bandit sollte pickle.loads Probleme finden

## Cleanup:

```bash
rm -rf test_security_violations
```
