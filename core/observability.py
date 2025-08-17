"""Observability utilities: OpenTelemetry tracing & Prometheus metrics."""

from __future__ import annotations

import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, OTLPSpanExporter
from prometheus_client import Counter, Histogram, start_http_server

# --------------------------------------------------------------------
# Tracing setup
# --------------------------------------------------------------------
service_name=os.getenv("OTEL_SERVICE_NAME", "codepipeline")
resource=Resource.create({"service.name": service_name})
tracer_provider=TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)
span_processor=BatchSpanProcessor(OTLPSpanExporter())
tracer_provider.add_span_processor(span_processor)
tracer=trace.get_tracer(__name__)

# --------------------------------------------------------------------
# Metrics setup
# --------------------------------------------------------------------
metric_reader=PeriodicExportingMetricReader(OTLPMetricExporter())
meter_provider=MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter=metrics.get_meter(__name__)

# Prometheus exposition
prom_port=int(os.getenv("PROM_PORT", "8001"))
start_http_server(prom_port)

RAG_LATENCY=Histogram(
    "rag_latency_seconds",
    "Latency of RAG retrieve_context",
    buckets=(0.05,0.1,0.2,0.5,1,2,5),
)
RAG_SUCCESS=Counter(
    "rag_success_total",
    "Number of successful RAG retrievals",
    ["status"]
)
