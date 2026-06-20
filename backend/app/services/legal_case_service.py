from datetime import UTC, datetime
import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
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


def generate_case_insight(db: Session, legal_case: LegalCase) -> dict[str, object]:
    """Generate and persist a compact AI summary for one owned legal matter."""
    notes = list_case_notes(db, legal_case.id, limit=30)
    context = build_case_context(db, legal_case)
    insight = _fallback_case_insight(legal_case, notes)

    if settings.openai_api_key and not settings.openai_api_key.startswith("replace-") and context.strip():
        try:
            model = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=settings.openai_temperature,
            )
            response = model.invoke(
                [
                    SystemMessage(
                        content=(
                            "당신은 개인용 한국 법률 비서입니다. 사용자가 저장한 사건 메모만 근거로 "
                            "사건 요약, 핵심 쟁점, 다음 확인할 일을 간결하게 정리하세요. "
                            "법률 자문처럼 단정하지 말고 참고용 정리임을 유지하세요. "
                            "반드시 JSON 객체로만 답하세요. 키는 summary, issues, next_actions, cautions 입니다."
                        )
                    ),
                    HumanMessage(content=f"사건 메모:\n{context}"),
                ]
            )
            parsed = json.loads(str(response.content))
            insight = _normalize_case_insight(parsed, insight)
        except Exception:
            insight = {**insight, "is_ready": False}

    summary = str(insight.get("summary") or "").strip()
    if summary:
        legal_case.summary = summary[:2000]
        legal_case.updated_at = datetime.now(UTC)
        db.add(legal_case)
        db.commit()
        db.refresh(legal_case)

    return insight


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


def get_case_note(db: Session, case_id: int, note_id: int) -> CaseNote | None:
    """Return one note only if it belongs to the given legal matter."""
    statement = select(CaseNote).where(
        CaseNote.id == note_id,
        CaseNote.case_id == case_id,
    )
    return db.scalar(statement)


def update_case_note(
    db: Session,
    legal_case: LegalCase,
    note: CaseNote,
    title: str | None,
    content: str,
) -> CaseNote:
    """Update an existing note under an owned legal matter."""
    note.title = (title or "메모").strip() or "메모"
    note.content = content.strip()
    note.updated_at = datetime.now(UTC)
    legal_case.updated_at = note.updated_at
    db.add(note)
    db.add(legal_case)
    db.commit()
    db.refresh(note)
    db.refresh(legal_case)
    return note


def delete_case_note(db: Session, legal_case: LegalCase, note: CaseNote) -> None:
    """Delete one note under an owned legal matter."""
    legal_case.updated_at = datetime.now(UTC)
    db.delete(note)
    db.add(legal_case)
    db.commit()
    db.refresh(legal_case)


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


def _fallback_case_insight(legal_case: LegalCase, notes: list[CaseNote]) -> dict[str, object]:
    """Build a useful local summary when the AI provider is unavailable."""
    note_texts = [note.content.strip() for note in notes if note.content.strip()]
    summary_source = note_texts[0] if note_texts else legal_case.summary or legal_case.title
    summary = f"{legal_case.title}: {summary_source[:220]}"
    issues = [note.title for note in notes[:3] if note.title.strip()]
    if not issues:
        issues = ["사실관계와 적용 가능한 법률 쟁점 확인"]

    return {
        "case_id": legal_case.id,
        "summary": summary,
        "issues": issues[:5],
        "next_actions": [
            "관련 계약서, 통지 내역, 증빙 자료를 정리하세요.",
            "상대방 주장과 본인 주장을 구분해 메모를 보강하세요.",
        ],
        "cautions": ["자동 정리는 저장된 메모 기반 참고 정보이며, 구체적 판단은 전문가 검토가 필요합니다."],
        "is_ready": bool(settings.openai_api_key and not str(settings.openai_api_key).startswith("replace-")),
    }


def _normalize_case_insight(parsed: object, fallback: dict[str, object]) -> dict[str, object]:
    if not isinstance(parsed, dict):
        return fallback

    def list_of_strings(key: str) -> list[str]:
        value = parsed.get(key)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()][:5]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return list(fallback.get(key, []))

    summary = str(parsed.get("summary") or fallback.get("summary") or "").strip()
    return {
        "case_id": fallback["case_id"],
        "summary": summary,
        "issues": list_of_strings("issues"),
        "next_actions": list_of_strings("next_actions"),
        "cautions": list_of_strings("cautions"),
        "is_ready": True,
    }
