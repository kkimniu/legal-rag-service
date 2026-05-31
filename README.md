# legal-rag-service

AI Hub 법률 데이터를 기반으로 하는 RAG(Retrieval-Augmented Generation) 법률 질의응답 웹 서비스입니다. 백엔드는 FastAPI, 프론트엔드는 React + TypeScript + Vite, AI 파이프라인은 LangChain/OpenAI/ChromaDB를 기준으로 구성합니다.

## 현재 상태

2026-05-31 기준:

| 항목 | 상태 |
| --- | --- |
| Branch | `develop` |
| Backend | FastAPI 기본 구조, health API, RAG ask API |
| Auth | 회원가입, 로그인, JWT 발급, 현재 사용자 조회 API |
| Frontend | 질문 입력, 생성 답변, 검색 근거 UI, 로그인/회원가입 UI |
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

색인 중 OpenAI rate limit이 발생했거나 중간에 끊겼다면 이어서 실행합니다.

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.medium.jsonl --collection-name legal_chunks_medium --max-per-domain 1000 --skip-existing --max-retries 8 --retry-base-seconds 3
```

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

최근 질문 이력 조회:

```powershell
$token = "<access_token>"
Invoke-RestMethod `
  -Method Get `
  -Uri http://localhost:8000/api/v1/rag/history `
  -Headers @{ Authorization = "Bearer $token" }
```

## 동작 확인

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

## RAG 검색 품질 평가

답변 생성 전에 검색 품질만 먼저 확인하려면 `ai/rag/evaluation_questions.jsonl` 질문 세트를 사용합니다. 이 평가는 답변 LLM 호출 없이 질문 임베딩과 ChromaDB 검색만 실행합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5
```

분야 필터 기준으로 비교하려면 아래 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_retrieval.py --collection-name legal_chunks_medium --top-k 5 --use-expected-domain-filter --output data\processed\retrieval_eval.medium.filtered.json
```

결과는 `data/processed/retrieval_eval.medium.json`에 저장됩니다.

현재 RAG 검색은 벡터 검색 결과에 질문 핵심 키워드가 포함된 chunk를 보강해서 합칩니다. 특정 법률 용어가 있는 질문에서 순수 벡터 검색이 다른 절차 쟁점으로 치우치는 문제를 줄이기 위한 기본 hybrid retrieval 방식입니다.

## 다음 작업

1. 검색 품질 확인 결과를 바탕으로 chunk 크기와 top-k 조정
2. 답변 품질 평가용 테스트셋 작성
3. 전체 데이터 변환 및 전체 ChromaDB 색인
4. 프론트 테스트 코드 추가
5. 배포 환경용 Docker 설정 분리
