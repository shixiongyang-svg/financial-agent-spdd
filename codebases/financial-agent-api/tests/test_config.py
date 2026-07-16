from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from financial_agent_api.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (
        "LLM_PROVIDER",
        "LOG_FORMAT",
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_CHAT_MODEL",
        "OLLAMA_OPS_MODEL",
        "DATABASE_URL",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIM",
        "COMPLAINTS_CSV_PATH",
        "DOCS_SOURCE_DIR",
    ):
        monkeypatch.delenv(key, raising=False)


def test_settings_defaults() -> None:
    settings = Settings()

    assert settings.llm_provider == "ollama"
    assert settings.log_format == "text"
    assert settings.openrouter_api_key is None
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.openrouter_model == "gpt-4.1-mini"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_chat_model == "gemma3:27b"
    assert settings.ollama_ops_model == "qwen3.5:4b"
    assert settings.database_url == "postgresql+psycopg://app:app@localhost:5432/app"
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.embedding_dim == 768
    assert settings.complaints_csv_path is None
    assert settings.docs_source_dir is None


def test_openrouter_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="OPENROUTER_API_KEY is required"):
        Settings(llm_provider="openrouter")


def test_openrouter_with_api_key_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("LOG_FORMAT", "json")

    settings = get_settings()

    assert settings.llm_provider == "openrouter"
    assert settings.openrouter_api_key == "test-key"
    assert settings.log_format == "json"


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_MODEL", "first-model")
    first = get_settings()
    monkeypatch.setenv("OPENROUTER_MODEL", "second-model")
    second = get_settings()

    assert first is second
    assert second.openrouter_model == "first-model"

    get_settings.cache_clear()
    refreshed = get_settings()
    assert refreshed.openrouter_model == "second-model"


def test_required_paths_raise_when_missing() -> None:
    settings = Settings()
    with pytest.raises(ValueError, match="COMPLAINTS_CSV_PATH is required"):
        settings.require_complaints_csv_path()
    with pytest.raises(ValueError, match="DOCS_SOURCE_DIR is required"):
        settings.require_docs_source_dir()
