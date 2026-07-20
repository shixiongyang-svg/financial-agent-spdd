from __future__ import annotations
import logging
from ...agent.state import AgentState
from ...services.llm_service import LLMService

logger = logging.getLogger(__name__)


async def summarise_tool(
    state: AgentState,
    llm: LLMService,
) -> dict:
    """Compress retrieved context into analysis_notes. Returns partial AgentState dict."""
    docs = state.get("retrieved_docs") or []
    complaints = state.get("structured_results") or []

    if not docs and not complaints:
        return {"analysis_notes": "No relevant context found."}

    docs_text = "\n\n".join(
        f"[Document {d.source_file} chunk {d.chunk_index}]\n{d.content}"
        for d in docs
    )
    complaints_text = "\n\n".join(
        f"[Complaint {c.complaint_id} | {c.product} | {c.company}]\nIssue: {c.issue}\nNarrative: {c.narrative or '(none)'}"
        for c in complaints
    )

    # TODO: migrate to prompts/summarise.j2 in Week 4
    system_prompt = (
        "You are a financial helpdesk assistant. "
        "Summarise the retrieved context into concise notes that will help answer the user question. "
        "Focus only on facts relevant to the question. Be brief."
    )
    user_prompt = (
        f"User question: {state['user_query']}\n\n"
        f"=== Retrieved documents ===\n{docs_text or '(none)'}\n\n"
        f"=== Retrieved complaints ===\n{complaints_text or '(none)'}\n\n"
        "Provide a concise summary of key relevant information."
    )

    notes = await llm.complete(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        request_id=state["request_id"],
    )
    if not notes or not notes.strip():
        raise ValueError("summarise_tool: LLM returned empty analysis_notes")
    return {"analysis_notes": notes.strip()}
