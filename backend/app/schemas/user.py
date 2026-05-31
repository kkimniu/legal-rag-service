from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Payload for creating a user once auth endpoints are added."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)


class UserRead(BaseModel):
    """Public user shape returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool


class Token(BaseModel):
    """JWT bearer token response."""

    access_token: str
    token_type: str = "bearer"
