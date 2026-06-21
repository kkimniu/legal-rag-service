from fastapi.testclient import TestClient

from app.core.config import settings
from app.schemas.rag import RagAskResponse


def _auth_headers(client: TestClient, email: str = "case-attachment-context@example.com") -> dict[str, str]:
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    login_response = client.post("/api/v1/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def test_text_attachment_is_extracted_on_upload(client: TestClient, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "upload_directory", str(tmp_path / "uploads"))
    headers = _auth_headers(client, "case-attachment-extract@example.com")
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Attachment extraction case", "domain_code": "01_civil_law"},
        headers=headers,
    )

    response = client.post(
        f"/api/v1/cases/{case_response.json()['id']}/attachments",
        headers=headers,
        files={"file": ("memo.txt", "계약 종료 후 보증금 미반환 자료".encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["extraction_status"] == "completed"
    assert response.json()["extracted_text_chars"] == len("계약 종료 후 보증금 미반환 자료")


def test_chat_message_api_passes_case_attachment_text_to_rag(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(settings, "upload_directory", str(tmp_path / "uploads"))
    headers = _auth_headers(client)
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Attachment context case", "domain_code": "01_civil_law"},
        headers=headers,
    )
    client.post(
        f"/api/v1/cases/{case_response.json()['id']}/attachments",
        headers=headers,
        files={"file": ("memo.txt", "계약 종료 후 보증금 미반환 자료".encode("utf-8"), "text/plain")},
    )
    session_response = client.post(
        "/api/v1/chat/sessions",
        json={
            "title": "첨부자료 상담",
            "domain_code": "01_civil_law",
            "case_id": case_response.json()["id"],
        },
        headers=headers,
    )

    captured = {}

    def fake_answer(self, question, domain_code=None, chat_history=None, answer_mode="general", case_context=None, case_id=None):
        captured["case_context"] = case_context
        captured["case_id"] = case_id
        return RagAskResponse(answer="첨부자료 기반 답변", is_ready=True, sources=[])

    monkeypatch.setattr("app.api.v1.routes.chat.RagService.answer", fake_answer)

    response = client.post(
        f"/api/v1/chat/sessions/{session_response.json()['id']}/messages",
        json={"content": "첨부자료 기준으로 설명해줘"},
        headers=headers,
    )

    assert response.status_code == 200
    assert "memo.txt" in captured["case_context"]
    assert "계약 종료 후 보증금 미반환 자료" in captured["case_context"]
    assert captured["case_id"] == case_response.json()["id"]


def test_case_attachment_can_be_reindexed(client: TestClient, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "upload_directory", str(tmp_path / "uploads"))
    headers = _auth_headers(client, "case-attachment-index@example.com")
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Attachment index case", "domain_code": "01_civil_law"},
        headers=headers,
    )
    upload_response = client.post(
        f"/api/v1/cases/{case_response.json()['id']}/attachments",
        headers=headers,
        files={"file": ("memo.txt", b"index this attachment", "text/plain")},
    )

    def fake_index(db, legal_case, attachment):
        attachment.vector_status = "completed"
        attachment.vector_chunk_count = 1
        return attachment

    monkeypatch.setattr("app.api.v1.routes.cases.index_case_attachment", fake_index)

    response = client.post(
        f"/api/v1/cases/{case_response.json()['id']}/attachments/{upload_response.json()['id']}/index",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["vector_status"] == "completed"
    assert response.json()["vector_chunk_count"] == 1
