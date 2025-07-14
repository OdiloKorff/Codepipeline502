
"""Structured logging configuration for CodePipeline.

Key features
------------
* **structlog** for structured JSON logs
* Automatic **OpenTelemetry** trace/span ID propagation
* **vector.dev** friendly: logs are emitted to *stdout* where a Vector agent
  can apply rotation, shipping, and retention policies externally.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, MutableMapping

# ---------------------------------------------------------------------------#
# structlog import – fall back to lightweight stub if library unavailable
# ---------------------------------------------------------------------------#
try:
    import structlog  # type: ignore
except (ModuleNotFoundError, ImportError):  # pragma: no cover
    import types, json  # local import to avoid hard dependency

    _processors = types.ModuleType("processors")
    class _JSONRenderer:
        def __call__(self, *_: Any, event_dict: MutableMapping[str, Any], **__: Any) -> str:  # type: ignore[override]
            return json.dumps(event_dict)

    _processors.JSONRenderer = _JSONRenderer
    _processors.TimeStamper = lambda *a, **k: (lambda *_a, **_k: _k.get("event_dict", {}))
    _processors.add_log_level = lambda *a, **k: (lambda *_a, **_k: _k.get("event_dict", {}))
    _processors.StackInfoRenderer = lambda *a, **k: (lambda *_a, **_k: _k.get("event_dict", {}))
    _processors.format_exc_info = lambda *a, **k: (lambda *_a, **_k: _k.get("event_dict", {}))

    structlog = types.ModuleType("structlog")
    structlog.processors = _processors
    structlog.stdlib = types.ModuleType("stdlib")
    structlog.stdlib.LoggerFactory = lambda *a, **k: logging.getLogger
    structlog.configure = lambda **kw: None  # type: ignore[assignment]
    structlog.make_filtering_bound_logger = lambda level: logging.Logger  # type: ignore[assignment]

    def _get_logger(name: str | None = None) -> logging.Logger:  # type: ignore[override]
        return logging.getLogger(name or "codepipeline")

    structlog.get_logger = _get_logger  # type: ignore[attr-defined]

    sys.modules["structlog"] = structlog

# ---------------------------------------------------------------------------#
# Basics
# ---------------------------------------------------------------------------#

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Std‑lib logging – minimal handler to stdout
_root = logging.getLogger()
_root.handlers.clear()
_root.setLevel(LOG_LEVEL)

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(logging.Formatter("%(message)s"))
_root.addHandler(_stream_handler)

# ---------------------------------------------------------------------------#
# OpenTelemetry context processing
# ---------------------------------------------------------------------------#
try:
    from opentelemetry.trace import get_current_span  # type: ignore
except (ModuleNotFoundError, ImportError):  # pragma: no cover
    def get_current_span():  # type: ignore
        return None

def _otel_trace_processor(
    _: Any, __: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Attach OpenTelemetry trace/span IDs (if any) to every log record."""
    span = get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx and ctx.is_valid:
            event_dict.setdefault("trace_id", f"{ctx.trace_id:032x}")
            event_dict.setdefault("span_id", f"{ctx.span_id:016x}")
    return event_dict

# ---------------------------------------------------------------------------#
# structlog configuration
# ---------------------------------------------------------------------------#

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.add_log_level,
        _otel_trace_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(_root.level),
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: str | None = None):  # type: ignore[override]
    """Return a bound logger for the given *name* (package or module)."""
    return structlog.get_logger(name)
