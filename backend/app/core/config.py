from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel

_DEFAULT_PROMPT_DEBUG_STAGES = "financial_analysis,tax_compliance,synthesis_report"


def _parse_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _parse_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


class Settings(BaseModel):
    app_name: str = "BizBuy Backend"
    environment: str = os.getenv("BIZBUY_ENV", "development")
    report_mode: str = os.getenv("REPORT_MODE", "deterministic")
    cors_origins: list[str] = _parse_origins(
        os.getenv("FRONTEND_ORIGIN", "http://localhost:3000,http://127.0.0.1:3000")
    )
    pipeline_enabled: bool = _parse_bool(os.getenv("BIZBUY_PIPELINE_ENABLED"), True)
    analysis_jobs_enabled: bool = _parse_bool(os.getenv("BIZBUY_ANALYSIS_JOBS_ENABLED"), True)
    pipeline_allow_partial_failures: bool = _parse_bool(
        os.getenv("BIZBUY_PIPELINE_ALLOW_PARTIAL_FAILURES"),
        True,
    )
    pipeline_enable_synthesis: bool = _parse_bool(os.getenv("BIZBUY_PIPELINE_ENABLE_SYNTHESIS"), True)
    pipeline_retry_attempts: int = _parse_int(os.getenv("BIZBUY_PIPELINE_RETRY_ATTEMPTS"), 0)
    pipeline_stage_timeout_seconds: float = _parse_float(
        os.getenv("BIZBUY_PIPELINE_STAGE_TIMEOUT_SECONDS"),
        240.0,
    )
    pipeline_prompt_debug_artifacts_enabled: bool = _parse_bool(
        os.getenv("BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED"),
        True,
    )
    pipeline_prompt_debug_include_bodies: bool = _parse_bool(
        os.getenv("BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES"),
        True,
    )
    pipeline_prompt_debug_stages: list[str] = _parse_csv(
        os.getenv("BIZBUY_PIPELINE_PROMPT_DEBUG_STAGES", _DEFAULT_PROMPT_DEBUG_STAGES)
    )
    use_mistral_batch: bool = _parse_bool(os.getenv("USE_MISTRAL_BATCH"), False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
