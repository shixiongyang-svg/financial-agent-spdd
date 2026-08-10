from __future__ import annotations
import logging
from ..agent.graph import build_graph
from ..agent.state import AgentState
from ..core.services_container import ServicesContainer

logger = logging.getLogger(__name__)
GRAPH_NAME = "financial_helpdesk_agent"


class AgentRunner:
    def __init__(self, container: ServicesContainer) -> None:
        self._container = container
        self._graph = build_graph(container)
        self._graph_name = GRAPH_NAME
        logger.info("agent_runner_initialized", extra={"graph_name": self._graph_name})

    async def run(
        self,
        *,
        user_query: str,
        session_id: str | None,
        request_id: str,
    ) -> AgentState:
        resolved_session_id, persisted_history = self._container.session_store.load_or_create_session(
            session_id=session_id,
        )
        current_history = list(persisted_history)
        current_history.append({"role": "user", "content": user_query})
        self._container.session_store.save_history(resolved_session_id, current_history)

        initial_state: AgentState = {
            "request_id": request_id,
            "session_id": resolved_session_id,
            "user_query": user_query,
            "conversation_history": current_history,
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
            extra={
                "request_id": request_id,
                "graph_name": self._graph_name,
                "session_id": resolved_session_id,
                "user_query": user_query[:100],
            },
        )
        try:
            final_state: AgentState = await self._graph.ainvoke(initial_state)
        except Exception as exc:
            if getattr(exc, "session_id", None) is None:
                setattr(exc, "session_id", resolved_session_id)
            raise
        final_history = list(final_state.get("conversation_history") or current_history)
        answer = final_state.get("final_answer")
        if isinstance(answer, str) and answer:
            final_history.append({"role": "assistant", "content": answer})
        self._container.session_store.save_history(resolved_session_id, final_history)
        final_state["conversation_history"] = final_history
        final_state["session_id"] = resolved_session_id
        logger.info(
            "agent_run_complete",
            extra={
                "request_id": request_id,
                "graph_name": self._graph_name,
                "session_id": resolved_session_id,
                "has_answer": final_state.get("final_answer") is not None,
            },
        )
        return final_state
