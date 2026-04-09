from __future__ import annotations

from datetime import datetime, timezone

from app.agents.schemas import ClarificationAnswer, EvidenceReference
from app.services.analysis_repository import AnalysisArtifactRepository, get_analysis_artifact_repository


def store_clarification_answers(
    analysis_id: str,
    clarifications: list[ClarificationAnswer],
    *,
    repository: AnalysisArtifactRepository | None = None,
) -> list[ClarificationAnswer]:
    artifact_repository = repository or get_analysis_artifact_repository()
    artifacts = artifact_repository.load_ingestion_artifacts(analysis_id)
    if artifacts is None:
        return clarifications

    merged: dict[str, ClarificationAnswer] = {
        clarification.question_id: clarification for clarification in artifacts.clarifications
    }
    for clarification in clarifications:
        merged[clarification.question_id] = clarification

    artifacts.clarifications = list(merged.values())
    artifacts.stored_at = datetime.now(timezone.utc).isoformat()
    artifact_repository.save_ingestion_artifacts(artifacts)
    return artifacts.clarifications


def build_clarification_evidence(
    clarifications: list[ClarificationAnswer],
    *,
    analysis_id: str | None = None,
) -> list[EvidenceReference]:
    if not clarifications:
        return []

    document_id = f"clarifications:{analysis_id or 'session'}"
    evidence: list[EvidenceReference] = []

    for clarification in clarifications:
        if clarification.value in (None, ""):
            continue
        label = clarification.value_label or str(clarification.value)
        evidence.append(
            EvidenceReference(
                document_id=document_id,
                file_name="User clarifications",
                section_id=clarification.question_id,
                snippet=f"{clarification.prompt} Answer: {label}",
                extracted_fields={
                    "source": clarification.source,
                    "supplemental": clarification.supplemental,
                    "value": clarification.value,
                    "legacy_field_path": clarification.legacy_field_path,
                },
                confidence=clarification.confidence,
            )
        )

    return evidence
