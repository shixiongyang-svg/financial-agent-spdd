from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from financial_agent_api.db.schema import apply_schema, render_schema_sql


def test_render_schema_sql_replaces_embedding_dim() -> None:
    rendered = render_schema_sql("embedding VECTOR(/* EMBEDDING_DIM */)", 1536)
    assert rendered == "embedding VECTOR(1536)"


def test_apply_schema_executes_statements(tmp_path: Path) -> None:
    schema_file = tmp_path / "schema.sql"
    schema_file.write_text(
        """
        CREATE TABLE test_docs (id INTEGER PRIMARY KEY, body TEXT);
        INSERT INTO test_docs (id, body) VALUES (1, 'ok');
        """,
        encoding="utf-8",
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    apply_schema(session_factory, schema_file, embedding_dim=768)

    with session_factory() as session:
        value = session.execute(text("SELECT body FROM test_docs WHERE id = 1")).scalar_one()
    assert value == "ok"
