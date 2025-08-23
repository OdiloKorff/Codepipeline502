"""
FeatureSpec Datenmodell für strukturierte Feature-Spezifikationen.

Implementiert ein robustes Pydantic-Modell mit Validierung, Serialisierung
und Audit-Funktionalitäten für sichere Feature-Entwicklung.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePath
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class TestConfig(BaseModel):
    """Test-Konfiguration für Feature-Spezifikationen."""
    coverage_min: int = Field(ge=0, le=100, default=80, description="Minimale Test-Coverage in %")
    pytest_args: list[str] = Field(default_factory=list, description="Zusätzliche pytest Argumente")


class QualityOverrides(BaseModel):
    """Optionale Quality-Policy Overrides."""
    score_threshold: Optional[int] = Field(None, ge=0, le=100, description="Override für Score-Schwellwert")
    coverage_min: Optional[int] = Field(None, ge=0, le=100, description="Override für Coverage-Minimum")
    sast_high: Optional[int] = Field(None, ge=0, description="Override für SAST High-Findings")
    secret_findings: Optional[int] = Field(None, ge=0, description="Override für Secret-Findings")
    budget_max: Optional[float] = Field(None, ge=0, description="Override für Budget-Maximum")


class FeatureSpec(BaseModel):
    """
    Strukturierte Feature-Spezifikation mit Validierung und Audit-Funktionen.
    
    Definiert alle notwendigen Metadaten, Constraints und Konfigurationen
    für sichere, automatisierte Feature-Entwicklung.
    """
    
    # Basis-Metadaten
    id: str = Field(
        ..., 
        pattern=r'^[A-Z0-9._-]+$',
        description="Feature-ID (nur Großbuchstaben, Ziffern, Bindestrich, Punkt, Unterstrich)"
    )
    title: str = Field(..., min_length=1, max_length=200, description="Feature-Titel")
    version: int = Field(ge=1, description="Feature-Version (>=1)")
    goal: str = Field(..., min_length=10, description="Feature-Ziel und Beschreibung")
    description: Optional[str] = Field(None, description="Optionale detaillierte Beschreibung")
    
    # Technische Spezifikation
    target_paths: list[str] = Field(
        ..., 
        min_length=1,
        description="Ziel-Pfade für Änderungen (nur relative Pfade)"
    )
    constraints: list[str] = Field(default_factory=list, description="Entwicklungs-Constraints")
    risk_level: Literal["low", "medium", "high"] = Field(default="medium", description="Risiko-Level")
    reviewers: list[str] = Field(default_factory=list, description="Erforderliche Reviewer")
    
    # LLM-Konfiguration
    model: str = Field(default="gpt-4o", description="LLM-Identifier")
    token_budget: int = Field(ge=0, default=8000, description="Token-Budget (>=0)")
    
    # Test & Quality
    tests: TestConfig = Field(default_factory=TestConfig, description="Test-Konfiguration")
    quality: Optional[QualityOverrides] = Field(None, description="Quality-Policy Overrides")
    hard_musts: list[str] = Field(default_factory=list, description="Harte Anforderungen")
    
    @field_validator('target_paths')
    @classmethod
    def validate_target_paths(cls, v: list[str]) -> list[str]:
        """Validiert target_paths gegen absolute Pfade und Parent-Traversal."""
        if not v:
            raise ValueError("target_paths darf nicht leer sein")
        
        validated_paths = []
        for path_str in v:
            if not path_str:
                raise ValueError("Leere Pfade sind nicht erlaubt")
            
            # Normalisiere Pfad
            path = PurePath(path_str)
            
            # Prüfe auf absolute Pfade (verschiedene Formate)
            if (path.is_absolute() or 
                str(path_str).startswith('/') or 
                str(path_str).startswith('\\') or
                (len(path_str) >= 3 and path_str[1:3] == ':\\')):  # Windows C:\
                raise ValueError(f"Absolute Pfade nicht erlaubt: {path_str}")
            
            # Prüfe auf Parent-Traversal (..)
            if '..' in path.parts:
                raise ValueError(f"Parent-Traversal nicht erlaubt: {path_str}")
            
            # Normalisiere und füge hinzu
            normalized = str(path).replace('\\', '/')
            validated_paths.append(normalized)
        
        return validated_paths
    
    @model_validator(mode='after')
    def validate_model_constraints(self) -> 'FeatureSpec':
        """Zusätzliche Model-weite Validierungen."""
        # Prüfe Token-Budget vs. Model
        if self.model.startswith('gpt-4') and self.token_budget > 128000:
            raise ValueError("GPT-4 Token-Budget überschreitet Maximum (128k)")
        elif self.model.startswith('gpt-3.5') and self.token_budget > 16000:
            raise ValueError("GPT-3.5 Token-Budget überschreitet Maximum (16k)")
        
        # Prüfe Risk-Level vs. Reviewers
        if self.risk_level == "high" and len(self.reviewers) < 2:
            raise ValueError("High-Risk Features benötigen mindestens 2 Reviewer")
        
        return self
    
    def canonical_json(self) -> str:
        """
        Erzeugt deterministisches JSON für Audit-Zwecke.
        
        Returns:
            Sortiertes JSON ohne Whitespace für konsistente Hashes.
        """
        # Konvertiere zu Dict und sortiere rekursiv
        data = self.model_dump(mode='json')
        return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    
    def sha256(self) -> str:
        """
        Berechnet SHA256-Hash der kanonischen JSON-Repräsentation.
        
        Returns:
            64-Zeichen Hex-String des SHA256-Hashes.
        """
        canonical = self.canonical_json()
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    @classmethod
    def from_file(cls, file_path: str | Path) -> 'FeatureSpec':
        """
        Lädt FeatureSpec aus JSON oder YAML-Datei.
        
        Args:
            file_path: Pfad zur Spec-Datei (.json oder .yaml/.yml)
        
        Returns:
            FeatureSpec-Instanz
        
        Raises:
            FileNotFoundError: Datei existiert nicht
            ValueError: Ungültiges Format oder Inhalt
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Spec-Datei nicht gefunden: {file_path}")
        
        content = path.read_text(encoding='utf-8')
        
        if path.suffix.lower() == '.json':
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Ungültiges JSON in {file_path}: {e}") from e
        elif path.suffix.lower() in ('.yaml', '.yml'):
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError as e:
                raise ValueError(f"Ungültiges YAML in {file_path}: {e}") from e
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}. Use .json, .yaml, or .yml")
        
        if not isinstance(data, dict):
            raise ValueError(f"Spec-Datei muss ein Objekt enthalten, nicht {type(data).__name__}")
        
        return cls(**data)
    
    def to_file(self, file_path: str | Path, format_type: Optional[Literal["json", "yaml"]] = None) -> None:
        """
        Speichert FeatureSpec in JSON oder YAML-Datei.
        
        Args:
            file_path: Ziel-Pfad für die Datei
            format_type: Explizites Format ('json' oder 'yaml'). 
                        Falls None, wird aus Dateiendung abgeleitet.
        
        Raises:
            ValueError: Ungültiges Format
        """
        path = Path(file_path)
        
        # Format bestimmen
        if format_type is None:
            if path.suffix.lower() == '.json':
                format_type = 'json'
            elif path.suffix.lower() in ('.yaml', '.yml'):
                format_type = 'yaml'
            else:
                raise ValueError(f"Cannot infer format from {path.suffix}. Specify format_type explicitly.")
        
        # Verzeichnis erstellen falls nötig
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Daten serialisieren
        data = self.model_dump(mode='json')
        
        if format_type == 'json':
            content = json.dumps(data, indent=2, ensure_ascii=False)
        elif format_type == 'yaml':
            content = yaml.dump(
                data, 
                default_flow_style=False, 
                allow_unicode=True, 
                sort_keys=True,
                indent=2
            )
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        path.write_text(content, encoding='utf-8')


# Convenience-Funktionen
def load_feature_spec(file_path: str | Path) -> FeatureSpec:
    """Lädt FeatureSpec aus Datei (Alias für FeatureSpec.from_file)."""
    return FeatureSpec.from_file(file_path)


def create_feature_spec(
    id: str,
    title: str,
    goal: str,
    target_paths: list[str],
    version: int = 1,
    **kwargs: Any
) -> FeatureSpec:
    """Erstellt FeatureSpec mit Mindest-Parametern."""
    return FeatureSpec(
        id=id,
        title=title,
        goal=goal,
        target_paths=target_paths,
        version=version,
        **kwargs
    )
