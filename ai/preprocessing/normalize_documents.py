from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RAW_DIR = Path("data/raw/aihub_legal")
DEFAULT_OUTPUT_PATH = Path("data/processed/legal_documents.jsonl")
ENCODINGS = ("utf-8-sig", "utf-8", "cp949")

DOMAIN_LABELS = {
    "01_civil_law": "민사법",
    "02_intellectual_property_law": "지식재산권법",
    "03_administrative_law": "행정법",
    "04_criminal_law": "형사법",
}


def read_json_with_fallback(path: Path) -> dict[str, Any] | list[Any]:
    """Load AI Hub JSON files while tolerating common Korean encodings."""
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Could not decode {path} with {ENCODINGS}: {last_error}",
    )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(normalize_text(item) for item in value if normalize_text(item))
    return " ".join(str(value).replace("\r", "\n").split())


def detect_split(path: Path) -> str:
    parts = set(path.parts)
    if "Training" in parts:
        return "train"
    if "Validation" in parts:
        return "validation"
    return "unknown"


def detect_source_type(path: Path) -> str:
    text = str(path)
    if "질의응답" in text or "_QA" in text:
        return "qa"
    if "요약" in text:
        return "summary"
    if "판결문" in text:
        return "judgment"
    if "결정례" in text:
        return "decision"
    return "unknown"


def get_domain(path: Path, raw_dir: Path) -> tuple[str, str]:
    relative = path.relative_to(raw_dir)
    domain_code = relative.parts[0] if relative.parts else "unknown"
    return domain_code, DOMAIN_LABELS.get(domain_code, domain_code)


def build_content(question: str, answer: str, context: str) -> str:
    parts = []
    if question:
        parts.append(f"질문: {question}")
    if answer:
        parts.append(f"답변: {answer}")
    if context:
        parts.append(f"근거 본문: {context}")
    return "\n\n".join(parts)


def normalize_document(path: Path, raw_dir: Path) -> dict[str, Any] | None:
    data = read_json_with_fallback(path)
    if not isinstance(data, dict):
        return None

    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    payload = None
    if isinstance(data.get("taskinfo"), dict):
        payload = data["taskinfo"]
    elif isinstance(data.get("label"), dict):
        payload = data["label"]

    if not isinstance(payload, dict):
        return None

    question = normalize_text(payload.get("input"))
    answer = normalize_text(payload.get("output"))
    instruction = normalize_text(payload.get("instruction"))
    context = normalize_text(payload.get("sentences"))

    content = build_content(question, answer, context)
    if not content:
        return None

    domain_code, domain_name = get_domain(path, raw_dir)
    doc_id = (
        info.get("doc_id")
        or info.get("determintId")
        or info.get("caseNum")
        or path.stem
    )

    title = (
        info.get("casenames")
        or info.get("caseName")
        or path.stem
    )

    return {
        "id": f"{domain_code}:{doc_id}:{path.stem}",
        "domain_code": domain_code,
        "domain_name": domain_name,
        "split": detect_split(path),
        "source_type": detect_source_type(path),
        "title": normalize_text(title),
        "content": content,
        "question": question,
        "answer": answer,
        "context": context,
        "metadata": {
            "source_path": str(path),
            "doc_id": normalize_text(doc_id),
            "case_number": normalize_text(info.get("caseNum")),
            "court": normalize_text(info.get("normalized_court") or info.get("courtCode")),
            "case_type": normalize_text(info.get("casetype") or info.get("caseCode")),
            "document_type": normalize_text(info.get("DocuType") or info.get("doc_class")),
            "announce_date": normalize_text(info.get("announce_date") or info.get("finalDate")),
            "task_type": normalize_text(info.get("taskType") or info.get("sentenceType")),
            "instruction": instruction,
        },
    }


def iter_json_files(raw_dir: Path) -> Iterable[Path]:
    # Keep this streaming-friendly. The raw dataset has hundreds of thousands of
    # files, so only sort the top-level domain folders and stream the files below.
    domain_dirs = [path for path in raw_dir.iterdir() if path.is_dir()]
    for domain_dir in sorted(domain_dirs, key=lambda path: path.name):
        yield from domain_dir.rglob("*.json")


def write_jsonl(
    raw_dir: Path,
    output_path: Path,
    max_documents: int | None,
    max_per_domain: int | None,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    domain_targets = {
        path.name
        for path in raw_dir.iterdir()
        if path.is_dir()
    }

    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for path in iter_json_files(raw_dir):
            stats["json_files_seen"] += 1
            domain_code, _ = get_domain(path, raw_dir)
            if max_per_domain and domain_counts[domain_code] >= max_per_domain:
                stats["skipped_by_domain_limit"] += 1
                continue

            try:
                document = normalize_document(path, raw_dir)
            except Exception:
                stats["errors"] += 1
                continue

            if document is None:
                stats["skipped"] += 1
                continue

            file.write(json.dumps(document, ensure_ascii=False) + "\n")
            stats["documents_written"] += 1
            domain_counts[document["domain_code"]] += 1
            source_type_counts[document["source_type"]] += 1

            if max_documents and stats["documents_written"] >= max_documents:
                break

            if max_per_domain and domain_targets:
                filled_domains = {
                    domain
                    for domain in domain_targets
                    if domain_counts[domain] >= max_per_domain
                }
                if filled_domains == domain_targets:
                    break

    return {
        "raw_dir": str(raw_dir),
        "output_path": str(output_path),
        "stats": dict(stats),
        "domains": dict(sorted(domain_counts.items())),
        "source_types": dict(sorted(source_type_counts.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize AI Hub legal JSON files to JSONL documents.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--max-per-domain", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = write_jsonl(args.raw_dir, args.output, args.max_documents, args.max_per_domain)
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"output: {args.output}")
    print(f"summary: {summary_path}")
    print(f"stats: {summary['stats']}")
    print(f"domains: {summary['domains']}")
    print(f"source_types: {summary['source_types']}")


if __name__ == "__main__":
    main()
