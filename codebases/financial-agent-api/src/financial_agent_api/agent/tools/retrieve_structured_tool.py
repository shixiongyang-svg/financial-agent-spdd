from __future__ import annotations
import logging
from ...agent.state import AgentState
from ...services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


async def retrieve_structured_tool(
    state: AgentState,
    retrieval: RetrievalService,
    *,
    product: str | None = None,
    issue: str | None = None,
) -> dict:
    """Retrieve complaint rows relevant to the user query. Returns partial AgentState dict."""
    complaints = await retrieval.retrieve_complaints(
        state["user_query"],
        product=product,
        issue=issue,
        request_id=state["request_id"],
    )
    return {"structured_results": complaints}
