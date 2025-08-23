"""
Zentraler Secret-Resolver für CodePipeline.

- Bezieht Secrets ausschließlich über definierte Quellen (ENV als MVP)
- Loggt niemals Secret-Werte
- Failt früh und klar, wenn ein Secret fehlt (für Secure-Apply-Pfade)
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class SecretValue:
    name: str
    source: str  # e.g. "env"


class SecretError(RuntimeError):
    pass


def get_secret(secret_name: str) -> SecretValue:
    """
    Liefert ein Secret über den zentralen Resolver.

    MVP: Nur ENV-Quelle erlaubt: CP_SECRET_<NAME>
    """
    if not secret_name or not secret_name.strip():
        raise SecretError("invalid secret name")

    env_key = f"CP_SECRET_{secret_name.upper()}"
    value = os.getenv(env_key)
    if value is None or value == "":
        raise SecretError(f"missing secret: {secret_name} (ENV {env_key})")

    # Niemals den Wert zurückgeben/loggen – nur Metadaten
    return SecretValue(name=secret_name, source="env")


