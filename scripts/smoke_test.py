from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://localhost:8000/api/v1"


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data = None
    request_headers = headers.copy() if headers else {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed_body = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed_body = body
        return exc.code, parsed_body


def login(base_url: str, email: str, password: str) -> str:
    data = urllib.parse.urlencode({"username": email, "password": password}).encode()
    request = urllib.request.Request(
        f"{base_url}/auth/login",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body["access_token"])


def print_step(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def run_smoke_test(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    email = args.email or f"smoke-{int(time.time())}@example.com"
    password = args.password

    status, health = request_json("GET", f"{base_url}/health")
    health_ok = status == 200 and isinstance(health, dict) and health.get("status") == "ok"
    print_step("health", health_ok, str(health))
    if not health_ok:
        return 1

    status, register_body = request_json(
        "POST",
        f"{base_url}/auth/register",
        {"email": email, "password": password},
    )
    register_ok = status in {201, 409}
    print_step("register", register_ok, f"status={status}")
    if not register_ok:
        print(register_body)
        return 1

    try:
        token = login(base_url, email, password)
    except Exception as exc:
        print_step("login", False, str(exc))
        return 1
    auth_headers = {"Authorization": f"Bearer {token}"}
    print_step("login", True)

    status, user = request_json("GET", f"{base_url}/auth/me", headers=auth_headers)
    me_ok = status == 200 and isinstance(user, dict) and user.get("email") == email
    print_step("current user", me_ok, str(user))
    if not me_ok:
        return 1

    status, history_before = request_json("GET", f"{base_url}/rag/history", headers=auth_headers)
    history_ok = status == 200 and isinstance(history_before, list)
    print_step("history list", history_ok, f"items={len(history_before) if isinstance(history_before, list) else 'n/a'}")
    if not history_ok:
        return 1

    if args.with_rag:
        status, answer = request_json(
            "POST",
            f"{base_url}/rag/ask",
            {
                "question": args.question,
                "domain_code": args.domain_code,
                "top_k": args.top_k,
            },
            headers=auth_headers,
        )
        ask_ok = status == 200 and isinstance(answer, dict) and answer.get("is_ready") is True
        print_step("rag ask", ask_ok, f"sources={len(answer.get('sources', [])) if isinstance(answer, dict) else 'n/a'}")
        if not ask_ok:
            print(answer)
            return 1

        status, history_after = request_json("GET", f"{base_url}/rag/history", headers=auth_headers)
        saved_ok = status == 200 and isinstance(history_after, list) and len(history_after) > len(history_before)
        print_step("history saved", saved_ok, f"items={len(history_after) if isinstance(history_after, list) else 'n/a'}")
        if not saved_ok:
            return 1

        query_id = history_after[0]["id"]
        status, _ = request_json("DELETE", f"{base_url}/rag/history/{query_id}", headers=auth_headers)
        delete_ok = status == 204
        print_step("history delete", delete_ok, f"status={status}")
        if not delete_ok:
            return 1

    print("Smoke test completed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small API smoke test against the legal RAG service.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default="Password123!")
    parser.add_argument("--with-rag", action="store_true", help="Also call /rag/ask. This uses OpenAI API credits.")
    parser.add_argument("--question", default="행정처분 취소소송에서 처분의 위법성을 다투려면 무엇을 확인해야 하나요?")
    parser.add_argument("--domain-code", default="03_administrative_law")
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    raise SystemExit(run_smoke_test(parse_args()))


if __name__ == "__main__":
    main()
