from __future__ import annotations

import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings


class RequestBodyTooLarge(RuntimeError):
    pass


class RequestBodyLimitMiddleware:
    """Reject oversized request bodies before FastAPI parses multipart data."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = _body_limit_for_scope(scope)
        if limit <= 0:
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > limit:
            await _send_413(send, limit)
            return

        seen = 0

        async def limited_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                seen += len(body)
                if seen > limit:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await _send_413(send, limit)


def _body_limit_for_scope(scope: Scope) -> int:
    method = str(scope.get("method") or "").upper()
    if method not in {"POST", "PUT", "PATCH"}:
        return 0

    path = str(scope.get("path") or "")
    settings = get_settings()
    if path in {"/api/documents/ingest", "/api/parse-documents"}:
        return settings.max_upload_request_bytes
    if path in {"/api/analyze", "/api/analyses"}:
        return settings.max_analysis_request_bytes
    return 0


def _content_length(scope: Scope) -> int | None:
    headers: list[tuple[bytes, bytes]] = scope.get("headers", [])  # type: ignore[assignment]
    for key, value in headers:
        if key.lower() == b"content-length":
            try:
                return int(value.decode("ascii"))
            except ValueError:
                return None
    return None


async def _send_413(send: Send, limit: int) -> None:
    payload: dict[str, Any] = {
        "detail": {
            "error": "request_too_large",
            "detail": "Request body exceeds the configured byte limit.",
            "limit_bytes": limit,
        }
    }
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})

