"""
Grafana dashboard definition for CodePipeline.
"""
from typing import Any

DASHBOARD: dict[str, Any] = {
    "title": "Metrics Dashboard",
    "panels": [
        {
            "title": "Token Cost",
            "type": "graph",
            "targets": [{"expr": "sum(token_cost)"}],
        },
        {
            "title": "Pipeline Latency",
            "type": "graph",
            "targets": [{"expr": "histogram_quantile(0.99, sum(rate(pipeline_latency_bucket[5m])) by (le))"}],
        },
        {
            "title": "Error Rate",
            "type": "graph",
            "targets": [{"expr": "sum(rate(pipeline_errors[5m]))"}],
        },
        {
            "title": "Reviewer Score",
            "type": "graph",
            "targets": [{"expr": "avg(reviewer_score)"}],
        },
    ],
}
