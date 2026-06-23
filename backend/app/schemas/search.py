from typing import Literal

from pydantic import BaseModel


class PersonalSearchResult(BaseModel):
    """One searchable item from a user's personal legal workspace."""

    result_type: Literal["case", "note", "task", "attachment", "chat"]
    id: int
    case_id: int | None = None
    session_id: int | None = None
    title: str
    snippet: str
    occurred_at: str


class PersonalSearchResponse(BaseModel):
    query: str
    results: list[PersonalSearchResult]
    total_count: int = 0


class LegalSearchResult(BaseModel):
    """One chunk from the legal knowledge base."""

    id: str
    title: str | None = None
    domain_name: str | None = None
    evidence_type: str
    snippet: str
    score: float | None = None


class LegalSearchResponse(BaseModel):
    query: str
    results: list[LegalSearchResult]
    total_count: int = 0
