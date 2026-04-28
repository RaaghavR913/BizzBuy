from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath
from uuid import UUID


class UnsafePathError(ValueError):
    """Raised when caller-controlled input cannot be used as a storage key."""


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SPLIT_PATH_RE = re.compile(r"[\\/]+")
_BACKEND_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def backend_project_root() -> Path:
    return _BACKEND_PROJECT_ROOT


def resolve_backend_storage_path(
    configured_path: str | Path | None,
    *,
    default_relative: str,
) -> Path:
    """Resolve backend storage paths independently of the process cwd."""
    raw_path = Path(configured_path or default_relative)
    if raw_path.is_absolute():
        return raw_path.resolve()

    parts = raw_path.parts
    if parts and parts[0].lower() == _BACKEND_PROJECT_ROOT.name.lower():
        return (_BACKEND_PROJECT_ROOT.parent / raw_path).resolve()
    return (_BACKEND_PROJECT_ROOT / raw_path).resolve()


def resolve_backend_env_path(env_var: str, *, default_relative: str) -> Path:
    return resolve_backend_storage_path(os.getenv(env_var), default_relative=default_relative)


def validate_analysis_id(value: str | None, *, field_name: str = "analysis_id") -> str | None:
    """Return a canonical UUID string or reject unsafe storage keys."""
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        raise UnsafePathError(f"{field_name} must not be empty.")
    try:
        parsed = UUID(candidate)
    except (TypeError, ValueError) as exc:
        raise UnsafePathError(f"{field_name} must be a canonical UUID.") from exc
    canonical = str(parsed)
    if candidate.lower() != canonical:
        raise UnsafePathError(f"{field_name} must be a canonical UUID.")
    return canonical


def validate_sha256_hex(value: str, *, field_name: str = "file_hash") -> str:
    candidate = str(value).strip()
    if not _SHA256_RE.fullmatch(candidate):
        raise UnsafePathError(f"{field_name} must be a SHA-256 hex digest.")
    return candidate.lower()


def safe_child_path(root: str | Path, *relative_parts: str) -> Path:
    """Resolve a child path and verify it stays inside root.

    The helper treats both POSIX and Windows path separators as separators on
    every platform so mixed-form traversal attempts are rejected consistently.
    """
    root_path = Path(root).resolve()
    if not relative_parts:
        raise UnsafePathError("At least one relative path segment is required.")

    clean_parts: list[str] = []
    for raw_part in relative_parts:
        part = str(raw_part)
        if not part or "\x00" in part:
            raise UnsafePathError("Path segment must not be empty.")
        if Path(part).is_absolute() or PureWindowsPath(part).is_absolute():
            raise UnsafePathError("Absolute paths are not allowed.")
        for segment in _SPLIT_PATH_RE.split(part):
            if segment in {"", ".", ".."}:
                raise UnsafePathError("Path traversal is not allowed.")
            clean_parts.append(segment)

    candidate = root_path.joinpath(*clean_parts).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise UnsafePathError("Resolved path escaped the storage root.") from exc
    return candidate
