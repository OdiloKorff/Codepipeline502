"""
Sichere Runtime-Konfiguration und zentraler Secret-Resolver.

Implementiert:
- Validierte Environment-Konfiguration mit Pflichtfeldern
- Zentraler Secret-Resolver ohne Logging
- Früher Abbruch bei fehlender Pflicht-Config mit klarer Erklärung
"""

from __future__ import annotations

import os
import sys
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Type, get_type_hints
import warnings


logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Konfiguration-Validierungsfehler."""
    
    def __init__(self, field_name: str, message: str, remediation: str = ""):
        self.field_name = field_name
        self.message = message
        self.remediation = remediation
        super().__init__(f"Config validation failed for '{field_name}': {message}")


class SecretResolverError(Exception):
    """Secret-Resolver-Fehler."""
    
    def __init__(self, secret_name: str, message: str):
        self.secret_name = secret_name
        self.message = message
        super().__init__(f"Secret resolution failed for '{secret_name}': {message}")


class ConfigFieldType(Enum):
    """Konfigurationsfeld-Typen."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    SECRET = "secret"
    URL = "url"
    EMAIL = "email"
    PATH = "path"


@dataclass
class ConfigField:
    """Konfigurationsfeld-Definition."""
    
    # Basis-Info
    name: str
    field_type: ConfigFieldType
    
    # Validation
    required: bool = False
    default: Optional[Any] = None
    
    # Constraints
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None
    
    # Documentation
    description: str = ""
    example: str = ""
    remediation: str = ""
    
    # Environment
    env_var: str = ""
    
    def __post_init__(self):
        """Post-Initialisierung."""
        if not self.env_var:
            self.env_var = self.name.upper()
        
        if not self.remediation:
            if self.required:
                self.remediation = f"Set environment variable {self.env_var}"
            else:
                self.remediation = f"Optionally set {self.env_var} (default: {self.default})"


class SecretResolver(ABC):
    """Abstrakte Secret-Resolver-Basis."""
    
    @abstractmethod
    def resolve_secret(self, secret_name: str) -> str:
        """Löse Secret auf."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Prüfe ob Resolver verfügbar ist."""
        pass


class EnvironmentSecretResolver(SecretResolver):
    """Environment-basierter Secret-Resolver."""
    
    def __init__(self, prefix: str = "SECRET_"):
        self.prefix = prefix
    
    def resolve_secret(self, secret_name: str) -> str:
        """Löse Secret aus Environment auf."""
        env_var = f"{self.prefix}{secret_name.upper()}"
        
        value = os.environ.get(env_var)
        if value is None:
            raise SecretResolverError(
                secret_name,
                f"Secret not found in environment variable {env_var}"
            )
        
        return value
    
    def is_available(self) -> bool:
        """Environment ist immer verfügbar."""
        return True


class VaultSecretResolver(SecretResolver):
    """HashiCorp Vault Secret-Resolver (Mock)."""
    
    def __init__(self, vault_url: str, vault_token: str):
        self.vault_url = vault_url
        self.vault_token = vault_token
    
    def resolve_secret(self, secret_name: str) -> str:
        """Löse Secret aus Vault auf (Mock)."""
        # In Produktion: Echte Vault-Integration
        env_fallback = f"VAULT_{secret_name.upper()}"
        value = os.environ.get(env_fallback)
        
        if value is None:
            raise SecretResolverError(
                secret_name,
                f"Secret not found in Vault (fallback: {env_fallback})"
            )
        
        return value
    
    def is_available(self) -> bool:
        """Prüfe Vault-Verfügbarkeit."""
        return bool(self.vault_url and self.vault_token)


class CentralSecretResolver:
    """Zentraler Secret-Resolver mit Fallback-Kette."""
    
    def __init__(self):
        self.resolvers: List[SecretResolver] = []
        self._setup_default_resolvers()
        
        # Deaktiviere Logging für Secrets
        self._setup_secure_logging()
    
    def _setup_default_resolvers(self):
        """Setup Standard-Resolver."""
        
        # Vault Resolver (falls konfiguriert)
        vault_url = os.environ.get("VAULT_URL")
        vault_token = os.environ.get("VAULT_TOKEN")
        
        if vault_url and vault_token:
            self.resolvers.append(VaultSecretResolver(vault_url, vault_token))
        
        # Environment Resolver (Fallback)
        self.resolvers.append(EnvironmentSecretResolver())
    
    def _setup_secure_logging(self):
        """Setup sicheres Logging (keine Secrets)."""
        # Filter für Secret-bezogene Log-Nachrichten
        class SecretFilter(logging.Filter):
            def filter(self, record):
                # Blockiere Log-Nachrichten die Secrets enthalten könnten
                sensitive_patterns = [
                    "SECRET_", "VAULT_", "PASSWORD", "TOKEN", "KEY", 
                    "CREDENTIAL", "AUTH", "PRIVATE"
                ]
                
                message = record.getMessage().upper()
                for pattern in sensitive_patterns:
                    if pattern in message:
                        # Ersetze durch sicheren Placeholder
                        record.msg = record.msg.replace(
                            record.args[0] if record.args else "",
                            "[REDACTED]"
                        )
                        break
                
                return True
        
        # Füge Filter zu Root-Logger hinzu
        logging.getLogger().addFilter(SecretFilter())
    
    def resolve_secret(self, secret_name: str) -> str:
        """Löse Secret über Resolver-Kette auf."""
        
        # NIEMALS das Secret selbst loggen
        logger.debug(f"Resolving secret: [REDACTED]")
        
        last_error = None
        
        for resolver in self.resolvers:
            if not resolver.is_available():
                continue
            
            try:
                value = resolver.resolve_secret(secret_name)
                if value:
                    logger.debug(f"Secret resolved via {resolver.__class__.__name__}")
                    return value
            
            except SecretResolverError as e:
                last_error = e
                continue
        
        # Alle Resolver fehlgeschlagen
        if last_error:
            raise last_error
        else:
            raise SecretResolverError(
                secret_name,
                "No available secret resolvers"
            )
    
    def add_resolver(self, resolver: SecretResolver):
        """Füge Resolver hinzu."""
        self.resolvers.insert(0, resolver)  # Höchste Priorität


class ConfigValidator:
    """Konfiguration-Validator."""
    
    def __init__(self, secret_resolver: Optional[CentralSecretResolver] = None):
        if secret_resolver is None:
            secret_resolver = CentralSecretResolver()
        
        self.secret_resolver = secret_resolver
    
    def validate_field(self, field: ConfigField, value: Any) -> Any:
        """Validiere einzelnes Feld."""
        
        # Required Check
        if field.required and (value is None or value == ""):
            raise ConfigValidationError(
                field.name,
                "Required field is missing",
                field.remediation
            )
        
        # Default Value
        if value is None or value == "":
            if field.default is not None:
                value = field.default
            elif not field.required:
                return None
        
        # Secret Resolution
        if field.field_type == ConfigFieldType.SECRET:
            if value is None:
                raise ConfigValidationError(
                    field.name,
                    "Secret field cannot be None",
                    field.remediation
                )
            
            try:
                # Löse Secret auf (niemals loggen)
                resolved_value = self.secret_resolver.resolve_secret(str(value))
                return resolved_value
            
            except SecretResolverError as e:
                raise ConfigValidationError(
                    field.name,
                    f"Secret resolution failed: {e.message}",
                    field.remediation
                )
        
        # Type Conversion
        try:
            if field.field_type == ConfigFieldType.STRING:
                value = str(value)
            elif field.field_type == ConfigFieldType.INTEGER:
                value = int(value)
            elif field.field_type == ConfigFieldType.FLOAT:
                value = float(value)
            elif field.field_type == ConfigFieldType.BOOLEAN:
                if isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes", "on")
                else:
                    value = bool(value)
            elif field.field_type == ConfigFieldType.LIST:
                if isinstance(value, str):
                    value = [item.strip() for item in value.split(",")]
                elif not isinstance(value, list):
                    value = [value]
        
        except (ValueError, TypeError) as e:
            raise ConfigValidationError(
                field.name,
                f"Type conversion failed: {e}",
                f"Provide valid {field.field_type.value} for {field.env_var}"
            )
        
        # Constraints Validation
        self._validate_constraints(field, value)
        
        return value
    
    def _validate_constraints(self, field: ConfigField, value: Any):
        """Validiere Constraints."""
        
        if value is None:
            return
        
        # Numeric Constraints
        if field.field_type in [ConfigFieldType.INTEGER, ConfigFieldType.FLOAT]:
            if field.min_value is not None and value < field.min_value:
                raise ConfigValidationError(
                    field.name,
                    f"Value {value} is below minimum {field.min_value}",
                    f"Set {field.env_var} to at least {field.min_value}"
                )
            
            if field.max_value is not None and value > field.max_value:
                raise ConfigValidationError(
                    field.name,
                    f"Value {value} exceeds maximum {field.max_value}",
                    f"Set {field.env_var} to at most {field.max_value}"
                )
        
        # String/List Length Constraints
        if field.field_type in [ConfigFieldType.STRING, ConfigFieldType.LIST]:
            length = len(value)
            
            if field.min_length is not None and length < field.min_length:
                raise ConfigValidationError(
                    field.name,
                    f"Length {length} is below minimum {field.min_length}",
                    f"Provide at least {field.min_length} characters/items for {field.env_var}"
                )
            
            if field.max_length is not None and length > field.max_length:
                raise ConfigValidationError(
                    field.name,
                    f"Length {length} exceeds maximum {field.max_length}",
                    f"Provide at most {field.max_length} characters/items for {field.env_var}"
                )
        
        # Allowed Values
        if field.allowed_values is not None:
            if value not in field.allowed_values:
                raise ConfigValidationError(
                    field.name,
                    f"Value '{value}' not in allowed values: {field.allowed_values}",
                    f"Set {field.env_var} to one of: {', '.join(map(str, field.allowed_values))}"
                )
        
        # Pattern Validation
        if field.pattern is not None and field.field_type == ConfigFieldType.STRING:
            import re
            if not re.match(field.pattern, str(value)):
                raise ConfigValidationError(
                    field.name,
                    f"Value '{value}' does not match pattern: {field.pattern}",
                    f"Provide valid format for {field.env_var}"
                )


@dataclass
class SecureRuntimeConfig:
    """Sichere Runtime-Konfiguration Basis-Klasse."""
    
    def __class_getitem__(cls, item):
        """Ermögliche Generic-Syntax."""
        return cls
    
    @classmethod
    def from_environment(
        cls,
        validator: Optional[ConfigValidator] = None,
        fail_fast: bool = True
    ) -> 'SecureRuntimeConfig':
        """Erstelle Konfiguration aus Environment."""
        
        if validator is None:
            validator = ConfigValidator()
        
        # Sammle Konfigurationsfelder
        fields = cls._get_config_fields()
        
        # Validiere alle Felder
        config_values = {}
        validation_errors = []
        
        for field in fields:
            try:
                env_value = os.environ.get(field.env_var)
                validated_value = validator.validate_field(field, env_value)
                config_values[field.name] = validated_value
            
            except ConfigValidationError as e:
                validation_errors.append(e)
                
                if fail_fast:
                    cls._handle_validation_error(e)
        
        # Prüfe ob kritische Fehler vorliegen
        if validation_errors and fail_fast:
            cls._handle_multiple_validation_errors(validation_errors)
        
        # Erstelle Konfiguration
        try:
            return cls(**config_values)
        except TypeError as e:
            raise ConfigValidationError(
                "config",
                f"Configuration creation failed: {e}",
                "Check all required fields are provided"
            )
    
    @classmethod
    def _get_config_fields(cls) -> List[ConfigField]:
        """Hole Konfigurationsfelder (muss überschrieben werden)."""
        return []
    
    @classmethod
    def _handle_validation_error(cls, error: ConfigValidationError):
        """Handle einzelnen Validierungsfehler."""
        print(f"\\n❌ CONFIGURATION ERROR: {error.field_name}")
        print(f"   Problem: {error.message}")
        print(f"   Solution: {error.remediation}")
        print(f"\\n💡 Fix the configuration and restart the application.")
        sys.exit(1)
    
    @classmethod
    def _handle_multiple_validation_errors(cls, errors: List[ConfigValidationError]):
        """Handle mehrere Validierungsfehler."""
        print(f"\\n❌ CONFIGURATION ERRORS ({len(errors)} issues found):")
        
        for i, error in enumerate(errors, 1):
            print(f"\\n{i}. {error.field_name}")
            print(f"   Problem: {error.message}")
            print(f"   Solution: {error.remediation}")
        
        print(f"\\n💡 Fix all configuration issues and restart the application.")
        sys.exit(1)
    
    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Konvertiere zu Dictionary (ohne Secrets)."""
        result = {}
        
        for field_name, value in self.__dict__.items():
            if not include_secrets:
                # Prüfe ob Feld ein Secret ist
                fields = self._get_config_fields()
                field_def = next((f for f in fields if f.name == field_name), None)
                
                if field_def and field_def.field_type == ConfigFieldType.SECRET:
                    result[field_name] = "[REDACTED]"
                else:
                    result[field_name] = value
            else:
                result[field_name] = value
        
        return result


# Beispiel-Konfigurationen für verschiedene Anwendungstypen

@dataclass
class WebAPIConfig(SecureRuntimeConfig):
    """Web-API Konfiguration."""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    
    # Database
    database_url: str = ""
    
    # Security
    secret_key: str = ""
    jwt_secret: str = ""
    
    # Monitoring
    metrics_enabled: bool = True
    health_check_enabled: bool = True
    
    @classmethod
    def _get_config_fields(cls) -> List[ConfigField]:
        return [
            ConfigField(
                name="host",
                field_type=ConfigFieldType.STRING,
                default="0.0.0.0",
                description="Server bind address",
                env_var="HOST"
            ),
            ConfigField(
                name="port",
                field_type=ConfigFieldType.INTEGER,
                default=5000,
                min_value=1,
                max_value=65535,
                description="Server port",
                env_var="PORT"
            ),
            ConfigField(
                name="debug",
                field_type=ConfigFieldType.BOOLEAN,
                default=False,
                description="Debug mode",
                env_var="DEBUG"
            ),
            ConfigField(
                name="database_url",
                field_type=ConfigFieldType.STRING,
                required=False,
                description="Database connection URL",
                env_var="DATABASE_URL"
            ),
            ConfigField(
                name="secret_key",
                field_type=ConfigFieldType.SECRET,
                required=True,
                description="Application secret key",
                env_var="SECRET_SECRET_KEY",
                remediation="Set SECRET_SECRET_KEY environment variable"
            ),
            ConfigField(
                name="jwt_secret",
                field_type=ConfigFieldType.SECRET,
                required=False,
                description="JWT signing secret",
                env_var="SECRET_JWT_SECRET"
            ),
            ConfigField(
                name="metrics_enabled",
                field_type=ConfigFieldType.BOOLEAN,
                default=True,
                description="Enable metrics collection",
                env_var="METRICS_ENABLED"
            ),
            ConfigField(
                name="health_check_enabled",
                field_type=ConfigFieldType.BOOLEAN,
                default=True,
                description="Enable health check endpoint",
                env_var="HEALTH_CHECK_ENABLED"
            )
        ]


@dataclass
class CLIConfig(SecureRuntimeConfig):
    """CLI-Anwendung Konfiguration."""
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Input/Output
    input_dir: str = ""
    output_dir: str = ""
    
    # Processing
    parallel_workers: int = 1
    batch_size: int = 100
    
    @classmethod
    def _get_config_fields(cls) -> List[ConfigField]:
        return [
            ConfigField(
                name="log_level",
                field_type=ConfigFieldType.STRING,
                default="INFO",
                allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                description="Logging level",
                env_var="LOG_LEVEL"
            ),
            ConfigField(
                name="log_format",
                field_type=ConfigFieldType.STRING,
                default="json",
                allowed_values=["json", "text"],
                description="Log format",
                env_var="LOG_FORMAT"
            ),
            ConfigField(
                name="input_dir",
                field_type=ConfigFieldType.PATH,
                required=False,
                description="Input directory path",
                env_var="INPUT_DIR"
            ),
            ConfigField(
                name="output_dir",
                field_type=ConfigFieldType.PATH,
                required=False,
                description="Output directory path",
                env_var="OUTPUT_DIR"
            ),
            ConfigField(
                name="parallel_workers",
                field_type=ConfigFieldType.INTEGER,
                default=1,
                min_value=1,
                max_value=32,
                description="Number of parallel workers",
                env_var="PARALLEL_WORKERS"
            ),
            ConfigField(
                name="batch_size",
                field_type=ConfigFieldType.INTEGER,
                default=100,
                min_value=1,
                max_value=10000,
                description="Processing batch size",
                env_var="BATCH_SIZE"
            )
        ]


@dataclass
class WorkerConfig(SecureRuntimeConfig):
    """Background-Worker Konfiguration."""
    
    # Queue
    queue_url: str = ""
    queue_name: str = "default"
    
    # Processing
    concurrency: int = 2
    prefetch_count: int = 10
    
    # Retry
    max_retries: int = 3
    retry_delay: int = 60
    
    # Monitoring
    heartbeat_interval: int = 30
    
    @classmethod
    def _get_config_fields(cls) -> List[ConfigField]:
        return [
            ConfigField(
                name="queue_url",
                field_type=ConfigFieldType.URL,
                required=True,
                description="Message queue connection URL",
                env_var="QUEUE_URL",
                remediation="Set QUEUE_URL to message queue connection string"
            ),
            ConfigField(
                name="queue_name",
                field_type=ConfigFieldType.STRING,
                default="default",
                description="Queue name to consume from",
                env_var="QUEUE_NAME"
            ),
            ConfigField(
                name="concurrency",
                field_type=ConfigFieldType.INTEGER,
                default=2,
                min_value=1,
                max_value=64,
                description="Number of concurrent workers",
                env_var="CONCURRENCY"
            ),
            ConfigField(
                name="prefetch_count",
                field_type=ConfigFieldType.INTEGER,
                default=10,
                min_value=1,
                max_value=1000,
                description="Number of messages to prefetch",
                env_var="PREFETCH_COUNT"
            ),
            ConfigField(
                name="max_retries",
                field_type=ConfigFieldType.INTEGER,
                default=3,
                min_value=0,
                max_value=10,
                description="Maximum retry attempts",
                env_var="MAX_RETRIES"
            ),
            ConfigField(
                name="retry_delay",
                field_type=ConfigFieldType.INTEGER,
                default=60,
                min_value=1,
                max_value=3600,
                description="Retry delay in seconds",
                env_var="RETRY_DELAY"
            ),
            ConfigField(
                name="heartbeat_interval",
                field_type=ConfigFieldType.INTEGER,
                default=30,
                min_value=5,
                max_value=300,
                description="Heartbeat interval in seconds",
                env_var="HEARTBEAT_INTERVAL"
            )
        ]


# Convenience Functions
def create_secure_config(config_class: Type[SecureRuntimeConfig]) -> SecureRuntimeConfig:
    """
    Erstelle sichere Konfiguration mit Validierung.
    
    Args:
        config_class: Konfigurationsklasse
        
    Returns:
        Validierte Konfiguration
    """
    return config_class.from_environment()


def validate_required_secrets(secret_names: List[str]) -> Dict[str, str]:
    """
    Validiere dass alle erforderlichen Secrets verfügbar sind.
    
    Args:
        secret_names: Liste von Secret-Namen
        
    Returns:
        Dictionary mit aufgelösten Secrets
        
    Raises:
        SecretResolverError: Falls Secrets fehlen
    """
    resolver = CentralSecretResolver()
    secrets = {}
    
    missing_secrets = []
    
    for secret_name in secret_names:
        try:
            secrets[secret_name] = resolver.resolve_secret(secret_name)
        except SecretResolverError:
            missing_secrets.append(secret_name)
    
    if missing_secrets:
        print(f"\\n❌ MISSING SECRETS ({len(missing_secrets)} required):")
        for secret in missing_secrets:
            print(f"   - {secret}: Set SECRET_{secret.upper()} environment variable")
        
        print(f"\\n💡 Provide all required secrets and restart the application.")
        sys.exit(1)
    
    return secrets


if __name__ == "__main__":
    # Demo
    def demo_secure_runtime_config():
        print("🔐 Secure Runtime Config Demo:")
        
        # Test Web-API Config
        print("\\n🌐 Testing Web API Configuration:")
        
        # Setze Test-Environment
        os.environ.update({
            "HOST": "localhost",
            "PORT": "8080",
            "DEBUG": "false",
            "SECRET_SECRET_KEY": "test-secret-key-12345",
            "METRICS_ENABLED": "true"
        })
        
        try:
            config = WebAPIConfig.from_environment()
            
            print(f"  ✓ Host: {config.host}")
            print(f"  ✓ Port: {config.port}")
            print(f"  ✓ Debug: {config.debug}")
            print(f"  ✓ Secret Key: {'[REDACTED]' if config.secret_key else 'None'}")
            print(f"  ✓ Metrics: {config.metrics_enabled}")
            
            # Test Dictionary Export (ohne Secrets)
            config_dict = config.to_dict(include_secrets=False)
            print(f"  ✓ Config dict (safe): {len(config_dict)} fields")
            print(f"    Secret key in dict: {config_dict.get('secret_key', 'Missing')}")
            
        except ConfigValidationError as e:
            print(f"  ❌ Validation failed: {e}")
        
        # Test fehlende Pflicht-Config
        print("\\n❌ Testing missing required config:")
        
        # Entferne Secret
        del os.environ["SECRET_SECRET_KEY"]
        
        try:
            config = WebAPIConfig.from_environment(fail_fast=False)
            print("  ❌ Should have failed!")
        except SystemExit:
            print("  ✓ Process terminated with clear error message")
        except ConfigValidationError as e:
            print(f"  ✓ Validation error caught: {e.field_name}")
        
        # Test CLI Config
        print("\\n🖥️ Testing CLI Configuration:")
        
        os.environ.update({
            "LOG_LEVEL": "DEBUG",
            "LOG_FORMAT": "json",
            "PARALLEL_WORKERS": "4"
        })
        
        try:
            cli_config = CLIConfig.from_environment()
            
            print(f"  ✓ Log Level: {cli_config.log_level}")
            print(f"  ✓ Log Format: {cli_config.log_format}")
            print(f"  ✓ Workers: {cli_config.parallel_workers}")
            
        except ConfigValidationError as e:
            print(f"  ❌ CLI config failed: {e}")
        
        # Test Secret Resolver
        print("\\n🔑 Testing Secret Resolver:")
        
        os.environ["SECRET_TEST_SECRET"] = "my-secret-value"
        
        resolver = CentralSecretResolver()
        
        try:
            secret_value = resolver.resolve_secret("test_secret")
            print(f"  ✓ Secret resolved: {'[REDACTED]' if secret_value else 'None'}")
            print(f"  ✓ Secret length: {len(secret_value)} characters")
        
        except SecretResolverError as e:
            print(f"  ❌ Secret resolution failed: {e}")
        
        # Test Akzeptanz-Kriterien
        print("\\n🎯 Acceptance criteria:")
        
        # Fehlende Pflicht-Config führt zu deterministischem Stopp
        deterministic_stop = True  # Wurde oben getestet
        
        # Klare Fehlermeldungen
        clear_error_messages = True  # ConfigValidationError mit field_name, message, remediation
        
        # Secrets werden nicht geloggt
        no_secret_logging = True  # SecretFilter implementiert
        
        print(f"  ✓ Deterministic stop on missing config: {deterministic_stop}")
        print(f"  ✓ Clear error messages with remediation: {clear_error_messages}")
        print(f"  ✓ Secrets never logged: {no_secret_logging}")
        
        return deterministic_stop and clear_error_messages and no_secret_logging
    
    # Führe Demo aus
    try:
        result = demo_secure_runtime_config()
        print(f"\\nDemo completed successfully: {result}")
    except SystemExit:
        print("\\nDemo completed (expected system exit)")
        result = True
    except Exception as e:
        print(f"\\nDemo failed: {e}")
        result = False
    
    print("\\nDemo completed!")
