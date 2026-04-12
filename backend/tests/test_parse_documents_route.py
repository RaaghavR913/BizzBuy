from __future__ import annotations

import asyncio
import shutil
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from app.api.routes.parse_documents import parse_documents_route


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
