from __future__ import annotations

import asyncio
import shutil
import time
from threading import Event
from pathlib import Path

from app.models.schemas import AnalysisJobRequest
from app.services.analysis_jobs import get_analysis_job, start_analysis_job
from app.services.analysis_repository import FileSystemAnalysisArtifactRepository

ANALYSIS_ID_1 = "11111111-1111-4111-8111-111111111111"
ANALYSIS_ID_2 = "22222222-2222-4222-8222-222222222222"
ANALYSIS_ID_3 = "33333333-3333-4333-8333-333333333333"


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
            progress_callback(
                "ingestion",
                "Ingesting uploaded documents.",
                0.2,
                running_agents=["ingestion"],
                agent_statuses={"ingestion": "running"},
            )
            progress_callback(
                "synthesis_started",
                "Assembling the final report.",
                0.9,
                completed_agents=["financial_analysis"],
                running_agents=["synthesis_report"],
                queued_agents=[],
                agent_statuses={"financial_analysis": "success", "synthesis_report": "running"},
                fallback_mode_active=False,
            )
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
                analysis_id=ANALYSIS_ID_1,
                documents=[{"document_id": "doc-1", "sections": [{"raw_text": "Revenue 100"}]}],
            ),
            repository=repository,
        )

        assert created.analysis_id == ANALYSIS_ID_1
        assert created.status == "queued"

        completed = _wait_for_status(repository, ANALYSIS_ID_1, "completed")

        assert completed.progress.stage == "completed"
        assert completed.progress.progress == 1.0

        status = get_analysis_job(ANALYSIS_ID_1, repository=repository)

        assert status is not None
        assert status.status == "completed"
        assert status.report is not None
        assert status.report["metadata"]["analysisId"] == ANALYSIS_ID_1
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
            progress_callback(
                "ingestion",
                "Ingesting uploaded documents.",
                0.2,
                running_agents=["ingestion"],
                agent_statuses={"ingestion": "running"},
            )
            progress_callback(
                "specialists_started",
                "Running specialist analysis agents in parallel.",
                0.45,
                completed_agents=[],
                running_agents=["financial_analysis", "tax_compliance"],
                queued_agents=["market_macro"],
                agent_statuses={
                    "financial_analysis": "running",
                    "tax_compliance": "running",
                    "market_macro": "queued",
                },
            )
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
                analysis_id=ANALYSIS_ID_2,
                documents=[{"document_id": "doc-2", "sections": [{"raw_text": "Revenue 250"}]}],
            ),
            repository=repository,
        )

        running = _wait_for_status(repository, ANALYSIS_ID_2, "running")

        assert running.progress.stage in {"ingestion", "specialists_started"}
        assert running.progress.progress >= 0.2

        reloaded_repository = FileSystemAnalysisArtifactRepository(artifact_root)
        reloaded = get_analysis_job(ANALYSIS_ID_2, repository=reloaded_repository)

        assert reloaded is not None
        assert reloaded.status == "running"
        assert reloaded.progress.message in {
            "Ingesting uploaded documents.",
            "Running specialist analysis agents in parallel.",
        }
        assert reloaded.progress.running_agents in (["ingestion"], ["financial_analysis", "tax_compliance"])
        assert reloaded.report is None

        release_job.set()
        completed = _wait_for_status(repository, ANALYSIS_ID_2, "completed")

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
            progress_callback(
                "specialists_started",
                "Running specialist analysis agents in parallel.",
                0.45,
                running_agents=["financial_analysis"],
                queued_agents=["tax_compliance"],
                agent_statuses={"financial_analysis": "running", "tax_compliance": "queued"},
            )
            progress_callback(
                "completed_with_warnings",
                "Analysis completed with partial failures.",
                1.0,
                completed_agents=["financial_analysis"],
                running_agents=[],
                queued_agents=[],
                agent_statuses={"financial_analysis": "success", "tax_compliance": "timeout"},
                fallback_mode_active=True,
            )
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
                analysis_id=ANALYSIS_ID_3,
                documents=[{"document_id": "doc-3", "sections": [{"raw_text": "Revenue 500"}]}],
            ),
            repository=repository,
        )

        completed = _wait_for_status(repository, ANALYSIS_ID_3, "completed")
        status = get_analysis_job(ANALYSIS_ID_3, repository=repository)

        assert completed.progress.stage == "completed"
        assert status is not None
        assert status.status == "completed"
        assert status.report is not None
        assert status.report["metadata"]["pipelineStatus"] == "partial"
        assert status.report["metadata"]["auditMetadata"]["partialFailures"] == ["tax_compliance"]
        assert completed.progress.fallback_mode_active is True
    finally:
        shutil.rmtree(artifact_root, ignore_errors=True)
