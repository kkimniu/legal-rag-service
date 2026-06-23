from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.search import (
    LegalSearchResponse,
    LegalSearchResult,
    PersonalSearchResponse,
    PersonalSearchResult,
)
from app.services.personal_search_service import search_personal_workspace
from app.services.rag_service import _get_chroma_client, _resolve_chroma_dir
from app.core.config import settings


router = APIRouter()


@router.get("", response_model=PersonalSearchResponse)
def search_workspace(
    q: str = Query(..., min_length=2, max_length=100),
    result_type: str | None = Query(default=None, pattern="^(case|note|task|attachment|chat)$"),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonalSearchResponse:
    """Search the current user's personal legal workspace."""
    data = search_personal_workspace(db, current_user.id, q, result_type=result_type, limit=limit)
    return PersonalSearchResponse(
        query=q.strip(),
        results=[PersonalSearchResult(**item) for item in data["results"]],
        total_count=data["total_count"],
    )


@router.get("/legal", response_model=LegalSearchResponse)
def search_legal(
    q: str = Query(..., min_length=2, max_length=200),
    limit: int = Query(default=10, ge=1, le=30),
    _current_user: User | None = Depends(get_optional_current_user),
) -> LegalSearchResponse:
    """Keyword search across the legal knowledge base (ChromaDB). No LLM call."""
    persist_dir = _resolve_chroma_dir()
    if persist_dir is None:
        return LegalSearchResponse(query=q.strip(), results=[], total_count=0)

    client = _get_chroma_client(str(persist_dir))
    query = q.strip()
    results: list[LegalSearchResult] = []
    seen_ids: set[str] = set()

    collections = [
        (settings.chroma_collection_name, "statute"),
        (settings.extra_chroma_collection_name, "statute"),
        (settings.precedent_chroma_collection_name, "precedent"),
    ]
    per_col = max(limit, 10)

    for col_name, evidence_type in collections:
        try:
            col = client.get_collection(col_name)
            raw = col.query(
                query_texts=[query],
                n_results=per_col,
                where_document={"$contains": query},
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            try:
                col = client.get_collection(col_name)
                raw = col.query(
                    query_texts=[query],
                    n_results=per_col,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                continue

        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        dists = raw.get("distances", [[]])[0]
        ids = raw.get("ids", [[]])[0]

        for chunk_id, text, meta, dist in zip(ids, docs, metas, dists):
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)
            snippet = text[:200].strip()
            results.append(LegalSearchResult(
                id=str(chunk_id),
                title=meta.get("title") or meta.get("article_title") or None,
                domain_name=meta.get("domain_name") or None,
                evidence_type=evidence_type,
                snippet=snippet,
                score=float(dist),
            ))

    results.sort(key=lambda r: r.score or 1.0)
    results = results[:limit]
    return LegalSearchResponse(query=query, results=results, total_count=len(results))
