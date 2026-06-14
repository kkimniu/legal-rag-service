from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal, get_db
from app.models.user import User
from app.services.user_service import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current authenticated user from a bearer token."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise credentials_error
        user_id = int(subject)
    except (JWTError, ValueError):
        raise credentials_error from None

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
) -> User | None:
    """Resolve a user when a bearer token is present, otherwise allow anonymous access."""
    if credentials is None:
        return None

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")
        if subject is None:
            raise credentials_error
        user_id = int(subject)
    except (JWTError, ValueError):
        raise credentials_error from None

    db = SessionLocal()
    try:
        user = get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise credentials_error
        return user
    except SQLAlchemyError:
        raise credentials_error from None
    finally:
        db.close()
