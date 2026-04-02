from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


def _parse_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


class Settings(BaseModel):
    app_name: str = "BizBuy Backend"
    environment: str = os.getenv("BIZBUY_ENV", "development")
    report_mode: str = os.getenv("REPORT_MODE", "deterministic")
    cors_origins: list[str] = _parse_origins(
        os.getenv("FRONTEND_ORIGIN", "http://localhost:3000,http://127.0.0.1:3000")
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
