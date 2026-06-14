from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.rag_query import RagQuery
from app.schemas.rag import RagAskResponse


def save_rag_query(
    db: Session,
    user_id: int,
    question: str,
    response: RagAskResponse,
) -> RagQuery:
    """Persist a successful RAG question and answer for a user."""
    query = RagQuery(
        user_id=user_id,
        question=question,
        answer=response.answer,
        sources=[source.model_dump() for source in response.sources],
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    return query


def list_rag_queries(db: Session, user_id: int, limit: int = 20) -> list[RagQuery]:
    """Return recent RAG query history for a user."""
    statement = (
        select(RagQuery)
        .where(RagQuery.user_id == user_id)
        .order_by(desc(RagQuery.created_at))
        .limit(limit)
    )
    return list(db.scalars(statement))


def delete_rag_query(db: Session, user_id: int, query_id: int) -> bool:
    """Delete one RAG query if it belongs to the user."""
    statement = select(RagQuery).where(
        RagQuery.id == query_id,
        RagQuery.user_id == user_id,
    )
    query = db.scalar(statement)
    if query is None:
        return False

    db.delete(query)
    db.commit()
    return True
