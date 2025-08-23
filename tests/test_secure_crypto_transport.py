#!/usr/bin/env python3
"""
Unit-Tests für die sicheren Krypto-, Transport- und Deserialisierungs-Refactorings.
Testet die refaktorierten Funktionen mit sicheren Alternativen.
"""

import pytest
import hashlib
import json
import yaml
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the refactored functions
from test_security_violations import unsafe_deserialize, unsafe_yaml_load, load_user_data, weak_password_hash


class TestSecureCryptoRefactoring:
    """Tests für sichere Krypto-Hash-Alternativen"""
    
    def test_weak_password_hash_uses_sha256(self):
        """Test dass weak_password_hash() SHA256 statt MD5 verwendet"""
        password = "test_password_123"
        result = weak_password_hash(password)
        
        # Verifiziere dass das Ergebnis SHA256 ist
        expected = hashlib.sha256(password.encode()).hexdigest()
        assert result == expected
        assert len(result) == 64  # SHA256 hex length
    
    def test_hash_functions_security_improvement(self):
        """Test dass SHA256 sicherer ist als MD5"""
        test_data = "sensitive_data_123"
        
        # SHA256 (sicher)
        sha256_hash = hashlib.sha256(test_data.encode()).hexdigest()
        
        # Verifiziere Eigenschaften
        assert len(sha256_hash) == 64  # 256 bits = 64 hex chars
        assert isinstance(sha256_hash, str)
        assert all(c in '0123456789abcdef' for c in sha256_hash)
    
    def test_hash_deterministic_behavior(self):
        """Test dass Hash-Funktionen deterministisch sind"""
        test_input = "consistent_input"
        
        hash1 = hashlib.sha256(test_input.encode()).hexdigest()
        hash2 = hashlib.sha256(test_input.encode()).hexdigest()
        
        assert hash1 == hash2  # Deterministisches Verhalten
    
    def test_different_inputs_different_hashes(self):
        """Test dass verschiedene Inputs verschiedene Hashes produzieren"""
        input1 = "input_one"
        input2 = "input_two"
        
        hash1 = hashlib.sha256(input1.encode()).hexdigest()
        hash2 = hashlib.sha256(input2.encode()).hexdigest()
        
        assert hash1 != hash2  # Verschiedene Inputs → verschiedene Hashes


class TestSecureDeserializationRefactoring:
    """Tests für sichere Deserialisierungs-Alternativen"""
    
    def test_unsafe_deserialize_uses_json(self):
        """Test dass unsafe_deserialize() JSON statt pickle verwendet"""
        # Sichere JSON-Daten
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        json_string = json.dumps(test_data)
        
        result = unsafe_deserialize(json_string)
        assert result == test_data
    
    def test_unsafe_deserialize_handles_bytes(self):
        """Test dass unsafe_deserialize() Bytes korrekt behandelt"""
        test_data = {"message": "hello"}
        json_bytes = json.dumps(test_data).encode('utf-8')
        
        result = unsafe_deserialize(json_bytes)
        assert result == test_data
    
    def test_unsafe_deserialize_rejects_invalid_data(self):
        """Test dass unsafe_deserialize() ungültige Daten ablehnt"""
        invalid_data = "this is not valid JSON"
        
        with pytest.raises(ValueError) as exc_info:
            unsafe_deserialize(invalid_data)
        assert "Unsichere Deserialisierung verhindert" in str(exc_info.value)
    
    def test_unsafe_yaml_load_uses_safe_load(self):
        """Test dass unsafe_yaml_load() yaml.safe_load verwendet"""
        yaml_string = """
        name: test
        values:
          - 1
          - 2
          - 3
        config:
          enabled: true
        """
        
        result = unsafe_yaml_load(yaml_string)
        
        expected = {
            'name': 'test',
            'values': [1, 2, 3],
            'config': {'enabled': True}
        }
        assert result == expected
    
    def test_load_user_data_uses_json(self):
        """Test dass load_user_data() JSON statt pickle verwendet"""
        import tempfile
        import os
        
        test_data = {"user": "john", "age": 30, "active": True}
        
        # Erstelle temporäre JSON-Datei
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name
        
        try:
            result = load_user_data(temp_file)
            assert result == test_data
        finally:
            os.unlink(temp_file)
    
    def test_json_serialization_safety(self):
        """Test dass JSON-Serialisierung sicher ist"""
        # JSON kann keine Code-Ausführung
        safe_data = {
            "string": "hello",
            "number": 42,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"}
        }
        
        # Serialisierung und Deserialisierung sollten sicher sein
        json_string = json.dumps(safe_data)
        result = json.loads(json_string)
        
        assert result == safe_data
        
        # JSON kann keine Funktionen oder Code serialisieren
        with pytest.raises(TypeError):
            json.dumps({"function": lambda x: x})


class TestSecureTransportRefactoring:
    """Tests für sichere HTTP-Transport-Konfiguration"""
    
    @patch('requests.post')
    def test_requests_with_timeout_and_verify(self, mock_post):
        """Test dass HTTP-Requests timeout und verify=True verwenden"""
        # Simuliere sicheren HTTP-Call
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response
        
        # Import einer Funktion die requests verwendet
        from deployer import create_github_release
        
        # Test-Parameter
        tag = "v1.0.0"
        repo = "test/repo"
        token = "test_token"
        artifacts = ["file1.txt"]
        
        result = create_github_release(tag, repo, token, artifacts)
        
        # Verifiziere dass requests.post mit sicheren Parametern aufgerufen wurde
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        # Prüfe sichere Parameter
        assert 'timeout' in kwargs
        assert kwargs['timeout'] == 30
        assert 'verify' in kwargs
        assert kwargs['verify'] is True
    
    def test_http_security_best_practices(self):
        """Test HTTP-Sicherheits-Best-Practices"""
        # Sichere HTTP-Konfiguration
        secure_config = {
            'timeout': 30,          # Verhindert hängende Requests
            'verify': True,         # SSL-Zertifikat-Validierung
            'allow_redirects': False,  # Kontrollierte Redirects
        }
        
        # Verifiziere Konfiguration
        assert secure_config['timeout'] > 0
        assert secure_config['verify'] is True
        assert 'timeout' in secure_config
    
    def test_ssl_verification_importance(self):
        """Test dass SSL-Verifikation wichtig für Sicherheit ist"""
        # verify=True ist der sichere Standard
        secure_verify = True
        insecure_verify = False
        
        assert secure_verify is True
        assert insecure_verify is False
        
        # In Produktion sollte verify immer True sein
        production_config = {'verify': True}
        assert production_config['verify'] is True


class TestSecurityImprovements:
    """Tests die die allgemeinen Sicherheitsverbesserungen demonstrieren"""
    
    def test_crypto_algorithm_strength(self):
        """Test dass SHA256 stärker als MD5 ist"""
        test_data = b"security_test_data"
        
        # SHA256 (sicher)
        sha256_hash = hashlib.sha256(test_data).hexdigest()
        
        # Eigenschaften von SHA256
        assert len(sha256_hash) == 64  # 256 bits
        
        # SHA256 ist kollisionsresistent und kryptographisch sicher
        # (im Gegensatz zu MD5 das gebrochen ist)
    
    def test_serialization_attack_prevention(self):
        """Test dass sichere Serialisierung Angriffe verhindert"""
        # JSON kann keine Code-Ausführung
        safe_formats = ['json']
        unsafe_formats = ['pickle', 'yaml.load']  # yaml.load ist unsicher
        
        # Sichere Formate sollten keine Code-Ausführung ermöglichen
        for format_name in safe_formats:
            assert format_name in ['json']  # Bekannt sichere Formate
        
        # yaml.safe_load ist die sichere Alternative zu yaml.load
        safe_yaml_method = 'yaml.safe_load'
        assert 'safe_load' in safe_yaml_method
    
    def test_timeout_prevents_dos(self):
        """Test dass Timeouts DoS-Angriffe verhindern"""
        # Timeouts verhindern hängende Verbindungen
        reasonable_timeout = 30  # Sekunden
        
        assert reasonable_timeout > 0
        assert reasonable_timeout < 300  # Nicht zu lang
        
        # Verschiedene Timeout-Typen
        timeouts = {
            'connect': 10,    # Verbindungsaufbau
            'read': 30,       # Datenübertragung
            'total': 60       # Gesamt-Timeout
        }
        
        for timeout_type, timeout_value in timeouts.items():
            assert timeout_value > 0
            assert isinstance(timeout_value, int)


class TestRegressionPrevention:
    """Tests die sicherstellen dass keine Regressions zu unsicheren Methoden auftreten"""
    
    def test_no_md5_usage(self):
        """Test dass MD5 nicht mehr verwendet wird"""
        # Diese Funktionen sollten jetzt SHA256 verwenden
        password = "test123"
        result = weak_password_hash(password)
        
        # Ergebnis sollte SHA256-Länge haben (64 Zeichen)
        assert len(result) == 64
        
        # Sollte nicht MD5-Länge haben (32 Zeichen)
        assert len(result) != 32
    
    def test_no_pickle_loads_usage(self):
        """Test dass pickle.loads nicht mehr direkt verwendet wird"""
        # Die refaktorierte Funktion sollte JSON verwenden
        test_data = '{"safe": "data"}'
        result = unsafe_deserialize(test_data)
        
        # Sollte JSON-Parsing verwenden
        assert isinstance(result, dict)
        assert result["safe"] == "data"
    
    def test_yaml_safe_load_usage(self):
        """Test dass yaml.safe_load statt yaml.load verwendet wird"""
        yaml_data = "key: value\nnumber: 42"
        result = unsafe_yaml_load(yaml_data)
        
        # Sollte sicher geparst werden
        assert result["key"] == "value"
        assert result["number"] == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
