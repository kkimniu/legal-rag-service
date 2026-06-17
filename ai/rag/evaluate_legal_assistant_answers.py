from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.rag_service import RagService  # noqa: E402


DEFAULT_QUESTIONS_PATH = Path("ai/rag/legal_assistant_answer_questions.jsonl")
DEFAULT_OUTPUT_PATH = Path("data/processed/precedents/legal_assistant_answer_eval.probe_10k.json")

REQUIRED_SECTIONS = ("답변 요약", "관련 법령", "관련 판례", "주의사항")


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


def normalize_terms(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def source_text(source: Any) -> str:
    parts = [
        source.title or "",
        source.domain_name or "",
        source.source_type or "",
        source.text or "",
        " ".join(str(value) for value in source.metadata.values()),
    ]
    return " ".join(parts)


def evaluate_one(service: RagService, item: dict[str, Any]) -> dict[str, Any]:
    question = str(item.get("question") or "").strip()
    domain_code = str(item.get("domain_code") or "").strip() or None
    expected_terms = normalize_terms(item.get("expected_terms"))

    response = service.answer(question, domain_code=domain_code)
    answer = response.answer
    sources = response.sources
    combined_sources = "\n".join(source_text(source) for source in sources)

    section_hits = [section for section in REQUIRED_SECTIONS if section in answer]
    answer_term_hits = [term for term in expected_terms if term in answer]
    source_term_hits = [term for term in expected_terms if term in combined_sources]
    statute_sources = [source for source in sources if source.metadata.get("evidence_type") == "statute"]
    precedent_sources = [source for source in sources if source.metadata.get("evidence_type") == "precedent"]

    precedent_case_hits = [
        source.metadata.get("meta_case_number") or source.metadata.get("case_number")
        for source in precedent_sources
        if source.metadata.get("meta_case_number") or source.metadata.get("case_number")
    ]

    failure_reasons: list[str] = []
    if not response.is_ready:
        failure_reasons.append("rag_not_ready")
    if len(answer) < 180:
        failure_reasons.append("answer_too_short")
    if len(section_hits) < len(REQUIRED_SECTIONS):
        failure_reasons.append("missing_required_sections")
    if not statute_sources:
        failure_reasons.append("missing_statute_sources")
    if not precedent_sources:
        failure_reasons.append("missing_precedent_sources")
    if not source_term_hits:
        failure_reasons.append("expected_terms_not_in_sources")
    if not precedent_case_hits:
        failure_reasons.append("missing_precedent_case_number")
    if "참고 정보" not in answer and "전문가 상담" not in answer and "법률 자문" not in answer:
        failure_reasons.append("missing_disclaimer")

    return {
        "id": item.get("id"),
        "domain_code": domain_code,
        "question": question,
        "is_ready": response.is_ready,
        "passes": not failure_reasons,
        "failure_reasons": failure_reasons,
        "answer_chars": len(answer),
        "section_hits": section_hits,
        "answer_term_hits": answer_term_hits,
        "source_term_hits": source_term_hits,
        "source_count": len(sources),
        "statute_source_count": len(statute_sources),
        "precedent_source_count": len(precedent_sources),
        "precedent_case_numbers": precedent_case_hits[:5],
        "answer_preview": answer[:800],
        "sources": [
            {
                "id": source.id,
                "title": source.title,
                "domain_name": source.domain_name,
                "source_type": source.source_type,
                "evidence_type": source.metadata.get("evidence_type"),
                "case_number": source.metadata.get("meta_case_number") or source.metadata.get("case_number"),
                "score": source.score,
            }
            for source in sources
        ],
    }


def summarize_by_domain(results: list[dict[str, Any]]) -> dict[str, dict[str, int | float]]:
    per_domain: dict[str, dict[str, int | float]] = {}
    for result in results:
        domain = str(result.get("domain_code") or "unknown")
        metrics = per_domain.setdefault(
            domain,
            {
                "questions": 0,
                "passed": 0,
                "failed": 0,
                "avg_answer_chars": 0.0,
                "avg_source_count": 0.0,
                "avg_precedent_source_count": 0.0,
            },
        )
        metrics["questions"] = int(metrics["questions"]) + 1
        metrics["passed"] = int(metrics["passed"]) + int(bool(result["passes"]))
        metrics["failed"] = int(metrics["failed"]) + int(not result["passes"])
        metrics["avg_answer_chars"] = float(metrics["avg_answer_chars"]) + int(result["answer_chars"])
        metrics["avg_source_count"] = float(metrics["avg_source_count"]) + int(result["source_count"])
        metrics["avg_precedent_source_count"] = float(metrics["avg_precedent_source_count"]) + int(result["precedent_source_count"])

    for metrics in per_domain.values():
        questions = int(metrics["questions"])
        metrics["pass_rate"] = int(metrics["passed"]) / questions if questions else 0.0
        metrics["avg_answer_chars"] = float(metrics["avg_answer_chars"]) / questions if questions else 0.0
        metrics["avg_source_count"] = float(metrics["avg_source_count"]) / questions if questions else 0.0
        metrics["avg_precedent_source_count"] = float(metrics["avg_precedent_source_count"]) / questions if questions else 0.0
    return per_domain


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated legal assistant answers with statute and precedent evidence.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-questions", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = RagService(top_k=args.top_k)
    questions = list(read_jsonl(args.questions))
    if args.max_questions:
        questions = questions[: args.max_questions]

    results = [evaluate_one(service, item) for item in questions]
    total = len(results)
    passed = sum(1 for result in results if result["passes"])
    summary = {
        "questions": total,
        "top_k": args.top_k,
        "pass_rate": passed / total if total else 0.0,
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
            if not result["passes"]
        ],
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
