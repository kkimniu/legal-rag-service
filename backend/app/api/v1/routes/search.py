from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.search import PersonalSearchResponse, PersonalSearchResult
from app.services.personal_search_service import search_personal_workspace


router = APIRouter()


@router.get("", response_model=PersonalSearchResponse)
def search_workspace(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(default=40, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonalSearchResponse:
    """Search the current user's personal legal workspace."""
    results = search_personal_workspace(db, current_user.id, q, limit=limit)
    return PersonalSearchResponse(
        query=q.strip(),
        results=[PersonalSearchResult(**item) for item in results],
    )
