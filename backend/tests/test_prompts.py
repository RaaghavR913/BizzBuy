from __future__ import annotations

import pytest

from app.agents.prompts import (
    AR_COLLECTIONS_PROMPT,
    CUSTOMER_CONCENTRATION_PROMPT,
    FINANCIAL_ANALYSIS_PROMPT,
    LEASE_CONTRACT_PROMPT,
    LENDING_AFFORDABILITY_PROMPT,
    MARKET_MACRO_PROMPT,
    OPERATIONS_TRANSFERABILITY_PROMPT,
    SYNTHESIS_REPORT_PROMPT,
    TAX_COMPLIANCE_PROMPT,
)


SPECIALIST_PROMPTS = [
    ("financial", FINANCIAL_ANALYSIS_PROMPT, "FinancialAnalysisOutput"),
    ("tax", TAX_COMPLIANCE_PROMPT, "TaxComplianceOutput"),
    ("ar", AR_COLLECTIONS_PROMPT, "ARCollectionsOutput"),
    ("customer", CUSTOMER_CONCENTRATION_PROMPT, "CustomerConcentrationOutput"),
    ("operations", OPERATIONS_TRANSFERABILITY_PROMPT, "OpsTransferabilityOutput"),
    ("lease", LEASE_CONTRACT_PROMPT, "LeaseContractOutput"),
    ("market", MARKET_MACRO_PROMPT, "MarketMacroOutput"),
    ("lending", LENDING_AFFORDABILITY_PROMPT, "LendingAffordabilityOutput"),
]


@pytest.mark.parametrize(("agent_name", "prompt", "schema_name"), SPECIALIST_PROMPTS)
def test_specialist_prompts_include_downstream_compact_output_guidance(
    agent_name: str,
    prompt: str,
    schema_name: str,
) -> None:
    lowered = prompt.lower()

    assert "downstream synthesis agent" in lowered, agent_name
    assert "full specialist analysis" in lowered, agent_name
    assert "compact" in lowered, agent_name
    assert "high-signal" in lowered, agent_name
    assert "evidence-grounded" in lowered, agent_name
    assert "non-redundant" in lowered, agent_name
    assert "concrete numbers" in lowered, agent_name
    assert "ranked findings" in lowered, agent_name
    assert "do not sacrifice analytical quality" in lowered, agent_name
    assert "lower confidence rather than compensating with extra prose" in lowered, agent_name
    assert "preserve the exact schema and every required field" in lowered, agent_name
    assert schema_name in prompt, agent_name


@pytest.mark.parametrize(("agent_name", "prompt", "_schema_name"), SPECIALIST_PROMPTS)
def test_specialist_prompts_emphasize_decision_relevant_non_overlapping_findings(
    agent_name: str,
    prompt: str,
    _schema_name: str,
) -> None:
    lowered = prompt.lower()

    assert "decision-relevant" in lowered, agent_name
    assert "prefer fewer, stronger findings" in lowered, agent_name
    assert "severity" in lowered, agent_name
    assert "material" in lowered, agent_name


def test_synthesis_prompt_assumes_compact_specialist_inputs_without_reinflating() -> None:
    lowered = SYNTHESIS_REPORT_PROMPT.lower()

    assert "compact specialist analyses" in lowered
    assert "do not re-expand" in lowered
    assert "write decisively, compactly, and with high signal" in lowered
    assert "combine overlapping specialist points instead of repeating them" in lowered
    assert "deterministic scorecard as read-only truth" in lowered
    assert "SynthesisReportOutput" in SYNTHESIS_REPORT_PROMPT
