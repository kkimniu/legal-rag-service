from fastapi.testclient import TestClient

from app.schemas.rag import RagAskResponse


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    response = client.post("/api/v1/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_case_timeline_aggregates_owned_activity(client: TestClient, monkeypatch) -> None:
    headers = _auth_headers(client, "timeline@example.com")
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "보증금 반환 사건", "domain_code": "01_civil_law"},
        headers=headers,
    )
    case_id = case_response.json()["id"]
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"title": "임대차계약서 확인", "content": "계약 종료일과 보증금을 확인했다."},
        headers=headers,
    )
    client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "내용증명 발송", "due_date": "2026-07-01"},
        headers=headers,
    )
    session_response = client.post(
        "/api/v1/chat/sessions",
        json={"title": "보증금 상담", "case_id": case_id, "domain_code": "01_civil_law"},
        headers=headers,
    )

    def fake_answer(self, question, domain_code=None, chat_history=None, answer_mode="general", case_context=None, case_id=None):
        return RagAskResponse(answer="확인할 사항을 정리했습니다.", is_ready=True, sources=[])

    monkeypatch.setattr("app.api.v1.routes.chat.RagService.answer", fake_answer)
    client.post(
        f"/api/v1/chat/sessions/{session_response.json()['id']}/messages",
        json={"content": "보증금을 받으려면 무엇을 해야 하나요?"},
        headers=headers,
    )

    response = client.get(f"/api/v1/cases/{case_id}/timeline", headers=headers)

    assert response.status_code == 200
    items = response.json()
    assert {"case", "note", "task", "chat"}.issubset({item["activity_type"] for item in items})
    assert any(item["session_id"] == session_response.json()["id"] for item in items if item["activity_type"] == "chat")
    assert [item["occurred_at"] for item in items] == sorted(
        [item["occurred_at"] for item in items], reverse=True
    )


def test_case_timeline_rejects_another_users_case(client: TestClient) -> None:
    owner_headers = _auth_headers(client, "timeline-owner@example.com")
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Owner case", "domain_code": "01_civil_law"},
        headers=owner_headers,
    )
    other_headers = _auth_headers(client, "timeline-other@example.com")

    response = client.get(
        f"/api/v1/cases/{case_response.json()['id']}/timeline",
        headers=other_headers,
    )

    assert response.status_code == 404
