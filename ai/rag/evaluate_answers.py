from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DEFAULT_QUESTIONS_PATH = Path("ai/rag/evaluation_questions.jsonl")
DEFAULT_OUTPUT_PATH = Path("data/processed/answer_eval.medium.json")
DEFAULT_API_URL = "http://localhost:8000/api/v1/rag/ask"


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            if isinstance(data, dict):
                yield data


def select_questions(
    questions: Iterable[dict[str, Any]],
    max_questions: int | None,
    per_domain_limit: int | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    domain_counts: Counter[str] = Counter()

    for item in questions:
        domain_code = str(item.get("domain_code") or "unknown")
        if per_domain_limit and domain_counts[domain_code] >= per_domain_limit:
            continue

        selected.append(item)
        domain_counts[domain_code] += 1

        if max_questions and len(selected) >= max_questions:
            break

    return selected


def post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API request failed with {exc.code}: {detail}") from exc
    return json.loads(data)


def normalize_terms(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def evaluate_answer(item: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    answer = str(response.get("answer") or "")
    sources = response.get("sources") if isinstance(response.get("sources"), list) else []
    expected_terms = normalize_terms(item.get("expected_terms"))

    answer_term_hits = [term for term in expected_terms if term in answer]
    source_term_hits = sorted(
        {
            term
            for source in sources
            for term in expected_terms
            if term in str(source.get("text") or "")
        }
    )
    source_domains = [str(source.get("domain_name") or "") for source in sources]
    has_disclaimer = any(token in answer for token in ("참고 정보", "참고정보", "법률 자문", "전문가 상담"))
    mentions_evidence = any(token in answer for token in ("근거", "제공된", "검색된", "위 자료"))
    failure_reasons = []
    if not response.get("is_ready"):
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

    return {
        "id": item.get("id"),
        "domain_code": item.get("domain_code"),
        "domain_name": item.get("domain_name"),
        "question": item.get("question"),
        "is_ready": bool(response.get("is_ready")),
        "answer_chars": len(answer),
        "source_count": len(sources),
        "has_disclaimer": has_disclaimer,
        "mentions_evidence": mentions_evidence,
        "answer_term_hits": answer_term_hits,
        "source_term_hits": source_term_hits,
        "failure_reasons": failure_reasons,
        "passes_basic_quality": not failure_reasons,
        "source_domains": source_domains,
        "answer_preview": answer[:500],
    }


def summarize_by_domain(results: list[dict[str, Any]]) -> dict[str, dict[str, int | float]]:
    per_domain: dict[str, dict[str, int | float]] = {}
    for result in results:
        domain_code = str(result["domain_code"])
        metrics = per_domain.setdefault(
            domain_code,
            {
                "questions": 0,
                "passed": 0,
                "failed": 0,
                "avg_answer_chars": 0,
                "avg_source_count": 0,
            },
        )
        metrics["questions"] = int(metrics["questions"]) + 1
        metrics["passed"] = int(metrics["passed"]) + int(bool(result["passes_basic_quality"]))
        metrics["failed"] = int(metrics["failed"]) + int(not result["passes_basic_quality"])
        metrics["avg_answer_chars"] = float(metrics["avg_answer_chars"]) + int(result["answer_chars"])
        metrics["avg_source_count"] = float(metrics["avg_source_count"]) + int(result["source_count"])

    for metrics in per_domain.values():
        questions = int(metrics["questions"])
        metrics["pass_rate"] = int(metrics["passed"]) / questions if questions else 0
        metrics["avg_answer_chars"] = float(metrics["avg_answer_chars"]) / questions if questions else 0
        metrics["avg_source_count"] = float(metrics["avg_source_count"]) / questions if questions else 0

    return per_domain


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated RAG answers with lightweight quality checks.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--use-domain-filter", action="store_true")
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--per-domain-limit", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected_questions = select_questions(
        questions=read_jsonl(args.questions),
        max_questions=args.max_questions,
        per_domain_limit=args.per_domain_limit,
    )

    results = []
    for item in selected_questions:
        payload = {
            "question": item["question"],
            "top_k": args.top_k,
            "domain_code": item["domain_code"] if args.use_domain_filter else None,
        }
        response = post_json(args.api_url, payload, args.timeout_seconds)
        results.append(evaluate_answer(item, response))

    total = len(results)
    passed = sum(1 for result in results if result["passes_basic_quality"])
    summary = {
        "questions": total,
        "api_url": args.api_url,
        "top_k": args.top_k,
        "use_domain_filter": args.use_domain_filter,
        "basic_quality_pass_rate": passed / total if total else 0,
        "passed": passed,
        "failed": total - passed,
        "per_domain": summarize_by_domain(results),
        "failed_results": [
            {
                "id": result["id"],
                "domain_code": result["domain_code"],
                "failure_reasons": result["failure_reasons"],
            }
            for result in results
            if not result["passes_basic_quality"]
        ],
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
