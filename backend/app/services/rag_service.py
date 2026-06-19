from pathlib import Path
import re
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

    def answer(
        self,
        question: str,
        domain_code: str | None = None,
        chat_history: list[tuple[str, str]] | None = None,
        answer_mode: str = "general",
    ) -> RagAskResponse:
        """Retrieve legal/statute chunks and precedent chunks, then generate a grounded answer."""
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
            retrieval_question = self._build_retrieval_question(question, chat_history or [])
            sources = self._retrieve_sources(retrieval_question, question, persist_directory, domain_code)
        except Exception as exc:
            return RagAskResponse(
                answer=f"RAG 검색 중 오류가 발생했습니다: {exc}",
                sources=[],
                is_ready=False,
            )

        if not sources:
            return RagAskResponse(
                answer="질문과 관련된 법률 또는 판례 근거를 찾지 못했습니다.",
                sources=[],
                is_ready=True,
            )

        try:
            answer = self._generate_answer(
                question,
                sources,
                chat_history=chat_history,
                answer_mode=answer_mode,
            )
        except Exception as exc:
            return RagAskResponse(
                answer=f"근거는 찾았지만 답변 생성 중 오류가 발생했습니다: {exc}",
                sources=sources,
                is_ready=True,
            )

        return RagAskResponse(answer=answer, sources=sources, is_ready=True)

    def _build_retrieval_question(self, question: str, chat_history: list[tuple[str, str]]) -> str:
        """Expand short follow-up questions with recent user context for retrieval."""
        previous_user_turns = [
            content.strip()
            for role, content in chat_history
            if role == "user" and content.strip()
        ][-3:]
        if not previous_user_turns:
            return question

        history = "\n".join(f"- {turn[:300]}" for turn in previous_user_turns)
        return f"이전 사용자 질문 맥락:\n{history}\n\n현재 후속 질문:\n{question}"

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

    def _retrieve_sources(
        self,
        retrieval_question: str,
        original_question: str,
        persist_directory: Path,
        domain_code: str | None = None,
    ) -> list[RagSource]:
        client = chromadb.PersistentClient(path=str(persist_directory))
        embeddings = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
        query_embedding = embeddings.embed_query(retrieval_question)

        statute_sources = self._retrieve_collection_sources(
            client=client,
            collection_name=settings.chroma_collection_name,
            evidence_type="statute",
            query_embedding=query_embedding,
            question=original_question,
            domain_code=domain_code,
            n_results=self.top_k,
        )
        precedent_sources = self._retrieve_collection_sources(
            client=client,
            collection_name=settings.precedent_chroma_collection_name,
            evidence_type="precedent",
            query_embedding=query_embedding,
            question=original_question,
            domain_code=domain_code,
            n_results=self.top_k,
        )

        return self._merge_sources(statute_sources[: self.top_k], precedent_sources[: self.top_k])

    def _retrieve_collection_sources(
        self,
        client: Any,
        collection_name: str,
        evidence_type: str,
        query_embedding: list[float],
        question: str,
        domain_code: str | None,
        n_results: int,
    ) -> list[RagSource]:
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            return []

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if domain_code:
            query_kwargs["where"] = {"domain_code": domain_code}

        result = collection.query(**query_kwargs)
        sources = self._sources_from_result(result, evidence_type=evidence_type)

        keyword_sources = self._retrieve_keyword_sources(
            collection=collection,
            question=question,
            query_embedding=query_embedding,
            domain_code=domain_code,
            evidence_type=evidence_type,
        )
        if keyword_sources:
            sources = self._merge_sources(keyword_sources, sources)

        return sources[:n_results]

    def _retrieve_keyword_sources(
        self,
        collection: Any,
        question: str,
        query_embedding: list[float],
        domain_code: str | None,
        evidence_type: str,
    ) -> list[RagSource]:
        sources: list[RagSource] = []
        for keyword in self._extract_keywords(question):
            query_kwargs: dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": min(2, self.top_k),
                "where_document": {"$contains": keyword},
                "include": ["documents", "metadatas", "distances"],
            }
            if domain_code:
                query_kwargs["where"] = {"domain_code": domain_code}

            try:
                result = collection.query(**query_kwargs)
            except Exception:
                continue

            sources.extend(self._sources_from_result(result, evidence_type=evidence_type))
        return sources

    def _sources_from_result(self, result: dict[str, Any], evidence_type: str) -> list[RagSource]:
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]
        sources = []
        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            safe_metadata = self._safe_metadata(metadata)
            safe_metadata["evidence_type"] = evidence_type
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

    def _merge_sources(self, *source_groups: list[RagSource]) -> list[RagSource]:
        merged: list[RagSource] = []
        seen_ids: set[str] = set()
        for sources in source_groups:
            for source in sources:
                if source.id in seen_ids:
                    continue
                merged.append(source)
                seen_ids.add(source.id)
        return merged

    def _extract_keywords(self, question: str) -> list[str]:
        stopwords = {
            "어떤",
            "무엇",
            "무엇인가",
            "하나요",
            "필요한가",
            "확인해야",
            "하려면",
            "판단",
            "관련",
            "대해",
            "위해",
            "통해",
            "대한",
            "있나요",
            "되는",
        }
        particles = ("으로", "에서", "에게", "에는", "이라면", "라면", "인가요", "하나요", "가", "이", "을", "를", "은", "는", "의", "도")
        keywords: list[str] = []

        for token in re.findall(r"[0-9A-Za-z가-힣]+", question):
            normalized = token
            for particle in particles:
                if len(normalized) > len(particle) + 1 and normalized.endswith(particle):
                    normalized = normalized[: -len(particle)]
                    break

            candidates = [normalized]
            if normalized.endswith("죄") and len(normalized) > 2:
                candidates.append(normalized[:-1])

            for candidate in candidates:
                if len(candidate) < 2 or candidate in stopwords or candidate in keywords:
                    continue
                keywords.append(candidate)

        return keywords[:3]

    def _generate_answer(
        self,
        question: str,
        sources: list[RagSource],
        chat_history: list[tuple[str, str]] | None = None,
        answer_mode: str = "general",
    ) -> str:
        model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.openai_temperature,
        )
        context = self._format_context(sources)
        conversation_context = self._format_chat_history(chat_history or [])
        mode_instruction = self._answer_mode_instruction(answer_mode)
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "당신은 한국 법률 질의응답 서비스를 돕는 RAG 어시스턴트입니다. "
                        "반드시 제공된 법률 근거와 판례 근거 안에서만 답변하세요. "
                        "근거에 없는 법률요건, 판례 취지, 결론은 추측하지 말고 근거 부족을 명확히 말하세요. "
                        "답변은 아래 형식을 지키세요.\n\n"
                        "답변 요약\n"
                        "관련 법령\n"
                        "- 법령명: ...\n"
                        "- 조문/근거: ...\n"
                        "관련 판례\n"
                        "- 사건번호: ...\n"
                        "- 사건명: ...\n"
                        "- 판결요약: ...\n"
                        "주의사항"
                    )
                ),
                HumanMessage(
                    content=(
                        f"최근 대화\n{conversation_context}\n\n"
                        f"답변 모드\n{mode_instruction}\n\n"
                        f"질문:\n{question}\n\n"
                        f"검색된 근거:\n{context}\n\n"
                        "검색된 근거만 사용해서 한국어로 답변하세요. "
                        "관련 판례가 없으면 '검색된 판례 근거가 부족합니다'라고 쓰세요. "
                        "관련 법령이 없으면 '검색된 법령 근거가 부족합니다'라고 쓰세요."
                    )
                ),
            ]
        )
        answer = str(response.content).strip()
        disclaimer = "이 답변은 검색된 법률/판례 데이터에 기반한 참고 정보이며, 구체적인 사건에는 전문가 상담이 필요할 수 있습니다."
        has_notice = (
            "참고 정보" in answer
            or "전문가 상담" in answer
            or "법률 자문" in answer
        )
        if not has_notice:
            answer = f"{answer}\n\n{disclaimer}"
        return answer

    def _answer_mode_instruction(self, answer_mode: str) -> str:
        instructions = {
            "brief": (
                "간단 답변 모드입니다. 핵심 결론을 먼저 말하고 관련 법령과 판례는 가장 중요한 근거만 짧게 정리하세요. "
                "불필요한 배경 설명은 줄이세요."
            ),
            "detailed": (
                "상세 검토 모드입니다. 사실관계, 법령, 판례, 적용 가능성, 한계를 차례대로 설명하세요. "
                "근거가 부족한 부분은 명확히 구분하세요."
            ),
            "issue": (
                "쟁점 정리 모드입니다. 질문에서 문제되는 법적 쟁점을 항목별로 나누고, 각 쟁점마다 관련 법령과 판례를 연결하세요. "
                "마지막에 추가로 확인할 사실을 제안하세요."
            ),
            "consultation": (
                "상담 준비 모드입니다. 전문가 상담 전에 준비해야 할 자료, 확인 질문, 위험 요소를 중심으로 정리하세요. "
                "답변은 법률 자문이 아니라 상담 준비용 참고 정보임을 분명히 하세요."
            ),
            "general": "기본 답변 모드입니다. 질문에 직접 답하고 관련 법령과 판례를 균형 있게 정리하세요.",
        }
        return instructions.get(answer_mode, instructions["general"])

    def _format_chat_history(self, chat_history: list[tuple[str, str]]) -> str:
        if not chat_history:
            return "최근 대화 없음"

        lines = []
        for role, content in chat_history[-6:]:
            label = "사용자" if role == "user" else "AI"
            clipped = content.strip()[:500]
            if clipped:
                lines.append(f"{label}: {clipped}")
        return "\n".join(lines) or "최근 대화 없음"

    def _format_context(self, sources: list[RagSource]) -> str:
        chunks = []
        remaining_chars = settings.rag_context_max_chars

        for index, source in enumerate(sources, start=1):
            title = source.title or "제목 없음"
            domain = source.domain_name or "분야 미상"
            evidence_type = source.metadata.get("evidence_type")
            evidence_label = "판례" if evidence_type == "precedent" else "법률"
            case_number = source.metadata.get("meta_case_number") or source.metadata.get("case_number") or ""
            court = source.metadata.get("meta_court") or source.metadata.get("court") or ""
            decision_date = source.metadata.get("meta_decision_date") or source.metadata.get("decision_date") or ""
            text = source.text.strip()
            header = (
                f"[근거 {index}] 유형: {evidence_label} / 분야: {domain} / 제목: {title}"
                f" / 사건번호: {case_number} / 법원: {court} / 선고일자: {decision_date}\n"
            )
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
