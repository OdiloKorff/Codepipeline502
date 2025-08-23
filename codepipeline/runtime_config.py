"""
Runtime-Config und Secret-Resolver nach 12-Factor-Prinzipien.

Implementiert Umgebungsvariablen-basierte Konfiguration mit optionalen Defaults,
strikter Validierung und zentralem Secret-Resolver.
"""

from __future__ import annotations

import os
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Type, get_type_hints
import logging

from .secret_resolver import get_secret, SecretError


logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Fehler bei Konfiguration."""
    pass


class ValidationError(ConfigError):
    """Fehler bei Validierung."""
    pass


class ConfigType(Enum):
    """Unterstützte Konfigurationstypen."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    SECRET = "secret"


@dataclass
class ConfigField:
    """Konfigurationsfeld-Definition."""
    name: str
    config_type: ConfigType
    required: bool = True
    default: Optional[Any] = None
    env_var: Optional[str] = None
    description: str = ""
    
    # Validierung
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None
    
    def __post_init__(self):
        if self.env_var is None:
            # Auto-generate env var name: field_name -> FIELD_NAME
            self.env_var = self.name.upper().replace('-', '_')


class ConfigValidator:
    """Validator für Konfigurationswerte."""
    
    @staticmethod
    def validate_field(field: ConfigField, value: Any) -> Any:
        """
        Validiere Konfigurationsfeld.
        
        Args:
            field: Feld-Definition
            value: Zu validierender Wert
            
        Returns:
            Validierter und konvertierter Wert
            
        Raises:
            ValidationError: Bei Validierungsfehlern
        """
        if value is None:
            if field.required:
                raise ValidationError(f"Required field '{field.name}' is missing")
            return field.default
        
        # Typ-Konvertierung
        try:
            converted_value = ConfigValidator._convert_type(field, value)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Field '{field.name}': Type conversion failed - {e}")
        
        # Validierungen
        ConfigValidator._validate_constraints(field, converted_value)
        
        return converted_value
    
    @staticmethod
    def _convert_type(field: ConfigField, value: Any) -> Any:
        """Konvertiere Wert zum korrekten Typ."""
        if field.config_type == ConfigType.STRING:
            return str(value)
        elif field.config_type == ConfigType.INTEGER:
            return int(value)
        elif field.config_type == ConfigType.FLOAT:
            return float(value)
        elif field.config_type == ConfigType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        elif field.config_type == ConfigType.LIST:
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                # Parse comma-separated string
                return [item.strip() for item in value.split(',') if item.strip()]
            return [value]
        elif field.config_type == ConfigType.SECRET:
            return str(value)  # Secrets are always strings
        else:
            return value
    
    @staticmethod
    def _validate_constraints(field: ConfigField, value: Any):
        """Validiere Constraints."""
        # Numeric constraints
        if field.config_type in (ConfigType.INTEGER, ConfigType.FLOAT):
            if field.min_value is not None and value < field.min_value:
                raise ValidationError(f"Field '{field.name}': Value {value} < min {field.min_value}")
            if field.max_value is not None and value > field.max_value:
                raise ValidationError(f"Field '{field.name}': Value {value} > max {field.max_value}")
        
        # String/List length constraints
        if field.config_type in (ConfigType.STRING, ConfigType.LIST):
            length = len(value)
            if field.min_length is not None and length < field.min_length:
                raise ValidationError(f"Field '{field.name}': Length {length} < min {field.min_length}")
            if field.max_length is not None and length > field.max_length:
                raise ValidationError(f"Field '{field.name}': Length {length} > max {field.max_length}")
        
        # Allowed values constraint
        if field.allowed_values is not None and value not in field.allowed_values:
            raise ValidationError(f"Field '{field.name}': Value '{value}' not in allowed values {field.allowed_values}")
        
        # Pattern constraint (for strings)
        if field.config_type == ConfigType.STRING and field.pattern is not None:
            import re
            if not re.match(field.pattern, value):
                raise ValidationError(f"Field '{field.name}': Value '{value}' doesn't match pattern '{field.pattern}'")


class BaseConfig(ABC):
    """Basis-Klasse für Konfigurationen."""
    
    def __init__(self):
        self._fields: Dict[str, ConfigField] = {}
        self._values: Dict[str, Any] = {}
        self._define_fields()
        self._load_configuration()
    
    @abstractmethod
    def _define_fields(self):
        """Definiere Konfigurationsfelder. Muss von Subklassen implementiert werden."""
        pass
    
    def add_field(self, field: ConfigField):
        """Füge Konfigurationsfeld hinzu."""
        self._fields[field.name] = field
    
    def _load_configuration(self):
        """Lade Konfiguration aus Umgebungsvariablen."""
        errors = []
        
        for field_name, field in self._fields.items():
            try:
                value = self._get_field_value(field)
                validated_value = ConfigValidator.validate_field(field, value)
                self._values[field_name] = validated_value
                
                # Log non-secret values
                if field.config_type != ConfigType.SECRET:
                    logger.debug(f"Config loaded: {field_name} = {validated_value}")
                else:
                    logger.debug(f"Secret loaded: {field_name} = [REDACTED]")
                    
            except (ValidationError, SecretError) as e:
                errors.append(f"{field_name}: {e}")
        
        if errors:
            error_msg = "Configuration validation failed:\\n" + "\\n".join(f"  - {err}" for err in errors)
            logger.error(error_msg)
            raise ConfigError(error_msg)
        
        logger.info(f"Configuration loaded successfully: {len(self._fields)} fields")
    
    def _get_field_value(self, field: ConfigField) -> Optional[str]:
        """Hole Feldwert aus Umgebung oder Secret-Resolver."""
        if field.config_type == ConfigType.SECRET:
            # Secrets über zentralen Resolver
            try:
                return get_secret(field.name.upper())
            except SecretError:
                if field.required:
                    raise
                return field.default
        else:
            # Normale Umgebungsvariablen
            return os.getenv(field.env_var, field.default)
    
    def get(self, field_name: str) -> Any:
        """Hole Konfigurationswert."""
        if field_name not in self._values:
            raise ConfigError(f"Unknown configuration field: {field_name}")
        return self._values[field_name]
    
    def get_all(self) -> Dict[str, Any]:
        """Hole alle Konfigurationswerte (ohne Secrets)."""
        result = {}
        for field_name, value in self._values.items():
            field = self._fields[field_name]
            if field.config_type != ConfigType.SECRET:
                result[field_name] = value
            else:
                result[field_name] = "[REDACTED]"
        return result
    
    def validate(self) -> List[str]:
        """Validiere Konfiguration und gib Fehler zurück."""
        errors = []
        
        for field_name, field in self._fields.items():
            try:
                value = self._get_field_value(field)
                ConfigValidator.validate_field(field, value)
            except (ValidationError, SecretError) as e:
                errors.append(f"{field_name}: {e}")
        
        return errors


class WebAPIConfig(BaseConfig):
    """Konfiguration für Web-API-Programme."""
    
    def _define_fields(self):
        self.add_field(ConfigField(
            name="host",
            config_type=ConfigType.STRING,
            default="0.0.0.0",
            description="Host address to bind to"
        ))
        
        self.add_field(ConfigField(
            name="port",
            config_type=ConfigType.INTEGER,
            default=8000,
            min_value=1,
            max_value=65535,
            description="Port to listen on"
        ))
        
        self.add_field(ConfigField(
            name="log_level",
            config_type=ConfigType.STRING,
            default="INFO",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            description="Logging level"
        ))
        
        self.add_field(ConfigField(
            name="database_url",
            config_type=ConfigType.SECRET,
            required=False,
            description="Database connection URL"
        ))
        
        self.add_field(ConfigField(
            name="api_key",
            config_type=ConfigType.SECRET,
            required=False,
            description="API authentication key"
        ))
        
        self.add_field(ConfigField(
            name="cors_origins",
            config_type=ConfigType.LIST,
            default=["*"],
            description="CORS allowed origins"
        ))
        
        self.add_field(ConfigField(
            name="debug",
            config_type=ConfigType.BOOLEAN,
            default=False,
            description="Enable debug mode"
        ))


class CLIConfig(BaseConfig):
    """Konfiguration für CLI-Programme."""
    
    def _define_fields(self):
        self.add_field(ConfigField(
            name="log_level",
            config_type=ConfigType.STRING,
            default="INFO",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            description="Logging level"
        ))
        
        self.add_field(ConfigField(
            name="config_file",
            config_type=ConfigType.STRING,
            required=False,
            description="Path to configuration file"
        ))
        
        self.add_field(ConfigField(
            name="output_format",
            config_type=ConfigType.STRING,
            default="text",
            allowed_values=["text", "json", "yaml"],
            description="Output format"
        ))
        
        self.add_field(ConfigField(
            name="verbose",
            config_type=ConfigType.BOOLEAN,
            default=False,
            description="Enable verbose output"
        ))


class WorkerConfig(BaseConfig):
    """Konfiguration für Worker-Programme."""
    
    def _define_fields(self):
        self.add_field(ConfigField(
            name="log_level",
            config_type=ConfigType.STRING,
            default="INFO",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            description="Logging level"
        ))
        
        self.add_field(ConfigField(
            name="queue_url",
            config_type=ConfigType.SECRET,
            required=True,
            description="Queue connection URL"
        ))
        
        self.add_field(ConfigField(
            name="worker_concurrency",
            config_type=ConfigType.INTEGER,
            default=1,
            min_value=1,
            max_value=100,
            description="Number of concurrent workers"
        ))
        
        self.add_field(ConfigField(
            name="max_retries",
            config_type=ConfigType.INTEGER,
            default=3,
            min_value=0,
            max_value=10,
            description="Maximum task retries"
        ))
        
        self.add_field(ConfigField(
            name="health_check_port",
            config_type=ConfigType.INTEGER,
            default=8080,
            min_value=1,
            max_value=65535,
            description="Health check port"
        ))


class BatchJobConfig(BaseConfig):
    """Konfiguration für Batch-Job-Programme."""
    
    def _define_fields(self):
        self.add_field(ConfigField(
            name="log_level",
            config_type=ConfigType.STRING,
            default="INFO",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            description="Logging level"
        ))
        
        self.add_field(ConfigField(
            name="batch_size",
            config_type=ConfigType.INTEGER,
            default=100,
            min_value=1,
            max_value=10000,
            description="Batch processing size"
        ))
        
        self.add_field(ConfigField(
            name="input_path",
            config_type=ConfigType.STRING,
            default="/app/input",
            description="Input directory path"
        ))
        
        self.add_field(ConfigField(
            name="output_path",
            config_type=ConfigType.STRING,
            default="/app/output",
            description="Output directory path"
        ))
        
        self.add_field(ConfigField(
            name="database_url",
            config_type=ConfigType.SECRET,
            required=False,
            description="Database connection URL"
        ))


class ConfigFactory:
    """Factory für Konfigurationsklassen."""
    
    _config_classes = {
        "web-api": WebAPIConfig,
        "cli": CLIConfig,
        "worker": WorkerConfig,
        "batch-job": BatchJobConfig
    }
    
    @classmethod
    def create_config(cls, program_type: str) -> BaseConfig:
        """
        Erstelle Konfiguration für Programm-Typ.
        
        Args:
            program_type: Typ des Programms (web-api, cli, worker, batch-job)
            
        Returns:
            Konfigurationsinstanz
            
        Raises:
            ConfigError: Bei unbekanntem Programm-Typ
        """
        config_class = cls._config_classes.get(program_type)
        if not config_class:
            raise ConfigError(f"Unknown program type: {program_type}")
        
        try:
            return config_class()
        except ConfigError:
            # Re-raise with context
            raise
        except Exception as e:
            raise ConfigError(f"Failed to create config for {program_type}: {e}")
    
    @classmethod
    def validate_config(cls, program_type: str) -> List[str]:
        """
        Validiere Konfiguration ohne zu laden.
        
        Args:
            program_type: Typ des Programms
            
        Returns:
            Liste von Validierungsfehlern
        """
        try:
            config_class = cls._config_classes.get(program_type)
            if not config_class:
                return [f"Unknown program type: {program_type}"]
            
            # Temporäre Instanz für Validierung
            temp_config = config_class.__new__(config_class)
            temp_config._fields = {}
            temp_config._values = {}
            temp_config._define_fields()
            
            return temp_config.validate()
        except Exception as e:
            return [f"Validation error: {e}"]


def get_config(program_type: str) -> BaseConfig:
    """
    Convenience-Funktion für Konfiguration.
    
    Args:
        program_type: Typ des Programms
        
    Returns:
        Konfigurationsinstanz
        
    Raises:
        ConfigError: Bei Konfigurationsfehlern
    """
    return ConfigFactory.create_config(program_type)


def validate_environment(program_type: str) -> bool:
    """
    Validiere Umgebung für Programm-Typ.
    
    Args:
        program_type: Typ des Programms
        
    Returns:
        True wenn valid, False sonst
    """
    errors = ConfigFactory.validate_config(program_type)
    
    if errors:
        logger.error(f"Environment validation failed for {program_type}:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    logger.info(f"Environment validation passed for {program_type}")
    return True


def early_config_check(program_type: str):
    """
    Frühe Konfigurationsprüfung mit erklärendem Abbruch.
    
    Args:
        program_type: Typ des Programms
        
    Raises:
        SystemExit: Bei Konfigurationsfehlern
    """
    try:
        config = get_config(program_type)
        logger.info(f"Configuration check passed for {program_type}")
        return config
    except ConfigError as e:
        logger.error(f"CONFIGURATION ERROR: {e}")
        logger.error("Please check your environment variables and try again.")
        logger.error("Required environment variables:")
        
        # Zeige erforderliche Variablen
        try:
            config_class = ConfigFactory._config_classes.get(program_type)
            if config_class:
                temp_config = config_class.__new__(config_class)
                temp_config._fields = {}
                temp_config._define_fields()
                
                for field_name, field in temp_config._fields.items():
                    if field.required:
                        logger.error(f"  - {field.env_var}: {field.description}")
        except:
            pass
        
        import sys
        sys.exit(1)


if __name__ == "__main__":
    # Demo
    print("⚙️ Runtime Config Demo:")
    
    # Test verschiedene Programm-Typen
    program_types = ["web-api", "cli", "worker", "batch-job"]
    
    for program_type in program_types:
        print(f"\\n--- {program_type.upper()} CONFIG ---")
        
        try:
            # Setze einige Test-Umgebungsvariablen
            if program_type == "web-api":
                os.environ["PORT"] = "3000"
                os.environ["DEBUG"] = "true"
            elif program_type == "worker":
                os.environ["WORKER_CONCURRENCY"] = "4"
            
            config = get_config(program_type)
            
            print("✓ Configuration loaded successfully")
            print("Configuration values:")
            for key, value in config.get_all().items():
                print(f"  {key}: {value}")
                
        except ConfigError as e:
            print(f"✗ Configuration failed: {e}")
        
        # Cleanup
        for key in list(os.environ.keys()):
            if key in ["PORT", "DEBUG", "WORKER_CONCURRENCY"]:
                del os.environ[key]
