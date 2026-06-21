from app.services.case_attachment_vector_service import split_attachment_text
from app.services.rag_service import RagService


def test_split_attachment_text_uses_overlap() -> None:
    chunks = split_attachment_text("abcdefghij", chunk_size=6, overlap=2)

    assert chunks == ["abcdef", "efghij"]


def test_rag_service_retrieves_only_selected_case_attachment() -> None:
    captured = {}

    class FakeCollection:
        def query(self, **kwargs):
            captured.update(kwargs)
            return {
                "ids": [["case-attachment-3-0"]],
                "documents": [["계약 종료 후 보증금 미반환 자료"]],
                "metadatas": [[{"case_id": 7, "attachment_id": 3, "title": "memo.txt"}]],
                "distances": [[0.1]],
            }

    class FakeClient:
        def get_collection(self, name):
            captured["collection_name"] = name
            return FakeCollection()

    sources = RagService(top_k=3)._retrieve_case_attachment_sources(FakeClient(), [0.2], case_id=7)

    assert captured["where"] == {"case_id": 7}
    assert sources[0].metadata["evidence_type"] == "case_attachment"
    assert sources[0].title == "memo.txt"
    assert "보증금" in sources[0].text
