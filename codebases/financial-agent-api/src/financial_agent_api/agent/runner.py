from __future__ import annotations
import logging
from ..agent.graph import build_graph
from ..agent.state import AgentState
from ..core.services_container import ServicesContainer

logger = logging.getLogger(__name__)


class AgentRunner:
    def __init__(self, container: ServicesContainer) -> None:
        self._graph = build_graph(container)

    async def run(
        self,
        *,
        user_query: str,
        session_id: str | None,
        conversation_history: list[dict],
        request_id: str,
    ) -> AgentState:
        initial_state: AgentState = {
            "request_id": request_id,
            "session_id": session_id,
            "user_query": user_query,
            "conversation_history": conversation_history,
            "safety_decision": None,
            "retrieved_docs": [],
            "structured_results": [],
            "scenario": None,
            "analysis_notes": "",
            "final_answer": None,
            "error": None,
        }
        logger.info(
            "agent_run_start",
            extra={"request_id": request_id, "user_query": user_query[:100]},
        )
        final_state: AgentState = await self._graph.ainvoke(initial_state)
        logger.info(
            "agent_run_complete",
            extra={
                "request_id": request_id,
                "has_answer": final_state.get("final_answer") is not None,
            },
        )
        return final_state
