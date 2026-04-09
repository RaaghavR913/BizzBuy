from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from app.agents.claude_client import call_agent
from app.agents.deterministic import (
    AGENT_DISPLAY_NAMES,
    SBA_DEFAULTS,
    compute_ar_metrics,
    compute_customer_metrics,
    compute_financial_metrics,
    compute_lease_metrics,
    compute_ops_metrics,
    compute_sba_lending,
    compute_synthesis_metrics,
    compute_tax_metrics,
    infer_business_context,
)
from app.agents.prompts import (
    AR_COLLECTIONS_PROMPT,
    CUSTOMER_CONCENTRATION_PROMPT,
    DOCUMENT_INGESTION_PROMPT,
    FINANCIAL_ANALYSIS_PROMPT,
    LEASE_CONTRACT_PROMPT,
    LENDING_AFFORDABILITY_PROMPT,
    MARKET_MACRO_PROMPT,
    OPERATIONS_TRANSFERABILITY_PROMPT,
    SYNTHESIS_REPORT_PROMPT,
    TAX_COMPLIANCE_PROMPT,
)
from app.agents.registry import AGENT_REGISTRY
from app.agents.schemas import (
    ARCollectionsOutput,
    AgentErrorPayload,
    AgentResult,
    CustomerConcentrationOutput,
    FinancialAnalysisOutput,
    IngestionOutput,
    LeaseContractOutput,
    LendingAffordabilityOutput,
    MarketMacroOutput,
    OpsTransferabilityOutput,
    Recommendation,
    SynthesisReportOutput,
    TaxComplianceOutput,
)


def _relevant_sections(ingestion_output: IngestionOutput, document_types: set[str]) -> list:
    sections = []
    for doc in ingestion_output.documents:
        if doc.document_type.value in document_types:
            sections.extend(doc.sections)
    return sections


def _raw_data_summary(ingestion_output: IngestionOutput, document_types: set[str]) -> str:
    summaries = []
    for doc in ingestion_output.documents:
        if doc.document_type.value not in document_types:
            continue
        section_summaries = [
            f"  [FY{section.timeframe.fiscal_year or 'unknown'}] {json.dumps(section.extracted_data, default=str)}"
            for section in doc.sections
        ]
        summaries.append(f"### {doc.file_name} ({doc.document_type.value})\n" + "\n".join(section_summaries))
    return "\n\n".join(summaries)


def _raw_text_summary(ingestion_output: IngestionOutput, document_types: set[str]) -> str:
    chunks = []
    for doc in ingestion_output.documents:
        if doc.document_type.value not in document_types:
            continue
        for section in doc.sections:
            if section.raw_text:
                chunks.append(section.raw_text)
    return "\n".join(chunks)


def run_document_ingestion(documents: list[dict[str, Any]]) -> AgentResult[IngestionOutput]:
    config = AGENT_REGISTRY["document-ingestion"]
    if not documents:
        return AgentResult(
            status="success",
            data=IngestionOutput(
                documents=[],
                metadata={
                    "total_documents": 0,
                    "successfully_parsed": 0,
                    "failed_documents": [],
                    "warnings": ["No documents were provided for ingestion."],
                },
            ),
        )
    user_message = f"Extract data from these documents: {documents}"
    return call_agent(config, DOCUMENT_INGESTION_PROMPT, user_message, IngestionOutput)


def run_financial_analysis(ingestion_output: IngestionOutput) -> AgentResult[FinancialAnalysisOutput]:
    config = AGENT_REGISTRY["financial-analysis"]
    relevant_doc_types = {"profit_and_loss", "balance_sheet", "cash_flow_statement"}
    sections = _relevant_sections(ingestion_output, relevant_doc_types)
    metrics = compute_financial_metrics(sections)
    warning = ""
    if metrics["data_years_available"] == 0:
        warning = (
            "\n\nWARNING: No profit and loss, balance sheet, or cash flow documents were found. "
            "All financial fields should reflect the missing data and confidence should be low."
        )
    user_message = (
        "## Pre-Computed Financial Metrics\n"
        + json.dumps(metrics, indent=2, default=str)
        + "\n\n## Raw Extracted Financial Data\n"
        + (_raw_data_summary(ingestion_output, relevant_doc_types) or "(No financial documents found)")
        + warning
    )
    return call_agent(config, FINANCIAL_ANALYSIS_PROMPT, user_message, FinancialAnalysisOutput)


def run_tax_compliance(ingestion_output: IngestionOutput) -> AgentResult[TaxComplianceOutput]:
    config = AGENT_REGISTRY["tax-compliance"]
    relevant_doc_types = {"tax_return_1120s", "tax_return_1040", "tax_return_schedule_c", "profit_and_loss"}
    metrics = compute_tax_metrics(_relevant_sections(ingestion_output, relevant_doc_types))
    if not metrics["has_tax_returns"]:
        user_message = (
            "## Pre-Computed Tax Metrics\n"
            + json.dumps(metrics, indent=2, default=str)
            + "\n\n## Raw Extracted Data\n(No tax returns found in the document package)\n\n"
            + "WARNING: No tax return documents were found. Confidence should be low, unreported income risk should be high, "
            + "and the summary should state that tax returns must be obtained before close."
        )
        return call_agent(config, TAX_COMPLIANCE_PROMPT, user_message, TaxComplianceOutput)

    user_message = (
        "## Pre-Computed Tax Metrics\n"
        + json.dumps(metrics, indent=2, default=str)
        + "\n\n## Raw Extracted Data\n"
        + _raw_data_summary(ingestion_output, relevant_doc_types)
    )
    return call_agent(config, TAX_COMPLIANCE_PROMPT, user_message, TaxComplianceOutput)


def run_ar_collections(ingestion_output: IngestionOutput) -> AgentResult[ARCollectionsOutput]:
    config = AGENT_REGISTRY["ar-collections"]
    relevant_doc_types = {"ar_aging_report", "profit_and_loss"}
    metrics = compute_ar_metrics(_relevant_sections(ingestion_output, relevant_doc_types))
    if not metrics["has_ar_data"]:
        user_message = (
            "## Pre-Computed AR Metrics\n"
            + json.dumps(metrics, indent=2, default=str)
            + "\n\n## Raw Extracted Data\n(No AR aging report found in the document package)\n\n"
            + "WARNING: No AR aging report was provided. This may mean the business has no receivables or the diligence package is incomplete."
        )
        return call_agent(config, AR_COLLECTIONS_PROMPT, user_message, ARCollectionsOutput)

    user_message = (
        "## Pre-Computed AR Metrics\n"
        + json.dumps(metrics, indent=2, default=str)
        + "\n\n## Raw Extracted AR Data\n"
        + (_raw_data_summary(ingestion_output, {"ar_aging_report"}) or "(No AR aging report found)")
    )
    return call_agent(config, AR_COLLECTIONS_PROMPT, user_message, ARCollectionsOutput)


def run_customer_concentration(ingestion_output: IngestionOutput) -> AgentResult[CustomerConcentrationOutput]:
    config = AGENT_REGISTRY["customer-concentration"]
    metrics = compute_customer_metrics(ingestion_output)
    user_message = (
        (
            "## Data Availability\nNo customer list was found in the provided documents. Customer concentration analysis cannot be fully performed.\n\n"
            if not metrics["customers"]
            else "## Pre-Computed Concentration Metrics\n" + json.dumps(metrics, indent=2, default=str) + "\n\n"
        )
        + "## Raw Document Data\n"
        + (_raw_text_summary(ingestion_output, {"customer_list", "contract"}) or "No customer list found")
    )
    return call_agent(config, CUSTOMER_CONCENTRATION_PROMPT, user_message, CustomerConcentrationOutput)


def run_ops_transferability(ingestion_output: IngestionOutput) -> AgentResult[OpsTransferabilityOutput]:
    config = AGENT_REGISTRY["operations-transferability"]
    metrics = compute_ops_metrics(ingestion_output)
    user_message = (
        (
            "## Data Availability\nNo operational documents were found in the provided package. "
            "Assess with low confidence and note the missing roster, insurance, equipment, or license data.\n\n"
            if not metrics["has_operational_docs"]
            else ""
        )
        + "## Pre-Computed Operational Metrics\n"
        + json.dumps(metrics, indent=2, default=str)
        + "\n\n## Raw Document Data\n"
        + (_raw_text_summary(ingestion_output, {"employee_roster", "insurance_policy", "equipment_list", "other"}) or "No operational documents found")
    )
    return call_agent(config, OPERATIONS_TRANSFERABILITY_PROMPT, user_message, OpsTransferabilityOutput)


def run_lease_contract(ingestion_output: IngestionOutput) -> AgentResult[LeaseContractOutput]:
    config = AGENT_REGISTRY["lease-contract"]
    metrics = compute_lease_metrics(ingestion_output)
    user_message = (
        (
            "## Data Availability\nNo lease or contract documents were found. "
            "Treat the missing lease package as a material diligence risk and note the very low confidence.\n\n"
            if not metrics["has_lease"] and not metrics["has_contracts"]
            else ""
        )
        + "## Pre-Computed Lease & Contract Metrics\n"
        + json.dumps(metrics, indent=2, default=str)
        + "\n\n## Raw Document Data\n"
        + (_raw_text_summary(ingestion_output, {"lease_agreement", "contract", "other"}) or "No lease or contracts found")
    )
    return call_agent(config, LEASE_CONTRACT_PROMPT, user_message, LeaseContractOutput)


def run_market_macro(
    ingestion_output: IngestionOutput,
    business_type: str | None = None,
    location: str | None = None,
) -> AgentResult[MarketMacroOutput]:
    config = AGENT_REGISTRY["market-macro"]
    inferred = infer_business_context(ingestion_output)
    effective_business_type = business_type or inferred["business_type"] or "Unknown (infer from documents)"
    effective_location = location or inferred["location"] or "Unknown (infer from documents)"
    indicators = []
    if inferred["revenue_range"]:
        indicators.append(f"Annual revenue: ~{inferred['revenue_range']}")
    if inferred["employee_count"]:
        indicators.append(f"Employees: {inferred['employee_count']}")
    user_message = (
        "Please assess current market conditions, industry trends, and macroeconomic factors relevant to acquiring this business.\n\n"
        f"## Business Profile\n- Business Type / Industry: {effective_business_type}\n- Location: {effective_location}\n"
        + (f"\n## Financial Indicators\n- " + "\n- ".join(indicators) if indicators else "")
        + "\n\n## Uploaded Documents\n"
        + "\n".join(f"- {doc.file_name} ({doc.document_type.value})" for doc in ingestion_output.documents)
        + "\n\n## Context From Documents\n"
        + (_raw_text_summary(ingestion_output, {doc.document_type.value for doc in ingestion_output.documents})[:12000] or "No document text available")
    )
    return call_agent(config, MARKET_MACRO_PROMPT, user_message, MarketMacroOutput)


def run_lending_affordability(
    ingestion_output: IngestionOutput,
    financial_analysis_output: FinancialAnalysisOutput,
    asking_price: float | None = None,
) -> AgentResult[LendingAffordabilityOutput]:
    config = AGENT_REGISTRY["lending-affordability"]
    sde = financial_analysis_output.profitability.sde
    if not sde or sde <= 0:
        return AgentResult(
            status="error",
            error=AgentErrorPayload(
                agent_name=config.name,
                error_type="validation",
                message="Lending analysis could not be completed because financial analysis did not produce a valid SDE figure.",
                timestamp=datetime.now(timezone.utc).isoformat(),
                retry_count=0,
            ),
        )

    base_asking_price = asking_price if asking_price and asking_price > 0 else round(sde * 3.0)
    base_case = compute_sba_lending(sde, base_asking_price)
    scenarios = [
        {"multiple": multiple, "asking_price": round(sde * multiple), "metrics": compute_sba_lending(sde, round(sde * multiple))}
        for multiple in (2.5, 3.0, 3.5)
    ]
    user_message = (
        "## Financial Analysis Summary\n"
        + json.dumps(financial_analysis_output.model_dump(mode="json"), indent=2, default=str)
        + "\n\n## Pre-Computed Lending Figures\n"
        + json.dumps(
            {
                "asking_price_used": base_asking_price,
                "asking_price_provided": asking_price,
                "base_case": base_case,
                "scenario_analysis": scenarios,
                "documents": [doc.file_name for doc in ingestion_output.documents],
                "sba_defaults": SBA_DEFAULTS,
            },
            indent=2,
            default=str,
        )
        + "\n\nUse the pre-computed figures above. If no asking price was provided, treat the 3.0x SDE case as the base case and use the other scenarios as bounds."
    )
    return call_agent(config, LENDING_AFFORDABILITY_PROMPT, user_message, LendingAffordabilityOutput)


def run_synthesis_report(agent_results: Dict[str, Any]) -> AgentResult[SynthesisReportOutput]:
    config = AGENT_REGISTRY["synthesis-report"]
    metrics = compute_synthesis_metrics(agent_results)
    recommendation = Recommendation.CONDITIONAL_BUY
    if metrics["composite_score"] <= 20:
        recommendation = Recommendation.STRONG_BUY
    elif metrics["composite_score"] <= 40:
        recommendation = Recommendation.BUY
    elif metrics["composite_score"] <= 60:
        recommendation = Recommendation.CONDITIONAL_BUY
    elif metrics["composite_score"] <= 80:
        recommendation = Recommendation.CAUTION
    else:
        recommendation = Recommendation.DO_NOT_BUY

    user_message = (
        "## Pre-Computed Assessment Metrics\n"
        + json.dumps(
            {
                "composite_score": metrics["composite_score"],
                "completeness": metrics["completeness"],
                "successful_agents": metrics["successful_agents"],
                "failed_agents": metrics["failed_agents"],
                "red_flags": metrics["red_flags"],
                "green_flags": metrics["green_flags"],
                "section_summaries": {
                    AGENT_DISPLAY_NAMES[key]: value for key, value in metrics["section_summaries"].items()
                },
                "suggested_recommendation_band": recommendation.value,
            },
            indent=2,
            default=str,
        )
    )
    return call_agent(config, SYNTHESIS_REPORT_PROMPT, user_message, SynthesisReportOutput)
