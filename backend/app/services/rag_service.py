from app.core.config import settings


class RagService:
    """Facade for retrieval and generation logic used by API routes."""

    def __init__(self, top_k: int | None = None) -> None:
        self.top_k = top_k or settings.rag_top_k

    def answer(self, question: str) -> str:
        """Placeholder until the LangChain retrieval chain is wired in."""
        return f"RAG pipeline is not connected yet. Received question: {question}"
