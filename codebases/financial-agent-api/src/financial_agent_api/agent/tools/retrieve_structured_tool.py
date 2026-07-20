from __future__ import annotations
import logging
from ...agent.state import AgentState
from ...services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


async def retrieve_structured_tool(
    state: AgentState,
    retrieval: RetrievalService,
) -> dict:
    """Retrieve complaint rows relevant to the user query. Returns partial AgentState dict."""
    try:
        complaints = await retrieval.retrieve_complaints(
            state["user_query"],
            request_id=state["request_id"],
        )
        return {"structured_results": complaints}
    except Exception as exc:
        logger.warning("retrieve_structured_tool failed", extra={"error": str(exc), "request_id": state["request_id"]})
        return {"structured_results": [], "error": str(exc)}
