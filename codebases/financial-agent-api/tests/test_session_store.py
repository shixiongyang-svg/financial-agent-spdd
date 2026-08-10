from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from financial_agent_api.services.session_store import SessionStore


def _make_store() -> SessionStore:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE conversation_sessions (
                  session_id TEXT PRIMARY KEY,
                  conversation_history TEXT NOT NULL DEFAULT '[]',
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    return SessionStore(sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False))


def test_session_store_creates_and_loads_history() -> None:
    store = _make_store()
    session_id, history = store.load_or_create_session(session_id=None)

    assert session_id
    assert history == []

    store.save_history(session_id, [{"role": "user", "content": "hello"}])
    assert store.load_history(session_id) == [{"role": "user", "content": "hello"}]


def test_session_store_loads_db_history_for_existing_session() -> None:
    store = _make_store()
    session_id, _ = store.load_or_create_session(session_id=None)

    store.save_history(session_id, [{"role": "assistant", "content": "db"}])

    resolved_session_id, history = store.load_or_create_session(session_id=session_id)

    assert resolved_session_id == session_id
    assert history == [{"role": "assistant", "content": "db"}]


def test_session_store_append_turns_persists_user_and_assistant() -> None:
    store = _make_store()
    session_id, _ = store.load_or_create_session(session_id=None)

    store.append_turns(
        session_id=session_id,
        conversation_history=[{"role": "assistant", "content": "prior"}],
        user_query="new question",
        assistant_reply="new answer",
    )

    assert store.load_history(session_id) == [
        {"role": "assistant", "content": "prior"},
        {"role": "user", "content": "new question"},
        {"role": "assistant", "content": "new answer"},
    ]
