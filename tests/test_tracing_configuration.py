from opentelemetry import trace
from codepipeline import tracer

def test_tracer_is_configured():
    assert trace.get_tracer_provider() is not None
    assert tracer is not None