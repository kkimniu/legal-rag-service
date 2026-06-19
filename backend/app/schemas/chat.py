from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.rag import RagSource


class ChatSessionCreate(BaseModel):
    """Optional title payload for creating a chatbot session."""

    title: str | None = Field(default=None, max_length=255)
    domain_code: str | None = Field(default=None, pattern=r"^0[1-4]_[a-z_]+$")


class ChatMessageCreate(BaseModel):
    """User message sent to a chatbot session."""

    content: str = Field(..., min_length=1)
    answer_mode: Literal["general", "brief", "detailed", "issue", "consultation"] = "general"


class ChatMessageRead(BaseModel):
    """Stored chatbot message."""

    id: int
    role: str
    content: str
    answer_mode: str | None = None
    sources: list[RagSource] = []
    created_at: str


class ChatSessionRead(BaseModel):
    """Chatbot conversation summary."""

    id: int
    title: str
    domain_code: str | None = None
    is_pinned: bool = False
    created_at: str
    updated_at: str
    message_count: int = 0
    last_message_preview: str | None = None


class ChatSessionPinUpdate(BaseModel):
    """Pinned state update for a chatbot conversation."""

    is_pinned: bool


class ChatTurnResponse(BaseModel):
    """Response returned after one user message and assistant answer."""

    session: ChatSessionRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    is_ready: bool
