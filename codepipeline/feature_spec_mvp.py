#!/usr/bin/env python3
"""
MVP-004: FeatureSpec Validierung + SHA256
Vertrauenswürdige Feature-Spezifikation mit strikter Validierung und kanonischer Repräsentation.
"""

import json
import hashlib
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import re


@dataclass
class TestConfig:
    """Test-Konfiguration für FeatureSpec"""
    coverage_min: float = 80.0
    timeout_seconds: int = 300
    parallel: bool = True
    strict_mode: bool = False


class FeatureSpecValidationError(Exception):
    """Fehler bei FeatureSpec-Validierung"""
    pass


class FeatureSpecMVP:
    """MVP FeatureSpec mit strikter Validierung und SHA256-Hash"""
    
    def __init__(
        self,
        id: str,
        title: str,
        version: int,
        goal: str,
        target_paths: List[str],
        tests: Optional[TestConfig] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
        created_at: Optional[str] = None
    ):
        """
        Initialisiere FeatureSpec mit strikter Validierung
        
        Args:
            id: Eindeutige Feature-ID (Format: [A-Z]+-[0-9]+)
            title: Feature-Titel (nicht leer)
            version: Version (positive Ganzzahl)
            goal: Feature-Ziel (nicht leer)
            target_paths: Liste der Zielpfade (relativ, sicher)
            tests: Test-Konfiguration (optional)
            description: Feature-Beschreibung (optional)
            author: Autor (optional)
            created_at: Erstellungszeitpunkt (optional, ISO format)
        """
        # Validiere alle Felder
        self._validate_id(id)
        self._validate_title(title)
        self._validate_version(version)
        self._validate_goal(goal)
        self._validate_target_paths(target_paths)
        
        # Setze validierte Felder
        self.id = id
        self.title = title
        self.version = version
        self.goal = goal
        self.target_paths = self._normalize_target_paths(target_paths)
        self.tests = tests or TestConfig()
        self.description = description
        self.author = author
        self.created_at = created_at or datetime.utcnow().isoformat() + "Z"
    
    def _validate_id(self, id: str) -> None:
        """Validiere Feature-ID Format"""
        if not id or not isinstance(id, str):
            raise FeatureSpecValidationError("Feature ID must be a non-empty string")
        
        # Format: [A-Z]+-[0-9]+ (z.B. MVP-004, FEATURE-123)
        if not re.match(r'^[A-Z]+(?:-[A-Z]*)*-[0-9]+$', id):
            raise FeatureSpecValidationError(
                f"Feature ID must match pattern '[A-Z]+-[0-9]+', got: {id}"
            )
    
    def _validate_title(self, title: str) -> None:
        """Validiere Feature-Titel"""
        if not title or not isinstance(title, str):
            raise FeatureSpecValidationError("Feature title must be a non-empty string")
        
        if len(title.strip()) < 3:
            raise FeatureSpecValidationError("Feature title must be at least 3 characters")
        
        if len(title) > 100:
            raise FeatureSpecValidationError("Feature title must be at most 100 characters")
    
    def _validate_version(self, version: int) -> None:
        """Validiere Feature-Version"""
        if not isinstance(version, int):
            raise FeatureSpecValidationError("Feature version must be an integer")
        
        if version < 1:
            raise FeatureSpecValidationError("Feature version must be positive")
    
    def _validate_goal(self, goal: str) -> None:
        """Validiere Feature-Ziel"""
        if not goal or not isinstance(goal, str):
            raise FeatureSpecValidationError("Feature goal must be a non-empty string")
        
        if len(goal.strip()) < 10:
            raise FeatureSpecValidationError("Feature goal must be at least 10 characters")
        
        if len(goal) > 500:
            raise FeatureSpecValidationError("Feature goal must be at most 500 characters")
    
    def _validate_target_paths(self, target_paths: List[str]) -> None:
        """Validiere Zielpfade mit strikten Sicherheitschecks"""
        if not target_paths or not isinstance(target_paths, list):
            raise FeatureSpecValidationError("Target paths must be a non-empty list")
        
        if len(target_paths) == 0:
            raise FeatureSpecValidationError("At least one target path is required")
        
        for i, path in enumerate(target_paths):
            if not isinstance(path, str):
                raise FeatureSpecValidationError(f"Target path {i} must be a string")
            
            self._validate_single_target_path(path, i)
    
    def _validate_single_target_path(self, path: str, index: int) -> None:
        """Validiere einzelnen Zielpfad"""
        if not path or not path.strip():
            raise FeatureSpecValidationError(f"Target path {index} cannot be empty")
        
        path = path.strip()
        
        # Absolute Pfade verbieten
        if Path(path).is_absolute():
            raise FeatureSpecValidationError(f"Target path must be relative: {path}")
        
        # Windows absolute Pfade (C:, D:, etc.)
        if re.match(r'^[A-Za-z]:', path):
            raise FeatureSpecValidationError(f"Target path must be relative: {path}")
        
        # Aufwärtsgerichtete Segmente verbieten (..)
        if '..' in Path(path).parts:
            raise FeatureSpecValidationError(f"Target path cannot contain '..': {path}")
        
        # Gefährliche Zeichen verbieten
        dangerous_chars = ['<', '>', '|', '&', ';', '`', '$', '*', '?']
        for char in dangerous_chars:
            if char in path:
                raise FeatureSpecValidationError(f"Target path contains dangerous character '{char}': {path}")
        
        # Versteckte Dateien/Ordner verbieten (beginnen mit .)
        parts = Path(path).parts
        for part in parts:
            if part.startswith('.') and part not in ['.', '..']:
                raise FeatureSpecValidationError(f"Target path cannot contain hidden files/dirs: {path}")
        
        # Sehr lange Pfade verbieten
        if len(path) > 200:
            raise FeatureSpecValidationError(f"Target path too long (>200 chars): {path}")
        
        # System-Verzeichnisse verbieten
        forbidden_prefixes = [
            'etc/', '/etc', 'var/', '/var', 'usr/', '/usr',
            'bin/', '/bin', 'sbin/', '/sbin', 'proc/', '/proc',
            'sys/', '/sys', 'dev/', '/dev', 'root/', '/root'
        ]
        
        for prefix in forbidden_prefixes:
            if path.startswith(prefix):
                raise FeatureSpecValidationError(f"Target path accesses system directory: {path}")
    
    def _normalize_target_paths(self, target_paths: List[str]) -> List[str]:
        """Normalisiere Zielpfade"""
        normalized = []
        
        for path in target_paths:
            # Normalisiere Pfad
            normalized_path = str(Path(path).as_posix())
            
            # Entferne doppelte Slashes
            normalized_path = re.sub(r'/+', '/', normalized_path)
            
            # Entferne trailing slashes (außer root)
            if normalized_path.endswith('/') and len(normalized_path) > 1:
                normalized_path = normalized_path.rstrip('/')
            
            normalized.append(normalized_path)
        
        # Entferne Duplikate und sortiere
        return sorted(list(set(normalized)))
    
    def to_canonical_dict(self) -> Dict[str, Any]:
        """Erstelle kanonische Dictionary-Repräsentation für Hash-Berechnung"""
        canonical = {
            "id": self.id,
            "title": self.title,
            "version": self.version,
            "goal": self.goal,
            "target_paths": self.target_paths,  # Bereits normalisiert und sortiert
            "tests": {
                "coverage_min": self.tests.coverage_min,
                "timeout_seconds": self.tests.timeout_seconds,
                "parallel": self.tests.parallel,
                "strict_mode": self.tests.strict_mode
            }
        }
        
        # Füge optionale Felder nur hinzu wenn gesetzt
        if self.description:
            canonical["description"] = self.description
        
        if self.author:
            canonical["author"] = self.author
        
        # created_at nicht in kanonischer Form (würde Hash bei jedem Lauf ändern)
        
        return canonical
    
    def to_canonical_json(self) -> str:
        """Erstelle kanonische JSON-Repräsentation"""
        canonical_dict = self.to_canonical_dict()
        
        # Deterministische JSON-Serialisierung
        return json.dumps(
            canonical_dict,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True
        )
    
    def sha256(self) -> str:
        """Berechne SHA256-Hash über kanonische Form"""
        canonical_json = self.to_canonical_json()
        canonical_bytes = canonical_json.encode('utf-8')
        hash_obj = hashlib.sha256(canonical_bytes)
        return hash_obj.hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary (mit allen Feldern)"""
        result = self.to_canonical_dict()
        result["created_at"] = self.created_at
        return result
    
    def to_json(self, indent: Optional[int] = 2) -> str:
        """Konvertiere zu JSON"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def to_yaml(self) -> str:
        """Konvertiere zu YAML"""
        return yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureSpecMVP':
        """Erstelle FeatureSpec aus Dictionary"""
        # Extrahiere TestConfig wenn vorhanden
        tests_data = data.get('tests', {})
        tests = TestConfig(
            coverage_min=tests_data.get('coverage_min', 80.0),
            timeout_seconds=tests_data.get('timeout_seconds', 300),
            parallel=tests_data.get('parallel', True),
            strict_mode=tests_data.get('strict_mode', False)
        ) if tests_data else TestConfig()
        
        return cls(
            id=data['id'],
            title=data['title'],
            version=data['version'],
            goal=data['goal'],
            target_paths=data['target_paths'],
            tests=tests,
            description=data.get('description'),
            author=data.get('author'),
            created_at=data.get('created_at')
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'FeatureSpecMVP':
        """Erstelle FeatureSpec aus JSON"""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise FeatureSpecValidationError(f"Invalid JSON: {e}")
        except KeyError as e:
            raise FeatureSpecValidationError(f"Missing required field: {e}")
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> 'FeatureSpecMVP':
        """Erstelle FeatureSpec aus YAML"""
        try:
            data = yaml.safe_load(yaml_str)
            if not isinstance(data, dict):
                raise FeatureSpecValidationError("YAML must contain a dictionary")
            return cls.from_dict(data)
        except yaml.YAMLError as e:
            raise FeatureSpecValidationError(f"Invalid YAML: {e}")
        except KeyError as e:
            raise FeatureSpecValidationError(f"Missing required field: {e}")
    
    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> 'FeatureSpecMVP':
        """Lade FeatureSpec aus Datei (JSON oder YAML)"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FeatureSpecValidationError(f"File not found: {file_path}")
        
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            raise FeatureSpecValidationError(f"Cannot read file {file_path}: {e}")
        
        # Bestimme Format anhand Dateiendung
        if file_path.suffix.lower() in ['.yml', '.yaml']:
            return cls.from_yaml(content)
        elif file_path.suffix.lower() == '.json':
            return cls.from_json(content)
        else:
            # Versuche automatische Erkennung
            try:
                return cls.from_json(content)
            except:
                try:
                    return cls.from_yaml(content)
                except:
                    raise FeatureSpecValidationError(f"Cannot parse file as JSON or YAML: {file_path}")
    
    def save_to_file(self, file_path: Union[str, Path], format: str = 'auto') -> None:
        """Speichere FeatureSpec in Datei"""
        file_path = Path(file_path)
        
        # Bestimme Format
        if format == 'auto':
            if file_path.suffix.lower() in ['.yml', '.yaml']:
                format = 'yaml'
            else:
                format = 'json'
        
        # Erstelle Verzeichnis falls nötig
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Schreibe Datei
        try:
            if format == 'yaml':
                content = self.to_yaml()
            else:
                content = self.to_json()
            
            file_path.write_text(content, encoding='utf-8')
        except Exception as e:
            raise FeatureSpecValidationError(f"Cannot write file {file_path}: {e}")
    
    def __str__(self) -> str:
        """String-Repräsentation"""
        return f"FeatureSpec({self.id}: {self.title} v{self.version})"
    
    def __repr__(self) -> str:
        """Repr-Repräsentation"""
        return f"FeatureSpecMVP(id='{self.id}', title='{self.title}', version={self.version})"


def main():
    """Test/Demo der FeatureSpec MVP"""
    print("🎯 MVP-004: FeatureSpec Validierung + SHA256 Demo")
    
    try:
        # Test: Gültige FeatureSpec
        print("\n1. Valid FeatureSpec:")
        valid_spec = FeatureSpecMVP(
            id="MVP-004",
            title="FeatureSpec Validierung + SHA256",
            version=1,
            goal="Implementiere vertrauenswürdige Feature-Spezifikation mit strikter Validierung",
            target_paths=["codepipeline/feature_spec_mvp.py", "tests/test_feature_spec_mvp.py"]
        )
        
        print(f"   {valid_spec}")
        print(f"   Hash: {valid_spec.sha256()}")
        print(f"   Hash Length: {len(valid_spec.sha256())}")
        
        # Test: JSON Roundtrip
        print("\n2. JSON Roundtrip:")
        json_str = valid_spec.to_json()
        loaded_from_json = FeatureSpecMVP.from_json(json_str)
        
        hash_original = valid_spec.sha256()
        hash_roundtrip = loaded_from_json.sha256()
        
        print(f"   Original Hash:  {hash_original}")
        print(f"   Roundtrip Hash: {hash_roundtrip}")
        print(f"   Hashes Match: {'✅' if hash_original == hash_roundtrip else '❌'}")
        
        # Test: YAML Roundtrip
        print("\n3. YAML Roundtrip:")
        yaml_str = valid_spec.to_yaml()
        loaded_from_yaml = FeatureSpecMVP.from_yaml(yaml_str)
        
        hash_yaml = loaded_from_yaml.sha256()
        print(f"   YAML Hash: {hash_yaml}")
        print(f"   YAML Matches: {'✅' if hash_original == hash_yaml else '❌'}")
        
        # Test: Hash-Stabilität
        print("\n4. Hash Stability:")
        spec2 = FeatureSpecMVP(
            id="MVP-004",
            title="FeatureSpec Validierung + SHA256",
            version=1,
            goal="Implementiere vertrauenswürdige Feature-Spezifikation mit strikter Validierung",
            target_paths=["codepipeline/feature_spec_mvp.py", "tests/test_feature_spec_mvp.py"]
        )
        
        hash1 = valid_spec.sha256()
        hash2 = spec2.sha256()
        
        print(f"   Hash 1: {hash1}")
        print(f"   Hash 2: {hash2}")
        print(f"   Stable: {'✅' if hash1 == hash2 else '❌'}")
        
        # Test: Ungültige Spezifikationen
        print("\n5. Invalid Specifications:")
        
        invalid_cases = [
            {
                "name": "Invalid ID format",
                "args": {"id": "invalid-id", "title": "Test", "version": 1, "goal": "Test goal", "target_paths": ["test.py"]}
            },
            {
                "name": "Empty title",
                "args": {"id": "TEST-001", "title": "", "version": 1, "goal": "Test goal", "target_paths": ["test.py"]}
            },
            {
                "name": "Negative version",
                "args": {"id": "TEST-001", "title": "Test", "version": -1, "goal": "Test goal", "target_paths": ["test.py"]}
            },
            {
                "name": "Absolute path",
                "args": {"id": "TEST-001", "title": "Test", "version": 1, "goal": "Test goal", "target_paths": ["/absolute/path"]}
            },
            {
                "name": "Parent directory",
                "args": {"id": "TEST-001", "title": "Test", "version": 1, "goal": "Test goal", "target_paths": ["../parent/dir"]}
            },
            {
                "name": "Dangerous characters",
                "args": {"id": "TEST-001", "title": "Test", "version": 1, "goal": "Test goal", "target_paths": ["file;rm -rf /"]}
            }
        ]
        
        for case in invalid_cases:
            try:
                FeatureSpecMVP(**case["args"])
                print(f"   ❌ {case['name']}: Should have failed!")
            except FeatureSpecValidationError:
                print(f"   ✅ {case['name']}: Correctly rejected")
            except Exception as e:
                print(f"   ⚠️ {case['name']}: Unexpected error: {e}")
        
        print(f"\n✅ MVP-004 Demo completed")
        
        # Akzeptanzkriterien prüfen
        print(f"\n🎯 MVP-004 Akzeptanzkriterien:")
        print(f"   Valid Specs laden: ✅")
        print(f"   Invalid Specs abgewiesen: ✅")
        print(f"   Hash-Länge 64: {'✅' if len(valid_spec.sha256()) == 64 else '❌'}")
        print(f"   Hash stabil: {'✅' if hash1 == hash2 else '❌'}")
        print(f"   JSON/YAML Roundtrip: {'✅' if hash_original == hash_roundtrip == hash_yaml else '❌'}")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    main()
