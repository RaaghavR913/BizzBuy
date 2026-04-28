from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.agents.schemas import (
    DocumentInfo,
    DocumentSection,
    DocumentStatus,
    IngestionIssue,
    IngestionMetadata,
    IngestionOutput,
    SectionContentType,
    Timeframe,
)
from app.core.path_safety import validate_analysis_id
from app.services.analysis_repository import (
    AnalysisArtifactRepository,
    build_stored_ingestion_artifacts,
    get_analysis_artifact_repository,
)
from app.services.intake_service import IntakeDocument, infer_missing_document_inputs, normalize_document_payload
from app.services.section_data_normalizer import infer_latest_fiscal_year, normalize_section_extracted_data
from app.services.section_kind import infer_effective_section_identity
from app.agents.evidence_utils import safe_fiscal_year


def ingest_document_payloads(documents: list[dict[str, Any]]) -> IngestionOutput:
    intake_documents = [normalize_document_payload(document, index) for index, document in enumerate(documents)]
    return ingest_intake_documents(intake_documents)


def ingest_and_persist_document_payloads(
    documents: list[dict[str, Any]],
    *,
    analysis_id: str | None = None,
    repository: AnalysisArtifactRepository | None = None,
) -> IngestionOutput:
    intake_documents = [normalize_document_payload(document, index) for index, document in enumerate(documents)]
    return ingest_and_persist_intake_documents(
        intake_documents,
        analysis_id=analysis_id,
        repository=repository,
    )


def ingest_intake_documents(documents: list[IntakeDocument]) -> IngestionOutput:
    document_infos: list[DocumentInfo] = []
    failed_artifacts: list[IngestionIssue] = []
    warnings: list[str] = []

    for document in documents:
        sections = _build_sections(document)
        status = DocumentStatus.PARSED if sections else DocumentStatus.FAILED
        notes = list(document.notes)

        if not sections:
            notes.append("No structured text, rows, sheets, or parsed sections were available for ingestion.")
            failed_artifacts.append(
                IngestionIssue(
                    document_id=document.document_id,
                    file_name=document.file_name,
                    document_type=document.canonical_type,
                    stage="preprocessing",
                    code="no_extractable_content",
                    message="Document did not include parsed sections, spreadsheet rows, or raw text.",
                )
            )
        elif any(section.status == DocumentStatus.PARTIAL for section in sections):
            status = DocumentStatus.PARTIAL
            notes.append("One or more sections were only partially normalized during ingestion.")

        document_infos.append(
            DocumentInfo(
                document_id=document.document_id,
                file_name=document.file_name,
                mime_type=document.mime_type,
                document_type=document.canonical_type,
                declared_type=document.declared_type,
                canonical_type=document.canonical_type,
                size_bytes=document.size_bytes,
                status=status,
                confidence=_document_confidence(sections, status),
                notes=notes,
                sections=sections,
            )
        )

        if status == DocumentStatus.FAILED:
            warnings.append(f"{document.file_name} could not be converted into ingestion sections.")

    return IngestionOutput(
        documents=document_infos,
        metadata=IngestionMetadata(
            total_documents=len(document_infos),
            successfully_parsed=sum(1 for document in document_infos if document.status in {DocumentStatus.PARSED, DocumentStatus.PARTIAL}),
            failed_documents=[document.document_id for document in document_infos if document.status == DocumentStatus.FAILED],
            failed_artifacts=failed_artifacts,
            missing_inputs=infer_missing_document_inputs(documents),
            overall_confidence=_overall_confidence(document_infos),
            warnings=warnings,
        ),
    )


def ingest_and_persist_intake_documents(
    documents: list[IntakeDocument],
    *,
    analysis_id: str | None = None,
    repository: AnalysisArtifactRepository | None = None,
) -> IngestionOutput:
    output = ingest_intake_documents(documents)
    resolved_analysis_id = validate_analysis_id(analysis_id) if analysis_id else str(uuid4())
    if resolved_analysis_id is None:
        resolved_analysis_id = str(uuid4())
    artifact_repository = repository or get_analysis_artifact_repository()
    artifact_ref = artifact_repository.get_ingestion_artifact_ref(resolved_analysis_id)
    output.metadata.analysis_id = resolved_analysis_id
    output.metadata.artifact_refs = [artifact_ref]
    artifacts = build_stored_ingestion_artifacts(resolved_analysis_id, output)
    artifact_repository.save_ingestion_artifacts(artifacts)
    return output


def _build_sections(document: IntakeDocument) -> list[DocumentSection]:
    if document.sections:
        return [_normalize_section(document, section, index) for index, section in enumerate(document.sections)]
    if document.sheets:
        result: list[DocumentSection] = []
        for sheet_index, sheet in enumerate(document.sheets):
            result.extend(_sheet_sections(document, sheet, sheet_index))
        return result
    if document.spreadsheet_rows:
        return _rows_sections(document)
    if document.raw_text:
        return [_text_section(document)]
    return []


def _normalize_section(document: IntakeDocument, section: dict[str, Any], index: int) -> DocumentSection:
    timeframe_payload = section.get("timeframe") if isinstance(section.get("timeframe"), dict) else {}
    timeframe = Timeframe(
        start_date=timeframe_payload.get("startDate") or timeframe_payload.get("start_date"),
        end_date=timeframe_payload.get("endDate") or timeframe_payload.get("end_date"),
        fiscal_year=timeframe_payload.get("fiscalYear") or timeframe_payload.get("fiscal_year") or section.get("fiscalYear") or section.get("fiscal_year"),
    )
    extracted = (
        section.get("extracted_data")
        if isinstance(section.get("extracted_data"), dict)
        else section.get("extractedData")
        if isinstance(section.get("extractedData"), dict)
        else section.get("data")
        if isinstance(section.get("data"), dict)
        else {}
    )
    raw_text = section.get("raw_text") or section.get("rawText") or section.get("text") or ""
    notes = [str(note) for note in section.get("notes", []) if isinstance(note, (str, int, float))]
    status = DocumentStatus(section.get("status")) if section.get("status") in DocumentStatus._value2member_map_ else DocumentStatus.PARSED
    content_type_raw = section.get("contentType") or section.get("content_type")
    content_type = (
        SectionContentType(content_type_raw)
        if content_type_raw in SectionContentType._value2member_map_
        else SectionContentType.STRUCTURED if extracted else SectionContentType.TEXT if raw_text else SectionContentType.UNKNOWN
    )
    rows = extracted.get("rows") if isinstance(extracted.get("rows"), list) else []
    rows = [row for row in rows if isinstance(row, dict)]
    section_name = section.get("sectionName") or section.get("section_name") or section.get("name")
    section_document_type, section_kind = infer_effective_section_identity(
        parent_document_type=document.canonical_type,
        explicit_section_kind=section.get("section_kind") or section.get("sectionKind"),
        explicit_document_type=section.get("document_type") or section.get("documentType"),
        section_name=section_name,
        raw_text=str(raw_text),
        rows=rows,
    )
    timeframe.fiscal_year = safe_fiscal_year(timeframe.fiscal_year)
    if timeframe.fiscal_year is None:
        timeframe.fiscal_year = infer_latest_fiscal_year(rows)

    normalized = DocumentSection(
        section_id=section.get("sectionId") or section.get("section_id") or f"{document.document_id}:section-{index + 1}",
        document_id=document.document_id,
        document_type=section_document_type,
        section_kind=section_kind,
        timeframe=timeframe,
        extracted_data=extracted,
        raw_text=str(raw_text),
        confidence=_normalize_confidence(section.get("confidence"), default=0.75 if extracted or raw_text else 0.2),
        section_name=section_name,
        page=section.get("page"),
        page_start=section.get("pageStart") or section.get("page_start"),
        page_end=section.get("pageEnd") or section.get("page_end"),
        source_format=str(section.get("sourceFormat") or section.get("source_format") or _infer_source_format(document)),
        content_type=content_type,
        status=status,
        notes=notes,
    )
    normalized.extracted_data = normalize_section_extracted_data(normalized)
    return normalized


def _sheet_sections(document: IntakeDocument, sheet: dict[str, Any], index: int) -> list[DocumentSection]:
    """Convert a single workbook sheet into one or more DocumentSections.

    Sheets that contain stacked financial statements (e.g. Income Statement
    + SDE Reconciliation) are split into multiple sections by the unified
    ``split_rows_into_sections`` helper.
    """
    from app.services.section_splitter import split_rows_into_sections

    all_rows = sheet.get("rows") if isinstance(sheet.get("rows"), list) else []
    all_rows = [row for row in all_rows if isinstance(row, dict)]
    sheet_name = str(sheet.get("name") or f"Sheet {index + 1}")
    raw_text = str(sheet.get("text") or "")
    base_confidence = _normalize_confidence(sheet.get("confidence"), default=0.8 if all_rows else 0.45)

    segments = split_rows_into_sections(all_rows, document.canonical_type)

    sections: list[DocumentSection] = []
    for seg_index, (seg_kind, seg_rows) in enumerate(segments):
        notes = [f"Normalized spreadsheet sheet '{sheet_name}' into a section."]
        section_document_type, section_kind = infer_effective_section_identity(
            parent_document_type=document.canonical_type,
            explicit_section_kind=seg_kind if seg_kind != document.canonical_type.value else None,
            explicit_document_type=sheet.get("document_type") or sheet.get("documentType"),
            section_name=sheet_name,
            raw_text=raw_text,
            rows=seg_rows,
        )
        fiscal_year = safe_fiscal_year(sheet.get("fiscalYear") or sheet.get("fiscal_year")) or infer_latest_fiscal_year(seg_rows)
        suffix = f"-{seg_index + 1}" if len(segments) > 1 else ""
        normalized = DocumentSection(
            section_id=f"{document.document_id}:sheet-{index + 1}{suffix}",
            document_id=document.document_id,
            document_type=section_document_type,
            section_kind=section_kind,
            timeframe=Timeframe(fiscal_year=fiscal_year),
            extracted_data={"rows": seg_rows},
            raw_text=raw_text,
            confidence=base_confidence,
            section_name=sheet_name,
            source_format="spreadsheet",
            content_type=SectionContentType.SHEET,
            status=DocumentStatus.PARSED if seg_rows or raw_text else DocumentStatus.PARTIAL,
            notes=notes,
        )
        normalized.extracted_data = normalize_section_extracted_data(normalized)
        sections.append(normalized)
    return sections


def _rows_sections(document: IntakeDocument) -> list[DocumentSection]:
    """Convert flat spreadsheet rows into one or more DocumentSections.

    Stacked financial statements within a single CSV/spreadsheet are split
    by the unified ``split_rows_into_sections`` helper.
    """
    from app.services.section_splitter import split_rows_into_sections

    all_rows = document.spreadsheet_rows
    segments = split_rows_into_sections(all_rows, document.canonical_type)

    sections: list[DocumentSection] = []
    for seg_index, (seg_kind, seg_rows) in enumerate(segments):
        section_document_type, section_kind = infer_effective_section_identity(
            parent_document_type=document.canonical_type,
            explicit_section_kind=seg_kind if seg_kind != document.canonical_type.value else None,
            rows=seg_rows,
        )
        suffix = f"-{seg_index + 1}" if len(segments) > 1 else ""
        normalized = DocumentSection(
            section_id=f"{document.document_id}:rows-1{suffix}",
            document_id=document.document_id,
            document_type=section_document_type,
            section_kind=section_kind,
            timeframe=Timeframe(fiscal_year=infer_latest_fiscal_year(seg_rows)),
            extracted_data={"rows": seg_rows},
            raw_text="",
            confidence=0.8,
            section_name="Sheet 1",
            source_format="spreadsheet",
            content_type=SectionContentType.TABLE,
            status=DocumentStatus.PARSED,
            notes=["Normalized spreadsheet rows into a single section."],
        )
        normalized.extracted_data = normalize_section_extracted_data(normalized)
        sections.append(normalized)
    return sections


def _text_section(document: IntakeDocument) -> DocumentSection:
    source_format = _infer_source_format(document)
    notes = []
    if source_format == "pdf":
        notes.append("PDF content was ingested as raw text without page-level OCR.")
    section_document_type, section_kind = infer_effective_section_identity(
        parent_document_type=document.canonical_type,
        section_name="Document Text",
        raw_text=document.raw_text or "",
    )
    return DocumentSection(
        section_id=f"{document.document_id}:text-1",
        document_id=document.document_id,
        document_type=section_document_type,
        section_kind=section_kind,
        timeframe=Timeframe(),
        extracted_data={},
        raw_text=document.raw_text or "",
        confidence=0.6 if source_format == "pdf" else 0.7,
        section_name="Document Text",
        source_format=source_format,
        content_type=SectionContentType.TEXT,
        status=DocumentStatus.PARTIAL if source_format == "pdf" else DocumentStatus.PARSED,
        notes=notes,
    )


def _infer_source_format(document: IntakeDocument) -> str:
    if "pdf" in document.mime_type or document.file_name.lower().endswith(".pdf"):
        return "pdf"
    if "sheet" in document.mime_type or document.file_name.lower().endswith((".csv", ".xlsx", ".xls")):
        return "spreadsheet"
    if document.mime_type.startswith("text/"):
        return "text"
    return "unknown"


def _normalize_confidence(value: Any, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(numeric, 0.0), 1.0)


def _document_confidence(sections: list[DocumentSection], status: DocumentStatus) -> float:
    if not sections:
        return 0.0 if status == DocumentStatus.FAILED else 0.2
    return round(sum(section.confidence for section in sections) / len(sections), 4)


def _overall_confidence(documents: list[DocumentInfo]) -> float:
    if not documents:
        return 0.0
    confidences = [document.confidence or 0.0 for document in documents]
    return round(sum(confidences) / len(confidences), 4)
