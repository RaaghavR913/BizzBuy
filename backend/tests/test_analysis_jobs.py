from __future__ import annotations

import asyncio
import shutil
import time
from threading import Event
from pathlib import Path

from app.models.schemas import AnalysisJobRequest
from app.services.analysis_jobs import get_analysis_job, start_analysis_job
from app.services.analysis_repository import FileSystemAnalysisArtifactRepository


def _wait_for_status(
    repository: FileSystemAnalysisArtifactRepository,
    analysis_id: str,
    expected_status: str,
    timeout_seconds: float = 2.0,
):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        job = repository.load_analysis_job(analysis_id)
        if job and job.status == expected_status:
            return job
        time.sleep(0.02)
    raise AssertionError(f"Timed out waiting for {analysis_id} to reach {expected_status}.")


def test_analysis_job_persists_progress_and_completed_report(monkeypatch) -> None:
    artifact_root = Path("backend/.test-artifacts/analysis-jobs-complete")
    shutil.rmtree(artifact_root, ignore_errors=True)
    repository = FileSystemAnalysisArtifactRepository(artifact_root)

    async def fake_run_pipeline(payload, progress_callback=None):
        if progress_callback:
            progress_callback("ingestion", "Ingesting uploaded documents.", 0.2)
            progress_callback("synthesis", "Assembling the final report.", 0.9)
        await asyncio.sleep(0.05)
        return {
            "modeAvailable": {"summary": True, "deep": False},
            "summary": {"headline": "Ready", "overview": "Complete", "keyFindings": [], "recommendedActions": []},
            "scorecard": {
                "buyerFacingDimensions": [],
                "technicalScorecards": [],
                "dealBreakers": [],
                "conflicts": [],
                "validatedMetrics": {},
            },
            "metadata": {"contractVersion": "2.0", "analysisId": payload["analysisId"], "pipelineStatus": "completed"},
        }

    monkeypatch.setattr("app.services.analysis_jobs.run_pipeline", fake_run_pipeline)

    try:
        created = start_analysis_job(
            AnalysisJobRequest(
                analysis_id="analysis-job-1",
                documents=[{"document_id": "doc-1", "sections": [{"raw_text": "Revenue 100"}]}],
            ),
            repository=repository,
        )

        assert created.analysis_id == "analysis-job-1"
        assert created.status == "queued"

        completed = _wait_for_status(repository, "analysis-job-1", "completed")

        assert completed.progress.stage == "completed"
        assert completed.progress.progress == 1.0

        status = get_analysis_job("analysis-job-1", repository=repository)

        assert status is not None
        assert status.status == "completed"
        assert status.report is not None
        assert status.report["metadata"]["analysisId"] == "analysis-job-1"
        assert status.report["summary"]["headline"] == "Ready"
    finally:
        shutil.rmtree(artifact_root, ignore_errors=True)


def test_analysis_job_status_is_reloadable_while_running(monkeypatch) -> None:
    artifact_root = Path("backend/.test-artifacts/analysis-jobs-running")
    shutil.rmtree(artifact_root, ignore_errors=True)
    repository = FileSystemAnalysisArtifactRepository(artifact_root)
    release_job = Event()

    async def fake_run_pipeline(payload, progress_callback=None):
        if progress_callback:
            progress_callback("ingestion", "Ingesting uploaded documents.", 0.2)
            progress_callback("specialist_analysis", "Running specialist analysis agents.", 0.45)
        while not release_job.is_set():
            await asyncio.sleep(0.02)
        if progress_callback:
            progress_callback("completed", "Analysis complete.", 1.0)
        return {
            "modeAvailable": {"summary": True, "deep": False},
            "summary": {"headline": "Finished", "overview": "Done", "keyFindings": [], "recommendedActions": []},
            "scorecard": {
                "buyerFacingDimensions": [],
                "technicalScorecards": [],
                "dealBreakers": [],
                "conflicts": [],
                "validatedMetrics": {},
            },
            "metadata": {"contractVersion": "2.0", "analysisId": payload["analysisId"], "pipelineStatus": "completed"},
        }

    monkeypatch.setattr("app.services.analysis_jobs.run_pipeline", fake_run_pipeline)

    try:
        start_analysis_job(
            AnalysisJobRequest(
                analysis_id="analysis-job-2",
                documents=[{"document_id": "doc-2", "sections": [{"raw_text": "Revenue 250"}]}],
            ),
            repository=repository,
        )

        running = _wait_for_status(repository, "analysis-job-2", "running")

        assert running.progress.stage in {"ingestion", "specialist_analysis"}
        assert running.progress.progress >= 0.2

        reloaded_repository = FileSystemAnalysisArtifactRepository(artifact_root)
        reloaded = get_analysis_job("analysis-job-2", repository=reloaded_repository)

        assert reloaded is not None
        assert reloaded.status == "running"
        assert reloaded.progress.message in {
            "Ingesting uploaded documents.",
            "Running specialist analysis agents.",
        }
        assert reloaded.report is None

        release_job.set()
        completed = _wait_for_status(repository, "analysis-job-2", "completed")

        assert completed.completed_at is not None
    finally:
        release_job.set()
        shutil.rmtree(artifact_root, ignore_errors=True)


def test_analysis_job_persists_partial_report_without_marking_job_failed(monkeypatch) -> None:
    artifact_root = Path("backend/.test-artifacts/analysis-jobs-partial")
    shutil.rmtree(artifact_root, ignore_errors=True)
    repository = FileSystemAnalysisArtifactRepository(artifact_root)

    async def fake_run_pipeline(payload, progress_callback=None):
        if progress_callback:
            progress_callback("specialist_analysis", "Running specialist analysis agents.", 0.45)
            progress_callback("completed_with_warnings", "Analysis completed with partial failures.", 1.0)
        await asyncio.sleep(0.05)
        return {
            "modeAvailable": {"summary": True, "deep": False},
            "summary": {"headline": "Caution", "overview": "Partial", "keyFindings": [], "recommendedActions": []},
            "scorecard": {
                "buyerFacingDimensions": [],
                "technicalScorecards": [],
                "dealBreakers": [],
                "conflicts": [],
                "validatedMetrics": {},
            },
            "metadata": {
                "contractVersion": "2.0",
                "analysisId": payload["analysisId"],
                "pipelineStatus": "partial",
                "auditMetadata": {"partialFailures": ["tax_compliance"]},
            },
        }

    monkeypatch.setattr("app.services.analysis_jobs.run_pipeline", fake_run_pipeline)

    try:
        start_analysis_job(
            AnalysisJobRequest(
                analysis_id="analysis-job-3",
                documents=[{"document_id": "doc-3", "sections": [{"raw_text": "Revenue 500"}]}],
            ),
            repository=repository,
        )

        completed = _wait_for_status(repository, "analysis-job-3", "completed")
        status = get_analysis_job("analysis-job-3", repository=repository)

        assert completed.progress.stage == "completed"
        assert status is not None
        assert status.status == "completed"
        assert status.report is not None
        assert status.report["metadata"]["pipelineStatus"] == "partial"
        assert status.report["metadata"]["auditMetadata"]["partialFailures"] == ["tax_compliance"]
    finally:
        shutil.rmtree(artifact_root, ignore_errors=True)
