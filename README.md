# Legal RAG Service

**사건 관리부터 AI 법률 상담까지, 한 곳에서.**

AI Hub 법령·판례 데이터 174,799 청크를 근거로 실시간 스트리밍 답변을 제공하는 개인용 법률 워크스페이스입니다.
사건별 메모·할 일·기한 알림·첨부자료 OCR을 통합 관리하고, 법률 조문과 판례를 인용한 RAG 기반 챗봇으로 빠르게 검토할 수 있습니다.

> 이 서비스의 답변은 법률 자문이 아닌 참고 정보입니다.

---

## 주요 기능

### 사건 관리

- 사건 생성 · 제목 · 요약 편집 · 삭제
- 사건 상태 관리 (진행중 / 관찰중 / 종료)
- 사건 검색 · 상태 필터 · 종료 사건 숨기기
- 사건별 AI 요약 · 핵심 쟁점 · 다음 할 일 자동 생성 (Insight)
- 사건 보고서 Markdown 파일 내보내기

### 메모 & 할 일

- 사건별 메모 작성 · 수정 · 삭제
- 사건별 할 일 추가 · 기한 설정 · 완료 처리 · 삭제
- 기한 알림 센터: 기한 초과 / 오늘 마감 / 7일 이내 임박 / 30일 이내 분류
- 로그인 시 기한 초과·오늘 마감 항목 경고 배너

### 첨부자료

- PDF · DOCX · 텍스트 · 이미지 파일 업로드
- 텍스트 자동 추출 (PDF 기본 추출 → 추출 실패 시 OCR 자동 전환)
- 스캔 이미지 및 이미지형 PDF OCR (OpenAI Vision API, GPT-4o-mini)
- 추출 텍스트 ChromaDB 색인 → 사건별 유사도 검색 · RAG 컨텍스트 반영
- 원본 파일 다운로드

### 채팅 & RAG 답변

- 멀티턴 대화 · 사건 연결 채팅 · 채팅방 고정 · 삭제
- 실시간 스트리밍 응답 (Server-Sent Events)
- 답변 모드: 기본 / 간단 / 상세 검토 / 쟁점 정리 / 상담 준비
- 법령 조문 + 판례 근거 분리 표시 · 사건번호 · 법원 · 선고일 표시
- 근거 부족 판단 및 품질 경고
- 답변 재생성
- 답변 내 법령·판례 자동 하이퍼링크 (국가법령정보센터 / 대법원 종합법률정보)

### 통합 검색

- 사건 · 메모 · 할 일 · 첨부자료 · 채팅 통합 키워드 검색
- 유형별 필터 · 검색어 하이라이팅 · 더 보기 페이지네이션

### 활동 타임라인

- 사건별 최근 노트 · 할 일 · 첨부자료 · 채팅 활동 시간순 표시

---

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL |
| 인증 | JWT access token + refresh token (python-jose, passlib) |
| Frontend | React 19, TypeScript, Vite, Axios |
| AI / RAG | LangChain, OpenAI API (gpt-4o-mini, text-embedding-3-small), ChromaDB |
| OCR | OpenAI Vision API (GPT-4o-mini), PyMuPDF, Pillow |
| Infra | Docker, Docker Compose, Nginx |

---

## RAG 데이터 현황

| 컬렉션 | 청크 수 | 설명 |
| --- | --- | --- |
| `legal_chunks_probe` | 101,385 | 민사법 중심 법령·조문·QA |
| `precedent_chunks_probe_10k` | 73,414 | 도메인별 균형 샘플 1만 건 판례 |
| 합계 | **174,799** | |

평가 결과:
- 판례 검색 평가: 20/20 통과
- 법률+판례 답변 평가: 8/8 통과

---

## 프로젝트 구조

```text
legal-rag-service/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/     # FastAPI 라우터 (cases, chat, search, auth …)
│   │   ├── models/            # SQLAlchemy ORM 모델
│   │   ├── schemas/           # Pydantic 스키마
│   │   ├── services/          # 비즈니스 로직 (RAG, OCR, 사건 서비스 등)
│   │   └── core/              # 설정, 보안
│   ├── migrations/            # Alembic 마이그레이션
│   └── tests/                 # pytest 테스트 (48개)
├── frontend/
│   └── src/
│       ├── App.tsx            # 메인 React 컴포넌트
│       ├── api/               # axios · fetch API 레이어
│       └── styles.css         # 전체 스타일
├── ai/
│   ├── preprocessing/         # 원본 데이터 정규화 · 청크 생성
│   ├── embeddings/            # OpenAI 임베딩 · ChromaDB 색인
│   └── rag/                   # 검색 · 답변 품질 평가 스크립트
├── scripts/                   # smoke test 등 운영 보조
├── docs/                      # 설계 · 배포 · 릴리즈 문서
├── data/                      # 원본 · 전처리 · 청크 (Git 제외)
└── chroma_db/                 # ChromaDB 로컬 저장소 (Git 제외)
```

---

## 환경 변수

`.env.example`을 복사해 `.env`를 만듭니다.

```powershell
Copy-Item .env.example .env
```

| 변수 | 설명 | 예시 |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API 키 (필수) | `sk-...` |
| `JWT_SECRET_KEY` | JWT 서명 시크릿 (필수, 운영 시 교체) | 임의 긴 문자열 |
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql+psycopg://legal_rag:pw@localhost:5432/legal_rag` |
| `CHROMA_PERSIST_DIRECTORY` | ChromaDB 저장 경로 | `./chroma_db` |
| `CHROMA_COLLECTION_NAME` | 법령 컬렉션 이름 | `legal_chunks_probe` |
| `PRECEDENT_CHROMA_COLLECTION_NAME` | 판례 컬렉션 이름 | `precedent_chunks_probe_10k` |
| `BACKEND_CORS_ORIGINS` | 허용 프론트엔드 주소 | `http://localhost:5173` |

---

## Docker로 실행

```powershell
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

| 서비스 | 주소 |
| --- | --- |
| 프론트엔드 | http://localhost:5173 |
| 백엔드 API 문서 | http://localhost:8000/docs |
| 헬스체크 | http://localhost:8000/api/v1/health |

> `chroma_db/` 디렉터리가 준비되어 있어야 RAG 답변이 동작합니다.

---

## 로컬 개발 실행

**Backend**

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Frontend**

```powershell
cd frontend
npm install
npm run dev
```

---

## 데이터 파이프라인

판례 정규화 → 청크 생성 → ChromaDB 색인 순서로 실행합니다.

**1. 판례 정규화**

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_precedents.py \
  --output data\processed\precedents\precedent_documents.sample.jsonl \
  --max-documents 1000
```

**2. 청크 생성**

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\chunk_precedents.py \
  --input  data\processed\precedents\precedent_documents.sample.jsonl \
  --output data\chunks\precedents\precedent_chunks.sample.jsonl
```

**3. ChromaDB 색인 (dry-run)**

```powershell
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py \
  --input          data\chunks\precedents\precedent_chunks.sample.jsonl \
  --collection-name precedent_chunks_probe \
  --dry-run
```

`--dry-run` 제거 시 실제 임베딩 · 색인을 실행합니다.

---

## 테스트

**Backend (pytest)**

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

**Frontend**

```powershell
cd frontend
npm run test -- --run
npm run build
```

**배포 Smoke Test**

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --with-rag --with-chat
```

`--with-rag`, `--with-chat`는 OpenAI API를 호출하므로 소량의 비용이 발생합니다.

**RAG 품질 평가**

```powershell
# 판례 검색 평가
.\.venv\Scripts\python.exe ai\rag\evaluate_precedent_retrieval.py \
  --collection-name precedent_chunks_probe_10k \
  --top-k 5 --use-keyword-boost \
  --output data\processed\precedents\precedent_retrieval_eval.probe_10k.hybrid.json

# 법률+판례 답변 평가
.\.venv\Scripts\python.exe ai\rag\evaluate_legal_assistant_answers.py \
  --top-k 5 \
  --output data\processed\precedents\legal_assistant_answer_eval.probe_10k.json
```

---

## 주요 API 엔드포인트

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | 회원가입 |
| POST | `/api/v1/auth/login` | 로그인 (access + refresh token 발급) |
| GET | `/api/v1/cases` | 사건 목록 |
| POST | `/api/v1/cases` | 사건 생성 |
| PATCH | `/api/v1/cases/{id}` | 사건 수정 |
| DELETE | `/api/v1/cases/{id}` | 사건 삭제 |
| GET | `/api/v1/cases/{id}/report` | 사건 보고서 Markdown 다운로드 |
| GET | `/api/v1/cases/tasks/upcoming` | 기한 임박 할 일 목록 |
| POST | `/api/v1/cases/{id}/attachments` | 첨부자료 업로드 |
| POST | `/api/v1/cases/{id}/attachments/{aid}/ocr` | 첨부자료 OCR 재실행 |
| POST | `/api/v1/chat/sessions/{id}/messages` | 채팅 메시지 전송 (동기) |
| POST | `/api/v1/chat/sessions/{id}/messages/stream` | 채팅 메시지 전송 (SSE 스트리밍) |
| GET | `/api/v1/search/personal` | 통합 워크스페이스 검색 |

전체 API 명세는 서버 실행 후 `/docs`에서 확인할 수 있습니다.

---

## 알려진 제한사항

- 법률 답변은 참고 정보이며 법률 자문이 아닙니다.
- ChromaDB 색인 파일은 Git에 포함되지 않으므로 배포 서버에 별도 업로드해야 합니다.
- 판례 컬렉션은 도메인별 균형 샘플 1만 건 기준입니다. 전체 판례 색인은 추가 비용과 시간이 필요합니다.
- RAG 데이터는 AI Hub 수집 기준일 이후 개정 법령 및 신규 판례를 포함하지 않습니다. 1~2년 주기로 AI Hub 새 버전 데이터를 받아 재인덱싱하는 방식을 권장합니다.
- PDF OCR은 최대 5페이지까지만 처리합니다.
- OpenAI API 장애 또는 rate limit 발생 시 RAG 답변 및 OCR 기능이 일시적으로 동작하지 않을 수 있습니다.

---

## Git에 포함하지 않는 항목

```gitignore
.env
.env.*
.claude/
.venv/
node_modules/
frontend/dist/
data/raw/
data/processed/
data/chunks/
chroma_db/
*.db
*.sqlite3
```

---

## 주요 문서

- [판례 검색 확장 설계](docs/case-law-rag-extension.md)
- [데이터 출처와 처리 흐름](docs/data-source.md)
- [배포 가이드](docs/deployment.md)
- [VPS + Docker Compose 배포 가이드](docs/vps-deployment.md)
- [Oracle Cloud Always Free 배포 가이드](docs/oracle-cloud-always-free.md)
- [릴리즈 체크리스트](docs/release-checklist.md)

---

## 라이선스

MIT
