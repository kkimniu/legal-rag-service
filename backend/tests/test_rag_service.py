from app.schemas.rag import RagSource
from app.services.rag_service import RagService


def test_build_retrieval_question_expands_follow_up_with_user_context() -> None:
    service = RagService()

    retrieval_question = service._build_retrieval_question(
        "그럼 입증책임은 누구에게 있나요?",
        [
            ("user", "계약 불이행으로 손해가 발생한 경우 손해배상 책임은 어떻게 판단되나요?"),
            ("assistant", "검색 근거에 기반한 답변입니다."),
        ],
    )

    assert "계약 불이행" in retrieval_question
    assert "입증책임" in retrieval_question
    assert "검색 근거에 기반한 답변입니다." not in retrieval_question


def test_build_retrieval_question_uses_original_question_without_history() -> None:
    service = RagService()

    assert service._build_retrieval_question("손해배상 책임은 무엇인가요?", []) == "손해배상 책임은 무엇인가요?"


def test_assess_sources_filters_weak_evidence() -> None:
    service = RagService()
    sources = [
        RagSource(
            id="weak-statute",
            text="약한 법령 근거",
            score=2.0,
            metadata={"evidence_type": "statute"},
        ),
        RagSource(
            id="good-precedent",
            text="좋은 판례 근거",
            score=0.2,
            metadata={"evidence_type": "precedent"},
        ),
    ]

    reliable_sources, status, warnings = service._assess_sources(sources)

    assert [source.id for source in reliable_sources] == ["good-precedent"]
    assert status == "partial"
    assert any("법령 근거" in warning for warning in warnings)


def test_insufficient_evidence_answer_uses_safe_format() -> None:
    service = RagService()

    answer = service._insufficient_evidence_answer(["답변을 생성하기에 충분한 관련 근거가 없습니다."])

    assert "답변 요약" in answer
    assert "관련 법령" in answer
    assert "관련 판례" in answer
    assert "주의사항" in answer
    assert "다시 질문" in answer
