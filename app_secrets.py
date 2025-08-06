"""
Secrets management for CodePipeline.
"""

import os
import pathlib

import hvac

from codepipeline.logging_config import get_logger

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

def ensure_env(var_name:str)->None:
    if os.getenv(var_name):
        return
    path,key=_DEFAULT_SECRET_MAP.get(var_name, (None, None))
    if not path:
        _log.warning("No default Vault path for %s", var_name)
        return
    try:
        os.environ[var_name]=get_secret(path,key)
        _log.info("Fetched secret %s from Vault", var_name)
    except Exception as exc:
        _log.error("Failed to fetch secret %s: %s", var_name, exc)
