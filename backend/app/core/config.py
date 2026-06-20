from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration for local, Docker, and deployed runtime."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "legal-rag-service"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+psycopg://legal_rag:legal_rag_password@localhost:5432/legal_rag"

    jwt_secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 14

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    chroma_persist_directory: str = "./chroma_db"
    chroma_collection_name: str = "legal_chunks"
    precedent_chroma_collection_name: str = "precedent_chunks_probe_10k"
    rag_top_k: int = 5
    rag_context_max_chars: int = 6000
    rag_case_context_max_chars: int = 2500
    rag_max_source_distance: float = 1.25
    rag_min_reliable_sources: int = 1
    openai_temperature: float = 0.2
    upload_directory: str = "./uploads"
    max_upload_size_mb: int = 20

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated origins from env vars without forcing JSON syntax."""
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cache settings so dependency injection and app startup use the same values."""
    return Settings()


settings = get_settings()
