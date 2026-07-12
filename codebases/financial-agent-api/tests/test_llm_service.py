from __future__ import annotations

import io
import json
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from financial_agent_api.core.config import Settings, get_settings
from financial_agent_api.core.exceptions import LLMOutputValidationError, LLMProviderError
from financial_agent_api.core.logging import bind_request_id, configure_logging, reset_request_id
from financial_agent_api.main import app
from financial_agent_api.services.llm_client import LLMHTTPClient
from financial_agent_api.services.llm_service import LLMService


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "LLM_PROVIDER",
        "LOG_FORMAT",
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_CHAT_MODEL",
        "OLLAMA_OPS_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
async def test_openrouter_complete_uses_expected_endpoint_and_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret"
        body = json.loads(request.content.decode())
        assert body["model"] == "gpt-4.1-mini"
        assert body["response_format"] == {"type": "json_object"}
        assert body["max_tokens"] == 128
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "openrouter-ok"}}]},
        )

    settings = Settings(llm_provider="openrouter", openrouter_api_key="secret")
    client = LLMHTTPClient(settings.openrouter_base_url, settings.openrouter_api_key, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)

    result = await service.complete(
        [{"role": "user", "content": "hello"}],
        response_format="json_object",
        max_tokens=128,
    )

    assert result == "openrouter-ok"
    await client.close()


@pytest.mark.asyncio
async def test_ollama_complete_uses_expected_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://localhost:11434/api/chat"
        body = json.loads(request.content.decode())
        assert body["model"] == "gemma3:27b"
        assert body["format"] == "json"
        return httpx.Response(200, json={"message": {"content": "ollama-ok"}})

    settings = Settings()
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)

    result = await service.complete(
        [{"role": "user", "content": "hello"}],
        response_format="json",
    )

    assert result == "ollama-ok"
    await client.close()


@pytest.mark.asyncio
async def test_complete_retries_server_errors_three_times(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error": "unavailable"})

    monkeypatch.setattr("financial_agent_api.services.llm_service.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("financial_agent_api.services.llm_service.random.uniform", lambda _a, _b: 0.0)

    settings = Settings()
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)
    token = bind_request_id("req-503")
    try:
        with pytest.raises(LLMProviderError) as exc_info:
            await service.complete([{"role": "user", "content": "retry"}])
    finally:
        reset_request_id(token)
        await client.close()

    assert attempts == 3
    assert sleeps == [1.0, 2.0]
    assert exc_info.value.provider == "ollama"
    assert exc_info.value.status_code == 503
    assert exc_info.value.request_id == "req-503"


@pytest.mark.asyncio
async def test_complete_retries_request_error_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("connect failed", request=request)
        return httpx.Response(200, json={"message": {"content": "recovered"}})

    monkeypatch.setattr("financial_agent_api.services.llm_service.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("financial_agent_api.services.llm_service.random.uniform", lambda _a, _b: 0.0)

    settings = Settings()
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)

    result = await service.complete([{"role": "user", "content": "retry"}])

    assert result == "recovered"
    assert attempts == 2
    assert sleeps == [1.0]
    await client.close()


@pytest.mark.asyncio
async def test_complete_does_not_retry_on_429() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, json={"error": "rate limited"})

    settings = Settings()
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)

    with pytest.raises(LLMProviderError) as exc_info:
        await service.complete([{"role": "user", "content": "rate"}], request_id="fallback-id")

    assert attempts == 1
    assert exc_info.value.status_code == 429
    assert exc_info.value.request_id == "fallback-id"
    await client.close()


@pytest.mark.asyncio
async def test_complete_does_not_retry_on_400() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, content=b"bad request")

    settings = Settings()
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)

    with pytest.raises(LLMProviderError) as exc_info:
        await service.complete([{"role": "user", "content": "bad"}])

    assert attempts == 1
    assert exc_info.value.status_code == 400
    assert "bad request" in exc_info.value.payload
    await client.close()


@pytest.mark.asyncio
async def test_complete_raises_on_invalid_success_payload() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    settings = Settings()
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)

    with pytest.raises(LLMProviderError, match="unexpected"):
        await service.complete([{"role": "user", "content": "bad payload"}])

    await client.close()


@pytest.mark.asyncio
async def test_embed_is_stub() -> None:
    settings = Settings()
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})))
    service = LLMService(settings=settings, http_client=client)

    with pytest.raises(NotImplementedError, match="Task 2"):
        await service.embed("hello")

    await client.close()


def test_provider_error_and_output_validation_error_are_redacted() -> None:
    provider_error = LLMProviderError("openrouter", 500, "Bearer super-secret-token", "req-1")
    output_error = LLMOutputValidationError("invalid", "x" * 250, "req-2")

    assert "[REDACTED]" in str(provider_error)
    assert "super-secret-token" not in str(provider_error)
    assert "..." in str(output_error)


@pytest.mark.asyncio
async def test_long_prompt_is_truncated_in_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging("json")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "ok"}})

    settings = Settings(log_format="json")
    client = LLMHTTPClient(settings.ollama_base_url, transport=httpx.MockTransport(handler))
    service = LLMService(settings=settings, http_client=client)

    await service.complete([{"role": "user", "content": "a" * 501}])

    logs = [json.loads(line) for line in stream.getvalue().strip().splitlines() if line.strip()]
    start_log = next(item for item in logs if item["event"] == "llm_complete_start")
    message_payload = start_log["payload"]["messages"][0]
    assert message_payload["_truncated"] is True
    assert len(message_payload["content"]) == 500
    await client.close()


def test_fastapi_lifespan_and_request_id_middleware(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FORMAT", "json")

    with TestClient(app) as client:
        assert app.state.container.settings.log_format == "json"
        response = client.get("/readyz", headers={"X-Request-Id": "req-main"})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["X-Request-Id"] == "req-main"

        generated = client.get("/healthz")
        assert generated.status_code == 200
        assert generated.json() == {"status": "ok"}
        assert generated.headers["X-Request-Id"]
