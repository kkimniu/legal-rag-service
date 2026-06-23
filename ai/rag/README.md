# RAG Evaluation

RAG 검색·답변 품질을 확인하는 평가 스크립트 모음입니다.

## 판례 검색 평가

`precedent_evaluation_questions.jsonl` 기반으로 ChromaDB 검색 품질을 평가합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_precedent_retrieval.py --collection-name precedent_chunks_probe_10k --top-k 5 --use-keyword-boost --output data\processed\precedents\precedent_retrieval_eval.probe_10k.json
```

현재 `precedent_chunks_probe_10k` 기준:

- 판례 문서 샘플: 10,000건
- 분야 분포: 민사/지식재산권/행정/형사 각 2,500건
- chunk 수: 73,414개
- 평가 질문: 20개
- 키워드 보강 기준 도메인 적중률: 100%
- 키워드 보강 기준 기대 키워드 적중률: 100%

## 법령·판례 통합 답변 평가

`legal_assistant_answer_questions.jsonl` 기반으로 실제 RAG API 답변 품질을 평가합니다.
`답변 요약`, `관련 법령`, `관련 판례`, `주의사항` 섹션 포함 여부와 근거 포함 여부를 확인합니다.

```powershell
.\.venv\Scripts\python.exe scripts\eval_chat_answers.py
```

현재 `legal_chunks_probe` + `legal_chunks_extra` + `precedent_chunks_probe_10k` 기준:

- 평가 질문: 8개 (민사/지식재산권/행정/형사 각 2개)
- 답변 품질 통과율: 8/8 (100%)
