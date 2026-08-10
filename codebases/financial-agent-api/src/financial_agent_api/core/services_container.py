from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .prompt_service import PromptService
from ..services.llm_service import LLMService
from ..services.product_issue_service import ProductIssueService
from ..services.retrieval_service import RetrievalService
from ..services.session_store import SessionStore


@dataclass(slots=True)
class ServicesContainer:
    settings: Settings
    session_factory: sessionmaker[Session]
    llm: LLMService
    retrieval: RetrievalService
    prompt_service: PromptService
    product_issue_service: ProductIssueService
    session_store: SessionStore
