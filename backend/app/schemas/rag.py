from typing import Literal

from pydantic import BaseModel, Field


class RagAskRequest(BaseModel):
    """Question payload for the legal RAG endpoint."""

    question: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    domain_code: str | None = Field(default=None, pattern=r"^0[1-4]_[a-z_]+$")
    answer_mode: Literal["general", "brief", "detailed", "issue", "consultation"] = "general"


class RagSource(BaseModel):
    """Retrieved legal chunk returned as answer evidence."""

    id: str
    title: str | None = None
    domain_name: str | None = None
    source_type: str | None = None
    text: str
    score: float | None = None
    metadata: dict[str, str | int | float | bool] = {}


class RagAskResponse(BaseModel):
    """Answer response for the legal RAG endpoint."""

    answer: str
    sources: list[RagSource] = []
    is_ready: bool = False
    evidence_status: str = "unknown"
    evidence_warnings: list[str] = []


class RagQueryRead(BaseModel):
    """Stored RAG query history item."""

    id: int
    question: str
    answer: str
    sources: list[dict]
    created_at: str
