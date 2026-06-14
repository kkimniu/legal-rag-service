from pydantic import BaseModel, Field

from app.schemas.rag import RagSource


class ChatSessionCreate(BaseModel):
    """Optional title payload for creating a chatbot session."""

    title: str | None = Field(default=None, max_length=255)


class ChatMessageCreate(BaseModel):
    """User message sent to a chatbot session."""

    content: str = Field(..., min_length=1)
    domain_code: str | None = Field(default=None, pattern=r"^0[1-4]_[a-z_]+$")


class ChatMessageRead(BaseModel):
    """Stored chatbot message."""

    id: int
    role: str
    content: str
    sources: list[RagSource] = []
    created_at: str


class ChatSessionRead(BaseModel):
    """Chatbot conversation summary."""

    id: int
    title: str
    created_at: str
    updated_at: str


class ChatTurnResponse(BaseModel):
    """Response returned after one user message and assistant answer."""

    session: ChatSessionRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    is_ready: bool
