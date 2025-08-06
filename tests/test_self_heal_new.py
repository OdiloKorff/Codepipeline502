
from unittest.mock import patch

from codepipeline.self_healing import self_heal


@patch("codepipeline.self_healing.calculate_reward", return_value=0.9)
@patch("codepipeline.self_healing._openai_fine_tune", return_value="model-abc")
@patch("codepipeline.self_healing.mlflow.MlflowClient")
def test_self_heal_flow(mc, ft, rw):
    mc.return_value.create_model_version.return_value.version=2
    assert self_heal(".", "model://base")=="2"
