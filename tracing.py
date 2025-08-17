
"""Lightweight tracing adapter used in the CI test environment.

We avoid importing heavy OpenTelemetry exporters which are not installed."""


class _NoopSpan:  # noqa: D401
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False

class _NoopTracer:  # noqa: D401
    def start_as_current_span(self, *_a, **_kw): return _NoopSpan()

tracer = _NoopTracer()
