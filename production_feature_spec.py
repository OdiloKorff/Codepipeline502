"""
Production FeatureSpec Datenmodell.

Definiert ein Pydantic-v2-Modell für FeatureSpec mit folgenden Feldern:
- id mit Pattern nur Großbuchstaben Ziffern Bindestrich Punkt Unterstrich
- title, version mindestens 1, goal, optionale description
- target_paths als Liste strikt relativer Pfade ohne Traversal
- constraints, risk_level low medium high, reviewers
- model, token_budget mindestens 0
- tests mit coverage_min und pytest_args
- quality für Policy-Overrides, hard_musts

Implementiert Methoden für deterministische JSON-Ausgabe und SHA256-Hash,
sowie Laden und Speichern aus JSON oder YAML.
"""

import hashlib
import json
import os
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RiskLevel(str, Enum):
    """Risk-Level für Features."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TestConfig(BaseModel):
    """Test-Konfiguration."""
    model_config = ConfigDict(extra='forbid')
    
    coverage_min: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Minimum test coverage percentage"
    )
    pytest_args: List[str] = Field(
        default_factory=lambda: ["-v"],
        description="Additional pytest arguments"
    )


class QualityOverrides(BaseModel):
    """Quality-Policy-Overrides."""
    model_config = ConfigDict(extra='allow')  # Erlaube zusätzliche Felder
    
    max_complexity: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum cyclomatic complexity"
    )
    security_threshold: Optional[str] = Field(
        default=None,
        pattern=r"^(none|low|medium|high)$",
        description="Security scan severity threshold"
    )


class ProductionFeatureSpec(BaseModel):
    """
    Production-ready FeatureSpec mit vollständiger Validierung.
    
    Definiert alle Aspekte einer automatisierten Feature-Entwicklung
    mit strikten Validierungsregeln und deterministischer Serialisierung.
    """
    model_config = ConfigDict(
        extra='forbid',
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    # Pflichtfelder
    id: str = Field(
        ...,
        pattern=r"^[A-Z0-9._-]+$",
        min_length=1,
        max_length=50,
        description="Unique feature identifier (uppercase, digits, dash, dot, underscore only)"
    )
    
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable feature title"
    )
    
    version: int = Field(
        ...,
        ge=1,
        description="Feature specification version (must be >= 1)"
    )
    
    goal: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Clear description of what the feature should accomplish"
    )
    
    target_paths: List[str] = Field(
        ...,
        min_length=1,
        description="List of relative paths where changes are allowed"
    )
    
    constraints: List[str] = Field(
        default_factory=list,
        description="Implementation constraints and requirements"
    )
    
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM,
        description="Risk assessment level"
    )
    
    reviewers: List[str] = Field(
        default_factory=list,
        description="List of required reviewers"
    )
    
    model: str = Field(
        default="gpt-4o-mini",
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="LLM model identifier"
    )
    
    token_budget: int = Field(
        default=5000,
        ge=0,
        le=100000,
        description="Maximum tokens allowed for LLM operations"
    )
    
    # Optionale Felder
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Detailed feature description"
    )
    
    tests: TestConfig = Field(
        default_factory=TestConfig,
        description="Test configuration"
    )
    
    quality: QualityOverrides = Field(
        default_factory=QualityOverrides,
        description="Quality policy overrides"
    )
    
    hard_musts: List[str] = Field(
        default_factory=list,
        description="Critical quality gates that must pass"
    )
    
    @field_validator('target_paths')
    @classmethod
    def validate_target_paths(cls, v: List[str]) -> List[str]:
        """Validiere target_paths für Sicherheit."""
        if not v:
            raise ValueError("target_paths cannot be empty")
        
        validated_paths = []
        for path in v:
            # Entferne führende/trailing Whitespace
            path = path.strip()
            
            if not path:
                raise ValueError("Empty path in target_paths")
            
            # Prüfe auf absolute Pfade
            if os.path.isabs(path):
                raise ValueError(f"Absolute paths not allowed: {path}")
            
            # Prüfe auf Parent-Directory-Traversal
            if ".." in path:
                raise ValueError(f"Parent directory traversal not allowed: {path}")
            
            # Prüfe auf Windows-Drive-Letters
            if re.match(r"^[A-Za-z]:", path):
                raise ValueError(f"Windows drive letters not allowed: {path}")
            
            # Normalisiere Pfad
            normalized_path = os.path.normpath(path)
            
            # Prüfe nach Normalisierung erneut
            if os.path.isabs(normalized_path) or ".." in normalized_path:
                raise ValueError(f"Path traversal detected after normalization: {path}")
            
            validated_paths.append(normalized_path)
        
        return validated_paths
    
    @field_validator('reviewers')
    @classmethod
    def validate_reviewers(cls, v: List[str], info) -> List[str]:
        """Validiere Reviewer-Anforderungen basierend auf Risk-Level."""
        # Note: info.data ist verfügbar für andere Felder
        return v  # Wird in model_validator geprüft
    
    @model_validator(mode='after')
    def validate_risk_level_requirements(self) -> 'ProductionFeatureSpec':
        """Validiere Risk-Level-spezifische Anforderungen."""
        
        # High-Risk-Features benötigen mindestens 2 Reviewer
        if self.risk_level == RiskLevel.HIGH and len(self.reviewers) < 2:
            raise ValueError("High-Risk Features benötigen mindestens 2 Reviewer")
        
        # Medium-Risk-Features benötigen mindestens 1 Reviewer
        if self.risk_level == RiskLevel.MEDIUM and len(self.reviewers) < 1:
            raise ValueError("Medium-Risk Features benötigen mindestens 1 Reviewer")
        
        # High-Risk-Features benötigen höhere Coverage
        if self.risk_level == RiskLevel.HIGH and self.tests.coverage_min < 90.0:
            raise ValueError("High-Risk Features benötigen mindestens 90% Test-Coverage")
        
        # High-Risk-Features müssen Security-Scan enthalten
        if self.risk_level == RiskLevel.HIGH and "security_scan" not in self.hard_musts:
            self.hard_musts.append("security_scan")
        
        return self
    
    def canonical_json(self) -> str:
        """
        Deterministisches JSON für Hashing und Reproduzierbarkeit.
        
        Returns:
            JSON-String mit sortierten Keys und konsistenter Formatierung
        """
        # Konvertiere zu Dictionary
        data = self.model_dump()
        
        # Sortiere alle Dictionary-Keys rekursiv
        def sort_dict_recursive(obj):
            if isinstance(obj, dict):
                return {k: sort_dict_recursive(v) for k, v in sorted(obj.items())}
            elif isinstance(obj, list):
                return [sort_dict_recursive(item) for item in obj]
            else:
                return obj
        
        sorted_data = sort_dict_recursive(data)
        
        # Generiere deterministisches JSON
        return json.dumps(
            sorted_data,
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True
        )
    
    def sha256(self) -> str:
        """
        SHA256-Hash für Audit-Trail und Reproduzierbarkeit.
        
        Returns:
            64-Zeichen Hex-String
        """
        canonical = self.canonical_json()
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> 'ProductionFeatureSpec':
        """
        Lade FeatureSpec aus JSON- oder YAML-Datei.
        
        Args:
            file_path: Pfad zur Spec-Datei
            
        Returns:
            ProductionFeatureSpec-Instanz
            
        Raises:
            FileNotFoundError: Datei nicht gefunden
            ValueError: Ungültiges Format oder Validierungsfehler
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Spec-Datei nicht gefunden: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            raise ValueError(f"Spec-Datei ist leer: {file_path}")
        
        # Bestimme Format basierend auf Dateiendung und Inhalt
        suffix = file_path.suffix.lower()
        
        try:
            if suffix in ['.json'] or content.startswith('{'):
                data = json.loads(content)
            elif suffix in ['.yaml', '.yml'] or content.startswith('---'):
                data = yaml.safe_load(content)
            else:
                # Versuche JSON zuerst, dann YAML
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = yaml.safe_load(content)
        
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise ValueError(f"Ungültiges JSON/YAML-Format in {file_path}: {e}")
        
        if not isinstance(data, dict):
            raise ValueError(f"Spec-Datei muss ein JSON/YAML-Objekt enthalten: {file_path}")
        
        # Erstelle und validiere FeatureSpec
        try:
            return cls(**data)
        except Exception as e:
            raise ValueError(f"FeatureSpec-Validierung fehlgeschlagen für {file_path}: {e}")
    
    def to_file(self, file_path: Union[str, Path], format: str = "json") -> None:
        """
        Speichere FeatureSpec in JSON- oder YAML-Datei.
        
        Args:
            file_path: Ziel-Dateipfad
            format: "json" oder "yaml"
            
        Raises:
            ValueError: Ungültiges Format
        """
        file_path = Path(file_path)
        
        if format not in ["json", "yaml"]:
            raise ValueError(f"Ungültiges Format: {format}. Erlaubt: json, yaml")
        
        # Erstelle Verzeichnis falls nötig
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.model_dump()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            if format == "json":
                json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
            else:  # yaml
                # Konvertiere Enums zu Strings für YAML-Kompatibilität
                def convert_enums(obj):
                    if isinstance(obj, dict):
                        return {k: convert_enums(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_enums(item) for item in obj]
                    elif hasattr(obj, 'value'):  # Enum
                        return obj.value
                    else:
                        return obj
                
                yaml_data = convert_enums(data)
                yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=True)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Hole Zusammenfassung für Logging und Debugging.
        
        Returns:
            Dictionary mit wichtigen Spec-Informationen
        """
        return {
            "id": self.id,
            "title": self.title,
            "version": self.version,
            "risk_level": self.risk_level.value,
            "target_paths_count": len(self.target_paths),
            "reviewers_count": len(self.reviewers),
            "token_budget": self.token_budget,
            "coverage_min": self.tests.coverage_min,
            "hard_musts_count": len(self.hard_musts),
            "hash": self.sha256()[:16]
        }


def test_production_feature_spec():
    """Teste ProductionFeatureSpec umfassend."""
    print("🧪 PRODUCTION FEATURE SPEC TESTS")
    print("=" * 70)
    
    # Test 1: Gültige Spec erstellen
    print("\n✅ Test 1: Gültige Spec-Erstellung")
    
    valid_spec_data = {
        "id": "TEST-SPEC-001",
        "title": "Test Feature for Validation",
        "version": 1,
        "goal": "Comprehensive test of FeatureSpec validation and functionality",
        "description": "Detailed description of the test feature",
        "target_paths": ["src/test/", "tests/test/"],
        "constraints": ["secure implementation", "comprehensive testing"],
        "risk_level": "medium",
        "reviewers": ["tech-lead"],
        "model": "gpt-4o-mini",
        "token_budget": 5000,
        "tests": {
            "coverage_min": 85.0,
            "pytest_args": ["-v", "--tb=short"]
        },
        "quality": {
            "max_complexity": 10,
            "security_threshold": "medium"
        },
        "hard_musts": ["coverage_threshold", "security_scan"]
    }
    
    try:
        spec = ProductionFeatureSpec(**valid_spec_data)
        print(f"   ✅ Spec erstellt: {spec.id}")
        print(f"   📊 Summary: {spec.get_summary()}")
        
        # Test Hash-Länge
        hash_value = spec.sha256()
        print(f"   🔐 Hash: {hash_value[:16]}... (Länge: {len(hash_value)})")
        assert len(hash_value) == 64, f"Hash sollte 64 Zeichen haben, hat {len(hash_value)}"
        
        # Test deterministische JSON-Ausgabe
        json1 = spec.canonical_json()
        json2 = spec.canonical_json()
        assert json1 == json2, "Canonical JSON sollte deterministisch sein"
        print("   📄 Canonical JSON: Deterministisch ✅")
        
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return False
    
    # Test 2: Target-Paths-Validierung
    print("\n🛡️ Test 2: Target-Paths-Validierung")
    
    invalid_paths_tests = [
        ([], "Empty target_paths"),
        (["/absolute/path"], "Absolute path"),
        (["../parent/traversal"], "Parent traversal"),
        (["src/../etc/passwd"], "Hidden traversal"),
        (["C:\\Windows\\System32"], "Windows drive letter"),
        (["normal/path", "../bad/path"], "Mixed valid/invalid"),
        ([""], "Empty string path"),
        (["   "], "Whitespace-only path")
    ]
    
    for invalid_paths, test_name in invalid_paths_tests:
        test_data = valid_spec_data.copy()
        test_data["target_paths"] = invalid_paths
        
        try:
            ProductionFeatureSpec(**test_data)
            print(f"   ❌ {test_name}: Sollte fehlschlagen, aber hat nicht!")
            return False
        except ValueError as e:
            print(f"   ✅ {test_name}: Korrekt blockiert ({str(e)[:50]}...)")
    
    # Test 3: Risk-Level-Validierung
    print("\n🔥 Test 3: Risk-Level-Validierung")
    
    # High-Risk ohne genug Reviewer
    high_risk_data = valid_spec_data.copy()
    high_risk_data["risk_level"] = "high"
    high_risk_data["reviewers"] = ["single-reviewer"]  # Nur 1 statt 2
    
    try:
        ProductionFeatureSpec(**high_risk_data)
        print("   ❌ High-Risk mit 1 Reviewer: Sollte fehlschlagen!")
        return False
    except ValueError as e:
        print(f"   ✅ High-Risk-Validierung: {e}")
    
    # High-Risk mit korrekten Reviewern
    high_risk_data["reviewers"] = ["security-team", "tech-lead"]
    high_risk_data["tests"] = {"coverage_min": 90.0}  # Höhere Coverage für High-Risk
    
    try:
        high_risk_spec = ProductionFeatureSpec(**high_risk_data)
        print(f"   ✅ High-Risk korrekt: {high_risk_spec.id}")
        
        # Prüfe automatisches Hinzufügen von security_scan
        assert "security_scan" in high_risk_spec.hard_musts, "security_scan sollte automatisch hinzugefügt werden"
        print("   ✅ Security-Scan automatisch hinzugefügt")
        
    except Exception as e:
        print(f"   ❌ High-Risk-Spec-Fehler: {e}")
        return False
    
    # Test 4: Datei-I/O
    print("\n💾 Test 4: Datei-I/O (JSON/YAML)")
    
    # JSON-Export/Import
    json_file = "test_spec.json"
    try:
        spec.to_file(json_file, format="json")
        loaded_spec_json = ProductionFeatureSpec.from_file(json_file)
        
        assert spec.sha256() == loaded_spec_json.sha256(), "JSON-Roundtrip sollte identische Hashes produzieren"
        print("   ✅ JSON-Roundtrip: Identische Hashes")
        
    except Exception as e:
        print(f"   ❌ JSON-I/O-Fehler: {e}")
        return False
    
    # YAML-Export/Import
    yaml_file = "test_spec.yaml"
    try:
        spec.to_file(yaml_file, format="yaml")
        loaded_spec_yaml = ProductionFeatureSpec.from_file(yaml_file)
        
        assert spec.sha256() == loaded_spec_yaml.sha256(), "YAML-Roundtrip sollte identische Hashes produzieren"
        print("   ✅ YAML-Roundtrip: Identische Hashes")
        
    except Exception as e:
        print(f"   ❌ YAML-I/O-Fehler: {e}")
        return False
    
    # Test 5: Edge-Cases
    print("\n⚡ Test 5: Edge-Cases")
    
    edge_cases = [
        # ID-Pattern-Tests
        ({"id": "invalid-lowercase"}, "Lowercase in ID"),
        ({"id": "VALID_ID.123-TEST"}, "Valid complex ID", True),
        ({"id": ""}, "Empty ID"),
        ({"id": "A" * 51}, "Too long ID"),
        
        # Version-Tests
        ({"version": 0}, "Version 0"),
        ({"version": -1}, "Negative version"),
        
        # Token-Budget-Tests
        ({"token_budget": -1}, "Negative token budget"),
        ({"token_budget": 0}, "Zero token budget", True),
        ({"token_budget": 100001}, "Too high token budget"),
        
        # Coverage-Tests
        ({"tests": {"coverage_min": -1}}, "Negative coverage"),
        ({"tests": {"coverage_min": 101}}, "Coverage > 100%"),
    ]
    
    for test_data, test_name, *should_pass in edge_cases:
        should_pass = should_pass[0] if should_pass else False
        
        test_spec_data = valid_spec_data.copy()
        test_spec_data.update(test_data)
        
        try:
            test_spec = ProductionFeatureSpec(**test_spec_data)
            if should_pass:
                print(f"   ✅ {test_name}: Korrekt erlaubt")
            else:
                print(f"   ❌ {test_name}: Sollte fehlschlagen!")
                return False
        except Exception as e:
            if should_pass:
                print(f"   ❌ {test_name}: Sollte erlaubt sein! ({e})")
                return False
            else:
                print(f"   ✅ {test_name}: Korrekt blockiert")
    
    # Test 6: Reproduzierbarkeit
    print("\n🔄 Test 6: Reproduzierbarkeit")
    
    # Erstelle mehrere Instanzen derselben Spec
    hashes = []
    jsons = []
    
    for i in range(3):
        test_spec = ProductionFeatureSpec(**valid_spec_data)
        hashes.append(test_spec.sha256())
        jsons.append(test_spec.canonical_json())
    
    # Alle Hashes sollten identisch sein
    unique_hashes = set(hashes)
    unique_jsons = set(jsons)
    
    if len(unique_hashes) == 1 and len(unique_jsons) == 1:
        print("   ✅ Reproduzierbarkeit: 3 Instanzen → 1 Hash, 1 JSON")
    else:
        print(f"   ❌ Reproduzierbarkeit: {len(unique_hashes)} Hashes, {len(unique_jsons)} JSONs")
        return False
    
    # Cleanup
    for file_path in [json_file, yaml_file]:
        try:
            Path(file_path).unlink()
        except:
            pass
    
    print("\n🎉 Alle Tests bestanden!")
    print("✅ ProductionFeatureSpec ist vollständig funktional und sicher")
    
    return True


def demo_production_feature_spec():
    """Demo der Production FeatureSpec."""
    print("🏭 PRODUCTION FEATURE SPEC DEMO")
    print("=" * 80)
    
    # Führe Tests aus
    test_success = test_production_feature_spec()
    
    if not test_success:
        print("\n❌ Tests fehlgeschlagen!")
        return 1
    
    # Demo verschiedener Spec-Typen
    print("\n📋 Demo: Verschiedene Spec-Typen")
    
    spec_examples = [
        {
            "name": "Low-Risk Feature",
            "data": {
                "id": "LOW-RISK-001",
                "title": "Simple UI Enhancement",
                "version": 1,
                "goal": "Add a new button to the user interface",
                "target_paths": ["src/ui/"],
                "risk_level": "low",
                "reviewers": [],  # Low-Risk braucht keine Reviewer
                "token_budget": 2000
            }
        },
        {
            "name": "Medium-Risk Feature",
            "data": {
                "id": "MEDIUM-RISK-001", 
                "title": "API Endpoint Extension",
                "version": 1,
                "goal": "Add new REST API endpoint for user data",
                "target_paths": ["src/api/", "tests/api/"],
                "risk_level": "medium",
                "reviewers": ["backend-team"],
                "token_budget": 5000,
                "tests": {"coverage_min": 85.0}
            }
        },
        {
            "name": "High-Risk Feature",
            "data": {
                "id": "HIGH-RISK-001",
                "title": "Payment System Integration",
                "version": 1,
                "goal": "Integrate secure payment processing system",
                "target_paths": ["src/payment/", "tests/payment/"],
                "constraints": ["PCI DSS compliance", "encryption required"],
                "risk_level": "high",
                "reviewers": ["security-team", "senior-dev", "tech-lead"],
                "token_budget": 10000,
                "tests": {"coverage_min": 95.0},
                "hard_musts": ["security_scan", "coverage_threshold", "license_compliance"]
            }
        }
    ]
    
    for example in spec_examples:
        try:
            spec = ProductionFeatureSpec(**example["data"])
            summary = spec.get_summary()
            
            print(f"\n🎯 {example['name']}:")
            print(f"   ID: {summary['id']}")
            print(f"   Risk: {summary['risk_level']}")
            print(f"   Reviewers: {summary['reviewers_count']}")
            print(f"   Coverage: {summary['coverage_min']:.1f}%")
            print(f"   Hard-Musts: {summary['hard_musts_count']}")
            print(f"   Hash: {summary['hash']}...")
            
        except Exception as e:
            print(f"\n❌ {example['name']} Fehler: {e}")
    
    print("\n📊 Feature-Spec-Capabilities:")
    print("   ✅ Pydantic v2 mit strikter Validierung")
    print("   ✅ Deterministische JSON-Serialisierung")
    print("   ✅ SHA256-Hashing für Audit-Trail")
    print("   ✅ JSON/YAML-Import/Export")
    print("   ✅ Path-Security-Validierung")
    print("   ✅ Risk-Level-basierte Anforderungen")
    print("   ✅ Reproduzierbare Builds")
    
    print("\n✅ Production FeatureSpec Demo abgeschlossen!")
    
    return 0


if __name__ == "__main__":
    exit_code = demo_production_feature_spec()
    sys.exit(exit_code)
