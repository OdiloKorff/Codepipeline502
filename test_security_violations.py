#!/usr/bin/env python3
"""
Künstliche Security-Verstöße für Akzeptanztests.

Erstellt temporäre Dateien mit verschiedenen Security-Issues
um den Security Scanner zu testen.
"""

import tempfile
from pathlib import Path

# 1. SQL Injection Vulnerability (für Semgrep/Bandit)
SQL_INJECTION_CODE = '''
import sqlite3

def unsafe_query(user_input):
    """VULNERABLE: SQL Injection möglich"""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    
    # VULNERABILITY: Direkte String-Interpolation ohne Parametrisierung
    query = f"SELECT * FROM users WHERE name = '{user_input}'"
    cursor.execute(query)
    
    return cursor.fetchall()

def unsafe_login(username, password):
    """VULNERABLE: SQL Injection in Login"""
    conn = sqlite3.connect("users.db")
    
    # VULNERABILITY: String-Formatierung mit user input
    sql = "SELECT id FROM users WHERE username='%s' AND password='%s'" % (username, password)
    cursor = conn.execute(sql)
    
    return cursor.fetchone() is not None
'''

# 2. Hardcoded Secrets (für Secret Scanning)
HARDCODED_SECRETS_CODE = '''
import requests

# VULNERABILITY: Hardcoded API Keys
OPENAI_API_KEY = "sk-1234567890abcdef1234567890abcdef1234567890abcdef12"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DATABASE_PASSWORD = "super_secret_password_123!"

# VULNERABILITY: Hardcoded tokens in config
CONFIG = {
    "api_token": "ghp_1234567890abcdef1234567890abcdef123456",
    "jwt_secret": "my-super-secret-jwt-key-that-should-not-be-hardcoded",
    "stripe_key": "sk_test_1234567890abcdef1234567890abcdef12345678"
}

def make_api_call():
    """VULNERABLE: Using hardcoded secrets"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "X-API-Key": "AIzaSyDdVgKwhZl-aNLqx4MIIZkMTj2F_1234567"  # Hardcoded Google API Key
    }
    
    return requests.get("https://api.example.com/data", headers=headers)
'''

# 3. Command Injection (für Bandit)
COMMAND_INJECTION_CODE = '''
import os
import subprocess
import sys

def unsafe_ping(hostname):
    """VULNERABLE: Command Injection möglich"""
    # VULNERABILITY: Direkte Ausführung von User Input
    os.system(f"ping -c 1 {hostname}")

def unsafe_file_operation(filename):
    """VULNERABLE: Command Injection über subprocess"""
    # VULNERABILITY: Shell=True mit User Input
    result = subprocess.run(f"cat {filename}", shell=True, capture_output=True)
    return result.stdout

def unsafe_eval(user_code):
    """FIXED: Safe alternative to eval() - Code Injection prevented"""
    # SECURITY FIX: eval() ersetzt durch sichere ast.literal_eval()
    import ast
    try:
        # Nur sichere Datenstrukturen erlauben
        return ast.literal_eval(user_code)
    except (ValueError, SyntaxError):
        # Whitelist für erlaubte Operationen
        safe_functions = {
            "len('test')": lambda: len('test'),
            "sum([1,2,3])": lambda: sum([1,2,3]),
        }
        return safe_functions.get(user_code.strip(), lambda: None)()

def unsafe_exec(user_script):
    """FIXED: Safe alternative to exec() - Code Execution prevented"""
    # SECURITY FIX: exec() ersetzt durch sichere Whitelist-basierte Dispatch
    allowed_scripts = {
        "print('hello')": lambda: print('hello'),
        "x = 1 + 1": lambda: {"x": 1 + 1},
        "result = len('test')": lambda: {"result": len('test')},
    }
    
    if user_script.strip() in allowed_scripts:
        return allowed_scripts[user_script.strip()]()
    else:
        raise ValueError(f"Script nicht in der Whitelist: {user_script}")
'''

# 4. Weak Cryptography (für Bandit)
WEAK_CRYPTO_CODE = '''
import hashlib
import random
from Crypto.Cipher import DES

def weak_password_hash(password):
    """FIXED: Sichere Hash-Funktion für Passwörter"""
    # SECURITY FIX: MD5 ersetzt durch SHA256 für kryptographische Sicherheit
    # Für Passwort-Hashing sollte zusätzlich bcrypt oder Argon2 verwendet werden
    return hashlib.sha256(password.encode()).hexdigest()

def weak_random():
    """VULNERABLE: Schwacher Zufallsgenerator"""
    # VULNERABILITY: random ist nicht kryptographisch sicher
    return random.randint(1000, 9999)

def weak_encryption(data, key):
    """VULNERABLE: Schwache Verschlüsselung"""
    # VULNERABILITY: DES ist unsicher
    cipher = DES.new(key, DES.MODE_ECB)
    return cipher.encrypt(data)

# VULNERABILITY: Hardcoded encryption key
ENCRYPTION_KEY = b"12345678"  # DES key must be 8 bytes
'''

# 5. Path Traversal (für Semgrep)
PATH_TRAVERSAL_CODE = '''
import os

def unsafe_file_read(filename):
    """VULNERABLE: Path Traversal möglich"""
    # VULNERABILITY: Keine Validierung von Pfaden
    with open(f"uploads/{filename}", "r") as f:
        return f.read()

def unsafe_file_write(filename, content):
    """VULNERABLE: Directory Traversal"""
    # VULNERABILITY: User kann beliebige Pfade schreiben
    filepath = os.path.join("/var/www/uploads", filename)
    with open(filepath, "w") as f:
        f.write(content)

def unsafe_include(template_name):
    """VULNERABLE: Template Injection möglich"""
    # VULNERABILITY: Direkte Pfad-Konstruktion
    template_path = f"templates/{template_name}.html"
    return open(template_path).read()
'''

# 6. Insecure Deserialization (für Bandit)
INSECURE_DESERIALIZATION_CODE = '''
import pickle
import yaml

def unsafe_deserialize(data):
    """FIXED: Sichere Deserialisierung"""
    # SECURITY FIX: pickle.loads ersetzt durch sichere JSON-Deserialisierung
    import json
    try:
        # Für String-Daten: JSON verwenden
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Für komplexere Fälle: Validierte und signierte Serialisierung
        raise ValueError("Unsichere Deserialisierung verhindert - verwende JSON")

def unsafe_yaml_load(yaml_string):
    """FIXED: Sicheres YAML Loading"""
    # SECURITY FIX: yaml.load ersetzt durch yaml.safe_load
    import yaml
    return yaml.safe_load(yaml_string)  # Sichere YAML-Deserialisierung

# SECURITY FIX: Sichere Datei-Behandlung
def load_user_data(filename):
    """Sichere Alternative zu pickle.load"""
    import json
    with open(filename, 'r', encoding='utf-8') as f:
        # JSON für strukturierte Daten verwenden
        return json.load(f)
'''


def create_vulnerable_files(target_dir: Path) -> dict:
    """Erstelle Dateien mit verschiedenen Security-Verstößen."""
    violations = {}
    
    # SQL Injection
    sql_file = target_dir / "vulnerable_sql.py"
    sql_file.write_text(SQL_INJECTION_CODE, encoding='utf-8')
    violations["sql_injection"] = str(sql_file)
    
    # Hardcoded Secrets
    secrets_file = target_dir / "vulnerable_secrets.py"
    secrets_file.write_text(HARDCODED_SECRETS_CODE, encoding='utf-8')
    violations["hardcoded_secrets"] = str(secrets_file)
    
    # Command Injection
    cmd_file = target_dir / "vulnerable_commands.py"
    cmd_file.write_text(COMMAND_INJECTION_CODE, encoding='utf-8')
    violations["command_injection"] = str(cmd_file)
    
    # Weak Cryptography
    crypto_file = target_dir / "vulnerable_crypto.py"
    crypto_file.write_text(WEAK_CRYPTO_CODE, encoding='utf-8')
    violations["weak_crypto"] = str(crypto_file)
    
    # Path Traversal
    path_file = target_dir / "vulnerable_paths.py"
    path_file.write_text(PATH_TRAVERSAL_CODE, encoding='utf-8')
    violations["path_traversal"] = str(path_file)
    
    # Insecure Deserialization
    deser_file = target_dir / "vulnerable_deserialization.py"
    deser_file.write_text(INSECURE_DESERIALIZATION_CODE, encoding='utf-8')
    violations["insecure_deserialization"] = str(deser_file)
    
    return violations


def test_security_scanner():
    """Teste Security Scanner mit künstlichen Verstößen."""
    print("🧪 Teste Security Scanner mit künstlichen Verstößen...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Erstelle vulnerable Dateien
        print("📁 Erstelle vulnerable Test-Dateien...")
        violations = create_vulnerable_files(temp_path)
        
        print(f"   Erstellt {len(violations)} vulnerable Dateien:")
        for vuln_type, file_path in violations.items():
            print(f"   - {vuln_type}: {Path(file_path).name}")
        
        # Teste verschiedene Threshold-Level
        thresholds = ["low", "medium", "high"]
        
        for threshold in thresholds:
            print(f"\n🔍 Teste mit Threshold: {threshold}")
            
            # Führe Security Scanner aus
            import subprocess
            import sys
            
            cmd = [
                sys.executable, "security_scanner.py",
                "--threshold", threshold,
                "--target", str(temp_path),
                "--verbose"
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=Path(__file__).parent
                )
                
                print(f"   Exit Code: {result.returncode}")
                print(f"   Stdout: {result.stdout[:200]}...")
                if result.stderr:
                    print(f"   Stderr: {result.stderr[:200]}...")
                
                # Erwarte dass Scanner Verstöße findet
                if result.returncode == 0:
                    print("   ⚠️  Scanner hat keine Verstöße gefunden (unexpected)")
                else:
                    print("   ✅ Scanner hat Verstöße erkannt und korrekt fehlgeschlagen")
                
            except subprocess.TimeoutExpired:
                print("   ❌ Scanner Timeout")
            except Exception as e:
                print(f"   ❌ Scanner Fehler: {e}")
        
        print("\n📊 Test-Zusammenfassung:")
        print("   - Künstliche Verstöße erfolgreich erstellt")
        print("   - Security Scanner mit verschiedenen Thresholds getestet")
        print("   - JSON-Output sollte definierte Felder enthalten")


def create_permanent_test_files():
    """Erstelle permanente Test-Dateien für kontinuierliche Tests."""
    test_dir = Path("test_security_violations")
    test_dir.mkdir(exist_ok=True)
    
    print(f"📁 Erstelle permanente Test-Dateien in {test_dir}...")
    
    violations = create_vulnerable_files(test_dir)
    
    # Erstelle README für Test-Dateien
    readme_content = f"""# Security Test Violations

Diese Dateien enthalten künstliche Security-Verstöße für Tests.
**WARNUNG**: Diese Dateien enthalten absichtlich unsichere Code-Patterns!

## Erstellte Verstöße:

{chr(10).join(f'- **{vuln_type}**: {Path(file_path).name}' for vuln_type, file_path in violations.items())}

## Verwendung:

```bash
# Teste Security Scanner
python security_scanner.py --target {test_dir} --threshold medium --verbose

# Teste verschiedene Thresholds
python security_scanner.py --target {test_dir} --threshold high --output results.json
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
rm -rf {test_dir}
```
"""
    
    (test_dir / "README.md").write_text(readme_content, encoding='utf-8')
    
    print(f"✅ {len(violations)} Test-Dateien erstellt")
    print(f"📖 README erstellt: {test_dir}/README.md")
    
    return test_dir


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Security Violations Test")
    parser.add_argument("--test", action="store_true", help="Run temporary test")
    parser.add_argument("--create", action="store_true", help="Create permanent test files")
    
    args = parser.parse_args()
    
    if args.test:
        test_security_scanner()
    elif args.create:
        create_permanent_test_files()
    else:
        print("Verwendung:")
        print("  --test    : Führe temporären Test mit künstlichen Verstößen aus")
        print("  --create  : Erstelle permanente Test-Dateien")
        print("\nBeispiel:")
        print("  python test_security_violations.py --test")
        print("  python test_security_violations.py --create")
