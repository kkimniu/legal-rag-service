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
    result_type: str | None = Query(default=None, pattern="^(case|note|task|attachment|chat)$"),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonalSearchResponse:
    """Search the current user's personal legal workspace."""
    data = search_personal_workspace(db, current_user.id, q, result_type=result_type, limit=limit)
    return PersonalSearchResponse(
        query=q.strip(),
        results=[PersonalSearchResult(**item) for item in data["results"]],
        total_count=data["total_count"],
    )
