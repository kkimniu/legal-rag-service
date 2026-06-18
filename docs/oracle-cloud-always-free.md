# Oracle Cloud Always Free 배포 가이드

이 문서는 `legal-rag-service`를 Oracle Cloud Always Free의 Ampere A1 인스턴스에 배포하는 절차입니다.
목표는 비용을 최소화하면서 Docker Compose 기반 배포 경험을 얻는 것입니다.

Oracle Cloud Free Tier는 기간 제한이 있는 Free Trial과 만료되지 않는 Always Free 리소스로 구성됩니다.
가입할 때 홈 리전을 신중히 선택해야 하며, Always Free Compute 인스턴스는 홈 리전에서 생성해야 합니다.

## 1. 추천 구성

권장 인스턴스:

```text
Image: Ubuntu 22.04 또는 Ubuntu 24.04
Shape: VM.Standard.A1.Flex
OCPU: 2
Memory: 12GB
Boot volume: 50GB
Public IP: Ephemeral public IP
```

Oracle Ampere A1 Always Free 한도 안에서는 전체 tenancy 기준 최대 4 OCPU, 24GB 메모리까지 사용할 수 있습니다.
이 프로젝트는 처음에 2 OCPU, 12GB RAM으로 시작하고, 부족하면 나중에 4 OCPU, 24GB RAM까지 올리는 방식이 좋습니다.

## 2. Oracle Cloud에서 해야 할 일

1. Oracle Cloud 가입
2. 홈 리전 선택
3. Compute Instance 생성
4. SSH key 등록
5. Public IP 확인
6. Security List 또는 Network Security Group에서 포트 오픈

열어야 할 포트:

```text
22/tcp    SSH
80/tcp    Frontend
8000/tcp  Backend API, 초기 테스트용
```

나중에 도메인과 HTTPS를 붙이면 `8000`은 외부에 열지 않고, `80`/`443`만 열도록 바꾸는 것이 좋습니다.

## 3. 로컬 PC에서 SSH 접속

Windows PowerShell 기준:

```powershell
ssh -i C:\path\to\your-key.key ubuntu@YOUR_ORACLE_PUBLIC_IP
```

Oracle Linux 이미지를 선택했다면 사용자가 `opc`일 수 있습니다.

```powershell
ssh -i C:\path\to\your-key.key opc@YOUR_ORACLE_PUBLIC_IP
```

Ubuntu 이미지를 선택하면 보통 `ubuntu` 사용자를 씁니다.

## 4. 서버 기본 패키지 설치

서버에 접속한 뒤 실행합니다.

```bash
sudo apt update
sudo apt install -y ca-certificates curl git unzip
```

## 5. Docker 설치

Ubuntu 서버에서 실행합니다.

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

권한 적용을 위해 SSH를 끊었다가 다시 접속합니다.

```bash
exit
```

다시 접속 후 확인:

```bash
docker --version
docker compose version
```

## 6. 프로젝트 받기

서버에서 실행합니다.

```bash
sudo mkdir -p /srv/legal-rag
sudo chown -R $USER:$USER /srv/legal-rag
cd /srv/legal-rag
git clone https://github.com/kkimniu/legal-rag-service.git app
cd app
git checkout main
```

## 7. 운영 환경 변수 작성

```bash
cp .env.example .env
nano .env
```

최소 수정값:

```env
APP_ENV=production
BACKEND_CORS_ORIGINS=http://YOUR_ORACLE_PUBLIC_IP
JWT_SECRET_KEY=CHANGE_TO_LONG_RANDOM_SECRET

POSTGRES_DB=legal_rag
POSTGRES_USER=legal_rag
POSTGRES_PASSWORD=CHANGE_TO_STRONG_DB_PASSWORD

OPENAI_API_KEY=sk-...
CHROMA_COLLECTION_NAME=legal_chunks_probe
PRECEDENT_CHROMA_COLLECTION_NAME=precedent_chunks_probe_10k

CHROMA_HOST_PATH=/srv/legal-rag/chroma_db
BACKEND_HOST_PORT=8000
FRONTEND_HOST_PORT=80
VITE_API_BASE_URL=http://YOUR_ORACLE_PUBLIC_IP:8000/api/v1
```

저장:

```text
Ctrl + O
Enter
Ctrl + X
```

## 8. ChromaDB 업로드

로컬 PC PowerShell에서 실행합니다.

```powershell
scp -i C:\path\to\your-key.key -r chroma_db ubuntu@YOUR_ORACLE_PUBLIC_IP:/srv/legal-rag/chroma_db
```

서버에서 확인:

```bash
ls -la /srv/legal-rag/chroma_db
```

`chroma_db`는 Git에 올리지 않는 운영 데이터입니다. 서버 디스크에 따로 보관합니다.

## 9. Docker Compose 실행

서버에서 실행합니다.

```bash
cd /srv/legal-rag/app
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python -m alembic upgrade head
```

상태 확인:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs backend --tail 100
```

## 10. 접속 확인

브라우저에서 접속합니다.

```text
Frontend: http://YOUR_ORACLE_PUBLIC_IP
Backend Docs: http://YOUR_ORACLE_PUBLIC_IP:8000/docs
Health: http://YOUR_ORACLE_PUBLIC_IP:8000/api/v1/health
```

정상 확인 순서:

1. 회원가입
2. 로그인
3. 새 채팅 생성
4. 법률 질문 입력
5. 답변에 법령과 판례 근거가 함께 나오는지 확인
6. 새로고침 후 로그인 상태와 채팅 이력이 유지되는지 확인

## 11. 업데이트 배포

`main` 브랜치에 새 코드가 올라간 뒤 서버에서 실행합니다.

```bash
cd /srv/legal-rag/app
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python -m alembic upgrade head
```

## 12. 비용 방지 체크리스트

- Always Free 리소스인지 확인합니다.
- Ampere A1 전체 사용량을 4 OCPU, 24GB RAM 이하로 유지합니다.
- 유료 DB, Load Balancer, Object Storage 등을 실수로 추가하지 않습니다.
- Free Trial 크레딧으로 만든 유료 리소스가 남아 있지 않은지 확인합니다.
- 사용하지 않는 인스턴스와 볼륨은 삭제합니다.

## 13. 나중에 개선할 것

- 도메인 연결
- HTTPS 적용
- `8000` 포트 외부 노출 제거
- Caddy 또는 Nginx reverse proxy 추가
- PostgreSQL 백업 스크립트 추가
- `chroma_db` 백업 방식 정리
