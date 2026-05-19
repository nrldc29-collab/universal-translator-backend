"""
Tests for logging utilities.

This module tests the JSON formatter and trace ID management functionality
in the logging utilities module. Tests verify that log records are properly
formatted as JSON with trace IDs and custom fields.

Run tests:
    pytest server/tests/test_logging_utils.py

Purpose:
This ensures that structured logging works correctly, producing JSON-formatted
log entries with trace IDs for distributed tracing and custom event fields.
"""
import json
import logging

from stt_server import logging_utils

logger = logging.getLogger(__name__)


def test_json_formatter_includes_trace_id_and_event_fields():
    """
    Test that JSON formatter includes trace ID and event fields.
    
    Verifies that the JsonFormatter correctly formats log records as JSON,
    including trace IDs from the context and custom extra fields.
    """
    logger.info("Testing JSON formatter includes trace ID and event fields")
    
    logging_utils.set_trace_id("trace-123")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.extra_fields = {"event_type": "test.event", "source": "unit"}

    payload = json.loads(logging_utils.JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "hello"
    assert payload["trace_id"] == "trace-123"
    assert payload["event_type"] == "test.event"
    assert payload["source"] == "unit"

    logging_utils.set_trace_id(None)
    
    logger.info("JSON formatter test passed")
