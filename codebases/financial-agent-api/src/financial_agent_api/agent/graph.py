from __future__ import annotations
import asyncio
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from ..agent.state import AgentState
from ..agent.tools.retrieve_docs_tool import retrieve_docs_tool
from ..agent.tools.retrieve_structured_tool import retrieve_structured_tool
from ..agent.tools.summarise_tool import summarise_tool
from ..agent.tools.synthesise_answer_tool import synthesise_answer_tool
from ..core.services_container import ServicesContainer

logger = logging.getLogger(__name__)


def _ingest_input_node(state: AgentState) -> dict:
    """No-op validation gate — verifies user_query is present."""
    if not state.get("user_query"):
        raise ValueError("AgentState.user_query must not be empty")
    return {}


def _build_retrieve_phase_node(container: ServicesContainer):
    async def retrieve_phase_node(state: AgentState) -> dict:
        results = await asyncio.gather(
            retrieve_docs_tool(state, container.retrieval),
            retrieve_structured_tool(state, container.retrieval),
            return_exceptions=True,
        )
        docs_result, complaints_result = results

        docs_failed = isinstance(docs_result, BaseException) or (
            isinstance(docs_result, dict) and "error" in docs_result
        )
        complaints_failed = isinstance(complaints_result, BaseException) or (
            isinstance(complaints_result, dict) and "error" in complaints_result
        )

        if docs_failed and complaints_failed:
            raise RuntimeError(
                f"Both retrieval tasks failed. "
                f"docs_error={docs_result!r}, complaints_error={complaints_result!r}"
            )

        if docs_failed:
            logger.warning(
                "retrieve_docs_tool failed, continuing with empty docs",
                extra={"error": str(docs_result), "request_id": state["request_id"]},
            )
            docs_result = {"retrieved_docs": []}

        if complaints_failed:
            logger.warning(
                "retrieve_structured_tool failed, continuing with empty complaints",
                extra={"error": str(complaints_result), "request_id": state["request_id"]},
            )
            complaints_result = {"structured_results": []}

        merged: dict = {}
        merged.update(docs_result)  # type: ignore[arg-type]
        merged.update(complaints_result)  # type: ignore[arg-type]
        return merged

    return retrieve_phase_node


def _build_analysis_phase_node(container: ServicesContainer):
    async def analysis_phase_node(state: AgentState) -> dict:
        return await summarise_tool(state, container.llm)
    return analysis_phase_node


def _build_synthesis_phase_node(container: ServicesContainer):
    async def synthesis_phase_node(state: AgentState) -> dict:
        return await synthesise_answer_tool(state, container.llm)
    return synthesis_phase_node


def build_graph(container: ServicesContainer) -> Any:
    """Build and compile the LangGraph StateGraph. Returns a compiled graph."""
    graph: StateGraph = StateGraph(AgentState)

    graph.add_node("ingest_input", _ingest_input_node)
    graph.add_node("retrieve_phase", _build_retrieve_phase_node(container))
    graph.add_node("analysis_phase", _build_analysis_phase_node(container))
    graph.add_node("synthesis_phase", _build_synthesis_phase_node(container))

    graph.add_edge(START, "ingest_input")
    graph.add_edge("ingest_input", "retrieve_phase")
    graph.add_edge("retrieve_phase", "analysis_phase")
    graph.add_edge("analysis_phase", "synthesis_phase")
    graph.add_edge("synthesis_phase", END)

    return graph.compile()
