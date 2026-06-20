from datetime import UTC, datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.chat import ChatSession
from app.models.legal_case import CaseNote, LegalCase
from app.core.config import settings


def create_legal_case(
    db: Session,
    user_id: int,
    title: str,
    summary: str = "",
    status: str = "active",
    domain_code: str | None = None,
) -> LegalCase:
    """Create a personal legal matter for one user."""
    legal_case = LegalCase(
        user_id=user_id,
        title=title.strip(),
        summary=summary.strip(),
        status=status,
        domain_code=domain_code,
    )
    db.add(legal_case)
    db.commit()
    db.refresh(legal_case)
    return legal_case


def list_legal_cases(db: Session, user_id: int, limit: int = 50) -> list[LegalCase]:
    """Return recent personal legal matters for one user."""
    statement = (
        select(LegalCase)
        .where(LegalCase.user_id == user_id)
        .order_by(desc(LegalCase.updated_at), desc(LegalCase.created_at))
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_legal_case(db: Session, user_id: int, case_id: int) -> LegalCase | None:
    """Return one legal matter only if the current user owns it."""
    statement = select(LegalCase).where(
        LegalCase.id == case_id,
        LegalCase.user_id == user_id,
    )
    return db.scalar(statement)


def update_legal_case_status(
    db: Session,
    legal_case: LegalCase,
    status: str,
) -> LegalCase:
    """Update the workflow status for one owned legal matter."""
    legal_case.status = status
    legal_case.updated_at = datetime.now(UTC)
    db.add(legal_case)
    db.commit()
    db.refresh(legal_case)
    return legal_case


def create_case_note(
    db: Session,
    legal_case: LegalCase,
    title: str | None,
    content: str,
) -> CaseNote:
    """Create a note under an owned legal matter."""
    note = CaseNote(
        case_id=legal_case.id,
        title=(title or "메모").strip() or "메모",
        content=content.strip(),
    )
    legal_case.updated_at = datetime.now(UTC)
    db.add(note)
    db.add(legal_case)
    db.commit()
    db.refresh(note)
    db.refresh(legal_case)
    return note


def list_case_notes(db: Session, case_id: int, limit: int = 100) -> list[CaseNote]:
    """Return notes for one legal matter in chronological order."""
    statement = (
        select(CaseNote)
        .where(CaseNote.case_id == case_id)
        .order_by(CaseNote.created_at, CaseNote.id)
        .limit(limit)
    )
    return list(db.scalars(statement))


def count_case_notes(db: Session, case_id: int) -> int:
    """Count notes under one legal matter."""
    statement = select(func.count(CaseNote.id)).where(CaseNote.case_id == case_id)
    return int(db.scalar(statement) or 0)


def count_case_chats(db: Session, case_id: int) -> int:
    """Count chat sessions linked to one legal matter."""
    statement = select(func.count(ChatSession.id)).where(ChatSession.case_id == case_id)
    return int(db.scalar(statement) or 0)


def build_case_context(db: Session, legal_case: LegalCase) -> str:
    """Build a compact personal case context for RAG answer generation."""
    parts = [
        f"사건명: {legal_case.title}",
        f"상태: {legal_case.status}",
    ]
    if legal_case.summary:
        parts.append(f"사건 요약: {legal_case.summary}")
    if legal_case.domain_code:
        parts.append(f"분야 코드: {legal_case.domain_code}")

    notes = list_case_notes(db, legal_case.id, limit=20)
    if notes:
        parts.append("사건 메모:")
        for index, note in enumerate(notes, start=1):
            parts.append(f"[메모 {index}] {note.title}\n{note.content}")

    context = "\n\n".join(parts)
    return context[: settings.rag_case_context_max_chars]
