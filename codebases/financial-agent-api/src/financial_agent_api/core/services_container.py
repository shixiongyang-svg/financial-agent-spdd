from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from ..services.llm_service import LLMService


@dataclass(slots=True)
class ServicesContainer:
    settings: Settings
    llm: LLMService
