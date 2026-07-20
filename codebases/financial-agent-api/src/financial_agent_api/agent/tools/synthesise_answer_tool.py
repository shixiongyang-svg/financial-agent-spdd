from __future__ import annotations
import logging
from ...agent.state import AgentState
from ...services.llm_service import LLMService

logger = logging.getLogger(__name__)


async def synthesise_answer_tool(
    state: AgentState,
    llm: LLMService,
) -> dict:
    """Generate the final grounded answer. Returns partial AgentState dict. LLMProviderError propagates."""
    analysis_notes = state.get("analysis_notes") or "No relevant context found."

    # TODO: migrate to prompts/synthesise.j2 in Week 4
    system_prompt = (
        "You are a financial helpdesk assistant. "
        "Answer the user's question using only the provided context notes. "
        "Cite specific documents or complaints where relevant. "
        "If the context does not contain enough information, say so clearly."
    )
    user_prompt = (
        f"User question: {state['user_query']}\n\n"
        f"Context:\n{analysis_notes}\n\n"
        "Provide a clear, factual answer grounded in the context above."
    )

    answer = await llm.complete(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        request_id=state["request_id"],
    )
    if not answer or not answer.strip():
        raise ValueError("synthesise_answer_tool: LLM returned empty final_answer")
    return {"final_answer": answer.strip()}
