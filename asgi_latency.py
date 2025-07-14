"""ASGI middleware to track request latency via Prometheus Histogram.

Added for Work‑Item *G-01-03*.

The Histogram is exported on the default Prometheus /metrics endpoint
exposed by ``prometheus_fastapi_instrumentator``. It uses the global
bucket set ``[0.1, 0.3, 0.5, 1, 2]`` that is aligned with other histograms
in the project.
"""
from __future__ import annotations

import time
from typing import Callable, Awaitable

from starlette.types import ASGIApp, Receive, Scope, Send
from prometheus_client import Histogram

# Shared histogram instance – label cardinality is kept low (method+path+status)
REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "Latency of HTTP requests in seconds",
    labelnames=("method", "path", "status"),
    buckets=[0.1, 0.3, 0.5, 1, 2],
)

class LatencyMiddleware:  # pragma: no cover
    """Minimal ASGI middleware measuring request latency."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Non‑HTTP (e.g. websocket) – pass through
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "NA")
        path = scope.get("path", "NA")
        start = time.perf_counter()
        status_holder: dict[str, int] = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        duration = time.perf_counter() - start
        REQUEST_LATENCY.labels(method, path, str(status_holder["code"])).observe(duration)