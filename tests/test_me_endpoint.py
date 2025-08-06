
import importlib
import os

import bcrypt

os.environ["JWT_SECRET"] = "testsecret"
import product.security.token as token_mod

importlib.reload(token_mod)
from datetime import timedelta

from fastapi.testclient import TestClient
from product.api.auth_router import create_access_token, router


def test_me_endpoint(monkeypatch):
    class FakeUser:
        id = 1
        email = "user@example.com"
        hashed_password = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()

    class FakeSession:
        def query(self, model):
            class Q:
                def filter(self, *args, **kwargs): return self
                def one_or_none(self):
                    return FakeUser()
            return Q()

    def get_session_override():
        yield FakeSession()

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[router.get_session] = get_session_override  # type: ignore
    app.dependency_overrides[router.get_current_user] = lambda token=..., session=...: FakeUser()  # type: ignore

    client = TestClient(app)
    token = create_access_token({"sub": "user@example.com"}, timedelta(minutes=5))
    cookies = {"token": token}
    resp = client.get("/auth/me", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"
