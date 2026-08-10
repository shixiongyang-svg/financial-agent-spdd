from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ..agent.state import AgentState
from ..core.config import Settings
from ..core.exceptions import LLMOutputValidationError
from ..core.prompt_service import PromptService
from ..services.llm_service import LLMService

logger = logging.getLogger(__name__)

_KEEP_LAST_N_MESSAGES = 2


class _CompressionResult(BaseModel):
    summary_text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


async def compress_history(
    state: AgentState,
    llm: LLMService,
    prompt_service: PromptService,
    settings: Settings,
) -> dict[str, list[dict[str, Any]]]:
    history = list(state.get("conversation_history") or [])
    if len(history) <= settings.compress_threshold:
        return {}

    messages_to_compress = history[:-_KEEP_LAST_N_MESSAGES]
    if not messages_to_compress:
        return {}

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            rendered_prompt = prompt_service.render(
                "compress_history.j2",
                messages_to_compress=messages_to_compress,
            )
            model = settings.compress_ops_model
            raw_result = await llm.complete(
                [{"role": "user", "content": rendered_prompt}],
                model=model,
                response_format="json",
                request_id=state["request_id"],
            )
            result = _parse_result(raw_result, state["request_id"])
            if result.confidence < settings.compress_confidence_threshold:
                raise ValueError(
                    f"compression confidence {result.confidence} below threshold "
                    f"{settings.compress_confidence_threshold}"
                )
            compressed_history = [
                {
                    "role": "system",
                    "content": f"[compressed history]\n{result.summary_text}",
                },
                *history[-_KEEP_LAST_N_MESSAGES:],
            ]
            logger.info(
                "conversation_history_compressed",
                extra={
                    "request_id": state["request_id"],
                    "compressed_messages": len(messages_to_compress),
                    "retained_messages": _KEEP_LAST_N_MESSAGES,
                    "confidence": result.confidence,
                },
            )
            return {"conversation_history": compressed_history}
        except Exception as exc:  # retry once, then fall back to original history
            last_error = exc
            logger.warning(
                "conversation_history_compression_failed",
                extra={
                    "request_id": state["request_id"],
                    "attempt": attempt + 1,
                    "error": str(exc),
                },
            )

    if last_error is not None:
        logger.info(
            "conversation_history_compression_skipped",
            extra={"request_id": state["request_id"], "reason": str(last_error)},
        )
    return {}


def _parse_result(raw_result: str, request_id: str) -> _CompressionResult:
    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise LLMOutputValidationError("compress_history returned invalid JSON", raw_result, request_id) from exc

    try:
        return _CompressionResult.model_validate(payload)
    except ValidationError as exc:
        raise LLMOutputValidationError("compress_history payload failed validation", raw_result, request_id) from exc
