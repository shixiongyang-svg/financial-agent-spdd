from __future__ import annotations
import pytest
from financial_agent_api.agent.state import AgentState
from financial_agent_api.agent.tools.retrieve_docs_tool import retrieve_docs_tool
from financial_agent_api.agent.tools.retrieve_structured_tool import retrieve_structured_tool
from financial_agent_api.agent.tools.summarise_tool import summarise_tool
from financial_agent_api.agent.tools.synthesise_answer_tool import synthesise_answer_tool
from financial_agent_api.models.retrieval import DocumentChunk, ComplaintRow


def _make_state(**overrides) -> AgentState:
    base: AgentState = {
        "request_id": "req-test",
        "session_id": None,
        "user_query": "What is an overdraft fee?",
        "conversation_history": [],
        "safety_decision": None,
        "retrieved_docs": [],
        "structured_results": [],
        "scenario": None,
        "analysis_notes": "",
        "final_answer": None,
        "error": None,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class _FakeRetrieval:
    def __init__(self, docs=None, complaints=None):
        self._docs = docs or []
        self._complaints = complaints or []

    async def retrieve_docs(self, query, *, request_id=None, limit=5):
        return self._docs

    async def retrieve_complaints(self, query, *, request_id=None, limit=10, product=None):
        return self._complaints


class _FakeLLM:
    def __init__(self, response="summary text"):
        self._response = response

    async def complete(self, messages, *, model=None, temperature=0.0, max_tokens=None, response_format=None, request_id=None):
        return self._response


_DOC = DocumentChunk(doc_id=1, source_file="test.txt", chunk_index=0, content="overdraft info", similarity=0.9)
_COMPLAINT = ComplaintRow(complaint_id="C1", product="Checking", issue="overdraft fee", company="Bank A")


@pytest.mark.asyncio
async def test_retrieve_docs_tool_returns_docs():
    retrieval = _FakeRetrieval(docs=[_DOC])
    result = await retrieve_docs_tool(_make_state(), retrieval)  # type: ignore[arg-type]
    assert result == {"retrieved_docs": [_DOC]}


@pytest.mark.asyncio
async def test_retrieve_docs_tool_returns_empty_on_failure():
    class _FailingRetrieval:
        async def retrieve_docs(self, *a, **kw): raise RuntimeError("DB error")
    result = await retrieve_docs_tool(_make_state(), _FailingRetrieval())  # type: ignore[arg-type]
    assert result["retrieved_docs"] == []
    assert "error" in result


@pytest.mark.asyncio
async def test_retrieve_structured_tool_returns_complaints():
    retrieval = _FakeRetrieval(complaints=[_COMPLAINT])
    result = await retrieve_structured_tool(_make_state(), retrieval)  # type: ignore[arg-type]
    assert result == {"structured_results": [_COMPLAINT]}


@pytest.mark.asyncio
async def test_retrieve_structured_tool_returns_empty_on_failure():
    class _FailingRetrieval:
        async def retrieve_complaints(self, *a, **kw): raise RuntimeError("DB error")
    result = await retrieve_structured_tool(_make_state(), _FailingRetrieval())  # type: ignore[arg-type]
    assert result["structured_results"] == []
    assert "error" in result


@pytest.mark.asyncio
async def test_summarise_tool_skips_llm_when_no_context():
    llm = _FakeLLM()
    result = await summarise_tool(_make_state(), llm)  # type: ignore[arg-type]
    assert result == {"analysis_notes": "No relevant context found."}


@pytest.mark.asyncio
async def test_summarise_tool_calls_llm_with_context():
    state = _make_state(retrieved_docs=[_DOC])
    llm = _FakeLLM(response="Key point: overdraft fees apply when balance negative.")
    result = await summarise_tool(state, llm)  # type: ignore[arg-type]
    assert "analysis_notes" in result
    assert result["analysis_notes"] == "Key point: overdraft fees apply when balance negative."


@pytest.mark.asyncio
async def test_synthesise_answer_tool_returns_answer():
    state = _make_state(analysis_notes="Overdraft fee is charged when account goes negative.")
    llm = _FakeLLM(response="An overdraft fee is charged when your account balance goes below zero.")
    result = await synthesise_answer_tool(state, llm)  # type: ignore[arg-type]
    assert result["final_answer"] == "An overdraft fee is charged when your account balance goes below zero."
