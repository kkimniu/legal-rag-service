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


class CaseNoteCreate(BaseModel):
    """Payload for creating a note under one legal matter."""

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
