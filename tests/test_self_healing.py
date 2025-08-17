from pathlib import Path
from unittest.mock import patch

from codepipeline.self_healing import calculate_reward, self_heal


def test_reward_zero_on_failure(tmp_path: Path, monkeypatch):
    project = tmp_path / "repo"
    project.mkdir()
    monkeypatch.setattr("codepipeline.self_healing._run_coverage", lambda repo: 0.0)
    monkeypatch.setattr("codepipeline.self_healing._run_bandit", lambda repo: 0.0)
    assert calculate_reward(project)==0.0

@patch("codepipeline.self_healing.register_model")
@patch("codepipeline.self_healing.rlhf_finetune", return_value="model://new")
@patch("codepipeline.self_healing.calculate_reward", return_value=0.9)
def test_self_heal_flow(mock_reward,mock_ft, mock_reg):
    mock_reg.return_value="v1"
    version=self_heal("/tmp","model://base")
    mock_ft.assert_called()
    mock_reg.assert_called_once()
    assert version=="v1"
