from pathlib import Path
from typing import Any

import chromadb
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.schemas.rag import RagAskResponse, RagSource


class RagService:
    """Facade for retrieval and generation logic used by API routes."""

    def __init__(self, top_k: int | None = None) -> None:
        self.top_k = top_k or settings.rag_top_k

    def answer(self, question: str) -> RagAskResponse:
        """Retrieve legal chunks for a question and return a guarded response."""
        if not settings.openai_api_key or settings.openai_api_key.startswith("replace-"):
            return RagAskResponse(
                answer="OpenAI API 키가 아직 설정되지 않아 RAG 검색을 실행할 수 없습니다.",
                sources=[],
                is_ready=False,
            )

        persist_directory = self._resolve_chroma_directory()
        if persist_directory is None:
            return RagAskResponse(
                answer="ChromaDB 인덱스가 아직 생성되지 않았습니다. 샘플 또는 전체 chunk 색인을 먼저 생성하세요.",
                sources=[],
                is_ready=False,
            )

        try:
            sources = self._retrieve_sources(question, persist_directory)
        except Exception as exc:
            return RagAskResponse(
                answer=f"RAG 검색 중 오류가 발생했습니다: {exc}",
                sources=[],
                is_ready=False,
            )

        if not sources:
            return RagAskResponse(
                answer="질문과 관련된 법률 근거 chunk를 찾지 못했습니다.",
                sources=[],
                is_ready=True,
            )

        return RagAskResponse(
            answer="관련 법률 근거를 찾았습니다. 생성 답변 연결 전 단계이므로 sources를 우선 확인하세요.",
            sources=sources,
            is_ready=True,
        )

    def _resolve_chroma_directory(self) -> Path | None:
        candidates = [
            Path(settings.chroma_persist_directory),
            Path(__file__).resolve().parents[3] / settings.chroma_persist_directory,
            Path(__file__).resolve().parents[3] / "chroma_db",
        ]

        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.exists():
                return resolved
        return None

    def _retrieve_sources(self, question: str, persist_directory: Path) -> list[RagSource]:
        client = chromadb.PersistentClient(path=str(persist_directory))
        collection = client.get_collection(settings.chroma_collection_name)
        embeddings = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
        query_embedding = embeddings.embed_query(question)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=self.top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]

        sources = []
        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            safe_metadata = self._safe_metadata(metadata)
            sources.append(
                RagSource(
                    id=str(chunk_id),
                    title=self._optional_str(safe_metadata.get("title")),
                    domain_name=self._optional_str(safe_metadata.get("domain_name")),
                    source_type=self._optional_str(safe_metadata.get("source_type")),
                    text=str(text),
                    score=float(distance) if distance is not None else None,
                    metadata=safe_metadata,
                )
            )
        return sources

    def _safe_metadata(self, metadata: Any) -> dict[str, str | int | float | bool]:
        if not isinstance(metadata, dict):
            return {}
        return {
            str(key): value
            for key, value in metadata.items()
            if isinstance(value, (str, int, float, bool))
        }

    def _optional_str(self, value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)
