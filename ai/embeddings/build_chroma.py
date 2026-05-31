from __future__ import annotations

import argparse
import json
import os
import time
from itertools import islice
from pathlib import Path
from typing import Any, Iterable

import chromadb
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings


DEFAULT_INPUT_PATH = Path("data/chunks/legal_chunks.jsonl")
DEFAULT_PERSIST_DIR = Path("chroma_db")
DEFAULT_COLLECTION_NAME = "legal_chunks"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

METADATA_VALUE = str | int | float | bool


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


def batched(items: Iterable[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    iterator = iter(items)
    while batch := list(islice(iterator, batch_size)):
        yield batch


def limited_chunks(
    chunks: Iterable[dict[str, Any]],
    max_chunks: int | None,
    max_per_domain: int | None,
    stats: dict[str, Any],
) -> Iterable[dict[str, Any]]:
    domain_counts: dict[str, int] = {}
    yielded = 0

    for chunk in chunks:
        domain_code = str(chunk.get("domain_code") or "unknown")
        if max_per_domain and domain_counts.get(domain_code, 0) >= max_per_domain:
            stats["skipped_by_domain_limit"] = stats.get("skipped_by_domain_limit", 0) + 1
            continue

        yield chunk
        yielded += 1
        domain_counts[domain_code] = domain_counts.get(domain_code, 0) + 1

        if max_chunks and yielded >= max_chunks:
            break


def metadata_value(value: Any) -> METADATA_VALUE:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)


def flatten_metadata(chunk: dict[str, Any]) -> dict[str, METADATA_VALUE]:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}

    flattened: dict[str, METADATA_VALUE] = {
        "document_id": metadata_value(chunk.get("document_id")),
        "chunk_index": metadata_value(chunk.get("chunk_index")),
        "domain_code": metadata_value(chunk.get("domain_code")),
        "domain_name": metadata_value(chunk.get("domain_name")),
        "source_type": metadata_value(chunk.get("source_type")),
        "split": metadata_value(chunk.get("split")),
        "title": metadata_value(chunk.get("title")),
    }

    for key, value in metadata.items():
        flattened[f"meta_{key}"] = metadata_value(value)

    return flattened


def validate_chunk(chunk: dict[str, Any]) -> tuple[str, str, dict[str, METADATA_VALUE]]:
    chunk_id = str(chunk.get("id") or "").strip()
    text = str(chunk.get("text") or "").strip()

    if not chunk_id:
        raise ValueError("Chunk is missing id")
    if not text:
        raise ValueError(f"Chunk is missing text: {chunk_id}")

    return chunk_id, text, flatten_metadata(chunk)


def get_embedding_model(model: str) -> OpenAIEmbeddings:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env before building embeddings.")
    return OpenAIEmbeddings(model=model, api_key=api_key)


def embed_documents_with_retry(
    embeddings: OpenAIEmbeddings,
    texts: list[str],
    max_retries: int,
    retry_base_seconds: float,
) -> list[list[float]]:
    """Retry transient OpenAI embedding failures such as rate limits."""
    attempt = 0
    while True:
        try:
            return embeddings.embed_documents(texts)
        except Exception as exc:
            message = repr(exc).lower()
            is_retryable = any(token in message for token in ("ratelimit", "rate_limit", "timeout", "temporarily"))
            if not is_retryable or attempt >= max_retries:
                raise

            sleep_seconds = retry_base_seconds * (2**attempt)
            print(f"retryable embedding error; retrying in {sleep_seconds:.1f}s ({attempt + 1}/{max_retries})")
            time.sleep(sleep_seconds)
            attempt += 1


def filter_existing_chunks(
    collection: Any,
    ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, METADATA_VALUE]],
) -> tuple[list[str], list[str], list[dict[str, METADATA_VALUE]], int]:
    """Remove ids that are already present in Chroma when resuming a failed build."""
    existing = collection.get(ids=ids, include=[])
    existing_ids = set(existing.get("ids") or [])
    if not existing_ids:
        return ids, texts, metadatas, 0

    filtered_ids: list[str] = []
    filtered_texts: list[str] = []
    filtered_metadatas: list[dict[str, METADATA_VALUE]] = []

    for chunk_id, text, metadata in zip(ids, texts, metadatas, strict=True):
        if chunk_id in existing_ids:
            continue
        filtered_ids.append(chunk_id)
        filtered_texts.append(text)
        filtered_metadatas.append(metadata)

    return filtered_ids, filtered_texts, filtered_metadatas, len(existing_ids)


def build_chroma(
    input_path: Path,
    persist_dir: Path,
    collection_name: str,
    embedding_model_name: str,
    batch_size: int,
    max_chunks: int | None,
    max_per_domain: int | None,
    reset_collection: bool,
    dry_run: bool,
    max_retries: int,
    retry_base_seconds: float,
    skip_existing: bool,
) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Chunk JSONL does not exist: {input_path}")

    stats = {
        "chunks_seen": 0,
        "chunks_valid": 0,
        "batches": 0,
        "domains": {},
        "collection_name": collection_name,
        "embedding_model": embedding_model_name,
        "persist_dir": str(persist_dir),
        "dry_run": dry_run,
    }
    chunks = limited_chunks(read_jsonl(input_path), max_chunks, max_per_domain, stats)

    client = None
    collection = None
    embeddings = None

    if not dry_run:
        persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_dir))
        if reset_collection:
            try:
                client.delete_collection(collection_name)
            except Exception:
                pass
        collection = client.get_or_create_collection(name=collection_name)
        embeddings = get_embedding_model(embedding_model_name)

    for batch in batched(chunks, batch_size):
        ids: list[str] = []
        texts: list[str] = []
        metadatas: list[dict[str, METADATA_VALUE]] = []

        for chunk in batch:
            stats["chunks_seen"] += 1
            chunk_id, text, metadata = validate_chunk(chunk)
            domain_code = str(chunk.get("domain_code") or "unknown")
            stats["domains"][domain_code] = stats["domains"].get(domain_code, 0) + 1
            ids.append(chunk_id)
            texts.append(text)
            metadatas.append(metadata)
            stats["chunks_valid"] += 1

        stats["batches"] += 1

        if dry_run:
            continue

        if collection is None or embeddings is None:
            raise RuntimeError("Chroma collection or embedding model was not initialized.")

        if skip_existing:
            ids, texts, metadatas, skipped_existing = filter_existing_chunks(collection, ids, texts, metadatas)
            stats["skipped_existing"] = stats.get("skipped_existing", 0) + skipped_existing
            if not ids:
                continue

        vectors = embed_documents_with_retry(
            embeddings=embeddings,
            texts=texts,
            max_retries=max_retries,
            retry_base_seconds=retry_base_seconds,
        )
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=vectors)

    if not dry_run and collection is not None:
        stats["collection_count"] = collection.count()

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed legal chunks and store them in ChromaDB.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--persist-dir", type=Path, default=DEFAULT_PERSIST_DIR)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--embedding-model", default=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-chunks", type=int, default=None)
    parser.add_argument("--max-per-domain", type=int, default=None)
    parser.add_argument("--reset-collection", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-base-seconds", type=float, default=2.0)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_chroma(
        input_path=args.input,
        persist_dir=args.persist_dir,
        collection_name=args.collection_name,
        embedding_model_name=args.embedding_model,
        batch_size=args.batch_size,
        max_chunks=args.max_chunks,
        max_per_domain=args.max_per_domain,
        reset_collection=args.reset_collection,
        dry_run=args.dry_run,
        max_retries=args.max_retries,
        retry_base_seconds=args.retry_base_seconds,
        skip_existing=args.skip_existing,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
