from __future__ import annotations

import os
import time

from app.services.retention import cleanup_expired_children


def test_cleanup_expired_children_only_deletes_inside_root(tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    stale_dir = root / "stale"
    stale_dir.mkdir()
    stale_file = stale_dir / "payload.txt"
    stale_file.write_text("old", encoding="utf-8")
    fresh_dir = root / "fresh"
    fresh_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")

    old = time.time() - 3600
    os.utime(stale_file, (old, old))
    os.utime(stale_dir, (old, old))

    removed = cleanup_expired_children(root, max_age_seconds=60)

    assert stale_dir.resolve() in removed
    assert not stale_dir.exists()
    assert fresh_dir.exists()
    assert outside.exists()
