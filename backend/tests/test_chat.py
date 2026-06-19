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
    update_chat_session_pin,
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
    user_message = add_user_message(db_session, session, "계약 불이행 책임은 무엇인가요?", "issue")
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
        "issue",
    )

    sessions = list_chat_sessions(db_session, user.id)
    messages = list_chat_messages(db_session, session.id)

    assert sessions[0].id == session.id
    assert sessions[0].title == "계약 불이행 책임은 무엇인가요?"
    assert sessions[0].domain_code == "01_civil_law"
    assert sessions[0].is_pinned is False
    assert [message.id for message in messages] == [user_message.id, assistant_message.id]
    assert messages[0].answer_mode == "issue"
    assert messages[1].answer_mode == "issue"
    assert messages[1].sources[0]["id"] == "chunk-1"
    assert count_chat_messages(db_session, session.id) == 2
    assert get_last_chat_message(db_session, session.id).id == assistant_message.id


def test_pinned_chat_sessions_are_listed_first(db_session: Session) -> None:
    user = User(
        email="chat-pin@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    first = create_chat_session(db_session, user.id, "일반 대화")
    second = create_chat_session(db_session, user.id, "고정 대화")

    updated = update_chat_session_pin(db_session, user.id, second.id, True)
    sessions = list_chat_sessions(db_session, user.id)

    assert updated is not None
    assert updated.is_pinned is True
    assert [session.id for session in sessions] == [second.id, first.id]


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
    assert create_response.json()["is_pinned"] is False
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["title"] == "민사법 상담"
    assert sessions_response.json()[0]["domain_code"] == "01_civil_law"
    assert sessions_response.json()[0]["is_pinned"] is False
    assert sessions_response.json()[0]["message_count"] == 0
    assert sessions_response.json()[0]["last_message_preview"] is None
    assert messages_response.status_code == 200
    assert messages_response.json() == []


def test_chat_session_api_pins_owned_session(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "chat-pin-api@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "chat-pin-api@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/chat/sessions",
        json={"title": "중요 상담", "domain_code": "01_civil_law"},
        headers=headers,
    )
    pin_response = client.patch(
        f"/api/v1/chat/sessions/{create_response.json()['id']}/pin",
        json={"is_pinned": True},
        headers=headers,
    )

    assert pin_response.status_code == 200
    assert pin_response.json()["is_pinned"] is True


def test_chat_message_api_accepts_answer_mode(client: TestClient, monkeypatch) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "chat-mode-api@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "chat-mode-api@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/chat/sessions",
        json={"title": "답변 모드 테스트", "domain_code": "01_civil_law"},
        headers=headers,
    )

    captured = {}

    def fake_answer(self, question, domain_code=None, chat_history=None, answer_mode="general"):
        captured["answer_mode"] = answer_mode
        return RagAskResponse(answer="쟁점 정리 답변", is_ready=True, sources=[])

    monkeypatch.setattr("app.api.v1.routes.chat.RagService.answer", fake_answer)

    message_response = client.post(
        f"/api/v1/chat/sessions/{create_response.json()['id']}/messages",
        json={"content": "쟁점을 정리해줘", "answer_mode": "issue"},
        headers=headers,
    )

    assert message_response.status_code == 200
    assert captured["answer_mode"] == "issue"
    assert message_response.json()["user_message"]["answer_mode"] == "issue"
    assert message_response.json()["assistant_message"]["answer_mode"] == "issue"
