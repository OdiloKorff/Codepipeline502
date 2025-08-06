
import json

from codepipeline.logging_config import get_logger


def test_structlog_json(capfd):
    """Logger emits well‑formed JSON to stdout and retains extra fields."""
    logger = get_logger("test")
    msg = "hello"
    logger.info(msg, foo=1)

    captured, _ = capfd.readouterr()
    # Only consider first log line
    line = captured.strip().splitlines()[0]
    data = json.loads(line)
    assert data["event"] == msg
    assert data["foo"] == 1
    # trace_id may be absent when OTEL not active but key should exist or not error
    assert "timestamp" in data
