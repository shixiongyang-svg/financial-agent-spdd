from __future__ import annotations
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from financial_agent_api.main import app
from financial_agent_api.agent.state import AgentState
from financial_agent_api.core.exceptions import LLMProviderError


def _make_final_state() -> AgentState:
    return {
        "request_id": "req-endpoint-test",
        "session_id": None,
        "user_query": "What is an overdraft fee?",
        "conversation_history": [],
        "safety_decision": None,
        "retrieved_docs": [],
        "structured_results": [],
        "scenario": None,
        "analysis_notes": "Overdraft fees context.",
        "final_answer": "An overdraft fee is charged when your account balance goes below zero.",
        "error": None,
    }


def test_agent_query_happy_path():
    with patch("financial_agent_api.routers.agent.AgentRunner") as _mock_cls:
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(return_value=_make_final_state())
        with TestClient(app) as client:
            app.state.runner = mock_runner
            response = client.post(
                "/agent/query",
                json={"question": "What is an overdraft fee?"},
            )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] != ""
    assert "request_id" in data
    assert "X-Request-Id" in response.headers


def test_agent_query_llm_error_returns_502():
    with TestClient(app) as client:
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(
            side_effect=LLMProviderError(
                provider="openrouter",
                status_code=503,
                payload="Service unavailable",
                request_id="req-502-test",
            )
        )
        app.state.runner = mock_runner
        response = client.post(
            "/agent/query",
            json={"question": "What is an overdraft fee?"},
        )
    assert response.status_code == 502
    data = response.json()
    assert data["error_code"] == "llm_provider_error"
    assert "message" in data
    assert "request_id" in data
    assert "X-Request-Id" in response.headers


def test_agent_query_rejects_empty_question():
    with TestClient(app) as client:
        response = client.post("/agent/query", json={"question": ""})
    assert response.status_code == 422


def test_agent_query_rejects_too_long_question():
    with TestClient(app) as client:
        response = client.post("/agent/query", json={"question": "a" * 2001})
    assert response.status_code == 422
