from __future__ import annotations

import re

_BEARER_TOKEN_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)


def _safe_payload(payload: str) -> str:
    redacted = _BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", payload)
    preview = redacted[:200]
    if len(redacted) > 200:
        preview = f"{preview}..."
    return preview


class LLMProviderError(Exception):
    def __init__(
        self,
        provider: str,
        status_code: int | None,
        payload: str,
        request_id: str | None,
    ) -> None:
        self.provider = provider
        self.status_code = status_code
        self.payload = payload
        self.request_id = request_id
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"LLMProviderError(provider={self.provider}, status_code={self.status_code}, "
            f"request_id={self.request_id}, payload={_safe_payload(self.payload)!r})"
        )


class LLMOutputValidationError(Exception):
    def __init__(self, message: str, payload: str, request_id: str | None) -> None:
        self.message = message
        self.payload = payload
        self.request_id = request_id
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"LLMOutputValidationError(message={self.message!r}, request_id={self.request_id}, "
            f"payload={_safe_payload(self.payload)!r})"
        )


class ScenarioFeedbackRequired(Exception):
    def __init__(self, message: str, request_id: str | None, reason: str, session_id: str | None = None) -> None:
        self.message = message
        self.request_id = request_id
        self.reason = reason
        self.session_id = session_id
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"ScenarioFeedbackRequired(message={self.message!r}, request_id={self.request_id}, "
            f"reason={self.reason!r}, session_id={self.session_id!r})"
        )
