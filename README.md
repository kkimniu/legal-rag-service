# legal-rag-service

AI Hub 법률 데이터를 기반으로 하는 RAG(Retrieval-Augmented Generation) 법률 질의응답 웹 서비스입니다. 백엔드는 FastAPI, 프론트엔드는 React + TypeScript + Vite, AI 파이프라인은 LangChain/OpenAI/ChromaDB를 기준으로 구성합니다.

## 현재 상태

2026-05-31 기준:

| 항목 | 상태 |
| --- | --- |
| Branch | `develop` |
| Backend | FastAPI 기본 구조, health API, RAG ask API |
| Frontend | 질문 입력, 생성 답변, 검색 근거 UI |
| AI preprocessing | 데이터 구조 점검, 표준 JSONL 변환, chunk 생성 |
| Embeddings | OpenAI embedding -> ChromaDB 색인 스크립트 |
| Sample index | `legal_chunks_sample` 컬렉션 샘플 색인 확인 |
| Database | PostgreSQL Docker Compose 구성 추가 |

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
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\legal_chunks.sample.jsonl --collection-name legal_chunks_sample --reset-collection --max-chunks 100
```

## Docker Compose 실행

Docker Desktop 설치 후 `.env`를 준비하고 실행합니다. 현재 로컬 환경에 Docker CLI가 없다면 `docker compose` 명령은 실행되지 않습니다.

```powershell
docker compose up --build
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

## 다음 작업

1. Docker Compose 실행 검증
2. Alembic 초기화 및 첫 마이그레이션 작성
3. 사용자 회원가입/로그인 JWT API 구현
4. 샘플 색인 규모 확대
5. 전체 데이터 변환 및 전체 ChromaDB 색인
6. RAG 답변 품질 평가용 테스트셋 작성
7. 백엔드/프론트 테스트 코드 추가
