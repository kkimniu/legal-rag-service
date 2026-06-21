from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


CaseStatus = Literal["active", "watching", "closed"]


class LegalCaseCreate(BaseModel):
    """Payload for creating a personal legal matter."""

    title: str = Field(..., min_length=1, max_length=255)
    summary: str = ""
    status: CaseStatus = "active"
    domain_code: str | None = Field(default=None, pattern=r"^0[1-4]_[a-z_]+$")


class LegalCaseRead(BaseModel):
    """Personal legal matter summary."""

    id: int
    title: str
    summary: str
    status: str
    domain_code: str | None = None
    created_at: str
    updated_at: str
    note_count: int = 0
    chat_count: int = 0


class CaseInsightRead(BaseModel):
    """AI-generated personal legal matter summary."""

    case_id: int
    summary: str
    issues: list[str] = []
    next_actions: list[str] = []
    cautions: list[str] = []
    is_ready: bool = True


class LegalCaseUpdate(BaseModel):
    """Payload for updating a personal legal matter."""

    status: CaseStatus


class CaseNoteCreate(BaseModel):
    """Payload for creating a note under one legal matter."""

    title: str | None = Field(default=None, max_length=255)
    content: str = Field(..., min_length=1)


class CaseNoteUpdate(BaseModel):
    """Payload for updating a note under one legal matter."""

    title: str | None = Field(default=None, max_length=255)
    content: str = Field(..., min_length=1)


class CaseNoteRead(BaseModel):
    """Stored note under one legal matter."""

    id: int
    case_id: int
    title: str
    content: str
    created_at: str
    updated_at: str


class CaseAttachmentRead(BaseModel):
    """Uploaded file metadata under one legal matter."""

    id: int
    case_id: int
    original_filename: str
    content_type: str | None = None
    size_bytes: int
    extraction_status: str
    extracted_text_chars: int = 0
    vector_status: str
    vector_chunk_count: int = 0
    created_at: str


class CaseTaskCreate(BaseModel):
    """Payload for creating an action item under one legal matter."""

    title: str = Field(..., min_length=1, max_length=255)
    due_date: date | None = None


class CaseTaskUpdate(BaseModel):
    """Full editable state for one legal matter action item."""

    title: str = Field(..., min_length=1, max_length=255)
    due_date: date | None = None
    is_completed: bool = False


class CaseTaskRead(BaseModel):
    """Stored action item under one legal matter."""

    id: int
    case_id: int
    title: str
    due_date: str | None = None
    is_completed: bool
    created_at: str
    updated_at: str


class UpcomingCaseTaskRead(CaseTaskRead):
    """Incomplete dated task enriched with its legal matter title."""

    case_title: str
