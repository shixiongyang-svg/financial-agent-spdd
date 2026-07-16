from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from ..core.database import SessionFactory


def render_schema_sql(raw_sql: str, embedding_dim: int) -> str:
    return raw_sql.replace("/* EMBEDDING_DIM */", str(embedding_dim))


def apply_schema(session_factory: SessionFactory, schema_path: Path, embedding_dim: int) -> None:
    raw_sql = schema_path.read_text(encoding="utf-8")
    rendered_sql = render_schema_sql(raw_sql, embedding_dim)
    statements = [statement.strip() for statement in rendered_sql.split(";") if statement.strip()]

    with session_factory.begin() as session:
        for statement in statements:
            session.execute(text(statement))
