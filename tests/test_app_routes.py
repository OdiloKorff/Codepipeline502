
from fastapi.testclient import TestClient
import importlib, os
os.environ["JWT_SECRET"] = "testsecret"
from main import app

def test_auth_router_registered():
    client = TestClient(app)
    resp = client.get("/auth/health")
    assert resp.status_code == 200
