from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.services.legal_case_service import (
    create_case_note,
    create_legal_case,
    list_case_notes,
    list_legal_cases,
)


def test_legal_case_service_creates_case_and_note(db_session: Session) -> None:
    user = User(email="case@example.com", hashed_password=hash_password("password123"), is_active=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    legal_case = create_legal_case(
        db_session,
        user.id,
        title="임대차 보증금 반환",
        summary="보증금 반환 분쟁",
        domain_code="01_civil_law",
    )
    note = create_case_note(db_session, legal_case, "사실관계", "계약 종료 후 보증금을 받지 못함")

    assert list_legal_cases(db_session, user.id)[0].id == legal_case.id
    assert list_case_notes(db_session, legal_case.id)[0].id == note.id


def test_case_api_creates_notes_and_links_chat_session(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "case-api@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "case-api@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    case_response = client.post(
        "/api/v1/cases",
        json={"title": "임대차 보증금 반환", "domain_code": "01_civil_law"},
        headers=headers,
    )
    note_response = client.post(
        f"/api/v1/cases/{case_response.json()['id']}/notes",
        json={"title": "핵심 사실", "content": "계약 종료 후 보증금 미반환"},
        headers=headers,
    )
    chat_response = client.post(
        "/api/v1/chat/sessions",
        json={
            "title": "보증금 질문",
            "domain_code": "01_civil_law",
            "case_id": case_response.json()["id"],
        },
        headers=headers,
    )
    cases_response = client.get("/api/v1/cases", headers=headers)

    assert case_response.status_code == 201
    assert case_response.json()["title"] == "임대차 보증금 반환"
    assert note_response.status_code == 201
    assert note_response.json()["content"] == "계약 종료 후 보증금 미반환"
    assert chat_response.status_code == 200
    assert chat_response.json()["case_id"] == case_response.json()["id"]
    assert cases_response.json()[0]["note_count"] == 1
    assert cases_response.json()[0]["chat_count"] == 1


def test_case_api_updates_owned_case_status(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "case-status@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "case-status@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Status case", "domain_code": "01_civil_law"},
        headers=headers,
    )

    response = client.patch(
        f"/api/v1/cases/{case_response.json()['id']}",
        json={"status": "closed"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_case_api_generates_case_insight_without_openai_key(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    client.post(
        "/api/v1/auth/register",
        json={"email": "case-insight@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "case-insight@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Insight case", "domain_code": "01_civil_law"},
        headers=headers,
    )
    client.post(
        f"/api/v1/cases/{case_response.json()['id']}/notes",
        json={"title": "핵심 사실", "content": "계약 종료 후 보증금을 받지 못함"},
        headers=headers,
    )

    response = client.post(f"/api/v1/cases/{case_response.json()['id']}/insight", headers=headers)
    cases_response = client.get("/api/v1/cases", headers=headers)

    assert response.status_code == 200
    assert response.json()["case_id"] == case_response.json()["id"]
    assert "Insight case" in response.json()["summary"]
    assert response.json()["issues"]
    assert response.json()["next_actions"]
    assert cases_response.json()[0]["summary"] == response.json()["summary"]


def test_case_api_updates_and_deletes_case_note(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "case-note-edit@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "case-note-edit@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Editable note case", "domain_code": "01_civil_law"},
        headers=headers,
    )
    note_response = client.post(
        f"/api/v1/cases/{case_response.json()['id']}/notes",
        json={"title": "초안", "content": "처음 작성한 메모"},
        headers=headers,
    )

    update_response = client.patch(
        f"/api/v1/cases/{case_response.json()['id']}/notes/{note_response.json()['id']}",
        json={"title": "수정본", "content": "수정한 메모"},
        headers=headers,
    )
    delete_response = client.delete(
        f"/api/v1/cases/{case_response.json()['id']}/notes/{note_response.json()['id']}",
        headers=headers,
    )
    notes_response = client.get(f"/api/v1/cases/{case_response.json()['id']}/notes", headers=headers)
    cases_response = client.get("/api/v1/cases", headers=headers)

    assert update_response.status_code == 200
    assert update_response.json()["title"] == "수정본"
    assert update_response.json()["content"] == "수정한 메모"
    assert delete_response.status_code == 204
    assert notes_response.json() == []
    assert cases_response.json()[0]["note_count"] == 0


def test_case_api_uploads_lists_and_deletes_attachment(client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_directory", str(tmp_path / "uploads"))
    client.post(
        "/api/v1/auth/register",
        json={"email": "case-attachment@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "case-attachment@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Attachment case", "domain_code": "01_civil_law"},
        headers=headers,
    )

    upload_response = client.post(
        f"/api/v1/cases/{case_response.json()['id']}/attachments",
        headers=headers,
        files={"file": ("contract.txt", b"contract body", "text/plain")},
    )
    list_response = client.get(f"/api/v1/cases/{case_response.json()['id']}/attachments", headers=headers)
    delete_response = client.delete(
        f"/api/v1/cases/{case_response.json()['id']}/attachments/{upload_response.json()['id']}",
        headers=headers,
    )
    empty_list_response = client.get(f"/api/v1/cases/{case_response.json()['id']}/attachments", headers=headers)

    assert upload_response.status_code == 201
    assert upload_response.json()["original_filename"] == "contract.txt"
    assert upload_response.json()["content_type"] == "text/plain"
    assert upload_response.json()["size_bytes"] == len(b"contract body")
    assert upload_response.json()["extraction_status"] == "completed"
    assert upload_response.json()["extracted_text_chars"] == len("contract body")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert delete_response.status_code == 204
    assert empty_list_response.json() == []


def test_chat_session_rejects_other_users_case(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "owner-case@example.com", "password": "password123"},
    )
    owner_login = client.post(
        "/api/v1/auth/login",
        data={"username": "owner-case@example.com", "password": "password123"},
    )
    owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "소유자 사건"},
        headers=owner_headers,
    )

    client.post(
        "/api/v1/auth/register",
        json={"email": "other-case@example.com", "password": "password123"},
    )
    other_login = client.post(
        "/api/v1/auth/login",
        data={"username": "other-case@example.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.post(
        "/api/v1/chat/sessions",
        json={"title": "침범 시도", "case_id": case_response.json()["id"]},
        headers=other_headers,
    )

    assert response.status_code == 404
