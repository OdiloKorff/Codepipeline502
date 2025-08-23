from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class RunMeta:
    """Metadata für einen Pipeline-Run mit vollständigem Token-Accounting."""
    run_id: str
    started_at: float  # Unix timestamp
    seed: int  # Deterministischer Seed (PINNED)
    model: str
    temperature: float  # PINNED auf 0.0 für Determinismus
    token_prompt: int  # Exakte Prompt-Token
    token_completion: int  # Exakte Completion-Token
    tools: dict  # Tool -> Version mapping
    
    @property
    def total_tokens(self) -> int:
        """Gesamte Token-Anzahl für Budget-Checks."""
        return self.token_prompt + self.token_completion
    
    @property
    def is_deterministic(self) -> bool:
        """Prüfe ob Run deterministisch konfiguriert ist."""
        return self.temperature == 0.0 and isinstance(self.seed, int)


def _tool_version(cmd: list[str]) -> str | None:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        out = (res.stdout or res.stderr or "").strip().splitlines()
        return out[0] if out else None
    except Exception:
        return None


def collect_tool_versions() -> dict:
    tools = {}
    for name, args in {
        "python": ["python", "--version"],
        "pytest": ["pytest", "--version"],
        "ruff": ["ruff", "--version"],
        "mypy": ["mypy", "--version"],
        "semgrep": ["semgrep", "--version"],
        "bandit": ["bandit", "--version"],
        "gitleaks": ["gitleaks", "version"],
        "pip-audit": ["pip-audit", "--version"],
    }.items():
        if shutil.which(args[0]):
            tools[name] = _tool_version(args)
    tools["platform"] = platform.platform()
    return tools


def write_run_meta(path: str, meta: RunMeta) -> None:
    data = asdict(meta)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class MockTracer:
    """Mock tracer for environments without OpenTelemetry."""

    def start_span(self, name: str, **kwargs) -> 'MockSpan':
        return MockSpan(name)


class MockSpan:
    """Mock span for environments without OpenTelemetry."""

    def __init__(self, name: str):
        self.name = name
        self.start_time = time.time()

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()


# Global tracer instance
tracer = MockTracer()


def get_tracer(name: str) -> MockTracer:
    """Get a tracer instance."""
    return tracer


def create_span(name: str, **kwargs) -> MockSpan:
    """Create a new span."""
    return tracer.start_span(name, **kwargs)


__all__ = ['RunMeta', 'collect_tool_versions', 'write_run_meta', 'tracer', 'get_tracer', 'create_span', 'MockTracer', 'MockSpan']
