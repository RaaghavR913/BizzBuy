from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Dict
from uuid import uuid4

from app.agents.orchestrator import run_pipeline
from app.core.config import get_settings
from app.models.schemas import AnalysisJobProgress, AnalysisJobRecord, AnalysisJobRequest, AnalysisJobResponse
from app.services.analysis_repository import AnalysisArtifactRepository, get_analysis_artifact_repository
from app.services.analysis_service import run_analysis

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis-job")
_FUTURES: Dict[str, Future[None]] = {}
_FUTURES_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_response(
    job: AnalysisJobRecord,
    report: dict[str, object] | None = None,
) -> AnalysisJobResponse:
    return AnalysisJobResponse(
        analysis_id=job.analysis_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        progress=job.progress,
        error=job.error,
        report=report,
    )


def _persist_job(
    repository: AnalysisArtifactRepository,
    analysis_id: str,
    *,
    status: str,
    progress: float,
    stage: str,
    message: str,
    error: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> AnalysisJobRecord:
    existing = repository.load_analysis_job(analysis_id)
    timestamp = _now_iso()
    created_at = existing.created_at if existing else timestamp
    job = AnalysisJobRecord(
        analysis_id=analysis_id,
        status=status,  # type: ignore[arg-type]
        created_at=created_at,
        updated_at=timestamp,
        started_at=started_at if started_at is not None else (existing.started_at if existing else None),
        completed_at=completed_at if completed_at is not None else (existing.completed_at if existing else None),
        progress=AnalysisJobProgress(
            stage=stage,
            message=message,
            progress=progress,
            updated_at=timestamp,
        ),
        error=error,
    )
    repository.save_analysis_job(job)
    return job


def _update_progress(repository: AnalysisArtifactRepository, analysis_id: str, stage: str, message: str, progress: float) -> None:
    existing = repository.load_analysis_job(analysis_id)
    started_at = existing.started_at if existing else _now_iso()
    _persist_job(
        repository,
        analysis_id,
        status="running",
        progress=progress,
        stage=stage,
        message=message,
        started_at=started_at,
    )


def _run_analysis_job(payload: AnalysisJobRequest, repository: AnalysisArtifactRepository) -> None:
    analysis_id = payload.analysis_id or str(uuid4())
    started_at = _now_iso()
    _persist_job(
        repository,
        analysis_id,
        status="running",
        progress=0.05,
        stage="preparing",
        message="Preparing analysis inputs.",
        started_at=started_at,
    )

    try:
        if payload.documents:
            report = asyncio.run(
                run_pipeline(
                    payload.model_dump(mode="json", by_alias=True),
                    progress_callback=lambda stage, message, progress: _update_progress(
                        repository,
                        analysis_id,
                        stage,
                        message,
                        progress,
                    ),
                )
            )
        else:
            if not payload.financials or not payload.questionnaire or not payload.deal_info:
                raise ValueError("Structured analysis requires financials, questionnaire, and deal info.")

            _update_progress(repository, analysis_id, "deterministic_analysis", "Running structured analysis.", 0.45)
            report_model = run_analysis(payload.financials, payload.questionnaire, payload.deal_info)
            report = report_model.model_dump(mode="json", by_alias=True)

        repository.save_analysis_report(analysis_id, report)
        job = _persist_job(
            repository,
            analysis_id,
            status="completed",
            progress=1.0,
            stage="completed",
            message="Analysis complete.",
            started_at=started_at,
            completed_at=_now_iso(),
        )
        repository.save_analysis_job(job)
    except Exception as exc:  # pragma: no cover - covered through public API tests
        error_text = str(exc)
        first_line = error_text.splitlines()[0] if error_text else "Analysis failed."
        summarized = first_line[:480]
        if len(error_text) > 480:
            summarized += "  (truncated; see analysis_job.json for full error)"
        _persist_job(
            repository,
            analysis_id,
            status="failed",
            progress=1.0,
            stage="failed",
            message="Analysis failed.",
            error=summarized,
            started_at=started_at,
            completed_at=_now_iso(),
        )
        raise
    finally:
        with _FUTURES_LOCK:
            _FUTURES.pop(analysis_id, None)


def start_analysis_job(
    payload: AnalysisJobRequest,
    repository: AnalysisArtifactRepository | None = None,
) -> AnalysisJobResponse:
    settings = get_settings()
    if not settings.analysis_jobs_enabled:
        raise RuntimeError("Analysis jobs are disabled by rollout configuration.")

    artifact_repository = repository or get_analysis_artifact_repository()
    analysis_id = payload.analysis_id or str(uuid4())
    existing = artifact_repository.load_analysis_job(analysis_id)

    if existing and existing.status in {"queued", "running"}:
        return _build_response(existing)

    queued_job = AnalysisJobRecord(
        analysis_id=analysis_id,
        status="queued",
        created_at=_now_iso(),
        updated_at=_now_iso(),
        progress=AnalysisJobProgress(
            stage="queued",
            message="Analysis queued.",
            progress=0,
            updated_at=_now_iso(),
        ),
    )
    artifact_repository.save_analysis_job(queued_job)

    job_payload = payload.model_copy(update={"analysis_id": analysis_id})
    future = _EXECUTOR.submit(_run_analysis_job, job_payload, artifact_repository)
    with _FUTURES_LOCK:
        _FUTURES[analysis_id] = future

    return _build_response(queued_job)


def get_analysis_job(
    analysis_id: str,
    repository: AnalysisArtifactRepository | None = None,
) -> AnalysisJobResponse | None:
    artifact_repository = repository or get_analysis_artifact_repository()
    job = artifact_repository.load_analysis_job(analysis_id)
    if job is None:
        return None

    report = artifact_repository.load_analysis_report(analysis_id) if job.status == "completed" else None
    return _build_response(job, report=report)
