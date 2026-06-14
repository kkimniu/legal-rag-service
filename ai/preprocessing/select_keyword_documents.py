from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from normalize_documents import DEFAULT_RAW_DIR, DOMAIN_LABELS, ENCODINGS, get_domain, normalize_document


DEFAULT_OUTPUT_PATH = Path("data/processed/legal_documents.keyword.jsonl")


def iter_domain_json_files(raw_dir: Path, domain_code: str) -> Iterable[Path]:
    domain_dir = raw_dir / domain_code
    if not domain_dir.exists():
        raise FileNotFoundError(f"Domain directory does not exist: {domain_dir}")
    yield from domain_dir.rglob("*.json")


def file_contains_any_keyword(path: Path, keywords: list[str]) -> bool:
    for encoding in ENCODINGS:
        try:
            text = path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        return any(keyword in text for keyword in keywords)
    return False


def find_matched_keywords(document: dict[str, Any], keywords: list[str]) -> list[str]:
    haystack = "\n".join(
        [
            str(document.get("title") or ""),
            str(document.get("question") or ""),
            str(document.get("answer") or ""),
            str(document.get("context") or ""),
            str(document.get("content") or ""),
        ]
    )
    return [keyword for keyword in keywords if keyword in haystack]


def write_keyword_documents(
    raw_dir: Path,
    output_path: Path,
    domain_code: str,
    keywords: list[str],
    max_per_keyword: int,
    max_documents: int | None,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output_path = output_path.with_suffix(output_path.suffix + ".tmp")

    stats: Counter[str] = Counter()
    keyword_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    seen_document_ids: set[str] = set()

    with temp_output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for path in iter_domain_json_files(raw_dir, domain_code):
            stats["json_files_seen"] += 1
            if not file_contains_any_keyword(path, keywords):
                continue

            stats["keyword_files_seen"] += 1
            try:
                document = normalize_document(path, raw_dir)
            except Exception:
                stats["errors"] += 1
                continue

            if document is None:
                stats["skipped"] += 1
                continue

            current_domain_code, _ = get_domain(path, raw_dir)
            if current_domain_code != domain_code:
                continue

            matched_keywords = find_matched_keywords(document, keywords)
            if not matched_keywords:
                continue

            available_keywords = [
                keyword
                for keyword in matched_keywords
                if keyword_counts[keyword] < max_per_keyword
            ]
            if not available_keywords:
                stats["skipped_by_keyword_limit"] += 1
                if all(keyword_counts[keyword] >= max_per_keyword for keyword in keywords):
                    break
                continue

            document_id = str(document["id"])
            if document_id in seen_document_ids:
                continue

            document["metadata"]["matched_keywords"] = ",".join(available_keywords)
            output_file.write(json.dumps(document, ensure_ascii=False) + "\n")
            seen_document_ids.add(document_id)

            stats["documents_written"] += 1
            source_type_counts[str(document.get("source_type") or "unknown")] += 1
            for keyword in available_keywords:
                keyword_counts[keyword] += 1

            if max_documents and stats["documents_written"] >= max_documents:
                break
            if all(keyword_counts[keyword] >= max_per_keyword for keyword in keywords):
                break

    temp_output_path.replace(output_path)

    return {
        "raw_dir": str(raw_dir),
        "output_path": str(output_path),
        "domain_code": domain_code,
        "domain_name": DOMAIN_LABELS.get(domain_code, domain_code),
        "keywords": keywords,
        "max_per_keyword": max_per_keyword,
        "stats": dict(stats),
        "keyword_counts": dict(sorted(keyword_counts.items())),
        "source_types": dict(sorted(source_type_counts.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select normalized legal documents that contain target keywords.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--domain-code", default="03_administrative_law")
    parser.add_argument("--keywords", nargs="+", required=True)
    parser.add_argument("--max-per-keyword", type=int, default=50)
    parser.add_argument("--max-documents", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = write_keyword_documents(
        raw_dir=args.raw_dir,
        output_path=args.output,
        domain_code=args.domain_code,
        keywords=args.keywords,
        max_per_keyword=args.max_per_keyword,
        max_documents=args.max_documents,
    )
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"output: {args.output}")
    print(f"summary: {summary_path}")
    print(f"stats: {summary['stats']}")
    print(f"keyword_counts: {summary['keyword_counts']}")
    print(f"source_types: {summary['source_types']}")


if __name__ == "__main__":
    main()
