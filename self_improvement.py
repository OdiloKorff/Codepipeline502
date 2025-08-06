"""Utilities to log and query self‑improvement events of the pipeline."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger("codepipeline.self_improvement")

def log_improvement(improvement_type: str, details: Any | None = None) -> None:
    """Emit a structured log entry when the pipeline improves itself.

    Args:
        improvement_type: Semantic tag, e.g. "strategy_switch", "prompt_optimization", "auto_fix".
        details: Free‑form payload providing context (JSON‑serialisable recommended).
    """
    _LOGGER.info(
        f"Self‑improvement: {improvement_type}",
        extra={
            "self_improvement": True,
            "improvement_type": improvement_type,
            "details": details or "",
        },
    )
