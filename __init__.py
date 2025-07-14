
"""Top‑level package initialisation for *codepipeline*.

Highlights
----------
* Bootstraps **OpenTelemetry** (if installed) to enable distributed tracing.
* Initialises **structlog**‑based JSON logging (configuration delegated to
  :pymod:`codepipeline.logging_config`).
"""

from __future__ import annotations

import types
from typing import TYPE_CHECKING

# ---------------------------------------------------------------------------#
# Distributed tracing – optional
# ---------------------------------------------------------------------------#
try:
    from opentelemetry import trace  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import (  # type: ignore
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )

    _provider = TracerProvider()
    _provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(_provider)
    tracer = trace.get_tracer(__name__)
except ModuleNotFoundError:  # pragma: no cover
    # Lightweight stub so ``codepipeline.tracer`` is always defined.
    trace = types.ModuleType("trace")  # type: ignore
    tracer = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------#
# Structured logging – always on
# ---------------------------------------------------------------------------#
from .logging_config import get_logger  # re-export for convenience
from . import logging_config as _logging_config  # noqa: E402
import builtins as _bt; _bt.get_logger = get_logger  # global helper

# ---------------------------------------------------------------------------#
# Public API re‑exports
# ---------------------------------------------------------------------------#
from .version import __version__  # noqa: E402
from .token_budget_manager import check_budget  # noqa: E402
from .provider_broker import Provider, OpenAIProvider, AnthropicProvider, Broker  # noqa: E402
from .tree_sitter import parse_python_file  # noqa: E402
from .context_assembler import assemble_context, cosine_similarity  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover – type‑only imports
    from .logging_config import get_logger  # re‑export type for type‑checkers
import codepipeline.telemetry  # noqa: F401  # Auto‑import for OTLP export