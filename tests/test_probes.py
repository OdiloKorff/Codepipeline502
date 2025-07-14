import pytest
from fastapi.testclient import TestClient
from codepipeline.api.app import app

client = TestClient(app)

@pytest.mark.parametrize("path", ["/livez", "/readyz"])
def test_probes(path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
