from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ...agent.state import AgentState
from ...core.config import Settings
from ...core.exceptions import LLMOutputValidationError
from ...core.exceptions import ScenarioFeedbackRequired
from ...core.prompt_service import PromptService
from ...models.scenario import Scenario
from ...core.exceptions import LLMProviderError
from ...services.llm_service import LLMService
from ...services.product_issue_service import ProductIssueService

logger = logging.getLogger(__name__)


class _ScenarioPayload(BaseModel):
    product_type: str | None = None
    issue_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


async def scenario_extraction_tool(
    state: AgentState,
    llm: LLMService,
    prompt_service: PromptService,
    product_issue_service: ProductIssueService,
    settings: Settings,
) -> dict[str, Any]:
    allowed_product_issue_map = product_issue_service.get_allowed_product_issue_map()
    if not allowed_product_issue_map:
        logger.info(
            "scenario_extraction_skipped",
            extra={"request_id": state["request_id"], "reason": "empty_allowed_product_issue_map"},
        )
        return {"scenario": None}

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            rendered_prompt = prompt_service.render(
                "scenario_extraction.j2",
                messages=state.get("conversation_history") or [],
                allowed_product_issue_map=allowed_product_issue_map,
            )
            model = settings.ollama_ops_model if settings.llm_provider == "ollama" else None
            raw_result = await llm.complete(
                [{"role": "user", "content": rendered_prompt}],
                model=model,
                response_format="json",
                request_id=state["request_id"],
            )
            payload = _parse_payload(raw_result, state["request_id"])
            _validate_membership(payload, allowed_product_issue_map, state["request_id"])
            if payload.confidence < settings.scenario_confidence_threshold:
                raise LLMOutputValidationError(
                    "scenario extraction confidence below threshold",
                    raw_result,
                    state["request_id"],
                )
            scenario = Scenario(
                product_type=payload.product_type,
                issue_type=payload.issue_type,
                confidence=payload.confidence,
            )
            logger.info(
                "scenario_extraction_success",
                extra={
                    "request_id": state["request_id"],
                    "confidence": scenario.confidence,
                    "product_type": scenario.product_type,
                    "issue_type": scenario.issue_type,
                },
            )
            return {"scenario": scenario}
        except LLMProviderError as exc:
            logger.warning(
                "scenario_extraction_failed",
                extra={
                    "request_id": state["request_id"],
                    "attempt": attempt + 1,
                    "error": str(exc),
                    "retryable": False,
                },
            )
            raise
        except (LLMOutputValidationError, ValueError) as exc:
            last_error = exc
            logger.warning(
                "scenario_extraction_failed",
                extra={
                    "request_id": state["request_id"],
                    "attempt": attempt + 1,
                    "error": str(exc),
                    "retryable": attempt < 1,
                },
            )
            if attempt >= 1:
                break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "scenario_extraction_failed",
                extra={
                    "request_id": state["request_id"],
                    "attempt": attempt + 1,
                    "error": str(exc),
                    "retryable": False,
                },
            )
            raise

    if last_error is not None:
        feedback_prompt = prompt_service.render(
            "feedback_prompt.j2",
            user_query=state["user_query"],
            missing_fields="product_type, issue_type",
            allowed_values=json.dumps(allowed_product_issue_map, ensure_ascii=False, indent=2),
        )
        feedback_message = await _generate_feedback_message(
            llm=llm,
            prompt=feedback_prompt,
            request_id=state["request_id"],
            model=settings.ollama_ops_model if settings.llm_provider == "ollama" else None,
            fallback_reason=str(last_error),
            allowed_product_issue_map=allowed_product_issue_map,
        )
        raise ScenarioFeedbackRequired(
            feedback_message,
            request_id=state["request_id"],
            reason=str(last_error),
            session_id=state.get("session_id"),
        ) from last_error
    return {"scenario": None}


def _parse_payload(raw_result: str, request_id: str) -> _ScenarioPayload:
    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise LLMOutputValidationError("scenario extraction returned invalid JSON", raw_result, request_id) from exc
    try:
        return _ScenarioPayload.model_validate(payload)
    except ValidationError as exc:
        raise LLMOutputValidationError("scenario extraction payload failed validation", raw_result, request_id) from exc


def _validate_membership(
    payload: _ScenarioPayload,
    allowed_product_issue_map: dict[str, list[str]],
    request_id: str,
) -> None:
    if payload.product_type is None and payload.issue_type is not None:
        raise LLMOutputValidationError(
            "scenario extraction issue_type requires product_type",
            json.dumps(payload.model_dump()),
            request_id,
        )
    if payload.product_type is not None and payload.product_type not in allowed_product_issue_map:
        raise LLMOutputValidationError(
            "scenario extraction product_type not allowed",
            json.dumps(payload.model_dump()),
            request_id,
        )
    if payload.product_type is not None and payload.issue_type is not None:
        allowed_issues = allowed_product_issue_map.get(payload.product_type, [])
        if payload.issue_type not in allowed_issues:
            raise LLMOutputValidationError(
                "scenario extraction issue_type not allowed",
                json.dumps(payload.model_dump()),
                request_id,
            )


async def _generate_feedback_message(
    *,
    llm: LLMService,
    prompt: str,
    request_id: str,
    model: str | None,
    fallback_reason: str,
    allowed_product_issue_map: dict[str, list[str]],
) -> str:
    try:
        response = await llm.complete(
            [{"role": "user", "content": prompt}],
            model=model,
            request_id=request_id,
        )
        if isinstance(response, str) and response.strip():
            return response.strip()
    except Exception:
        pass

    allowed_products = ", ".join(sorted(allowed_product_issue_map.keys()))
    if allowed_products:
        return (
            "Please clarify the product and issue in your request. "
            f"Available products: {allowed_products}. "
            f"Reason: {fallback_reason}"
        )
    return "Please clarify the product and issue in your request."
