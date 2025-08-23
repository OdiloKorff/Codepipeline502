"""
Secrets management for CodePipeline.
"""

import os
import pathlib

import hvac

from logging_config import get_logger

_log = get_logger(__name__)

VAULT_ADDR = os.getenv("VAULT_ADDR", "https://vault.yourcorp.local")
VAULT_ROLE = os.getenv("VAULT_ROLE", "codepipeline")
GITHUB_JWT_PATH = os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN")  # GitHub OIDC env
# or generic OIDC token at path indicated by VAULT_OIDC_JWT_FILE
USER_JWT_FILE = os.getenv("VAULT_OIDC_JWT_FILE")

_client: hvac.Client | None = None

def _get_client() -> hvac.Client:
    global _client
    if _client:  # pragma: no cover
        return _client
    _client = hvac.Client(url=VAULT_ADDR)
    if os.getenv("VAULT_TOKEN"):
        _client.token = os.getenv("VAULT_TOKEN")
        return _client

    # OIDC login (CI)
    jwt = None
    if USER_JWT_FILE and pathlib.Path(USER_JWT_FILE).exists():
        jwt = pathlib.Path(USER_JWT_FILE).read_text().strip()
    elif GITHUB_JWT_PATH:
        jwt = GITHUB_JWT_PATH  # already contains token in GH Actions

    if jwt:
        resp = _client.auth.jwt.login(role=VAULT_ROLE, jwt=jwt)
        _client.token = resp["auth"]["client_token"]
        _log.info("Authenticated to Vault via OIDC role %s", VAULT_ROLE)
    else:
        raise OSError("No VAULT_TOKEN or OIDC JWT available for Vault login")
    return _client

# ---------------------------
def get_secret(path: str, key: str) -> str:
    client=_get_client()
    secret=client.secrets.kv.v2.read_secret_version(path=path)
    return secret["data"]["data"][key]

_DEFAULT_SECRET_MAP={
    "OPENAI_API_KEY": ("openai","OPENAI_API_KEY"),
    "ANTHROPIC_API_KEY": ("anthropic","ANTHROPIC_API_KEY"),
}

class SecretNotAvailableError(Exception):
    """Raised when a required secret is not available from environment or Vault."""
    pass


def ensure_env(var_name: str) -> None:
    """
    Ensure that the specified environment variable is available.
    
    First checks if the variable is already set in the environment.
    If not, attempts to fetch it from Vault using the default secret map.
    
    Args:
        var_name: Name of the environment variable to ensure
        
    Raises:
        SecretNotAvailableError: If the secret cannot be obtained from 
                                environment or Vault
    """
    # Check if already set in environment
    if os.getenv(var_name):
        _log.debug("Secret %s already available in environment", var_name)
        return
    
    # Try to fetch from Vault
    path, key = _DEFAULT_SECRET_MAP.get(var_name, (None, None))
    if not path:
        raise SecretNotAvailableError(
            f"Secret '{var_name}' not found in environment and no Vault path configured. "
            f"Available Vault paths: {list(_DEFAULT_SECRET_MAP.keys())}"
        )
    
    try:
        secret_value = get_secret(path, key)
        os.environ[var_name] = secret_value
        _log.info("Successfully fetched secret %s from Vault path %s", var_name, path)
    except Exception as exc:
        raise SecretNotAvailableError(
            f"Failed to fetch secret '{var_name}' from Vault path '{path}': {exc}"
        ) from exc


def validate_required_secrets(*var_names: str) -> None:
    """
    Validate that all required secrets are available.
    
    This should be called early in the application lifecycle to fail fast
    if required secrets are not available.
    
    Args:
        *var_names: Names of environment variables to validate
        
    Raises:
        SecretNotAvailableError: If any secret is not available
    """
    missing_secrets = []
    
    for var_name in var_names:
        try:
            ensure_env(var_name)
        except SecretNotAvailableError as e:
            missing_secrets.append(f"{var_name}: {e}")
    
    if missing_secrets:
        raise SecretNotAvailableError(
            "Required secrets not available:\n" + "\n".join(f"  - {s}" for s in missing_secrets)
        )
