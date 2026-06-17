# Release Checklist

`develop` 브랜치의 기능을 `main`으로 병합하기 전에 확인할 항목입니다. 이 체크리스트는 현재 법률+판례 RAG 챗봇 기능을 기준으로 합니다.

## 현재 포함된 주요 기능

- FastAPI 백엔드 기본 API
- React + TypeScript + Vite 프론트엔드
- JWT 로그인/회원가입
- refresh token 기반 로그인 유지
- PostgreSQL 기반 사용자/채팅/히스토리 저장
- ChromaDB 기반 법률 RAG 검색
- ChromaDB 기반 판례 RAG 검색
- 법률 컬렉션과 판례 컬렉션 분리 검색
- 챗봇형 멀티턴 대화
- 새 채팅 생성/조회/삭제
- 답변 재생성
- 답변 근거 표시
- 법률 근거/판례 근거 UI 구분
- 판례 사건번호 표시
- 판례 전처리/청크/임베딩 파이프라인
- 판례 검색 평가 스크립트
- 법률+판례 답변 평가 스크립트
- 배포 smoke test 스크립트

## 현재 기준 컬렉션

| 용도 | 컬렉션 |
| --- | --- |
| 법률/조문/QA 검색 | `legal_chunks_probe` |
| 판례 검색 | `precedent_chunks_probe_10k` |

## 로컬/Docker 실행 확인

```powershell
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

접속:

```text
Frontend: http://localhost:5173
Backend docs: http://localhost:8000/docs
Health: http://localhost:8000/api/v1/health
```

## 필수 수동 테스트

- [ ] 회원가입 가능
- [ ] 로그인 가능
- [ ] 새로고침 후 로그인 유지
- [ ] 새 채팅 생성 가능
- [ ] 채팅 목록 조회 가능
- [ ] 채팅 삭제 가능
- [ ] 질문 후 답변 생성
- [ ] 답변에 `답변 요약`, `관련 법령`, `관련 판례`, `주의사항` 표시
- [ ] 근거 펼치기 가능
- [ ] 법률 근거와 판례 근거 구분 표시
- [ ] 판례 근거에 사건번호 표시

권장 테스트 질문:

```text
상속한정승인과 상속포기에 관한 법률 근거와 판례를 같이 알려줘
```

## 자동 테스트

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

Smoke test:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --with-rag --with-chat
```

`--with-rag`, `--with-chat`는 OpenAI API를 호출하므로 비용이 발생할 수 있습니다.

## RAG 평가

판례 검색 평가:

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_precedent_retrieval.py --collection-name precedent_chunks_probe_10k --top-k 5 --use-keyword-boost --output data\processed\precedents\precedent_retrieval_eval.probe_10k.hybrid.json
```

법률+판례 답변 평가:

```powershell
.\.venv\Scripts\python.exe ai\rag\evaluate_legal_assistant_answers.py --top-k 5 --output data\processed\precedents\legal_assistant_answer_eval.probe_10k.json
```

현재 기록된 평가 결과:

- 판례 검색 평가: 20/20 통과
- 법률+판례 답변 평가: 8/8 통과

## GitHub에 올리면 안 되는 항목

아래 항목은 Git과 Docker 이미지에 포함하지 않습니다.

- `.env`
- `.env.*`
- `.claude/`
- `.venv/`
- `node_modules/`
- `frontend/dist/`
- `data/raw/`
- `data/processed/`
- `data/chunks/`
- `chroma_db/`
- `*.db`, `*.sqlite3`

확인 명령:

```powershell
git status --short
git check-ignore -v .env chroma_db\chroma.sqlite3 data\raw\precedents\incoming\Sublabel\1.판례\71므41.json
```

## 배포 전 확인

- [ ] 운영용 `JWT_SECRET_KEY` 설정
- [ ] 운영용 `OPENAI_API_KEY` secret 등록
- [ ] 운영 PostgreSQL `DATABASE_URL` 설정
- [ ] `BACKEND_CORS_ORIGINS`를 실제 프론트 도메인으로 설정
- [ ] `CHROMA_PERSIST_DIRECTORY`에 ChromaDB 데이터 업로드
- [ ] `CHROMA_COLLECTION_NAME=legal_chunks_probe`
- [ ] `PRECEDENT_CHROMA_COLLECTION_NAME=precedent_chunks_probe_10k`
- [ ] `alembic upgrade head` 적용
- [ ] 배포 후 smoke test 통과

## 알려진 제한사항

- 법률 답변은 참고 정보이며 법률 자문이 아닙니다.
- ChromaDB 색인 파일은 Git에 포함되지 않으므로 배포 서버에 별도 업로드해야 합니다.
- 판례 컬렉션은 현재 1만 건 균형 샘플 기준입니다. 전체 판례 색인은 비용과 시간이 더 필요합니다.
- 검색 품질은 도메인 필터와 키워드 보강을 함께 사용할 때 가장 안정적입니다.
- OpenAI API 장애나 rate limit이 발생할 수 있으므로 색인 스크립트는 `--skip-existing`, `--max-retries`로 재개하는 방식이 필요합니다.

## main 병합 절차

```powershell
git switch develop
git status
git pull origin develop

git switch main
git pull origin main
git merge develop
git push origin main
```

병합 후 GitHub에서 `main` 브랜치 README와 문서 링크가 정상 표시되는지 확인합니다.
