from fastapi import APIRouter

from app.schemas.rag import RagAskRequest, RagAskResponse
from app.services.rag_service import RagService

router = APIRouter()


@router.post("/ask", response_model=RagAskResponse)
def ask_legal_question(payload: RagAskRequest) -> RagAskResponse:
    """Answer a legal question with retrieved chunks when the vector index is ready."""
    return RagService(top_k=payload.top_k).answer(payload.question)
