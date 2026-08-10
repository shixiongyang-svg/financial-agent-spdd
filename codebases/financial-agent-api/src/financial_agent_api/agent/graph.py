from __future__ import annotations
import asyncio
import inspect
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from ..agent.history_compression import compress_history
from ..agent.state import AgentState
from ..agent.tools.retrieve_docs_tool import retrieve_docs_tool
from ..agent.tools.retrieve_structured_tool import retrieve_structured_tool
from ..agent.tools.scenario_extraction_tool import scenario_extraction_tool
from ..agent.tools.summarise_tool import summarise_tool
from ..agent.tools.synthesise_answer_tool import synthesise_answer_tool
from ..core.logging import bind_graph_context, reset_graph_context
from ..core.services_container import ServicesContainer

logger = logging.getLogger(__name__)
GRAPH_NAME = "financial_helpdesk_agent"
_DEBUG_STRING_LIMIT = 1000
_DEBUG_LIST_LIMIT = 20


def _debug_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > _DEBUG_STRING_LIMIT:
            return {
                "_truncated": True,
                "length": len(value),
                "value": value[:_DEBUG_STRING_LIMIT],
            }
        return value
    if isinstance(value, dict):
        items = list(value.items())
        truncated = len(items) > _DEBUG_LIST_LIMIT
        payload = {str(key): _debug_safe(item) for key, item in items[:_DEBUG_LIST_LIMIT]}
        if truncated:
            payload["_truncated"] = True
            payload["_item_count"] = len(items)
        return payload
    if isinstance(value, list):
        items = [_debug_safe(item) for item in value[:_DEBUG_LIST_LIMIT]]
        if len(value) > _DEBUG_LIST_LIMIT:
            items.append({"_truncated": True, "_item_count": len(value)})
        return items
    if hasattr(value, "model_dump"):
        return _debug_safe(value.model_dump(mode="json"))
    return str(value)


def _snapshot_state(state: AgentState) -> dict[str, Any]:
    return {key: _debug_safe(value) for key, value in state.items()}


def _wrap_node(name: str, node: Any):
    async def wrapped(state: AgentState) -> dict:
        graph_token, node_token = bind_graph_context(GRAPH_NAME, name)
        try:
            logger.debug(
                "graph_node_enter",
                extra={
                    "graph_name": GRAPH_NAME,
                    "node_name": name,
                    "state": _snapshot_state(state),
                },
            )
            try:
                result = node(state)
                if inspect.isawaitable(result):
                    result = await result
            except Exception:
                logger.exception(
                    "graph_node_error",
                    extra={
                        "graph_name": GRAPH_NAME,
                        "node_name": name,
                        "state": _snapshot_state(state),
                    },
                )
                raise

            next_state = dict(state)
            if isinstance(result, dict):
                next_state.update(result)

            logger.debug(
                "graph_node_exit",
                extra={
                    "graph_name": GRAPH_NAME,
                    "node_name": name,
                    "state": _snapshot_state(next_state),
                    "result": _debug_safe(result),
                },
            )
            return result
        finally:
            reset_graph_context(graph_token, node_token)

    return wrapped


def _ingest_input_node(state: AgentState) -> dict:
    """No-op validation gate — verifies user_query is present."""
    if not state.get("user_query"):
        raise ValueError("AgentState.user_query must not be empty")
    return {}


def _build_compress_history_node(container: ServicesContainer):
    async def compress_history_node(state: AgentState) -> dict:
        return await compress_history(
            state,
            container.llm,
            container.prompt_service,
            container.settings,
        )

    return compress_history_node


def _build_scenario_phase_node(container: ServicesContainer):
    async def scenario_phase_node(state: AgentState) -> dict:
        return await scenario_extraction_tool(
            state,
            container.llm,
            container.prompt_service,
            container.product_issue_service,
            container.settings,
        )

    return scenario_phase_node


def _build_retrieve_phase_node(container: ServicesContainer):
    async def retrieve_phase_node(state: AgentState) -> dict:
        scenario = state.get("scenario")
        async def _skip_complaints() -> dict:
            return {"structured_results": []}

        if scenario is None:
            logger.info(
                "complaints_retrieval_skipped",
                extra={"request_id": state["request_id"], "reason": "scenario_missing"},
            )
            complaints_task = _skip_complaints()
        elif scenario.product_type is None:
            logger.info(
                "complaints_retrieval_skipped",
                extra={"request_id": state["request_id"], "reason": "scenario_has_no_product"},
            )
            complaints_task = _skip_complaints()
        else:
            complaints_task = retrieve_structured_tool(
                state,
                container.retrieval,
                product=scenario.product_type,
                issue=scenario.issue_type,
            )

        docs_result, complaints_result = await asyncio.gather(
            retrieve_docs_tool(state, container.retrieval),
            complaints_task,
        )

        merged: dict = {}
        merged.update(docs_result)  # type: ignore[arg-type]
        merged.update(complaints_result)  # type: ignore[arg-type]
        return merged

    return retrieve_phase_node


def _build_analysis_phase_node(container: ServicesContainer):
    async def analysis_phase_node(state: AgentState) -> dict:
        return await summarise_tool(state, container.llm, container.prompt_service)
    return analysis_phase_node


def _build_synthesis_phase_node(container: ServicesContainer):
    async def synthesis_phase_node(state: AgentState) -> dict:
        return await synthesise_answer_tool(state, container.llm, container.prompt_service)
    return synthesis_phase_node


def build_graph(container: ServicesContainer) -> Any:
    """Build and compile the LangGraph StateGraph. Returns a compiled graph."""
    logger.info("graph_build", extra={"graph_name": GRAPH_NAME})
    graph: StateGraph = StateGraph(AgentState)

    graph.add_node("ingest_input", _wrap_node("ingest_input", _ingest_input_node))
    graph.add_node("compress_history", _wrap_node("compress_history", _build_compress_history_node(container)))
    graph.add_node("scenario_phase", _wrap_node("scenario_phase", _build_scenario_phase_node(container)))
    graph.add_node("retrieve_phase", _wrap_node("retrieve_phase", _build_retrieve_phase_node(container)))
    graph.add_node("analysis_phase", _wrap_node("analysis_phase", _build_analysis_phase_node(container)))
    graph.add_node("synthesis_phase", _wrap_node("synthesis_phase", _build_synthesis_phase_node(container)))

    graph.add_edge(START, "ingest_input")
    graph.add_edge("ingest_input", "compress_history")
    graph.add_edge("compress_history", "scenario_phase")
    graph.add_edge("scenario_phase", "retrieve_phase")
    graph.add_edge("retrieve_phase", "analysis_phase")
    graph.add_edge("analysis_phase", "synthesis_phase")
    graph.add_edge("synthesis_phase", END)

    return graph.compile()
