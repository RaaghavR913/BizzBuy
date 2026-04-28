from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.agents.schemas import ArtifactReference, ArtifactStorageKind, StoredIngestionArtifacts
from app.agents.evidence_utils import build_evidence_fields
from app.core.path_safety import resolve_backend_env_path, safe_child_path, validate_analysis_id
from app.models.schemas import AnalysisJobRecord


class AnalysisArtifactRepository(Protocol):
    def get_ingestion_artifact_ref(self, analysis_id: str) -> ArtifactReference:
        ...

    def get_analysis_job_ref(self, analysis_id: str) -> ArtifactReference:
        ...

    def get_analysis_report_ref(self, analysis_id: str) -> ArtifactReference:
        ...

    def get_prompt_debug_artifact_ref(self, analysis_id: str) -> ArtifactReference:
        ...

    def save_ingestion_artifacts(self, artifacts: StoredIngestionArtifacts) -> ArtifactReference:
        ...

    def load_ingestion_artifacts(self, analysis_id: str) -> StoredIngestionArtifacts | None:
        ...

    def save_analysis_job(self, job: AnalysisJobRecord) -> ArtifactReference:
        ...

    def load_analysis_job(self, analysis_id: str) -> AnalysisJobRecord | None:
        ...

    def save_analysis_report(self, analysis_id: str, report: dict[str, object]) -> ArtifactReference:
        ...

    def load_analysis_report(self, analysis_id: str) -> dict[str, object] | None:
        ...

    def save_prompt_debug_artifact(self, analysis_id: str, payload: dict[str, object]) -> ArtifactReference:
        ...

    def load_prompt_debug_artifact(self, analysis_id: str) -> dict[str, object] | None:
        ...


class FileSystemAnalysisArtifactRepository:
    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root_dir = (
            Path(root_dir).resolve()
            if root_dir is not None
            else resolve_backend_env_path("BIZBUY_ARTIFACT_DIR", default_relative=".artifacts")
        )
 
    _fs_lock = RLock()

    def _artifact_path(self, analysis_id: str, filename: str) -> Path:
        safe_analysis_id = validate_analysis_id(analysis_id)
        if safe_analysis_id is None:
            raise ValueError("analysis_id is required.")
        return safe_child_path(self.root_dir, safe_analysis_id, filename)

    def get_ingestion_artifact_ref(self, analysis_id: str) -> ArtifactReference:
        path = self._artifact_path(analysis_id, "ingestion_artifacts.json")
        return ArtifactReference(
            artifact_key="ingestion_artifacts",
            storage_kind=ArtifactStorageKind.FILESYSTEM,
            path=str(path),
            content_type="application/json",
        )

    def get_analysis_job_ref(self, analysis_id: str) -> ArtifactReference:
        path = self._artifact_path(analysis_id, "analysis_job.json")
        return ArtifactReference(
            artifact_key="analysis_job",
            storage_kind=ArtifactStorageKind.FILESYSTEM,
            path=str(path),
            content_type="application/json",
        )

    def get_analysis_report_ref(self, analysis_id: str) -> ArtifactReference:
        path = self._artifact_path(analysis_id, "analysis_report.json")
        return ArtifactReference(
            artifact_key="analysis_report",
            storage_kind=ArtifactStorageKind.FILESYSTEM,
            path=str(path),
            content_type="application/json",
        )

    def get_prompt_debug_artifact_ref(self, analysis_id: str) -> ArtifactReference:
        path = self._artifact_path(analysis_id, "prompt_debug.json")
        return ArtifactReference(
            artifact_key="prompt_debug",
            storage_kind=ArtifactStorageKind.FILESYSTEM,
            path=str(path),
            content_type="application/json",
        )

    def save_ingestion_artifacts(self, artifacts: StoredIngestionArtifacts) -> ArtifactReference:
        ref = self.get_ingestion_artifact_ref(artifacts.analysis_id)
        target_path = Path(ref.path)
        payload = artifacts.model_dump(mode="json")
        with self._fs_lock:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return ref

    def load_ingestion_artifacts(self, analysis_id: str) -> StoredIngestionArtifacts | None:
        ref = self.get_ingestion_artifact_ref(analysis_id)
        target_path = Path(ref.path)
        with self._fs_lock:
            if not target_path.exists():
                return None
            raw = target_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return StoredIngestionArtifacts.model_validate_json(raw)

    def save_analysis_job(self, job: AnalysisJobRecord) -> ArtifactReference:
        ref = self.get_analysis_job_ref(job.analysis_id)
        target_path = Path(ref.path)
        payload = job.model_dump(mode="json")
        with self._fs_lock:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return ref

    def load_analysis_job(self, analysis_id: str) -> AnalysisJobRecord | None:
        ref = self.get_analysis_job_ref(analysis_id)
        target_path = Path(ref.path)
        with self._fs_lock:
            if not target_path.exists():
                return None
            raw = target_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return AnalysisJobRecord.model_validate_json(raw)

    def save_analysis_report(self, analysis_id: str, report: dict[str, object]) -> ArtifactReference:
        ref = self.get_analysis_report_ref(analysis_id)
        target_path = Path(ref.path)
        with self._fs_lock:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return ref

    def load_analysis_report(self, analysis_id: str) -> dict[str, object] | None:
        ref = self.get_analysis_report_ref(analysis_id)
        target_path = Path(ref.path)
        with self._fs_lock:
            if not target_path.exists():
                return None
            raw = target_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
        raise ValueError("Stored analysis report must be a JSON object")

    def save_prompt_debug_artifact(self, analysis_id: str, payload: dict[str, object]) -> ArtifactReference:
        ref = self.get_prompt_debug_artifact_ref(analysis_id)
        target_path = Path(ref.path)
        with self._fs_lock:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return ref

    def load_prompt_debug_artifact(self, analysis_id: str) -> dict[str, object] | None:
        ref = self.get_prompt_debug_artifact_ref(analysis_id)
        target_path = Path(ref.path)
        with self._fs_lock:
            if not target_path.exists():
                return None
            raw = target_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
        raise ValueError("Stored prompt debug artifact must be a JSON object")


def build_stored_ingestion_artifacts(
    analysis_id: str,
    ingestion_output: "IngestionOutput",
) -> StoredIngestionArtifacts:
    from app.agents.schemas import EvidenceReference, IngestionDocumentArtifact, IngestionOutput

    if not isinstance(ingestion_output, IngestionOutput):
        raise TypeError("ingestion_output must be an IngestionOutput instance")

    document_inventory = [
        IngestionDocumentArtifact(
            document_id=document.document_id,
            file_name=document.file_name,
            document_type=document.document_type,
            status=document.status,
            confidence=document.confidence,
            section_ids=[section.section_id or "" for section in document.sections],
            notes=document.notes,
        )
        for document in ingestion_output.documents
    ]

    evidence_index = []
    for document in ingestion_output.documents:
        for section in document.sections:
            evidence_index.append(
                EvidenceReference(
                    document_id=document.document_id,
                    file_name=document.file_name,
                    section_id=section.section_id,
                    page=section.page or section.page_start,
                    snippet=(section.raw_text or "")[:280] or None,
                    extracted_fields=build_evidence_fields(section),
                    confidence=section.confidence,
                )
            )

    return StoredIngestionArtifacts(
        analysis_id=analysis_id,
        stored_at=datetime.now(timezone.utc).isoformat(),
        ingestion_output=ingestion_output,
        document_inventory=document_inventory,
        evidence_index=evidence_index,
    )


_DEFAULT_REPOSITORY: FileSystemAnalysisArtifactRepository | None = None


def get_analysis_artifact_repository() -> FileSystemAnalysisArtifactRepository:
    global _DEFAULT_REPOSITORY
    if _DEFAULT_REPOSITORY is None:
        _DEFAULT_REPOSITORY = FileSystemAnalysisArtifactRepository()
    return _DEFAULT_REPOSITORY
