from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.models.legal_case import CaseAttachment, CaseNote, CaseTask, LegalCase


def list_case_timeline(db: Session, legal_case: LegalCase, limit: int = 50) -> list[dict[str, object]]:
    """Aggregate recent activity from one owned legal matter without duplicating data."""
    per_source_limit = min(max(limit, 1), 100)
    items: list[dict[str, object]] = [
        _item("case", legal_case.id, None, "사건 생성", legal_case.title, legal_case.created_at)
    ]

    notes = db.scalars(
        select(CaseNote)
        .where(CaseNote.case_id == legal_case.id)
        .order_by(desc(CaseNote.updated_at))
        .limit(per_source_limit)
    )
    items.extend(
        _item("note", note.id, None, note.title, _snippet(note.content), note.updated_at)
        for note in notes
    )

    tasks = db.scalars(
        select(CaseTask)
        .where(CaseTask.case_id == legal_case.id)
        .order_by(desc(CaseTask.updated_at))
        .limit(per_source_limit)
    )
    for task in tasks:
        status = "완료" if task.is_completed else "진행 중"
        due_date = task.due_date.isoformat() if task.due_date else "기한 없음"
        items.append(_item("task", task.id, None, task.title, f"{status} · {due_date}", task.updated_at))

    attachments = db.scalars(
        select(CaseAttachment)
        .where(CaseAttachment.case_id == legal_case.id)
        .order_by(desc(CaseAttachment.created_at))
        .limit(per_source_limit)
    )
    items.extend(
        _item(
            "attachment",
            attachment.id,
            None,
            attachment.original_filename,
            f"{attachment.extraction_status} · {attachment.size_bytes:,}바이트",
            attachment.created_at,
        )
        for attachment in attachments
    )

    messages = db.execute(
        select(ChatMessage, ChatSession)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatSession.case_id == legal_case.id)
        .order_by(desc(ChatMessage.created_at))
        .limit(per_source_limit)
    ).all()
    for message, chat_session in messages:
        role = "질문" if message.role == "user" else "AI 답변"
        items.append(
            _item(
                "chat",
                message.id,
                chat_session.id,
                f"{role} · {chat_session.title}",
                _snippet(message.content),
                message.created_at,
            )
        )

    items.sort(key=lambda item: str(item["occurred_at"]), reverse=True)
    return items[:limit]


def _item(
    activity_type: str,
    entity_id: int,
    session_id: int | None,
    title: str,
    description: str,
    occurred_at: datetime,
) -> dict[str, object]:
    return {
        "activity_type": activity_type,
        "entity_id": entity_id,
        "session_id": session_id,
        "title": title,
        "description": description,
        "occurred_at": occurred_at.isoformat(),
    }


def _snippet(text: str, max_chars: int = 180) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= max_chars else f"{compact[:max_chars]}..."
