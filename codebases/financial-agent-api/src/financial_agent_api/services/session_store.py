from __future__ import annotations

import json
import logging
from uuid import uuid4

from sqlalchemy import text

from ..core.database import SessionFactory

logger = logging.getLogger(__name__)


class SessionStore:
    """Persist and load per-session conversation history."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def load_history(self, session_id: str) -> list[dict]:
        with self._session_factory() as session:
            row = session.execute(
                text(
                    """
                    SELECT conversation_history
                    FROM conversation_sessions
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).first()

        if row is None:
            return []

        raw_history = row[0]
        if raw_history in (None, ""):
            return []
        if isinstance(raw_history, list):
            return raw_history
        if isinstance(raw_history, str):
            try:
                parsed = json.loads(raw_history)
            except json.JSONDecodeError:
                return []
            return parsed if isinstance(parsed, list) else []
        return []

    def save_history(self, session_id: str, conversation_history: list[dict]) -> None:
        payload = json.dumps(conversation_history, ensure_ascii=False)
        with self._session_factory.begin() as session:
            session.execute(
                text(
                    """
                    INSERT INTO conversation_sessions (session_id, conversation_history)
                    VALUES (:session_id, CAST(:conversation_history AS TEXT))
                    ON CONFLICT(session_id) DO UPDATE SET
                      conversation_history = EXCLUDED.conversation_history,
                      updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {"session_id": session_id, "conversation_history": payload},
            )

    def load_or_create_session(
        self,
        *,
        session_id: str | None,
    ) -> tuple[str, list[dict]]:
        if session_id is None:
            new_session_id = str(uuid4())
            history: list[dict] = []
            self.save_history(new_session_id, history)
            return new_session_id, history

        history = self.load_history(session_id)
        if not history:
            self.save_history(session_id, history)
        return session_id, history

    def append_turns(
        self,
        *,
        session_id: str,
        conversation_history: list[dict],
        user_query: str,
        assistant_reply: str | None = None,
    ) -> None:
        history = list(conversation_history)
        history.append({"role": "user", "content": user_query})
        if assistant_reply is not None:
            history.append({"role": "assistant", "content": assistant_reply})
        self.save_history(session_id, history)
