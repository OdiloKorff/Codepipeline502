import os

os.environ["JWT_SECRET"] = "testsecret"

from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi.testclient import TestClient
from product.api.auth_router import router


def test_refresh_endpoint(monkeypatch):
    class FakeUser:
        email = "user@example.com"
        hashed_password = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()

    class FakeRefresh:
        token = "refresh123"
        user = FakeUser()
        expires_at = datetime.now(UTC) + timedelta(minutes=5)

    class FakeSession:
        def query(self, model):
            class Q:
                def filter(self, *args, **kwargs):
                    return self
                def one_or_none(self):
                    return FakeRefresh if model.__name__ == "RefreshToken" else FakeUser
            return Q()

    def get_session_override():
        yield FakeSession()

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[router.get_session] = get_session_override  # type: ignore

    client = TestClient(app)
    cookies = {"refresh_token": "refresh123"}
    resp = client.post("/auth/refresh", cookies=cookies)
    assert resp.status_code == 200
    assert "access_token" in resp.json()
