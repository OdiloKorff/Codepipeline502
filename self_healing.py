"""
Self-healing utilities for CodePipeline.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from codepipeline.logging_config import get_logger

_log = get_logger(__name__)

# ------------------------------------------------------------------ #
# Reward calculation
# ------------------------------------------------------------------ #
def _run_coverage(repo: Path) -> float:
    """Return coverage % using coverage.py run -m pytest."""
    cov_file = repo / ".coverage"
    if cov_file.exists():
        cov_file.unlink()
    try:
        subprocess.run(["coverage", "run", "-m", "pytest", "-q"], cwd=repo, check=True, capture_output=True)
        out = subprocess.check_output(["coverage", "report", "--format=json"], cwd=repo)
        data = json.loads(out)
        return data["totals"]["percent_covered"] / 100.0
    except Exception as exc:
        _log.warning("Coverage run failed: %s", exc)
        return 0.0

def _run_bandit(repo: Path) -> float:
    """Return inverted mean Bandit severity score (1 = no issues)."""
    try:
        out = subprocess.check_output(["bandit", "-r", ".", "-f", "json"], cwd=repo)
        data = json.loads(out)
        high = sum(1 for i in data["results"] if i["issue_severity"] == "HIGH")
        medium = sum(1 for i in data["results"] if i["issue_severity"] == "MEDIUM")
        score = 1.0 / (1 + high + 0.5 * medium)
        return score
    except Exception as exc:
        _log.warning("Bandit run failed: %s", exc)
        return 0.0

def calculate_reward(repo: Path) -> float:
    """Weighted reward: 0.7*coverage + 0.3*security"""
    cov = _run_coverage(repo)
    sec = _run_bandit(repo)
    reward = 0.7 * cov + 0.3 * sec
    _log.info("Reward calculated: coverage=%.2f security=%.2f reward=%.2f", cov, sec, reward)
    return reward

# ------------------------------------------------------------------ #
# RLHF Fine‑Tuner stub
# ------------------------------------------------------------------ #

def rlhf_finetune(previous_model_uri: str, reward: float) -> str:
    if reward >= 1.0:
        return previous_model_uri
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
    tmp.write(b'{"messages":[],"completion":"ok"}')
    tmp.close()
    # return _openai_fine_tune(tmp.name)  # TODO: implement
    return "model-placeholder"

# ------------------------------------------------------------------ #
# MLflow registry operations (mock)
# ------------------------------------------------------------------ #

def register_model(model_uri: str, stage: str = "Staging") -> str:
    # client = mlflow.MlflowClient()  # TODO: implement MLflow
    # Placeholder implementation
    import logging
    logging.warning("MLflow not implemented, using placeholder")
    client = None
    name = "codepipeline-model"
    try:
        client.create_registered_model(name)
    except Exception:
        pass
    mv = client.create_model_version(name, model_uri, "self_healing")
    client.set_model_version_tag(name, mv.version, "reward", "auto")
    client.transition_model_version_stage(name, mv.version, stage)
    return str(mv.version)
