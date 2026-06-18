# VPS + Docker Compose 배포 가이드

이 문서는 `legal-rag-service`를 단일 VPS에 Docker Compose로 배포하는 기준 절차입니다.
PostgreSQL은 Compose 내부 컨테이너를 사용하고, ChromaDB 색인 파일은 VPS의 호스트 디렉터리에 보관합니다.

## 1. VPS 준비

권장 사양:

- Ubuntu 22.04 LTS 이상
- 2 vCPU 이상
- RAM 4GB 이상
- 디스크 40GB 이상
- Docker, Docker Compose Plugin, Git 설치

서버 기본 준비 예시:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 2. 프로젝트 배치

```bash
sudo mkdir -p /srv/legal-rag
sudo chown -R $USER:$USER /srv/legal-rag
cd /srv/legal-rag
git clone https://github.com/kkimniu/legal-rag-service.git app
cd app
git checkout main
```

## 3. 운영 환경 변수 작성

서버에서 `.env`를 직접 생성합니다. 실제 비밀값은 Git에 올리지 않습니다.

```bash
cp .env.example .env
nano .env
```

운영 기준 예시:

```env
APP_ENV=production
APP_NAME=legal-rag-service
API_V1_PREFIX=/api/v1

BACKEND_CORS_ORIGINS=http://YOUR_SERVER_IP
JWT_SECRET_KEY=CHANGE_TO_LONG_RANDOM_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=14

POSTGRES_DB=legal_rag
POSTGRES_USER=legal_rag
POSTGRES_PASSWORD=CHANGE_TO_STRONG_DB_PASSWORD

OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_COLLECTION_NAME=legal_chunks_probe
PRECEDENT_CHROMA_COLLECTION_NAME=precedent_chunks_probe_10k
RAG_TOP_K=5
RAG_CONTEXT_MAX_CHARS=6000
OPENAI_TEMPERATURE=0.2

CHROMA_HOST_PATH=/srv/legal-rag/chroma_db
BACKEND_HOST_PORT=8000
FRONTEND_HOST_PORT=80
VITE_API_BASE_URL=http://YOUR_SERVER_IP:8000/api/v1
```

도메인과 HTTPS를 붙인 뒤에는 아래처럼 바꿉니다.

```env
BACKEND_CORS_ORIGINS=https://YOUR_DOMAIN
VITE_API_BASE_URL=https://YOUR_DOMAIN/api/v1
```

## 4. ChromaDB 색인 업로드

로컬에서 이미 생성한 `chroma_db`를 VPS의 `/srv/legal-rag/chroma_db`로 업로드합니다.

로컬 PC에서 실행:

```bash
scp -r chroma_db user@YOUR_SERVER_IP:/srv/legal-rag/chroma_db
```

서버에서 확인:

```bash
ls -la /srv/legal-rag/chroma_db
```

이 디렉터리에는 법률 컬렉션 `legal_chunks_probe`와 판례 컬렉션 `precedent_chunks_probe_10k`가 들어 있어야 합니다.

## 5. 빌드 및 실행

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python -m alembic upgrade head
```

상태 확인:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs backend --tail 100
docker compose -f docker-compose.prod.yml logs frontend --tail 100
```

## 6. 접속 확인

브라우저:

```text
Frontend: http://YOUR_SERVER_IP
Backend Docs: http://YOUR_SERVER_IP:8000/docs
Health: http://YOUR_SERVER_IP:8000/api/v1/health
```

서버 또는 로컬에서 API 확인:

```bash
curl http://YOUR_SERVER_IP:8000/api/v1/health
```

## 7. 배포 후 필수 점검

- 회원가입이 되는지 확인합니다.
- 로그인 후 새로고침해도 refresh token으로 로그인 상태가 유지되는지 확인합니다.
- 새 채팅 생성 후 질문과 답변이 누적되는지 확인합니다.
- 답변에 `답변 요약`, `관련 법령`, `관련 판례`, `주의사항` 섹션이 나오는지 확인합니다.
- 근거 카드에서 법률 근거와 판례 근거가 구분되는지 확인합니다.

## 8. 업데이트 배포

새 코드가 `main`에 올라간 뒤 서버에서 실행합니다.

```bash
cd /srv/legal-rag/app
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python -m alembic upgrade head
docker compose -f docker-compose.prod.yml ps
```

## 9. 운영 주의사항

- `.env`, `data/`, `chroma_db/`는 Git에 올리지 않습니다.
- `chroma_db`는 재생성 비용이 있으므로 VPS에서 주기적으로 백업합니다.
- PostgreSQL 볼륨도 정기적으로 백업합니다.
- 서버 방화벽에서는 처음에는 `80`, `8000`, `22`만 열어둡니다.
- 실제 운영 도메인을 붙일 때는 Nginx Proxy Manager, Caddy, 또는 호스트 Nginx로 HTTPS reverse proxy를 구성하는 것이 좋습니다.
