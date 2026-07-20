from __future__ import annotations
from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    conversation_history: list[dict] = []


class AgentQueryResponse(BaseModel):
    answer: str
    request_id: str
    retrieved_doc_ids: list[int]
    retrieved_complaint_ids: list[str]
