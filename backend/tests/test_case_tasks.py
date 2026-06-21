from fastapi.testclient import TestClient


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    response = client.post("/api/v1/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_case_task_api_manages_deadline_and_completion(client: TestClient) -> None:
    headers = _auth_headers(client, "case-task@example.com")
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Task case", "domain_code": "01_civil_law"},
        headers=headers,
    )
    case_id = case_response.json()["id"]

    create_response = client.post(
        f"/api/v1/cases/{case_id}/tasks",
        json={"title": "내용증명 발송", "due_date": "2026-07-01"},
        headers=headers,
    )
    task_id = create_response.json()["id"]
    list_response = client.get(f"/api/v1/cases/{case_id}/tasks", headers=headers)
    update_response = client.put(
        f"/api/v1/cases/{case_id}/tasks/{task_id}",
        json={"title": "내용증명 발송 완료", "due_date": "2026-07-01", "is_completed": True},
        headers=headers,
    )
    delete_response = client.delete(f"/api/v1/cases/{case_id}/tasks/{task_id}", headers=headers)
    empty_response = client.get(f"/api/v1/cases/{case_id}/tasks", headers=headers)

    assert create_response.status_code == 201
    assert create_response.json()["due_date"] == "2026-07-01"
    assert create_response.json()["is_completed"] is False
    assert list_response.json()[0]["title"] == "내용증명 발송"
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "내용증명 발송 완료"
    assert update_response.json()["is_completed"] is True
    assert delete_response.status_code == 204
    assert empty_response.json() == []


def test_case_task_api_rejects_other_user(client: TestClient) -> None:
    owner_headers = _auth_headers(client, "case-task-owner@example.com")
    case_response = client.post(
        "/api/v1/cases",
        json={"title": "Private task case"},
        headers=owner_headers,
    )
    other_headers = _auth_headers(client, "case-task-other@example.com")

    response = client.get(f"/api/v1/cases/{case_response.json()['id']}/tasks", headers=other_headers)

    assert response.status_code == 404
