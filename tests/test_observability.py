from codepipeline.core import observability as _obs

def test_metrics_available():
    assert _obs.RAG_LATENCY
    assert _obs.RAG_SUCCESS