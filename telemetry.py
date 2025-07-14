"""OpenTelemetry configuration for CodePipeline.

Initializes OTLP exporter if the environment variable
OTEL_EXPORTER_OTLP_ENDPOINT is set. This module is imported for its
side‑effects during application start‑up.
"""
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if _endpoint:
    # Lazily configure tracing only when endpoint provided
    _resource = Resource.create({SERVICE_NAME: "codepipeline"})
    _provider = TracerProvider(resource=_resource)
    trace.set_tracer_provider(_provider)

    _exporter = OTLPSpanExporter(endpoint=_endpoint, timeout=5)
    _processor = BatchSpanProcessor(_exporter)
    _provider.add_span_processor(_processor)