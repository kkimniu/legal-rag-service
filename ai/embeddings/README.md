# Embeddings

표준 chunk JSONL을 OpenAI embedding으로 변환하고 ChromaDB에 저장하는 영역입니다.

## Dry Run

API 호출 없이 chunk 입력과 metadata 변환만 검증합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.sample.jsonl --dry-run --max-chunks 100
```

## Sample Index

샘플 chunk를 실제 ChromaDB에 저장합니다. 실행 전 `.env`에 `OPENAI_API_KEY`가 있어야 합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.sample.jsonl --collection-name legal_chunks_sample --reset-collection
```

## Full Index

전체 chunk 파일을 색인합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.jsonl --collection-name legal_chunks --reset-collection
```

ChromaDB 저장 경로는 기본적으로 `chroma_db/`이며 Git에 커밋하지 않습니다.
