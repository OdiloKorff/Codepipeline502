"""
Post-merge runner for CodePipeline.
"""

import os
import subprocess
from typing import Any

from codepipeline.logging_config import get_logger

_log = get_logger(__name__)

DEFAULT_IMAGE = os.getenv("TEST_RUNNER_IMAGE", "python:3.11-slim")

def _docker_run_cmd(volume: str, cpus: float, memory: str) -> list[str]:
    return [
        "docker","run","--rm",
        "--cpus", str(cpus),
        "--memory", memory,
        "-v", f"{volume}:/workspace",
        "-w","/workspace",
        DEFAULT_IMAGE,
        "sh","-c","pip install -q pytest && pytest -q"
    ]

def run_tests(repo_path: str,
              *,
              timeout: int = 300,
              cpus: float = 1.0,
              memory: str = "1g",
              webhook_url: Optional[str] = None
             ) -> dict[str, Any]:
    """Run tests in docker and (optionally) POST result to webhook."""
    start = time.time()
    cmd = _docker_run_cmd(repo_path, cpus, memory)
    _log.info("Running tests in container: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        success = proc.returncode == 0
    except subprocess.TimeoutExpired as exc:
        success = False
        proc = exc
    duration = time.time() - start
    result = {
        "success": success,
        "returncode": getattr(proc, "returncode", -1),
        "stdout": getattr(proc, "stdout", ""),
        "stderr": getattr(proc, "stderr", ""),
        "duration": duration,
    }
    _log.info("Test run finished: success=%s, duration=%.2fs", success, duration)
    if webhook_url:
        try:
            import requests  # lazy
            requests.post(webhook_url, json=result, timeout=10)
        except Exception as exc:
            _log.warning("Webhook POST failed: %s", exc)
            result["webhook_error"] = str(exc)
    return result
