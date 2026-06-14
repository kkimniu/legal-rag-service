# legal-rag-service

AI Hub 법률 데이터를 기반으로 하는 RAG(Retrieval-Augmented Generation) 법률 질의응답 웹 서비스입니다. 백엔드는 FastAPI, 프론트엔드는 React + TypeScript + Vite, AI 파이프라인은 LangChain/OpenAI/ChromaDB를 기준으로 구성합니다.

## 현재 상태

2026-05-31 기준:

| 항목 | 상태 |
| --- | --- |
| Branch | `develop` |
| Backend | FastAPI 기본 구조, health API, RAG ask API, Chat API |
| Auth | 회원가입, 로그인, JWT 발급, 현재 사용자 조회 API |
| Frontend | 챗봇 UI, 생성 답변, 검색 근거 UI, 로그인/회원가입 UI, 대화방 조회/삭제 UI |
| AI preprocessing | 데이터 구조 점검, 표준 JSONL 변환, chunk 생성 |
| Embeddings | OpenAI embedding -> ChromaDB 색인 스크립트 |
| Sample index | `legal_chunks_sample` 1,000개, `legal_chunks_medium` 4,000개 균형 샘플 색인 확인 |
| Database | PostgreSQL Docker Compose 구성, Alembic 마이그레이션, 인증 API 검증 |

## 기술 스택

- Backend: FastAPI, Python, Pydantic Settings, SQLAlchemy, PostgreSQL, JWT
- Frontend: React, TypeScript, Vite, Axios
- AI/RAG: LangChain, OpenAI API, ChromaDB, tiktoken
- Infra: Docker, Docker Compose

## 프로젝트 구조

```text
backend/                  FastAPI 백엔드
frontend/                 React + TypeScript + Vite 프론트엔드
ai/preprocessing/         원본 데이터 점검, 정규화, chunk 생성
ai/embeddings/            embedding 생성 및 ChromaDB 색인
data/raw/                 AI Hub 원본 데이터, Git 제외
data/processed/           전처리 산출물, Git 제외
data/chunks/              검색용 chunk 산출물, Git 제외
docs/                     데이터 출처와 처리 문서
scripts/                  로컬 스모크 테스트와 운영 보조 스크립트
chroma_db/                ChromaDB 로컬 저장소, Git 제외
```

## 환경 변수

루트의 `.env.example`을 복사해서 `.env`를 만듭니다.

```powershell
Copy-Item .env.example .env
```

주요 변수:

- `OPENAI_API_KEY`: OpenAI API 키
- `OPENAI_MODEL`: 답변 생성 모델
- `OPENAI_EMBEDDING_MODEL`: 임베딩 모델
- `CHROMA_PERSIST_DIRECTORY`: ChromaDB 저장 경로
- `CHROMA_COLLECTION_NAME`: ChromaDB 컬렉션 이름
- `DATABASE_URL`: PostgreSQL 연결 문자열
- `VITE_API_BASE_URL`: 프론트엔드 API 주소

샘플 색인을 사용할 때:

```env
CHROMA_COLLECTION_NAME=legal_chunks_sample
```

중간 규모 색인을 사용할 때:

```env
CHROMA_COLLECTION_NAME=legal_chunks_medium
```

민사법 probe 색인을 사용할 때:

```env
CHROMA_COLLECTION_NAME=legal_chunks_civil_probe
```

## 로컬 실행

Backend:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

확인:

- API 문서: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`
- Frontend: `http://localhost:5173`

## RAG 데이터 처리

데이터 구조 점검:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\inspect_dataset.py --max-samples 1
```

표준 문서 샘플 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --output data\processed\legal_documents.sample.jsonl --max-per-domain 250
```

chunk 샘플 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.sample.jsonl --output data\chunks\legal_chunks.sample.jsonl
```

샘플 ChromaDB 색인:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.sample.jsonl --collection-name legal_chunks_sample --reset-collection --max-per-domain 250
```

중간 규모 문서/chunk 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --output data\processed\legal_documents.medium.jsonl --max-per-domain 1000
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.medium.jsonl --output data\chunks\legal_chunks.medium.jsonl
```

중간 규모 ChromaDB 색인:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.medium.jsonl --collection-name legal_chunks_medium --max-per-domain 1000 --reset-collection
```

행정법 키워드 보강 문서/chunk 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\select_keyword_documents.py --output data\processed\legal_documents.admin_keywords_v2.jsonl --domain-code 03_administrative_law --keywords 재량 일탈 남용 영업정지 과징금 제재처분 --max-per-keyword 40
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.admin_keywords_v2.jsonl --output data\chunks\legal_chunks.admin_keywords_v2.jsonl
.\.venv\Scripts\python.exe ai\preprocessing\select_keyword_documents.py --output data\processed\legal_documents.admin_procedure_keywords.jsonl --domain-code 03_administrative_law --keywords 사전통지 의견제출 절차 --max-per-keyword 40
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.admin_procedure_keywords.jsonl --output data\chunks\legal_chunks.admin_procedure_keywords.jsonl
```

보강 chunk를 기존 중간 색인에 추가:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.admin_keywords_v2.jsonl --collection-name legal_chunks_medium --skip-existing --max-retries 8 --retry-base-seconds 3
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.admin_procedure_keywords.jsonl --collection-name legal_chunks_medium --skip-existing --max-retries 8 --retry-base-seconds 3
```

색인 중 OpenAI rate limit이 발생했거나 중간에 끊겼다면 이어서 실행합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.medium.jsonl --collection-name legal_chunks_medium --max-per-domain 1000 --skip-existing --max-retries 8 --retry-base-seconds 3
```

전체 색인 전 규모/비용 추정:

먼저 원본 데이터를 분야별/배치별 표준 문서와 chunk로 변환합니다. 이 단계는 OpenAI API를 호출하지 않지만, 데이터가 커서 시간이 걸립니다. 완료 전에는 `.tmp` 파일에 쓰고, 성공하면 최종 `.jsonl`로 교체됩니다.

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --domain-code 01_civil_law --start-offset 0 --max-documents 10000 --output data\processed\legal_documents.civil.000000.jsonl
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.civil.000000.jsonl --output data\chunks\legal_chunks.civil.000000.jsonl
```

다음 배치는 offset을 배치 크기만큼 증가시켜 생성합니다.

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_documents.py --domain-code 01_civil_law --start-offset 10000 --max-documents 10000 --output data\processed\legal_documents.civil.010000.jsonl
.\.venv\Scripts\python.exe ai\preprocessing\chunk_documents.py --input data\processed\legal_documents.civil.010000.jsonl --output data\chunks\legal_chunks.civil.010000.jsonl
```

생성한 chunk 파일의 규모와 비용을 추정합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\estimate_index_size.py --input data\chunks\legal_chunks.civil.000000.jsonl --output data\processed\index_estimate.civil.000000.json
```

전체 원본 파일 수와 중간 샘플 통계를 사용해 full index를 projection:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\project_full_index.py --output data\processed\index_projection.full.json
```

전체 색인은 오래 걸리므로 작은 배치 파일 단위로 나눠 실행합니다. 먼저 dry run으로 첫 배치 입력을 확인합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.civil.000000.jsonl --collection-name legal_chunks_full --dry-run
```

첫 실제 배치만 컬렉션을 초기화합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.civil.000000.jsonl --collection-name legal_chunks_full --reset-collection --skip-existing --max-retries 8 --retry-base-seconds 3
```

다음 배치부터는 `--reset-collection` 없이 다른 chunk 배치 파일을 추가합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.civil.010000.jsonl --collection-name legal_chunks_full --skip-existing --max-retries 8 --retry-base-seconds 3
```

중간에 끊긴 배치는 같은 명령을 다시 실행합니다. `--skip-existing`이 이미 저장된 chunk id를 건너뛰므로 같은 범위를 안전하게 재시도할 수 있습니다.

현재 중간 색인과 행정법 보강 chunk 기준 추정:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\estimate_index_size.py --input data\chunks\legal_chunks.medium.jsonl data\chunks\legal_chunks.admin_keywords_v2.jsonl data\chunks\legal_chunks.admin_procedure_keywords.jsonl --output data\processed\index_estimate.medium_enriched.json
```

기본 비용 계산은 `text-embedding-3-small`의 1M tokens당 `$0.02`를 사용합니다. 실제 비용은 OpenAI 가격표와 계정 조건에 따라 달라질 수 있으므로 실행 전 확인합니다.

현재 생성된 중간+보강 chunk 파일 전체 기준 예시:

- 중복 제외 chunk 수: 18,250개
- 예상 embedding tokens: 약 1,175만 tokens
- 예상 embedding 비용: 약 $0.24
- 1M TPM 기준 이론상 최소 시간: 약 11.8분

중간 샘플 비율을 전체 원본에 투영한 full index 예상:

- 원본 JSON 문서 수: 537,122개
- 예상 chunk 수: 약 3,033,296개
- 예상 embedding tokens: 약 19.5억 tokens
- 예상 embedding 비용: 약 $39.07
- 1M TPM 기준 이론상 최소 시간: 약 32.6시간
- 실제 실행 시간은 네트워크, 재시도, Chroma upsert 속도 때문에 더 길어질 수 있습니다.

## Docker Compose 실행

Docker Desktop 설치 후 `.env`를 준비하고 실행합니다. 현재 로컬 환경에 Docker CLI가 없다면 `docker compose` 명령은 실행되지 않습니다.

```powershell
docker compose up --build
```

마이그레이션 적용:

```powershell
docker compose exec backend python -m alembic upgrade head
```

서비스:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

중지:

```powershell
docker compose down
```

볼륨까지 삭제:

```powershell
docker compose down -v
```

## Database Migration

Alembic은 `backend/alembic` 아래에 구성되어 있습니다. 로컬 PostgreSQL이 실행 중이고 `.env`의 `DATABASE_URL`이 맞으면 아래 명령으로 마이그레이션을 적용합니다.

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

새 마이그레이션 생성:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "마이그레이션 설명"
```

## Auth API

회원가입과 로그인 API는 PostgreSQL에 `users` 테이블이 있어야 동작합니다. 먼저 Alembic 마이그레이션을 적용합니다.

회원가입:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/auth/register `
  -ContentType "application/json" `
  -Body '{"email":"user@example.com","password":"password123"}'
```

로그인:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/auth/login `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=user@example.com&password=password123"
```

현재 사용자 조회:

```powershell
$token = "<access_token>"
Invoke-RestMethod `
  -Method Get `
  -Uri http://localhost:8000/api/v1/auth/me `
  -Headers @{ Authorization = "Bearer $token" }
```

프론트엔드에도 로그인/회원가입 패널이 있습니다. PostgreSQL과 Alembic 마이그레이션이 준비되지 않은 상태에서는 인증 요청이 실패 안내를 표시합니다.

로그인 상태에서 RAG 질문을 보내면 질문, 답변, 검색 근거가 `rag_queries` 테이블에 저장됩니다.
프론트엔드는 챗봇 UI를 기본 화면으로 사용하며, 로그인한 사용자의 대화방과 메시지를 `chat_sessions`, `chat_messages` 테이블에 저장합니다.

최근 질문 이력 조회:

```powershell
$token = "<access_token>"
Invoke-RestMethod `
  -Method Get `
  -Uri http://localhost:8000/api/v1/rag/history `
  -Headers @{ Authorization = "Bearer $token" }
```

## Chat API

챗봇 기능은 로그인한 사용자만 사용할 수 있습니다. 먼저 Alembic 마이그레이션을 적용해 `chat_sessions`, `chat_messages` 테이블을 생성합니다. 대화방은 생성 시점의 `domain_code`로 법 분야가 고정되고, 이후 메시지는 해당 분야 필터로 검색합니다.

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

대화방 생성:

```powershell
$token = "<access_token>"
$session = Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/chat/sessions `
  -ContentType "application/json" `
  -Headers @{ Authorization = "Bearer $token" } `
  -Body '{"title":"민사법 상담","domain_code":"01_civil_law"}'
```

메시지 전송:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/chat/sessions/$($session.id)/messages" `
  -ContentType "application/json" `
  -Headers @{ Authorization = "Bearer $token" } `
  -Body '{"content":"계약 불이행으로 손해가 발생한 경우 책임은 어떻게 판단되나요?"}'
```

대화방 목록 조회:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri http://localhost:8000/api/v1/chat/sessions `
  -Headers @{ Authorization = "Bearer $token" }
```

## 동작 확인

전체 실행 상태를 빠르게 확인:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

RAG 질문, 이력 저장, 이력 삭제까지 확인:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --with-rag
```

`--with-rag`는 실제 답변 생성과 임베딩 조회를 실행하므로 OpenAI 사용량이 발생합니다.

Backend health:

```powershell
cd backend
..\.venv\Scripts\python.exe -c "from fastapi.testclient import TestClient; from app.main import app; r=TestClient(app).get('/api/v1/health'); print(r.status_code, r.json())"
```

RAG ask:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/rag/ask `
  -ContentType "application/json" `
  -Body '{"question":"자동차 수리업자가 차량 수리에 실패했을 때 손해배상 책임을 면제받기 위해 증명해야 할 조건은 무엇인가요?"}'
```

Backend tests:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

Frontend tests:

```powershell
cd frontend
npm.cmd run test
```

## 브라우저 수동 테스트

1. Docker 실행: `docker compose up --build -d`
2. 마이그레이션 적용: `docker compose exec backend python -m alembic upgrade head`
3. 브라우저 접속: `http://localhost:5173`
4. 회원가입 또는 로그인
5. 법 분야를 선택하고 챗봇 메시지 입력
6. 답변, 검색 근거, RAG 연결 상태 확인
7. 대화 목록에서 방금 대화를 다시 열기
8. 대화 삭제 버튼으로 항목 삭제
9. API 문서 확인: `http://localhost:8000/docs`

## RAG 검색 품질 평가

답변 생성 전에 검색 품질만 먼저 확인하려면 `ai/rag/evaluation_questions.jsonl` 질문 세트를 사용합니다. 이 평가는 답변 LLM 호출 없이 질문 임베딩과 ChromaDB 검색만 실행합니다. 현재 질문 세트는 32개이며, 각 법 분야별 8개씩 구성되어 있습니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5
```

분야 필터 기준으로 비교하려면 아래 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5 --use-expected-domain-filter --output data\processed\retrieval_eval.medium.filtered.json
```

결과는 `data/processed/retrieval_eval.medium.json`에 저장됩니다.

현재 RAG 검색은 벡터 검색 결과에 질문 핵심 키워드가 포함된 chunk를 보강해서 합칩니다. 특정 법률 용어가 있는 질문에서 순수 벡터 검색이 다른 절차 쟁점으로 치우치는 문제를 줄이기 위한 기본 hybrid retrieval 방식입니다.

현재 `legal_chunks_medium` 기준선:

- 행정법 보강 chunk 추가 후 총 4,255개 chunk
- 분야 필터 + 키워드 보강 기준 32개 질문의 분야 적중률: 100%
- 분야 필터 + 키워드 보강 기준 32개 질문의 키워드 적중률: 100%

답변 품질 평가:

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_answers.py --use-domain-filter --per-domain-limit 2 --output data\processed\answer_eval.medium.8q.json
```

답변 평가는 실제 답변 생성 API를 호출하므로 OpenAI 사용량이 발생합니다.

현재 답변 품질 기준선:

- 분야별 1개씩 총 4개 질문 평가
- 분야별 2개씩 총 8개 질문 평가
- basic quality pass rate: 100%
- 점검 항목: 답변 길이, 근거 수, 면책 문구, 근거 언급, 기대 키워드 포함 여부
- 결과 항목: 전체/분야별 통과율, 평균 답변 길이, 평균 근거 수, 실패 사유
- 프롬프트는 근거에 없는 법률요건이나 일반론을 추측하지 않도록 제한

## 다음 작업

1. 챗봇 화면에서 4개 법 분야 probe 답변 품질 수동 확인
2. 답변 품질 평가용 테스트셋을 챗봇 API 기준으로 확장
3. 전체 데이터 변환 및 `legal_chunks_full` 배치 색인
4. 대화 제목 수정, 메시지 재생성 같은 챗봇 편의 기능 추가
5. 배포 환경용 Docker 설정 분리
