"""Tests for the /healthz endpoint."""

from fastapi.testclient import TestClient
from financial_agent_api.main import app

client = TestClient(app)


def test_healthz_returns_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
