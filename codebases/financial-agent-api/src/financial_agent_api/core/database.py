from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings

SessionFactory = sessionmaker[Session]


def create_engine_from_settings(settings: Settings) -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def to_pgvector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(format(float(value), ".12g") for value in vector) + "]"
