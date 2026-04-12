import shutil
from pathlib import Path

from app.agents.schemas import ClarificationAnswer, ClarificationAnswerType, ClarificationCategory
from app.services.analysis_repository import FileSystemAnalysisArtifactRepository
from app.services.clarification_service import build_clarification_evidence, store_clarification_answers
from app.services.ingestion_service import ingest_and_persist_document_payloads


def test_store_clarification_answers_persists_as_supplemental_artifacts() -> None:
    repo_root = Path("backend/.test-artifacts/clarification-service")
    shutil.rmtree(repo_root, ignore_errors=True)
    repository = FileSystemAnalysisArtifactRepository(repo_root)

    try:
        ingest_and_persist_document_payloads(
            [
                {
                    "id": "doc-1",
                    "fileName": "pnl.pdf",
                    "documentType": "profit_and_loss",
                    "mimeType": "application/pdf",
                    "text": "Revenue 1200000",
                }
            ],
            analysis_id="analysis-clarifications",
            repository=repository,
        )

        saved = store_clarification_answers(
            "analysis-clarifications",
            [
                ClarificationAnswer(
                    question_id="customer-top-revenue",
                    prompt="Largest customer revenue share?",
                    category=ClarificationCategory.CUSTOMER_CONCENTRATION,
                    answer_type=ClarificationAnswerType.PERCENT,
                    value=35,
                    value_label="35%",
                    related_document_types=["customer_list"],
                    legacy_field_path="customerConcentration.topCustomerRevenuePercent",
                )
            ],
            repository=repository,
        )

        assert len(saved) == 1
        assert saved[0].source == "user_asserted"
        assert saved[0].supplemental is True

        artifacts = repository.load_ingestion_artifacts("analysis-clarifications")
        assert artifacts is not None
        assert artifacts.clarifications[0].question_id == "customer-top-revenue"
        assert artifacts.clarifications[0].confidence == 0.6
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)


def test_build_clarification_evidence_marks_answers_as_lower_confidence() -> None:
    evidence = build_clarification_evidence(
        [
            ClarificationAnswer(
                question_id="pending-liabilities",
                prompt="Any pending liabilities outside the uploaded package?",
                category=ClarificationCategory.FINANCIAL_RISK,
                answer_type=ClarificationAnswerType.BOOLEAN,
                value=True,
                value_label="Yes",
                related_document_types=["tax_return_1120s"],
                legacy_field_path="financialRisk.pendingLiabilities",
            )
        ],
        analysis_id="analysis-clarifications",
    )

    assert len(evidence) == 1
    assert evidence[0].document_id == "clarifications:analysis-clarifications"
    assert evidence[0].confidence == 0.6
    assert evidence[0].extracted_fields["supplemental"] is True
    assert evidence[0].extracted_fields["source"] == "user_asserted"
