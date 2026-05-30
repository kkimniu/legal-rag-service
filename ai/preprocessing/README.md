# Preprocessing

AI Hub 법률 원본 데이터를 RAG에 넣기 전 구조를 점검하고 표준 포맷으로 변환하는 영역입니다.

권장 흐름:

1. `inspect_dataset.py`로 원본 데이터의 파일 수, 확장자, JSON 키, CSV 헤더를 확인합니다.
2. `normalize_documents.py`로 라벨링 JSON을 표준 문서 JSONL로 변환합니다.
3. 원본은 `data/raw/aihub_legal` 아래에 그대로 둡니다.
4. 정제된 문서는 `data/processed`에 JSONL로 저장합니다.
5. `chunk_documents.py`로 검색용 청크를 `data/chunks`에 저장합니다.

원본 데이터는 Git에 커밋하지 않습니다.

## Commands

데이터 구조 점검:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\inspect_dataset.py --max-samples 1
```

샘플 문서 변환:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --output data\processed\legal_documents.sample.jsonl --max-documents 1000
```

분야별 샘플 문서 변환:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --output data\processed\legal_documents.sample.jsonl --max-per-domain 250
```

전체 문서 변환:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py
```

샘플 문서 청크 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.sample.jsonl --output data\chunks\legal_chunks.sample.jsonl
```

전체 문서 청크 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py
```
