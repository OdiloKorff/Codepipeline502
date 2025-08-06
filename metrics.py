"""
Prometheus Metrics for Cost Dashboard
Tracks token usage and build duration.
"""


from prometheus_client import Counter, Histogram, start_http_server

# Metrics definitions
TOKEN_USAGE = Counter('codepipeline_tokens_total', 'Total tokens used')
BUILD_DURATION = Histogram('codepipeline_build_duration_seconds', 'Build duration in seconds', buckets=[0.1, 0.3, 0.5, 1, 2])

def record_token_usage(tokens: int):
    TOKEN_USAGE.inc(tokens)

def time_build(func):
    """Decorator to measure build time."""
    def wrapper(*args, **kwargs):
        with BUILD_DURATION.time():
            return func(*args, **kwargs)
    return wrapper

def start_metrics_server(port: int = 8000):
    """Start Prometheus metrics HTTP server."""
    start_http_server(port)
