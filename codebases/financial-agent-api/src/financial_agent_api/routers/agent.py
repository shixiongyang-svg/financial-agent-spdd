from __future__ import annotations
import logging
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..agent.runner import AgentRunner
from ..core.exceptions import LLMProviderError, ScenarioFeedbackRequired
from ..core.logging import get_request_id
from ..models.agent import AgentQueryRequest, AgentQueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(body: AgentQueryRequest, request: Request) -> AgentQueryResponse | JSONResponse:
    request_id = get_request_id() or str(uuid4())
    runner: AgentRunner = request.app.state.runner
    try:
        state = await runner.run(
            user_query=body.question,
            session_id=body.session_id,
            request_id=request_id,
        )
        return AgentQueryResponse(
            answer=state["final_answer"] or "",
            request_id=request_id,
            session_id=state["session_id"] or "",
            conversation_history=state.get("conversation_history", []),
            retrieved_doc_ids=[doc.doc_id for doc in state.get("retrieved_docs", [])],
            retrieved_complaint_ids=[c.complaint_id for c in state.get("structured_results", [])],
        )
    except ScenarioFeedbackRequired as exc:
        logger.warning(
            "scenario_feedback_required",
            extra={"request_id": request_id, "session_id": exc.session_id, "reason": exc.reason},
        )
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "scenario_feedback_required",
                "message": exc.message,
                "request_id": request_id,
                "session_id": exc.session_id,
            },
        )
    except LLMProviderError as exc:
        session_id = getattr(exc, "session_id", None)
        logger.error(
            "llm_provider_error",
            extra={"request_id": request_id, "session_id": session_id, "error": str(exc)},
        )
        return JSONResponse(
            status_code=502,
            content={
                "error_code": "llm_provider_error",
                "message": str(exc),
                "request_id": request_id,
                "session_id": session_id,
            },
        )
    except Exception as exc:
        session_id = getattr(exc, "session_id", None)
        logger.error(
            "agent_query_error",
            extra={"request_id": request_id, "session_id": session_id, "error": str(exc)},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "internal_error",
                "message": str(exc),
                "request_id": request_id,
                "session_id": session_id,
            },
        )
