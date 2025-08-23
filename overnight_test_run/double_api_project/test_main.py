import pytest
import json
from main import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'

def test_double_endpoint_valid(client):
    response = client.post('/double', json={'number': 5})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['result'] == 10

def test_double_endpoint_missing_number(client):
    response = client.post('/double', json={})
    assert response.status_code == 400
