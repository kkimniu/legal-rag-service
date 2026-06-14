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

특정 키워드가 포함된 문서만 보강 추출:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\select_keyword_documents.py --output data\processed\legal_documents.admin_keywords.jsonl --domain-code 03_administrative_law --keywords 재량 일탈 남용 영업정지 과징금 제재처분 --max-per-keyword 40
```

중간 색인에 없는 쟁점을 보강할 때 사용합니다. 출력 산출물은 `data/processed` 아래에 저장되며 Git에 커밋하지 않습니다.

전체 문서 변환:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py
```

대용량 데이터는 분야별/배치별로 나눠 변환합니다. 출력은 완료 전까지 `.tmp` 파일에 쓰고, 완료되면 최종 `.jsonl`로 교체됩니다.

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --domain-code 01_civil_law --start-offset 0 --max-documents 10000 --output data\processed\legal_documents.civil.000000.jsonl
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --domain-code 01_civil_law --start-offset 10000 --max-documents 10000 --output data\processed\legal_documents.civil.010000.jsonl
```

샘플 문서 청크 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.sample.jsonl --output data\chunks\legal_chunks.sample.jsonl
```

전체 문서 청크 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py
```

대용량 문서 청크도 같은 배치 파일 단위로 생성합니다.

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.civil.000000.jsonl --output data\chunks\legal_chunks.civil.000000.jsonl
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.civil.010000.jsonl --output data\chunks\legal_chunks.civil.010000.jsonl
```
