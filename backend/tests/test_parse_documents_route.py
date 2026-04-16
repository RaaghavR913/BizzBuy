from __future__ import annotations

import asyncio
import json
import shutil
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.parse_documents import parse_documents_route
from app.services.intake_service import extract_xlsx_workbook
from app.services.section_kind import infer_sheet_kinds


def test_parse_documents_route_returns_pipeline_seed_documents_and_analysis_id(monkeypatch) -> None:
    artifact_dir = Path("backend/.test-artifacts/parse-documents-route")
    shutil.rmtree(artifact_dir, ignore_errors=True)
    monkeypatch.setenv("BIZBUY_ARTIFACT_DIR", str(artifact_dir))

    upload = UploadFile(
        filename="seller-pnl.txt",
        file=BytesIO(b"Revenue 1200000\nSDE 300000"),
        headers={"content-type": "text/plain"},
    )

    try:
        response = asyncio.run(
            parse_documents_route(
                files=[upload],
                file_types='["profit_and_loss"]',
            )
        )
        payload = response.model_dump(by_alias=True)

        assert payload["success"] is True
        assert payload["analysisId"]
        assert len(payload["pipelineDocuments"]) == 1
        assert payload["pipelineDocuments"][0]["document_type"] == "profit_and_loss"
        assert payload["pipelineDocuments"][0]["sections"][0]["raw_text"].startswith("Revenue 1200000")
        assert payload["extractedData"]["dataCompleteness"] == 1
    finally:
        shutil.rmtree(artifact_dir, ignore_errors=True)


def test_parse_documents_route_accepts_frontend_filetypes_alias_multipart(monkeypatch) -> None:
    artifact_dir = Path("backend/.test-artifacts/filetypes-alias")
    shutil.rmtree(artifact_dir, ignore_errors=True)
    monkeypatch.setenv("BIZBUY_ARTIFACT_DIR", str(artifact_dir))

    try:
        client = TestClient(app)
        response = client.post(
            "/api/parse-documents",
            files={"files": ("seller-pnl.txt", b"Revenue 1200000\nNet Income 300000", "text/plain")},
            data={"fileTypes": '["profit_and_loss"]'},
        )
        payload = response.json()

        assert response.status_code == 200
        assert payload["success"] is True
        assert payload["pipelineDocuments"][0]["document_type"] == "profit_and_loss"
        assert payload["pipelineDocuments"][0]["declared_type"] == "profit_and_loss"
    finally:
        shutil.rmtree(artifact_dir, ignore_errors=True)


def test_peakair_workbook_sheet_kind_inference() -> None:
    sample_root = Path(__file__).resolve().parents[2] / "sample company1"
    workbook = sample_root / "PeakAir_Financials.xlsx"
    sheets, notes = extract_xlsx_workbook(workbook.read_bytes())

    assert notes == []
    assert infer_sheet_kinds(sheets) == [
        "profit_and_loss",
        "balance_sheet",
        "sde_summary",
    ]


def test_parse_documents_reuses_cached_ocr_text_by_file_hash(monkeypatch) -> None:
    artifact_dir = Path("backend/.test-artifacts/parse-documents-ocr-cache")
    shutil.rmtree(artifact_dir, ignore_errors=True)
    monkeypatch.setenv("BIZBUY_ARTIFACT_DIR", str(artifact_dir))
    file_hash = "a" * 64
    ocr_dir = artifact_dir / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = ocr_dir / f"{file_hash}.json"
    artifact_path.write_text(
        json.dumps(
            {
                "filename": "scanned.pdf",
                "file_hash": file_hash,
                "page_count": 1,
                "classification": {
                    "document_type": "pnl_income_statement",
                    "confidence": 0.91,
                    "reasoning": "cached",
                    "detected_period": "FY 2024",
                },
                "pages": [{"page_number": 1, "markdown": "Cached OCR Revenue 100000", "image_refs": []}],
                "full_markdown": "Cached OCR Revenue 100000",
                "ocr_model": "mistral-ocr-2512",
                "processing_time_ms": 1,
                "cost_usd": 0.002,
            }
        ),
        encoding="utf-8",
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/api/parse-documents",
            files={"files": ("scanned.pdf", b"%PDF cached text comes from artifact", "application/pdf")},
            data={
                "fileTypes": '["profit_and_loss"]',
                "fileHashes": json.dumps([file_hash]),
                "ocrArtifactRefs": json.dumps([str(artifact_path)]),
            },
        )
        payload = response.json()

        assert response.status_code == 200
        section = payload["pipelineDocuments"][0]["sections"][0]
        assert section["raw_text"] == "Cached OCR Revenue 100000"
        assert "Reused cached OCR artifact text for ingestion." in payload["pipelineDocuments"][0]["notes"]
    finally:
        shutil.rmtree(artifact_dir, ignore_errors=True)


def test_peakair_parse_documents_seeds_review_financial_data(monkeypatch) -> None:
    artifact_dir = Path("backend/.test-artifacts/peakair-parse-documents")
    shutil.rmtree(artifact_dir, ignore_errors=True)
    monkeypatch.setenv("BIZBUY_ARTIFACT_DIR", str(artifact_dir))
    sample_root = Path(__file__).resolve().parents[2] / "sample company1"
    files_to_upload = [
        ("PeakAir_CustomerList_PPE.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("PeakAir_EmployeeContracts.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("PeakAir_Financials.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("PeakAir_LeaseAgreement.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("PeakAir_TaxReturns.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]
    file_types = [
        "customer_list",
        "employee_roster",
        "profit_and_loss",
        "lease_agreement",
        "tax_return_schedule_c",
    ]

    opened_files = []
    try:
        multipart_files = []
        for filename, mime_type in files_to_upload:
            handle = (sample_root / filename).open("rb")
            opened_files.append(handle)
            multipart_files.append(("files", (filename, handle, mime_type)))

        client = TestClient(app)
        response = client.post(
            "/api/parse-documents",
            files=multipart_files,
            data={"fileTypes": json.dumps(file_types)},
        )
        payload = response.json()

        assert response.status_code == 200
        missing_keys = {
            note
            for note in payload["extractedData"]["parsingNotes"]
            if note.startswith("Missing ")
        }
        assert all("profit_and_loss" not in note for note in missing_keys)
        assert all("balance_sheet" not in note for note in missing_keys)
        assert all("tax_returns" not in note for note in missing_keys)
        assert payload["extractedData"]["parsingNotes"] == []

        financials_doc = next(document for document in payload["pipelineDocuments"] if document["file_name"] == "PeakAir_Financials.xlsx")
        sections_by_name = {section["section_name"]: section for section in financials_doc["sections"]}
        assert financials_doc["document_type"] == "profit_and_loss"
        assert sections_by_name["P&L Statement"]["document_type"] == "profit_and_loss"
        assert sections_by_name["P&L Statement"]["section_kind"] == "profit_and_loss"
        assert sections_by_name["Balance Sheet"]["document_type"] == "balance_sheet"
        assert sections_by_name["Balance Sheet"]["section_kind"] == "balance_sheet"
        assert sections_by_name["SDE Summary"]["document_type"] == "profit_and_loss"
        assert sections_by_name["SDE Summary"]["section_kind"] == "sde_summary"

        income_statement = payload["extractedData"]["incomeStatement"]
        balance_sheet = payload["extractedData"]["balanceSheet"]
        loan_terms = payload["extractedData"]["loanTerms"]

        assert income_statement["revenue"] == 983000
        assert income_statement["netIncome"] == 102904
        assert income_statement["cogs"] == 520990
        assert income_statement["sde"] == 346045
        assert income_statement["interestExpense"] == 5880
        assert balance_sheet["totalAssets"] == 313300
        assert balance_sheet["totalLiabilities"] == 174000
        assert balance_sheet["currentAssets"] == 173500
        assert balance_sheet["accountsReceivable"] == 98000
        assert loan_terms["askingPrice"] == 1150000
    finally:
        for handle in opened_files:
            handle.close()
        shutil.rmtree(artifact_dir, ignore_errors=True)
