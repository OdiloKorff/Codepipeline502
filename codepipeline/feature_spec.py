"""
Feature-Spezifikations-Modell innerhalb des Hauptpakets.

Symlink oder Kopie der feature_spec.py aus dem Root für saubere Paketstruktur.
"""

# Import der Hauptimplementierung aus dem Root
import sys
from pathlib import Path

# Füge Root-Verzeichnis zum Path hinzu
root_path = Path(__file__).parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

# Importiere alle Symbole aus der Root feature_spec.py
try:
    from feature_spec import *
    from feature_spec import FeatureSpec, QualityOverrides, TestConfig, create_feature_spec, load_feature_spec
except ImportError as e:
    # Fallback: Minimale Implementierung
    print(f"⚠️  Konnte feature_spec.py nicht aus Root laden: {e}")
    
    class FeatureSpec:
        """Minimal fallback FeatureSpec."""
        
        @classmethod
        def from_file(cls, file_path):
            raise NotImplementedError("FeatureSpec nicht verfügbar - siehe Root feature_spec.py")
        
        def sha256(self):
            return "fallback-hash"
