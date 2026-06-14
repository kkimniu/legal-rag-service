from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
    ChatTurnResponse,
)
from app.services.chat_service import (
    add_assistant_message,
    add_user_message,
    count_chat_messages,
    create_chat_session,
    delete_chat_session,
    get_last_chat_message,
    get_chat_session,
    list_chat_messages,
    list_chat_sessions,
    sources_from_raw,
)
from app.services.rag_service import RagService

router = APIRouter()


def session_read(session: ChatSession, db: Session | None = None) -> ChatSessionRead:
    message_count = count_chat_messages(db, session.id) if db is not None else 0
    last_message = get_last_chat_message(db, session.id) if db is not None else None
    last_message_preview = last_message.content[:80] if last_message is not None else None
    return ChatSessionRead(
        id=session.id,
        title=session.title,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        message_count=message_count,
        last_message_preview=last_message_preview,
    )


def message_read(message: ChatMessage) -> ChatMessageRead:
    return ChatMessageRead(
        id=message.id,
        role=message.role,
        content=message.content,
        sources=sources_from_raw(message.sources),
        created_at=message.created_at.isoformat(),
    )


@router.post("/sessions", response_model=ChatSessionRead)
def create_session(
    payload: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    """Create a new chatbot conversation for the current user."""
    return session_read(create_chat_session(db, current_user.id, payload.title), db)


@router.get("/sessions", response_model=list[ChatSessionRead])
def read_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionRead]:
    """Return recent chatbot conversations for the current user."""
    return [session_read(session, db) for session in list_chat_sessions(db, current_user.id)]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageRead])
def read_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessageRead]:
    """Return messages for one owned conversation."""
    session = get_chat_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session was not found.")
    return [message_read(message) for message in list_chat_messages(db, session.id)]


@router.post("/sessions/{session_id}/messages", response_model=ChatTurnResponse)
def send_message(
    session_id: int,
    payload: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatTurnResponse:
    """Store a user message, run RAG, and store the assistant answer."""
    session = get_chat_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session was not found.")

    previous_messages = list_chat_messages(db, session.id, limit=12)
    chat_history = [(message.role, message.content) for message in previous_messages]
    user_message = add_user_message(db, session, payload.content)
    response = RagService().answer(
        payload.content,
        domain_code=payload.domain_code,
        chat_history=chat_history,
    )
    assistant_message = add_assistant_message(db, session, response)

    return ChatTurnResponse(
        session=session_read(session, db),
        user_message=message_read(user_message),
        assistant_message=message_read(assistant_message),
        is_ready=response.is_ready,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete one owned chatbot conversation."""
    deleted = delete_chat_session(db, current_user.id, session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session was not found.")
