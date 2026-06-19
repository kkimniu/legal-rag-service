from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
