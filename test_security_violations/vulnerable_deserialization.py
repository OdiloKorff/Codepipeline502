
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
