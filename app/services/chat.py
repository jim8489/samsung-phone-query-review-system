from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import AgentOrchestrator
from app.models import ChatMessage, ChatSession


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    async def ask(self, query: str, session_id: str | None = None) -> dict:
        chat_session = self.db.get(ChatSession, session_id) if session_id else None
        if chat_session is None:
            chat_session = ChatSession(id=str(uuid4()))
            self.db.add(chat_session)
            self.db.flush()

        history_rows = self.db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == chat_session.id).order_by(ChatMessage.created_at.desc()).limit(8)
        ).all()
        history = [{"role": item.role, "content": item.content} for item in reversed(history_rows)]

        answer, mode, result = await AgentOrchestrator(self.db).answer(query, history=history)
        sources = result.sources
        self.db.add(ChatMessage(session_id=chat_session.id, role="user", content=query, sources=[]))
        self.db.add(ChatMessage(session_id=chat_session.id, role="assistant", content=answer, sources=sources))
        self.db.commit()

        return {
            "session_id": chat_session.id,
            "answer": answer,
            "mode": mode,
            "sources": sources,
            "relevant_phones": [phone.name for phone in result.phones],
        }
