from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Payload for creating a user once auth endpoints are added."""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """Public user shape returned by API endpoints."""

    id: int
    email: EmailStr
    is_active: bool
