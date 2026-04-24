from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from app.agents.schemas import (
    AgentEnvelope,
    AgentResult,
    AgentName,
    AgentSource,
    DeterministicScorecard,
    EvidenceReference,
    IngestionOutput,
    MissingInput,
    NormalizedFinding,
    PipelineMetadata,
    ScoreConflict,
    SynthesisReportOutput,
)
from app.agents.deterministic import AGENT_DISPLAY_NAMES
from app.agents.evidence_utils import build_evidence_fields
from app.models.schemas import ReportOutputV2
from app.services.scoring_engine import BUYER_DIMENSION_GROUPS

MAX_SUMMARY_FINDINGS = 5
MAX_RECOMMENDED_ACTIONS = 5

RECOMMENDATION_HEADLINES: dict[str, str] = {
    "strong_buy": "Strong fit based on current diligence",
    "buy": "Promising deal with manageable risk",
    "conditional_buy": "Proceed, but only with targeted diligence conditions",
    "caution": "Material diligence issues require caution",
    "do_not_buy": "Current evidence does not support moving forward",
}

RECOMMENDATION_ACTIONS: dict[str, str] = {
    "strong_buy": "Keep normal diligence moving while preserving price discipline.",
    "buy": "Proceed with confirmatory diligence and standard purchase protections.",
    "conditional_buy": "Tie next steps to resolving the highest-risk findings before close.",
    "caution": "Pause major commitments until the highest-risk findings are resolved.",
    "do_not_buy": "Do not proceed without a material change in price, structure, or evidence quality.",
}

SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

SYNTHESIS_SOURCE_TO_AGENT: dict[AgentSource, AgentName] = {
    AgentSource.FINANCIAL: AgentName.FINANCIAL_ANALYSIS,
    AgentSource.TAX: AgentName.TAX_COMPLIANCE,
    AgentSource.AR: AgentName.AR_COLLECTIONS,
    AgentSource.CUSTOMER: AgentName.CUSTOMER_CONCENTRATION,
    AgentSource.OPERATIONS: AgentName.OPERATIONS_TRANSFERABILITY,
    AgentSource.LEASE: AgentName.LEASE_CONTRACT,
    AgentSource.MARKET: AgentName.MARKET_MACRO,
    AgentSource.LENDING: AgentName.LENDING_AFFORDABILITY,
}

AGENT_REVIEW_ORDER: tuple[AgentName, ...] = (
    AgentName.FINANCIAL_ANALYSIS,
    AgentName.TAX_COMPLIANCE,
    AgentName.AR_COLLECTIONS,
    AgentName.CUSTOMER_CONCENTRATION,
    AgentName.OPERATIONS_TRANSFERABILITY,
    AgentName.LEASE_CONTRACT,
    AgentName.MARKET_MACRO,
    AgentName.LENDING_AFFORDABILITY,
)


def _successful_envelopes(agent_results: Mapping[str, AgentResult[Any]]) -> list[AgentEnvelope]:
    envelopes: list[AgentEnvelope] = []
    for result in agent_results.values():
        if not result or result.status != "success" or not isinstance(result.data, AgentEnvelope):
            continue
        envelopes.append(result.data)
    return envelopes


def _missing_inputs(
    ingestion_output: IngestionOutput | None,
    envelopes: list[AgentEnvelope],
) -> list[MissingInput]:
    deduped: dict[tuple[str, str | None], MissingInput] = {}
    for item in list(ingestion_output.metadata.missing_inputs if ingestion_output else []) + [
        missing_input for envelope in envelopes for missing_input in envelope.missing_inputs
    ]:
        key = (item.key, item.document_type.value if item.document_type else None)
        deduped[key] = item
    return list(deduped.values())


def _evidence_index(ingestion_output: IngestionOutput | None, envelopes: list[AgentEnvelope]) -> list[EvidenceReference]:
    deduped: dict[tuple[str, str | None, int | None, str | None], EvidenceReference] = {}
    for evidence in [ref for envelope in envelopes for ref in envelope.evidence]:
        deduped[(evidence.document_id, evidence.section_id, evidence.page, evidence.snippet)] = evidence

    if ingestion_output:
        for document in ingestion_output.documents:
            for section in document.sections:
                snippet = section.raw_text.strip().replace("\n", " ")[:240] if section.raw_text else None
                evidence = EvidenceReference(
                    document_id=document.document_id,
                    file_name=document.file_name,
                    section_id=section.section_id,
                    page=section.page or section.page_start,
                    snippet=snippet or None,
                    extracted_fields=build_evidence_fields(section),
                    confidence=section.confidence,
                )
                deduped[(evidence.document_id, evidence.section_id, evidence.page, evidence.snippet)] = evidence
    return list(deduped.values())


def _merged_evidence_index(
    ingestion_output: IngestionOutput | None,
    envelopes: list[AgentEnvelope],
    clarification_evidence: list[EvidenceReference],
) -> list[EvidenceReference]:
    return _dedupe_evidence(_evidence_index(ingestion_output, envelopes) + clarification_evidence)


def _dedupe_evidence(evidence_items: list[EvidenceReference]) -> list[EvidenceReference]:
    deduped: dict[tuple[str, str | None, int | None, str | None], EvidenceReference] = {}
    for evidence in evidence_items:
        deduped[(evidence.document_id, evidence.section_id, evidence.page, evidence.snippet)] = evidence
    return list(deduped.values())


def _conflict_findings(conflicts: list[ScoreConflict]) -> list[NormalizedFinding]:
    findings: list[NormalizedFinding] = []
    for conflict in conflicts:
        findings.append(
            NormalizedFinding(
                finding_id=f"conflict-{conflict.key}",
                source_agent="synthesis_report",
                category="conflict",
                severity="medium",
                title=f"Conflicting inputs for {conflict.key}",
                description=conflict.description,
                evidence=conflict.evidence,
                confidence=0.7,
                missing_data=False,
            )
        )
    return findings


def _rank_finding(finding: NormalizedFinding) -> tuple[int, float, str]:
    return (
        SEVERITY_RANK.get(finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity), 0),
        1.0 if finding.missing_data else 0.0,
        finding.finding_id,
    )


def _summary_findings(scorecard: DeterministicScorecard, synthesis_output: SynthesisReportOutput | None) -> list[NormalizedFinding]:
    findings = list(scorecard.deal_breakers)
    seen = {finding.finding_id for finding in findings}

    for technical_scorecard in scorecard.technical_scorecards:
        for finding in technical_scorecard.findings:
            if finding.finding_id in seen:
                continue
            findings.append(finding)
            seen.add(finding.finding_id)

    for conflict_finding in _conflict_findings(scorecard.conflicts):
        if conflict_finding.finding_id in seen:
            continue
        findings.append(conflict_finding)
        seen.add(conflict_finding.finding_id)

    if synthesis_output:
        for red_flag in synthesis_output.red_flags:
            synthetic = NormalizedFinding(
                finding_id=f"red-flag-{red_flag.id}",
                source_agent=SYNTHESIS_SOURCE_TO_AGENT[red_flag.source],
                category="conflict" if red_flag.severity.value == "critical" else "earnings_quality",
                severity=red_flag.severity,
                title=red_flag.title,
                description=red_flag.description,
                metric_impact={"financial_impact": red_flag.financial_impact} if red_flag.financial_impact is not None else {},
                confidence=0.75,
                missing_data=False,
            )
            if synthetic.finding_id in seen:
                continue
            findings.append(synthetic)
            seen.add(synthetic.finding_id)

    findings.sort(key=_rank_finding, reverse=True)
    return findings[:MAX_SUMMARY_FINDINGS]


def _recommended_actions(
    scorecard: DeterministicScorecard,
    synthesis_output: SynthesisReportOutput | None,
    missing_inputs: list[MissingInput],
) -> list[str]:
    actions: list[str] = []

    if synthesis_output:
        actions.extend(step.action for step in sorted(synthesis_output.next_steps, key=lambda step: step.priority))

    for missing_input in missing_inputs:
        actions.append(f"Obtain missing diligence item: {missing_input.description}")

    if scorecard.conflicts:
        actions.append("Reconcile conflicting specialist metrics before relying on the final valuation view.")

    recommendation = scorecard.overall_recommendation
    if recommendation and recommendation in RECOMMENDATION_ACTIONS:
        actions.append(RECOMMENDATION_ACTIONS[recommendation])

    deduped: list[str] = []
    seen: set[str] = set()
    for action in actions:
        cleaned = action.strip()
        if not cleaned or cleaned in seen:
            continue
        deduped.append(cleaned)
        seen.add(cleaned)
        if len(deduped) >= MAX_RECOMMENDED_ACTIONS:
            break
    return deduped


def _agent_headline(envelope: AgentEnvelope) -> str | None:
    if envelope.findings:
        highest = sorted(envelope.findings, key=_rank_finding, reverse=True)[0]
        return highest.title
    return envelope.summary


def _scoring_impact(agent_name: AgentName, scorecard: DeterministicScorecard) -> dict[str, Any]:
    buyer_facing_dimensions = [
        key
        for key, (_, primary_agent, supporting_agents) in BUYER_DIMENSION_GROUPS.items()
        if agent_name.value == primary_agent or agent_name.value in supporting_agents
    ]
    technical_scorecard = next(
        (item for item in scorecard.technical_scorecards if item.name == AGENT_DISPLAY_NAMES.get(agent_name.value)),
        None,
    )
    risk_contribution = None
    if technical_scorecard and technical_scorecard.score is not None:
        risk_contribution = round((10 - technical_scorecard.score) * 10, 2)
    return {
        "buyerFacingDimensions": buyer_facing_dimensions,
        "riskContribution": risk_contribution,
    }


def _deep_review_sections(scorecard: DeterministicScorecard, envelopes: list[AgentEnvelope]) -> list[dict[str, Any]]:
    envelope_by_name = {envelope.agent_name: envelope for envelope in envelopes}
    reviews: list[dict[str, Any]] = []
    for agent_name in AGENT_REVIEW_ORDER:
        envelope = envelope_by_name.get(agent_name)
        if envelope is None:
            continue
        evidence = _dedupe_evidence(envelope.evidence + [item for finding in envelope.findings for item in finding.evidence])
        reviews.append(
            {
                "agentName": agent_name.value,
                "headline": _agent_headline(envelope),
                "summary": envelope.summary,
                "technicalScore": envelope.overall_score,
                "confidence": envelope.confidence,
                "keyMetrics": {key: metric.model_dump(mode="json", by_alias=True) for key, metric in envelope.normalized_metrics.items()},
                "findings": [finding.model_dump(mode="json", by_alias=True) for finding in envelope.findings],
                "evidence": [item.model_dump(mode="json", by_alias=True) for item in evidence],
                "missingInputs": [item.model_dump(mode="json", by_alias=True) for item in envelope.missing_inputs],
                "scoringImpact": _scoring_impact(agent_name, scorecard),
            }
        )
    return reviews


def _missing_data_detail(missing_inputs: list[MissingInput], envelopes: list[AgentEnvelope]) -> list[dict[str, Any]]:
    detail: list[dict[str, Any]] = []
    for missing_input in missing_inputs:
        affected_agents = sorted(
            [
                envelope.agent_name
                for envelope in envelopes
                if any(
                    item.key == missing_input.key and item.document_type == missing_input.document_type
                    for item in envelope.missing_inputs
                )
            ],
            key=lambda name: name.value,
        )
        related_findings = [
            finding.finding_id
            for envelope in envelopes
            for finding in envelope.findings
            if finding.missing_data
            and (
                missing_input.key.lower() in finding.title.lower()
                or missing_input.key.lower() in finding.description.lower()
            )
        ]
        impact_bits: list[str] = []
        if missing_input.required:
            impact_bits.append("Required input lowered report completeness.")
        if affected_agents:
            impact_bits.append(
                "Impacts " + ", ".join(AGENT_DISPLAY_NAMES.get(agent.value, agent.value) for agent in affected_agents) + "."
            )
        detail.append(
            {
                "key": missing_input.key,
                "description": missing_input.description,
                "documentType": missing_input.document_type.value if missing_input.document_type else None,
                "required": missing_input.required,
                "reason": missing_input.reason,
                "affectedAgents": [agent.value for agent in affected_agents],
                "relatedFindings": related_findings,
                "impactSummary": " ".join(impact_bits) if impact_bits else None,
            }
        )
    return detail


def _audit_trail(
    *,
    ingestion_output: IngestionOutput | None,
    envelopes: list[AgentEnvelope],
    scorecard: DeterministicScorecard,
    synthesis_result: AgentResult[SynthesisReportOutput] | None,
    metadata: PipelineMetadata | None,
    missing_inputs: list[MissingInput],
    clarification_evidence: list[EvidenceReference],
) -> list[str]:
    lines: list[str] = []
    if ingestion_output:
        lines.append(
            f"Ingestion parsed {ingestion_output.metadata.successfully_parsed} of {ingestion_output.metadata.total_documents} source documents."
        )
    lines.append(f"{len(envelopes)} specialist analyses completed successfully and fed one shared scorecard.")
    if scorecard.conflicts:
        for conflict in scorecard.conflicts:
            lines.append(f"Conflict logged for {conflict.key}; conservative value retained in deterministic scoring.")
    if missing_inputs:
        lines.append(f"{len(missing_inputs)} missing diligence inputs reduced completeness to {scorecard.completeness_score or 0:.2f}.")
    if clarification_evidence:
        lines.append(
            f"{len(clarification_evidence)} user clarifications were stored as supplemental evidence and kept below documentary confidence."
        )
    if metadata and metadata.partial_failures:
        lines.append("Partial failures were recorded for: " + ", ".join(metadata.partial_failures) + ".")
    if scorecard.overall_recommendation:
        lines.append(
            f"Deterministic recommendation resolved to {scorecard.overall_recommendation} with risk score {scorecard.overall_risk_score}."
        )
    if synthesis_result:
        lines.append(
            "Narrative synthesis "
            + ("completed after scoring." if synthesis_result.status == "success" else "did not complete; summary fell back to deterministic metadata.")
        )
    return lines


def _overview(
    scorecard: DeterministicScorecard,
    synthesis_output: SynthesisReportOutput | None,
    ingestion_output: IngestionOutput | None,
    envelopes: list[AgentEnvelope],
    agent_results: Mapping[str, AgentResult[Any]] | None = None,
) -> str:
    if synthesis_output and synthesis_output.executive_summary:
        return synthesis_output.executive_summary

    completed = len(envelopes)
    total_docs = ingestion_output.metadata.total_documents if ingestion_output else 0
    recommendation = scorecard.overall_recommendation or "analysis_pending"
    risk_score = scorecard.overall_risk_score
    completeness = scorecard.completeness_score

    not_applicable_count = 0
    if agent_results:
        not_applicable_count = sum(
            1 for r in agent_results.values() if r and r.status == "not_applicable"
        )

    agent_summary = ""
    if completed:
        agent_summary = f" {completed} specialist analyses contributed to this summary."
        if not_applicable_count:
            agent_summary += f" {not_applicable_count} agents were not applicable to the uploaded documents."
    elif not_applicable_count:
        agent_summary = f" No specialist analyses were applicable to the uploaded document set; {not_applicable_count} agents were skipped."
    else:
        agent_summary = " No specialist analyses completed successfully."

    return (
        f"Pipeline completed with recommendation '{recommendation}'"
        + (f" at risk score {risk_score}." if risk_score is not None else ".")
        + agent_summary
        + (f" The package included {total_docs} documents." if total_docs else "")
        + (f" Completeness score is {completeness:.2f}." if completeness is not None else "")
    )


def _headline(scorecard: DeterministicScorecard) -> str | None:
    recommendation = scorecard.overall_recommendation
    if not recommendation:
        return None
    return RECOMMENDATION_HEADLINES.get(recommendation, recommendation.replace("_", " ").title())


def assemble_summary_report(
    *,
    ingestion_output: IngestionOutput | None,
    agent_results: Mapping[str, AgentResult[Any]],
    scorecard: DeterministicScorecard,
    synthesis_result: AgentResult[SynthesisReportOutput] | None,
    metadata: PipelineMetadata | None = None,
    analysis_id: str | None = None,
    clarification_evidence: list[EvidenceReference] | None = None,
    include_deep_review: bool = False,
    deterministic_fallback: Any | None = None,
) -> ReportOutputV2:
    synthesis_output = None
    if synthesis_result and synthesis_result.status == "success" and synthesis_result.data:
        if isinstance(synthesis_result.data, SynthesisReportOutput):
            synthesis_output = synthesis_result.data
        else:
            synthesis_output = SynthesisReportOutput.model_validate(synthesis_result.data)
    envelopes = _successful_envelopes(agent_results)
    missing_inputs = _missing_inputs(ingestion_output, envelopes)
    clarification_evidence = clarification_evidence or []

    pipeline_status = "completed"
    if ingestion_output is None:
        pipeline_status = "failed"
    elif (metadata and metadata.partial_failures) or (synthesis_result and synthesis_result.status != "success"):
        pipeline_status = "partial"

    generated_at = (
        metadata.completed_at
        if metadata and metadata.completed_at
        else datetime.now(timezone.utc).isoformat()
    )

    # Use deterministic fallback headline/overview when all LLM agents failed
    # but we still have parsed financial data.
    fallback_headline = None
    fallback_overview = None
    if deterministic_fallback is not None and not envelopes:
        try:
            fallback_headline = deterministic_fallback.final_recommendation or None
            fallback_overview = deterministic_fallback.executive_summary or None
        except AttributeError:
            pass

    payload = {
        "modeAvailable": {"summary": True, "deep": include_deep_review},
        "summary": {
            "headline": fallback_headline or _headline(scorecard),
            "overview": fallback_overview or _overview(scorecard, synthesis_output, ingestion_output, envelopes, agent_results),
            "keyFindings": [finding.model_dump(mode="json", by_alias=True) for finding in _summary_findings(scorecard, synthesis_output)],
            "recommendedActions": _recommended_actions(scorecard, synthesis_output, missing_inputs),
        },
        "scorecard": scorecard.model_dump(mode="json", by_alias=True),
        "deepReview": (
            {
                "agentReviews": _deep_review_sections(scorecard, envelopes),
                "evidenceIndex": [
                    evidence.model_dump(mode="json", by_alias=True)
                    for evidence in _merged_evidence_index(ingestion_output, envelopes, clarification_evidence)
                ],
                "auditTrail": _audit_trail(
                    ingestion_output=ingestion_output,
                    envelopes=envelopes,
                    scorecard=scorecard,
                    synthesis_result=synthesis_result,
                    metadata=metadata,
                    missing_inputs=missing_inputs,
                    clarification_evidence=clarification_evidence,
                ),
                "missingData": _missing_data_detail(missing_inputs, envelopes),
            }
            if include_deep_review
            else None
        ),
        "metadata": {
            "contractVersion": "2.0",
            "generatedAt": generated_at,
            "analysisId": analysis_id or (ingestion_output.metadata.analysis_id if ingestion_output else None),
            "pipelineStatus": pipeline_status,
            "sourceDocumentCount": ingestion_output.metadata.total_documents if ingestion_output else 0,
            "totalTokens": metadata.total_tokens if metadata else None,
            "estimatedCost": metadata.estimated_cost if metadata else None,
            "totalLatencyMs": metadata.total_latency_ms if metadata else None,
            "auditMetadata": (
                {
                    "partialFailures": list(metadata.partial_failures),
                    "stageMetrics": {
                        key: metric.model_dump(mode="json", by_alias=True)
                        for key, metric in metadata.stage_metrics.items()
                    },
                    "summedStageLatencyMs": metadata.summed_stage_latency_ms,
                    "criticalPath": dict(metadata.critical_path),
                    "debugArtifacts": {
                        key: ref.model_dump(mode="json", by_alias=True)
                        for key, ref in metadata.debug_artifacts.items()
                    },
                    "rolloutFlags": dict(metadata.rollout_flags),
                }
                if metadata
                else None
            ),
        },
    }

    return ReportOutputV2.model_validate(payload)
