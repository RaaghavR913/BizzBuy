from __future__ import annotations

import shutil
from pathlib import Path

from app.agents.schemas import ArtifactStorageKind
from app.services.analysis_repository import FileSystemAnalysisArtifactRepository
from app.agents.schemas import DocumentStatus, DocumentType, SectionContentType
from app.services.ingestion_service import ingest_and_persist_document_payloads, ingest_document_payloads
from app.services.intake_service import normalize_document_payload

ANALYSIS_ID = "77777777-7777-4777-8777-777777777777"


def test_normalize_document_payload_maps_legacy_metadata_to_canonical_contract() -> None:
    payload = normalize_document_payload(
        {
            "id": "doc-1",
            "name": "seller-pnl.pdf",
            "documentType": "income_statement",
            "mimeType": "application/pdf",
            "sizeBytes": 4096,
            "text": "Revenue 1200000",
        },
        index=0,
    )

    assert payload.document_id == "doc-1"
    assert payload.file_name == "seller-pnl.pdf"
    assert payload.declared_type == DocumentType.PROFIT_AND_LOSS
    assert payload.canonical_type == DocumentType.PROFIT_AND_LOSS
    assert payload.mime_type == "application/pdf"
    assert payload.size_bytes == 4096
    assert payload.raw_text == "Revenue 1200000"


def test_ingest_document_payloads_tracks_parsed_failed_and_missing_documents() -> None:
    output = ingest_document_payloads(
        [
            {
                "id": "pdf-1",
                "fileName": "pnl.pdf",
                "documentType": "profit_and_loss",
                "mimeType": "application/pdf",
                "text": "Revenue 1200000",
            },
            {
                "id": "sheet-1",
                "fileName": "customers.csv",
                "documentType": "customer_list",
                "rows": [
                    {"name": "A", "annualRevenue": 500000},
                    {"name": "B", "annualRevenue": 300000},
                ],
            },
            {
                "id": "parsed-1",
                "fileName": "tax.json",
                "documentType": "tax_return_1120s",
                "sections": [
                    {
                        "sectionId": "tax-2024",
                        "fiscalYear": 2024,
                        "extractedData": {"gross_receipts": 1000000},
                        "rawText": "Gross receipts 1000000",
                        "confidence": 0.91,
                        "contentType": "structured",
                        "page": 2,
                    }
                ],
            },
            {
                "id": "failed-1",
                "fileName": "empty.pdf",
                "documentType": "balance_sheet",
                "mimeType": "application/pdf",
            },
        ]
    )

    assert output.metadata.total_documents == 4
    assert output.metadata.successfully_parsed == 3
    assert output.metadata.overall_confidence == 0.5775
    assert output.metadata.failed_documents == ["failed-1"]
    assert len(output.metadata.failed_artifacts) == 1
    assert output.metadata.failed_artifacts[0].code == "no_extractable_content"

    pdf_doc = next(document for document in output.documents if document.document_id == "pdf-1")
    assert pdf_doc.status == DocumentStatus.PARTIAL
    assert pdf_doc.confidence == 0.6
    assert pdf_doc.sections[0].source_format == "pdf"
    assert pdf_doc.sections[0].content_type == SectionContentType.TEXT

    spreadsheet_doc = next(document for document in output.documents if document.document_id == "sheet-1")
    assert spreadsheet_doc.status == DocumentStatus.PARSED
    assert spreadsheet_doc.confidence == 0.8
    assert spreadsheet_doc.sections[0].content_type == SectionContentType.TABLE
    assert spreadsheet_doc.sections[0].extracted_data["rows"][0]["name"] == "A"

    parsed_doc = next(document for document in output.documents if document.document_id == "parsed-1")
    assert parsed_doc.sections[0].page == 2
    assert parsed_doc.sections[0].timeframe.fiscal_year == 2024
    assert parsed_doc.sections[0].content_type == SectionContentType.STRUCTURED

    missing_keys = {item.key for item in output.metadata.missing_inputs}
    assert "cash_flow_statement" in missing_keys
    assert "ar_aging_report" in missing_keys
    assert "balance_sheet" not in missing_keys


def test_ingest_and_persist_document_payloads_stores_reloadable_artifacts() -> None:
    repo_root = Path("backend/.test-artifacts/ingestion-service")
    shutil.rmtree(repo_root, ignore_errors=True)
    repository = FileSystemAnalysisArtifactRepository(repo_root)

    try:
        output = ingest_and_persist_document_payloads(
            [
                {
                    "id": "doc-1",
                    "fileName": "pnl.pdf",
                    "documentType": "profit_and_loss",
                    "mimeType": "application/pdf",
                    "sections": [
                        {
                            "sectionId": "pnl-2024",
                            "page": 2,
                            "rawText": "Revenue 1200000",
                            "extractedData": {"revenue": 1200000},
                            "confidence": 0.9,
                        }
                    ],
                }
            ],
            analysis_id=ANALYSIS_ID,
            repository=repository,
        )

        assert output.metadata.analysis_id == ANALYSIS_ID
        assert len(output.metadata.artifact_refs) == 1
        assert output.metadata.artifact_refs[0].storage_kind == ArtifactStorageKind.FILESYSTEM

        stored = repository.load_ingestion_artifacts(ANALYSIS_ID)

        assert stored is not None
        assert stored.analysis_id == ANALYSIS_ID
        assert stored.ingestion_output.metadata.analysis_id == ANALYSIS_ID
        assert stored.document_inventory[0].document_id == "doc-1"
        assert stored.document_inventory[0].confidence == 0.9
        assert stored.evidence_index[0].section_id == "pnl-2024"
        assert stored.evidence_index[0].extracted_fields["revenue"] == 1200000
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)
