from __future__ import annotations

import base64
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable
from uuid import uuid4

from app.agents.openrouter_client import call_agent
from app.agents.context_builders import (
    build_ar_user_message,
    build_customer_user_message,
    build_financial_user_message,
    build_lease_user_message,
    build_market_user_message,
    build_ops_user_message,
    build_synthesis_user_message,
    build_tax_user_message,
    compact_json,
    describe_user_message,
)
from app.agents.evidence_utils import build_evidence_fields
from app.agents.mistral_ocr_client import (
    IngestionResult,
    MistralOCRError,
    ocr_document,
)
from app.agents.deterministic import (
    SBA_DEFAULTS,
    SEVERITY_ORDER,
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
    AgentSource,
    AgentEnvelope,
    AgentErrorPayload,
    AgentExecutionStatus,
    AgentName,
    AgentResult,
    AnnualExpense,
    AnnualRevenue,
    BalanceSheet,
    CashFlow,
    CustomerConcentrationOutput,
    DeterministicTag,
    DocumentInfo,
    DocumentSection,
    DocumentStatus,
    DocumentType,
    EvidenceReference,
    ExpenseAnalysis,
    FinancialAnalysisOutput,
    FinancialRisk,
    FindingCategory,
    GreenFlag,
    IngestionMetadata,
    IngestionOutput,
    LeaseContractOutput,
    LendingAffordabilityOutput,
    MarketMacroOutput,
    MissingInput,
    NextStep,
    NormalizedFinding,
    NormalizedMetric,
    OpsTransferabilityOutput,
    Profitability,
    RedFlag,
    RevenueAnalysis,
    SectionSummaries,
    SectionSummary,
    SdeAddBack,
    DeterministicScorecard,
    SectionContentType,
    Severity,
    SynthesisReportOutput,
    TaxComplianceOutput,
    Timeframe,
    Trend,
)
from app.services.financial_data_extractor import AskingPriceEvidence, resolve_asking_price
from app.services.ingestion_service import ingest_and_persist_document_payloads


def _not_applicable_result(agent_name: str, message: str) -> AgentResult[Any]:
    """Return a not_applicable result without calling the LLM."""
    return AgentResult(
        status="not_applicable",
        error=AgentErrorPayload(
            agent_name=agent_name,
            error_type="not_applicable",
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            retry_count=0,
        ),
    )


def _relevant_sections(ingestion_output: IngestionOutput, document_types: set[str]) -> list:
    sections = []
    for doc in ingestion_output.documents:
        for section in doc.sections:
            if _section_matches(section, document_types, doc):
                sections.append(section)
    return sections


def _raw_data_summary(ingestion_output: IngestionOutput, document_types: set[str]) -> str:
    summaries = []
    for doc in ingestion_output.documents:
        for section in doc.sections:
            if not _section_matches(section, document_types, doc):
                continue
            label = section.section_name or section.section_id or "Section"
            kind = section.section_kind or "unknown"
            summaries.append(
                f"### {doc.file_name} / {label} ({section.document_type.value}, kind={kind})\n"
                f"[FY{section.timeframe.fiscal_year or 'unknown'}] {json.dumps(section.extracted_data, default=str)}"
            )
    return "\n\n".join(summaries)


def _raw_text_summary(ingestion_output: IngestionOutput, document_types: set[str]) -> str:
    chunks = []
    for doc in ingestion_output.documents:
        for section in doc.sections:
            if _section_matches(section, document_types, doc) and section.raw_text:
                chunks.append(section.raw_text)
    return "\n".join(chunks)


def _make_evidence_references(
    ingestion_output: IngestionOutput,
    document_types: Iterable[DocumentType | str],
    *,
    limit: int = 8,
) -> list[EvidenceReference]:
    allowed = {item.value if isinstance(item, DocumentType) else item for item in document_types}
    evidence: list[EvidenceReference] = []
    for doc in ingestion_output.documents:
        for section in doc.sections:
            if not _section_matches(section, allowed, doc):
                continue
            snippet = None
            if section.raw_text:
                snippet = section.raw_text.strip().replace("\n", " ")[:240] or None
            extracted_fields = build_evidence_fields(section)
            evidence.append(
                EvidenceReference(
                    document_id=doc.document_id,
                    file_name=doc.file_name,
                    section_id=section.section_id,
                    page=section.page or section.page_start,
                    snippet=snippet,
                    extracted_fields=extracted_fields,
                    confidence=section.confidence,
                )
            )
            if len(evidence) >= limit:
                return evidence
    return evidence


def _has_document_type(ingestion_output: IngestionOutput, *document_types: DocumentType) -> bool:
    wanted = {document_type.value for document_type in document_types}
    return any(
        doc.document_type.value in wanted or any(_section_matches(section, wanted, doc) for section in doc.sections)
        for doc in ingestion_output.documents
    )


def _section_type_value(section: DocumentSection, doc: DocumentInfo | None = None) -> str:
    if section.section_kind and section.section_kind in DocumentType._value2member_map_:
        return section.section_kind
    if section.document_type:
        return section.document_type.value
    if doc:
        return doc.document_type.value
    return DocumentType.OTHER.value


def _section_matches(section: DocumentSection, allowed: set[str], doc: DocumentInfo | None = None) -> bool:
    if section.section_kind and section.section_kind != DocumentType.OTHER.value:
        if section.section_kind == "sde_summary":
            return "sde_summary" in allowed
        return section.section_kind in allowed or section.document_type.value in allowed
    if section.document_type.value in allowed:
        return True
    return bool(doc and doc.document_type.value in allowed)


def _metric(
    value: float | int | str | bool | None,
    *,
    unit: str | None = None,
    confidence: float | None = None,
    evidence: list[EvidenceReference] | None = None,
) -> NormalizedMetric:
    return NormalizedMetric(
        value=value,
        unit=unit,
        confidence=confidence,
        evidence=list(evidence or []),
    )


def _missing_input(
    key: str,
    description: str,
    *,
    document_type: DocumentType | None = None,
    required: bool = True,
    reason: str | None = None,
) -> MissingInput:
    return MissingInput(
        key=key,
        description=description,
        document_type=document_type,
        required=required,
        reason=reason,
    )


def _missing_input_findings(
    agent_name: AgentName,
    missing_inputs: list[MissingInput],
    confidence: float,
) -> list[NormalizedFinding]:
    findings: list[NormalizedFinding] = []
    for missing_input in missing_inputs:
        findings.append(
            NormalizedFinding(
                finding_id=f"{agent_name.value}-missing-{missing_input.key}",
                source_agent=agent_name,
                category=FindingCategory.MISSING_DATA,
                severity=Severity.HIGH if missing_input.required else Severity.MEDIUM,
                title=missing_input.description,
                description=missing_input.reason or missing_input.description,
                deterministic_tags=[DeterministicTag.COMPLETENESS_PENALTY],
                confidence=confidence,
                missing_data=True,
            )
        )
    return findings


def _copy_result(result: AgentResult[Any], data: Any) -> AgentResult[Any]:
    return AgentResult(
        status=result.status,
        data=data,
        error=result.error,
        token_usage=result.token_usage,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        diagnostics=dict(result.diagnostics),
    )


def _call_llm_agent(
    config,
    system_prompt: str,
    user_message: str,
    schema_class,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    if diagnostic_context is None:
        return call_agent(config, system_prompt, user_message, schema_class)
    return call_agent(
        config,
        system_prompt,
        user_message,
        schema_class,
        diagnostic_context=diagnostic_context,
    )


def _map_financial_category(raw_category: str | None) -> FindingCategory:
    category = (raw_category or "").lower()
    if "cash" in category:
        return FindingCategory.CASH_FLOW
    if "working" in category or "liquidity" in category:
        return FindingCategory.WORKING_CAPITAL
    return FindingCategory.EARNINGS_QUALITY


def _map_customer_category(title: str, description: str) -> FindingCategory:
    combined = f"{title} {description}".lower()
    if "contract" in combined or "renew" in combined:
        return FindingCategory.CONTRACT_DURABILITY
    return FindingCategory.CUSTOMER_CONCENTRATION


def _map_ops_category(raw_category: str | None) -> FindingCategory:
    if "owner" in (raw_category or "").lower():
        return FindingCategory.OWNER_DEPENDENCE
    return FindingCategory.OPERATIONAL_TRANSFERABILITY


def _map_lease_category(title: str, description: str) -> FindingCategory:
    combined = f"{title} {description}".lower()
    if "lease" in combined or "assign" in combined:
        return FindingCategory.LEASE_TRANSFERABILITY
    return FindingCategory.CONTRACT_DURABILITY


def _wrap_specialist_output(
    *,
    agent_name: AgentName,
    result: AgentResult[Any],
    normalized_metrics: dict[str, NormalizedMetric],
    findings: list[NormalizedFinding],
    missing_inputs: list[MissingInput],
    evidence: list[EvidenceReference],
) -> AgentResult[Any]:
    if result.status != "success" or not result.data:
        return result

    domain_output = result.data
    confidence = float(getattr(domain_output, "confidence", 0.0) or 0.0)
    envelope = AgentEnvelope(
        agent_name=agent_name,
        status=AgentExecutionStatus.SUCCESS,
        summary=getattr(domain_output, "summary", None),
        confidence=getattr(domain_output, "confidence", None),
        overall_score=getattr(domain_output, "overall_score", None),
        normalized_metrics=normalized_metrics,
        findings=[*findings, *_missing_input_findings(agent_name, missing_inputs, confidence)],
        missing_inputs=missing_inputs,
        evidence=evidence,
        raw_domain_output=domain_output,
    )
    return _copy_result(result, envelope)


def _normalize_financial_output(
    ingestion_output: IngestionOutput,
    result: AgentResult[FinancialAnalysisOutput],
    metrics: dict[str, Any],
) -> AgentResult[Any]:
    evidence = _make_evidence_references(
        ingestion_output,
        [DocumentType.PROFIT_AND_LOSS, DocumentType.BALANCE_SHEET, DocumentType.CASH_FLOW_STATEMENT, "sde_summary"],
    )
    domain_output = result.data
    if not domain_output:
        return result

    most_recent_year = metrics.get("most_recent_year") or {}
    normalized_metrics = {
        "revenue_latest": _metric(most_recent_year.get("revenue"), unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "revenue_growth_yoy": _metric(
            metrics.get("revenue_growth_rates", [{}])[-1].get("rate") if metrics.get("revenue_growth_rates") else None,
            unit="ratio",
            confidence=domain_output.confidence,
            evidence=evidence,
        ),
        "gross_margin": _metric(metrics.get("gross_margin"), unit="ratio", confidence=domain_output.confidence, evidence=evidence),
        "ebitda": _metric(domain_output.profitability.ebitda, unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "ebitda_margin": _metric(metrics.get("ebitda_margin"), unit="ratio", confidence=domain_output.confidence, evidence=evidence),
        "sde_reported": _metric(metrics.get("sde", {}).get("reported_net_income"), unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "sde_validated_candidate": _metric(domain_output.profitability.sde, unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "working_capital": _metric(metrics.get("working_capital"), unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "cash_flow_net_income_divergence": _metric(
            metrics.get("cash_flow_vs_net_income_divergence"),
            unit="ratio",
            confidence=domain_output.confidence,
            evidence=evidence,
        ),
    }
    findings = [
        NormalizedFinding(
            finding_id=risk.id,
            source_agent=AgentName.FINANCIAL_ANALYSIS,
            category=_map_financial_category(risk.category),
            severity=risk.severity,
            title=risk.title,
            description=risk.description,
            deterministic_tags=[DeterministicTag.SDE_ADJUSTMENT] if risk.financial_impact else [],
            metric_impact={"financial_impact_usd": risk.financial_impact} if risk.financial_impact is not None else {},
            evidence=evidence,
            confidence=domain_output.confidence,
        )
        for risk in domain_output.risks
    ]
    missing_inputs: list[MissingInput] = []
    if not _has_document_type(ingestion_output, DocumentType.PROFIT_AND_LOSS):
        missing_inputs.append(
            _missing_input(
                "profit_and_loss",
                "Profit and loss statements were not provided.",
                document_type=DocumentType.PROFIT_AND_LOSS,
                reason="Financial scoring needs operating results to validate revenue, margins, and SDE.",
            )
        )
    if not _has_document_type(ingestion_output, DocumentType.BALANCE_SHEET):
        missing_inputs.append(
            _missing_input(
                "balance_sheet",
                "Balance sheet was not provided.",
                document_type=DocumentType.BALANCE_SHEET,
                required=False,
                reason="Working capital and leverage assessment are less reliable without a balance sheet.",
            )
        )
    if not _has_document_type(ingestion_output, DocumentType.CASH_FLOW_STATEMENT):
        missing_inputs.append(
            _missing_input(
                "cash_flow_statement",
                "Cash flow statement was not provided.",
                document_type=DocumentType.CASH_FLOW_STATEMENT,
                required=False,
                reason="Cash conversion and free cash flow validation are limited without a cash flow statement.",
            )
        )
    return _wrap_specialist_output(
        agent_name=AgentName.FINANCIAL_ANALYSIS,
        result=result,
        normalized_metrics=normalized_metrics,
        findings=findings,
        missing_inputs=missing_inputs,
        evidence=evidence,
    )


def _normalize_tax_output(
    ingestion_output: IngestionOutput,
    result: AgentResult[TaxComplianceOutput],
    metrics: dict[str, Any],
) -> AgentResult[Any]:
    evidence = _make_evidence_references(
        ingestion_output,
        [
            DocumentType.TAX_RETURN_1120S,
            DocumentType.TAX_RETURN_1040,
            DocumentType.TAX_RETURN_SCHEDULE_C,
            DocumentType.PROFIT_AND_LOSS,
        ],
    )
    domain_output = result.data
    if not domain_output:
        return result

    potential_exposure = sum(flag.potential_exposure or 0 for flag in domain_output.compliance_flags)
    normalized_metrics = {
        "max_revenue_discrepancy_pct": _metric(
            metrics.get("max_percentage_discrepancy"),
            unit="ratio",
            confidence=domain_output.confidence,
            evidence=evidence,
        ),
        "missing_tax_years_count": _metric(
            len(metrics.get("year_coverage", {}).get("missing_tax_years", [])),
            confidence=domain_output.confidence,
            evidence=evidence,
        ),
        "tax_returns_present": _metric(metrics.get("has_tax_returns"), confidence=domain_output.confidence, evidence=evidence),
        "potential_tax_exposure": _metric(potential_exposure or None, unit="usd", confidence=domain_output.confidence, evidence=evidence),
    }
    findings = [
        NormalizedFinding(
            finding_id=flag.id,
            source_agent=AgentName.TAX_COMPLIANCE,
            category=FindingCategory.TAX_COMPLIANCE,
            severity=flag.severity,
            title=flag.title,
            description=flag.description,
            deterministic_tags=[DeterministicTag.VALUATION_PRESSURE] if flag.potential_exposure else [],
            metric_impact={"potential_tax_exposure": flag.potential_exposure} if flag.potential_exposure is not None else {},
            evidence=evidence,
            confidence=domain_output.confidence,
        )
        for flag in domain_output.compliance_flags
    ]
    missing_inputs: list[MissingInput] = []
    if not metrics.get("has_tax_returns"):
        missing_inputs.append(
            _missing_input(
                "tax_returns",
                "Business tax returns were not provided.",
                reason="Tax return coverage is required to reconcile reported revenue and identify filing exposure.",
            )
        )
    return _wrap_specialist_output(
        agent_name=AgentName.TAX_COMPLIANCE,
        result=result,
        normalized_metrics=normalized_metrics,
        findings=findings,
        missing_inputs=missing_inputs,
        evidence=evidence,
    )


def _normalize_ar_output(
    ingestion_output: IngestionOutput,
    result: AgentResult[ARCollectionsOutput],
    metrics: dict[str, Any],
) -> AgentResult[Any]:
    evidence = _make_evidence_references(ingestion_output, [DocumentType.AR_AGING_REPORT, DocumentType.PROFIT_AND_LOSS])
    domain_output = result.data
    if not domain_output:
        return result

    normalized_metrics = {
        "dso": _metric(metrics.get("dso"), unit="days", confidence=domain_output.confidence, evidence=evidence),
        "top_customer_ar_pct": _metric(metrics.get("top_customer_percent"), unit="ratio", confidence=domain_output.confidence, evidence=evidence),
        "write_off_risk_pct": _metric(metrics.get("estimated_write_off_percent"), unit="ratio", confidence=domain_output.confidence, evidence=evidence),
        "over_90_ar_pct": _metric(
            metrics.get("aging_percentages", {}).get("over_90"),
            unit="ratio",
            confidence=domain_output.confidence,
            evidence=evidence,
        ),
    }
    findings = [
        NormalizedFinding(
            finding_id=flag.id,
            source_agent=AgentName.AR_COLLECTIONS,
            category=FindingCategory.RECEIVABLES,
            severity=flag.severity,
            title=f"Receivable at risk: {flag.customer_name or flag.customer_id or flag.id}",
            description=flag.description,
            deterministic_tags=[DeterministicTag.VALUATION_PRESSURE] if flag.amount else [],
            metric_impact={"amount_at_risk": flag.amount, "days_past_due": flag.days_past_due},
            evidence=evidence,
            confidence=domain_output.confidence,
        )
        for flag in domain_output.collectibility_flags
    ]
    missing_inputs: list[MissingInput] = []
    if not metrics.get("has_ar_data"):
        missing_inputs.append(
            _missing_input(
                "ar_aging_report",
                "AR aging report was not provided.",
                document_type=DocumentType.AR_AGING_REPORT,
                reason="Receivables quality and write-off risk cannot be validated without an AR aging report.",
            )
        )
    return _wrap_specialist_output(
        agent_name=AgentName.AR_COLLECTIONS,
        result=result,
        normalized_metrics=normalized_metrics,
        findings=findings,
        missing_inputs=missing_inputs,
        evidence=evidence,
    )


def _normalize_customer_output(
    ingestion_output: IngestionOutput,
    result: AgentResult[CustomerConcentrationOutput],
    metrics: dict[str, Any],
) -> AgentResult[Any]:
    evidence = _make_evidence_references(ingestion_output, [DocumentType.CUSTOMER_LIST, DocumentType.CONTRACT])
    domain_output = result.data
    if not domain_output:
        return result

    normalized_metrics = {
        "top_customer_revenue_pct": _metric(metrics.get("top_customer_percent"), unit="pct", confidence=domain_output.confidence, evidence=evidence),
        "top5_revenue_pct": _metric(metrics.get("top5_percent"), unit="pct", confidence=domain_output.confidence, evidence=evidence),
        "hhi": _metric(metrics.get("herfindahl_index"), confidence=domain_output.confidence, evidence=evidence),
        "single_customer_dependency": _metric(metrics.get("single_customer_dependency"), confidence=domain_output.confidence, evidence=evidence),
    }
    findings = [
        NormalizedFinding(
            finding_id=risk.id,
            source_agent=AgentName.CUSTOMER_CONCENTRATION,
            category=_map_customer_category(risk.title, risk.description),
            severity=risk.severity,
            title=risk.title,
            description=risk.description,
            deterministic_tags=[DeterministicTag.VALUATION_PRESSURE],
            evidence=evidence,
            confidence=domain_output.confidence,
        )
        for risk in domain_output.contract_risks
    ]
    missing_inputs: list[MissingInput] = []
    if not metrics.get("customers"):
        missing_inputs.append(
            _missing_input(
                "customer_list",
                "Customer list was not provided.",
                document_type=DocumentType.CUSTOMER_LIST,
                reason="Customer concentration cannot be measured reliably without customer-level revenue data.",
            )
        )
    if not _has_document_type(ingestion_output, DocumentType.CONTRACT):
        missing_inputs.append(
            _missing_input(
                "customer_contracts",
                "Customer contracts were not provided.",
                document_type=DocumentType.CONTRACT,
                required=False,
                reason="Contract durability and renewal risk are less certain without supporting customer agreements.",
            )
        )
    return _wrap_specialist_output(
        agent_name=AgentName.CUSTOMER_CONCENTRATION,
        result=result,
        normalized_metrics=normalized_metrics,
        findings=findings,
        missing_inputs=missing_inputs,
        evidence=evidence,
    )


def _normalize_ops_output(
    ingestion_output: IngestionOutput,
    result: AgentResult[OpsTransferabilityOutput],
    metrics: dict[str, Any],
) -> AgentResult[Any]:
    evidence = _make_evidence_references(
        ingestion_output,
        [DocumentType.EMPLOYEE_ROSTER, DocumentType.INSURANCE_POLICY, DocumentType.EQUIPMENT_LIST, DocumentType.OTHER],
    )
    domain_output = result.data
    if not domain_output:
        return result

    key_person_risk_count = sum(
        1
        for person in domain_output.employees.key_personnel
        if getattr(person.retention_risk, "value", str(person.retention_risk)).lower() in {"high", "medium"}
    )
    normalized_metrics = {
        "owner_dependence_score": _metric(domain_output.owner_dependence.score, confidence=domain_output.confidence, evidence=evidence),
        "delegated_management": _metric(domain_output.owner_dependence.has_delegated_management, confidence=domain_output.confidence, evidence=evidence),
        "headcount": _metric(domain_output.employees.headcount, confidence=domain_output.confidence, evidence=evidence),
        "key_person_risk_count": _metric(key_person_risk_count, confidence=domain_output.confidence, evidence=evidence),
        "transferable_license_count": _metric(metrics.get("transferable_license_count"), confidence=domain_output.confidence, evidence=evidence),
    }
    findings = [
        NormalizedFinding(
            finding_id=risk.id,
            source_agent=AgentName.OPERATIONS_TRANSFERABILITY,
            category=_map_ops_category(risk.category),
            severity=risk.severity,
            title=risk.title,
            description=risk.description,
            deterministic_tags=[DeterministicTag.TRANSFERABILITY_PRESSURE],
            evidence=evidence,
            confidence=domain_output.confidence,
        )
        for risk in domain_output.risks
    ]
    missing_inputs: list[MissingInput] = []
    if not metrics.get("has_operational_docs"):
        missing_inputs.append(
            _missing_input(
                "operational_documents",
                "Operational diligence documents were not provided.",
                reason="Roster, insurance, equipment, and license support are needed to evaluate transferability.",
            )
        )
    elif not _has_document_type(ingestion_output, DocumentType.EMPLOYEE_ROSTER):
        missing_inputs.append(
            _missing_input(
                "employee_roster",
                "Employee roster was not provided.",
                document_type=DocumentType.EMPLOYEE_ROSTER,
                reason="Management depth and key-person dependency are harder to verify without roster data.",
            )
        )
    return _wrap_specialist_output(
        agent_name=AgentName.OPERATIONS_TRANSFERABILITY,
        result=result,
        normalized_metrics=normalized_metrics,
        findings=findings,
        missing_inputs=missing_inputs,
        evidence=evidence,
    )


def _normalize_lease_output(
    ingestion_output: IngestionOutput,
    result: AgentResult[LeaseContractOutput],
    metrics: dict[str, Any],
) -> AgentResult[Any]:
    evidence = _make_evidence_references(ingestion_output, [DocumentType.LEASE_AGREEMENT, DocumentType.CONTRACT, DocumentType.OTHER])
    domain_output = result.data
    if not domain_output:
        return result

    non_transferable_contracts = sum(1 for contract in domain_output.other_contracts if not contract.transferable)
    assignment_clause_risk = None
    if domain_output.lease is not None:
        assignment_clause_risk = not domain_output.lease.is_transferable
    normalized_metrics = {
        "remaining_lease_months": _metric(metrics.get("remaining_months"), confidence=domain_output.confidence, evidence=evidence),
        "assignment_clause_risk": _metric(assignment_clause_risk, confidence=domain_output.confidence, evidence=evidence),
        "monthly_rent": _metric(metrics.get("monthly_rent"), unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "key_contracts_non_transferable_count": _metric(non_transferable_contracts, confidence=domain_output.confidence, evidence=evidence),
    }
    findings = [
        NormalizedFinding(
            finding_id=risk.id,
            source_agent=AgentName.LEASE_CONTRACT,
            category=_map_lease_category(risk.title, risk.description),
            severity=risk.severity,
            title=risk.title,
            description=risk.description,
            deterministic_tags=[DeterministicTag.TRANSFERABILITY_PRESSURE],
            evidence=evidence,
            confidence=domain_output.confidence,
        )
        for risk in domain_output.risks
    ]
    missing_inputs: list[MissingInput] = []
    if not metrics.get("has_lease") and not metrics.get("has_contracts"):
        missing_inputs.append(
            _missing_input(
                "lease_and_contracts",
                "Lease and key contracts were not provided.",
                reason="Transferability and assignment risk cannot be verified without the lease package or key contracts.",
            )
        )
    elif not metrics.get("has_lease"):
        missing_inputs.append(
            _missing_input(
                "lease_agreement",
                "Lease agreement was not provided.",
                document_type=DocumentType.LEASE_AGREEMENT,
                reason="Remaining term and assignment rights depend on the lease agreement.",
            )
        )
    if not metrics.get("has_contracts"):
        missing_inputs.append(
            _missing_input(
                "key_contracts",
                "Key contracts were not provided.",
                document_type=DocumentType.CONTRACT,
                required=False,
                reason="Counterparty transferability and non-assignment risk are harder to verify without contract support.",
            )
        )
    return _wrap_specialist_output(
        agent_name=AgentName.LEASE_CONTRACT,
        result=result,
        normalized_metrics=normalized_metrics,
        findings=findings,
        missing_inputs=missing_inputs,
        evidence=evidence,
    )


def _normalize_market_output(
    ingestion_output: IngestionOutput,
    result: AgentResult[MarketMacroOutput],
    *,
    business_type_known: bool,
    location_known: bool,
) -> AgentResult[Any]:
    evidence = _make_evidence_references(ingestion_output, [doc.document_type for doc in ingestion_output.documents])
    domain_output = result.data
    if not domain_output:
        return result

    threat_count = sum(1 for threat in domain_output.threats if threat.severity in {Severity.HIGH, Severity.CRITICAL})
    normalized_metrics = {
        "industry_trend": _metric(domain_output.industry_overview.trend.value, confidence=domain_output.confidence, evidence=evidence),
        "competitor_density": _metric(domain_output.local_market.competitor_density.value, confidence=domain_output.confidence, evidence=evidence),
        "demand_outlook_score": _metric(domain_output.local_market.demand_outlook, confidence=domain_output.confidence, evidence=evidence),
        "threat_count_high_or_critical": _metric(threat_count, confidence=domain_output.confidence, evidence=evidence),
    }
    findings = [
        NormalizedFinding(
            finding_id=threat.id,
            source_agent=AgentName.MARKET_MACRO,
            category=FindingCategory.MARKET_CONDITIONS,
            severity=threat.severity,
            title=threat.title,
            description=threat.description,
            evidence=evidence,
            confidence=domain_output.confidence,
        )
        for threat in domain_output.threats
    ]
    missing_inputs: list[MissingInput] = []
    if not ingestion_output.documents:
        missing_inputs.append(
            _missing_input(
                "document_context",
                "No documents were provided for market context.",
                required=False,
                reason="Market analysis can still use generic industry knowledge, but deal-specific context is limited without source documents.",
            )
        )
    if not business_type_known:
        missing_inputs.append(
            _missing_input(
                "business_type",
                "Business type was not provided.",
                required=False,
                reason="Industry-specific market benchmarking is less precise without a clear business type.",
            )
        )
    if not location_known:
        missing_inputs.append(
            _missing_input(
                "location",
                "Business location was not provided.",
                required=False,
                reason="Local competitive density and demand outlook are less precise without a known geography.",
            )
        )
    return _wrap_specialist_output(
        agent_name=AgentName.MARKET_MACRO,
        result=result,
        normalized_metrics=normalized_metrics,
        findings=findings,
        missing_inputs=missing_inputs,
        evidence=evidence,
    )


def _unwrap_financial_output(financial_analysis_output: FinancialAnalysisOutput | AgentEnvelope | Any) -> FinancialAnalysisOutput | None:
    if isinstance(financial_analysis_output, AgentEnvelope):
        raw = financial_analysis_output.raw_domain_output
        if isinstance(raw, FinancialAnalysisOutput):
            return raw
        if isinstance(raw, dict):
            return FinancialAnalysisOutput.model_validate(raw)
        return None
    if isinstance(financial_analysis_output, FinancialAnalysisOutput):
        return financial_analysis_output
    if isinstance(financial_analysis_output, dict):
        return FinancialAnalysisOutput.model_validate(financial_analysis_output)
    raw = getattr(financial_analysis_output, "raw_domain_output", None)
    if isinstance(raw, FinancialAnalysisOutput):
        return raw
    return financial_analysis_output if hasattr(financial_analysis_output, "profitability") else None


def _normalize_lending_output(
    ingestion_output: IngestionOutput,
    result: AgentResult[LendingAffordabilityOutput],
    *,
    asking_price_evidence: AskingPriceEvidence | None,
) -> AgentResult[Any]:
    evidence = _make_evidence_references(
        ingestion_output,
        [DocumentType.PROFIT_AND_LOSS, DocumentType.BALANCE_SHEET, DocumentType.CASH_FLOW_STATEMENT, "sde_summary"],
    )
    domain_output = result.data
    if not domain_output:
        return result

    normalized_metrics = {
        "asking_price": _metric(domain_output.affordability_analysis.asking_price, unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "adjusted_sde": _metric(domain_output.affordability_analysis.adjusted_sde, unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "sde_multiple": _metric(domain_output.affordability_analysis.sde_multiple, unit="x", confidence=domain_output.confidence, evidence=evidence),
        "dscr": _metric(domain_output.sba7a.dscr, unit="ratio", confidence=domain_output.confidence, evidence=evidence),
        "dscr_meets_minimum": _metric(domain_output.sba7a.dscr_meets_minimum, confidence=domain_output.confidence, evidence=evidence),
        "total_cash_needed": _metric(domain_output.buyer_requirements.total_cash_needed, unit="usd", confidence=domain_output.confidence, evidence=evidence),
        "eligible_for_sba": _metric(domain_output.sba7a.eligible_for_sba, confidence=domain_output.confidence, evidence=evidence),
    }
    if asking_price_evidence:
        normalized_metrics["asking_price_source"] = _metric(asking_price_evidence.source, confidence=domain_output.confidence, evidence=evidence)
    findings = [
        NormalizedFinding(
            finding_id=risk.id,
            source_agent=AgentName.LENDING_AFFORDABILITY,
            category=FindingCategory.LENDING,
            severity=risk.severity,
            title=risk.title,
            description=risk.description,
            deterministic_tags=[DeterministicTag.BANKABILITY_PRESSURE],
            evidence=evidence,
            confidence=domain_output.confidence,
        )
        for risk in domain_output.risks
    ]
    missing_inputs: list[MissingInput] = []
    if not asking_price_evidence or asking_price_evidence.source == "estimated_3x_sde":
        missing_inputs.append(
            _missing_input(
                "asking_price",
                "Explicit asking price was not provided.",
                required=False,
                reason="Lending used a deterministic 3.0x SDE fallback because neither user input nor source documents supplied an asking price.",
            )
        )
    return _wrap_specialist_output(
        agent_name=AgentName.LENDING_AFFORDABILITY,
        result=result,
        normalized_metrics=normalized_metrics,
        findings=findings,
        missing_inputs=missing_inputs,
        evidence=evidence,
    )


def _build_lending_handoff(
    financial_output: FinancialAnalysisOutput,
    *,
    asking_price_evidence: AskingPriceEvidence | None,
    base_case: dict[str, Any],
    scenarios: list[dict[str, Any]],
    documents: list[str],
) -> dict[str, Any]:
    profitability = financial_output.profitability
    balance_sheet = financial_output.balance_sheet
    cash_flow = financial_output.cash_flow
    return {
        "financial_summary": {
            "summary": financial_output.summary,
            "overall_score": financial_output.overall_score,
            "confidence": financial_output.confidence,
            "adjusted_sde": profitability.sde,
            "ebitda": profitability.ebitda,
            "gross_margin": profitability.gross_margin,
            "ebitda_margin": getattr(profitability, "ebitda_margin", None),
            "working_capital": balance_sheet.working_capital,
            "operating_cash_flow": cash_flow.operating_cash_flow,
            "free_cash_flow": cash_flow.free_cash_flow,
            "highest_severity_risks": [
                {
                    "id": risk.id,
                    "severity": risk.severity.value if hasattr(risk.severity, "value") else risk.severity,
                    "title": risk.title,
                    "financial_impact": risk.financial_impact,
                }
                for risk in sorted(financial_output.risks, key=lambda item: SEVERITY_ORDER.get(getattr(item.severity, "value", item.severity), 99))[:4]
            ],
        },
        "asking_price": {
            "value": asking_price_evidence.value if asking_price_evidence else None,
            "source": asking_price_evidence.source if asking_price_evidence else None,
            "document_id": asking_price_evidence.document_id if asking_price_evidence else None,
            "section_id": asking_price_evidence.section_id if asking_price_evidence else None,
            "section_name": asking_price_evidence.section_name if asking_price_evidence else None,
        },
        "base_case": base_case,
        "scenario_analysis": scenarios,
        "documents": documents,
        "sba_defaults": SBA_DEFAULTS,
    }


def build_financial_fallback_result(
    ingestion_output: IngestionOutput,
    *,
    reason: str,
) -> AgentResult[Any]:
    relevant_doc_types = {"profit_and_loss", "balance_sheet", "cash_flow_statement", "sde_summary"}
    sections = _relevant_sections(ingestion_output, relevant_doc_types)
    metrics = compute_financial_metrics(sections)
    most_recent_year = metrics.get("most_recent_year") or {}
    sde_metrics = metrics.get("sde") or {}
    balance_sheet_metrics = metrics.get("balance_sheet") or {}
    cash_flow_metrics = metrics.get("cash_flow") or {}

    financial_risks: list[FinancialRisk] = [
        FinancialRisk(
            id="financial-timeout-fallback",
            category="earnings_quality",
            severity=Severity.HIGH,
            title="Financial narrative timed out",
            description="The LLM financial narrative did not finish inside the stage budget, so this section fell back to deterministic extracted metrics.",
            evidence=reason,
            recommendation="Treat this as a low-confidence placeholder and validate the underlying statements directly.",
        )
    ]
    if metrics.get("cash_flow_vs_net_income_divergence") is not None and metrics["cash_flow_vs_net_income_divergence"] > 0.25:
        financial_risks.append(
            FinancialRisk(
                id="financial-cashflow-divergence",
                category="cash_flow",
                severity=Severity.MEDIUM,
                title="Cash flow diverges from net income",
                description="Operating cash flow and reported net income differ materially in the extracted statements.",
                evidence="Deterministic comparison of cash flow and net income exceeded 25%.",
                financial_impact=None,
                recommendation="Reconcile cash conversion before relying on reported earnings quality.",
            )
        )
    if metrics.get("working_capital") is not None and metrics["working_capital"] < 0:
        financial_risks.append(
            FinancialRisk(
                id="financial-negative-working-capital",
                category="working_capital",
                severity=Severity.HIGH,
                title="Negative working capital detected",
                description="Current liabilities exceed current assets in the extracted balance sheet.",
                evidence="Deterministic working capital calculation returned a negative value.",
                financial_impact=abs(float(metrics["working_capital"])),
                recommendation="Confirm liquidity needs and normalize near-term working capital requirements.",
            )
        )

    fallback_score = 6
    if metrics.get("data_years_available", 0) <= 1:
        fallback_score -= 1
    if metrics.get("cash_flow_vs_net_income_divergence") is not None and metrics["cash_flow_vs_net_income_divergence"] > 0.25:
        fallback_score -= 1
    if metrics.get("working_capital") is not None and metrics["working_capital"] < 0:
        fallback_score -= 2
    if not sde_metrics.get("sde"):
        fallback_score -= 2
    fallback_score = max(2, min(8, fallback_score))

    summary = (
        "Financial analysis fell back to deterministic extracted metrics because the narrative stage exceeded its runtime budget. "
        "Use the reported revenue, EBITDA, SDE, and balance-sheet figures as low-confidence placeholders until the source statements are validated."
    )
    confidence = 0.32 if metrics.get("data_years_available", 0) else 0.18

    synthetic_output = FinancialAnalysisOutput(
        revenue_analysis=RevenueAnalysis(
            annual_figures=[
                AnnualRevenue(
                    year=item.get("year") or 0,
                    revenue=float(item.get("revenue") or 0.0),
                    cogs=float(item.get("cogs") or 0.0),
                    gross_profit=float(item.get("gross_profit") or 0.0),
                )
                for item in metrics.get("annual_financials", [])
            ],
            growth_rate=float((metrics.get("revenue_growth_rates") or [{}])[-1].get("rate") or 0.0),
            trend=(
                Trend.INCREASING
                if ((metrics.get("revenue_growth_rates") or [{}])[-1].get("rate") or 0.0) > 0.03
                else Trend.DECLINING
                if ((metrics.get("revenue_growth_rates") or [{}])[-1].get("rate") or 0.0) < -0.03
                else Trend.STABLE
            ),
            seasonality_notes="Deterministic fallback summary only; detailed seasonality analysis was not completed.",
        ),
        expense_analysis=ExpenseAnalysis(
            annual_figures=[
                AnnualExpense(
                    year=item.get("year") or 0,
                    total_expenses=float(item.get("operating_expenses") or 0.0),
                    breakdown={},
                )
                for item in metrics.get("annual_financials", [])
            ],
            largest_categories=[],
        ),
        profitability=Profitability(
            gross_margin=float(metrics.get("gross_margin") or 0.0),
            net_margin=float(metrics.get("net_margin") or 0.0),
            ebitda=float(most_recent_year.get("ebitda") or 0.0),
            adjusted_ebitda=float(most_recent_year.get("ebitda") or 0.0),
            sde=float(sde_metrics.get("sde") or 0.0),
            sde_add_backs=[
                SdeAddBack(description=label.replace("_", " ").title(), amount=float(value or 0.0), justification="Deterministic fallback add-back.")
                for label, value in (
                    ("owner_salary", sde_metrics.get("owner_salary")),
                    ("owner_benefits", sde_metrics.get("owner_benefits")),
                    ("depreciation", sde_metrics.get("depreciation")),
                    ("interest_expense", sde_metrics.get("interest_expense")),
                    ("one_time_expenses", sde_metrics.get("one_time_expenses")),
                )
                if value not in (None, 0, 0.0)
            ],
        ),
        cash_flow=CashFlow(
            operating_cash_flow=float(cash_flow_metrics.get("operating_cash_flow") or 0.0),
            free_cash_flow=float(cash_flow_metrics.get("free_cash_flow") or 0.0),
            cash_flow_vs_net_income=bool((metrics.get("cash_flow_vs_net_income_divergence") or 0.0) > 0.2),
        ),
        balance_sheet=BalanceSheet(
            total_assets=float(balance_sheet_metrics.get("total_assets") or 0.0),
            total_liabilities=float(balance_sheet_metrics.get("total_liabilities") or 0.0),
            equity=float(balance_sheet_metrics.get("equity") or 0.0),
            current_ratio=float(metrics.get("current_ratio") or 0.0),
            debt_to_equity=float(metrics.get("debt_to_equity") or 0.0),
            working_capital=float(metrics.get("working_capital") or 0.0),
        ),
        risks=financial_risks,
        overall_score=fallback_score,
        confidence=confidence,
        summary=summary,
    )

    user_message = build_financial_user_message(ingestion_output, metrics)
    diagnostics = describe_user_message(user_message)
    diagnostics["response_chars"] = len(compact_json(synthetic_output.model_dump(mode="json")))
    diagnostics["fallback_used"] = True

    normalized = _normalize_financial_output(
        ingestion_output,
        AgentResult(status="success", data=synthetic_output, diagnostics=diagnostics),
        metrics,
    )
    if normalized.status == "success" and isinstance(normalized.data, AgentEnvelope):
        normalized = normalized.model_copy(
            update={
                "data": normalized.data.model_copy(
                    update={
                        "status": AgentExecutionStatus.PARTIAL,
                        "summary": summary,
                        "confidence": confidence,
                    }
                ),
                "diagnostics": diagnostics,
            }
        )
    return normalized


def build_synthesis_fallback_result(
    scorecard: DeterministicScorecard,
    agent_results: Dict[str, Any],
    *,
    reason: str,
) -> AgentResult[SynthesisReportOutput]:
    metrics = compute_synthesis_metrics(agent_results)
    section_key_map = {
        "financial": "financial_analysis",
        "tax": "tax_compliance",
        "ar": "ar_collections",
        "customer": "customer_concentration",
        "operations": "operations_transferability",
        "lease": "lease_contract",
        "market": "market_macro",
        "lending": "lending_affordability",
    }

    section_payload = metrics.get("section_summaries", {})
    section_summaries = SectionSummaries(
        **{
            field_name: SectionSummary(
                score=int((section_payload.get(agent_key) or {}).get("score") or 1),
                summary=(section_payload.get(agent_key) or {}).get("summary") or "Analysis unavailable.",
                top_risks=list((section_payload.get(agent_key) or {}).get("top_risks") or ["Analysis did not complete."])[:3],
            )
            for field_name, agent_key in section_key_map.items()
        }
    )

    red_flags = [
        RedFlag(
            id=str(item.get("id") or f"fallback-red-{idx}"),
            severity=Severity(item.get("severity") or Severity.MEDIUM.value),
            source=AgentSource(item.get("source") or AgentSource.FINANCIAL.value),
            title=str(item.get("title") or "Diligence risk"),
            description=str(item.get("description") or "Elevated diligence risk was identified by deterministic scoring."),
            financial_impact=item.get("financial_impact"),
        )
        for idx, item in enumerate(metrics.get("red_flags", [])[:6], start=1)
    ]
    green_flags = [
        GreenFlag(
            id=str(item.get("id") or f"fallback-green-{idx}"),
            source=AgentSource(item.get("source") or AgentSource.FINANCIAL.value),
            title=str(item.get("title") or "Positive signal"),
            description=str(item.get("description") or "Deterministic scoring identified a relatively favorable signal."),
        )
        for idx, item in enumerate(metrics.get("green_flags", [])[:4], start=1)
    ]

    missing_descriptions: list[str] = []
    for result in agent_results.values():
        if result and result.status == "success" and isinstance(result.data, AgentEnvelope):
            for missing_input in result.data.missing_inputs:
                if missing_input.description not in missing_descriptions:
                    missing_descriptions.append(missing_input.description)

    next_steps: list[NextStep] = []
    for index, finding in enumerate(scorecard.deal_breakers[:3], start=1):
        next_steps.append(
            NextStep(
                priority=index,
                action=f"Resolve critical issue: {finding.title}",
                reason=finding.description,
            )
        )
    for index, description in enumerate(missing_descriptions[:2], start=len(next_steps) + 1):
        next_steps.append(
            NextStep(
                priority=min(index, 5),
                action=f"Obtain missing diligence item: {description}",
                reason="This input lowered completeness and should be resolved before relying on the final narrative.",
            )
        )
    if not next_steps:
        next_steps.append(
            NextStep(
                priority=1,
                action="Review the deterministic scorecard directly.",
                reason="Narrative synthesis timed out, so the coded scorecard is the authoritative output for this run.",
            )
        )

    recommendation = scorecard.overall_recommendation or "conditional_buy"
    recommendation_guidance = {
        "strong_buy": "Normal diligence can continue, but keep price discipline anchored to the coded scorecard.",
        "buy": "Proceed with confirmatory diligence while preserving standard protections.",
        "conditional_buy": "Tie progress to resolving the top red flags and missing diligence items before close.",
        "caution": "Pause commitments until the top red flags are resolved or repriced.",
        "do_not_buy": "Current deterministic evidence does not support moving forward without a material change in price or structure.",
    }
    executive_summary = (
        "Narrative synthesis fell back to a deterministic summary because the synthesis stage exceeded its runtime budget. "
        f"The authoritative scorecard recommendation is '{recommendation}'"
        + (
            f" at risk score {scorecard.overall_risk_score}. "
            if scorecard.overall_risk_score is not None
            else ". "
        )
        + f"{len(metrics.get('successful_agents', []))} specialist analyses completed successfully."
    )
    fallback_output = SynthesisReportOutput(
        executive_summary=executive_summary,
        red_flags=red_flags,
        green_flags=green_flags,
        section_summaries=section_summaries,
        next_steps=next_steps[:5],
        deal_terms_suggestion=recommendation_guidance.get(recommendation, recommendation_guidance["conditional_buy"]),
    )

    user_message = build_synthesis_user_message(scorecard, agent_results, metrics)
    diagnostics = describe_user_message(user_message)
    diagnostics["response_chars"] = len(compact_json(fallback_output.model_dump(mode="json")))
    diagnostics["fallback_used"] = True

    return AgentResult(
        status="success",
        data=fallback_output,
        diagnostics=diagnostics,
    )


_OCR_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tiff"}
_STRUCTURED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".docx"}

_OCR_MIME_PREFIXES = ("application/pdf", "image/")
_STRUCTURED_MIMES = {
    "text/csv",
    "text/tab-separated-values",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_MISTRAL_TO_DOCUMENT_TYPE: dict[str, DocumentType] = {
    "pnl_income_statement": DocumentType.PROFIT_AND_LOSS,
    "balance_sheet": DocumentType.BALANCE_SHEET,
    "cash_flow_statement": DocumentType.CASH_FLOW_STATEMENT,
    "tax_return": DocumentType.TAX_RETURN_1120S,
    "lease_contract": DocumentType.LEASE_AGREEMENT,
    "ar_aging_report": DocumentType.AR_AGING_REPORT,
    "bank_statement": DocumentType.OTHER,
    "business_acquisition_document": DocumentType.CONTRACT,
    "other": DocumentType.OTHER,
}


def _classify_file_route(filename: str, mime: str) -> str:
    """Return 'ocr', 'structured', or 'unsupported'."""
    ext = Path(filename).suffix.lower()
    if ext in _OCR_EXTENSIONS:
        return "ocr"
    if ext in _STRUCTURED_EXTENSIONS:
        return "structured"
    if any(mime.startswith(prefix) for prefix in _OCR_MIME_PREFIXES):
        return "ocr"
    if mime in _STRUCTURED_MIMES:
        return "structured"
    return "unsupported"


def _bridge_ocr_to_document_info(
    ocr_result: IngestionResult,
    doc_payload: dict[str, Any],
) -> DocumentInfo:
    """Convert Mistral IngestionResult to pipeline DocumentInfo.

    Creates one DocumentSection per OCR page, populating raw_text with the
    page markdown. extracted_data is left empty because OCR produces
    markdown, not structured key-value pairs. Phase 2 Claude agents
    compensate by reading raw_text directly.
    """
    document_id = doc_payload.get("id") or doc_payload.get("document_id") or str(uuid4())
    doc_type = _MISTRAL_TO_DOCUMENT_TYPE.get(
        ocr_result.classification.document_type, DocumentType.OTHER,
    )
    mime = doc_payload.get("mime_type") or doc_payload.get("mimeType") or "application/pdf"

    sections: list[DocumentSection] = []
    for page in ocr_result.pages:
        sections.append(
            DocumentSection(
                section_id=f"{document_id}:page-{page.page_number}",
                document_id=document_id,
                document_type=doc_type,
                section_kind=doc_type.value if doc_type != DocumentType.OTHER else None,
                timeframe=Timeframe(),
                extracted_data={},
                raw_text=page.markdown,
                confidence=ocr_result.classification.confidence,
                section_name=f"Page {page.page_number}",
                page=page.page_number,
                page_start=page.page_number,
                page_end=page.page_number,
                source_format="pdf",
                content_type=SectionContentType.TEXT,
                status=DocumentStatus.PARSED,
                notes=[],
            )
        )

    return DocumentInfo(
        document_id=document_id,
        file_name=ocr_result.filename,
        mime_type=mime,
        document_type=doc_type,
        declared_type=None,
        canonical_type=doc_type,
        size_bytes=None,
        status=DocumentStatus.PARSED if sections else DocumentStatus.FAILED,
        confidence=ocr_result.classification.confidence,
        notes=[
            f"OCR model: {ocr_result.ocr_model}",
            f"Classification: {ocr_result.classification.document_type} "
            f"(confidence={ocr_result.classification.confidence:.2f})",
            f"Processing time: {ocr_result.processing_time_ms}ms",
        ],
        sections=sections,
    )


def run_document_ingestion(documents: list[dict[str, Any]], analysis_id: str | None = None) -> AgentResult[IngestionOutput]:
    if not documents:
        return AgentResult(
            status="success",
            data=IngestionOutput(
                documents=[],
                metadata=IngestionMetadata(
                    total_documents=0,
                    successfully_parsed=0,
                    ingestion_source="structured",
                    failed_documents=[],
                    warnings=["No documents were provided for ingestion."],
                ),
            ),
        )

    pre_sectioned_docs: list[dict[str, Any]] = []
    ocr_docs: list[dict[str, Any]] = []
    structured_docs: list[dict[str, Any]] = []
    unsupported: list[str] = []

    for doc in documents:
        # If the document already carries parsed sections (produced by the
        # /parse-documents step), reuse them directly — no re-OCR needed.
        if isinstance(doc.get("sections"), list) and len(doc["sections"]) > 0:
            pre_sectioned_docs.append(doc)
            continue

        filename = (
            doc.get("filename") or doc.get("file_name") or doc.get("fileName") or "unknown"
        )
        mime = doc.get("mime_type") or doc.get("mimeType") or ""
        route = _classify_file_route(filename, mime)
        if route == "ocr":
            ocr_docs.append(doc)
        elif route == "structured":
            structured_docs.append(doc)
        else:
            unsupported.append(filename)

    if unsupported and not ocr_docs and not structured_docs and not pre_sectioned_docs:
        return AgentResult(
            status="error",
            error=AgentErrorPayload(
                agent_name="document-ingestion",
                error_type="validation",
                message=f"Unsupported file type(s): {', '.join(unsupported)}. "
                        f"Supported: PDF, DOCX, images (PNG/JPG/WEBP/TIFF), and spreadsheets (XLSX/CSV/TSV).",
                timestamp=datetime.now(timezone.utc).isoformat(),
                retry_count=0,
            ),
        )

    total_cost_usd = 0.0
    all_document_infos: list[DocumentInfo] = []
    all_warnings: list[str] = []
    ingestion_source = "structured"

    # Pre-sectioned documents (produced by /parse-documents step) — reuse as-is.
    if pre_sectioned_docs:
        pre_output = ingest_and_persist_document_payloads(pre_sectioned_docs, analysis_id=analysis_id)
        all_document_infos.extend(pre_output.documents)
        all_warnings.extend(pre_output.metadata.warnings)
        if pre_output.metadata.ingestion_source:
            ingestion_source = pre_output.metadata.ingestion_source

    for doc in ocr_docs:
        filename = doc.get("filename") or doc.get("file_name") or "unknown"
        raw_content = doc.get("content") or doc.get("file_bytes") or b""
        if isinstance(raw_content, str):
            file_bytes = base64.b64decode(raw_content)
        else:
            file_bytes = raw_content

        try:
            result = ocr_document(file_bytes, filename)
        except MistralOCRError as exc:
            all_warnings.append(f"OCR failed for {filename}: {exc}")
            doc_id = doc.get("id") or doc.get("document_id") or str(uuid4())
            all_document_infos.append(
                DocumentInfo(
                    document_id=doc_id,
                    file_name=filename,
                    mime_type=doc.get("mime_type") or doc.get("mimeType") or "application/octet-stream",
                    document_type=DocumentType.OTHER,
                    status=DocumentStatus.FAILED,
                    confidence=0.0,
                    notes=[f"OCR error: {exc}"],
                    sections=[],
                )
            )
            continue

        total_cost_usd += result.cost_usd
        ingestion_source = "ocr"
        all_document_infos.append(_bridge_ocr_to_document_info(result, doc))

    if structured_docs:
        structured_output = ingest_and_persist_document_payloads(structured_docs, analysis_id=analysis_id)
        all_document_infos.extend(structured_output.documents)
        all_warnings.extend(structured_output.metadata.warnings)

    if unsupported:
        all_warnings.append(f"Skipped unsupported file type(s): {', '.join(unsupported)}")

    output = IngestionOutput(
        documents=all_document_infos,
        metadata=IngestionMetadata(
            total_documents=len(all_document_infos),
            successfully_parsed=sum(
                1 for d in all_document_infos
                if d.status in {DocumentStatus.PARSED, DocumentStatus.PARTIAL}
            ),
            ingestion_source=ingestion_source,
            failed_documents=[
                d.document_id for d in all_document_infos
                if d.status == DocumentStatus.FAILED
            ],
            warnings=all_warnings,
        ),
    )
    return AgentResult(status="success", data=output, cost_usd=total_cost_usd)


def run_financial_analysis(
    ingestion_output: IngestionOutput,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    config = AGENT_REGISTRY["financial-analysis"]
    relevant_doc_types = {"profit_and_loss", "balance_sheet", "cash_flow_statement", "sde_summary"}
    sections = _relevant_sections(ingestion_output, relevant_doc_types)
    metrics = compute_financial_metrics(sections)
    if metrics["data_years_available"] == 0 and not sections:
        return _not_applicable_result(
            config.name,
            "No financial documents (P&L, balance sheet, or cash flow) were found; financial analysis is not applicable.",
        )
    warning = ""
    if metrics["data_years_available"] == 0:
        warning = (
            "\n\nWARNING: No profit and loss, balance sheet, or cash flow documents were found. "
            "All financial fields should reflect the missing data and confidence should be low."
        )
    user_message = build_financial_user_message(ingestion_output, metrics, warning=warning or None)
    result = _call_llm_agent(
        config,
        FINANCIAL_ANALYSIS_PROMPT,
        user_message,
        FinancialAnalysisOutput,
        diagnostic_context=diagnostic_context,
    )
    return _normalize_financial_output(ingestion_output, result, metrics)


def run_tax_compliance(
    ingestion_output: IngestionOutput,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    config = AGENT_REGISTRY["tax-compliance"]
    relevant_doc_types = {"tax_return_1120s", "tax_return_1040", "tax_return_schedule_c", "profit_and_loss"}
    metrics = compute_tax_metrics(_relevant_sections(ingestion_output, relevant_doc_types))
    if not metrics["has_tax_returns"]:
        # If there are no tax returns AND no P&L to reconcile against, the agent has nothing useful to analyze.
        has_pl = bool(_relevant_sections(ingestion_output, {"profit_and_loss"}))
        if not has_pl:
            return _not_applicable_result(
                config.name,
                "No tax returns or financial documents were found; tax compliance analysis is not applicable.",
            )
        user_message = (
            build_tax_user_message(ingestion_output, metrics, missing_tax_returns=True)
        )
        result = _call_llm_agent(
            config,
            TAX_COMPLIANCE_PROMPT,
            user_message,
            TaxComplianceOutput,
            diagnostic_context=diagnostic_context,
        )
        return _normalize_tax_output(ingestion_output, result, metrics)

    user_message = build_tax_user_message(ingestion_output, metrics)
    result = _call_llm_agent(
        config,
        TAX_COMPLIANCE_PROMPT,
        user_message,
        TaxComplianceOutput,
        diagnostic_context=diagnostic_context,
    )
    return _normalize_tax_output(ingestion_output, result, metrics)


def run_ar_collections(
    ingestion_output: IngestionOutput,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    config = AGENT_REGISTRY["ar-collections"]
    relevant_doc_types = {"ar_aging_report", "profit_and_loss"}
    metrics = compute_ar_metrics(_relevant_sections(ingestion_output, relevant_doc_types))
    if not metrics["has_ar_data"]:
        return _not_applicable_result(
            config.name,
            "No AR aging report was uploaded; AR collections analysis is not applicable.",
        )

    user_message = build_ar_user_message(ingestion_output, metrics)
    result = _call_llm_agent(
        config,
        AR_COLLECTIONS_PROMPT,
        user_message,
        ARCollectionsOutput,
        diagnostic_context=diagnostic_context,
    )
    return _normalize_ar_output(ingestion_output, result, metrics)


def run_customer_concentration(
    ingestion_output: IngestionOutput,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    config = AGENT_REGISTRY["customer-concentration"]
    metrics = compute_customer_metrics(ingestion_output)
    # Only skip when neither customer list NOR contract documents are present at all.
    # If docs exist but structured extraction returned no rows, the LLM can still
    # analyze the raw text (customer lists are often unstructured PDFs).
    has_customer_docs = any(
        doc.document_type.value in {"customer_list", "contract"}
        for doc in ingestion_output.documents
    )
    if not metrics["customers"] and not has_customer_docs:
        return _not_applicable_result(
            config.name,
            "No customer list or contracts were uploaded; customer concentration analysis is not applicable.",
        )
    user_message = build_customer_user_message(ingestion_output, metrics)
    result = _call_llm_agent(
        config,
        CUSTOMER_CONCENTRATION_PROMPT,
        user_message,
        CustomerConcentrationOutput,
        diagnostic_context=diagnostic_context,
    )
    return _normalize_customer_output(ingestion_output, result, metrics)


def run_ops_transferability(
    ingestion_output: IngestionOutput,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    config = AGENT_REGISTRY["operations-transferability"]
    metrics = compute_ops_metrics(ingestion_output)
    if not metrics["has_operational_docs"]:
        return _not_applicable_result(
            config.name,
            "No operational documents (employee roster, insurance, equipment list) were uploaded; operations transferability analysis is not applicable.",
        )
    user_message = build_ops_user_message(ingestion_output, metrics)
    result = _call_llm_agent(
        config,
        OPERATIONS_TRANSFERABILITY_PROMPT,
        user_message,
        OpsTransferabilityOutput,
        diagnostic_context=diagnostic_context,
    )
    return _normalize_ops_output(ingestion_output, result, metrics)


def run_lease_contract(
    ingestion_output: IngestionOutput,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    config = AGENT_REGISTRY["lease-contract"]
    metrics = compute_lease_metrics(ingestion_output)
    if not metrics["has_lease"] and not metrics["has_contracts"]:
        return _not_applicable_result(
            config.name,
            "No lease agreement or contracts were uploaded; lease & contract analysis is not applicable.",
        )
    user_message = build_lease_user_message(ingestion_output, metrics)
    result = _call_llm_agent(
        config,
        LEASE_CONTRACT_PROMPT,
        user_message,
        LeaseContractOutput,
        diagnostic_context=diagnostic_context,
    )
    return _normalize_lease_output(ingestion_output, result, metrics)


def run_market_macro(
    ingestion_output: IngestionOutput,
    business_type: str | None = None,
    location: str | None = None,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    config = AGENT_REGISTRY["market-macro"]
    inferred = infer_business_context(ingestion_output)
    effective_business_type = business_type or inferred["business_type"] or "Unknown (infer from documents)"
    effective_location = location or inferred["location"] or "Unknown (infer from documents)"
    user_message = build_market_user_message(
        ingestion_output,
        business_type=effective_business_type,
        location=effective_location,
        revenue_range=inferred["revenue_range"],
        employee_count=inferred["employee_count"],
    )
    result = _call_llm_agent(
        config,
        MARKET_MACRO_PROMPT,
        user_message,
        MarketMacroOutput,
        diagnostic_context=diagnostic_context,
    )
    return _normalize_market_output(
        ingestion_output,
        result,
        business_type_known=effective_business_type != "Unknown (infer from documents)",
        location_known=effective_location != "Unknown (infer from documents)",
    )


def run_lending_affordability(
    ingestion_output: IngestionOutput,
    financial_analysis_output: FinancialAnalysisOutput | AgentEnvelope | Any,
    asking_price: float | None = None,
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[Any]:
    config = AGENT_REGISTRY["lending-affordability"]
    normalized_financial_output = _unwrap_financial_output(financial_analysis_output)
    if normalized_financial_output is None:
        return AgentResult(
            status="error",
            error=AgentErrorPayload(
                agent_name=config.name,
                error_type="validation",
                message="Lending analysis could not be completed because financial analysis output could not be normalized.",
                timestamp=datetime.now(timezone.utc).isoformat(),
                retry_count=0,
            ),
        )

    sde = normalized_financial_output.profitability.sde
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

    asking_price_evidence = resolve_asking_price(
        ingestion_output,
        user_asking_price=asking_price,
        fallback_sde=sde,
    )
    base_asking_price = asking_price_evidence.value if asking_price_evidence else round(sde * 3.0)
    base_case = compute_sba_lending(sde, base_asking_price)
    scenarios = [
        {"multiple": multiple, "asking_price": round(sde * multiple), "metrics": compute_sba_lending(sde, round(sde * multiple))}
        for multiple in (2.5, 3.0, 3.5)
    ]
    lending_handoff = _build_lending_handoff(
        normalized_financial_output,
        asking_price_evidence=asking_price_evidence,
        base_case=base_case,
        scenarios=scenarios,
        documents=[doc.file_name for doc in ingestion_output.documents],
    )
    user_message = (
        "## Lending Context\n"
        + compact_json(lending_handoff)
        + "\n\nUse the pre-computed figures above. If asking_price.source is estimated_3x_sde, treat it as a fallback base case and use the other scenarios as bounds."
    )
    result = _call_llm_agent(
        config,
        LENDING_AFFORDABILITY_PROMPT,
        user_message,
        LendingAffordabilityOutput,
        diagnostic_context=diagnostic_context,
    )
    return _normalize_lending_output(ingestion_output, result, asking_price_evidence=asking_price_evidence)


def run_synthesis_report(
    scorecard: DeterministicScorecard,
    agent_results: Dict[str, Any],
    *,
    diagnostic_context: dict[str, Any] | None = None,
) -> AgentResult[SynthesisReportOutput]:
    config = AGENT_REGISTRY["synthesis-report"]
    metrics = compute_synthesis_metrics(agent_results)

    user_message = build_synthesis_user_message(scorecard, agent_results, metrics)
    return _call_llm_agent(
        config,
        SYNTHESIS_REPORT_PROMPT,
        user_message,
        SynthesisReportOutput,
        diagnostic_context=diagnostic_context,
    )
