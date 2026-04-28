from __future__ import annotations

import shutil
import time
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.path_safety import resolve_backend_env_path


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def cleanup_expired_children(
    root: str | Path,
    *,
    max_age_seconds: int,
    now: float | None = None,
    exclude_names: set[str] | None = None,
) -> list[Path]:
    """Delete expired immediate children under root and return removed paths."""
    if max_age_seconds <= 0:
        return []

    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        return []

    cutoff = (now if now is not None else time.time()) - max_age_seconds
    removed: list[Path] = []
    excluded = exclude_names or set()
    for child in root_path.iterdir():
        if child.name in excluded:
            continue
        try:
            resolved = child.resolve()
            resolved.relative_to(root_path)
        except Exception:
            continue
        try:
            if resolved.stat().st_mtime <= cutoff:
                _remove_path(resolved)
                removed.append(resolved)
        except FileNotFoundError:
            continue
    return removed


def cleanup_configured_storage(settings: Settings | None = None) -> dict[str, list[Path]]:
    effective = settings or get_settings()
    artifact_root = resolve_backend_env_path("BIZBUY_ARTIFACT_DIR", default_relative=".artifacts")
    upload_root = resolve_backend_env_path("BIZBUY_UPLOAD_DIR", default_relative="uploads")
    return {
        "uploads": cleanup_expired_children(
            upload_root,
            max_age_seconds=effective.upload_retention_seconds,
        ),
        "ocr": cleanup_expired_children(
            artifact_root / "ocr",
            max_age_seconds=effective.ocr_artifact_retention_seconds,
        ),
        "analyses": cleanup_expired_children(
            artifact_root,
            max_age_seconds=effective.analysis_artifact_retention_seconds,
            exclude_names={"ocr"},
        ),
    }
