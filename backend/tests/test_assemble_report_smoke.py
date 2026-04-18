"""Smoke test: assemble_summary_report must not raise given real ingestion data with spreadsheet rows.

Uses the ingestion_artifacts.json from a known-good artifact directory. If the file is absent
(e.g. fresh checkout, CI without artifacts) the test is automatically skipped.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from app.agents.schemas import (
    AgentEnvelope,
    AgentExecutionStatus,
    AgentName,
    AgentResult,
    DeterministicScorecard,
    DeterministicTag,
    IngestionMetadata,
    IngestionOutput,
    NormalizedMetric,
    PipelineMetadata,
    PipelineStageMetric,
    SynthesisReportOutput,
    DocumentType,
    Timeframe,
    DocumentInfo,
    DocumentSection,
)
from app.models.schemas import ReportOutputV2
from app.services.report_assembler import assemble_summary_report

# Path to the artifact we use for the smoke test.
_ARTIFACTS_ROOT = pathlib.Path(__file__).parent.parent / "backend" / ".artifacts"
_PREFERRED_ARTIFACT = _ARTIFACTS_ROOT / "84057e63-96d8-470e-8eb3-ad4fc88cb34e" / "ingestion_artifacts.json"


def _find_artifact() -> pathlib.Path | None:
    if _PREFERRED_ARTIFACT.exists():
        return _PREFERRED_ARTIFACT
    for candidate in sorted(_ARTIFACTS_ROOT.glob("*/ingestion_artifacts.json")):
        return candidate
    return None


def _minimal_ingestion_output_with_rows() -> IngestionOutput:
    """Return a minimal IngestionOutput with spreadsheet rows to reproduce the original bug."""
    return IngestionOutput(
        documents=[
            DocumentInfo(
                document_id="doc-row-test",
                file_name="financial.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                document_type=DocumentType.PROFIT_AND_LOSS,
                sections=[
                    DocumentSection(
                        document_id="doc-row-test",
                        document_type=DocumentType.PROFIT_AND_LOSS,
                        section_kind="profit_and_loss",
                        section_name="P&L",
                        timeframe=Timeframe(fiscal_year=2024),
                        extracted_data={
                            "rows": [
                                {"row_index": 1, "A": "Revenue", "B": 500000},
                                {"row_index": 2, "A": "COGS", "B": 200000},
                            ],
                            "total_revenue": 500000,
                        },
                        raw_text="Revenue | 500000\nCOGS | 200000",
                        confidence=0.9,
                        source_format="spreadsheet",
                    )
                ],
            )
        ],
        metadata=IngestionMetadata(
            total_documents=1,
            successfully_parsed=1,
            failed_documents=[],
            warnings=[],
            analysis_id="smoke-test",
        ),
    )


def _stub_agent_results() -> dict[str, AgentResult]:
    """Return skipped AgentResult stubs for every agent name."""
    return {name.value: AgentResult(status="skipped", data=None) for name in AgentName}


def _stub_scorecard() -> DeterministicScorecard:
    return DeterministicScorecard(
        overall_risk_score=60,
        overall_recommendation="caution",
        technical_scorecards=[],
        deal_breakers=[],
        conflicts=[],
        completeness_score=0.5,
        confidence_score=0.5,
        validated_metrics={},
    )


def _stub_synthesis_result() -> AgentResult:
    synthesis = SynthesisReportOutput.model_validate(
        {
            "executive_summary": "Smoke-test executive summary.",
            "red_flags": [],
            "green_flags": [],
            "section_summaries": {
                "financial": {"score": 5, "summary": "OK", "top_risks": []},
                "tax": {"score": 5, "summary": "OK", "top_risks": []},
                "ar": {"score": 5, "summary": "OK", "top_risks": []},
                "customer": {"score": 5, "summary": "OK", "top_risks": []},
                "operations": {"score": 5, "summary": "OK", "top_risks": []},
                "lease": {"score": 5, "summary": "OK", "top_risks": []},
                "market": {"score": 5, "summary": "OK", "top_risks": []},
                "lending": {"score": 5, "summary": "OK", "top_risks": []},
            },
            "next_steps": [],
            "deal_terms_suggestion": "Use diligence conditions before advancing.",
        }
    )
    return AgentResult(status="success", data=synthesis)


def _stub_metadata() -> PipelineMetadata:
    return PipelineMetadata(
        started_at="2024-01-01T00:00:00Z",
        completed_at="2024-01-01T00:01:00Z",
        total_tokens=100,
        estimated_cost=0.001,
        total_latency_ms=1000,
        stage_metrics={},
    )


# ---- Tests ----

def test_assemble_with_row_data_does_not_raise():
    """assemble_summary_report must return a valid ReportOutputV2 even when ingestion
    data contains spreadsheet rows (the original 292-error regression)."""
    result = assemble_summary_report(
        ingestion_output=_minimal_ingestion_output_with_rows(),
        agent_results=_stub_agent_results(),
        scorecard=_stub_scorecard(),
        synthesis_result=_stub_synthesis_result(),
        metadata=_stub_metadata(),
        include_deep_review=True,
    )

    # Must be parseable by the strict ReportOutputV2 schema
    assert isinstance(result, ReportOutputV2)
    assert result.summary.overview  # synthesis text must flow through
    # All extracted_fields on evidence refs must be primitives
    for ref in result.deep_review.evidence_index:
        for key, val in ref.extracted_fields.items():
            assert val is None or isinstance(val, (str, int, float, bool)), (
                f"Non-primitive in ref {ref.document_id} key '{key}': {type(val)}"
            )


@pytest.mark.skipif(not _find_artifact(), reason="No ingestion_artifacts.json found in .artifacts/")
def test_assemble_from_real_artifact():
    """Load a real ingestion artifact and confirm assembly succeeds end-to-end."""
    artifact_path = _find_artifact()
    assert artifact_path is not None

    raw = json.loads(artifact_path.read_text())
    ingestion_output = IngestionOutput.model_validate(raw["ingestion_output"])

    result = assemble_summary_report(
        ingestion_output=ingestion_output,
        agent_results=_stub_agent_results(),
        scorecard=_stub_scorecard(),
        synthesis_result=_stub_synthesis_result(),
        metadata=_stub_metadata(),
        include_deep_review=True,
    )

    assert isinstance(result, ReportOutputV2)
    assert result.summary.overview
    # Every extracted_field on every evidence ref must be a primitive
    for ref in result.deep_review.evidence_index:
        for key, val in ref.extracted_fields.items():
            assert val is None or isinstance(val, (str, int, float, bool)), (
                f"Non-primitive in ref {ref.document_id} key '{key}': {type(val)}"
            )
