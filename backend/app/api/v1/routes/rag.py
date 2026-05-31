from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user
from app.db.session import SessionLocal, get_db
from app.models.user import User
from app.schemas.rag import RagAskRequest, RagAskResponse, RagQueryRead
from app.services.rag_history_service import list_rag_queries, save_rag_query
from app.services.rag_service import RagService

router = APIRouter()


@router.post("/ask", response_model=RagAskResponse)
def ask_legal_question(
    payload: RagAskRequest,
    current_user: User | None = Depends(get_optional_current_user),
) -> RagAskResponse:
    """Answer a legal question with retrieved chunks when the vector index is ready."""
    response = RagService(top_k=payload.top_k).answer(payload.question)
    if current_user is not None and response.is_ready:
        db = SessionLocal()
        try:
            save_rag_query(db, current_user.id, payload.question, response)
        except SQLAlchemyError:
            pass
        finally:
            db.close()
    return response


@router.get("/history", response_model=list[RagQueryRead])
def read_rag_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RagQueryRead]:
    """Return recent RAG query history for the current user."""
    history = list_rag_queries(db, current_user.id)
    return [
        RagQueryRead(
            id=item.id,
            question=item.question,
            answer=item.answer,
            sources=item.sources,
            created_at=item.created_at.isoformat(),
        )
        for item in history
    ]
