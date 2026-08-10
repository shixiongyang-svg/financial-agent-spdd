from __future__ import annotations
from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class AgentQueryResponse(BaseModel):
    answer: str
    request_id: str
    session_id: str
    conversation_history: list[dict]
    retrieved_doc_ids: list[int]
    retrieved_complaint_ids: list[str]
