from fastapi.testclient import TestClient

from app.schemas.rag import RagAskResponse


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    response = client.post("/api/v1/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_personal_search_finds_owned_workspace_content(client: TestClient, monkeypatch, tmp_path) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_directory", str(tmp_path / "uploads"))
    headers = _auth_headers(client, "personal-search@example.com")
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "보증금 통합검색 사건", "domain_code": "01_civil_law"},
        headers=headers,
    )
    case_id = case_response.json()["id"]
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "보증금 메모", "content": "임대인이 보증금을 반환하지 않음"},
        headers=headers,
    )
    client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "보증금 내용증명 발송", "due_date": "2026-07-01"},
        headers=headers,
    )
    client.post(
        f"/api/v1/cases/{case_id}/attachments",
        files={"file": ("deposit.txt", "보증금 계약서 내용".encode("utf-8"), "text/plain")},
        headers=headers,
    )
    session_response = client.post(
        "/api/v1/chat/sessions",
        json={"title": "보증금 상담", "case_id": case_id, "domain_code": "01_civil_law"},
        headers=headers,
    )

    def fake_answer(self, question, domain_code=None, chat_history=None, answer_mode="general", case_context=None, case_id=None):
        return RagAskResponse(answer="보증금 검색 답변", is_ready=True, sources=[])

    monkeypatch.setattr("app.api.v1.routes.chat.RagService.answer", fake_answer)
    client.post(
        f"/api/v1/chat/sessions/{session_response.json()['id']}/messages",
        json={"content": "보증금 반환 방법"},
        headers=headers,
    )

    other_headers = _auth_headers(client, "personal-search-other@example.com")
    client.post("/api/v1/cases", json={"title": "보증금 다른 사용자 비밀"}, headers=other_headers)

    response = client.get("/api/v1/search", params={"q": "보증금"}, headers=headers)

    assert response.status_code == 200
    result_types = {item["result_type"] for item in response.json()["results"]}
    assert {"case", "note", "task", "attachment", "chat"}.issubset(result_types)
    assert all("다른 사용자 비밀" not in item["title"] for item in response.json()["results"])


def test_personal_search_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/search", params={"q": "보증금"})

    assert response.status_code == 401
