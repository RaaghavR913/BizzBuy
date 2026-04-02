from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.analyze import router as analyze_router
from app.api.routes.health import router as health_router
from app.api.routes.parse_documents import router as parse_documents_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(parse_documents_router, tags=["documents"])
api_router.include_router(analyze_router, tags=["analysis"])
