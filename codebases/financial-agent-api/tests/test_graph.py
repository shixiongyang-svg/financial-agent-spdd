from __future__ import annotations
import pytest
from financial_agent_api.agent.graph import build_graph
from financial_agent_api.agent.state import AgentState
from financial_agent_api.models.retrieval import DocumentChunk, ComplaintRow


class _FakeRetrieval:
    async def retrieve_docs(self, *a, **kw): return []
    async def retrieve_complaints(self, *a, **kw): return []


class _FakeLLM:
    async def complete(self, messages, **kw): return "test answer"
    async def embed(self, text, **kw): return [0.1, 0.2]


class _FakeContainer:
    retrieval = _FakeRetrieval()
    llm = _FakeLLM()


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


@pytest.mark.asyncio
async def test_graph_raises_when_both_retrievals_fail():
    class _FailingRetrieval:
        async def retrieve_docs(self, *a, **kw): raise RuntimeError("docs DB down")
        async def retrieve_complaints(self, *a, **kw): raise RuntimeError("complaints DB down")

    class _ContainerWithFailingRetrieval:
        retrieval = _FailingRetrieval()
        llm = _FakeLLM()

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
