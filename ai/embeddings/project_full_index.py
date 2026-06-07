from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_RAW_DIR = Path("data/raw/aihub_legal")
DEFAULT_DOCUMENT_SUMMARY = Path("data/processed/legal_documents.medium.summary.json")
DEFAULT_CHUNK_SUMMARY = Path("data/chunks/legal_chunks.medium.summary.json")
DEFAULT_INDEX_ESTIMATE = Path("data/processed/index_estimate.medium_enriched.json")
DEFAULT_OUTPUT_PATH = Path("data/processed/index_projection.full.json")
DEFAULT_PRICE_PER_1M_TOKENS = 0.02
DEFAULT_TPM_LIMIT = 1_000_000


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return data


def count_raw_json_files(raw_dir: Path) -> dict[str, int]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw directory does not exist: {raw_dir}")

    counts: dict[str, int] = {}
    for domain_dir in sorted(path for path in raw_dir.iterdir() if path.is_dir()):
        counts[domain_dir.name] = sum(1 for _ in domain_dir.rglob("*.json"))
    return counts


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0
    return numerator / denominator


def project_full_index(
    raw_counts: dict[str, int],
    document_summary: dict[str, Any],
    chunk_summary: dict[str, Any],
    index_estimate: dict[str, Any],
    price_per_1m_tokens: float,
    tpm_limit: int,
) -> dict[str, Any]:
    sample_documents_by_domain = {
        str(domain): int(count)
        for domain, count in document_summary.get("domains", {}).items()
    }
    sample_chunks_by_domain = {
        str(domain): int(count)
        for domain, count in chunk_summary.get("domains", {}).items()
    }

    avg_tokens_per_chunk = float(index_estimate.get("projection", {}).get("avg_tokens_per_chunk") or 0)
    projected_domains: dict[str, dict[str, float | int]] = {}

    total_projected_documents = 0
    total_projected_chunks = 0.0
    for domain, raw_documents in raw_counts.items():
        sample_documents = sample_documents_by_domain.get(domain, 0)
        sample_chunks = sample_chunks_by_domain.get(domain, 0)
        chunks_per_document = safe_ratio(sample_chunks, sample_documents)
        projected_chunks = raw_documents * chunks_per_document

        projected_domains[domain] = {
            "raw_documents": raw_documents,
            "sample_documents": sample_documents,
            "sample_chunks": sample_chunks,
            "chunks_per_document": chunks_per_document,
            "projected_chunks": round(projected_chunks),
        }
        total_projected_documents += raw_documents
        total_projected_chunks += projected_chunks

    projected_tokens = round(total_projected_chunks * avg_tokens_per_chunk)
    estimated_cost_usd = projected_tokens / 1_000_000 * price_per_1m_tokens
    minimum_minutes_at_tpm = projected_tokens / tpm_limit if tpm_limit > 0 else None

    return {
        "inputs": {
            "raw_counts": raw_counts,
            "sample_document_summary": document_summary.get("output_path"),
            "sample_chunk_summary": chunk_summary.get("output_path"),
            "avg_tokens_per_chunk_source": index_estimate.get("input_paths"),
        },
        "assumptions": {
            "projection_method": "raw documents by domain * medium sample chunks_per_document by domain",
            "avg_tokens_per_chunk": avg_tokens_per_chunk,
            "price_per_1m_tokens_usd": price_per_1m_tokens,
            "tpm_limit": tpm_limit,
        },
        "domains": projected_domains,
        "projection": {
            "documents": total_projected_documents,
            "chunks": round(total_projected_chunks),
            "tokens": projected_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "minimum_minutes_at_tpm": minimum_minutes_at_tpm,
            "minimum_hours_at_tpm": minimum_minutes_at_tpm / 60 if minimum_minutes_at_tpm is not None else None,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project full index size from raw counts and medium sample statistics.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--document-summary", type=Path, default=DEFAULT_DOCUMENT_SUMMARY)
    parser.add_argument("--chunk-summary", type=Path, default=DEFAULT_CHUNK_SUMMARY)
    parser.add_argument("--index-estimate", type=Path, default=DEFAULT_INDEX_ESTIMATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--price-per-1m-tokens", type=float, default=DEFAULT_PRICE_PER_1M_TOKENS)
    parser.add_argument("--tpm-limit", type=int, default=DEFAULT_TPM_LIMIT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    projection = project_full_index(
        raw_counts=count_raw_json_files(args.raw_dir),
        document_summary=read_json(args.document_summary),
        chunk_summary=read_json(args.chunk_summary),
        index_estimate=read_json(args.index_estimate),
        price_per_1m_tokens=args.price_per_1m_tokens,
        tpm_limit=args.tpm_limit,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(projection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in projection.items() if key != "domains"}, ensure_ascii=False, indent=2))
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
