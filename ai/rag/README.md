# RAG Evaluation

RAG 답변 생성 전에 검색 품질을 먼저 확인하는 도구입니다. 답변 LLM 호출 없이 질문 임베딩과 ChromaDB 검색만 사용합니다.

## 질문 세트

`evaluation_questions.jsonl`은 법률 분야별 기본 질문과 기대 분야, 기대 키워드를 담습니다.

## 검색 평가 실행

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5
```

분야 필터를 적용한 검색 품질을 비교하려면 아래 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5 --use-expected-domain-filter --output data\processed\retrieval_eval.medium.filtered.json
```

결과는 `data/processed/retrieval_eval.medium.json`에 저장됩니다.
