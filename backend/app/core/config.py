from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field, model_validator

_DEFAULT_PROMPT_DEBUG_STAGES = (
    "ingestion,"
    "financial_analysis,"
    "tax_compliance,"
    "ar_collections,"
    "customer_concentration,"
    "operations_transferability,"
    "lease_contract,"
    "market_macro,"
    "lending_affordability,"
    "synthesis_report"
)


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


def _environment() -> str:
    return os.getenv("BIZBUY_ENV", "development")


def _is_production_env() -> bool:
    return _environment().strip().lower() == "production"


def _default_cors_origins() -> list[str]:
    return _parse_origins(
        os.getenv("FRONTEND_ORIGIN", "http://localhost:3000,http://127.0.0.1:3000")
    )


class Settings(BaseModel):
    app_name: str = "BizBuy Backend"
    environment: str = Field(default_factory=_environment)
    report_mode: str = Field(default_factory=lambda: os.getenv("REPORT_MODE", "deterministic"))
    cors_origins: list[str] = Field(default_factory=_default_cors_origins)
    pipeline_enabled: bool = Field(default_factory=lambda: _parse_bool(os.getenv("BIZBUY_PIPELINE_ENABLED"), True))
    analysis_jobs_enabled: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_ANALYSIS_JOBS_ENABLED"), True)
    )
    pipeline_allow_partial_failures: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_PIPELINE_ALLOW_PARTIAL_FAILURES"), True)
    )
    pipeline_enable_synthesis: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_PIPELINE_ENABLE_SYNTHESIS"), True)
    )
    pipeline_retry_attempts: int = Field(
        default_factory=lambda: _parse_int(os.getenv("BIZBUY_PIPELINE_RETRY_ATTEMPTS"), 0)
    )
    pipeline_stage_timeout_seconds: float = Field(
        default_factory=lambda: _parse_float(os.getenv("BIZBUY_PIPELINE_STAGE_TIMEOUT_SECONDS"), 0.0)
    )
    pipeline_prompt_debug_artifacts_enabled: bool = Field(
        default_factory=lambda: _parse_bool(
            os.getenv("BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED"),
            not _is_production_env(),
        )
    )
    pipeline_prompt_debug_include_bodies: bool = Field(
        default_factory=lambda: _parse_bool(
            os.getenv("BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES"),
            not _is_production_env(),
        )
    )
    pipeline_prompt_debug_stages: list[str] = Field(
        default_factory=lambda: _parse_csv(
            os.getenv("BIZBUY_PIPELINE_PROMPT_DEBUG_STAGES", _DEFAULT_PROMPT_DEBUG_STAGES)
        )
    )
    use_mistral_batch: bool = Field(default_factory=lambda: _parse_bool(os.getenv("USE_MISTRAL_BATCH"), False))

    auth_required: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_REQUIRE_EXPENSIVE_ROUTE_AUTH"), _is_production_env())
    )
    api_bearer_token: str | None = Field(default_factory=lambda: os.getenv("BIZBUY_API_BEARER_TOKEN") or None)
    rate_limit_enabled: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_RATE_LIMIT_ENABLED"), True)
    )
    rate_limit_window_seconds: int = Field(
        default_factory=lambda: max(1, _parse_int(os.getenv("BIZBUY_RATE_LIMIT_WINDOW_SECONDS"), 60))
    )
    upload_rate_limit: int = Field(default_factory=lambda: _parse_int(os.getenv("BIZBUY_UPLOAD_RATE_LIMIT"), 60))
    parse_rate_limit: int = Field(default_factory=lambda: _parse_int(os.getenv("BIZBUY_PARSE_RATE_LIMIT"), 60))
    analysis_rate_limit: int = Field(default_factory=lambda: _parse_int(os.getenv("BIZBUY_ANALYSIS_RATE_LIMIT"), 30))
    sse_rate_limit: int = Field(default_factory=lambda: _parse_int(os.getenv("BIZBUY_SSE_RATE_LIMIT"), 60))
    upload_bytes_per_window: int = Field(
        default_factory=lambda: _parse_int(os.getenv("BIZBUY_UPLOAD_BYTES_PER_WINDOW"), 200 * 1024 * 1024)
    )
    max_upload_files: int = Field(
        default_factory=lambda: max(1, _parse_int(os.getenv("BIZBUY_MAX_UPLOAD_FILES"), 10))
    )
    max_upload_request_bytes: int = Field(
        default_factory=lambda: max(1, _parse_int(os.getenv("BIZBUY_MAX_UPLOAD_REQUEST_BYTES"), 100 * 1024 * 1024))
    )
    max_zip_entries: int = Field(
        default_factory=lambda: max(1, _parse_int(os.getenv("BIZBUY_MAX_ZIP_ENTRIES"), 256))
    )
    max_zip_uncompressed_bytes: int = Field(
        default_factory=lambda: max(1, _parse_int(os.getenv("BIZBUY_MAX_ZIP_UNCOMPRESSED_BYTES"), 50 * 1024 * 1024))
    )
    trusted_proxy_ips: list[str] = Field(
        default_factory=lambda: _parse_csv(os.getenv("BIZBUY_TRUSTED_PROXY_IPS"))
    )
    trust_x_forwarded_for: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_TRUST_X_FORWARDED_FOR"), False)
    )
    max_active_analysis_jobs: int = Field(
        default_factory=lambda: _parse_int(os.getenv("BIZBUY_MAX_ACTIVE_ANALYSIS_JOBS"), 20)
    )
    max_active_sse_connections_per_identity: int = Field(
        default_factory=lambda: _parse_int(os.getenv("BIZBUY_MAX_ACTIVE_SSE_CONNECTIONS"), 5)
    )
    api_docs_enabled: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_API_DOCS_ENABLED"), not _is_production_env())
    )
    delete_uploads_after_ingest: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_DELETE_UPLOADS_AFTER_INGEST"), _is_production_env())
    )
    retention_cleanup_on_startup: bool = Field(
        default_factory=lambda: _parse_bool(os.getenv("BIZBUY_RETENTION_CLEANUP_ON_STARTUP"), False)
    )
    upload_retention_seconds: int = Field(
        default_factory=lambda: _parse_int(os.getenv("BIZBUY_UPLOAD_RETENTION_SECONDS"), 24 * 60 * 60)
    )
    ocr_artifact_retention_seconds: int = Field(
        default_factory=lambda: _parse_int(os.getenv("BIZBUY_OCR_ARTIFACT_RETENTION_SECONDS"), 7 * 24 * 60 * 60)
    )
    analysis_artifact_retention_seconds: int = Field(
        default_factory=lambda: _parse_int(os.getenv("BIZBUY_ANALYSIS_ARTIFACT_RETENTION_SECONDS"), 30 * 24 * 60 * 60)
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment.strip().lower() != "production":
            return self

        if not os.getenv("FRONTEND_ORIGIN"):
            raise ValueError("FRONTEND_ORIGIN must be set explicitly in production.")

        unsafe_origins = {"*", "http://localhost:3000", "http://127.0.0.1:3000"}
        for origin in self.cors_origins:
            lower_origin = origin.lower()
            if (
                origin in unsafe_origins
                or lower_origin.startswith("http://localhost")
                or lower_origin.startswith("http://127.0.0.1")
            ):
                raise ValueError("Production FRONTEND_ORIGIN must not include wildcard or localhost origins.")

        if self.auth_required and not self.api_bearer_token:
            raise ValueError("BIZBUY_API_BEARER_TOKEN is required when production route auth is enabled.")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
