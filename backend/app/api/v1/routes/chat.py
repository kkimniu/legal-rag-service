import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionPinUpdate,
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
    update_chat_session_pin,
)
from app.services.legal_case_service import build_case_context, get_legal_case
from app.schemas.rag import RagAskResponse
from app.services.rag_service import RagService

router = APIRouter()


def session_read(session: ChatSession, db: Session | None = None) -> ChatSessionRead:
    message_count = count_chat_messages(db, session.id) if db is not None else 0
    last_message = get_last_chat_message(db, session.id) if db is not None else None
    last_message_preview = last_message.content[:80] if last_message is not None else None
    return ChatSessionRead(
        id=session.id,
        title=session.title,
        case_id=session.case_id,
        domain_code=session.domain_code,
        is_pinned=session.is_pinned,
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
        answer_mode=message.answer_mode,
        evidence_status=message.evidence_status,
        evidence_warnings=message.evidence_warnings or [],
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
    if payload.case_id is not None and get_legal_case(db, current_user.id, payload.case_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    return session_read(
        create_chat_session(db, current_user.id, payload.title, payload.domain_code, payload.case_id),
        db,
    )


@router.get("/sessions", response_model=list[ChatSessionRead])
def read_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionRead]:
    """Return recent chatbot conversations for the current user."""
    return [session_read(session, db) for session in list_chat_sessions(db, current_user.id)]


@router.get("/sessions/{session_id}", response_model=ChatSessionRead)
def read_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    """Return one owned chatbot conversation summary."""
    session = get_chat_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session was not found.")
    return session_read(session, db)


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


@router.patch("/sessions/{session_id}/pin", response_model=ChatSessionRead)
def update_session_pin(
    session_id: int,
    payload: ChatSessionPinUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    """Pin or unpin one owned chatbot conversation."""
    session = update_chat_session_pin(db, current_user.id, session_id, payload.is_pinned)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session was not found.")
    return session_read(session, db)


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
    case_context = None
    if session.case_id is not None:
        legal_case = get_legal_case(db, current_user.id, session.case_id)
        if legal_case is not None:
            case_context = build_case_context(db, legal_case)
    user_message = add_user_message(db, session, payload.content, payload.answer_mode)
    response = RagService().answer(
        payload.content,
        domain_code=session.domain_code,
        chat_history=chat_history,
        answer_mode=payload.answer_mode,
        case_context=case_context,
        case_id=session.case_id,
    )
    assistant_message = add_assistant_message(db, session, response, payload.answer_mode)

    return ChatTurnResponse(
        session=session_read(session, db),
        user_message=message_read(user_message),
        assistant_message=message_read(assistant_message),
        is_ready=response.is_ready,
    )


@router.post("/sessions/{session_id}/messages/stream")
def send_message_stream(
    session_id: int,
    payload: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream RAG answer tokens via Server-Sent Events."""
    session = get_chat_session(db, current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session was not found.")

    previous_messages = list_chat_messages(db, session.id, limit=12)
    chat_history = [(m.role, m.content) for m in previous_messages]
    case_context = None
    if session.case_id is not None:
        legal_case = get_legal_case(db, current_user.id, session.case_id)
        if legal_case is not None:
            case_context = build_case_context(db, legal_case)

    rag = RagService()
    rag_prep = rag.prepare_rag(
        payload.content,
        domain_code=session.domain_code,
        chat_history=chat_history,
        answer_mode=payload.answer_mode,
        case_context=case_context,
        case_id=session.case_id,
    )
    user_message = add_user_message(db, session, payload.content, payload.answer_mode)

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        yield _sse({"type": "user_message", "message": message_read(user_message).model_dump()})

        if rag_prep.answer:
            # Early exit: no API key / no sources / insufficient evidence
            assistant_message = add_assistant_message(db, session, rag_prep, payload.answer_mode)
            yield _sse({
                "type": "done",
                "session": session_read(session, db).model_dump(),
                "user_message": message_read(user_message).model_dump(),
                "assistant_message": message_read(assistant_message).model_dump(),
                "is_ready": rag_prep.is_ready,
            })
            return

        full_text = ""
        try:
            for token in rag.stream_generation(
                payload.content,
                sources=rag_prep.sources,
                chat_history=chat_history,
                answer_mode=payload.answer_mode,
                evidence_warnings=rag_prep.evidence_warnings,
                case_context=case_context,
            ):
                full_text += token
                yield _sse({"type": "token", "content": token})
        except Exception as exc:
            error_resp = RagAskResponse(
                answer=f"답변 생성 중 오류가 발생했습니다: {exc}",
                sources=rag_prep.sources,
                is_ready=True,
                evidence_status=rag_prep.evidence_status,
                evidence_warnings=rag_prep.evidence_warnings,
            )
            assistant_message = add_assistant_message(db, session, error_resp, payload.answer_mode)
            yield _sse({
                "type": "done",
                "session": session_read(session, db).model_dump(),
                "user_message": message_read(user_message).model_dump(),
                "assistant_message": message_read(assistant_message).model_dump(),
                "is_ready": False,
            })
            return

        disclaimer = "이 답변은 검색된 법률/판례 데이터에 기반한 참고 정보이며, 구체적인 사건에는 전문가 상담이 필요할 수 있습니다."
        has_notice = "참고 정보" in full_text or "전문가 상담" in full_text or "법률 자문" in full_text
        if not has_notice:
            extra = f"\n\n{disclaimer}"
            yield _sse({"type": "token", "content": extra})
            full_text += extra

        final_resp = RagAskResponse(
            answer=full_text,
            sources=rag_prep.sources,
            is_ready=True,
            evidence_status=rag_prep.evidence_status,
            evidence_warnings=rag_prep.evidence_warnings,
        )
        assistant_message = add_assistant_message(db, session, final_resp, payload.answer_mode)
        yield _sse({
            "type": "done",
            "session": session_read(session, db).model_dump(),
            "user_message": message_read(user_message).model_dump(),
            "assistant_message": message_read(assistant_message).model_dump(),
            "is_ready": True,
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


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
