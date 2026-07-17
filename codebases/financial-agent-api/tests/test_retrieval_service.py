from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from financial_agent_api.services.retrieval_service import RetrievalService


class _FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.last_params: dict[str, Any] | None = None

    def execute(self, _sql: Any, params: dict[str, Any]) -> _FakeResult:
        self.last_params = params
        return _FakeResult(self._rows)


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> "_FakeSessionFactory":
        return self

    def __enter__(self) -> _FakeSession:
        return self._session

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        return None


class _FakeLLM:
    def __init__(self, embedding: Sequence[float]) -> None:
        self._embedding = list(embedding)

    async def embed(self, _query: str, *, request_id: str | None = None) -> list[float]:
        assert request_id in (None, "req-1")
        return self._embedding


@pytest.mark.asyncio
async def test_retrieve_docs_projects_rows_to_document_chunk() -> None:
    session = _FakeSession(
        [
            {
                "doc_id": 7,
                "source_file": "guide.md",
                "chunk_index": 2,
                "content": "chunk",
                "similarity": 0.88,
            }
        ]
    )
    service = RetrievalService(_FakeSessionFactory(session), _FakeLLM([0.1, 0.2, 0.3]))  # type: ignore[arg-type]

    rows = await service.retrieve_docs("hello", request_id="req-1")
    assert len(rows) == 1
    assert rows[0].doc_id == 7
    assert session.last_params == {"query_vector": "[0.1,0.2,0.3]", "limit": 5}


@pytest.mark.asyncio
async def test_retrieve_complaints_projects_rows_to_complaint_row() -> None:
    session = _FakeSession(
        [
            {
                "complaint_id": "C1",
                "date_received": None,
                "product": "Credit card",
                "issue": "fees",
                "company": "Bank",
                "state": "CA",
                "submitted_via": "Web",
                "narrative": "details",
            }
        ]
    )
    service = RetrievalService(_FakeSessionFactory(session), _FakeLLM([0.0]))  # type: ignore[arg-type]

    rows = await service.retrieve_complaints("fees", product="credit")
    assert len(rows) == 1
    assert rows[0].complaint_id == "C1"
    assert session.last_params == {
        "query_pattern": "%fees%",
        "product_pattern": "%credit%",
        "product_filter_enabled": True,
        "limit": 10,
    }
