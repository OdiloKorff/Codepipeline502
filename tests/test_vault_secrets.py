from unittest.mock import patch, MagicMock
import os
import importlib

@patch("codepipeline.secrets._get_client")
def test_ensure_env_fetch(mock_client):
    client=MagicMock()
    client.secrets.kv.v2.read_secret_version.return_value={"data":{"data":{"OPENAI_API_KEY":"xyz"}}}
    mock_client.return_value=client
    os.environ.pop("OPENAI_API_KEY", None)
    from codepipeline import secrets
    importlib.reload(secrets)
    secrets.ensure_env("OPENAI_API_KEY")
    assert os.getenv("OPENAI_API_KEY")=="xyz"