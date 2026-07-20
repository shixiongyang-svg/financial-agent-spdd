from __future__ import annotations
from typing import TypedDict
from ..models.retrieval import DocumentChunk, ComplaintRow
from ..models.safety import SafetyDecision
from ..models.scenario import Scenario


class AgentState(TypedDict):
    request_id: str
    session_id: str | None
    user_query: str
    conversation_history: list[dict]
    safety_decision: SafetyDecision | None   # reserved, always None this week
    retrieved_docs: list[DocumentChunk]
    structured_results: list[ComplaintRow]
    scenario: Scenario | None                # reserved, always None this week
    analysis_notes: str
    final_answer: str | None
    error: str | None
