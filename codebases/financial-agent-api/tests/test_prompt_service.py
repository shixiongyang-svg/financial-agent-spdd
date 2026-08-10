"""Test PromptService initialization, template loading, and StrictUndefined behavior."""
import pytest

from financial_agent_api.core.prompt_service import PromptService


class TestPromptService:
    """PromptService unit tests."""

    @pytest.fixture
    def service(self):
        """Initialize PromptService for each test."""
        return PromptService()

    def test_init(self, service):
        """Test PromptService initializes without error."""
        assert service is not None
        assert service._TEMPLATES_DIR.exists()

    def test_required_templates_exist(self, service):
        """Test all required templates are found."""
        verification = service.verify_templates()
        for template_name in service._REQUIRED_TEMPLATES:
            assert verification[template_name] is True, f"Required template {template_name} not found"

    def test_template_loading(self, service):
        """Test templates can be loaded."""
        # Try to load each required template (will raise if not found or malformed)
        for template_name in service._REQUIRED_TEMPLATES:
            assert service.has_template(template_name)

    def test_strict_undefined_raises_on_missing_variable(self, service):
        """Test that StrictUndefined raises UndefinedError when variable is missing."""
        from jinja2 import UndefinedError

        with pytest.raises(UndefinedError):
            service.render(
                "scenario_extraction.j2",
                allowed_product_issue_map={},
            )

    def test_render_with_complete_context(self, service):
        """Test rendering with complete context (no missing variables)."""
        result = service.render(
            "compress_history.j2",
            messages_to_compress=[],
            summary_text="Test summary",
            confidence=0.9,
        )
        assert "Test summary" in result
        assert "0.9" in result

    def test_optional_templates_listed(self, service):
        """Test that optional templates are catalogued."""
        assert "feedback_prompt.j2" in service._OPTIONAL_TEMPLATES

    def test_render_scenario_extraction_template(self, service):
        """Test scenario_extraction.j2 rendering with valid context."""
        result = service.render(
            "scenario_extraction.j2",
            messages=[{"role": "user", "content": "What about my interest rate?"}],
            allowed_product_issue_map={"credit_card": ["interest_rate", "fees"]},
            product_type="credit_card",
            issue_type="interest_rate",
            confidence=0.95,
        )
        # JSON 应该包含指定的值
        assert "credit_card" in result
        assert "0.95" in result

    def test_render_summarization_template(self, service):
        """Test summarization.j2 rendering with valid context."""
        result = service.render(
            "summarization.j2",
            user_query="What are my options?",
            conversation_history=[{"role": "user", "content": "Hello"}],
            retrieved_complaints=[],
            retrieved_docs=[],
        )
        assert "What are my options?" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
