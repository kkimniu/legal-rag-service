from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from jose import JWTError

from app.core.security import create_access_token, create_refresh_token, decode_refresh_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import RefreshTokenRequest, Token, UserCreate, UserRead
from app.services.user_service import authenticate_user, create_guest_user, create_user, get_user_by_email, get_user_by_id

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Register a user account."""
    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )
    return create_user(db, payload)


@router.post("/login", response_model=Token)
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Authenticate a user and issue a JWT access token."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = str(user.id)
    return Token(
        access_token=create_access_token(subject=subject),
        refresh_token=create_refresh_token(subject=subject),
    )


@router.post("/refresh", response_model=Token)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> Token:
    """Issue a fresh access token from a valid refresh token."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token_payload = decode_refresh_token(payload.refresh_token)
        subject = token_payload.get("sub")
        if subject is None:
            raise credentials_error
        user_id = int(subject)
    except (JWTError, ValueError):
        raise credentials_error from None

    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_error

    subject = str(user.id)
    return Token(
        access_token=create_access_token(subject=subject),
        refresh_token=create_refresh_token(subject=subject),
    )


@router.post("/guest", response_model=Token, status_code=status.HTTP_201_CREATED)
def login_as_guest(db: Session = Depends(get_db)) -> Token:
    """Create a one-time anonymous guest account and return a JWT."""
    user = create_guest_user(db)
    subject = str(user.id)
    return Token(
        access_token=create_access_token(subject=subject),
        refresh_token=None,
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the current authenticated user."""
    return current_user
