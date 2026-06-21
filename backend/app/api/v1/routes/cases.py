from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.legal_case import CaseNote, LegalCase
from app.models.user import User
from app.schemas.legal_case import (
    CaseAttachmentRead,
    CaseInsightRead,
    CaseNoteCreate,
    CaseNoteRead,
    CaseNoteUpdate,
    LegalCaseCreate,
    LegalCaseRead,
    LegalCaseUpdate,
)
from app.services.legal_case_service import (
    count_case_chats,
    count_case_notes,
    create_case_attachment,
    create_case_note,
    create_legal_case,
    delete_case_attachment,
    delete_case_note,
    generate_case_insight,
    get_case_attachment,
    get_case_note,
    get_legal_case,
    list_case_attachments,
    list_case_notes,
    list_legal_cases,
    update_case_note,
    update_legal_case_status,
)
from app.services.case_attachment_vector_service import (
    delete_case_attachment_vectors,
    index_case_attachment,
)

router = APIRouter()


def case_read(legal_case: LegalCase, db: Session) -> LegalCaseRead:
    return LegalCaseRead(
        id=legal_case.id,
        title=legal_case.title,
        summary=legal_case.summary,
        status=legal_case.status,
        domain_code=legal_case.domain_code,
        created_at=legal_case.created_at.isoformat(),
        updated_at=legal_case.updated_at.isoformat(),
        note_count=count_case_notes(db, legal_case.id),
        chat_count=count_case_chats(db, legal_case.id),
    )


def note_read(note: CaseNote) -> CaseNoteRead:
    return CaseNoteRead(
        id=note.id,
        case_id=note.case_id,
        title=note.title,
        content=note.content,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


def attachment_read(attachment) -> CaseAttachmentRead:
    return CaseAttachmentRead(
        id=attachment.id,
        case_id=attachment.case_id,
        original_filename=attachment.original_filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        extraction_status=attachment.extraction_status,
        extracted_text_chars=len(attachment.extracted_text or ""),
        vector_status=attachment.vector_status,
        vector_chunk_count=attachment.vector_chunk_count,
        created_at=attachment.created_at.isoformat(),
    )


@router.post("", response_model=LegalCaseRead, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: LegalCaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LegalCaseRead:
    """Create a personal legal matter."""
    legal_case = create_legal_case(
        db=db,
        user_id=current_user.id,
        title=payload.title,
        summary=payload.summary,
        status=payload.status,
        domain_code=payload.domain_code,
    )
    return case_read(legal_case, db)


@router.get("", response_model=list[LegalCaseRead])
def read_cases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LegalCaseRead]:
    """Return personal legal matters for the current user."""
    return [case_read(legal_case, db) for legal_case in list_legal_cases(db, current_user.id)]


@router.patch("/{case_id}", response_model=LegalCaseRead)
def update_case(
    case_id: int,
    payload: LegalCaseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LegalCaseRead:
    """Update one owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    return case_read(update_legal_case_status(db, legal_case, payload.status), db)


@router.post("/{case_id}/insight", response_model=CaseInsightRead)
def create_case_insight(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaseInsightRead:
    """Generate a compact AI summary for one owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    return CaseInsightRead(**generate_case_insight(db, legal_case))


@router.get("/{case_id}/notes", response_model=list[CaseNoteRead])
def read_case_notes(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CaseNoteRead]:
    """Return notes for one owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    return [note_read(note) for note in list_case_notes(db, legal_case.id)]


@router.post("/{case_id}/notes", response_model=CaseNoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    case_id: int,
    payload: CaseNoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaseNoteRead:
    """Create a note under one owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    return note_read(create_case_note(db, legal_case, payload.title, payload.content))


@router.patch("/{case_id}/notes/{note_id}", response_model=CaseNoteRead)
def update_note(
    case_id: int,
    note_id: int,
    payload: CaseNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaseNoteRead:
    """Update one note under an owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    note = get_case_note(db, legal_case.id, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case note was not found.")
    return note_read(update_case_note(db, legal_case, note, payload.title, payload.content))


@router.delete("/{case_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    case_id: int,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete one note under an owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    note = get_case_note(db, legal_case.id, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case note was not found.")
    delete_case_note(db, legal_case, note)


@router.get("/{case_id}/attachments", response_model=list[CaseAttachmentRead])
def read_attachments(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CaseAttachmentRead]:
    """Return uploaded file metadata for one owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    return [attachment_read(attachment) for attachment in list_case_attachments(db, legal_case.id)]


@router.post("/{case_id}/attachments", response_model=CaseAttachmentRead, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    case_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaseAttachmentRead:
    """Upload one file under an owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    try:
        return attachment_read(create_case_attachment(db, legal_case, file))
    except ValueError as exc:
        if str(exc) == "upload_too_large":
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Upload file is too large.") from exc
        raise


@router.delete("/{case_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    case_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete one uploaded file under an owned legal matter."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    attachment = get_case_attachment(db, legal_case.id, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case attachment was not found.")
    delete_case_attachment_vectors(attachment.id)
    delete_case_attachment(db, legal_case, attachment)


@router.post("/{case_id}/attachments/{attachment_id}/index", response_model=CaseAttachmentRead)
def index_attachment(
    case_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CaseAttachmentRead:
    """Create or replace vector chunks for one owned attachment."""
    legal_case = get_legal_case(db, current_user.id, case_id)
    if legal_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal case was not found.")
    attachment = get_case_attachment(db, legal_case.id, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case attachment was not found.")
    return attachment_read(index_case_attachment(db, legal_case, attachment))
