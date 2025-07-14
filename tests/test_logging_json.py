import logging
import json
from codepipeline import __init__ as cp_init

def test_logging_uses_json_formatter(caplog):
    logger = logging.getLogger()
    caplog.set_level(logging.INFO)
    logger.info("test-message")
    record = caplog.records[0]
    # record.message should be test-message and record.getMessage() returns JSON
    msg = record.getMessage()
    obj = json.loads(msg)
    assert obj.get("message") == "test-message"