from pathlib import Path
import re
from typing import Any

import chromadb
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import settings
from app.schemas.rag import RagAskResponse, RagSource


# 법률 동의어/유사어 사전 — 질문에서 핵심어가 감지되면 검색 쿼리에 관련 용어를 추가해
# 같은 색인 안에서도 더 많은 관련 청크를 회수한다.
_LEGAL_SYNONYMS: dict[str, list[str]] = {
    # 임대차·주거
    "전세": ["전세", "임대차", "임차인", "임대인", "주택임대차보호법", "전세금", "보증금"],
    "월세": ["월세", "임대차", "임차인", "차임", "보증금"],
    "임대차": ["임대차", "전세", "월세", "임차인", "임대인", "보증금", "주택임대차보호법"],
    "전세사기": ["전세사기", "임대차", "사기", "주택임대차보호법", "임차권등기", "보증금반환"],
    "임차인": ["임차인", "세입자", "임대차", "보증금"],
    "임대인": ["임대인", "집주인", "임대차", "보증금반환"],
    "보증금": ["보증금", "임대차", "전세금", "반환청구", "주택임대차보호법"],
    "명도": ["명도", "명도소송", "퇴거", "임대차", "점유"],
    # 계약
    "계약해지": ["계약해지", "해지", "계약해제", "손해배상", "위약금"],
    "계약해제": ["계약해제", "해제", "원상회복", "손해배상", "민법"],
    "위약금": ["위약금", "손해배상", "계약해지", "위약벌"],
    "대여금": ["대여금", "대출", "차용", "변제", "금전소비대차"],
    # 노동
    "해고": ["해고", "부당해고", "해고예고", "근로기준법", "해고수당"],
    "부당해고": ["부당해고", "해고", "근로기준법", "복직", "노동위원회"],
    "임금": ["임금", "급여", "임금체불", "최저임금", "근로기준법"],
    "퇴직금": ["퇴직금", "퇴직급여", "근로자퇴직급여보장법"],
    "산재": ["산재", "산업재해", "업무상재해", "근로복지공단", "산업재해보상보험법"],
    "근로계약": ["근로계약", "근로기준법", "계약직", "기간제", "파견"],
    # 손해배상
    "손해배상": ["손해배상", "배상", "불법행위", "위자료", "민법 제750조"],
    "교통사고": ["교통사고", "손해배상", "자동차손해배상보장법", "보험", "과실비율"],
    "의료사고": ["의료사고", "의료과실", "손해배상", "의료분쟁"],
    # 형사
    "사기": ["사기", "사기죄", "형법 제347조", "편취", "기망"],
    "폭행": ["폭행", "폭행죄", "형법 제260조", "상해", "상해죄"],
    "협박": ["협박", "협박죄", "형법 제283조", "공갈"],
    "명예훼손": ["명예훼손", "형법 제307조", "모욕", "사이버명예훼손"],
    "스토킹": ["스토킹", "스토킹처벌법", "접근금지", "피해자보호명령"],
    "절도": ["절도", "절도죄", "형법 제329조", "절취", "재물"],
    # 가족법
    "이혼": ["이혼", "협의이혼", "재판이혼", "위자료", "재산분할", "양육권"],
    "양육비": ["양육비", "이혼", "양육권", "친권", "가정법원"],
    "상속": ["상속", "상속인", "상속포기", "한정승인", "유언", "민법"],
    "한정승인": ["한정승인", "상속포기", "상속", "채무초과", "민법"],
    "상속포기": ["상속포기", "한정승인", "상속", "가정법원", "민법"],
    "유언": ["유언", "유언장", "상속", "유증", "유언집행자"],
    # 소비자·행정
    "환불": ["환불", "청약철회", "소비자보호법", "전자상거래법", "반품"],
    "개인정보": ["개인정보", "개인정보보호법", "정보통신망법", "개인정보침해"],
    "행정심판": ["행정심판", "행정소송", "취소소송", "행정처분"],
    "과태료": ["과태료", "행정처분", "행정법", "이의신청"],
}


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
        case_context: str | None = None,
        case_id: int | None = None,
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
            retrieval_question = self._build_retrieval_question(question, chat_history or [], case_context=case_context)
            sources = self._retrieve_sources(
                retrieval_question,
                question,
                persist_directory,
                domain_code,
                case_id=case_id,
            )
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
                evidence_status="none",
                evidence_warnings=["검색된 법령 또는 판례 근거가 없습니다."],
            )

        reliable_sources, evidence_status, evidence_warnings = self._assess_sources(sources)
        if not reliable_sources:
            return RagAskResponse(
                answer=self._insufficient_evidence_answer(evidence_warnings),
                sources=sources,
                is_ready=True,
                evidence_status=evidence_status,
                evidence_warnings=evidence_warnings,
            )

        try:
            answer = self._generate_answer(
                question,
                reliable_sources,
                chat_history=chat_history,
                answer_mode=answer_mode,
                evidence_warnings=evidence_warnings,
                case_context=case_context,
            )
        except Exception as exc:
            return RagAskResponse(
                answer=f"근거는 찾았지만 답변 생성 중 오류가 발생했습니다: {exc}",
                sources=reliable_sources,
                is_ready=True,
                evidence_status=evidence_status,
                evidence_warnings=evidence_warnings,
            )

        return RagAskResponse(
            answer=answer,
            sources=reliable_sources,
            is_ready=True,
            evidence_status=evidence_status,
            evidence_warnings=evidence_warnings,
        )

    def _expand_query(self, question: str, keywords: list[str]) -> list[str]:
        """키워드에 매칭되는 법률 동의어를 모아 확장 검색어 목록을 반환한다.
        정확한 키를 우선 매칭하고, 없으면 부분 일치로 폴백한다."""
        expanded: list[str] = []
        seen: set[str] = set()
        for keyword in keywords:
            if keyword in _LEGAL_SYNONYMS:
                matched_synonyms = _LEGAL_SYNONYMS[keyword]
            else:
                matched_synonyms = next(
                    (synonyms for key, synonyms in _LEGAL_SYNONYMS.items()
                     if keyword in key or key in keyword),
                    [],
                )
            for term in matched_synonyms:
                if term not in seen:
                    expanded.append(term)
                    seen.add(term)
        return expanded

    def _build_retrieval_question(
        self,
        question: str,
        chat_history: list[tuple[str, str]],
        case_context: str | None = None,
    ) -> str:
        """질문을 법률 동의어로 확장하고 최근 대화 맥락을 합쳐 검색 쿼리를 구성한다."""
        previous_user_turns = [
            content.strip()
            for role, content in chat_history
            if role == "user" and content.strip()
        ][-3:]

        keywords = self._extract_keywords(question)
        expanded_terms = self._expand_query(question, keywords)

        sections = []
        if case_context and case_context.strip():
            sections.append(f"개인 사건 메모:\n{case_context.strip()[:1000]}")

        if previous_user_turns:
            history = "\n".join(f"- {turn[:300]}" for turn in previous_user_turns)
            sections.append(f"이전 사용자 질문 맥락:\n{history}")

        sections.append(f"현재 질문:\n{question}")

        if expanded_terms:
            sections.append(f"관련 법률 용어:\n{' '.join(expanded_terms[:15])}")

        return "\n\n".join(sections)

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
        case_id: int | None = None,
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

        attachment_sources = self._retrieve_case_attachment_sources(
            client=client,
            query_embedding=query_embedding,
            case_id=case_id,
        )

        return self._merge_sources(
            statute_sources[: self.top_k],
            precedent_sources[: self.top_k],
            attachment_sources[: self.top_k],
        )

    def _retrieve_case_attachment_sources(
        self,
        client: Any,
        query_embedding: list[float],
        case_id: int | None,
    ) -> list[RagSource]:
        if case_id is None:
            return []
        try:
            collection = client.get_collection(settings.case_attachment_collection_name)
            result = collection.query(
                query_embeddings=[query_embedding],
                n_results=self.top_k,
                where={"case_id": case_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []
        return self._sources_from_result(result, evidence_type="case_attachment")

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
        keywords = self._extract_keywords(question)
        expanded = self._expand_query(question, keywords)
        # 원본 키워드 우선, 확장 용어를 뒤에 추가해 검색 대상을 넓힌다.
        search_terms = keywords + [t for t in expanded if t not in keywords]

        for term in search_terms[:8]:
            query_kwargs: dict[str, Any] = {
                "query_embeddings": [query_embedding],
                "n_results": min(3, self.top_k),
                "where_document": {"$contains": term},
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

    def _assess_sources(self, sources: list[RagSource]) -> tuple[list[RagSource], str, list[str]]:
        reliable_sources = [source for source in sources if self._is_reliable_source(source)]
        has_statute = any(source.metadata.get("evidence_type") == "statute" for source in reliable_sources)
        has_precedent = any(source.metadata.get("evidence_type") == "precedent" for source in reliable_sources)

        warnings: list[str] = []
        weak_count = len(sources) - len(reliable_sources)
        if weak_count > 0:
            warnings.append(f"관련성이 낮은 검색 근거 {weak_count}개를 답변 생성에서 제외했습니다.")
        if not has_statute:
            warnings.append("신뢰 가능한 법령 근거가 부족합니다.")
        if not has_precedent:
            warnings.append("신뢰 가능한 판례 근거가 부족합니다.")
        if len(reliable_sources) < settings.rag_min_reliable_sources:
            warnings.append("답변을 생성하기에 충분한 관련 근거가 없습니다.")

        if not reliable_sources:
            return [], "insufficient", warnings
        if warnings:
            return reliable_sources, "partial", warnings
        return reliable_sources, "sufficient", []

    def _is_reliable_source(self, source: RagSource) -> bool:
        if source.score is None:
            return True
        return source.score <= settings.rag_max_source_distance

    def _insufficient_evidence_answer(self, warnings: list[str]) -> str:
        warning_lines = "\n".join(f"- {warning}" for warning in warnings)
        return (
            "답변 요약\n"
            "검색된 근거의 관련성이 낮아 현재 질문에 대해 근거 기반 답변을 생성하기 어렵습니다.\n\n"
            "관련 법령\n"
            "- 검색된 법령 근거가 부족합니다.\n\n"
            "관련 판례\n"
            "- 검색된 판례 근거가 부족합니다.\n\n"
            "주의사항\n"
            f"{warning_lines}\n"
            "- 질문의 사실관계, 분야, 사건 유형, 계약/처분/판결 관련 정보를 더 구체화한 뒤 다시 질문해 주세요.\n"
            "- 이 답변은 검색된 법률/판례 데이터에 기반한 참고 정보이며, 구체적인 사건에는 전문가 상담이 필요할 수 있습니다."
        )

    def _extract_keywords(self, question: str) -> list[str]:
        stopwords = {
            "어떤", "무엇", "무엇인가", "하나요", "필요한가", "확인해야",
            "하려면", "판단", "관련", "대해", "위해", "통해", "대한",
            "있나요", "되는", "경우", "때문", "어떻게", "알고싶어",
            "알려줘", "알려주세요", "궁금해", "궁금합니다", "설명",
        }
        particles = (
            "으로", "에서", "에게", "에는", "이라면", "라면", "인가요",
            "하나요", "가", "이", "을", "를", "은", "는", "의", "도",
            "에서의", "으로의", "에의", "과", "와", "로", "으로",
        )
        keywords: list[str] = []

        for token in re.findall(r"[0-9A-Za-z가-힣]+", question):
            normalized = token
            for particle in particles:
                if len(normalized) > len(particle) + 1 and normalized.endswith(particle):
                    normalized = normalized[: -len(particle)]
                    break

            candidates = [normalized]
            # "사기죄" → "사기"도 함께 추가
            if normalized.endswith("죄") and len(normalized) > 2:
                candidates.append(normalized[:-1])
            # "불법행위" → "불법"+"행위" 분리 없이 전체 유지 (법률 복합어 보호)

            for candidate in candidates:
                if len(candidate) < 2 or candidate in stopwords or candidate in keywords:
                    continue
                keywords.append(candidate)

        return keywords[:5]

    def _generate_answer(
        self,
        question: str,
        sources: list[RagSource],
        chat_history: list[tuple[str, str]] | None = None,
        answer_mode: str = "general",
        evidence_warnings: list[str] | None = None,
        case_context: str | None = None,
    ) -> str:
        model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.openai_temperature,
        )
        context = self._format_context(sources)
        conversation_context = self._format_chat_history(chat_history or [])
        mode_instruction = self._answer_mode_instruction(answer_mode)
        evidence_warning_text = self._format_evidence_warnings(evidence_warnings or [])
        personal_case_context = self._format_case_context(case_context)
        response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "당신은 한국 법률 상담을 돕는 AI 어시스턴트입니다. "
                        "반드시 제공된 법률 근거와 판례 근거 안에서만 답변하세요. "
                        "근거에 없는 법률요건, 판례 취지, 법적 결론은 절대 추측하지 말고 "
                        "근거 부족임을 명확히 밝히세요.\n\n"
                        "답변 원칙:\n"
                        "1. 검색된 근거에 없는 내용은 '근거 없음'으로 명시\n"
                        "2. 조문 번호(예: 민법 제750조)와 판례 사건번호를 정확히 인용\n"
                        "3. 법률 용어는 정확하게 사용하되 일반인이 이해할 수 있도록 설명 추가\n"
                        "4. 사실관계가 불명확할 때는 판단 유보 후 확인 필요 사항 제시\n"
                        "5. 이 답변은 법률 자문이 아닌 참고 정보임을 반드시 명시\n\n"
                        "답변 형식 (반드시 준수):\n"
                        "답변 요약\n"
                        "[핵심 결론을 2~4문장으로 요약]\n\n"
                        "관련 법령\n"
                        "- 법령명 및 조문: ...\n"
                        "- 적용 근거: ...\n\n"
                        "관련 판례\n"
                        "- 사건번호: ...\n"
                        "- 법원/선고일: ...\n"
                        "- 판결 요지: ...\n\n"
                        "주의사항\n"
                        "[한계, 추가 확인 필요 사항, 전문가 상담 권고]"
                    )
                ),
                HumanMessage(
                    content=(
                        f"최근 대화\n{conversation_context}\n\n"
                        f"개인 사건 메모\n{personal_case_context}\n\n"
                        f"답변 모드\n{mode_instruction}\n\n"
                        f"근거 품질 경고\n{evidence_warning_text}\n\n"
                        f"질문:\n{question}\n\n"
                        f"검색된 근거:\n{context}\n\n"
                        "위 검색된 근거만 사용해서 한국어로 답변하세요. "
                        "관련 판례가 없으면 '관련 판례\\n- 검색된 판례 근거가 부족합니다.'라고 쓰세요. "
                        "관련 법령이 없으면 '관련 법령\\n- 검색된 법령 근거가 부족합니다.'라고 쓰세요. "
                        "근거에 없는 내용을 임의로 추가하지 마세요."
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
                "쟁점 정리 모드입니다. 질문에서 문제되는 법적 쟁점을 항목별로 나누고, "
                "각 쟁점마다 관련 법령과 판례를 연결하세요. "
                "마지막에 추가로 확인할 사실을 제안하세요."
            ),
            "consultation": (
                "상담 준비 모드입니다. 전문가 상담 전에 준비해야 할 자료, 확인 질문, 위험 요소를 중심으로 정리하세요. "
                "답변은 법률 자문이 아니라 상담 준비용 참고 정보임을 분명히 하세요."
            ),
            "general": "기본 답변 모드입니다. 질문에 직접 답하고 관련 법령과 판례를 균형 있게 정리하세요.",
        }
        return instructions.get(answer_mode, instructions["general"])

    def _format_case_context(self, case_context: str | None) -> str:
        if not case_context or not case_context.strip():
            return "연결된 개인 사건 메모 없음"
        return case_context.strip()

    def _format_evidence_warnings(self, warnings: list[str]) -> str:
        if not warnings:
            return "경고 없음"
        return "\n".join(f"- {warning}" for warning in warnings)

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
            if evidence_type == "case_attachment":
                evidence_label = "개인 사건 첨부자료"
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
