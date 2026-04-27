from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.core.security import RequestIdentity, _active_sse, _rate_windows, acquire_sse_slot, release_sse_slot
from app.main import app


def _reset_settings_and_limits() -> None:
    get_settings.cache_clear()
    _rate_windows.clear()
    _active_sse.clear()


def test_production_defaults_disable_sensitive_debug_and_require_auth(monkeypatch) -> None:
    monkeypatch.setenv("BIZBUY_ENV", "production")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("BIZBUY_API_BEARER_TOKEN", "secret-token")
    monkeypatch.delenv("BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED", raising=False)
    monkeypatch.delenv("BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES", raising=False)
    monkeypatch.delenv("BIZBUY_API_DOCS_ENABLED", raising=False)
    _reset_settings_and_limits()

    try:
        settings = get_settings()

        assert settings.auth_required is True
        assert settings.api_docs_enabled is False
        assert settings.pipeline_prompt_debug_artifacts_enabled is False
        assert settings.pipeline_prompt_debug_include_bodies is False
        assert settings.delete_uploads_after_ingest is True
    finally:
        _reset_settings_and_limits()


def test_production_requires_explicit_non_local_cors(monkeypatch) -> None:
    monkeypatch.setenv("BIZBUY_ENV", "production")
    monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)
    monkeypatch.setenv("BIZBUY_API_BEARER_TOKEN", "secret-token")
    _reset_settings_and_limits()

    try:
        with pytest.raises(ValueError, match="FRONTEND_ORIGIN"):
            get_settings()
    finally:
        _reset_settings_and_limits()


def test_production_expensive_route_rejects_missing_token(monkeypatch) -> None:
    monkeypatch.setenv("BIZBUY_ENV", "production")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("BIZBUY_API_BEARER_TOKEN", "secret-token")
    _reset_settings_and_limits()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/parse-documents",
            files={"files": ("seller-pnl.txt", b"Revenue 1200000\nNet Income 300000", "text/plain")},
            data={"fileTypes": '["profit_and_loss"]'},
        )

        assert response.status_code == 401
    finally:
        _reset_settings_and_limits()


def test_authorized_expensive_route_still_works(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BIZBUY_ENV", "production")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("BIZBUY_API_BEARER_TOKEN", "secret-token")
    monkeypatch.setenv("BIZBUY_ARTIFACT_DIR", str(tmp_path))
    _reset_settings_and_limits()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/parse-documents",
            headers={"Authorization": "Bearer secret-token"},
            files={"files": ("seller-pnl.txt", b"Revenue 1200000\nNet Income 300000", "text/plain")},
            data={"fileTypes": '["profit_and_loss"]'},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
    finally:
        _reset_settings_and_limits()


def test_rate_limit_returns_429(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BIZBUY_ENV", "development")
    monkeypatch.setenv("BIZBUY_PARSE_RATE_LIMIT", "1")
    monkeypatch.setenv("BIZBUY_ARTIFACT_DIR", str(tmp_path))
    _reset_settings_and_limits()

    try:
        client = TestClient(app)
        kwargs = {
            "files": {"files": ("seller-pnl.txt", b"Revenue 1200000\nNet Income 300000", "text/plain")},
            "data": {"fileTypes": '["profit_and_loss"]'},
        }
        first = client.post("/api/parse-documents", **kwargs)
        second = client.post("/api/parse-documents", **kwargs)

        assert first.status_code == 200
        assert second.status_code == 429
    finally:
        _reset_settings_and_limits()


def test_sse_connection_limit_is_enforced(monkeypatch) -> None:
    monkeypatch.setenv("BIZBUY_MAX_ACTIVE_SSE_CONNECTIONS", "1")
    _reset_settings_and_limits()
    identity = RequestIdentity(key="ip:test", ip_key="ip:test", authenticated=False)

    try:
        acquire_sse_slot(identity)
        with pytest.raises(Exception) as exc:
            acquire_sse_slot(identity)
        assert getattr(exc.value, "status_code", None) == 429
    finally:
        release_sse_slot(identity)
        _reset_settings_and_limits()
