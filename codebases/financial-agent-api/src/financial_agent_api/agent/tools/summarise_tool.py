from __future__ import annotations
import logging
from ...agent.state import AgentState
from ...services.llm_service import LLMService
from ...core.prompt_service import PromptService

logger = logging.getLogger(__name__)


async def summarise_tool(
    state: AgentState,
    llm: LLMService,
    prompt_service: PromptService,
) -> dict:
    """Compress retrieved context into analysis_notes. Returns partial AgentState dict.

    Note: 字段映射 - analysis_notes ← summarization node output（见 Task 4 决议 5）
    """
    docs = state.get("retrieved_docs") or []
    complaints = state.get("structured_results") or []

    if not docs and not complaints:
        return {"analysis_notes": "No relevant context found."}

    # 渲染 summarization.j2 模板
    summary_prompt = prompt_service.render(
        "summarization.j2",
        user_query=state["user_query"],
        conversation_history=state.get("conversation_history") or [],
        retrieved_docs=docs,
        retrieved_complaints=complaints,
    )

    notes = await llm.complete(
        [{"role": "user", "content": summary_prompt}],
        request_id=state["request_id"],
    )
    if not notes or not notes.strip():
        raise ValueError("summarise_tool: LLM returned empty analysis_notes")
    return {"analysis_notes": notes.strip()}
