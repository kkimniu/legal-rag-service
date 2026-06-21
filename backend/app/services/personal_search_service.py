from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.models.legal_case import CaseAttachment, CaseNote, CaseTask, LegalCase

_ALL_TYPES = {"case", "note", "task", "attachment", "chat"}


def search_personal_workspace(
    db: Session,
    user_id: int,
    query: str,
    result_type: str | None = None,
    limit: int = 40,
) -> dict[str, object]:
    """Search one user's cases, notes, tasks, attachments, and conversations."""
    normalized_query = query.strip()
    if not normalized_query:
        return {"results": [], "total_count": 0}
    pattern = f"%{_escape_like(normalized_query)}%"

    active_types = {result_type} if result_type in _ALL_TYPES else _ALL_TYPES
    # when a single type is selected give it the full limit; otherwise distribute
    per_type_limit = limit if len(active_types) == 1 else max(8, limit // len(active_types))
    results: list[dict[str, object]] = []

    if "case" in active_types:
        cases = db.scalars(
            select(LegalCase)
            .where(
                LegalCase.user_id == user_id,
                or_(
                    LegalCase.title.ilike(pattern, escape="\\"),
                    LegalCase.summary.ilike(pattern, escape="\\"),
                ),
            )
            .limit(per_type_limit)
        )
        for legal_case in cases:
            results.append(
                _result(
                    "case",
                    legal_case.id,
                    legal_case.id,
                    None,
                    legal_case.title,
                    legal_case.summary or legal_case.title,
                    normalized_query,
                    legal_case.updated_at,
                )
            )

    if "note" in active_types:
        note_rows = db.execute(
            select(CaseNote, LegalCase.title)
            .join(LegalCase, LegalCase.id == CaseNote.case_id)
            .where(
                LegalCase.user_id == user_id,
                or_(
                    CaseNote.title.ilike(pattern, escape="\\"),
                    CaseNote.content.ilike(pattern, escape="\\"),
                ),
            )
            .limit(per_type_limit)
        ).all()
        for note, _case_title in note_rows:
            results.append(
                _result("note", note.id, note.case_id, None, note.title, note.content, normalized_query, note.updated_at)
            )

    if "task" in active_types:
        task_rows = db.execute(
            select(CaseTask, LegalCase.title)
            .join(LegalCase, LegalCase.id == CaseTask.case_id)
            .where(LegalCase.user_id == user_id, CaseTask.title.ilike(pattern, escape="\\"))
            .limit(per_type_limit)
        ).all()
        for task, case_title in task_rows:
            status = "완료" if task.is_completed else "진행중"
            due_date = task.due_date.isoformat() if task.due_date else "기한 없음"
            results.append(
                _result(
                    "task",
                    task.id,
                    task.case_id,
                    None,
                    task.title,
                    f"{case_title} · {status} · {due_date}",
                    normalized_query,
                    task.updated_at,
                )
            )

    if "attachment" in active_types:
        attachment_rows = db.execute(
            select(CaseAttachment, LegalCase.title)
            .join(LegalCase, LegalCase.id == CaseAttachment.case_id)
            .where(
                LegalCase.user_id == user_id,
                or_(
                    CaseAttachment.original_filename.ilike(pattern, escape="\\"),
                    CaseAttachment.extracted_text.ilike(pattern, escape="\\"),
                ),
            )
            .limit(per_type_limit)
        ).all()
        for attachment, case_title in attachment_rows:
            results.append(
                _result(
                    "attachment",
                    attachment.id,
                    attachment.case_id,
                    None,
                    attachment.original_filename,
                    attachment.extracted_text or case_title,
                    normalized_query,
                    attachment.created_at,
                )
            )

    if "chat" in active_types:
        chat_rows = db.execute(
            select(ChatMessage, ChatSession)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.user_id == user_id,
                or_(
                    ChatSession.title.ilike(pattern, escape="\\"),
                    ChatMessage.content.ilike(pattern, escape="\\"),
                ),
            )
            .limit(per_type_limit)
        ).all()
        for message, session in chat_rows:
            results.append(
                _result(
                    "chat",
                    message.id,
                    session.case_id,
                    session.id,
                    session.title,
                    message.content,
                    normalized_query,
                    message.created_at,
                )
            )

    results.sort(key=lambda item: str(item["occurred_at"]), reverse=True)
    total_count = len(results)
    return {"results": results[:limit], "total_count": total_count}


def _result(
    result_type: str,
    item_id: int,
    case_id: int | None,
    session_id: int | None,
    title: str,
    text: str,
    query: str,
    occurred_at: datetime,
) -> dict[str, object]:
    return {
        "result_type": result_type,
        "id": item_id,
        "case_id": case_id,
        "session_id": session_id,
        "title": title,
        "snippet": _snippet(text, query),
        "occurred_at": occurred_at.isoformat(),
    }


def _snippet(text: str, query: str, radius: int = 90) -> str:
    compact = " ".join(text.split())
    index = compact.casefold().find(query.casefold())
    if index < 0:
        return compact[: radius * 2]
    start = max(0, index - radius)
    end = min(len(compact), index + len(query) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end]}{suffix}"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
