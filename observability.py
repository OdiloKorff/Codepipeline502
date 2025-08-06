"""
Observability utilities for CodePipeline.
"""

from codepipeline.logging_config import get_logger

logger = get_logger(__name__)

_meter = None
_tracer = None
_request_counter = None
_request_latency = None

def init_telemetry():
    import importlib
    global _meter, _tracer, _request_counter, _request_latency
    # Lazy import of OpenTelemetry modules
    otel_metrics = importlib.import_module('opentelemetry.metrics')
    otel_trace = importlib.import_module('opentelemetry.trace')
    sdk_metrics = importlib.import_module('opentelemetry.sdk.metrics')
    prometheus_reader = importlib.import_module('opentelemetry.exporter.prometheus')
    sdk_trace = importlib.import_module('opentelemetry.sdk.trace')
    sdk_trace_export = importlib.import_module('opentelemetry.sdk.trace.export')

    # Metrics setup
    reader = prometheus_reader.PrometheusMetricReader()
    provider = sdk_metrics.MeterProvider(metric_readers=[reader])
    otel_metrics.set_meter_provider(provider)
    _meter = otel_metrics.get_meter(__name__)

    # Tracing setup
    tracer_provider = sdk_trace.TracerProvider()
    span_processor = sdk_trace_export.BatchSpanProcessor(sdk_trace_export.ConsoleSpanExporter())
    tracer_provider.add_span_processor(span_processor)
    otel_trace.set_tracer_provider(tracer_provider)
    _tracer = otel_trace.get_tracer(__name__)

    # Instruments
    _request_counter = _meter.create_counter(
        "requests_total", description="Total number of requests"
    )
    _request_latency = _meter.create_histogram(
        "request_latency_seconds", description="Request latency in seconds"
    )

def get_meter():
    if _meter is None:
        init_telemetry()
    return _meter

def get_tracer():
    if _tracer is None:
        init_telemetry()
    return _tracer

def get_request_counter():
    if _request_counter is None:
        init_telemetry()
    return _request_counter

def get_request_latency():
    if _request_latency is None:
        init_telemetry()
    return _request_latency
