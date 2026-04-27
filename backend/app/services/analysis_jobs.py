from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Dict
from uuid import uuid4

from app.agents.orchestrator import run_pipeline
from app.core.config import get_settings
from app.core.path_safety import validate_analysis_id
from app.models.schemas import AnalysisJobProgress, AnalysisJobRecord, AnalysisJobRequest, AnalysisJobResponse
from app.services.analysis_repository import AnalysisArtifactRepository, get_analysis_artifact_repository
from app.services.analysis_service import run_analysis

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis-job")
_FUTURES: Dict[str, Future[None]] = {}
_FUTURES_LOCK = Lock()


class AnalysisJobLimitError(RuntimeError):
    pass


class AnalysisJobAccessError(RuntimeError):
    pass


_OWNER_CHECK_SKIPPED = object()


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


def _ensure_owner_access(job: AnalysisJobRecord, owner_flow_id: str | None) -> None:
    if not job.owner_flow_id:
        return
    if owner_flow_id and job.owner_flow_id == owner_flow_id:
        return
    raise AnalysisJobAccessError("Analysis job does not belong to this session.")


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
    completed_agents: list[str] | None = None,
    running_agents: list[str] | None = None,
    queued_agents: list[str] | None = None,
    agent_statuses: dict[str, str] | None = None,
    fallback_mode_active: bool | None = None,
    owner_flow_id: str | None = None,
) -> AnalysisJobRecord:
    existing = repository.load_analysis_job(analysis_id)
    timestamp = _now_iso()
    created_at = existing.created_at if existing else timestamp
    prev_agents = existing.progress.completed_agents if existing else []
    prev_running = existing.progress.running_agents if existing else []
    prev_queued = existing.progress.queued_agents if existing else []
    prev_statuses = existing.progress.agent_statuses if existing else {}
    job = AnalysisJobRecord(
        analysis_id=analysis_id,
        owner_flow_id=owner_flow_id if owner_flow_id is not None else (existing.owner_flow_id if existing else None),
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
            completed_agents=completed_agents if completed_agents is not None else prev_agents,
            running_agents=running_agents if running_agents is not None else prev_running,
            queued_agents=queued_agents if queued_agents is not None else prev_queued,
            agent_statuses=agent_statuses if agent_statuses is not None else prev_statuses,
            fallback_mode_active=bool(
                fallback_mode_active if fallback_mode_active is not None else (existing.progress.fallback_mode_active if existing else False)
            ),
        ),
        error=error,
    )
    repository.save_analysis_job(job)
    broadcast_job_snapshot(analysis_id, repository)
    return job


def _update_progress(
    repository: AnalysisArtifactRepository,
    analysis_id: str,
    stage: str,
    message: str,
    progress: float,
    completed_agents: list[str] | None = None,
    running_agents: list[str] | None = None,
    queued_agents: list[str] | None = None,
    agent_statuses: dict[str, str] | None = None,
    fallback_mode_active: bool | None = None,
) -> None:
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
        completed_agents=completed_agents,
        running_agents=running_agents,
        queued_agents=queued_agents,
        agent_statuses=agent_statuses,
        fallback_mode_active=fallback_mode_active,
    )


def _run_analysis_job(payload: AnalysisJobRequest, repository: AnalysisArtifactRepository) -> None:
    analysis_id = validate_analysis_id(payload.analysis_id) or str(uuid4())
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
            # Use a manually managed event loop so we can abandon timed-out agent
            # threads without blocking. asyncio.run() calls shutdown_default_executor()
            # which waits indefinitely for any lingering executor threads (e.g. agent
            # HTTP requests that exceeded the stage timeout). By shutting down the
            # executor with wait=False we let those threads finish in the background
            # and return immediately so the job status can be flipped to "completed".
            _pipeline_executor = ThreadPoolExecutor(
                max_workers=20,
                thread_name_prefix=f"agents-{analysis_id[:8]}",
            )
            _loop = asyncio.new_event_loop()
            _loop.set_default_executor(_pipeline_executor)
            try:
                report = _loop.run_until_complete(
                    run_pipeline(
                        payload.model_dump(mode="json", by_alias=True),
                        progress_callback=lambda stage, message, progress, completed_agents=None, **extra: _update_progress(
                            repository,
                            analysis_id,
                            stage,
                            message,
                            progress,
                            completed_agents=completed_agents,
                            running_agents=extra.get("running_agents"),
                            queued_agents=extra.get("queued_agents"),
                            agent_statuses=extra.get("agent_statuses"),
                            fallback_mode_active=extra.get("fallback_mode_active"),
                        ),
                    )
                )
            finally:
                # Abandon any agent threads still waiting on HTTP — do not block.
                _pipeline_executor.shutdown(wait=False)
                _loop.close()
        else:
            if not payload.financials or not payload.questionnaire or not payload.deal_info:
                raise ValueError("Structured analysis requires financials, questionnaire, and deal info.")

            _update_progress(repository, analysis_id, "deterministic_analysis", "Running structured analysis.", 0.45)
            report_model = run_analysis(payload.financials, payload.questionnaire, payload.deal_info)
            report = report_model.model_dump(mode="json", by_alias=True)

        repository.save_analysis_report(analysis_id, report)
        # Verify the report was actually persisted before marking the job completed.
        if repository.load_analysis_report(analysis_id) is None:
            raise RuntimeError(
                f"analysis_report.json was not readable after save for {analysis_id}. "
                "The job cannot be marked completed."
            )
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
    *,
    owner_flow_id: str | None = None,
) -> AnalysisJobResponse:
    settings = get_settings()
    if not settings.analysis_jobs_enabled:
        raise RuntimeError("Analysis jobs are disabled by rollout configuration.")

    artifact_repository = repository or get_analysis_artifact_repository()
    analysis_id = validate_analysis_id(payload.analysis_id) or str(uuid4())
    existing = artifact_repository.load_analysis_job(analysis_id)
    if existing:
        _ensure_owner_access(existing, owner_flow_id)

    if existing and existing.status in {"queued", "running"}:
        return _build_response(existing)

    with _FUTURES_LOCK:
        active_jobs = sum(1 for future in _FUTURES.values() if not future.done())
        if settings.max_active_analysis_jobs > 0 and active_jobs >= settings.max_active_analysis_jobs:
            raise AnalysisJobLimitError("Maximum active analysis jobs reached.")

    queued_job = AnalysisJobRecord(
        analysis_id=analysis_id,
        owner_flow_id=owner_flow_id,
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
    broadcast_job_snapshot(analysis_id, artifact_repository)

    job_payload = payload.model_copy(update={"analysis_id": analysis_id})
    future = _EXECUTOR.submit(_run_analysis_job, job_payload, artifact_repository)
    with _FUTURES_LOCK:
        _FUTURES[analysis_id] = future

    return _build_response(queued_job)


def get_analysis_job(
    analysis_id: str,
    repository: AnalysisArtifactRepository | None = None,
    *,
    owner_flow_id: str | None | object = _OWNER_CHECK_SKIPPED,
) -> AnalysisJobResponse | None:
    artifact_repository = repository or get_analysis_artifact_repository()
    analysis_id = validate_analysis_id(analysis_id) or analysis_id
    job = artifact_repository.load_analysis_job(analysis_id)
    if job is None:
        return None
    if owner_flow_id is not _OWNER_CHECK_SKIPPED:
        _ensure_owner_access(job, owner_flow_id if isinstance(owner_flow_id, str) else None)

    # Serve the report whenever it exists on disk (partial or complete).
    # The frontend renders whatever sections are populated and shows skeletons for the rest.
    report = artifact_repository.load_analysis_report(analysis_id)
    return _build_response(job, report=report)


def broadcast_job_snapshot(
    analysis_id: str, repository: AnalysisArtifactRepository | None = None
) -> None:
    """Push the current job + report to any SSE subscribers (e.g. after disk writes)."""
    artifact_repository = repository or get_analysis_artifact_repository()
    analysis_id = validate_analysis_id(analysis_id) or analysis_id
    snap = get_analysis_job(analysis_id, artifact_repository)
    if snap is None:
        return
    from app.services.sse_registry import publish_json_from_thread

    publish_json_from_thread(analysis_id, snap.model_dump(mode="json", by_alias=True))
