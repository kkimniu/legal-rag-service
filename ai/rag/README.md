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

## 판례 검색 평가

판례 컬렉션 품질은 `precedent_evaluation_questions.jsonl`과 `evaluate_precedent_retrieval.py`로 확인합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_precedent_retrieval.py --collection-name precedent_chunks_probe_10k --top-k 5 --use-keyword-boost --output data\processed\precedents\precedent_retrieval_eval.probe_10k.hybrid.json
```

현재 `precedent_chunks_probe_10k` 기준:

- 판례 문서 샘플: 10,000건
- 분야 분포: 민사/지식재산권/행정/형사 각 2,500건
- chunk 수: 73,414개
- 평가 질문: 20개
- 키워드 보강 기준 도메인 적중률: 100%
- 키워드 보강 기준 기대 키워드 적중률: 100%

## 법률+판례 답변 평가

실제 답변이 `답변 요약`, `관련 법령`, `관련 판례`, `주의사항` 형식을 지키는지 확인합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_legal_assistant_answers.py --top-k 5 --output data\processed\precedents\legal_assistant_answer_eval.probe_10k.json
```

현재 `precedent_chunks_probe_10k`와 `legal_chunks_probe` 기준:

- 평가 질문: 8개
- 분야 분포: 민사/지식재산권/행정/형사 각 2개
- 필수 답변 섹션: 답변 요약, 관련 법령, 관련 판례, 주의사항
- 법률 근거와 판례 근거 동시 포함
- 답변 품질 통과율: 8/8 (100%)

## 답변 품질 평가

검색 품질이 안정화된 뒤에는 실제 `/rag/ask` API를 호출해 생성 답변을 점검합니다. 이 평가는 답변 길이, 근거 수, 면책 문구, 근거 언급, 기대 키워드가 근거에 포함되는지를 확인합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_answers.py --use-domain-filter --per-domain-limit 2 --output data\processed\answer_eval.medium.8q.json
```

기본값은 분야별 1개 질문만 실행합니다. 질문 수를 늘리면 답변 생성 LLM 호출 비용이 함께 증가합니다. 결과에는 전체 통과율, 분야별 통과율, 평균 답변 길이, 평균 근거 수, 실패 사유가 포함됩니다.

현재 기준선은 분야별 2개씩 총 8개 질문에서 basic quality 100%입니다. 답변 생성 프롬프트는 근거에 없는 법률요건, 예시, 일반론을 작성하지 않고 근거 부족을 명확히 밝히도록 설정되어 있습니다.
