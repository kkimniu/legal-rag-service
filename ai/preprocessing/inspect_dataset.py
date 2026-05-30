from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_RAW_DIR = Path("data/raw/aihub_legal")
DEFAULT_OUTPUT_PATH = Path("data/processed/dataset_profile.json")
ENCODINGS = ("utf-8-sig", "utf-8", "cp949")


def read_text_with_fallback(path: Path) -> tuple[str, str]:
    """Read Korean AI Hub files whether they are UTF-8 or CP949 encoded."""
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Could not decode {path} with {ENCODINGS}: {last_error}",
    )


def summarize_json(path: Path) -> dict[str, Any]:
    text, encoding = read_text_with_fallback(path)
    data = json.loads(text)

    summary: dict[str, Any] = {
        "path": str(path),
        "encoding": encoding,
        "root_type": type(data).__name__,
    }

    if isinstance(data, dict):
        summary["keys"] = list(data.keys())
        summary["nested_keys"] = {
            key: list(value.keys())
            for key, value in data.items()
            if isinstance(value, dict)
        }
    elif isinstance(data, list):
        summary["length"] = len(data)
        if data and isinstance(data[0], dict):
            summary["first_item_keys"] = list(data[0].keys())

    return summary


def summarize_csv(path: Path) -> dict[str, Any]:
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                reader = csv.reader(file)
                header = next(reader)
                first_row = next(reader, [])
            return {
                "path": str(path),
                "encoding": encoding,
                "header": header,
                "first_row_columns": len(first_row),
            }
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Could not decode {path} with {ENCODINGS}: {last_error}",
    )


def empty_domain_summary() -> dict[str, Any]:
    return {
        "total_files": 0,
        "extensions": Counter(),
        "json_samples": [],
        "csv_samples": [],
        "zip_samples": [],
    }


def inspect_dataset(raw_dir: Path, max_samples: int) -> dict[str, Any]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory does not exist: {raw_dir}")

    domains: dict[str, dict[str, Any]] = defaultdict(empty_domain_summary)

    for path in raw_dir.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(raw_dir)
        domain = relative.parts[0] if relative.parts else "_root"
        domain_summary = domains[domain]
        extension = path.suffix.lower() or "(none)"

        domain_summary["total_files"] += 1
        domain_summary["extensions"][extension] += 1

        if extension == ".json" and len(domain_summary["json_samples"]) < max_samples:
            try:
                domain_summary["json_samples"].append(summarize_json(path))
            except Exception as exc:  # Keep profiling resilient on malformed files.
                domain_summary["json_samples"].append({"path": str(path), "error": repr(exc)})

        if extension == ".csv" and len(domain_summary["csv_samples"]) < max_samples:
            try:
                domain_summary["csv_samples"].append(summarize_csv(path))
            except Exception as exc:
                domain_summary["csv_samples"].append({"path": str(path), "error": repr(exc)})

        if extension == ".zip" and len(domain_summary["zip_samples"]) < max_samples:
            domain_summary["zip_samples"].append(str(path))

    normalized_domains = {}
    total_files = 0
    total_extensions: Counter[str] = Counter()

    for domain, summary in sorted(domains.items()):
        total_files += summary["total_files"]
        total_extensions.update(summary["extensions"])
        normalized_domains[domain] = {
            **summary,
            "extensions": dict(sorted(summary["extensions"].items())),
        }

    return {
        "raw_dir": str(raw_dir),
        "total_files": total_files,
        "extensions": dict(sorted(total_extensions.items())),
        "domains": normalized_domains,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect AI Hub legal raw dataset structure.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--max-samples", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = inspect_dataset(args.raw_dir, args.max_samples)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"raw_dir: {profile['raw_dir']}")
    print(f"total_files: {profile['total_files']}")
    print(f"extensions: {profile['extensions']}")
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
