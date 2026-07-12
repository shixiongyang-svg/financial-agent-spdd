from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_RESERVED_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        if not hasattr(record, "duration_ms"):
            record.duration_ms = None
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", get_request_id()),
            "event": record.getMessage(),
            "duration_ms": getattr(record, "duration_ms", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED_FIELDS and key not in payload:
                payload[key] = _json_safe(value)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        request_id = getattr(record, "request_id", get_request_id()) or "-"
        duration_ms = getattr(record, "duration_ms", None)
        duration_text = f" duration_ms={duration_ms}" if duration_ms is not None else ""
        return f"{timestamp} {record.levelname} [{request_id}] {record.getMessage()}{duration_text}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return str(value)


def configure_logging(log_format: str, level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.filters.clear()
    root_logger.setLevel(level.upper())

    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    elif log_format == "text":
        handler.setFormatter(TextFormatter())
    else:
        raise ValueError(f"Unsupported log format: {log_format}")

    root_logger.addHandler(handler)


def bind_request_id(request_id: str) -> Token[str | None]:
    return _request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id_context.reset(token)


def get_request_id() -> str | None:
    return _request_id_context.get()
