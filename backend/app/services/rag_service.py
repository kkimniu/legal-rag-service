from pathlib import Path
from typing import Any

import chromadb
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import settings
from app.schemas.rag import RagAskResponse, RagSource


class RagService:
    """Facade for retrieval and generation logic used by API routes."""

    def __init__(self, top_k: int | None = None) -> None:
        self.top_k = top_k or settings.rag_top_k

    def answer(self, question: str) -> RagAskResponse:
        """Retrieve legal chunks and generate a grounded Korean answer."""
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

        try:
            answer = self._generate_answer(question, sources)
        except Exception as exc:
            return RagAskResponse(
                answer=f"근거 chunk는 찾았지만 답변 생성 중 오류가 발생했습니다: {exc}",
                sources=sources,
                is_ready=True,
            )

        return RagAskResponse(answer=answer, sources=sources, is_ready=True)

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

    def _generate_answer(self, question: str, sources: list[RagSource]) -> str:
        model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.openai_temperature,
        )
        context = self._format_context(sources)
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "당신은 한국 법률 질의응답 서비스를 돕는 RAG 어시스턴트입니다. "
                        "반드시 제공된 근거 안에서만 답변하고, 근거에 없는 내용은 추측하지 마세요. "
                        "답변은 한국어로 작성하고, 법률 자문이 아니라 참고 정보라는 점을 간단히 밝혀주세요."
                    )
                ),
                HumanMessage(
                    content=(
                        f"질문:\n{question}\n\n"
                        f"검색된 근거:\n{context}\n\n"
                        "위 근거만 사용해 핵심 답변을 3~6문장으로 작성하세요. "
                        "가능하면 어떤 근거를 참고했는지 문장 안에 짧게 언급하세요."
                    )
                ),
            ]
        )
        answer = str(response.content).strip()
        disclaimer = "※ 이 답변은 검색된 법률 데이터에 기반한 참고 정보이며, 구체적인 사건에는 전문가 상담이 필요할 수 있습니다."
        has_notice = (
            "참고 정보" in answer
            or "참고정보" in answer
            or "법률 자문" in answer
            or "전문가 상담" in answer
        )
        if not has_notice:
            answer = f"{answer}\n\n{disclaimer}"
        return answer

    def _format_context(self, sources: list[RagSource]) -> str:
        chunks = []
        remaining_chars = settings.rag_context_max_chars

        for index, source in enumerate(sources, start=1):
            title = source.title or "제목 없음"
            domain = source.domain_name or "분야 미상"
            text = source.text.strip()
            header = f"[근거 {index}] 분야: {domain} / 제목: {title}\n"
            available = max(0, remaining_chars - len(header))
            if available <= 0:
                break

            clipped_text = text[:available]
            chunks.append(f"{header}{clipped_text}")
            remaining_chars -= len(header) + len(clipped_text)

            if remaining_chars <= 0:
                break

        return "\n\n".join(chunks)

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
