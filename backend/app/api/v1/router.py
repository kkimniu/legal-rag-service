from fastapi import APIRouter

from app.api.v1.routes import auth, cases, chat, health, rag, search

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
