from fastapi.testclient import TestClient


def test_register_login_and_read_current_user(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert register_response.status_code == 201
    assert register_response.json()["email"] == "user@example.com"
    assert "hashed_password" not in register_response.json()

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "password123"},
    )

    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert login_response.json()["token_type"] == "bearer"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


def test_register_duplicate_email_returns_conflict(client: TestClient) -> None:
    payload = {"email": "duplicate@example.com", "password": "password123"}

    first_response = client.post("/api/v1/auth/register", json=payload)
    second_response = client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_login_with_wrong_password_returns_unauthorized(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_read_current_user_without_token_returns_unauthorized(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
