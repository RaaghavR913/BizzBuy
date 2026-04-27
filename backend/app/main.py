from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="BizBuy Backend",
    version="0.1.0",
    description="Deterministic acquisition analysis backend for BizBuy.",
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


def _mask(key: str) -> str:
    val = os.getenv(key)
    if not val:
        return "NOT SET"
    return f"{'*' * (len(val) - 4)}{val[-4:]}" if len(val) > 4 else "****"


@app.on_event("startup")
async def _set_sse_loop() -> None:
    import asyncio

    from app.services.sse_registry import set_event_loop

    set_event_loop(asyncio.get_running_loop())


@app.on_event("startup")
async def _log_startup() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("BizBuy backend starting - environment=%s", settings.environment)
    if settings.environment.strip().lower() == "production":
        logger.info(
            "  Security: auth_required=%s rate_limits=%s docs_enabled=%s",
            settings.auth_required,
            settings.rate_limit_enabled,
            settings.api_docs_enabled,
        )
    else:
        logger.info("  OPENROUTER_API_KEY  : %s", _mask("OPENROUTER_API_KEY"))
        logger.info("  MISTRAL_API_KEY     : %s", _mask("MISTRAL_API_KEY"))
    logger.info(
        "  Pipeline: timeout=%ss  retries=%d  partial_failures=%s  synthesis=%s",
        settings.pipeline_stage_timeout_seconds,
        settings.pipeline_retry_attempts,
        settings.pipeline_allow_partial_failures,
        settings.pipeline_enable_synthesis,
    )
    if settings.retention_cleanup_on_startup:
        from app.services.retention import cleanup_configured_storage

        removed = cleanup_configured_storage(settings)
        logger.info(
            "  Retention cleanup removed uploads=%d ocr=%d analyses=%d",
            len(removed["uploads"]),
            len(removed["ocr"]),
            len(removed["analyses"]),
        )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "environment": settings.environment,
        "reportMode": settings.report_mode,
    }
