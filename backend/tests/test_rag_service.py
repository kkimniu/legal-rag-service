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
