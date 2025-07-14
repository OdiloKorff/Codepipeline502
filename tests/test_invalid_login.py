"""Invalid login scenario tests."""

import bcrypt
from fastapi.testclient import TestClient
from product.api.auth_router import router
from fastapi import FastAPI

def test_invalid_login_endpoint():
    class FakeSession:
        def query(self, model):
            class Q:
                def __init__(self, model): self.model = model
                def filter(self, *args, **kwargs): return self
                def one_or_none(self):  # Always return None to simulate user not found
                    return None
            return Q(model)

    def get_session_override():
        yield FakeSession()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[router.get_session] = get_session_override  # type: ignore
    client = TestClient(app)
    resp = client.post('/auth/login', json={'username': 'wrong@example.com', 'password': 'wrongpass'})
    assert resp.status_code == 401
    assert resp.json()['detail'] == 'invalid credentials'