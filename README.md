# legal-rag-service

AI Hub 법률 데이터와 판례 데이터를 활용한 RAG 기반 법률 질의응답 챗봇 서비스입니다.

사용자가 질문하면 법률/조문 근거와 판례 근거를 함께 검색하고, 답변을 `답변 요약`, `관련 법령`, `관련 판례`, `주의사항` 형식으로 제공합니다. 답변과 검색 결과는 법률 자문이 아닌 참고 정보입니다.

## 주요 기능

- 회원가입/로그인
- JWT access token + refresh token 로그인 유지
- 채팅 세션 생성/조회/삭제
- 채팅방 검색 및 중요 대화 고정
- 선택한 사건 기준 채팅 목록 필터링
- 멀티턴 챗봇 대화
- 사건 노트 생성 및 채팅 연결
- 사건별 메모 작성 및 조회
- 사건 개요, 최근 메모, 연결 대화 요약
- 사건 메모 기반 RAG 답변
- 답변 모드 선택(기본, 간단, 상세, 쟁점, 상담 준비)
- 근거 부족 판단 및 근거 품질 경고
- 법률 데이터 RAG 검색
- 판례 데이터 RAG 검색
- 법률 컬렉션과 판례 컬렉션 분리 검색
- 답변 근거 표시
- 법률 근거/판례 근거 UI 구분
- 판례 사건번호 표시
- 판례 전처리, 청크 생성, ChromaDB 색인 파이프라인
- 검색 품질 평가와 답변 품질 평가 스크립트
- Docker Compose 실행 구성
- 배포 smoke test 스크립트

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Backend | FastAPI, SQLAlchemy, Alembic, PostgreSQL, JWT |
| Frontend | React 19, TypeScript, Vite, Axios |
| AI/RAG | LangChain, OpenAI API, ChromaDB, tiktoken |
| Infra | Docker, Docker Compose, Nginx |

## 프로젝트 구조

```text
backend/        FastAPI API, 인증, DB, RAG 서비스
frontend/       React 챗봇 UI
ai/
  preprocessing/  원본 데이터 정규화와 청크 생성
  embeddings/     OpenAI embedding과 ChromaDB 색인
  rag/            검색/답변 평가 스크립트
data/
  raw/          원본 데이터 위치 (Git 제외)
  processed/    전처리 산출물 (Git 제외)
  chunks/       청크 산출물 (Git 제외)
docs/           설계, 배포, 릴리즈 문서
scripts/        smoke test 등 운영 보조 스크립트
chroma_db/      로컬 ChromaDB 저장소 (Git 제외)
```

## 현재 RAG 컬렉션

| 용도 | 컬렉션 |
| --- | --- |
| 법률/조문/QA 검색 | `legal_chunks_probe` |
| 판례 검색 | `precedent_chunks_probe_10k` |

현재 판례 컬렉션은 도메인별 2,500건씩 총 1만 건의 균형 샘플로 구성되어 있습니다.

기록된 평가 결과:

- 판례 검색 평가: 20/20 통과
- 법률+판례 답변 평가: 8/8 통과

## 환경 변수

로컬 실행 전 `.env.example`을 복사해 `.env`를 만듭니다.

```powershell
Copy-Item .env.example .env
```

필수 값:

```env
OPENAI_API_KEY=sk-...
JWT_SECRET_KEY=replace-with-long-random-secret
DATABASE_URL=postgresql+psycopg://legal_rag:legal_rag_password@localhost:5432/legal_rag
CHROMA_PERSIST_DIRECTORY=./chroma_db
CHROMA_COLLECTION_NAME=legal_chunks_probe
PRECEDENT_CHROMA_COLLECTION_NAME=precedent_chunks_probe_10k
```

## Docker 실행

```powershell
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

접속:

```text
Frontend: http://localhost:5173
Backend Docs: http://localhost:8000/docs
Health: http://localhost:8000/api/v1/health
```

주의:

- `chroma_db/`가 준비되어 있어야 RAG 답변이 정상 동작합니다.
- 원본 데이터, 전처리 산출물, ChromaDB는 Git에 올리지 않습니다.

## 로컬 개발 실행

Backend:

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

## 데이터 파이프라인

판례 샘플 정규화:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_precedents.py --output data\processed\precedents\precedent_documents.sample.jsonl --max-documents 1000
```

판례 청크 생성:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_precedents.py --input data\processed\precedents\precedent_documents.sample.jsonl --output data\chunks\precedents\precedent_chunks.sample.jsonl
```

판례 ChromaDB dry-run:

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\precedents\precedent_chunks.sample.jsonl --collection-name precedent_chunks_probe --dry-run
```

## 테스트와 평가

Backend:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

Frontend:

```powershell
cd frontend
npm.cmd run test -- --run
npm.cmd run build
```

배포 smoke test:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --with-rag --with-chat
```

판례 검색 평가:

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_precedent_retrieval.py --collection-name precedent_chunks_probe_10k --top-k 5 --use-keyword-boost --output data\processed\precedents\precedent_retrieval_eval.probe_10k.hybrid.json
```

법률+판례 답변 평가:

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_legal_assistant_answers.py --top-k 5 --output data\processed\precedents\legal_assistant_answer_eval.probe_10k.json
```

## 주요 문서

- [판례 검색 확장 설계](docs/case-law-rag-extension.md)
- [데이터 출처와 처리 흐름](docs/data-source.md)
- [배포 가이드](docs/deployment.md)
- [VPS + Docker Compose 배포 가이드](docs/vps-deployment.md)
- [Oracle Cloud Always Free 배포 가이드](docs/oracle-cloud-always-free.md)
- [릴리즈 체크리스트](docs/release-checklist.md)

## Git에 포함하지 않는 항목

- `.env`, `.env.*`
- `.claude/`
- `.venv/`
- `node_modules/`
- `frontend/dist/`
- `data/raw/`
- `data/processed/`
- `data/chunks/`
- `chroma_db/`
- `*.db`, `*.sqlite3`

## 라이선스

MIT
