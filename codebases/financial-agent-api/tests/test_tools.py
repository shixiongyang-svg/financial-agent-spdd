from __future__ import annotations
import pytest
from financial_agent_api.agent.state import AgentState
from financial_agent_api.agent.history_compression import compress_history
from financial_agent_api.agent.tools.retrieve_docs_tool import retrieve_docs_tool
from financial_agent_api.agent.tools.retrieve_structured_tool import retrieve_structured_tool
from financial_agent_api.agent.tools.scenario_extraction_tool import scenario_extraction_tool
from financial_agent_api.agent.tools.summarise_tool import summarise_tool
from financial_agent_api.agent.tools.synthesise_answer_tool import synthesise_answer_tool
from financial_agent_api.core.exceptions import LLMOutputValidationError
from financial_agent_api.core.exceptions import LLMProviderError
from financial_agent_api.core.exceptions import ScenarioFeedbackRequired
from financial_agent_api.core.config import Settings
from financial_agent_api.core.prompt_service import PromptService
from financial_agent_api.models.retrieval import DocumentChunk, ComplaintRow


def _make_state(**overrides) -> AgentState:
    base: AgentState = {
        "request_id": "req-test",
        "session_id": None,
        "user_query": "What is an overdraft fee?",
        "conversation_history": [],
        "safety_decision": None,
        "retrieved_docs": [],
        "structured_results": [],
        "scenario": None,
        "analysis_notes": "",
        "final_answer": None,
        "error": None,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class _FakeRetrieval:
    def __init__(self, docs=None, complaints=None):
        self._docs = docs or []
        self._complaints = complaints or []

    async def retrieve_docs(self, query, *, request_id=None, limit=5):
        return self._docs

    async def retrieve_complaints(self, query, *, request_id=None, limit=10, product=None, issue=None):
        return self._complaints


class _FakeLLM:
    def __init__(self, response="summary text"):
        self._response = response
        self.calls = 0
        self.models: list[str | None] = []

    async def complete(self, messages, *, model=None, temperature=0.0, max_tokens=None, response_format=None, request_id=None):
        self.calls += 1
        self.models.append(model)
        return self._response


class _FakeProductIssueService:
    def __init__(self, mapping):
        self._mapping = mapping

    def get_allowed_product_issue_map(self):
        return self._mapping


_PROMPT_SERVICE = PromptService()


_DOC = DocumentChunk(doc_id=1, source_file="test.txt", chunk_index=0, content="overdraft info", similarity=0.9)
_COMPLAINT = ComplaintRow(complaint_id="C1", product="Checking", issue="overdraft fee", company="Bank A")


@pytest.mark.asyncio
async def test_retrieve_docs_tool_returns_docs():
    retrieval = _FakeRetrieval(docs=[_DOC])
    result = await retrieve_docs_tool(_make_state(), retrieval)  # type: ignore[arg-type]
    assert result == {"retrieved_docs": [_DOC]}


@pytest.mark.asyncio
async def test_retrieve_docs_tool_raises_on_failure():
    class _FailingRetrieval:
        async def retrieve_docs(self, *a, **kw): raise RuntimeError("DB error")
    with pytest.raises(RuntimeError, match="DB error"):
        await retrieve_docs_tool(_make_state(), _FailingRetrieval())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_retrieve_structured_tool_returns_complaints():
    retrieval = _FakeRetrieval(complaints=[_COMPLAINT])
    result = await retrieve_structured_tool(_make_state(), retrieval)  # type: ignore[arg-type]
    assert result == {"structured_results": [_COMPLAINT]}


@pytest.mark.asyncio
async def test_retrieve_structured_tool_raises_on_failure():
    class _FailingRetrieval:
        async def retrieve_complaints(self, *a, **kw): raise RuntimeError("DB error")
    with pytest.raises(RuntimeError, match="DB error"):
        await retrieve_structured_tool(_make_state(), _FailingRetrieval())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_summarise_tool_skips_llm_when_no_context():
    llm = _FakeLLM()
    result = await summarise_tool(_make_state(), llm, _PROMPT_SERVICE)  # type: ignore[arg-type]
    assert result == {"analysis_notes": "No relevant context found."}


@pytest.mark.asyncio
async def test_summarise_tool_calls_llm_with_context():
    state = _make_state(retrieved_docs=[_DOC])
    llm = _FakeLLM(response="Key point: overdraft fees apply when balance negative.")
    result = await summarise_tool(state, llm, _PROMPT_SERVICE)  # type: ignore[arg-type]
    assert "analysis_notes" in result
    assert result["analysis_notes"] == "Key point: overdraft fees apply when balance negative."


@pytest.mark.asyncio
async def test_synthesise_answer_tool_returns_answer():
    state = _make_state(analysis_notes="Overdraft fee is charged when account goes negative.")
    llm = _FakeLLM(response="An overdraft fee is charged when your account balance goes below zero.")
    result = await synthesise_answer_tool(state, llm, _PROMPT_SERVICE)  # type: ignore[arg-type]
    assert result["final_answer"] == "An overdraft fee is charged when your account balance goes below zero."


@pytest.mark.asyncio
async def test_compress_history_rewrites_long_history() -> None:
    state = _make_state(
        conversation_history=[
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
            {"role": "assistant", "content": "four"},
            {"role": "user", "content": "five"},
            {"role": "assistant", "content": "six"},
        ]
    )
    llm = _FakeLLM(response='{"summary_text":"summary","confidence":0.9}')
    settings = Settings(compress_threshold=5, compress_confidence_threshold=0.7)

    result = await compress_history(state, llm, _PROMPT_SERVICE, settings)  # type: ignore[arg-type]

    assert "conversation_history" in result
    assert len(result["conversation_history"]) == 3
    assert result["conversation_history"][0]["content"].startswith("[compressed history]")


@pytest.mark.asyncio
async def test_compress_history_uses_compress_ops_model_for_openrouter() -> None:
    state = _make_state(
        conversation_history=[
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "two"},
            {"role": "user", "content": "three"},
            {"role": "assistant", "content": "four"},
            {"role": "user", "content": "five"},
            {"role": "assistant", "content": "six"},
        ]
    )
    llm = _FakeLLM(response='{"summary_text":"summary","confidence":0.9}')
    settings = Settings(
        llm_provider="openrouter",
        compress_threshold=5,
        compress_ops_model="custom-compress-model",
        compress_confidence_threshold=0.7,
    )

    result = await compress_history(state, llm, _PROMPT_SERVICE, settings)  # type: ignore[arg-type]

    assert result["conversation_history"][0]["content"].startswith("[compressed history]")
    assert llm.models == ["custom-compress-model"]


@pytest.mark.asyncio
async def test_scenario_extraction_tool_returns_scenario() -> None:
    state = _make_state(
        conversation_history=[{"role": "user", "content": "fees on my credit card?"}]
    )
    llm = _FakeLLM(response='{"product_type":"credit_card","issue_type":"fees","confidence":0.9}')
    settings = Settings()
    product_issue_service = _FakeProductIssueService({"credit_card": ["fees", "interest_rate"]})

    result = await scenario_extraction_tool(
        state,
        llm,
        _PROMPT_SERVICE,
        product_issue_service,
        settings,
    )  # type: ignore[arg-type]

    assert result["scenario"].product_type == "credit_card"
    assert result["scenario"].issue_type == "fees"
    assert result["scenario"].confidence == 0.9


@pytest.mark.asyncio
async def test_scenario_extraction_tool_returns_none_only_when_mapping_empty() -> None:
    state = _make_state(
        conversation_history=[{"role": "user", "content": "fees on my credit card?"}]
    )
    llm = _FakeLLM(response='{"product_type":"credit_card","issue_type":"fees","confidence":0.9}')
    settings = Settings()
    product_issue_service = _FakeProductIssueService({})

    result = await scenario_extraction_tool(
        state,
        llm,
        _PROMPT_SERVICE,
        product_issue_service,
        settings,
    )  # type: ignore[arg-type]

    assert result == {"scenario": None}
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_scenario_extraction_tool_rejects_issue_without_product() -> None:
    state = _make_state(
        conversation_history=[{"role": "user", "content": "I have a billing question"}]
    )
    llm = _FakeLLM(response='{"product_type":null,"issue_type":"fees","confidence":0.9}')
    settings = Settings()
    product_issue_service = _FakeProductIssueService({"credit_card": ["fees", "interest_rate"]})

    with pytest.raises(LLMOutputValidationError):
        await scenario_extraction_tool(
            state,
            llm,
            _PROMPT_SERVICE,
            product_issue_service,
            settings,
        )  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_scenario_extraction_tool_retries_only_validation_errors() -> None:
    state = _make_state(
        conversation_history=[{"role": "user", "content": "fees on my credit card?"}]
    )

    class _RetryableLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, messages, *, model=None, temperature=0.0, max_tokens=None, response_format=None, request_id=None):
            self.calls += 1
            if self.calls == 1:
                return "not json"
            return '{"product_type":"credit_card","issue_type":"fees","confidence":0.9}'

    llm = _RetryableLLM()
    settings = Settings()
    product_issue_service = _FakeProductIssueService({"credit_card": ["fees", "interest_rate"]})

    result = await scenario_extraction_tool(
        state,
        llm,  # type: ignore[arg-type]
        _PROMPT_SERVICE,
        product_issue_service,
        settings,
    )

    assert llm.calls == 2
    assert result["scenario"].product_type == "credit_card"
    assert result["scenario"].issue_type == "fees"
    assert result["scenario"].confidence == 0.9


@pytest.mark.asyncio
async def test_scenario_extraction_tool_does_not_retry_provider_errors() -> None:
    state = _make_state(
        conversation_history=[{"role": "user", "content": "fees on my credit card?"}]
    )

    class _ProviderErrorLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, messages, *, model=None, temperature=0.0, max_tokens=None, response_format=None, request_id=None):
            self.calls += 1
            raise LLMProviderError("openrouter", 400, "bad request", "req-test")

    llm = _ProviderErrorLLM()
    settings = Settings()
    product_issue_service = _FakeProductIssueService({"credit_card": ["fees", "interest_rate"]})

    with pytest.raises(LLMProviderError, match="status_code=400"):
        await scenario_extraction_tool(
            state,
            llm,  # type: ignore[arg-type]
            _PROMPT_SERVICE,
            product_issue_service,
            settings,
        )

    assert llm.calls == 1


@pytest.mark.asyncio
async def test_scenario_extraction_tool_returns_feedback_after_validation_failures() -> None:
    state = _make_state(
        session_id="session-feedback",
        conversation_history=[{"role": "user", "content": "I need help"}],
    )

    class _BadLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, messages, *, model=None, temperature=0.0, max_tokens=None, response_format=None, request_id=None):
            self.calls += 1
            if self.calls < 3:
                return "not json"
            return "Please clarify the product and issue."

    llm = _BadLLM()
    settings = Settings()
    product_issue_service = _FakeProductIssueService({"credit_card": ["fees", "interest_rate"]})

    with pytest.raises(ScenarioFeedbackRequired) as exc_info:
        await scenario_extraction_tool(
            state,
            llm,  # type: ignore[arg-type]
            _PROMPT_SERVICE,
            product_issue_service,
            settings,
        )

    assert llm.calls == 3
    assert exc_info.value.message == "Please clarify the product and issue."
    assert exc_info.value.session_id == "session-feedback"
