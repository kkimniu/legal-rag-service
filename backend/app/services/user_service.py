import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email."""
    return db.scalar(select(User).where(User.email == email))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Fetch a user by primary key."""
    return db.get(User, user_id)


def create_user(db: Session, payload: UserCreate) -> User:
    """Create a new active user with a hashed password."""
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_guest_user(db: Session) -> User:
    """Create a one-time anonymous guest user and return it with a JWT-ready record."""
    short_id = uuid.uuid4().hex[:12]
    user = User(
        email=f"guest_{short_id}@guest.local",
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user when credentials are valid."""
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
