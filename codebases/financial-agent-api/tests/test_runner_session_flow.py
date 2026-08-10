from __future__ import annotations

from typing import Any

import pytest

from financial_agent_api.agent.runner import AgentRunner
from financial_agent_api.agent.state import AgentState


class _FakeSessionStore:
    def __init__(self, history: list[dict[str, Any]] | None = None) -> None:
        self.history = list(history or [])
        self.saved_histories: list[list[dict[str, Any]]] = []
        self.loaded_session_id: str | None = None

    def load_or_create_session(
        self,
        *,
        session_id: str | None,
    ) -> tuple[str, list[dict]]:
        self.loaded_session_id = session_id
        resolved_session_id = session_id or "generated-session"
        base_history = list(self.history) if session_id is not None else []
        return resolved_session_id, base_history

    def save_history(self, session_id: str, conversation_history: list[dict]) -> None:
        self.saved_histories.append(list(conversation_history))
        self.history = list(conversation_history)


class _FakeGraph:
    def __init__(self, final_state: AgentState) -> None:
        self.final_state = final_state
        self.initial_state: AgentState | None = None

    async def ainvoke(self, initial_state: AgentState) -> AgentState:
        self.initial_state = initial_state
        return self.final_state


@pytest.mark.asyncio
async def test_runner_creates_session_when_missing_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    session_store = _FakeSessionStore()
    fake_graph = _FakeGraph(
        {
            "request_id": "req-runner",
            "session_id": "generated-session",
            "user_query": "Need help",
            "conversation_history": [
                {"role": "user", "content": "Need help"},
                {"role": "assistant", "content": "final answer"},
            ],
            "safety_decision": None,
            "retrieved_docs": [],
            "structured_results": [],
            "scenario": None,
            "analysis_notes": "",
            "final_answer": "final answer",
            "error": None,
        }
    )

    class _FakeRunnerContainer:
        def __init__(self, session_store: _FakeSessionStore) -> None:
            self.session_store = session_store

    monkeypatch.setattr("financial_agent_api.agent.runner.build_graph", lambda _container: fake_graph)

    runner = AgentRunner(_FakeRunnerContainer(session_store))  # type: ignore[arg-type]
    result = await runner.run(
        user_query="Need help",
        session_id=None,
        request_id="req-runner",
    )

    assert session_store.loaded_session_id is None
    assert result["session_id"] == "generated-session"
    assert result["conversation_history"] == [
        {"role": "user", "content": "Need help"},
        {"role": "assistant", "content": "final answer"},
    ]
    assert session_store.saved_histories[0] == [{"role": "user", "content": "Need help"}]


@pytest.mark.asyncio
async def test_runner_loads_history_and_persists_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    session_store = _FakeSessionStore(history=[{"role": "assistant", "content": "previous"}])
    fake_graph = _FakeGraph(
        {
            "request_id": "req-runner",
            "session_id": "generated-session",
            "user_query": "Need help",
            "conversation_history": [
                {"role": "assistant", "content": "previous"},
                {"role": "user", "content": "Need help"},
                {"role": "assistant", "content": "final answer"},
            ],
            "safety_decision": None,
            "retrieved_docs": [],
            "structured_results": [],
            "scenario": None,
            "analysis_notes": "",
            "final_answer": "final answer",
            "error": None,
        }
    )

    class _FakeRunnerContainer:
        def __init__(self, session_store: _FakeSessionStore) -> None:
            self.session_store = session_store

    def _fake_build_graph(_container: Any) -> _FakeGraph:
        return fake_graph

    monkeypatch.setattr("financial_agent_api.agent.runner.build_graph", _fake_build_graph)

    runner = AgentRunner(_FakeRunnerContainer(session_store))  # type: ignore[arg-type]
    result = await runner.run(
        user_query="Need help",
        session_id="existing-session",
        request_id="req-runner",
    )

    assert session_store.loaded_session_id == "existing-session"
    assert session_store.saved_histories[0] == [
        {"role": "assistant", "content": "previous"},
        {"role": "user", "content": "Need help"},
    ]
    assert session_store.saved_histories[-1] == [
        {"role": "assistant", "content": "previous"},
        {"role": "user", "content": "Need help"},
        {"role": "assistant", "content": "final answer"},
    ]
    assert result["session_id"] == "existing-session"
    assert result["conversation_history"][-1]["content"] == "final answer"
    assert fake_graph.initial_state is not None
    assert fake_graph.initial_state["conversation_history"][0]["content"] == "previous"
