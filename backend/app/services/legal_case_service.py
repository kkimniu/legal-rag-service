from datetime import UTC, datetime
import json
from pathlib import Path
import re
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from fastapi import UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.chat import ChatSession
from app.models.legal_case import CaseAttachment, CaseNote, LegalCase
from app.core.config import settings
from app.services.case_task_service import list_case_tasks


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


def update_legal_case(
    db: Session,
    legal_case: LegalCase,
    title: str | None = None,
    summary: str | None = None,
    status: str | None = None,
) -> LegalCase:
    """Update title, summary, and/or status for one owned legal matter."""
    if title is not None:
        legal_case.title = title.strip()
    if summary is not None:
        legal_case.summary = summary.strip()
    if status is not None:
        legal_case.status = status
    legal_case.updated_at = datetime.now(UTC)
    db.add(legal_case)
    db.commit()
    db.refresh(legal_case)
    return legal_case


def delete_legal_case(db: Session, legal_case: LegalCase) -> None:
    """Delete one owned legal matter and all its child records and files."""
    from app.services.case_attachment_vector_service import delete_case_attachment_vectors

    for attachment in list_case_attachments(db, legal_case.id):
        delete_case_attachment_vectors(attachment.id)
        Path(attachment.storage_path).unlink(missing_ok=True)

    db.delete(legal_case)
    db.commit()


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


def list_case_attachments(db: Session, case_id: int, limit: int = 100) -> list[CaseAttachment]:
    """Return uploaded file metadata for one legal matter."""
    statement = (
        select(CaseAttachment)
        .where(CaseAttachment.case_id == case_id)
        .order_by(desc(CaseAttachment.created_at), desc(CaseAttachment.id))
        .limit(limit)
    )
    return list(db.scalars(statement))


def get_case_attachment(db: Session, case_id: int, attachment_id: int) -> CaseAttachment | None:
    """Return one attachment only if it belongs to the given legal matter."""
    statement = select(CaseAttachment).where(
        CaseAttachment.id == attachment_id,
        CaseAttachment.case_id == case_id,
    )
    return db.scalar(statement)


def create_case_attachment(db: Session, legal_case: LegalCase, upload_file: UploadFile) -> CaseAttachment:
    """Store an uploaded file on disk and persist its metadata."""
    upload_root = Path(settings.upload_directory).resolve()
    case_dir = upload_root / "cases" / str(legal_case.id)
    case_dir.mkdir(parents=True, exist_ok=True)

    original_name = Path(upload_file.filename or "attachment").name[:255]
    suffix = Path(original_name).suffix[:20]
    stored_name = f"{uuid4().hex}{suffix}"
    storage_path = case_dir / stored_name
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    size = 0
    with storage_path.open("wb") as target:
        while chunk := upload_file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                target.close()
                storage_path.unlink(missing_ok=True)
                raise ValueError("upload_too_large")
            target.write(chunk)

    extracted_text, extraction_status = extract_attachment_text(storage_path, upload_file.content_type)
    attachment = CaseAttachment(
        case_id=legal_case.id,
        original_filename=original_name or "attachment",
        stored_filename=stored_name,
        storage_path=str(storage_path),
        content_type=upload_file.content_type,
        size_bytes=size,
        extracted_text=extracted_text,
        extraction_status=extraction_status,
    )
    legal_case.updated_at = datetime.now(UTC)
    db.add(attachment)
    db.add(legal_case)
    db.commit()
    db.refresh(attachment)
    db.refresh(legal_case)
    return attachment


def delete_case_attachment(db: Session, legal_case: LegalCase, attachment: CaseAttachment) -> None:
    """Delete one attachment record and its local file when present."""
    Path(attachment.storage_path).unlink(missing_ok=True)
    legal_case.updated_at = datetime.now(UTC)
    db.delete(attachment)
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

    tasks = list_case_tasks(db, legal_case.id, limit=20)
    if tasks:
        parts.append("사건 할 일과 기한:")
        for index, task in enumerate(tasks, start=1):
            status = "완료" if task.is_completed else "진행중"
            due_date = task.due_date.isoformat() if task.due_date else "기한 없음"
            parts.append(f"[할 일 {index}] {task.title} / {status} / {due_date}")

    attachment_context = build_case_attachment_context(db, legal_case.id)
    if attachment_context:
        parts.append(attachment_context)

    context = "\n\n".join(parts)
    return context[: settings.rag_case_context_max_chars]


def build_case_attachment_context(db: Session, case_id: int) -> str:
    """Build compact extracted attachment text for answer generation."""
    attachments = list_case_attachments(db, case_id, limit=20)
    sections: list[str] = []
    remaining_chars = settings.case_attachment_context_max_chars

    for index, attachment in enumerate(attachments, start=1):
        if remaining_chars <= 0:
            break
        header = (
            f"[첨부자료 {index}] {attachment.original_filename} "
            f"(status={attachment.extraction_status}, size={attachment.size_bytes})\n"
        )
        text = (attachment.extracted_text or "").strip() or "추출 가능한 텍스트가 없습니다."
        available = max(0, remaining_chars - len(header))
        if available <= 0:
            break
        clipped_text = text[:available]
        sections.append(f"{header}{clipped_text}")
        remaining_chars -= len(header) + len(clipped_text)

    if not sections:
        return ""
    return "사건 첨부자료 추출 내용:\n" + "\n\n".join(sections)


_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"})


def extract_attachment_text(path: Path, content_type: str | None = None) -> tuple[str, str]:
    """Extract text from supported user-uploaded case files."""
    suffix = path.suffix.lower()
    try:
        if suffix in {".txt", ".md", ".csv", ".json", ".log"} or (content_type or "").startswith("text/"):
            return _clip_extracted_text(_read_text_file(path)), "completed"
        if suffix == ".pdf":
            text, status = _extract_pdf_text(path)
            if not text or len(text.strip()) < 50:
                ocr_text, ocr_status = _extract_pdf_text_ocr(path)
                if ocr_text:
                    return ocr_text, ocr_status
            return text, status
        if suffix == ".docx":
            return _extract_docx_text(path)
        if suffix in _IMAGE_SUFFIXES:
            return _extract_image_text_ocr(path)
    except Exception:
        return "", "failed"
    return "", "unsupported"


def ocr_case_attachment(db: Session, attachment: "CaseAttachment") -> "CaseAttachment":
    """Re-run OCR extraction on an existing attachment and persist the result."""
    path = Path(attachment.storage_path)
    suffix = path.suffix.lower()
    try:
        if suffix in _IMAGE_SUFFIXES:
            text, extraction_status = _extract_image_text_ocr(path)
        elif suffix == ".pdf":
            text, extraction_status = _extract_pdf_text_ocr(path)
            if not text:
                text, extraction_status = _extract_pdf_text(path)
        else:
            text, extraction_status = extract_attachment_text(path, attachment.content_type)
    except Exception:
        text, extraction_status = "", "failed"
    attachment.extracted_text = text
    attachment.extraction_status = extraction_status
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def _read_text_file(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _extract_pdf_text(path: Path) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except Exception:
        return "", "unsupported"

    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    text = _clip_extracted_text(text)
    return text, "completed" if text else "empty"


def _extract_docx_text(path: Path) -> tuple[str, str]:
    try:
        from docx import Document
    except Exception:
        return "", "unsupported"

    document = Document(str(path))
    parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    text = _clip_extracted_text("\n".join(parts))
    return text, "completed" if text else "empty"


def _ocr_via_openai(image_b64: str, mime_type: str) -> str:
    """Call GPT-4o-mini Vision to extract text from a base64-encoded image."""
    if not settings.openai_api_key or str(settings.openai_api_key).startswith("replace-"):
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=str(settings.openai_api_key))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_b64}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "이 이미지에 있는 모든 텍스트를 정확하게 추출해 주세요. "
                                "원본 레이아웃과 줄바꿈을 최대한 유지하고, 텍스트만 출력하세요. "
                                "텍스트가 없으면 빈 문자열을 반환하세요."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=4000,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""


def _extract_image_text_ocr(path: Path) -> tuple[str, str]:
    """Extract text from an image file (JPG/PNG/etc.) using OpenAI Vision."""
    import base64
    import io

    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as img:
            max_side = 1920
            if max(img.size) > max_side:
                ratio = max_side / max(img.size)
                img = img.resize(
                    (int(img.size[0] * ratio), int(img.size[1] * ratio)),
                    PILImage.LANCZOS,
                )
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            image_b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
        text = _ocr_via_openai(image_b64, "image/jpeg")
        if not text:
            return "", "empty"
        return _clip_extracted_text(text), "completed"
    except Exception:
        return "", "failed"


def _extract_pdf_text_ocr(path: Path, max_pages: int = 5) -> tuple[str, str]:
    """Render image-based PDF pages to JPEG and OCR via OpenAI Vision."""
    import base64

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "", "unsupported"
    try:
        doc = fitz.open(str(path))
        page_texts: list[str] = []
        n = min(len(doc), max_pages)
        for i in range(n):
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72))
            image_b64 = base64.standard_b64encode(pix.tobytes("jpeg")).decode("utf-8")
            text = _ocr_via_openai(image_b64, "image/jpeg")
            if text:
                page_texts.append(f"[페이지 {i + 1}]\n{text}")
        doc.close()
        if not page_texts:
            return "", "empty"
        return _clip_extracted_text("\n\n".join(page_texts)), "completed"
    except Exception:
        return "", "failed"


def _clip_extracted_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[: settings.case_attachment_extract_max_chars]


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


def generate_case_report_markdown(db: Session, legal_case: LegalCase) -> str:
    """Assemble a Markdown report for one legal matter."""
    from datetime import date as _date
    from app.models.chat import ChatMessage, ChatSession
    from app.services.chat_service import list_chat_messages

    status_map = {"active": "진행중", "watching": "관찰중", "closed": "종결"}
    today = _date.today().isoformat()
    lines: list[str] = [
        f"# {legal_case.title}",
        "",
        f"**생성일**: {today}  ",
        f"**상태**: {status_map.get(legal_case.status, legal_case.status)}  ",
        f"**분야**: {legal_case.domain_code or '미지정'}",
        "",
    ]

    if legal_case.summary:
        lines += ["## 사건 요약", "", legal_case.summary, ""]

    notes = list_case_notes(db, legal_case.id, limit=50)
    if notes:
        lines.append("## 메모")
        for note in notes:
            lines += [f"### {note.title or '(제목 없음)'}", "", note.content, ""]

    tasks = list_case_tasks(db, legal_case.id, limit=50)
    if tasks:
        lines.append("## 할 일과 기한")
        for task in tasks:
            mark = "✅" if task.is_completed else "⬜"
            due = f" (기한: {task.due_date.isoformat()})" if task.due_date else ""
            lines.append(f"- {mark} {task.title}{due}")
        lines.append("")

    sessions = list(
        db.scalars(
            select(ChatSession)
            .where(ChatSession.case_id == legal_case.id)
            .order_by(ChatSession.created_at)
        )
    )
    if sessions:
        lines.append("## 채팅 근거")
        for session in sessions:
            lines += [f"### {session.title}", ""]
            for msg in list_chat_messages(db, session.id, limit=100):
                role_label = "**사용자**" if msg.role == "user" else "**AI**"
                lines += [f"{role_label}: {msg.content}", ""]
                if msg.role == "assistant" and msg.sources:
                    for src in msg.sources[:5]:
                        if isinstance(src, dict):
                            title = src.get("title") or ""
                            excerpt = (src.get("text") or "")[:120]
                            lines.append(f"> 출처: {title} — {excerpt}")
                    lines.append("")

    return "\n".join(lines)


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
