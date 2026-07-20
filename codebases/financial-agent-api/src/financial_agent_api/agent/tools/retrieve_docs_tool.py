from __future__ import annotations
import logging
from ...agent.state import AgentState
from ...services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


async def retrieve_docs_tool(
    state: AgentState,
    retrieval: RetrievalService,
) -> dict:
    """Retrieve document chunks relevant to the user query. Returns partial AgentState dict."""
    try:
        docs = await retrieval.retrieve_docs(
            state["user_query"],
            request_id=state["request_id"],
        )
        return {"retrieved_docs": docs}
    except Exception as exc:
        logger.warning("retrieve_docs_tool failed", extra={"error": str(exc), "request_id": state["request_id"]})
        return {"retrieved_docs": [], "error": str(exc)}
