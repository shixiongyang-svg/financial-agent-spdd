from __future__ import annotations
import io
import json
import sys

import pytest
from financial_agent_api.agent.graph import build_graph
from financial_agent_api.agent.state import AgentState
from financial_agent_api.core.config import Settings
from financial_agent_api.core.logging import configure_logging, reset_request_id, bind_request_id
from financial_agent_api.core.prompt_service import PromptService
from financial_agent_api.models.scenario import Scenario


class _FakeRetrieval:
    def __init__(self) -> None:
        self.docs_calls = 0
        self.complaints_calls = 0

    async def retrieve_docs(self, *a, **kw):
        self.docs_calls += 1
        return []

    async def retrieve_complaints(self, *a, **kw):
        self.complaints_calls += 1
        return []


class _FakeLLM:
    async def complete(self, messages, **kw): return "test answer"
    async def embed(self, text, **kw): return [0.1, 0.2]


class _FakeContainer:
    def __init__(self) -> None:
        self.retrieval = _FakeRetrieval()
        self.llm = _FakeLLM()
        self.prompt_service = PromptService()
        self.settings = Settings()


@pytest.mark.asyncio
async def test_graph_produces_final_answer():
    container = _FakeContainer()
    graph = build_graph(container)  # type: ignore[arg-type]
    initial: AgentState = {
        "request_id": "req-graph-test",
        "session_id": None,
        "user_query": "What is a late fee?",
        "conversation_history": [],
        "safety_decision": None,
        "retrieved_docs": [],
        "structured_results": [],
        "scenario": None,
        "analysis_notes": "",
        "final_answer": None,
        "error": None,
    }
    result = await graph.ainvoke(initial)
    assert result["final_answer"] == "test answer"
    assert result["user_query"] == "What is a late fee?"
    assert container.retrieval.complaints_calls == 0


@pytest.mark.asyncio
async def test_graph_skips_complaints_when_scenario_missing():
    container = _FakeContainer()
    graph = build_graph(container)  # type: ignore[arg-type]
    initial: AgentState = {
        "request_id": "req-graph-test-skip",
        "session_id": None,
        "user_query": "What is a late fee?",
        "conversation_history": [],
        "safety_decision": None,
        "retrieved_docs": [],
        "structured_results": [],
        "scenario": None,
        "analysis_notes": "",
        "final_answer": None,
        "error": None,
    }
    result = await graph.ainvoke(initial)
    assert result["final_answer"] == "test answer"
    assert container.retrieval.docs_calls == 1
    assert container.retrieval.complaints_calls == 0


@pytest.mark.asyncio
async def test_graph_raises_when_both_retrievals_fail():
    class _FailingRetrieval:
        async def retrieve_docs(self, *a, **kw): raise RuntimeError("docs DB down")
        async def retrieve_complaints(self, *a, **kw): raise RuntimeError("complaints DB down")

    class _ContainerWithFailingRetrieval:
        retrieval = _FailingRetrieval()
        llm = _FakeLLM()
        prompt_service = PromptService()
        settings = Settings()

    graph = build_graph(_ContainerWithFailingRetrieval())  # type: ignore[arg-type]
    initial: AgentState = {
        "request_id": "req-fail-test",
        "session_id": None,
        "user_query": "test question",
        "conversation_history": [],
        "safety_decision": None,
        "retrieved_docs": [],
        "structured_results": [],
        "scenario": None,
        "analysis_notes": "",
        "final_answer": None,
        "error": None,
    }
    with pytest.raises(Exception):
        await graph.ainvoke(initial)


@pytest.mark.asyncio
async def test_graph_raises_when_docs_retrieval_fails():
    class _FailingDocsRetrieval:
        async def retrieve_docs(self, *a, **kw):
            raise RuntimeError("docs DB down")

        async def retrieve_complaints(self, *a, **kw):
            return []

    class _ContainerWithFailingDocs:
        retrieval = _FailingDocsRetrieval()
        llm = _FakeLLM()
        prompt_service = PromptService()
        settings = Settings()

    graph = build_graph(_ContainerWithFailingDocs())  # type: ignore[arg-type]
    initial: AgentState = {
        "request_id": "req-docs-fail-test",
        "session_id": None,
        "user_query": "test question",
        "conversation_history": [],
        "safety_decision": None,
        "retrieved_docs": [],
        "structured_results": [],
        "scenario": None,
        "analysis_notes": "",
        "final_answer": None,
        "error": None,
    }
    with pytest.raises(RuntimeError, match="docs DB down"):
        await graph.ainvoke(initial)


@pytest.mark.asyncio
async def test_graph_raises_when_complaints_retrieval_fails():
    class _FailingComplaintsRetrieval:
        async def retrieve_docs(self, *a, **kw):
            return []

        async def retrieve_complaints(self, *a, **kw):
            raise RuntimeError("complaints DB down")

    class _ContainerWithFailingComplaints:
        retrieval = _FailingComplaintsRetrieval()
        llm = _FakeLLM()
        prompt_service = PromptService()
        settings = Settings()

    graph = build_graph(_ContainerWithFailingComplaints())  # type: ignore[arg-type]
    initial: AgentState = {
        "request_id": "req-complaints-fail-test",
        "session_id": None,
        "user_query": "test question",
        "conversation_history": [],
        "safety_decision": None,
        "retrieved_docs": [],
        "structured_results": [],
        "scenario": Scenario(product_type="credit_card", issue_type=None, confidence=0.95),
        "analysis_notes": "",
        "final_answer": None,
        "error": None,
    }
    with pytest.raises(RuntimeError, match="complaints DB down"):
        await graph.ainvoke(initial)


@pytest.mark.asyncio
async def test_graph_emits_debug_state_logs(monkeypatch: pytest.MonkeyPatch):
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)
    configure_logging("json", level="DEBUG")

    token = bind_request_id("req-debug-graph")
    try:
        container = _FakeContainer()
        graph = build_graph(container)  # type: ignore[arg-type]
        initial: AgentState = {
            "request_id": "req-debug-graph",
            "session_id": None,
            "user_query": "What is a late fee?",
            "conversation_history": [],
            "safety_decision": None,
            "retrieved_docs": [],
            "structured_results": [],
            "scenario": None,
            "analysis_notes": "",
            "final_answer": None,
            "error": None,
        }
        result = await graph.ainvoke(initial)
    finally:
        reset_request_id(token)

    logs = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    events = [item["event"] for item in logs]
    assert "graph_build" in events
    assert "graph_node_enter" in events
    assert "graph_node_exit" in events

    enter_log = next(item for item in logs if item["event"] == "graph_node_enter" and item["node_name"] == "ingest_input")
    assert enter_log["graph_name"] == "financial_helpdesk_agent"
    assert enter_log["state"]["user_query"] == "What is a late fee?"

    exit_log = next(item for item in logs if item["event"] == "graph_node_exit" and item["node_name"] == "synthesis_phase")
    assert exit_log["state"]["final_answer"] == "test answer"
    assert result["final_answer"] == "test answer"
