
import os
from datetime import UTC, datetime, timedelta

import bcrypt
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

os.environ["JWT_SECRET"] = "testsecret"

from product.api.auth_router import router


class _FakeUser:
    id = 1
    email = "user@example.com"
    hashed_password = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()

class _Token:
    def __init__(self, expired=False):
        self.token = "valid" if not expired else "expired"
        self.user = _FakeUser()
        delta = -1 if expired else 5
        self.expires_at = datetime.now(UTC) + timedelta(minutes=delta)

class _Session:
    def __init__(self, token_obj):
        self._token_obj = token_obj
    def query(self, model):
        class Q:
            def __init__(self, token_obj): self.token_obj = token_obj
            def filter(self, *args, **kwargs): return self
            def one_or_none(self):
                if model.__name__ == "User":
                    return _FakeUser()
                return self.token_obj
        return Q(self._token_obj)

@pytest.fixture
def make_app():
    def _factory(token_obj):
        app = FastAPI()
        app.include_router(router)
        def _session():
            yield _Session(token_obj)
        app.dependency_overrides[router.get_session] = _session  # type: ignore
        return app
    return _factory

@pytest.mark.asyncio
async def test_login_success(make_app):
    app = make_app(_Token())
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/auth/login", json={"username": "user@example.com", "password": "secret"})
        assert resp.status_code == 200

@pytest.mark.asyncio
async def test_login_wrong_password(make_app):
    app = make_app(_Token())
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/auth/login", json={"username": "user@example.com", "password": "bad"})
        assert resp.status_code == 401

@pytest.mark.asyncio
async def test_refresh_valid(make_app):
    token_obj = _Token()
    app = make_app(token_obj)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/auth/refresh", cookies={"refresh_token": token_obj.token})
        assert resp.status_code == 200

@pytest.mark.asyncio
async def test_refresh_expired(make_app):
    token_obj = _Token(expired=True)
    app = make_app(token_obj)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/auth/refresh", cookies={"refresh_token": token_obj.token})
        assert resp.status_code == 401
