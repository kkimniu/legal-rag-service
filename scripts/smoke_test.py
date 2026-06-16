from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_QUESTION = "상속한정승인과 상속포기에 관한 법률 근거와 판례를 같이 알려줘"
DEFAULT_DOMAIN_CODE = "01_civil_law"
REQUIRED_ANSWER_SECTIONS = ("답변 요약", "관련 법령", "관련 판례", "주의사항")


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> tuple[int, Any]:
    data = None
    request_headers = headers.copy() if headers else {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed_body = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed_body = body
        return exc.code, parsed_body
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc.reason)}


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


def source_evidence_counts(sources: list[dict[str, Any]]) -> tuple[int, int]:
    statute_count = 0
    precedent_count = 0
    for source in sources:
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        evidence_type = metadata.get("evidence_type")
        if evidence_type == "statute":
            statute_count += 1
        elif evidence_type == "precedent":
            precedent_count += 1
    return statute_count, precedent_count


def answer_has_required_sections(answer: str) -> bool:
    return all(section in answer for section in REQUIRED_ANSWER_SECTIONS)


def run_rag_smoke(
    base_url: str,
    auth_headers: dict[str, str],
    question: str,
    domain_code: str,
    top_k: int,
    timeout: int,
) -> bool:
    status, answer = request_json(
        "POST",
        f"{base_url}/rag/ask",
        {
            "question": question,
            "domain_code": domain_code,
            "top_k": top_k,
        },
        headers=auth_headers,
        timeout=timeout,
    )
    ask_ok = status == 200 and isinstance(answer, dict) and answer.get("is_ready") is True
    sources = answer.get("sources", []) if isinstance(answer, dict) else []
    statute_count, precedent_count = source_evidence_counts(sources if isinstance(sources, list) else [])
    sections_ok = answer_has_required_sections(str(answer.get("answer") or "")) if isinstance(answer, dict) else False
    evidence_ok = statute_count > 0 and precedent_count > 0
    ok = ask_ok and sections_ok and evidence_ok
    print_step(
        "rag ask",
        ok,
        f"status={status}, sources={len(sources) if isinstance(sources, list) else 'n/a'}, "
        f"statute={statute_count}, precedent={precedent_count}, sections={sections_ok}",
    )
    if not ok:
        print(answer)
    return ok


def run_chat_smoke(
    base_url: str,
    auth_headers: dict[str, str],
    question: str,
    domain_code: str,
    timeout: int,
) -> bool:
    status, session = request_json(
        "POST",
        f"{base_url}/chat/sessions",
        {"title": None, "domain_code": domain_code},
        headers=auth_headers,
        timeout=timeout,
    )
    session_ok = status == 200 and isinstance(session, dict) and session.get("id")
    print_step("chat session create", session_ok, f"status={status}")
    if not session_ok:
        print(session)
        return False

    session_id = int(session["id"])
    try:
        status, turn = request_json(
            "POST",
            f"{base_url}/chat/sessions/{session_id}/messages",
            {"content": question},
            headers=auth_headers,
            timeout=timeout,
        )
        assistant = turn.get("assistant_message") if isinstance(turn, dict) else None
        answer = str(assistant.get("content") or "") if isinstance(assistant, dict) else ""
        sources = assistant.get("sources", []) if isinstance(assistant, dict) else []
        statute_count, precedent_count = source_evidence_counts(sources if isinstance(sources, list) else [])
        sections_ok = answer_has_required_sections(answer)
        chat_ok = (
            status == 200
            and isinstance(turn, dict)
            and turn.get("is_ready") is True
            and sections_ok
            and statute_count > 0
            and precedent_count > 0
        )
        print_step(
            "chat message",
            chat_ok,
            f"status={status}, sources={len(sources) if isinstance(sources, list) else 'n/a'}, "
            f"statute={statute_count}, precedent={precedent_count}, sections={sections_ok}",
        )
        if not chat_ok:
            print(turn)
        return chat_ok
    finally:
        request_json(
            "DELETE",
            f"{base_url}/chat/sessions/{session_id}",
            headers=auth_headers,
            timeout=30,
        )


def run_smoke_test(args: argparse.Namespace) -> int:
    base_url = args.base_url.rstrip("/")
    email = args.email or f"smoke-{int(time.time())}@example.com"
    password = args.password

    status, health = request_json("GET", f"{base_url}/health", timeout=args.timeout)
    health_ok = status == 200 and isinstance(health, dict) and health.get("status") == "ok"
    print_step("health", health_ok, str(health))
    if not health_ok:
        return 1

    status, register_body = request_json(
        "POST",
        f"{base_url}/auth/register",
        {"email": email, "password": password},
        timeout=args.timeout,
    )
    register_ok = status in {200, 201, 409}
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

    status, user = request_json("GET", f"{base_url}/auth/me", headers=auth_headers, timeout=args.timeout)
    me_ok = status == 200 and isinstance(user, dict) and user.get("email") == email
    print_step("current user", me_ok, str(user))
    if not me_ok:
        return 1

    status, history_before = request_json("GET", f"{base_url}/rag/history", headers=auth_headers, timeout=args.timeout)
    history_ok = status == 200 and isinstance(history_before, list)
    print_step("history list", history_ok, f"items={len(history_before) if isinstance(history_before, list) else 'n/a'}")
    if not history_ok:
        return 1

    if args.with_rag:
        if not run_rag_smoke(base_url, auth_headers, args.question, args.domain_code, args.top_k, args.timeout):
            return 1

        status, history_after = request_json("GET", f"{base_url}/rag/history", headers=auth_headers, timeout=args.timeout)
        saved_ok = status == 200 and isinstance(history_after, list) and len(history_after) > len(history_before)
        print_step("history saved", saved_ok, f"items={len(history_after) if isinstance(history_after, list) else 'n/a'}")
        if not saved_ok:
            return 1

        query_id = history_after[0]["id"]
        status, _ = request_json("DELETE", f"{base_url}/rag/history/{query_id}", headers=auth_headers, timeout=args.timeout)
        delete_ok = status == 204
        print_step("history delete", delete_ok, f"status={status}")
        if not delete_ok:
            return 1

    if args.with_chat and not run_chat_smoke(base_url, auth_headers, args.question, args.domain_code, args.timeout):
        return 1

    print("Smoke test completed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run API smoke tests against the legal RAG service.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default="Password123!")
    parser.add_argument("--with-rag", action="store_true", help="Also call /rag/ask. This uses OpenAI API credits.")
    parser.add_argument("--with-chat", action="store_true", help="Also create a chat session and send one message.")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--domain-code", default=DEFAULT_DOMAIN_CODE)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args()


def main() -> None:
    raise SystemExit(run_smoke_test(parse_args()))


if __name__ == "__main__":
    main()
