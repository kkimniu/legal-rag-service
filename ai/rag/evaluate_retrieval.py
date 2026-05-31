from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

import chromadb
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings


DEFAULT_QUESTIONS_PATH = Path("ai/rag/evaluation_questions.jsonl")
DEFAULT_PERSIST_DIR = Path("chroma_db")
DEFAULT_COLLECTION_NAME = "legal_chunks_medium"
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


def get_env_value(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def normalize_terms(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def evaluate_question(
    collection: Any,
    embeddings: OpenAIEmbeddings,
    item: dict[str, Any],
    top_k: int,
    use_expected_domain_filter: bool,
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

    result = collection.query(**query_kwargs)

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    ids = result.get("ids", [[]])[0]

    sources = []
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
        safe_metadata = metadata if isinstance(metadata, dict) else {}
        text = str(document or "")
        sources.append(
            {
                "id": str(chunk_id),
                "domain_code": str(safe_metadata.get("domain_code") or ""),
                "domain_name": str(safe_metadata.get("domain_name") or ""),
                "source_type": str(safe_metadata.get("source_type") or ""),
                "title": str(safe_metadata.get("title") or ""),
                "score": float(distance) if distance is not None else None,
                "term_hits": [term for term in expected_terms if term in text],
            }
        )

    domain_hit = any(source["domain_code"] == expected_domain for source in sources)
    term_hit = any(source["term_hits"] for source in sources)

    return {
        "id": item.get("id"),
        "question": question,
        "expected_domain": expected_domain,
        "domain_filter": expected_domain if use_expected_domain_filter else None,
        "domain_hit": domain_hit,
        "term_hit": term_hit,
        "sources": sources,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Chroma retrieval quality with a small legal question set.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--persist-dir", type=Path, default=Path(get_env_value("CHROMA_PERSIST_DIRECTORY", str(DEFAULT_PERSIST_DIR))))
    parser.add_argument("--collection-name", default=get_env_value("CHROMA_COLLECTION_NAME", DEFAULT_COLLECTION_NAME))
    parser.add_argument("--embedding-model", default=get_env_value("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("data/processed/retrieval_eval.medium.json"))
    parser.add_argument("--use-expected-domain-filter", action="store_true")
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
        )
        for item in read_jsonl(args.questions)
    ]

    total = len(results)
    domain_hits = sum(1 for item in results if item["domain_hit"])
    term_hits = sum(1 for item in results if item["term_hit"])
    summary = {
        "questions": total,
        "collection_name": args.collection_name,
        "top_k": args.top_k,
        "use_expected_domain_filter": args.use_expected_domain_filter,
        "domain_hit_rate": domain_hits / total if total else 0,
        "term_hit_rate": term_hits / total if total else 0,
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
