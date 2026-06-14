from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.rag import RagAskResponse, RagSource
from app.services.chat_service import (
    add_assistant_message,
    add_user_message,
    count_chat_messages,
    create_chat_session,
    delete_chat_session,
    get_last_chat_message,
    list_chat_messages,
    list_chat_sessions,
)


def test_chat_service_stores_sessions_and_messages(db_session: Session) -> None:
    user = User(
        email="chat@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    session = create_chat_session(db_session, user.id, domain_code="01_civil_law")
    user_message = add_user_message(db_session, session, "계약 불이행 책임은 무엇인가요?")
    assistant_message = add_assistant_message(
        db_session,
        session,
        RagAskResponse(
            answer="근거 기반 답변입니다.",
            is_ready=True,
            sources=[
                RagSource(
                    id="chunk-1",
                    title="계약",
                    domain_name="민사법",
                    source_type="qa",
                    text="근거 본문",
                    score=0.1,
                    metadata={},
                )
            ],
        ),
    )

    sessions = list_chat_sessions(db_session, user.id)
    messages = list_chat_messages(db_session, session.id)

    assert sessions[0].id == session.id
    assert sessions[0].title == "계약 불이행 책임은 무엇인가요?"
    assert sessions[0].domain_code == "01_civil_law"
    assert [message.id for message in messages] == [user_message.id, assistant_message.id]
    assert messages[1].sources[0]["id"] == "chunk-1"
    assert count_chat_messages(db_session, session.id) == 2
    assert get_last_chat_message(db_session, session.id).id == assistant_message.id


def test_delete_chat_session_only_deletes_owner_session(db_session: Session) -> None:
    owner = User(email="chat-owner@example.com", hashed_password=hash_password("password123"), is_active=True)
    other = User(email="chat-other@example.com", hashed_password=hash_password("password123"), is_active=True)
    db_session.add_all([owner, other])
    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(other)

    session = create_chat_session(db_session, owner.id, "삭제할 대화")

    assert delete_chat_session(db_session, other.id, session.id) is False
    assert len(list_chat_sessions(db_session, owner.id)) == 1

    assert delete_chat_session(db_session, owner.id, session.id) is True
    assert list_chat_sessions(db_session, owner.id) == []


def test_chat_session_api_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/chat/sessions")

    assert response.status_code == 401


def test_chat_session_api_creates_and_reads_owned_session(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "chat-api@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "chat-api@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/chat/sessions",
        json={"title": "민사법 상담", "domain_code": "01_civil_law"},
        headers=headers,
    )
    sessions_response = client.get("/api/v1/chat/sessions", headers=headers)
    messages_response = client.get(
        f"/api/v1/chat/sessions/{create_response.json()['id']}/messages",
        headers=headers,
    )

    assert create_response.status_code == 200
    assert create_response.json()["title"] == "민사법 상담"
    assert create_response.json()["domain_code"] == "01_civil_law"
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["title"] == "민사법 상담"
    assert sessions_response.json()[0]["domain_code"] == "01_civil_law"
    assert sessions_response.json()[0]["message_count"] == 0
    assert sessions_response.json()[0]["last_message_preview"] is None
    assert messages_response.status_code == 200
    assert messages_response.json() == []
