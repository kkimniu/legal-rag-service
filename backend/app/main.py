import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

_log = logging.getLogger(__name__)


def _startup_tasks() -> None:
    from app.db.session import SessionLocal
    from app.services.rag_service import prewarm_chromadb
    from app.services.user_service import delete_stale_guest_users

    db = SessionLocal()
    try:
        deleted = delete_stale_guest_users(db)
        if deleted:
            _log.info("[startup] deleted %d stale guest account(s)", deleted)
    except Exception as exc:
        _log.warning("[startup] guest cleanup failed: %s", exc)
    finally:
        db.close()

    prewarm_chromadb()


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_startup_tasks, daemon=True, name="startup-tasks")
    t.start()
    _log.info("[startup] background startup tasks launched")
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
