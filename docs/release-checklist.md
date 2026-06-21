# Release Checklist

`develop` 브랜치의 기능을 `main`으로 병합하기 전에 확인할 항목입니다.

## 포함된 주요 기능

### 인증
- JWT access token + refresh token 로그인 유지
- 회원가입 / 로그인 / 로그아웃

### 사건 관리
- 사건 생성 · 제목 · 요약 편집 · 삭제 (확인 다이얼로그)
- 사건 상태 관리 (진행중 / 관찰중 / 종료) · 필터 · 검색
- 사건별 AI Insight (요약 · 쟁점 · 다음 할 일)
- 사건 보고서 Markdown 내보내기

### 메모 & 할 일
- 사건별 메모 작성 · 수정 · 삭제
- 사건별 할 일 · 기한 · 완료 상태 관리
- 기한 알림 센터 (기한 초과 / 오늘 / 7일 이내 / 30일 이내)
- 로그인 시 기한 초과·오늘 마감 경고 배너

### 첨부자료
- PDF · DOCX · 텍스트 · 이미지 파일 업로드
- 텍스트 자동 추출 (실패 시 OCR 자동 전환)
- 스캔 문서 OCR (OpenAI Vision API + PyMuPDF)
- ChromaDB 색인 · 원본 다운로드

### 채팅 & RAG 답변
- 멀티턴 대화 · 사건 연결 · 고정 · 삭제
- 실시간 스트리밍 응답 (SSE)
- 답변 모드 5종 · 근거 표시 · 재생성
- 답변 내 법령·판례 자동 하이퍼링크

### 검색 & 타임라인
- 사건·메모·할 일·첨부자료·채팅 통합 검색 (유형 필터 · 하이라이팅)
- 사건별 활동 타임라인

## RAG 컬렉션

| 컬렉션 | 청크 수 |
| --- | --- |
| `legal_chunks_probe` | 101,385 |
| `precedent_chunks_probe_10k` | 73,414 |

## 자동 테스트

```powershell
# Backend (48개 테스트)
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q

# Frontend
cd frontend
npm.cmd run test -- --run
npm.cmd run build

# Smoke test
.\.venv\Scripts\python.exe scripts\smoke_test.py --with-rag --with-chat
```

## Docker 실행 확인

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

### 인증
- [ ] 회원가입 가능
- [ ] 로그인 가능
- [ ] 새로고침 후 로그인 유지

### 사건 관리
- [ ] 사건 생성 가능
- [ ] 사건 제목·요약 편집 모달 동작
- [ ] 사건 삭제 확인 다이얼로그 동작
- [ ] 사건 상태 필터 동작

### 기한 알림
- [ ] 기한 초과 항목이 경고 배너에 표시
- [ ] 기한 알림 센터에서 4개 그룹 구분 표시

### 채팅 & 스트리밍
- [ ] 질문 전송 시 세 점 애니메이션 → 토큰 스트리밍으로 전환
- [ ] 답변에 `답변 요약` `관련 법령` `관련 판례` `주의사항` 표시
- [ ] 근거 펼치기 동작
- [ ] 법령·판례 자동 링크 클릭 시 외부 사이트 이동
- [ ] 답변 재생성 스트리밍 동작

### 첨부자료 & OCR
- [ ] PDF 업로드 후 텍스트 추출 완료
- [ ] 이미지 파일 업로드 후 OCR 버튼 표시
- [ ] OCR 실행 후 추출 상태 `completed` 전환
- [ ] 파일 다운로드 동작

### 검색
- [ ] 키워드 검색 결과 하이라이팅 표시
- [ ] 유형 필터 전환 후 결과 변경 확인
- [ ] 더 보기 동작

### 보고서 내보내기
- [ ] 사건 보고서 `.md` 파일 다운로드

권장 테스트 질문:

```text
전세 보증금을 돌려받지 못한 경우 법적으로 어떻게 대응할 수 있나요?
```

## 배포 전 확인

- [ ] 운영용 `JWT_SECRET_KEY` 설정
- [ ] 운영용 `OPENAI_API_KEY` secret 등록
- [ ] 운영 PostgreSQL `DATABASE_URL` 설정
- [ ] `BACKEND_CORS_ORIGINS`를 실제 프론트 도메인으로 설정
- [ ] `CHROMA_PERSIST_DIRECTORY`에 ChromaDB 데이터 업로드
- [ ] `alembic upgrade head` 적용
- [ ] 배포 후 smoke test 통과

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

병합 후 GitHub에서 `main` 브랜치 README가 정상 표시되는지 확인합니다.

## GitHub에 올리면 안 되는 항목

- `.env`, `.env.*`
- `.claude/`
- `.venv/`
- `node_modules/`
- `frontend/dist/`
- `data/raw/`, `data/processed/`, `data/chunks/`
- `chroma_db/`
- `*.db`, `*.sqlite3`
