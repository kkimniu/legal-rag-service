from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field


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

    @computed_field  # type: ignore[misc]
    @property
    def is_guest(self) -> bool:
        return str(self.email).endswith("@guest.local")


class Token(BaseModel):
    """JWT bearer token response."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Payload for requesting a new access token."""

    refresh_token: str
