from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RAW_DIR = Path("data/raw/precedents/incoming")
DEFAULT_OUTPUT_PATH = Path("data/processed/precedents/precedent_documents.jsonl")
ENCODINGS = ("utf-8-sig", "utf-8", "cp949")
SOURCE_PRIORITY = ("Sublabel", "Training", "Validation", "Other")

DOMAIN_LABELS = {
    "01_civil_law": "민사법",
    "02_intellectual_property_law": "지식재산권법",
    "03_administrative_law": "행정법",
    "04_criminal_law": "형사법",
    "unknown": "미분류",
}

DOMAIN_KEYWORDS = {
    "02_intellectual_property_law": (
        "지식재산",
        "특허",
        "상표",
        "디자인",
        "저작",
        "실용신안",
        "권리범위",
        "무효심판",
        "특허법원",
        "등록상표",
    ),
    "03_administrative_law": (
        "행정",
        "재결",
        "심판",
        "처분",
        "세무",
        "조세",
        "과세",
        "납세",
        "시정명령",
        "공정거래",
        "공동행위",
        "구합",
    ),
    "04_criminal_law": (
        "형사",
        "사기",
        "횡령",
        "배임",
        "살인",
        "폭행",
        "상해",
        "절도",
        "강도",
        "고단",
        "고합",
        "초기",
    ),
    "01_civil_law": (
        "민사",
        "가사",
        "이혼",
        "상속",
        "혼인",
        "부양료",
        "위자료",
        "재산분할",
        "손해배상",
        "보증금",
        "매매",
        "임대차",
        "가압류",
        "가단",
        "가합",
        "므",
    ),
}

CASE_NUMBER_PATTERNS = (
    ("02_intellectual_property_law", re.compile(r"\d+(허|후)\d*")),
    ("03_administrative_law", re.compile(r"\d+(두|누|구합)\d*")),
    ("04_criminal_law", re.compile(r"\d+(고단|고합|도|노|모|초기)\d*")),
    ("01_civil_law", re.compile(r"\d+(가단|가합|나|다|므|느|드|르|스|즈|으|카)\d*")),
)


def read_json_with_fallback(path: Path) -> dict[str, Any] | list[Any]:
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
    if isinstance(value, dict):
        return "\n".join(f"{key}: {normalize_text(item)}" for key, item in value.items() if normalize_text(item))
    return " ".join(str(value).replace("\r", "\n").split())


def normalize_list_text(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    output = []
    for value in values:
        text = normalize_text(value)
        if text:
            output.append(text)
    return output


def detect_split(path: Path) -> str:
    parts = set(path.parts)
    if "Training" in parts:
        return "train"
    if "Validation" in parts:
        return "validation"
    return "raw"


def detect_domain(path: Path, *values: str) -> tuple[str, str]:
    haystack = " ".join([str(path), *values])
    for domain_code, pattern in CASE_NUMBER_PATTERNS:
        if pattern.search(haystack):
            return domain_code, DOMAIN_LABELS[domain_code]

    for domain_code, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return domain_code, DOMAIN_LABELS[domain_code]
    return "unknown", DOMAIN_LABELS["unknown"]


def stable_id(prefix: str, path: Path, *values: str) -> str:
    candidate = ":".join(value for value in values if value)
    if candidate:
        safe = "".join(ch if ch.isalnum() else "-" for ch in candidate).strip("-")
        if safe:
            return f"{prefix}:{safe[:120]}"
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{path.stem}:{digest}"


def join_sections(sections: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"{title}\n{body}" for title, body in sections if body)


def normalize_sublabel_case(data: dict[str, Any], path: Path) -> dict[str, Any] | None:
    title = normalize_text(data.get("사건명"))
    case_number = normalize_text(data.get("사건번호"))
    court = normalize_text(data.get("법원명"))
    decision_date = normalize_text(data.get("선고일자"))
    summary = normalize_text(data.get("판결요지"))
    issue = normalize_text(data.get("판시사항"))
    full_text = normalize_text(data.get("판례내용"))

    content = join_sections(
        [
            ("사건명", title),
            ("사건번호", case_number),
            ("법원", court),
            ("선고일자", decision_date),
            ("판시사항", issue),
            ("판결요지", summary),
            ("참조조문", normalize_text(data.get("참조조문"))),
            ("참조판례", normalize_text(data.get("참조판례"))),
            ("판례내용", full_text),
        ]
    )
    if not content:
        return None

    domain_code, domain_name = detect_domain(path, title, case_number, normalize_text(data.get("사건종류명")))
    return {
        "id": stable_id("precedent", path, case_number, str(data.get("판례일련번호") or "")),
        "domain_code": domain_code,
        "domain_name": domain_name,
        "split": detect_split(path),
        "source_type": "case_law",
        "title": title or case_number or path.stem,
        "case_number": case_number,
        "case_name": title,
        "court": court,
        "decision_date": decision_date,
        "summary": summary or issue,
        "content": content,
        "metadata": {
            "source_path": str(path),
            "source_dataset": "Sublabel",
            "precedent_serial": normalize_text(data.get("판례일련번호")),
            "case_type": normalize_text(data.get("사건종류명")),
            "decision_type": normalize_text(data.get("판결유형")),
            "detail_link": normalize_text(data.get("판례상세링크")),
            "reference_statutes": normalize_text(data.get("참조조문")),
            "reference_cases": normalize_text(data.get("참조판례")),
        },
    }


def normalize_sublabel_decision(data: dict[str, Any], path: Path) -> dict[str, Any] | None:
    title = normalize_text(data.get("사건명"))
    case_number = normalize_text(data.get("사건번호"))
    agency = normalize_text(data.get("재결청") or data.get("처분청"))
    decision_date = normalize_text(data.get("의결일자") or data.get("재결일자"))
    summary = normalize_text(data.get("재결요지"))

    content = join_sections(
        [
            ("사건명", title),
            ("사건번호", case_number),
            ("재결청", agency),
            ("의결일자", decision_date),
            ("재결요지", summary),
            ("주문", normalize_text(data.get("주문"))),
            ("청구취지", normalize_text(data.get("청구취지"))),
            ("이유", normalize_text(data.get("이유"))),
        ]
    )
    if not content:
        return None

    return {
        "id": stable_id("admin-decision", path, case_number, str(data.get("행정심판재결례일련번호") or "")),
        "domain_code": "03_administrative_law",
        "domain_name": DOMAIN_LABELS["03_administrative_law"],
        "split": detect_split(path),
        "source_type": "admin_decision",
        "title": title or case_number or path.stem,
        "case_number": case_number,
        "case_name": title,
        "court": agency,
        "decision_date": decision_date,
        "summary": summary,
        "content": content,
        "metadata": {
            "source_path": str(path),
            "source_dataset": "Sublabel",
            "decision_serial": normalize_text(data.get("행정심판재결례일련번호")),
            "disposition_agency": normalize_text(data.get("처분청")),
            "decision_agency": normalize_text(data.get("재결청")),
        },
    }


def normalize_labeled_judgment(data: dict[str, Any], path: Path) -> dict[str, Any] | None:
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    reference_info = data.get("Reference_info") if isinstance(data.get("Reference_info"), dict) else {}
    class_info = data.get("Class_info") if isinstance(data.get("Class_info"), dict) else {}

    title = normalize_text(info.get("caseNm") or info.get("caseTitle"))
    case_number = normalize_text(info.get("caseNo") or info.get("caseNoID"))
    court = normalize_text(info.get("courtNm") or info.get("courtType"))
    decision_date = normalize_text(info.get("judmnAdjuDe"))
    summary_items = []
    for item in data.get("Summary", []):
        if isinstance(item, dict):
            summary_text = normalize_text(item.get("summ_pass") or item.get("summ_contxt"))
        else:
            summary_text = normalize_text(item)
        if summary_text:
            summary_items.append(summary_text)
    qa_items = []
    for item in data.get("jdgmnInfo", []):
        if not isinstance(item, dict):
            continue
        question = normalize_text(item.get("question") or item.get("q"))
        answer = normalize_text(item.get("answer") or item.get("a"))
        if question or answer:
            qa_items.append(f"질문: {question}\n답변: {answer}".strip())

    judgment = normalize_text(data.get("jdgmn"))
    content = join_sections(
        [
            ("사건명", title),
            ("사건번호", case_number),
            ("법원", court),
            ("선고일자", decision_date),
            ("요약", "\n".join(summary_items)),
            ("질답", "\n\n".join(qa_items)),
            ("참조조문", normalize_text(reference_info.get("reference_rules"))),
            ("참조판례", normalize_text(reference_info.get("reference_court_case"))),
            ("판결문", judgment),
        ]
    )
    if not content:
        return None

    domain_code, domain_name = detect_domain(
        path,
        title,
        case_number,
        normalize_text(class_info.get("class_name")),
        normalize_text(class_info.get("instance_name")),
    )
    return {
        "id": stable_id("labeled-precedent", path, case_number, normalize_text(info.get("id"))),
        "domain_code": domain_code,
        "domain_name": domain_name,
        "split": detect_split(path),
        "source_type": "labeled_judgment",
        "title": title or case_number or path.stem,
        "case_number": case_number,
        "case_name": title,
        "court": court,
        "decision_date": decision_date,
        "summary": summary_items[0] if summary_items else "",
        "content": content,
        "metadata": {
            "source_path": str(path),
            "source_dataset": "Training/Validation",
            "raw_id": normalize_text(info.get("id")),
            "data_type": normalize_text(info.get("dataType")),
            "class_name": normalize_text(class_info.get("class_name")),
            "instance_name": normalize_text(class_info.get("instance_name")),
            "keywords": normalize_text(data.get("keyword_tagg")),
            "reference_statutes": normalize_text(reference_info.get("reference_rules")),
            "reference_cases": normalize_text(reference_info.get("reference_court_case")),
        },
    }


def normalize_precedent_qa(data: dict[str, Any], path: Path) -> dict[str, Any] | None:
    question = normalize_text(data.get("question"))
    answer = normalize_text(data.get("answer"))
    commentary = normalize_text(data.get("commentary"))
    title = normalize_text(data.get("title"))
    content = join_sections(
        [
            ("제목", title),
            ("질문", question),
            ("답변", answer),
            ("해설", commentary),
            ("관련 법령", normalize_text(data.get("reference_rules"))),
            ("관련 판례", normalize_text(data.get("reference_court_case"))),
            ("일반 참고", normalize_text(data.get("reference_general"))),
        ]
    )
    if not content:
        return None

    domain_code, domain_name = detect_domain(path, title, question, answer, normalize_text(data.get("keyword")))
    return {
        "id": stable_id("precedent-qa", path, normalize_text(data.get("id"))),
        "domain_code": domain_code,
        "domain_name": domain_name,
        "split": detect_split(path),
        "source_type": "precedent_qa",
        "title": title or question[:80] or path.stem,
        "case_number": "",
        "case_name": title,
        "court": "",
        "decision_date": "",
        "summary": answer[:500],
        "content": content,
        "metadata": {
            "source_path": str(path),
            "source_dataset": "Other",
            "raw_id": normalize_text(data.get("id")),
            "keywords": normalize_text(data.get("keyword")),
            "reference_statutes": normalize_text(data.get("reference_rules")),
            "reference_cases": normalize_text(data.get("reference_court_case")),
        },
    }


def normalize_precedent(path: Path) -> dict[str, Any] | None:
    data = read_json_with_fallback(path)
    if not isinstance(data, dict):
        return None
    if "판례일련번호" in data:
        return normalize_sublabel_case(data, path)
    if "행정심판재결례일련번호" in data:
        return normalize_sublabel_decision(data, path)
    if "info" in data and "jdgmn" in data:
        return normalize_labeled_judgment(data, path)
    if {"question", "answer"}.issubset(data):
        return normalize_precedent_qa(data, path)
    return None


def iter_json_files(raw_dir: Path, source_filter: str | None) -> Iterable[Path]:
    if source_filter:
        candidates = [raw_dir / source_filter]
    else:
        priority = {name: index for index, name in enumerate(SOURCE_PRIORITY)}
        candidates = sorted(
            (path for path in raw_dir.iterdir() if path.is_dir()),
            key=lambda path: (priority.get(path.name, len(priority)), path.name),
        )
    for root in candidates:
        if root.exists():
            yield from root.rglob("*.json")


def temp_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.name}.tmp")


def write_jsonl(
    raw_dir: Path,
    output_path: Path,
    source_filter: str | None,
    start_offset: int,
    max_documents: int | None,
    max_per_domain: int | None,
    skip_unknown_domain: bool,
    progress_interval: int,
) -> dict[str, Any]:
    if start_offset < 0:
        raise ValueError("start_offset must be 0 or greater.")
    if progress_interval < 0:
        raise ValueError("progress_interval must be 0 or greater.")
    if source_filter and not (raw_dir / source_filter).exists():
        raise ValueError(f"Unknown source folder: {source_filter}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_path = temp_output_path(output_path)

    stats: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()

    with write_path.open("w", encoding="utf-8", newline="\n") as file:
        for path in iter_json_files(raw_dir, source_filter):
            if stats["json_files_seen"] < start_offset:
                stats["json_files_seen"] += 1
                stats["skipped_by_offset"] += 1
                continue

            stats["json_files_seen"] += 1
            try:
                document = normalize_precedent(path)
            except Exception:
                stats["errors"] += 1
                continue

            if document is None:
                stats["skipped_unrecognized_schema"] += 1
                continue

            domain_code = str(document.get("domain_code") or "unknown")
            if skip_unknown_domain and domain_code == "unknown":
                stats["skipped_unknown_domain"] += 1
                continue

            if max_per_domain and domain_counts[domain_code] >= max_per_domain:
                stats["skipped_by_domain_limit"] += 1
                continue

            file.write(json.dumps(document, ensure_ascii=False) + "\n")
            stats["documents_written"] += 1
            domain_counts[domain_code] += 1
            source_type_counts[str(document.get("source_type") or "unknown")] += 1

            if progress_interval and stats["documents_written"] % progress_interval == 0:
                print(
                    "progress: "
                    f"json_files_seen={stats['json_files_seen']} "
                    f"documents_written={stats['documents_written']} "
                    f"domains={dict(sorted(domain_counts.items()))}",
                    flush=True,
                )

            if max_documents and stats["documents_written"] >= max_documents:
                break

    write_path.replace(output_path)
    return {
        "raw_dir": str(raw_dir),
        "output_path": str(output_path),
        "source_filter": source_filter,
        "start_offset": start_offset,
        "max_documents": max_documents,
        "max_per_domain": max_per_domain,
        "skip_unknown_domain": skip_unknown_domain,
        "stats": dict(stats),
        "domains": dict(sorted(domain_counts.items())),
        "source_types": dict(sorted(source_type_counts.items())),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize precedent JSON files to JSONL documents.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--source", choices=("Other", "Sublabel", "Training", "Validation"))
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--max-per-domain", type=int, default=None)
    parser.add_argument("--skip-unknown-domain", action="store_true")
    parser.add_argument("--progress-interval", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = write_jsonl(
        raw_dir=args.raw_dir,
        output_path=args.output,
        source_filter=args.source,
        start_offset=args.start_offset,
        max_documents=args.max_documents,
        max_per_domain=args.max_per_domain,
        skip_unknown_domain=args.skip_unknown_domain,
        progress_interval=args.progress_interval,
    )
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"output: {args.output}")
    print(f"summary: {summary_path}")
    print(f"stats: {summary['stats']}")
    print(f"domains: {summary['domains']}")
    print(f"source_types: {summary['source_types']}")


if __name__ == "__main__":
    main()
