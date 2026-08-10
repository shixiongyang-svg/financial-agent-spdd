from __future__ import annotations
import logging
from ...agent.state import AgentState
from ...services.llm_service import LLMService
from ...core.prompt_service import PromptService

logger = logging.getLogger(__name__)


async def synthesise_answer_tool(
    state: AgentState,
    llm: LLMService,
    prompt_service: PromptService,
) -> dict:
    """Generate the final grounded answer. Returns partial AgentState dict. LLMProviderError propagates.

    Note: 字段映射 - final_answer ← synthesise node output（见 Task 4 决议 5）
    """
    analysis_notes = state.get("analysis_notes") or "No relevant context found."

    # 渲染 synthesise.j2 模板
    synthesis_prompt = prompt_service.render(
        "synthesise.j2",
        user_query=state["user_query"],
        summarization=analysis_notes,
    )

    answer = await llm.complete(
        [{"role": "user", "content": synthesis_prompt}],
        request_id=state["request_id"],
    )
    if not answer or not answer.strip():
        raise ValueError("synthesise_answer_tool: LLM returned empty final_answer")
    return {"final_answer": answer.strip()}
