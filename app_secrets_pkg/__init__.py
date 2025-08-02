
"""Vault secrets helper.

Provides get_secret(path, key) that fetches secrets from HashiCorp Vault using
token-based or OIDC/JWT–based auth. Falls back to env‑vars during tests.

This implementation is intentionally minimal; it is safe for import at
runtime even when `hvac` is not installed by falling back to a stub module
that tests can monkey‑patch.
"""

from __future__ import annotations

import os
import types
from typing import Any, Dict

# -----------------------------------------------------------------------------
# Optional import of the heavy hvac dependency.
# The tests monkey‑patch ``hvac.Client``, so we must expose an attribute called
# ``hvac`` on this module even when the actual package is unavailable.
# -----------------------------------------------------------------------------
try:
    import hvac  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – runtime envs without hvac
    hvac = types.ModuleType("hvac")  # type: ignore
    class _DummyClient:  # pylint: disable=too-few-public-methods
        """Very small stub so type‑checkers and tests are happy."""
        def __init__(self, *_, **__):  # noqa: D401,E501
            pass
    hvac.Client = _DummyClient  # type: ignore[attr-defined]

__all__ = ["get_secret"]

def _build_client() -> "hvac.Client":  # type: ignore[name-defined]
    """Instantiate a Vault client authenticated via token or OIDC.

    Order of precedence:

    1. A pre‑formatted OIDC JWT in ``VAULT_JWT`` (recommended with
       GitHub‑Actions OIDC federation).
    2. A static token in ``VAULT_TOKEN`` (legacy / local development).

    Raises
    ------
    EnvironmentError
        If *no* supported auth mechanism could be found.
    """
    # Modern: OIDC with GitHub‑Actions / cloud workload identities
    if jwt := os.getenv("VAULT_JWT"):
        client = hvac.Client()  # type: ignore[call-arg]
        client.auth.jwt.login(role="github-actions", jwt=jwt)  # type: ignore[attr-defined]
        return client  # pragma: no cover

    # Fallback: static token, mainly for local dev & tests
    if token := os.getenv("VAULT_TOKEN"):
        return hvac.Client(token=token)  # type: ignore[call-arg]

    raise EnvironmentError("Neither VAULT_JWT nor VAULT_TOKEN is set")

def get_secret(path: str, key: str) -> Any:  # noqa: D401
    """Return the secret value stored at *path*/*key* in Vault.

    Parameters
    ----------
    path:
        KV v2 mount path + secret path, e.g. ``"kv/data/project/config"``.
    key:
        Desired key in the secret's data map.

    Examples
    --------
    >>> os.environ["VAULT_TOKEN"] = "dev-token"
    >>> get_secret("kv/data/project", "DATABASE_URL")
    'postgresql://…'
    """
    client = _build_client()
    # Vault KV v2 API ‑ single version read
    secret_resp: Dict[str, Any] = client.secrets.kv.v2.read_secret_version(path=path)  # type: ignore[attr-defined]
    return secret_resp["data"]["data"][key]