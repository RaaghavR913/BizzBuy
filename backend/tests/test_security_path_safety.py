from __future__ import annotations

import pytest

from app.core.path_safety import (
    UnsafePathError,
    backend_project_root,
    resolve_backend_storage_path,
    safe_child_path,
    validate_analysis_id,
)
from app.models.schemas import AnalysisJobProgress, AnalysisJobRecord
from app.services.analysis_repository import FileSystemAnalysisArtifactRepository

VALID_ANALYSIS_ID = "55555555-5555-4555-8555-555555555555"


@pytest.mark.parametrize(
    "bad_id",
    ["../escape", r"..\escape", "/tmp/escape", "", "analysis-job-1"],
)
def test_analysis_id_rejects_path_like_or_non_uuid_values(bad_id: str) -> None:
    with pytest.raises(UnsafePathError):
        validate_analysis_id(bad_id)


def test_repository_writes_valid_analysis_artifacts_under_root(tmp_path) -> None:
    repository = FileSystemAnalysisArtifactRepository(tmp_path)
    job = AnalysisJobRecord(
        analysis_id=VALID_ANALYSIS_ID,
        status="queued",
        created_at="2026-04-26T00:00:00+00:00",
        updated_at="2026-04-26T00:00:00+00:00",
        progress=AnalysisJobProgress(),
    )

    ref = repository.save_analysis_job(job)

    target = tmp_path / VALID_ANALYSIS_ID / "analysis_job.json"
    assert target.exists()
    assert ref.path == str(target.resolve())
    assert repository.load_analysis_job(VALID_ANALYSIS_ID).analysis_id == VALID_ANALYSIS_ID


@pytest.mark.parametrize("bad_id", ["../escape", r"..\escape", "/tmp/escape"])
def test_repository_rejects_invalid_analysis_artifact_ids(tmp_path, bad_id: str) -> None:
    repository = FileSystemAnalysisArtifactRepository(tmp_path)

    with pytest.raises(UnsafePathError):
        repository.get_analysis_job_ref(bad_id)

    assert not (tmp_path.parent / "escape").exists()


@pytest.mark.parametrize("bad_part", ["../escape.txt", r"..\escape.txt", "/tmp/escape.txt", ""])
def test_safe_child_path_rejects_traversal_and_absolute_forms(tmp_path, bad_part: str) -> None:
    with pytest.raises(UnsafePathError):
        safe_child_path(tmp_path, bad_part)


def test_backend_storage_defaults_are_independent_of_cwd(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    backend_root = backend_project_root()

    assert resolve_backend_storage_path(None, default_relative=".artifacts") == backend_root / ".artifacts"
    assert resolve_backend_storage_path(None, default_relative="uploads") == backend_root / "uploads"
    assert resolve_backend_storage_path("backend/.artifacts", default_relative=".artifacts") == backend_root / ".artifacts"


def test_backend_storage_allows_absolute_overrides(tmp_path) -> None:
    configured = tmp_path / "artifacts"

    assert resolve_backend_storage_path(configured, default_relative=".artifacts") == configured.resolve()
