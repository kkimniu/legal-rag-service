# RAG Evaluation

RAG 답변 생성 전에 검색 품질을 먼저 확인하는 도구입니다. 답변 LLM 호출 없이 질문 임베딩과 ChromaDB 검색만 사용합니다.

## 질문 세트

`evaluation_questions.jsonl`은 법률 분야별 기본 질문과 기대 분야, 기대 키워드를 담습니다. 현재 질문 세트는 32개이며, 각 법 분야별 8개씩 구성되어 있습니다.

중간 색인에 아직 충분한 근거가 없는 질문은 `coverage_gap`으로 표시할 수 있습니다. 이 질문은 전체 데이터 색인 필요성을 확인하는 용도이며, core 검색 품질 점수에서는 분리해서 봅니다.

## 검색 평가 실행

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5
```

분야 필터를 적용한 검색 품질을 비교하려면 아래 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5 --use-expected-domain-filter --output data\processed\retrieval_eval.medium.filtered.json
```

실제 서비스 검색 방식과 가장 가까운 조건은 분야 필터와 키워드 보강을 함께 켠 평가입니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5 --use-expected-domain-filter --use-keyword-boost --output data\processed\retrieval_eval.medium.expanded.hybrid.json
```

결과는 `data/processed/retrieval_eval.medium.json`에 저장됩니다.

## 현재 기준선

`legal_chunks_medium`에 행정법 키워드 보강 chunk를 추가한 기준, 분야 필터와 키워드 보강을 함께 사용하면 32개 질문 전체에서 분야 적중률과 키워드 적중률이 모두 100%입니다.
