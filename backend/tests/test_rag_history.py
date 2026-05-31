from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.rag import RagAskResponse, RagSource
from app.services.rag_history_service import list_rag_queries, save_rag_query


def test_save_and_list_rag_query_history(db_session: Session) -> None:
    user = User(
        email="history@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    response = RagAskResponse(
        answer="검색 근거에 기반한 답변입니다.",
        is_ready=True,
        sources=[
            RagSource(
                id="chunk-1",
                title="손해배상",
                domain_name="민사법",
                source_type="qa",
                text="근거 본문",
                score=0.1,
                metadata={"document_id": "doc-1"},
            )
        ],
    )

    saved = save_rag_query(
        db=db_session,
        user_id=user.id,
        question="질문입니다.",
        response=response,
    )
    history = list_rag_queries(db_session, user.id)

    assert saved.id is not None
    assert len(history) == 1
    assert history[0].question == "질문입니다."
    assert history[0].answer == "검색 근거에 기반한 답변입니다."
    assert history[0].sources[0]["id"] == "chunk-1"
