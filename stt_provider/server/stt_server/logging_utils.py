"""
Logging utilities for structured JSON logging and audit trails.

This module provides JSON-formatted logging with trace ID support for distributed
tracing, as well as structured event logging and admin audit logging to files.
"""
import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Context variable for trace ID support across async operations
trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

# Log directory and file paths
LOG_DIR = Path("logs")
EVENT_LOG_PATH = LOG_DIR / "stt-events.jsonl"
ADMIN_AUDIT_LOG_PATH = LOG_DIR / "admin-audit.jsonl"


def new_trace_id() -> str:
    """
    Generate a new trace ID and set it in the context.
    
    Creates a new UUID v4 trace ID for tracking requests across the service
    and sets it in the async context for use in logging throughout the request.
    
    Returns:
        New trace ID string
    """
    trace_id = str(uuid.uuid4())
    trace_id_ctx.set(trace_id)
    return trace_id


def set_trace_id(trace_id: Optional[str]) -> None:
    """
    Set the trace ID in the context.
    
    Allows setting an existing trace ID (e.g., from an incoming request header)
    for correlation across the service.
    
    Args:
        trace_id: Trace ID string to set, or None to clear
    """
    trace_id_ctx.set(trace_id)


def get_trace_id() -> Optional[str]:
    """
    Get the current trace ID from the context.
    
    Returns:
        Current trace ID string, or None if not set
    """
    return trace_id_ctx.get()


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Formats log records as JSON objects with timestamp, level, logger name,
    message, trace ID, module, function, line number, and optional
    exception information and extra fields.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON-formatted log entry as a string
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": get_trace_id(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None,
            }

        # Add extra fields if present
        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            payload.update(extra_fields)

        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    """
    Configure the root logger with JSON formatting.
    
    Sets up the logging system to output structured JSON logs to stdout,
    clearing any existing handlers and setting the log level to INFO.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def log_event(event_type: str, level: str = "info", **fields: Any) -> None:
    """
    Log a structured event with additional fields.
    
    Logs an event with a specific type and additional structured fields.
    The event type is included in the log record's extra fields for filtering.
    
    Args:
        event_type: Type of event being logged
        level: Log level (debug, info, warning, error, critical)
        **fields: Additional fields to include in the log entry
    """
    logger = logging.getLogger("stt_server")
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(
        event_type,
        extra={"extra_fields": {"event_type": event_type, **fields}},
    )


def log_admin_event(event_type: str, level: str = "info", **fields: Any) -> None:
    """
    Log an admin event to the audit log file.
    
    Writes structured admin events to the admin audit log file for compliance
    and security auditing. Events are written in JSONL format (one JSON object
    per line) with timestamp, level, event type, trace ID, and additional fields.
    
    Args:
        event_type: Type of admin event being logged
        level: Log level (debug, info, warning, error, critical)
        **fields: Additional fields to include in the audit log entry
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "created_at": created_at,
        "timestamp": created_at,
        "level": level.upper(),
        "event_type": event_type,
        "trace_id": get_trace_id(),
        **fields,
    }

    with ADMIN_AUDIT_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, default=str, separators=(",", ":")) + "\n")
