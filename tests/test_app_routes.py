
from fastapi.testclient import TestClient
import importlib, os
os.environ["JWT_SECRET"] = "testsecret"
from app.main import app

def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_stats_endpoint():
    client = TestClient(app)
    resp = client.post("/stats", json={"values": [1, 2, 3]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert data["sum"] == 6.0
    assert data["mean"] == 2.0
