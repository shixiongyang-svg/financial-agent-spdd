from __future__ import annotations

import io
import json
import logging
import sys

import pytest

from financial_agent_api.core.logging import (
    JSONFormatter,
    bind_request_id,
    configure_logging,
    get_request_id,
    reset_request_id,
)


@pytest.fixture(autouse=True)
def reset_logging() -> None:
    logging.getLogger().handlers.clear()
    logging.getLogger().filters.clear()


def test_bind_request_id_round_trip() -> None:
    token = bind_request_id("req-1")
    assert get_request_id() == "req-1"
    reset_request_id(token)
    assert get_request_id() is None


def test_configure_logging_json(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging("json")
    token = bind_request_id("req-json")
    try:
        logging.getLogger("test").info("json-event", extra={"duration_ms": 12.5, "details": {"ok": True}})
    finally:
        reset_request_id(token)

    payload = json.loads(stream.getvalue().strip())
    assert payload["event"] == "json-event"
    assert payload["level"] == "INFO"
    assert payload["request_id"] == "req-json"
    assert payload["duration_ms"] == 12.5
    assert payload["details"] == {"ok": True}
    assert "timestamp" in payload


def test_json_formatter_includes_exception() -> None:
    formatter = JSONFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.getLogger("test").makeRecord(
            name="test",
            level=logging.ERROR,
            fn=__file__,
            lno=1,
            msg="failure",
            args=(),
            exc_info=sys.exc_info(),
        )

    rendered = json.loads(formatter.format(record))
    assert rendered["event"] == "failure"
    assert rendered["duration_ms"] is None
    assert "RuntimeError: boom" in rendered["exception"]


def test_configure_logging_text(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging("text", level="DEBUG")
    token = bind_request_id("req-text")
    try:
        logging.getLogger("test").debug("text-event", extra={"duration_ms": 1.25})
    finally:
        reset_request_id(token)

    output = stream.getvalue().strip()
    assert "DEBUG" in output
    assert "req-text" in output
    assert "text-event" in output
    assert "duration_ms=1.25" in output


def test_configure_logging_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="Unsupported log format"):
        configure_logging("yaml")
