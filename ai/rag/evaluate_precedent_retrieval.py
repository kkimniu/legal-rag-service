from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import chromadb
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings


DEFAULT_QUESTIONS_PATH = Path("ai/rag/precedent_evaluation_questions.jsonl")
DEFAULT_PERSIST_DIR = Path("chroma_db")
DEFAULT_COLLECTION_NAME = "precedent_chunks_probe_10k"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


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


def extract_keywords(question: str) -> list[str]:
    stopwords = {
        "관련",
        "판례",
        "근거",
        "알려줘",
        "찾아줘",
        "있어",
        "있나요",
        "어떤",
        "여부",
        "판단",
    }
    particles = ("으로", "에서", "에게", "에는", "이라면", "라면", "인가요", "하나요", "가", "이", "을", "를", "은", "는", "의", "도")
    keywords: list[str] = []

    for token in re.findall(r"[0-9A-Za-z가-힣]+", question):
        normalized = token
        for particle in particles:
            if len(normalized) > len(particle) + 1 and normalized.endswith(particle):
                normalized = normalized[: -len(particle)]
                break
        if len(normalized) >= 2 and normalized not in stopwords and normalized not in keywords:
            keywords.append(normalized)
    return keywords[:4]


def metadata_text(metadata: dict[str, Any]) -> str:
    return " ".join(str(value) for value in metadata.values() if value is not None)


def build_sources(result: dict[str, Any], expected_terms: list[str]) -> list[dict[str, Any]]:
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    ids = result.get("ids", [[]])[0]

    sources = []
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
        safe_metadata = metadata if isinstance(metadata, dict) else {}
        text = str(document or "")
        searchable_text = f"{text} {metadata_text(safe_metadata)}"
        sources.append(
            {
                "id": str(chunk_id),
                "domain_code": str(safe_metadata.get("domain_code") or ""),
                "domain_name": str(safe_metadata.get("domain_name") or ""),
                "source_type": str(safe_metadata.get("source_type") or ""),
                "title": str(safe_metadata.get("title") or ""),
                "case_number": str(safe_metadata.get("meta_case_number") or safe_metadata.get("case_number") or ""),
                "score": float(distance) if distance is not None else None,
                "term_hits": [term for term in expected_terms if term in searchable_text],
            }
        )
    return sources


def merge_sources(*source_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for sources in source_groups:
        for source in sources:
            source_id = source["id"]
            if source_id in seen_ids:
                continue
            merged.append(source)
            seen_ids.add(source_id)
    return merged


def evaluate_question(
    collection: Any,
    embeddings: OpenAIEmbeddings,
    item: dict[str, Any],
    top_k: int,
    use_expected_domain_filter: bool,
    use_keyword_boost: bool,
) -> dict[str, Any]:
    question = str(item.get("question") or "").strip()
    expected_domain = str(item.get("domain_code") or "").strip()
    expected_terms = normalize_terms(item.get("expected_terms"))
    query_embedding = embeddings.embed_query(question)

    query_kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if use_expected_domain_filter and expected_domain:
        query_kwargs["where"] = {"domain_code": expected_domain}

    sources = build_sources(collection.query(**query_kwargs), expected_terms)

    if use_keyword_boost:
        keyword_sources: list[dict[str, Any]] = []
        for keyword in extract_keywords(question):
            keyword_query_kwargs = {
                **query_kwargs,
                "where_document": {"$contains": keyword},
            }
            try:
                keyword_sources.extend(build_sources(collection.query(**keyword_query_kwargs), expected_terms))
            except Exception:
                continue
        sources = merge_sources(keyword_sources, sources)[:top_k]

    domain_hit = any(source["domain_code"] == expected_domain for source in sources)
    term_hit = any(source["term_hits"] for source in sources)
    case_law_hit = any(source["source_type"] in {"case_law", "labeled_judgment", "admin_decision"} for source in sources)

    return {
        "id": item.get("id"),
        "question": question,
        "expected_domain": expected_domain,
        "expected_terms": expected_terms,
        "domain_hit": domain_hit,
        "term_hit": term_hit,
        "case_law_hit": case_law_hit,
        "term_hit_count": sum(len(source["term_hits"]) for source in sources),
        "sources": sources,
    }


def rate(items: list[dict[str, Any]], key: str) -> float:
    return sum(1 for item in items if item[key]) / len(items) if items else 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate precedent Chroma retrieval quality.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--persist-dir", type=Path, default=Path(os.getenv("CHROMA_PERSIST_DIRECTORY", str(DEFAULT_PERSIST_DIR))))
    parser.add_argument("--collection-name", default=os.getenv("PRECEDENT_CHROMA_COLLECTION_NAME", DEFAULT_COLLECTION_NAME))
    parser.add_argument("--embedding-model", default=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("data/processed/precedents/precedent_retrieval_eval.json"))
    parser.add_argument("--use-expected-domain-filter", action="store_true")
    parser.add_argument("--use-keyword-boost", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env before running retrieval evaluation.")

    client = chromadb.PersistentClient(path=str(args.persist_dir))
    collection = client.get_collection(args.collection_name)
    embeddings = OpenAIEmbeddings(model=args.embedding_model, api_key=api_key)

    results = [
        evaluate_question(
            collection=collection,
            embeddings=embeddings,
            item=item,
            top_k=args.top_k,
            use_expected_domain_filter=args.use_expected_domain_filter,
            use_keyword_boost=args.use_keyword_boost,
        )
        for item in read_jsonl(args.questions)
    ]

    per_domain: dict[str, dict[str, int | float]] = {}
    for item in results:
        domain = str(item["expected_domain"])
        metrics = per_domain.setdefault(domain, {"questions": 0, "domain_hits": 0, "term_hits": 0, "case_law_hits": 0})
        metrics["questions"] = int(metrics["questions"]) + 1
        metrics["domain_hits"] = int(metrics["domain_hits"]) + int(bool(item["domain_hit"]))
        metrics["term_hits"] = int(metrics["term_hits"]) + int(bool(item["term_hit"]))
        metrics["case_law_hits"] = int(metrics["case_law_hits"]) + int(bool(item["case_law_hit"]))

    for metrics in per_domain.values():
        questions = int(metrics["questions"])
        metrics["domain_hit_rate"] = int(metrics["domain_hits"]) / questions if questions else 0
        metrics["term_hit_rate"] = int(metrics["term_hits"]) / questions if questions else 0
        metrics["case_law_hit_rate"] = int(metrics["case_law_hits"]) / questions if questions else 0

    summary = {
        "questions": len(results),
        "collection_name": args.collection_name,
        "top_k": args.top_k,
        "use_expected_domain_filter": args.use_expected_domain_filter,
        "use_keyword_boost": args.use_keyword_boost,
        "domain_hit_rate": rate(results, "domain_hit"),
        "term_hit_rate": rate(results, "term_hit"),
        "case_law_hit_rate": rate(results, "case_law_hit"),
        "per_domain": per_domain,
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
