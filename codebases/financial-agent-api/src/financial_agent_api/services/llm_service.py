from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

import httpx

from ..core.config import Settings
from ..core.exceptions import LLMProviderError
from ..core.logging import get_request_id
from .llm_client import LLMHTTPClient

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, settings: Settings, http_client: LLMHTTPClient) -> None:
        self._settings = settings
        self._http_client = http_client

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: str | None = None,
        request_id: str | None = None,
    ) -> str:
        provider = self._settings.llm_provider
        effective_request_id = get_request_id() or request_id
        payload = self._build_payload(
            provider=provider,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        logger.info(
            "llm_complete_start",
            extra={
                "provider": provider,
                "model": payload["model"],
                "request_id": get_request_id(),
                "payload": _truncate_for_log(payload),
            },
        )

        attempts = 3
        last_error: LLMProviderError | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._http_client.request(
                    method="POST",
                    path=self._path_for_provider(provider),
                    json=payload,
                )
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = LLMProviderError(
                    provider=provider,
                    status_code=None,
                    payload=str(exc),
                    request_id=effective_request_id,
                )
                if attempt == attempts:
                    raise last_error from exc
                await self._sleep_before_retry(attempt)
                continue

            status_code = int(response.get("_status_code", 500))
            if 200 <= status_code < 300:
                content = self._extract_content(provider, response, effective_request_id)
                logger.info(
                    "llm_complete_success",
                    extra={
                        "provider": provider,
                        "model": payload["model"],
                        "request_id": get_request_id(),
                        "payload": _truncate_for_log({"content": content}),
                    },
                )
                return content

            last_error = LLMProviderError(
                provider=provider,
                status_code=status_code,
                payload=self._response_payload(response),
                request_id=effective_request_id,
            )
            if status_code == 429 or 400 <= status_code < 500:
                raise last_error
            if 500 <= status_code < 600:
                if attempt == attempts:
                    raise last_error
                await self._sleep_before_retry(attempt)
                continue
            raise last_error

        if last_error is None:
            raise LLMProviderError(provider=provider, status_code=None, payload="Unknown LLM error", request_id=effective_request_id)
        raise last_error

    async def embed(
        self,
        text_value: str,
        *,
        model: str | None = None,
        request_id: str | None = None,
    ) -> list[float]:
        provider = self._settings.llm_provider
        effective_request_id = get_request_id() or request_id
        selected_model = model or self._settings.embedding_model
        payload: dict[str, Any]
        if provider == "openrouter":
            payload = {"model": selected_model, "input": text_value}
        else:
            payload = {"model": selected_model, "prompt": text_value}

        logger.info(
            "llm_embed_start",
            extra={
                "provider": provider,
                "model": selected_model,
                "request_id": get_request_id(),
                "payload": _truncate_for_log(payload),
            },
        )

        attempts = 3
        last_error: LLMProviderError | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._http_client.request(
                    method="POST",
                    path=self._embedding_path_for_provider(provider),
                    json=payload,
                )
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = LLMProviderError(
                    provider=provider,
                    status_code=None,
                    payload=str(exc),
                    request_id=effective_request_id,
                )
                if attempt == attempts:
                    raise last_error from exc
                await self._sleep_before_retry(attempt)
                continue

            status_code = int(response.get("_status_code", 500))
            if 200 <= status_code < 300:
                embedding = self._extract_embedding(provider, response, effective_request_id)
                logger.info(
                    "llm_embed_success",
                    extra={
                        "provider": provider,
                        "model": selected_model,
                        "request_id": get_request_id(),
                        "embedding_dim": len(embedding),
                    },
                )
                return embedding

            last_error = LLMProviderError(
                provider=provider,
                status_code=status_code,
                payload=self._response_payload(response),
                request_id=effective_request_id,
            )
            if status_code == 429 or 400 <= status_code < 500:
                raise last_error
            if 500 <= status_code < 600:
                if attempt == attempts:
                    raise last_error
                await self._sleep_before_retry(attempt)
                continue
            raise last_error

        if last_error is None:
            raise LLMProviderError(provider=provider, status_code=None, payload="Unknown embedding error", request_id=effective_request_id)
        raise last_error

    def _build_payload(
        self,
        *,
        provider: str,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int | None,
        response_format: str | None,
    ) -> dict[str, Any]:
        selected_model = model or self._default_model(provider)
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if provider == "openrouter" and response_format is not None:
            payload["response_format"] = {"type": response_format}
        if provider == "ollama" and response_format is not None:
            payload["format"] = response_format
        return payload

    def _default_model(self, provider: str) -> str:
        if provider == "openrouter":
            return self._settings.openrouter_model
        return self._settings.ollama_chat_model

    def _path_for_provider(self, provider: str) -> str:
        if provider == "openrouter":
            return "/chat/completions"
        return "/api/chat"

    def _embedding_path_for_provider(self, provider: str) -> str:
        if provider == "openrouter":
            return "/embeddings"
        return "/api/embeddings"

    def _extract_content(
        self,
        provider: str,
        response: dict[str, Any],
        request_id: str | None,
    ) -> str:
        if provider == "openrouter":
            choices = response.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        texts: list[str] = []
                        for part in content:
                            if isinstance(part, dict):
                                text_value = part.get("text")
                                if isinstance(text_value, str):
                                    texts.append(text_value)
                        return "".join(texts)
        else:
            message = response.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
        raise LLMProviderError(
            provider=provider,
            status_code=int(response.get("_status_code", 200)),
            payload=self._response_payload(response),
            request_id=request_id,
        )

    async def _sleep_before_retry(self, attempt: int) -> None:
        base_delay = float(2 ** (attempt - 1))
        jitter = random.uniform(0.0, 0.25)
        await asyncio.sleep(base_delay + jitter)

    def _response_payload(self, response: dict[str, Any]) -> str:
        try:
            return json.dumps(response, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(response)

    def _extract_embedding(
        self,
        provider: str,
        response: dict[str, Any],
        request_id: str | None,
    ) -> list[float]:
        if provider == "openrouter":
            data = response.get("data")
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    embedding = first.get("embedding")
                    if isinstance(embedding, list):
                        return [float(value) for value in embedding]
        else:
            embedding = response.get("embedding")
            if isinstance(embedding, list):
                return [float(value) for value in embedding]
        raise LLMProviderError(
            provider=provider,
            status_code=int(response.get("_status_code", 200)),
            payload=self._response_payload(response),
            request_id=request_id,
        )


def _truncate_for_log(payload: dict[str, Any]) -> dict[str, Any]:
    truncated: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            if len(value) > 500:
                truncated[key] = value[:500]
                truncated["_truncated"] = True
            else:
                truncated[key] = value
        elif isinstance(value, list):
            truncated[key] = [_truncate_message(item) if isinstance(item, dict) else item for item in value]
        else:
            truncated[key] = value
    return truncated


def _truncate_message(message: dict[str, Any]) -> dict[str, Any]:
    truncated = dict(message)
    for key, value in list(truncated.items()):
        if isinstance(value, str) and len(value) > 500:
            truncated[key] = value[:500]
            truncated["_truncated"] = True
    return truncated
