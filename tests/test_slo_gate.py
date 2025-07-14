
from scripts import slo_gate as sg

sample_metrics="""
rag_latency_seconds_bucket{le="0.1"} 90
rag_latency_seconds_bucket{le="0.2"} 95
rag_latency_seconds_bucket{le="1"} 100
rag_success_total{status="ok"} 990
rag_success_total 1000
"""

def test_p95_latency():
    buckets=sg._parse_histogram_buckets(sample_metrics)
    assert sg._p95_latency_ms(buckets)==200.0

def test_success_rate():
    assert abs(sg._success_rate(sample_metrics)-0.99)<1e-6
