# Embeddings

표준 chunk JSONL을 OpenAI embedding으로 변환하고 ChromaDB에 저장하는 영역입니다.

## Dry Run

API 호출 없이 chunk 입력과 metadata 변환만 검증합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.sample.jsonl --dry-run --max-chunks 100
```

분야별 균형 샘플 검증:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.sample.jsonl --dry-run --max-per-domain 250
```

## Sample Index

샘플 chunk를 실제 ChromaDB에 저장합니다. 실행 전 `.env`에 `OPENAI_API_KEY`가 있어야 합니다.

분야별 250개씩 총 1,000개 chunk 색인:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.sample.jsonl --collection-name legal_chunks_sample --reset-collection --max-per-domain 250
```

## Full Index

전체 chunk 파일을 색인합니다. 비용과 시간이 발생하므로 샘플 품질을 먼저 확인한 뒤 실행합니다.

먼저 원본 데이터를 분야별/배치별 표준 문서와 chunk로 변환합니다. 이 단계는 OpenAI API를 호출하지 않지만, 데이터가 커서 시간이 걸립니다. 완료 전에는 `.tmp` 파일에 쓰고, 성공하면 최종 `.jsonl`로 교체됩니다.

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --domain-code 01_civil_law --start-offset 0 --max-documents 10000 --output data\processed\legal_documents.civil.000000.jsonl
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.civil.000000.jsonl --output data\chunks\legal_chunks.civil.000000.jsonl
```

색인 전에 token 수, 예상 비용, 최소 실행 시간을 추정합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\estimate_index_size.py --input data\chunks\legal_chunks.civil.000000.jsonl --output data\processed\index_estimate.civil.000000.json
```

중간 샘플 통계와 원본 파일 수를 기준으로 전체 색인 규모를 projection합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\project_full_index.py --output data\processed\index_projection.full.json
```

처음에는 작은 배치 파일로 dry run을 실행해 입력을 확인합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.civil.000000.jsonl --collection-name legal_chunks_full --dry-run
```

첫 실제 배치만 기존 컬렉션을 초기화합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.civil.000000.jsonl --collection-name legal_chunks_full --reset-collection --skip-existing --max-retries 8 --retry-base-seconds 3
```

다음 배치부터는 `--reset-collection`을 빼고 다른 chunk 배치 파일을 추가합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.civil.010000.jsonl --collection-name legal_chunks_full --skip-existing --max-retries 8 --retry-base-seconds 3
```

중간에 끊긴 배치는 같은 명령을 다시 실행합니다. `--skip-existing`이 이미 저장된 chunk id를 건너뛰므로 이어서 복구할 수 있습니다.

한 번에 전체를 실행해야 할 때만 아래 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.jsonl --collection-name legal_chunks --reset-collection
```

ChromaDB 저장 경로는 기본적으로 `chroma_db/`이며 Git에 커밋하지 않습니다.
