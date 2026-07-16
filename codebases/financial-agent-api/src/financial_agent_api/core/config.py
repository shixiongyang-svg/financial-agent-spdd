from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["ollama", "openrouter"] = "ollama"
    log_format: Literal["json", "text"] = "text"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "gpt-4.1-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "gemma3:27b"
    ollama_ops_model: str = "qwen3.5:4b"
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = Field(default=768, ge=1)
    complaints_csv_path: str | None = None
    docs_source_dir: str | None = None

    @model_validator(mode="after")
    def validate_openrouter_settings(self) -> Self:
        if self.llm_provider == "openrouter" and not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required when llm_provider=openrouter")
        return self

    def require_complaints_csv_path(self) -> Path:
        if not self.complaints_csv_path:
            raise ValueError("COMPLAINTS_CSV_PATH is required")
        return Path(self.complaints_csv_path)

    def require_docs_source_dir(self) -> Path:
        if not self.docs_source_dir:
            raise ValueError("DOCS_SOURCE_DIR is required")
        return Path(self.docs_source_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
