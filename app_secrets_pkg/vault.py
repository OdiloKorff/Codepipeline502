import os
from typing import Any

from hvac import Client


class VaultClient:
    def __init__(self) -> None:
        vault_addr = os.environ["VAULT_ADDR"]
        role_id = os.environ["VAULT_ROLE_ID"]
        secret_id = os.environ["VAULT_SECRET_ID"]
        self.client: Client = Client(url=vault_addr)
        self.client.auth_approle(role_id, secret_id)

    def get_secret(self, path: str, field: str | None = None) -> Any:
        secret = self.client.secrets.kv.v2.read_secret_version(path=path)
        data: dict[str, Any] = secret['data']['data']
        return data if field is None else data.get(field)
