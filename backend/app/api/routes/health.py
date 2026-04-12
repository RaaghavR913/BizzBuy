from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "ok": True,
        "service": settings.app_name,
        "environment": settings.environment,
        "reportMode": settings.report_mode,
        "frontendOrigins": settings.cors_origins,
    }
