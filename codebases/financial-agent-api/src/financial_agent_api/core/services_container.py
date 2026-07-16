from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from ..services.llm_service import LLMService
from ..services.retrieval_service import RetrievalService


@dataclass(slots=True)
class ServicesContainer:
    settings: Settings
    session_factory: sessionmaker[Session]
    llm: LLMService
    retrieval: RetrievalService
