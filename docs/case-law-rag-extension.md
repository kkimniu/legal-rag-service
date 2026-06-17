# 판례 검색 확장 설계

## 목표

기존 AI Hub 법률 데이터 기반 RAG 챗봇을 법령 조문과 판례를 함께 검색하는 AI Legal Assistant로 확장한다. 현재 FastAPI, ChromaDB, PostgreSQL, React 챗봇 구조를 유지하고, 판례 데이터 파이프라인과 검색 계층을 별도로 추가한다.

## 데이터 저장 구조

```text
data/
  raw/
    statutes/                 법령 원본 데이터
    precedents/               판례 원본 데이터
  processed/
    statute_documents.*.jsonl  정규화된 법령 문서
    precedent_documents.*.jsonl 정규화된 판례 문서
  chunks/
    statute_chunks.*.jsonl     법령 검색 chunk
    precedent_chunks.*.jsonl   판례 검색 chunk
```

원본 판례 파일은 Git에 커밋하지 않는다. 전처리 산출물과 ChromaDB 저장소도 기존 정책처럼 Git 제외 대상으로 유지한다.

## 판례 문서 포맷

판례 전처리 산출물은 JSONL 한 줄당 하나의 판례 문서로 저장한다.

```json
{
  "id": "precedent:2023da12345",
  "source_type": "precedent",
  "court": "대법원",
  "case_number": "2023다12345",
  "case_name": "손해배상",
  "judgment_date": "2024-01-15",
  "case_type": "민사",
  "domain_code": "01_civil_law",
  "domain_name": "민사법",
  "title": "대법원 2024. 1. 15. 선고 2023다12345 판결",
  "summary": "계약 불이행과 손해배상 범위에 관한 판례",
  "holding": "채무불이행과 상당인과관계 있는 손해에 한해 배상책임을 인정한다.",
  "facts": "사안의 개요",
  "reasoning": "법원의 판단 이유",
  "content": "사건개요, 판결요지, 판단이유를 합친 검색용 본문",
  "metadata": {
    "source_path": "data/raw/precedents/...",
    "source_url": "https://...",
    "keywords": ["채무불이행", "손해배상", "상당인과관계"]
  }
}
```

## 판례 Chunk 포맷

```json
{
  "id": "precedent:2023da12345:chunk:0001",
  "document_id": "precedent:2023da12345",
  "chunk_index": 1,
  "source_type": "precedent",
  "text": "판결요지와 판단이유 일부",
  "domain_code": "01_civil_law",
  "domain_name": "민사법",
  "title": "대법원 2024. 1. 15. 선고 2023다12345 판결",
  "metadata": {
    "court": "대법원",
    "case_number": "2023다12345",
    "case_name": "손해배상",
    "judgment_date": "2024-01-15",
    "case_type": "민사",
    "chunk_size": 920
  }
}
```

## 판례 임베딩 파이프라인

```text
판례 원본 수집
-> ai/preprocessing/normalize_precedents.py
-> data/processed/precedent_documents.*.jsonl
-> ai/preprocessing/chunk_precedents.py
-> data/chunks/precedent_chunks.*.jsonl
-> ai/embeddings/build_chroma.py
-> ChromaDB precedent_chunks 컬렉션
```

권장 스크립트 구조:

```text
ai/preprocessing/
  normalize_precedents.py     판례 원본 정규화
  chunk_precedents.py         판례 chunk 생성

ai/embeddings/
  build_chroma.py             기존 스크립트 재사용

ai/rag/
  evaluate_precedent_retrieval.py
  evaluate_legal_assistant_answers.py
```

초기 실행 예시:

```powershell
.\.venv\Scripts\python.exe ai\preprocessing\normalize_precedents.py --input data\raw\precedents --output data\processed\precedent_documents.sample.jsonl --max-documents 1000
.\.venv\Scripts\python.exe ai\preprocessing\chunk_precedents.py --input data\processed\precedent_documents.sample.jsonl --output data\chunks\precedent_chunks.sample.jsonl
.\.venv\Scripts\python.exe ai\embeddings\build_chroma.py --input data\chunks\precedent_chunks.sample.jsonl --collection-name precedent_chunks_probe --reset-collection --skip-existing
```

## ChromaDB 컬렉션 구조

법령/법률 데이터와 판례 데이터는 컬렉션을 분리한다.

```text
statute_chunks_probe      법령/조문/기존 법률 QA chunk
precedent_chunks_probe    판례 chunk
legal_chunks_probe        현재 통합 법률 QA probe 컬렉션
```

실무형 확장에서는 아래 설정을 추가한다.

```env
STATUTE_CHROMA_COLLECTION_NAME=legal_chunks_probe
PRECEDENT_CHROMA_COLLECTION_NAME=precedent_chunks_probe
STATUTE_TOP_K=4
PRECEDENT_TOP_K=4
```

## RAG 검색 개선

현재 `RagService`는 하나의 Chroma 컬렉션을 검색한다. 확장 후에는 `LegalAssistantService`를 추가해 법령 컬렉션과 판례 컬렉션을 각각 검색한다.

```python
from dataclasses import dataclass


@dataclass
class RetrievedEvidence:
    id: str
    source_type: str
    title: str | None
    text: str
    score: float | None
    metadata: dict


class LegalAssistantService:
    def __init__(self, statute_top_k: int = 4, precedent_top_k: int = 4) -> None:
        self.statute_top_k = statute_top_k
        self.precedent_top_k = precedent_top_k

    def answer(self, question: str, domain_code: str | None = None) -> dict:
        statute_sources = self.retrieve_statutes(question, domain_code)
        precedent_sources = self.retrieve_precedents(question, domain_code)
        answer = self.generate_answer(question, statute_sources, precedent_sources)
        return {
            "answer": answer,
            "statutes": statute_sources,
            "precedents": precedent_sources,
        }

    def retrieve_statutes(self, question: str, domain_code: str | None) -> list[RetrievedEvidence]:
        # existing Chroma retrieval logic reused with STATUTE_CHROMA_COLLECTION_NAME
        raise NotImplementedError

    def retrieve_precedents(self, question: str, domain_code: str | None) -> list[RetrievedEvidence]:
        # same embedding query, but against PRECEDENT_CHROMA_COLLECTION_NAME
        raise NotImplementedError
```

## 답변 형식

답변 생성 프롬프트는 아래 구조를 강제한다.

```text
답변 요약
...

관련 법령
- 법령명:
- 조문:
- 관련 내용:

관련 판례
- 사건번호:
- 사건명:
- 판결요약:

주의사항
- 검색된 법령과 판례에 기반한 참고 정보입니다.
- 구체적 사건에는 전문가 검토가 필요할 수 있습니다.
```

프롬프트 핵심 규칙:

```text
- 법령 근거와 판례 근거를 구분해서 답변한다.
- 판례가 없으면 "검색된 판례 근거가 부족합니다"라고 말한다.
- 근거에 없는 법률요건이나 판례 취지는 추측하지 않는다.
- 사용자의 후속 질문은 최근 대화 맥락을 참고하되, 법률 내용은 검색 근거 안에서만 작성한다.
```

## FastAPI 수정 예시

새 endpoint를 기존 `/rag`와 분리해 `/legal-assistant/ask`로 둔다.

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_optional_current_user
from app.models.user import User
from app.services.legal_assistant_service import LegalAssistantService

router = APIRouter()


class LegalAssistantAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    domain_code: str | None = Field(default=None, pattern=r"^0[1-4]_[a-z_]+$")


@router.post("/ask")
def ask_legal_assistant(
    payload: LegalAssistantAskRequest,
    current_user: User | None = Depends(get_optional_current_user),
) -> dict:
    return LegalAssistantService().answer(
        question=payload.question,
        domain_code=payload.domain_code,
    )
```

라우터 등록:

```python
from app.api.v1.routes import legal_assistant

api_router.include_router(
    legal_assistant.router,
    prefix="/legal-assistant",
    tags=["legal-assistant"],
)
```

## SQLAlchemy 모델 설계

판례 원문 자체는 대용량 검색 데이터이므로 ChromaDB와 JSONL 파일에 둔다. PostgreSQL에는 사용자 상호작용과 참조 메타데이터만 저장한다.

```python
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PrecedentReference(Base):
    __tablename__ = "precedent_references"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_number: Mapped[str] = mapped_column(String(100), index=True)
    case_name: Mapped[str | None] = mapped_column(String(255))
    court: Mapped[str | None] = mapped_column(String(100), index=True)
    judgment_date: Mapped[str | None] = mapped_column(String(20), index=True)
    domain_code: Mapped[str | None] = mapped_column(String(80), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LegalAssistantQuery(Base):
    __tablename__ = "legal_assistant_queries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    statute_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    precedent_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
```

## 프로젝트 폴더 구조 제안

```text
backend/
  app/
    api/v1/routes/
      legal_assistant.py
    models/
      precedent.py
      legal_assistant_query.py
    schemas/
      legal_assistant.py
      precedent.py
    services/
      legal_assistant_service.py
      precedent_retriever.py
      statute_retriever.py

ai/
  preprocessing/
    normalize_precedents.py
    chunk_precedents.py
  embeddings/
    build_chroma.py
  rag/
    evaluate_precedent_retrieval.py
    evaluate_legal_assistant_answers.py

data/
  raw/
    statutes/
    precedents/
  processed/
  chunks/

docs/
  case-law-rag-extension.md
```

## 구현 순서

1. 판례 원본 데이터 위치 확정 및 `data/raw/precedents/README.md` 작성
2. `normalize_precedents.py` 구현
3. `chunk_precedents.py` 구현
4. `precedent_chunks_probe` Chroma 컬렉션 생성
5. `PrecedentRetriever`, `StatuteRetriever` 분리
6. `LegalAssistantService` 추가
7. `/legal-assistant/ask` API 추가
8. 챗봇 메시지 저장 구조에 `statute_sources`, `precedent_sources` 표시 확장
9. 답변 품질 평가 스크립트 추가

## README 추가용 요약

```md
## 판례 검색 확장

본 프로젝트는 법령/법률 QA 기반 RAG에서 판례 검색을 함께 사용하는 AI Legal Assistant로 확장할 수 있도록 설계되어 있습니다.

- 법령 컬렉션과 판례 컬렉션을 ChromaDB에서 분리
- 판례 원본, 전처리 문서, chunk 산출물을 별도 관리
- 답변 생성 시 관련 법령과 관련 판례를 구분하여 제시
- 사건번호, 사건명, 판결요약 등 판례 메타데이터 제공
- 기존 챗봇/인증/대화 저장 구조를 유지하면서 확장 가능
```
