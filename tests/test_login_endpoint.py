import os

os.environ["JWT_SECRET"] = "testsecret"

import bcrypt
from fastapi.testclient import TestClient
from product.api.auth_router import router


def test_login_endpoint(monkeypatch):
    # Setup fake user
    class FakeSession:
        def query(self, model):
            class Q:
                def __init__(self, model): self.model = model
                def filter(self, *args, **kwargs): return self
                def one_or_none(self):
                    class UserObj:
                        email = "user@example.com"
                        hashed_password = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
                    return UserObj()
            return Q(model)
    def get_session_override():
        yield FakeSession()
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[router.get_session] = get_session_override  # type: ignore

    client = TestClient(app)
    resp = client.post("/auth/login", json={"username": "user@example.com", "password": "secret"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
