from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_stats_normal():
    """Test /stats with normal values"""
    response = client.post("/stats", json={"values": [1, 2, 3]})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert data["sum"] == 6.0
    assert data["mean"] == 2.0

def test_stats_empty():
    """Test /stats with empty list"""
    response = client.post("/stats", json={"values": []})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["sum"] == 0.0
    assert data["mean"] == 0.0

def test_stats_single_value():
    """Test /stats with single value"""
    response = client.post("/stats", json={"values": [5.5]})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["sum"] == 5.5
    assert data["mean"] == 5.5

def test_stats_negative_values():
    """Test /stats with negative values"""
    response = client.post("/stats", json={"values": [-1, 0, 1]})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert data["sum"] == 0.0
    assert data["mean"] == 0.0 