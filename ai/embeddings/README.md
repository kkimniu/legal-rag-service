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

색인 전에 token 수, 예상 비용, 최소 실행 시간을 추정합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\estimate_index_size.py --input data\chunks\legal_chunks.jsonl --output data\processed\index_estimate.full.json
```

중간 샘플 통계와 원본 파일 수를 기준으로 전체 색인 규모를 projection합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\project_full_index.py --output data\processed\index_projection.full.json
```

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.jsonl --collection-name legal_chunks --reset-collection
```

ChromaDB 저장 경로는 기본적으로 `chroma_db/`이며 Git에 커밋하지 않습니다.
