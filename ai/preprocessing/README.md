# Preprocessing

AI Hub 법률 데이터와 판례 데이터를 RAG 검색에 맞는 표준 JSONL 구조로 변환하는 영역입니다.

## 법률 QA/조문 데이터

원본 위치:

```text
data/raw/aihub_legal/
```

샘플 문서 변환:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --output data\processed\legal_documents.sample.jsonl --max-documents 1000
```

샘플 chunk 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.sample.jsonl --output data\chunks\legal_chunks.sample.jsonl
```

대용량 처리는 분야별/배치별로 나눠 실행합니다.

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --domain-code 01_civil_law --start-offset 0 --max-documents 10000 --output data\processed\legal_documents.civil.000000.jsonl
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.civil.000000.jsonl --output data\chunks\legal_chunks.civil.000000.jsonl
```

## 판례 데이터

원본 위치:

```text
data/raw/precedents/incoming/
```

지원하는 입력 스키마:

- `Sublabel`: 판례와 행정심판 재결례 원문 메타데이터
- `Training`, `Validation`: AI Hub 판결문 라벨링 데이터
- `Other`: 판례 관련 QA 보조 데이터

판례 샘플 문서 변환:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_precedents.py --output data\processed\precedents\precedent_documents.sample.jsonl --max-documents 1000
```

판례 샘플 chunk 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_precedents.py --input data\processed\precedents\precedent_documents.sample.jsonl --output data\chunks\precedents\precedent_chunks.sample.jsonl
```

판례 컬렉션 dry-run:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\precedents\precedent_chunks.sample.jsonl --collection-name precedent_chunks_probe --dry-run
```

실제 판례 임베딩:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\precedents\precedent_chunks.sample.jsonl --collection-name precedent_chunks_probe --reset-collection --skip-existing
```

## 주의

- 원본 JSON은 Git에 올리지 않습니다.
- 전처리 결과와 ChromaDB도 재생성 가능한 산출물이므로 Git에 올리지 않습니다.
- 큰 데이터는 `--max-documents`, `--start-offset`, `--max-per-domain` 옵션으로 나눠 처리합니다.
