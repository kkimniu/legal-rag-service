from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_OUTPUT_PATH = Path("data/processed/chat_answer_eval.probe.json")

# 4개 분야 × 2 케이스, 각 케이스마다 첫 질문 + 후속 질문
EVAL_CASES: list[dict[str, Any]] = [
    {
        "id": "civil_lease_deposit",
        "domain_code": "01_civil_law",
        "domain_name": "민사법",
        "first_question": "임대차 계약에서 보증금 반환이 거부될 때 어떤 법적 절차를 밟아야 하나요?",
        "first_expected_terms": ["보증금", "임대차", "반환"],
        "followup_question": "보증금 반환 소송에서 소멸시효는 몇 년이고 기산점은 어떻게 정해지나요?",
        "followup_expected_terms": ["소멸시효", "기간"],
        "context_bridge_terms": ["보증금", "임대차"],
    },
    {
        "id": "civil_damages_penalty",
        "domain_code": "01_civil_law",
        "domain_name": "민사법",
        "first_question": "계약 위반으로 손해배상을 청구할 때 어떤 요건을 확인해야 하나요?",
        "first_expected_terms": ["손해배상", "채무불이행", "책임"],
        "followup_question": "위약금 약정이 있는 경우 실제 손해를 초과하는 금액도 청구할 수 있나요?",
        "followup_expected_terms": ["위약금", "손해배상"],
        "context_bridge_terms": ["손해배상", "계약"],
    },
    {
        "id": "ip_trademark_infringement",
        "domain_code": "02_intellectual_property_law",
        "domain_name": "지식재산권법",
        "first_question": "상표 침해가 의심될 때 먼저 확인해야 할 사항은 무엇인가요?",
        "first_expected_terms": ["상표", "침해", "유사"],
        "followup_question": "상표 침해가 인정되면 어떤 민사·형사 구제 수단을 활용할 수 있나요?",
        "followup_expected_terms": ["침해", "구제"],
        "context_bridge_terms": ["상표", "침해"],
    },
    {
        "id": "ip_patent_scope",
        "domain_code": "02_intellectual_property_law",
        "domain_name": "지식재산권법",
        "first_question": "특허권에서 청구범위 해석이 침해 판단에 왜 중요한가요?",
        "first_expected_terms": ["특허", "청구범위", "침해"],
        "followup_question": "균등론이 적용되면 청구범위 문언을 벗어난 경우에도 침해가 인정될 수 있나요?",
        "followup_expected_terms": ["균등론", "청구범위"],
        "context_bridge_terms": ["특허", "청구범위"],
    },
    {
        "id": "admin_disposition_appeal",
        "domain_code": "03_administrative_law",
        "domain_name": "행정법",
        "first_question": "행정처분에 불복하려면 행정심판과 행정소송 중 어떤 절차를 선택해야 하나요?",
        "first_expected_terms": ["행정처분", "취소", "심판"],
        "followup_question": "제소기간을 이미 지났는데 다른 구제 방법이 있나요?",
        "followup_expected_terms": ["제소기간", "구제"],
        "context_bridge_terms": ["행정처분", "취소"],
    },
    {
        "id": "admin_fine_suspension",
        "domain_code": "03_administrative_law",
        "domain_name": "행정법",
        "first_question": "과징금 처분이 재량권 남용에 해당한다고 다투려면 어떤 주장을 해야 하나요?",
        "first_expected_terms": ["과징금", "재량", "처분"],
        "followup_question": "이 처분에 대해 집행정지를 신청하려면 어떤 요건을 충족해야 하나요?",
        "followup_expected_terms": ["집행정지", "요건"],
        "context_bridge_terms": ["과징금", "처분"],
    },
    {
        "id": "criminal_fraud_complaint",
        "domain_code": "04_criminal_law",
        "domain_name": "형사법",
        "first_question": "사기죄로 고소할 때 입증해야 할 구성요건은 무엇인가요?",
        "first_expected_terms": ["사기", "기망", "재산"],
        "followup_question": "경찰이 불기소 의견을 냈을 때 피해자로서 이의를 제기하는 절차가 있나요?",
        "followup_expected_terms": ["불기소", "이의"],
        "context_bridge_terms": ["사기", "피해"],
    },
    {
        "id": "criminal_self_defense_excess",
        "domain_code": "04_criminal_law",
        "domain_name": "형사법",
        "first_question": "정당방위가 인정되기 위한 요건은 구체적으로 어떻게 되나요?",
        "first_expected_terms": ["정당방위", "방위", "상당성"],
        "followup_question": "방위 행위가 지나쳤다고 판단될 경우 과잉방위로 처벌받을 수 있나요?",
        "followup_expected_terms": ["과잉방위", "방위"],
        "context_bridge_terms": ["정당방위", "방위"],
    },
]


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 180,
) -> tuple[int, Any]:
    data = None
    req_headers = headers.copy() if headers else {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed


def login(base_url: str, email: str, password: str) -> str:
    data = urllib.parse.urlencode({"username": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{base_url}/auth/login",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return str(body["access_token"])


def setup_auth(base_url: str, email: str, password: str) -> str:
    """Register (409 = already exists is fine) then login."""
    request_json("POST", f"{base_url}/auth/register", {"email": email, "password": password})
    return login(base_url, email, password)


def evaluate_turn(
    turn: int,
    question: str,
    expected_terms: list[str],
    context_bridge_terms: list[str],
    response: dict[str, Any],
    check_context: bool,
) -> dict[str, Any]:
    assistant_msg = response.get("assistant_message") or {}
    answer = str(assistant_msg.get("content") or "")
    sources: list[dict] = assistant_msg.get("sources") or []
    is_ready = bool(response.get("is_ready"))

    answer_term_hits = [t for t in expected_terms if t in answer]
    source_term_hits = sorted(
        {t for src in sources for t in expected_terms if t in str(src.get("text") or "")}
    )
    context_hits = [t for t in context_bridge_terms if t in answer] if check_context else []

    has_disclaimer = any(
        tok in answer for tok in ("참고 정보", "참고정보", "법률 자문", "전문가 상담")
    )
    mentions_evidence = any(
        tok in answer for tok in ("근거", "제공된", "검색된", "위 자료")
    )

    failure_reasons: list[str] = []
    if not is_ready:
        failure_reasons.append("rag_not_ready")
    if len(answer) < 80:
        failure_reasons.append("answer_too_short")
    if len(sources) == 0:
        failure_reasons.append("no_sources")
    if not has_disclaimer:
        failure_reasons.append("missing_disclaimer")
    if not mentions_evidence:
        failure_reasons.append("missing_evidence_reference")
    if not source_term_hits:
        failure_reasons.append("expected_terms_not_in_sources")
    if check_context and not context_hits:
        failure_reasons.append("context_not_continued")

    return {
        "turn": turn,
        "question": question,
        "is_ready": is_ready,
        "answer_chars": len(answer),
        "source_count": len(sources),
        "has_disclaimer": has_disclaimer,
        "mentions_evidence": mentions_evidence,
        "answer_term_hits": answer_term_hits,
        "source_term_hits": source_term_hits,
        "context_hits": context_hits,
        "failure_reasons": failure_reasons,
        "passes": not failure_reasons,
        "answer_preview": answer[:400],
    }


def run_case(
    base_url: str,
    auth_headers: dict[str, str],
    case: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    status, session = request_json(
        "POST",
        f"{base_url}/chat/sessions",
        {"title": None, "domain_code": case["domain_code"]},
        auth_headers,
        timeout,
    )
    if status != 200 or not isinstance(session, dict):
        return {
            "id": case["id"],
            "domain_code": case["domain_code"],
            "domain_name": case["domain_name"],
            "error": f"session create failed: {status} {session}",
            "passes": False,
            "turn_results": [],
        }

    session_id = int(session["id"])
    turn_results: list[dict[str, Any]] = []

    try:
        status, turn1_resp = request_json(
            "POST",
            f"{base_url}/chat/sessions/{session_id}/messages",
            {"content": case["first_question"]},
            auth_headers,
            timeout,
        )
        if status != 200:
            return {
                "id": case["id"],
                "domain_code": case["domain_code"],
                "domain_name": case["domain_name"],
                "session_id": session_id,
                "error": f"turn1 failed: {status} {turn1_resp}",
                "passes": False,
                "turn_results": [],
            }

        t1 = evaluate_turn(
            turn=1,
            question=case["first_question"],
            expected_terms=case["first_expected_terms"],
            context_bridge_terms=[],
            response=turn1_resp,
            check_context=False,
        )
        turn_results.append(t1)

        status, turn2_resp = request_json(
            "POST",
            f"{base_url}/chat/sessions/{session_id}/messages",
            {"content": case["followup_question"]},
            auth_headers,
            timeout,
        )
        if status != 200:
            t2: dict[str, Any] = {
                "turn": 2,
                "question": case["followup_question"],
                "error": f"turn2 failed: {status} {turn2_resp}",
                "passes": False,
                "failure_reasons": ["api_error"],
                "context_hits": [],
            }
        else:
            t2 = evaluate_turn(
                turn=2,
                question=case["followup_question"],
                expected_terms=case["followup_expected_terms"],
                context_bridge_terms=case["context_bridge_terms"],
                response=turn2_resp,
                check_context=True,
            )
        turn_results.append(t2)

    finally:
        request_json(
            "DELETE",
            f"{base_url}/chat/sessions/{session_id}",
            headers=auth_headers,
            timeout=30,
        )

    both_pass = all(t.get("passes", False) for t in turn_results)
    return {
        "id": case["id"],
        "domain_code": case["domain_code"],
        "domain_name": case["domain_name"],
        "session_id": session_id,
        "passes": both_pass,
        "turn_results": turn_results,
    }


def summarize_by_domain(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    per_domain: dict[str, dict[str, Any]] = {}
    for result in results:
        domain_code = str(result.get("domain_code") or "unknown")
        m = per_domain.setdefault(
            domain_code,
            {
                "domain_name": result.get("domain_name", ""),
                "cases": 0,
                "passed": 0,
                "failed": 0,
                "turn1_passed": 0,
                "turn2_passed": 0,
                "context_continued": 0,
                "avg_answer_chars_t1": 0.0,
                "avg_answer_chars_t2": 0.0,
                "avg_source_count_t1": 0.0,
                "avg_source_count_t2": 0.0,
            },
        )
        m["cases"] += 1
        m["passed"] += int(result.get("passes", False))
        m["failed"] += int(not result.get("passes", False))

        for t in result.get("turn_results", []):
            n = t.get("turn", 0)
            if n == 1:
                m["turn1_passed"] += int(t.get("passes", False))
                m["avg_answer_chars_t1"] += t.get("answer_chars", 0)
                m["avg_source_count_t1"] += t.get("source_count", 0)
            elif n == 2:
                m["turn2_passed"] += int(t.get("passes", False))
                m["avg_answer_chars_t2"] += t.get("answer_chars", 0)
                m["avg_source_count_t2"] += t.get("source_count", 0)
                m["context_continued"] += int(bool(t.get("context_hits")))

    for m in per_domain.values():
        n = int(m["cases"]) or 1
        m["pass_rate"] = float(m["passed"]) / n
        m["context_continuation_rate"] = float(m["context_continued"]) / n
        m["avg_answer_chars_t1"] = float(m["avg_answer_chars_t1"]) / n
        m["avg_answer_chars_t2"] = float(m["avg_answer_chars_t2"]) / n
        m["avg_source_count_t1"] = float(m["avg_source_count_t1"]) / n
        m["avg_source_count_t2"] = float(m["avg_source_count_t2"]) / n

    return per_domain


def print_step(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="챗봇 API 기준 답변 품질 평가 스크립트. "
        "분야별 2문항씩 첫 질문+후속 질문 멀티턴을 실행하고 품질 지표를 수집합니다."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--email",
        default=None,
        help="테스트용 계정 이메일. 미지정시 타임스탬프 기반 임시 계정 생성",
    )
    parser.add_argument("--password", default="Password123!")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="각 API 호출 타임아웃(초)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    email = args.email or f"eval-chat-{int(time.time())}@example.com"

    print(f"[AUTH] {email}")
    try:
        token = setup_auth(base_url, email, args.password)
    except Exception as exc:
        print(f"[FAIL] auth - {exc}")
        raise SystemExit(1)
    auth_headers = {"Authorization": f"Bearer {token}"}
    print_step("auth", True)

    results: list[dict[str, Any]] = []
    for case in EVAL_CASES:
        print(f"\n--- {case['id']} ({case['domain_name']}) ---")
        result = run_case(base_url, auth_headers, case, args.timeout)
        turns = result.get("turn_results", [])
        t1 = next((t for t in turns if t.get("turn") == 1), {})
        t2 = next((t for t in turns if t.get("turn") == 2), {})
        print_step(
            "T1",
            bool(t1.get("passes")),
            f"chars={t1.get('answer_chars', 0)}, srcs={t1.get('source_count', 0)}, "
            f"terms={t1.get('answer_term_hits', [])}",
        )
        print_step(
            "T2",
            bool(t2.get("passes")),
            f"chars={t2.get('answer_chars', 0)}, srcs={t2.get('source_count', 0)}, "
            f"ctx={'yes' if t2.get('context_hits') else 'no'}({t2.get('context_hits', [])})",
        )
        if result.get("error"):
            print(f"  error: {result['error']}")
        results.append(result)

    total = len(results)
    passed = sum(1 for r in results if r.get("passes"))
    per_domain = summarize_by_domain(results)

    output: dict[str, Any] = {
        "eval_type": "chat_api_multiturn",
        "base_url": base_url,
        "eval_email": email,
        "total_cases": total,
        "total_passed": passed,
        "total_failed": total - passed,
        "overall_pass_rate": passed / total if total else 0,
        "per_domain": per_domain,
        "failed_cases": [
            {
                "id": r["id"],
                "domain_code": r.get("domain_code"),
                "turn_failures": [
                    {
                        "turn": t.get("turn"),
                        "failure_reasons": t.get("failure_reasons", []),
                    }
                    for t in r.get("turn_results", [])
                    if not t.get("passes")
                ],
            }
            for r in results
            if not r.get("passes")
        ],
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 60)
    summary_keys = [k for k in output if k != "results"]
    print(json.dumps({k: output[k] for k in summary_keys}, ensure_ascii=False, indent=2))
    print(f"\noutput: {args.output}")


if __name__ == "__main__":
    main()
