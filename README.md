# legal-rag-service

AI Hub 법률 데이터 기반 RAG 법률 질의응답 챗봇 서비스입니다.  
멀티턴 대화, 분야별 검색 근거 제시, 답변 재생성을 지원합니다.

---

## 기술 스택

| 영역 | 사용 기술 |
|------|-----------|
| Backend | FastAPI, SQLAlchemy, PostgreSQL, Alembic, JWT |
| Frontend | React 19, TypeScript, Vite, Axios |
| AI / RAG | LangChain, OpenAI API, ChromaDB, tiktoken |
| Infra | Docker, Docker Compose, Nginx |

---

## 프로젝트 구조

```
backend/          FastAPI 백엔드 (API, 인증, RAG, 챗봇)
frontend/         React + TypeScript 프론트엔드
ai/
  preprocessing/  원본 데이터 정규화, 키워드 선별, 청킹
  embeddings/     OpenAI 임베딩 → ChromaDB 색인
  rag/            검색·답변 품질 평가 스크립트
data/
  raw/            AI Hub 원본 데이터 (Git 제외)
  processed/      전처리 JSONL 산출물 (Git 제외)
  chunks/         청크 JSONL 산출물 (Git 제외)
scripts/          스모크 테스트, 챗봇 답변 품질 평가
docs/             데이터 출처 문서
chroma_db/        ChromaDB 로컬 저장소 (Git 제외)
```

---

## 판례 검색 확장 설계

기존 법률 QA/조문 검색 기반 RAG를 법령과 판례를 함께 활용하는 AI Legal Assistant로 확장하는 설계를 포함합니다.

- 법령 컬렉션과 판례 컬렉션을 ChromaDB에서 분리
- 판례 원본, 전처리 문서, chunk 산출물을 별도 관리
- 사건번호, 사건명, 법원, 선고일, 판결요약 metadata 설계
- 답변 형식: 답변 요약, 관련 법령, 관련 판례, 주의사항
- 현재 FastAPI, SQLAlchemy, ChromaDB 구조를 유지하면서 확장

상세 설계는 [docs/case-law-rag-extension.md](docs/case-law-rag-extension.md)를 참고합니다.

main 병합 전 확인 항목은 [docs/release-checklist.md](docs/release-checklist.md)를 참고합니다.

---

## 판례 데이터 전처리

판례 원본은 `data/raw/precedents/incoming` 아래에 보관합니다. 원본은 삭제하거나 Git에 올리지 않고, 필요한 필드만 전처리해서 검색용 JSONL로 변환합니다.

```powershell
# 1. 판례 원본 JSON 정규화
.\.venv\Scripts\python.exe ai\preprocessing\normalize_precedents.py --output data\processed\precedents\precedent_documents.sample.jsonl --max-documents 1000

# 2. 판례 검색용 chunk 생성
.\.venv\Scripts\python.exe ai\preprocessing\chunk_precedents.py --input data\processed\precedents\precedent_documents.sample.jsonl --output data\chunks\precedents\precedent_chunks.sample.jsonl

# 3. 임베딩 전 dry-run 검증
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\precedents\precedent_chunks.sample.jsonl --collection-name precedent_chunks_probe --dry-run
```

지원하는 입력 폴더:

- `Sublabel`: 판례/행정심판 재결례 원문 메타데이터
- `Training`, `Validation`: AI Hub 판결문 라벨링 데이터
- `Other`: 판례 관련 QA 보조 데이터

현재 판례 검색용 1만 건 균형 샘플 컬렉션은 `precedent_chunks_probe_10k`입니다. 도메인별 2,500건씩 정규화했고, 판례 검색 평가 20개 질문에서 키워드 보강 기준 20/20을 통과했습니다.

법률+판례 답변 평가도 8개 질문 기준 8/8을 통과했습니다. 답변은 `답변 요약`, `관련 법령`, `관련 판례`, `주의사항` 형식을 따르도록 구성되어 있습니다.

---

## 로컬 개발 환경 설정

### 1. 환경 변수

```bash
cp .env.example .env
```

`.env`에서 반드시 채워야 하는 항목:

```env
OPENAI_API_KEY=sk-...          # OpenAI API 키
JWT_SECRET_KEY=랜덤-시크릿-키   # 32자 이상 임의 문자열
CHROMA_COLLECTION_NAME=legal_chunks_probe  # 사용할 컬렉션명
```

### 2. PostgreSQL 실행

```bash
docker-compose up -d db
```

### 3. 백엔드 실행

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 4. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:5173 접속

---

## 데이터 파이프라인 (ChromaDB 색인 구축)

챗봇이 동작하려면 ChromaDB 색인이 필요합니다.  
아래 순서로 원본 데이터 → 청크 → 임베딩 색인을 생성합니다.

```bash
# 1. 키워드 기반 문서 선별 (예: 행정법, 분야별 반복)
cd ai/preprocessing
python select_keyword_documents.py \
  --raw-dir ../../data/raw/aihub_legal \
  --domain-code 03_administrative_law \
  --keywords 행정처분 취소 위법 재량 \
  --output ../../data/processed/legal_documents.admin.jsonl

# 2. 청크 분할
python chunk_documents.py \
  --input ../../data/processed/legal_documents.admin.jsonl \
  --output ../../data/chunks/legal_chunks.admin.jsonl

# 3. OpenAI 임베딩 → ChromaDB 색인
cd ../embeddings
python build_chroma.py \
  --input ../../data/chunks/legal_chunks.admin.jsonl \
  --persist-dir ../../chroma_db \
  --collection-name legal_chunks_probe \
  --skip-existing
```

> `--skip-existing` 플래그를 사용하면 이미 색인된 청크는 건너뜁니다.  
> 현재 서비스는 `legal_chunks_probe` 컬렉션 (20,077개 청크)을 사용합니다.

---

## 테스트 및 평가

### 백엔드 유닛 테스트

```bash
cd backend
pytest tests/ -v
```

### API 스모크 테스트 (서버 실행 중)

```bash
python scripts/smoke_test.py --with-rag
```

### 챗봇 답변 품질 평가 (서버 실행 중)

4개 분야 × 2케이스 멀티턴 평가를 실행하고 `data/processed/chat_answer_eval.probe.json`에 저장합니다.

```bash
python scripts/eval_chat_answers.py
```

현재 평가 기준 통과율: **8/8 (100%)**

### 프론트엔드 테스트

```bash
cd frontend
npm test
```

---

## Docker Compose 배포 (로컬/서버)

운영 배포 환경변수, ChromaDB 볼륨, PostgreSQL 마이그레이션, smoke test 체크리스트는 [docs/deployment.md](docs/deployment.md)를 참고합니다.

전체 스택을 컨테이너로 실행합니다.

```bash
# 빌드 및 실행
docker-compose up -d --build

# 마이그레이션 적용
docker-compose exec backend alembic upgrade head
```

| 서비스 | 포트 | 설명 |
|--------|------|------|
| frontend | 5173 | React 앱 (Nginx) |
| backend | 8000 | FastAPI |
| db | 5432 | PostgreSQL 16 |

> `chroma_db/` 디렉터리를 사전에 구성해야 합니다. 색인 없이 실행하면 RAG 답변이 비어 있습니다.

---

## 클라우드 배포

### 전제 조건

클라우드 배포 시 아래 세 가지가 필요합니다.

1. **PostgreSQL** — 외부 관리형 DB (Railway, Supabase, AWS RDS 등)
2. **ChromaDB 데이터** — 로컬에서 구축 후 서버에 전송하거나 볼륨으로 마운트
3. **환경 변수** — `OPENAI_API_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL` 등

---

### 옵션 A: Fly.io (권장)

Docker 기반 배포, 퍼시스턴트 볼륨 지원, 무료 티어 있음.

```bash
# Fly CLI 설치
# https://fly.io/docs/hands-on/install-flyctl/

# 로그인 및 앱 생성
fly auth login
fly launch --no-deploy

# ChromaDB용 볼륨 생성
fly volumes create chroma_data --size 5

# PostgreSQL 생성
fly postgres create --name legal-rag-db
fly postgres attach legal-rag-db

# 시크릿 설정
fly secrets set OPENAI_API_KEY=sk-...
fly secrets set JWT_SECRET_KEY=랜덤-32자
fly secrets set CHROMA_COLLECTION_NAME=legal_chunks_probe

# ChromaDB 데이터 업로드 (로컬 → 볼륨)
fly ssh sftp shell
# 또는 fly deploy 전에 chroma_db/ 디렉터리를 이미지에 포함

# 배포
fly deploy
fly ssh console -C "cd /app/backend && alembic upgrade head"
```

`fly.toml` 예시:

```toml
[mounts]
  source = "chroma_data"
  destination = "/app/chroma_db"

[env]
  APP_ENV = "production"
  CHROMA_PERSIST_DIRECTORY = "/app/chroma_db"
```

---

### 옵션 B: Railway

GitHub 연동 자동 배포, PostgreSQL 플러그인 내장.

1. [railway.app](https://railway.app) → New Project → GitHub 연결
2. PostgreSQL 플러그인 추가 → `DATABASE_URL` 자동 주입
3. 환경 변수 추가: `OPENAI_API_KEY`, `JWT_SECRET_KEY`, `CHROMA_COLLECTION_NAME`
4. 볼륨 마운트 설정: `/app/chroma_db` (Railway 볼륨 기능 필요)
5. Deploy

> ChromaDB 데이터를 미리 서버에 올려야 합니다. Docker 이미지에 포함하거나 볼륨을 사전 채우는 방식을 사용하세요.

---

### 옵션 C: Render

```yaml
# render.yaml
services:
  - type: web
    name: legal-rag-backend
    runtime: docker
    dockerfilePath: backend/Dockerfile
    disk:
      name: chroma
      mountPath: /app/chroma_db
      sizeGB: 5
    envVars:
      - key: OPENAI_API_KEY
        sync: false
      - key: JWT_SECRET_KEY
        sync: false
      - key: DATABASE_URL
        fromDatabase:
          name: legal-rag-db
          property: connectionString
```

---

### ChromaDB 데이터 클라우드 전송 방법

클라우드 볼륨이 준비된 뒤, 로컬의 `chroma_db/`를 아래 방법으로 전송합니다.

```bash
# Fly.io의 경우
fly ssh sftp put chroma_db/ /app/chroma_db/

# 일반 서버(SCP)의 경우
scp -r chroma_db/ user@server:/app/chroma_db/

# rsync
rsync -avz chroma_db/ user@server:/app/chroma_db/
```

---

## API 엔드포인트

`http://localhost:8000/docs` 에서 Swagger UI를 확인할 수 있습니다.

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/auth/register` | 회원가입 |
| POST | `/api/v1/auth/login` | 로그인 (JWT 발급) |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 |
| GET | `/api/v1/auth/me` | 현재 사용자 조회 |
| POST | `/api/v1/chat/sessions` | 대화 세션 생성 |
| GET | `/api/v1/chat/sessions` | 대화 목록 조회 |
| POST | `/api/v1/chat/sessions/{id}/messages` | 메시지 전송 (RAG 답변 생성) |
| GET | `/api/v1/chat/sessions/{id}/messages` | 대화 메시지 조회 |
| DELETE | `/api/v1/chat/sessions/{id}` | 대화 삭제 |
| POST | `/api/v1/rag/ask` | 단건 RAG 질의 (평가 스크립트용) |
| GET | `/api/v1/health` | 서버 상태 확인 |

---

## 주요 기능

- **멀티턴 대화**: 같은 세션 내 이전 Q&A를 맥락으로 반영
- **분야 고정**: 세션별 법 분야 고정 (민사법 / 지식재산권법 / 행정법 / 형사법)
- **검색 근거 표시**: 답변 아래 참조 문서 출처 펼치기/접기
- **답변 재생성**: 마지막 질문을 다시 보내 새 답변 생성
- **Refresh Token**: 자동 로그인 유지 (14일)
- **답변 품질 평가**: 분야별 멀티턴 자동 평가 스크립트

---

## 라이선스

MIT
