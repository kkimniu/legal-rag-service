# Deployment Guide

이 문서는 `legal-rag-service`를 운영 환경에 올리기 전 확인해야 할 배포 조건과 절차를 정리합니다. 원본 데이터와 ChromaDB 색인 파일은 대용량 산출물이므로 Git과 Docker 이미지에 포함하지 않고, 서버 볼륨 또는 별도 스토리지로 관리합니다.

## 배포 구성

```text
Client Browser
  -> Frontend: React static build served by Nginx
  -> Backend: FastAPI
  -> PostgreSQL: user, chat, history data
  -> ChromaDB persistent directory: legal and precedent vector indexes
  -> OpenAI API: embeddings and answer generation
```

## 필수 운영 환경변수

Backend:

```env
APP_ENV=production
BACKEND_CORS_ORIGINS=https://your-frontend-domain.example
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB_NAME
JWT_SECRET_KEY=replace-with-long-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=14
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIRECTORY=/app/chroma_db
CHROMA_COLLECTION_NAME=legal_chunks_probe
PRECEDENT_CHROMA_COLLECTION_NAME=precedent_chunks_probe_10k
RAG_TOP_K=5
RAG_CONTEXT_MAX_CHARS=6000
OPENAI_TEMPERATURE=0.2
```

Frontend build arg:

```env
VITE_API_BASE_URL=https://your-backend-domain.example/api/v1
```

## Git/Docker에 포함하면 안 되는 항목

- `.env`, `.env.*`
- `data/raw/`
- `data/processed/`
- `data/chunks/`
- `chroma_db/`
- `frontend/dist/`
- `.venv/`, `node_modules/`
- `.claude/`

현재 `.gitignore`와 `.dockerignore`에서 위 항목을 제외합니다.

## ChromaDB 준비

현재 서비스 기준 컬렉션:

| 용도 | 컬렉션 |
| --- | --- |
| 법률/조문/QA 검색 | `legal_chunks_probe` |
| 판례 검색 | `precedent_chunks_probe_10k` |

서버에서는 `CHROMA_PERSIST_DIRECTORY`가 가리키는 경로에 로컬에서 생성한 `chroma_db` 디렉터리 내용을 올려야 합니다. 색인이 없는 상태로 실행하면 RAG 답변이 비거나 준비되지 않은 상태로 응답할 수 있습니다.

일반 서버 예시:

```powershell
scp -r chroma_db user@server:/app/chroma_db
```

Docker Compose 운영 예시:

```yaml
volumes:
  - /srv/legal-rag/chroma_db:/app/chroma_db
```

## PostgreSQL 준비

운영 DB는 컨테이너 내부 임시 DB가 아니라 관리형 PostgreSQL 또는 서버 볼륨 기반 PostgreSQL을 사용합니다.

배포 후 반드시 마이그레이션을 적용합니다.

```powershell
docker compose exec backend python -m alembic upgrade head
```

## Docker Compose 배포 절차

1. 서버에 `.env` 작성
2. `chroma_db` 디렉터리 업로드 또는 볼륨 연결
3. 이미지 빌드 및 실행

```powershell
docker compose up -d --build
```

4. DB 마이그레이션

```powershell
docker compose exec backend python -m alembic upgrade head
```

5. 상태 확인

```powershell
docker compose ps
docker compose logs backend --tail 100
```

## 배포 후 Smoke Test

Backend health:

```powershell
curl http://localhost:8000/api/v1/health
```

Automated API smoke test:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --with-rag --with-chat
```

이 명령은 회원가입, 로그인, 현재 사용자 조회, RAG 질문, RAG 히스토리 저장/삭제, 채팅 세션 생성, 채팅 답변의 법률/판례 근거 포함 여부를 확인합니다. `--with-rag`, `--with-chat` 옵션은 OpenAI API를 호출하므로 비용이 발생할 수 있습니다.

Swagger:

```text
http://localhost:8000/docs
```

Frontend:

```text
http://localhost:5173
```

권장 수동 테스트:

1. 회원가입
2. 로그인
3. 새 채팅 생성
4. 질문 입력

```text
상속한정승인과 상속포기에 관한 법률 근거와 판례를 같이 알려줘
```

확인 항목:

- 답변에 `답변 요약`, `관련 법령`, `관련 판례`, `주의사항`이 표시되는가
- 근거 카드에 `법률 근거`, `판례 근거`가 구분되는가
- 판례 근거에 사건번호가 표시되는가
- 새로고침 후 로그인 상태가 유지되는가

## 평가 명령

판례 검색 평가:

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_precedent_retrieval.py --collection-name precedent_chunks_probe_10k --top-k 5 --use-keyword-boost --output data\processed\precedents\precedent_retrieval_eval.probe_10k.hybrid.json
```

법률+판례 답변 평가:

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_legal_assistant_answers.py --top-k 5 --output data\processed\precedents\legal_assistant_answer_eval.probe_10k.json
```

현재 기준:

- 판례 검색 평가: 20/20 통과
- 법률+판례 답변 평가: 8/8 통과

## 배포 체크리스트

- [ ] `JWT_SECRET_KEY`를 운영용 긴 랜덤 문자열로 교체
- [ ] `OPENAI_API_KEY`를 서버 secret으로 등록
- [ ] `DATABASE_URL`이 운영 PostgreSQL을 가리키는지 확인
- [ ] `BACKEND_CORS_ORIGINS`가 실제 프론트 도메인과 일치하는지 확인
- [ ] `CHROMA_PERSIST_DIRECTORY`에 ChromaDB 데이터가 존재하는지 확인
- [ ] `CHROMA_COLLECTION_NAME=legal_chunks_probe`
- [ ] `PRECEDENT_CHROMA_COLLECTION_NAME=precedent_chunks_probe_10k`
- [ ] `alembic upgrade head` 적용
- [ ] `/api/v1/health` 정상 응답
- [ ] 회원가입/로그인/새 채팅/질문 답변 수동 테스트 완료

## 운영 주의사항

- 원본 AI Hub/판례 데이터는 서버 이미지에 포함하지 않습니다.
- ChromaDB는 재생성 가능한 산출물이지만 생성 비용과 시간이 있으므로 운영에서는 백업을 권장합니다.
- OpenAI API 장애 또는 rate limit에 대비해 색인 스크립트는 `--skip-existing`, `--max-retries` 옵션으로 재개할 수 있게 실행합니다.
- 법률 답변은 참고 정보로 제공되며, UI와 답변 모두 전문가 상담이 필요할 수 있음을 표시해야 합니다.
