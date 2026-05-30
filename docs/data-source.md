# Data Source

AI Hub 법률 데이터 원본은 `data/raw/aihub_legal` 아래에 보관합니다. 원본 데이터는 크기가 크고 재배포 제한이 있을 수 있으므로 Git에 커밋하지 않습니다.

## Raw Directory Mapping

| Local directory | Source dataset |
| --- | --- |
| `data/raw/aihub_legal/01_civil_law` | `01.민사법 LLM 사전학습 및 Instruction Tuning 데이터` |
| `data/raw/aihub_legal/02_intellectual_property_law` | `02.지식재산권법 LLM 사전학습 및 Instruction Tuning 데이터` |
| `data/raw/aihub_legal/03_administrative_law` | `03.행정법 LLM 사전학습 및 Instruction Tuning 데이터` |
| `data/raw/aihub_legal/04_criminal_law` | `04.형사법 LLM 사전학습 및 Instruction Tuning 데이터` |

## Processing Plan

1. 원본 구조 점검: `ai/preprocessing/inspect_dataset.py`
2. 표준 문서 JSONL 생성: `ai/preprocessing/normalize_documents.py`
3. RAG 검색용 청크 생성: `data/chunks/legal_chunks.jsonl`
4. 임베딩 생성 후 ChromaDB 저장

## Notes

- 한글 폴더명과 파일명은 유지해도 됩니다.
- Python 스크립트에서는 `pathlib.Path`와 UTF-8/CP949 fallback을 사용합니다.
- 원본 데이터는 수정하지 않고, 변환 결과만 `processed`와 `chunks`에 새로 생성합니다.
