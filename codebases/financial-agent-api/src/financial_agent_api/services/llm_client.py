from __future__ import annotations

import logging
from typing import Any

import httpx

from ..core.logging import get_request_id

logger = logging.getLogger(__name__)


class LLMHTTPClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=30.0,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        logger.info(
            "llm_http_request",
            extra={
                "method": method.upper(),
                "path": path,
                "request_id": get_request_id(),
                "payload": _truncate_for_log(kwargs.get("json")),
            },
        )
        try:
            response = await self._client.request(method=method, url=path, **kwargs)
        except (httpx.RequestError, httpx.TimeoutException):
            logger.exception(
                "llm_http_request_failed",
                extra={
                    "method": method.upper(),
                    "path": path,
                    "request_id": get_request_id(),
                },
            )
            raise

        raw_text = response.text
        try:
            parsed_body: Any = response.json() if raw_text else {}
        except ValueError:
            parsed_body = {"_body_text": raw_text}

        payload: dict[str, Any]
        if isinstance(parsed_body, dict):
            payload = dict(parsed_body)
        else:
            payload = {"data": parsed_body}
        payload["_status_code"] = response.status_code
        payload["_text"] = raw_text

        logger.info(
            "llm_http_response",
            extra={
                "method": method.upper(),
                "path": path,
                "request_id": get_request_id(),
                "status_code": response.status_code,
                "payload": _truncate_for_log(payload),
            },
        )
        return payload


def _truncate_for_log(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) > 500:
            return {"value": value[:500], "_truncated": True}
        return value
    if isinstance(value, dict):
        truncated: dict[str, Any] = {}
        for key, item in value.items():
            truncated[str(key)] = _truncate_for_log(item)
        return truncated
    if isinstance(value, list):
        return [_truncate_for_log(item) for item in value]
    return value
