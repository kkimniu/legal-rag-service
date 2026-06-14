from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter


DEFAULT_INPUT_PATH = Path("data/processed/legal_documents.jsonl")
DEFAULT_OUTPUT_PATH = Path("data/chunks/legal_chunks.jsonl")


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


def create_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "? ",
            "! ",
            "다. ",
            "요. ",
            " ",
            "",
        ],
    )


def chunk_document(
    document: dict[str, Any],
    splitter: RecursiveCharacterTextSplitter,
) -> list[dict[str, Any]]:
    content = str(document.get("content") or "").strip()
    if not content:
        return []

    chunks = splitter.split_text(content)
    document_id = str(document.get("id") or "")
    metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}

    output = []
    for index, chunk_text in enumerate(chunks):
        chunk_id = f"{document_id}:chunk:{index:04d}"
        output.append(
            {
                "id": chunk_id,
                "document_id": document_id,
                "chunk_index": index,
                "text": chunk_text,
                "domain_code": document.get("domain_code"),
                "domain_name": document.get("domain_name"),
                "source_type": document.get("source_type"),
                "split": document.get("split"),
                "title": document.get("title"),
                "metadata": {
                    **metadata,
                    "chunk_size": len(chunk_text),
                },
            }
        )
    return output


def temp_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.name}.tmp")


def write_chunks(
    input_path: Path,
    output_path: Path,
    chunk_size: int,
    chunk_overlap: int,
    start_offset: int,
    max_documents: int | None,
    progress_interval: int,
) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input document JSONL does not exist: {input_path}")
    if start_offset < 0:
        raise ValueError("start_offset must be 0 or greater.")
    if progress_interval < 0:
        raise ValueError("progress_interval must be 0 or greater.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_path = temp_output_path(output_path)
    splitter = create_splitter(chunk_size, chunk_overlap)

    stats: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()

    with write_path.open("w", encoding="utf-8", newline="\n") as file:
        for document in read_jsonl(input_path):
            if stats["documents_seen"] < start_offset:
                stats["documents_seen"] += 1
                stats["skipped_by_offset"] += 1
                continue

            documents_after_offset = stats["documents_seen"] - stats["skipped_by_offset"]
            if max_documents and documents_after_offset >= max_documents:
                break

            stats["documents_seen"] += 1
            chunks = chunk_document(document, splitter)
            if not chunks:
                stats["documents_without_content"] += 1
                continue

            stats["documents_chunked"] += 1
            stats["chunks_written"] += len(chunks)
            domain_counts[str(document.get("domain_code") or "unknown")] += len(chunks)
            source_type_counts[str(document.get("source_type") or "unknown")] += len(chunks)

            for chunk in chunks:
                file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

            documents_after_offset = stats["documents_seen"] - stats["skipped_by_offset"]
            if progress_interval and documents_after_offset % progress_interval == 0:
                print(
                    "progress: "
                    f"documents_seen={stats['documents_seen']} "
                    f"documents_chunked={stats['documents_chunked']} "
                    f"chunks_written={stats['chunks_written']} "
                    f"domains={dict(sorted(domain_counts.items()))}",
                    flush=True,
                )

    write_path.replace(output_path)

    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "start_offset": start_offset,
        "max_documents": max_documents,
        "stats": dict(stats),
        "domains": dict(sorted(domain_counts.items())),
        "source_types": dict(sorted(source_type_counts.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk normalized legal documents for RAG retrieval.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--progress-interval", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = write_chunks(
        input_path=args.input,
        output_path=args.output,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        start_offset=args.start_offset,
        max_documents=args.max_documents,
        progress_interval=args.progress_interval,
    )
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"input: {args.input}")
    print(f"output: {args.output}")
    print(f"summary: {summary_path}")
    print(f"stats: {summary['stats']}")
    print(f"domains: {summary['domains']}")
    print(f"source_types: {summary['source_types']}")


if __name__ == "__main__":
    main()
