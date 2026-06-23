import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.rag_service import prewarm_chromadb

    t = threading.Thread(target=prewarm_chromadb, daemon=True, name="chroma-prewarm")
    t.start()
    _log.info("[startup] ChromaDB prewarming started in background thread")
    yield


def create_app() -> FastAPI:
    """Create the FastAPI app so tests and ASGI servers share one entrypoint."""
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
