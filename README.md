# legal-rag-service

AI Hub 법률 데이터를 기반으로 하는 RAG(Retrieval-Augmented Generation) 법률 질의응답 웹 서비스입니다.  
백엔드는 FastAPI, 프론트엔드는 React + TypeScript + Vite, AI 파이프라인은 LangChain/OpenAI/ChromaDB를 기준으로 구성합니다.

## 현재 확인된 상태

2026-05-25 기준 로컬 프로젝트에서 확인한 상태입니다.

| 항목 | 상태 |
| --- | --- |
| Git 저장소 | 생성됨 |
| Python venv | `.venv` 생성됨 |
| Python 버전 | `3.13.12` |
| venv pip | 아직 없음 (`No module named pip`) |
| Node.js | `v24.16.0` |
| npm | `11.13.0` (`npm.cmd`로 확인) |
| Frontend node_modules | 아직 없음 |
| package-lock.json | 아직 없음 |
| Backend 구조 | 생성됨 |
| Frontend 구조 | 생성됨 |
| AI/data/docs 구조 | 생성됨 |

PowerShell 실행 정책 때문에 `npm --version`은 막힐 수 있습니다. Windows에서는 `npm.cmd`를 사용하면 됩니다.

## 기술 스택

- Backend: FastAPI, Python, Pydantic Settings, SQLAlchemy, PostgreSQL, JWT
- Frontend: React, TypeScript, Vite, Axios
- AI/RAG: LangChain, OpenAI API, ChromaDB, tiktoken
- Database: PostgreSQL
- Auth: JWT
- 확장 예정: Docker, Docker Compose, Alembic, CI/CD, 클라우드 배포

## 프로젝트 구조

```text
legal-rag-service/
  backend/
    app/
      api/              API 라우터와 엔드포인트
      core/             환경 설정, 보안, 공통 설정
      db/               DB 연결과 세션 관리
      models/           SQLAlchemy ORM 모델
      schemas/          Pydantic 요청/응답 스키마
      services/         비즈니스 로직과 RAG 서비스
    requirements.txt    백엔드 Python 패키지 목록

  frontend/
    src/
      api/              백엔드 API 클라이언트
      App.tsx           초기 질의응답 화면
      main.tsx          React 엔트리포인트
    package.json        프론트엔드 패키지와 실행 스크립트

  ai/
    preprocessing/      원천 법률 데이터 정제
    embeddings/         임베딩 생성
    vectorstore/        ChromaDB 저장/색인
    rag/                검색 및 생성 체인

  data/
    raw/                AI Hub 원천 데이터
    processed/          전처리 완료 데이터
    chunks/             검색용 청크 데이터

  docs/                 API, 데이터 처리, 배포 문서
```

## 설치 순서

1. `.env.example`을 참고해 `.env`를 만듭니다.
2. Python venv에 `pip`를 준비합니다.
3. 백엔드 패키지를 설치합니다.
4. 프론트엔드 패키지를 설치합니다.
5. 백엔드와 프론트엔드 개발 서버를 각각 실행합니다.

## Backend 실행

현재 `.venv`에는 `pip`가 없으므로 먼저 아래 명령으로 `pip`를 준비합니다.

```powershell
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

패키지 설치와 서버 실행:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

실행 후 확인:

- API 문서: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`

## Frontend 실행

PowerShell에서 `npm` 실행이 막히면 `npm.cmd`를 사용합니다.

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

실행 후 확인:

- Frontend: `http://localhost:5173`

## 환경 변수

루트의 `.env.example`을 복사해서 `.env`로 사용합니다.

```powershell
Copy-Item .env.example .env
```

주요 변수:

- `DATABASE_URL`: PostgreSQL 연결 문자열
- `OPENAI_API_KEY`: OpenAI API 키
- `OPENAI_MODEL`: 답변 생성 모델
- `OPENAI_EMBEDDING_MODEL`: 임베딩 모델
- `CHROMA_PERSIST_DIRECTORY`: ChromaDB 저장 경로
- `VITE_API_BASE_URL`: 프론트엔드가 호출할 백엔드 API 주소

## 추천 초기 패키지

Backend:

- `fastapi`, `uvicorn`: API 서버
- `pydantic-settings`, `python-dotenv`: 환경 설정 관리
- `sqlalchemy`, `psycopg`, `alembic`: PostgreSQL과 마이그레이션
- `python-jose`, `passlib`: JWT 인증과 비밀번호 처리
- `langchain`, `langchain-openai`, `chromadb`, `tiktoken`: RAG 파이프라인
- `pytest`, `httpx`: 테스트

Frontend:

- `react`, `react-dom`: UI
- `typescript`, `vite`: 개발 서버와 빌드
- `axios`: API 호출
- `react-router-dom`: 라우팅

## 다음 작업 추천

1. `pip` 설치 후 `backend/requirements.txt` 설치
2. `frontend`에서 `npm.cmd install` 실행
3. PostgreSQL 로컬 실행 또는 Docker Compose 추가
4. Alembic 초기화와 첫 마이그레이션 작성
5. `/api/v1/rag/ask` 엔드포인트 구현
6. AI Hub 데이터 전처리 스크립트 추가
7. ChromaDB 색인 생성 스크립트 추가

## Docker 확장 메모

현재 구조는 Docker 확장을 고려해 `backend`, `frontend`, `ai`, `data`를 분리했습니다. 다음 단계에서 아래 파일을 추가하면 됩니다.

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`
- PostgreSQL 볼륨
- ChromaDB persist 볼륨
- 운영/개발 환경변수 분리
