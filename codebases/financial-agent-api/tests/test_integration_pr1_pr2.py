"""Integration test: PromptService and updated tools work together."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from financial_agent_api.core.prompt_service import PromptService
from financial_agent_api.agent.tools.summarise_tool import summarise_tool
from financial_agent_api.agent.tools.synthesise_answer_tool import synthesise_answer_tool
from financial_agent_api.models.scenario import Scenario


class TestIntegrationPromptTools:
    """Integration tests for PromptService with summarise_tool and synthesise_answer_tool."""

    @pytest.fixture
    def prompt_service(self):
        return PromptService()

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLMService."""
        mock = AsyncMock()
        mock.complete = AsyncMock(return_value="Test response from LLM")
        return mock

    def test_scenario_model_fields(self):
        """Test Scenario model has correct fields (3 fields only)."""
        # Create scenario with new format
        scenario = Scenario(
            product_type="credit_card",
            issue_type="interest_rate",
            confidence=0.95,
        )

        # Verify fields
        assert scenario.product_type == "credit_card"
        assert scenario.issue_type == "interest_rate"
        assert scenario.confidence == 0.95

        # Verify old fields don't exist
        assert not hasattr(scenario, "amount")
        assert not hasattr(scenario, "jurisdiction")

    def test_scenario_model_optional_fields(self):
        """Test Scenario model allows null product_type and issue_type."""
        scenario = Scenario(
            product_type=None,
            issue_type=None,
            confidence=0.5,
        )

        assert scenario.product_type is None
        assert scenario.issue_type is None
        assert scenario.confidence == 0.5

    @pytest.mark.asyncio
    async def test_summarise_tool_with_prompt_service(self, mock_llm_service, prompt_service):
        """Test summarise_tool uses PromptService correctly."""
        state = {
            "user_query": "What are my options for credit card interest?",
            "request_id": "test-123",
            "retrieved_docs": [
                MagicMock(
                    source_file="credit_guide.txt",
                    chunk_index=0,
                    content="Credit cards have variable interest rates.",
                )
            ],
            "structured_results": [
                MagicMock(
                    complaint_id="C123",
                    product="credit_card",
                    company="Bank A",
                    issue="high_interest",
                    narrative="User complained about high interest rate.",
                )
            ],
        }

        result = await summarise_tool(state, mock_llm_service, prompt_service)

        # Verify LLM was called
        mock_llm_service.complete.assert_called_once()
        call_args = mock_llm_service.complete.call_args
        messages = call_args[0][0]

        # Verify message structure (should be single user message with rendered template)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "What are my options" in messages[0]["content"]

        # Verify result
        assert result["analysis_notes"] == "Test response from LLM"

    @pytest.mark.asyncio
    async def test_synthesise_tool_with_prompt_service(self, mock_llm_service, prompt_service):
        """Test synthesise_answer_tool uses PromptService correctly."""
        state = {
            "user_query": "What are my options for credit card interest?",
            "request_id": "test-123",
            "analysis_notes": "Bank A offers variable rates from 5% to 25%. User concerned about high rates.",
        }

        result = await synthesise_answer_tool(state, mock_llm_service, prompt_service)

        # Verify LLM was called
        mock_llm_service.complete.assert_called_once()
        call_args = mock_llm_service.complete.call_args
        messages = call_args[0][0]

        # Verify message structure
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "What are my options" in messages[0]["content"]
        assert "5% to 25%" in messages[0]["content"]

        # Verify result
        assert result["final_answer"] == "Test response from LLM"

    @pytest.mark.asyncio
    async def test_tools_with_empty_context(self, mock_llm_service, prompt_service):
        """Test tools handle empty context gracefully."""
        state = {
            "user_query": "Test query",
            "request_id": "test-123",
        }

        result = await summarise_tool(state, mock_llm_service, prompt_service)
        assert result["analysis_notes"] == "No relevant context found."

    def test_prompt_service_templates_exist(self, prompt_service):
        """Verify all required templates are available."""
        assert prompt_service.has_template("scenario_extraction.j2")
        assert prompt_service.has_template("compress_history.j2")
        assert prompt_service.has_template("summarization.j2")
        assert prompt_service.has_template("synthesise.j2")

    def test_prompt_service_verification(self, prompt_service):
        """Test compilation-time template verification."""
        results = prompt_service.verify_templates()

        # All required templates should exist
        assert results["scenario_extraction.j2"] is True
        assert results["compress_history.j2"] is True
        assert results["summarization.j2"] is True
        assert results["synthesise.j2"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
