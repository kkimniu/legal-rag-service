from pathlib import Path

import chromadb
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.legal_case import CaseAttachment, LegalCase


def split_attachment_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split extracted attachment text into stable overlapping chunks."""
    size = chunk_size or settings.case_attachment_chunk_size
    chunk_overlap = overlap if overlap is not None else settings.case_attachment_chunk_overlap
    if size <= 0 or chunk_overlap < 0 or chunk_overlap >= size:
        raise ValueError("Invalid attachment chunk settings.")

    normalized = text.strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = end - chunk_overlap
    return chunks


def index_case_attachment(db: Session, legal_case: LegalCase, attachment: CaseAttachment) -> CaseAttachment:
    """Embed one extracted attachment and upsert its chunks into ChromaDB."""
    text = (attachment.extracted_text or "").strip()
    if attachment.extraction_status != "completed" or not text:
        return _save_vector_status(db, attachment, "skipped", 0)
    if not settings.openai_api_key or str(settings.openai_api_key).startswith("replace-"):
        return _save_vector_status(db, attachment, "pending", 0)

    chunks = split_attachment_text(text)
    if not chunks:
        return _save_vector_status(db, attachment, "skipped", 0)

    try:
        persist_directory = _resolve_chroma_directory()
        persist_directory.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_directory))
        collection = client.get_or_create_collection(settings.case_attachment_collection_name)
        collection.delete(where={"attachment_id": attachment.id})

        embeddings = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
        vectors = embeddings.embed_documents(chunks)
        ids = [f"case-attachment-{attachment.id}-{index}" for index in range(len(chunks))]
        metadatas = [
            {
                "user_id": legal_case.user_id,
                "case_id": legal_case.id,
                "attachment_id": attachment.id,
                "chunk_index": index,
                "title": attachment.original_filename,
                "domain_code": legal_case.domain_code or "",
                "domain_name": "개인 사건 첨부자료",
                "source_type": "case_attachment",
            }
            for index in range(len(chunks))
        ]
        collection.upsert(ids=ids, documents=chunks, embeddings=vectors, metadatas=metadatas)
    except Exception:
        return _save_vector_status(db, attachment, "failed", 0)

    return _save_vector_status(db, attachment, "completed", len(chunks))


def delete_case_attachment_vectors(attachment_id: int) -> None:
    """Best-effort removal of all vectors belonging to one attachment."""
    try:
        persist_directory = _resolve_chroma_directory()
        if not persist_directory.exists():
            return
        client = chromadb.PersistentClient(path=str(persist_directory))
        collection = client.get_collection(settings.case_attachment_collection_name)
        collection.delete(where={"attachment_id": attachment_id})
    except Exception:
        return


def _save_vector_status(
    db: Session,
    attachment: CaseAttachment,
    status: str,
    chunk_count: int,
) -> CaseAttachment:
    attachment.vector_status = status
    attachment.vector_chunk_count = chunk_count
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def _resolve_chroma_directory() -> Path:
    configured = Path(settings.chroma_persist_directory)
    if configured.is_absolute():
        return configured.resolve()
    return (Path(__file__).resolve().parents[3] / configured).resolve()
