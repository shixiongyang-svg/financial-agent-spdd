from __future__ import annotations

import io
import json
import logging
import sys

import httpx
import pytest

from financial_agent_api.core.config import Settings
from financial_agent_api.core.logging import (
    JSONFormatter,
    bind_graph_context,
    bind_request_id,
    configure_logging,
    get_graph_name,
    get_request_id,
    get_node_name,
    reset_request_id,
    reset_graph_context,
)
from financial_agent_api.services.llm_client import LLMHTTPClient
from financial_agent_api.services.llm_service import LLMService


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
    graph_token, node_token = bind_graph_context("graph-a", "node-b")
    try:
        logging.getLogger("test").debug(
            "text-event",
            extra={
                "duration_ms": 1.25,
                "state": {"foo": "bar"},
                "result": {"answer": "ok"},
            },
        )
    finally:
        reset_graph_context(graph_token, node_token)
        reset_request_id(token)

    output = stream.getvalue().strip()
    assert "DEBUG" in output
    assert "req-text" in output
    assert "graph=graph-a" in output
    assert "node=node-b" in output
    assert "text-event" in output
    assert "duration_ms=1.25" in output
    assert 'state={"foo": "bar"}' in output
    assert 'result={"answer": "ok"}' in output


def test_graph_context_round_trip() -> None:
    graph_token, node_token = bind_graph_context("graph-x", "node-y")
    try:
        assert get_graph_name() == "graph-x"
        assert get_node_name() == "node-y"
    finally:
        reset_graph_context(graph_token, node_token)
    assert get_graph_name() is None
    assert get_node_name() is None


@pytest.mark.asyncio
async def test_llm_logs_include_graph_context(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging("json", level="DEBUG")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:11434/api/chat"
        return httpx.Response(200, json={"message": {"content": "ok"}})

    settings = Settings()
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)

    graph_token, node_token = bind_graph_context("graph-x", "node-y")
    try:
        await service.complete([{"role": "user", "content": "hello"}])
    finally:
        reset_graph_context(graph_token, node_token)
        await client.close()

    logs = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    start_log = next(item for item in logs if item["event"] == "llm_complete_start")
    http_log = next(item for item in logs if item["event"] == "llm_http_request")
    assert start_log["graph_name"] == "graph-x"
    assert start_log["node_name"] == "node-y"
    assert http_log["graph_name"] == "graph-x"
    assert http_log["node_name"] == "node-y"


def test_configure_logging_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="Unsupported log format"):
        configure_logging("yaml")
