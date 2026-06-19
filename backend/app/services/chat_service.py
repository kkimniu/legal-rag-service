from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.schemas.rag import RagAskResponse, RagSource


def create_chat_session(
    db: Session,
    user_id: int,
    title: str | None = None,
    domain_code: str | None = None,
) -> ChatSession:
    """Create a new chatbot conversation."""
    session = ChatSession(
        user_id=user_id,
        title=(title or "새 대화").strip() or "새 대화",
        domain_code=domain_code,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_chat_sessions(db: Session, user_id: int, limit: int = 30) -> list[ChatSession]:
    """Return recent chatbot conversations for a user."""
    statement = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(desc(ChatSession.is_pinned), desc(ChatSession.updated_at), desc(ChatSession.created_at))
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_chat_session(db: Session, user_id: int, session_id: int) -> ChatSession | None:
    """Return one conversation only if the current user owns it."""
    statement = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
    )
    return db.scalar(statement)


def list_chat_messages(db: Session, session_id: int, limit: int = 50) -> list[ChatMessage]:
    """Return stored messages for a conversation in chronological order."""
    statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
        .limit(limit)
    )
    return list(db.scalars(statement))


def count_chat_messages(db: Session, session_id: int) -> int:
    """Count messages stored in one conversation."""
    statement = select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
    return int(db.scalar(statement) or 0)


def get_last_chat_message(db: Session, session_id: int) -> ChatMessage | None:
    """Return the newest message in one conversation."""
    statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        .limit(1)
    )
    return db.scalar(statement)


def add_user_message(db: Session, session: ChatSession, content: str) -> ChatMessage:
    """Persist a user message and use it to name a new conversation."""
    message = ChatMessage(session_id=session.id, role="user", content=content.strip(), sources=[])
    if session.title == "새 대화":
        session.title = content.strip()[:40] or "새 대화"
    session.updated_at = datetime.now(UTC)
    db.add(message)
    db.add(session)
    db.commit()
    db.refresh(message)
    db.refresh(session)
    return message


def add_assistant_message(db: Session, session: ChatSession, response: RagAskResponse) -> ChatMessage:
    """Persist the assistant answer and its retrieved sources."""
    message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=response.answer,
        sources=[source.model_dump() for source in response.sources],
    )
    session.updated_at = datetime.now(UTC)
    db.add(message)
    db.add(session)
    db.commit()
    db.refresh(message)
    db.refresh(session)
    return message


def delete_chat_session(db: Session, user_id: int, session_id: int) -> bool:
    """Delete a conversation if it belongs to the current user."""
    session = get_chat_session(db, user_id, session_id)
    if session is None:
        return False
    db.delete(session)
    db.commit()
    return True


def update_chat_session_pin(
    db: Session,
    user_id: int,
    session_id: int,
    is_pinned: bool,
) -> ChatSession | None:
    """Update pinned state for one owned conversation."""
    session = get_chat_session(db, user_id, session_id)
    if session is None:
        return None
    session.is_pinned = is_pinned
    session.updated_at = datetime.now(UTC)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def sources_from_raw(raw_sources: list[dict]) -> list[RagSource]:
    """Convert JSON-stored source dictionaries back into typed API sources."""
    sources: list[RagSource] = []
    for source in raw_sources:
        if isinstance(source, dict):
            sources.append(RagSource(**source))
    return sources
