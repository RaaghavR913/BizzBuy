from __future__ import annotations

import hashlib
import hmac
from ipaddress import ip_address, ip_network
import time
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Literal

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

RouteBucket = Literal["upload", "parse", "analysis", "sse"]


@dataclass(frozen=True)
class RequestIdentity:
    key: str
    ip_key: str
    authenticated: bool


@dataclass
class _Window:
    reset_at: float
    count: int = 0
    bytes_used: int = 0


_rate_lock = Lock()
_rate_windows: dict[tuple[str, str], _Window] = {}
_sse_lock = Lock()
_active_sse: dict[str, int] = {}


def _client_ip(request: Request) -> str:
    settings = get_settings()
    remote_addr = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for and _should_trust_forwarded_for(remote_addr, settings.trusted_proxy_ips):
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    return remote_addr


def _should_trust_forwarded_for(remote_addr: str, trusted_proxy_ips: list[str]) -> bool:
    settings = get_settings()
    if not settings.trust_x_forwarded_for or not trusted_proxy_ips:
        return False
    if remote_addr == "unknown":
        return False

    for trusted in trusted_proxy_ips:
        if _matches_trusted_proxy(remote_addr, trusted):
            return True
    return False


def _matches_trusted_proxy(remote_addr: str, trusted: str) -> bool:
    candidate = trusted.strip()
    if not candidate:
        return False
    if candidate == remote_addr:
        return True
    try:
        return ip_address(remote_addr) in ip_network(candidate, strict=False)
    except ValueError:
        return False


def _token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    header_token = request.headers.get("x-bizbuy-api-token")
    if header_token:
        return header_token.strip()
    query_token = request.query_params.get("access_token")
    if query_token:
        return query_token.strip()
    return None


def identify_request(request: Request) -> RequestIdentity:
    settings = get_settings()
    ip_key = f"ip:{_client_ip(request)}"
    if not settings.auth_required:
        return RequestIdentity(key=ip_key, ip_key=ip_key, authenticated=False)

    expected = settings.api_bearer_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend access control is not configured.",
        )

    token = _token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication token.")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    return RequestIdentity(key=f"token:{token_hash}", ip_key=ip_key, authenticated=True)


def _bucket_limit(bucket: RouteBucket) -> int:
    settings = get_settings()
    if bucket == "upload":
        return settings.upload_rate_limit
    if bucket == "parse":
        return settings.parse_rate_limit
    if bucket == "sse":
        return settings.sse_rate_limit
    return settings.analysis_rate_limit


def _check_counter(bucket: str, key: str, *, increment: int = 1, byte_increment: int = 0) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    limit = _bucket_limit(bucket) if bucket in {"upload", "parse", "analysis", "sse"} else 0
    byte_limit = settings.upload_bytes_per_window if bucket == "upload_bytes" else 0
    now = time.monotonic()
    reset_at = now + settings.rate_limit_window_seconds
    with _rate_lock:
        window = _rate_windows.get((bucket, key))
        if window is None or window.reset_at <= now:
            window = _Window(reset_at=reset_at)
            _rate_windows[(bucket, key)] = window

        if limit > 0 and window.count + increment > limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")
        if byte_limit > 0 and window.bytes_used + byte_increment > byte_limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Upload byte quota exceeded.")

        window.count += increment
        window.bytes_used += byte_increment


def check_rate_limit(request: Request, bucket: RouteBucket) -> RequestIdentity:
    identity = identify_request(request)
    _check_counter(bucket, identity.ip_key)
    if identity.authenticated:
        _check_counter(bucket, identity.key)
    return identity


def record_upload_bytes(request: Request | None, total_bytes: int) -> None:
    if request is None or total_bytes <= 0:
        return
    identity = identify_request(request)
    _check_counter("upload_bytes", identity.ip_key, increment=0, byte_increment=total_bytes)
    if identity.authenticated:
        _check_counter("upload_bytes", identity.key, increment=0, byte_increment=total_bytes)


def protect_expensive_route(bucket: RouteBucket) -> Callable[[Request], RequestIdentity]:
    def _dependency(request: Request) -> RequestIdentity:
        return check_rate_limit(request, bucket)

    return _dependency


def acquire_sse_slot(identity: RequestIdentity) -> None:
    max_connections = get_settings().max_active_sse_connections_per_identity
    if max_connections <= 0:
        return
    with _sse_lock:
        current = _active_sse.get(identity.key, 0)
        if current >= max_connections:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="SSE connection limit exceeded.",
            )
        _active_sse[identity.key] = current + 1


def release_sse_slot(identity: RequestIdentity) -> None:
    with _sse_lock:
        current = _active_sse.get(identity.key, 0)
        if current <= 1:
            _active_sse.pop(identity.key, None)
        else:
            _active_sse[identity.key] = current - 1
