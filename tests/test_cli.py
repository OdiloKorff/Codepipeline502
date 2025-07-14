from typer.testing import CliRunner
from codepipeline.cli import app
from unittest.mock import patch, MagicMock
import pathlib, json, os, tempfile

def test_synth_cli(monkeypatch):
    runner = CliRunner()
    fake = MagicMock(return_value="print('hi')\n")
    monkeypatch.setattr("codepipeline.cli._gw.chat", fake)
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["synth", "--prompt", "hello", "--target", "app.py"])
        assert result.exit_code == 0
        assert pathlib.Path("app.py").read_text() == "print('hi')\n"