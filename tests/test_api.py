"""
Test API endpoints.
"""

import sys

# Temporarily rename secrets to avoid conflict
if 'secrets' in sys.modules:
    del sys.modules['secrets']

from unittest.mock import patch

from fastapi.testclient import TestClient

from codepipeline.api.app import app

client = TestClient(app)

@patch("codepipeline.api.app._gw.chat", return_value="print('x')\n")
def test_synth_endpoint(mock_chat):
    resp = client.post("/synth", json={"prompt":"x"})
    assert resp.status_code == 200
    assert resp.json()["code"] == "print('x')\n"
