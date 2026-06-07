from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import tiktoken


DEFAULT_INPUT_PATH = Path("data/chunks/legal_chunks.jsonl")
DEFAULT_OUTPUT_PATH = Path("data/processed/index_estimate.json")
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_PRICE_PER_1M_TOKENS = 0.02
DEFAULT_TPM_LIMIT = 1_000_000


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


def get_encoding(model: str) -> tiktoken.Encoding:
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def percentile(values: list[int], percent: float) -> int:
    if not values:
        return 0
    sorted_values = sorted(values)
    index = round((len(sorted_values) - 1) * percent)
    return sorted_values[index]


def estimate_inputs(
    input_paths: list[Path],
    embedding_model: str,
    max_chunks: int | None,
    dedupe_ids: bool,
) -> dict[str, Any]:
    encoding = get_encoding(embedding_model)

    stats: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    source_types: Counter[str] = Counter()
    token_counts: list[int] = []
    seen_ids: set[str] = set()

    for input_path in input_paths:
        if not input_path.exists():
            raise FileNotFoundError(f"Chunk JSONL does not exist: {input_path}")

        for chunk in read_jsonl(input_path):
            stats["chunks_seen"] += 1
            chunk_id = str(chunk.get("id") or "")
            if dedupe_ids and chunk_id:
                if chunk_id in seen_ids:
                    stats["duplicate_ids_skipped"] += 1
                    continue
                seen_ids.add(chunk_id)

            text = str(chunk.get("text") or "").strip()
            if not text:
                stats["chunks_without_text"] += 1
                continue

            tokens = len(encoding.encode(text))
            token_counts.append(tokens)
            stats["chunks_counted"] += 1
            stats["tokens"] += tokens
            domains[str(chunk.get("domain_code") or "unknown")] += 1
            source_types[str(chunk.get("source_type") or "unknown")] += 1

            if max_chunks and stats["chunks_counted"] >= max_chunks:
                break

        if max_chunks and stats["chunks_counted"] >= max_chunks:
            break

    return {
        "input_paths": [str(path) for path in input_paths],
        "embedding_model": embedding_model,
        "stats": dict(stats),
        "domains": dict(sorted(domains.items())),
        "source_types": dict(sorted(source_types.items())),
        "token_distribution": {
            "min": min(token_counts) if token_counts else 0,
            "avg": mean(token_counts) if token_counts else 0,
            "p50": percentile(token_counts, 0.50),
            "p90": percentile(token_counts, 0.90),
            "p95": percentile(token_counts, 0.95),
            "max": max(token_counts) if token_counts else 0,
        },
    }


def add_cost_projection(
    estimate: dict[str, Any],
    price_per_1m_tokens: float,
    tpm_limit: int,
    scale_to_chunks: int | None,
) -> dict[str, Any]:
    stats = estimate["stats"]
    chunks_counted = int(stats.get("chunks_counted", 0))
    tokens = int(stats.get("tokens", 0))

    avg_tokens_per_chunk = tokens / chunks_counted if chunks_counted else 0
    projected_chunks = scale_to_chunks or chunks_counted
    projected_tokens = round(avg_tokens_per_chunk * projected_chunks)
    estimated_cost_usd = projected_tokens / 1_000_000 * price_per_1m_tokens
    minimum_minutes_at_tpm = projected_tokens / tpm_limit if tpm_limit > 0 else None

    estimate["projection"] = {
        "price_per_1m_tokens_usd": price_per_1m_tokens,
        "chunks": projected_chunks,
        "avg_tokens_per_chunk": avg_tokens_per_chunk,
        "tokens": projected_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "tpm_limit": tpm_limit,
        "minimum_minutes_at_tpm": minimum_minutes_at_tpm,
        "scale_to_chunks": scale_to_chunks,
    }
    return estimate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate embedding index size, tokens, API cost, and minimum runtime.")
    parser.add_argument("--input", type=Path, nargs="+", default=[DEFAULT_INPUT_PATH])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--price-per-1m-tokens", type=float, default=DEFAULT_PRICE_PER_1M_TOKENS)
    parser.add_argument("--tpm-limit", type=int, default=DEFAULT_TPM_LIMIT)
    parser.add_argument("--max-chunks", type=int, default=None)
    parser.add_argument("--scale-to-chunks", type=int, default=None)
    parser.add_argument("--no-dedupe-ids", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    estimate = estimate_inputs(
        input_paths=args.input,
        embedding_model=args.embedding_model,
        max_chunks=args.max_chunks,
        dedupe_ids=not args.no_dedupe_ids,
    )
    estimate = add_cost_projection(
        estimate=estimate,
        price_per_1m_tokens=args.price_per_1m_tokens,
        tpm_limit=args.tpm_limit,
        scale_to_chunks=args.scale_to_chunks,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(estimate, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({key: value for key, value in estimate.items() if key != "domains" and key != "source_types"}, ensure_ascii=False, indent=2))
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
