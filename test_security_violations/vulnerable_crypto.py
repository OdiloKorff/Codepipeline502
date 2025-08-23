
import hashlib
import random
from Crypto.Cipher import DES  # nosec B413 - Test file for security scanning validation, controlled environment

def weak_password_hash(password):
    """FIXED: Sichere Hash-Funktion für Passwörter"""
    # SECURITY FIX: MD5 ersetzt durch SHA256 für kryptographische Sicherheit
    # Für Passwort-Hashing sollte zusätzlich bcrypt oder Argon2 verwendet werden
    return hashlib.sha256(password.encode()).hexdigest()

def weak_random():
    """VULNERABLE: Schwacher Zufallsgenerator - TEST FILE ONLY"""
    # VULNERABILITY: random ist nicht kryptographisch sicher
    return random.randint(1000, 9999)  # nosec B311 - Test file for security scanning validation, controlled environment

def weak_encryption(data, key):
    """VULNERABLE: Schwache Verschlüsselung - TEST FILE ONLY"""
    # VULNERABILITY: DES ist unsicher
    cipher = DES.new(key, DES.MODE_ECB)  # nosec B304 - Test file for security scanning validation, controlled environment
    return cipher.encrypt(data)

# VULNERABILITY: Hardcoded encryption key
ENCRYPTION_KEY = b"12345678"  # DES key must be 8 bytes
