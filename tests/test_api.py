"""
Test API endpoints.
"""

import sys
import os

# Temporarily rename secrets to avoid conflict
if 'secrets' in sys.modules:
    del sys.modules['secrets']

from fastapi.testclient import TestClient
from codepipeline.api.app import app
from unittest.mock import patch

client = TestClient(app)

@patch("codepipeline.api.app._gw.chat", return_value="print('x')\n")
def test_synth_endpoint(mock_chat):
    resp = client.post("/synth", json={"prompt":"x"})
    assert resp.status_code == 200
    assert resp.json()["code"] == "print('x')\n"