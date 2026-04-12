from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from app.agents.deterministic import AGENT_DISPLAY_NAMES, AGENT_WEIGHTS
from app.agents.schemas import (
    AgentEnvelope,
    AgentResult,
    BuyerFacingDimension,
    DeterministicScorecard,
    DeterministicTag,
    EvidenceReference,
    IngestionOutput,
    MissingInput,
    NormalizedFinding,
    NormalizedMetric,
    ScoreConflict,
    Severity,
    TechnicalScorecard,
)

SEVERITY_PENALTIES: dict[Severity, float] = {
    Severity.LOW: 1.0,
    Severity.MEDIUM: 4.0,
    Severity.HIGH: 9.0,
    Severity.CRITICAL: 16.0,
}

CONSERVATIVE_DIRECTION: dict[str, str] = {
    "revenue_latest": "min",
    "gross_margin": "min",
    "ebitda": "min",
    "ebitda_margin": "min",
    "sde_reported": "min",
    "sde_validated_candidate": "min",
    "adjusted_sde": "min",
    "working_capital": "min",
    "cash_flow_net_income_divergence": "max",
    "max_revenue_discrepancy_pct": "max",
    "missing_tax_years_count": "max",
    "tax_returns_present": "false",
    "potential_tax_exposure": "max",
    "dso": "max",
    "top_customer_ar_pct": "max",
    "write_off_risk_pct": "max",
    "over_90_ar_pct": "max",
    "top_customer_revenue_pct": "max",
    "top5_revenue_pct": "max",
    "hhi": "max",
    "single_customer_dependency": "true",
    "owner_dependence_score": "max",
    "delegated_management": "false",
    "key_person_risk_count": "max",
    "transferable_license_count": "min",
    "remaining_lease_months": "min",
    "assignment_clause_risk": "true",
    "key_contracts_non_transferable_count": "max",
    "threat_count_high_or_critical": "max",
    "asking_price": "max",
    "sde_multiple": "max",
    "dscr": "min",
    "dscr_meets_minimum": "false",
    "total_cash_needed": "max",
    "cash_needed_total": "max",
    "eligible_for_sba": "false",
}

ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    "adjusted_sde": ("adjusted_sde", "sde_validated_candidate"),
    "total_cash_needed": ("total_cash_needed", "cash_needed_total"),
}

BUYER_DIMENSION_GROUPS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "financial_quality": ("Financial Quality", "financial_analysis", ("tax_compliance",)),
    "revenue_durability": ("Revenue Durability", "customer_concentration", ("ar_collections", "market_macro")),
    "transferability": ("Transferability", "operations_transferability", ("lease_contract",)),
    "bankability": ("Bankability", "lending_affordability", ("financial_analysis",)),
}

RECOMMENDATION_ORDER = ["strong_buy", "buy", "conditional_buy", "caution", "do_not_buy"]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _agent_envelope(result: AgentResult[Any] | None) -> AgentEnvelope | None:
    if not result or result.status != "success" or not result.data:
        return None
    if isinstance(result.data, AgentEnvelope):
        return result.data
    return None


def _agent_score(result: AgentResult[Any] | None) -> int | None:
    envelope = _agent_envelope(result)
    if envelope is not None:
        return envelope.overall_score
    if result and result.status == "success" and result.data:
        score = _get_value(result.data, "overall_score")
        return int(score) if isinstance(score, (int, float)) else None
    return None


def _agent_summary(result: AgentResult[Any] | None) -> str | None:
    envelope = _agent_envelope(result)
    if envelope is not None:
        return envelope.summary
    if result and result.status == "success" and result.data:
        summary = _get_value(result.data, "summary")
        return str(summary) if summary else None
    return None


def _metric_value(metric: NormalizedMetric) -> float | int | str | bool | None:
    return metric.value


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _values_conflict(left: Any, right: Any) -> bool:
    if type(left) is type(right) and isinstance(left, (str, bool)):
        return left != right
    left_num = _coerce_number(left)
    right_num = _coerce_number(right)
    if left_num is not None and right_num is not None:
        return abs(left_num - right_num) > 1e-9
    return left != right


def _choose_conservative_key(key: str, values: list[Any]) -> Any:
    direction = CONSERVATIVE_DIRECTION.get(key, "max")
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    if direction == "false":
        return all(bool(value) for value in filtered)
    if direction == "true":
        return any(bool(value) for value in filtered)
    if direction == "min":
        numeric = [_coerce_number(value) for value in filtered]
        if all(value is not None for value in numeric):
            chosen = min(value for value in numeric if value is not None)
            return int(chosen) if all(isinstance(value, int) and not isinstance(value, bool) for value in filtered) else chosen
        return filtered[0]
    numeric = [_coerce_number(value) for value in filtered]
    if all(value is not None for value in numeric):
        chosen = max(value for value in numeric if value is not None)
        return int(chosen) if all(isinstance(value, int) and not isinstance(value, bool) for value in filtered) else chosen
    return filtered[0]


def _clone_metric(metric: NormalizedMetric, *, value: Any | None = None) -> NormalizedMetric:
    payload = metric.model_dump()
    if value is not None:
        payload["value"] = value
    return NormalizedMetric.model_validate(payload)


def _collect_metric_candidates(
    agent_results: Mapping[str, AgentResult[Any]],
) -> tuple[dict[str, list[tuple[str, NormalizedMetric]]], list[NormalizedFinding], list[MissingInput]]:
    metric_candidates: dict[str, list[tuple[str, NormalizedMetric]]] = defaultdict(list)
    findings: list[NormalizedFinding] = []
    missing_inputs: list[MissingInput] = []

    for agent_key, result in agent_results.items():
        envelope = _agent_envelope(result)
        if envelope is None:
            continue
        findings.extend(envelope.findings)
        missing_inputs.extend(envelope.missing_inputs)
        for metric_key, metric in envelope.normalized_metrics.items():
            metric_candidates[metric_key].append((agent_key, metric))

    lending_result = agent_results.get("lending_affordability")
    if lending_result and lending_result.status == "success" and lending_result.data:
        payload = lending_result.data.raw_domain_output if isinstance(lending_result.data, AgentEnvelope) else lending_result.data
        sba = _get_value(payload, "sba7a")
        affordability = _get_value(payload, "affordability_analysis")
        buyer_requirements = _get_value(payload, "buyer_requirements")
        fallbacks = {
            "dscr": NormalizedMetric(value=_get_value(sba, "dscr"), unit="ratio"),
            "dscr_meets_minimum": NormalizedMetric(value=_get_value(sba, "dscr_meets_minimum")),
            "asking_price": NormalizedMetric(value=_get_value(affordability, "asking_price"), unit="usd"),
            "adjusted_sde": NormalizedMetric(value=_get_value(affordability, "adjusted_sde"), unit="usd"),
            "sde_multiple": NormalizedMetric(value=_get_value(affordability, "sde_multiple"), unit="x"),
            "total_cash_needed": NormalizedMetric(value=_get_value(buyer_requirements, "total_cash_needed"), unit="usd"),
        }
        for metric_key, metric in fallbacks.items():
            if metric.value is not None and not metric_candidates.get(metric_key):
                metric_candidates[metric_key].append(("lending_affordability", metric))

    return metric_candidates, findings, missing_inputs


def _resolve_validated_metrics(
    agent_results: Mapping[str, AgentResult[Any]],
) -> tuple[dict[str, NormalizedMetric], list[ScoreConflict], list[NormalizedFinding], list[MissingInput]]:
    metric_candidates, findings, missing_inputs = _collect_metric_candidates(agent_results)
    validated_metrics: dict[str, NormalizedMetric] = {}
    conflicts: list[ScoreConflict] = []
    handled_keys: set[str] = set()

    for canonical_key, aliases in ALIAS_GROUPS.items():
        candidates: list[tuple[str, str, NormalizedMetric]] = []
        for alias in aliases:
            for agent_key, metric in metric_candidates.get(alias, []):
                candidates.append((alias, agent_key, metric))
        if not candidates:
            continue
        values = [_metric_value(metric) for _, _, metric in candidates]
        conservative_value = _choose_conservative_key(canonical_key, values)
        validated_metrics[canonical_key] = _clone_metric(candidates[0][2], value=conservative_value)
        handled_keys.update(aliases)
        if any(_values_conflict(values[0], value) for value in values[1:]):
            conflicts.append(
                ScoreConflict(
                    key=canonical_key,
                    description=f"Conflicting values detected for {canonical_key}; retained conservative value.",
                    conservative_value=conservative_value,
                    conflicting_values={f"{agent_key}:{alias}": _metric_value(metric) for alias, agent_key, metric in candidates},
                    evidence=[evidence for _, _, metric in candidates for evidence in metric.evidence][:8],
                )
            )

    for metric_key, candidates in metric_candidates.items():
        if metric_key in handled_keys:
            continue
        values = [_metric_value(metric) for _, metric in candidates]
        conservative_value = _choose_conservative_key(metric_key, values)
        validated_metrics[metric_key] = _clone_metric(candidates[0][1], value=conservative_value)
        if any(_values_conflict(values[0], value) for value in values[1:]):
            conflicts.append(
                ScoreConflict(
                    key=metric_key,
                    description=f"Conflicting values detected for {metric_key}; retained conservative value.",
                    conservative_value=conservative_value,
                    conflicting_values={agent_key: _metric_value(metric) for agent_key, metric in candidates},
                    evidence=[evidence for _, metric in candidates for evidence in metric.evidence][:8],
                )
            )

    return validated_metrics, conflicts, findings, missing_inputs


def _collect_missing_inputs(ingestion_output: IngestionOutput | None, envelope_missing_inputs: list[MissingInput]) -> list[MissingInput]:
    missing_inputs = list(envelope_missing_inputs)
    if ingestion_output is not None:
        missing_inputs.extend(ingestion_output.metadata.missing_inputs)
    deduped: dict[tuple[str, str | None], MissingInput] = {}
    for item in missing_inputs:
        deduped[(item.key, item.document_type.value if item.document_type else None)] = item
    return list(deduped.values())


def _base_risk_score(agent_results: Mapping[str, AgentResult[Any]]) -> float:
    successful_weights = 0.0
    weighted_sum = 0.0
    for agent_key, weight in AGENT_WEIGHTS.items():
        score = _agent_score(agent_results.get(agent_key))
        if score is None:
            continue
        successful_weights += weight
        weighted_sum += score * weight
    if successful_weights == 0:
        return 100.0
    normalized_score = weighted_sum / successful_weights
    return (11 - normalized_score) * 10


def _finding_penalty(findings: list[NormalizedFinding]) -> float:
    penalty = 0.0
    for finding in findings:
        severity_penalty = SEVERITY_PENALTIES[finding.severity]
        if finding.missing_data:
            severity_penalty += 1.0
        penalty += severity_penalty * AGENT_WEIGHTS.get(finding.source_agent.value, 0.05)
    return penalty


def _metric_penalty(validated_metrics: Mapping[str, NormalizedMetric]) -> float:
    penalty = 0.0

    def metric_number(key: str) -> float | None:
        metric = validated_metrics.get(key)
        return _coerce_number(metric.value) if metric is not None else None

    dscr = metric_number("dscr")
    if dscr is not None:
        if dscr < 1.0:
            penalty += 14.0
        elif dscr < 1.25:
            penalty += 8.0
        elif dscr < 1.4:
            penalty += 3.0

    sde_multiple = metric_number("sde_multiple")
    if sde_multiple is not None:
        if sde_multiple > 4.0:
            penalty += 8.0
        elif sde_multiple > 3.5:
            penalty += 4.0

    top_customer = metric_number("top_customer_revenue_pct")
    if top_customer is not None:
        if top_customer > 50:
            penalty += 10.0
        elif top_customer > 30:
            penalty += 6.0
        elif top_customer > 20:
            penalty += 3.0

    discrepancy = metric_number("max_revenue_discrepancy_pct")
    if discrepancy is not None:
        if discrepancy > 0.2:
            penalty += 10.0
        elif discrepancy > 0.1:
            penalty += 6.0
        elif discrepancy > 0.05:
            penalty += 3.0

    overdue_ar = metric_number("over_90_ar_pct")
    if overdue_ar is not None:
        if overdue_ar > 0.2:
            penalty += 8.0
        elif overdue_ar > 0.1:
            penalty += 4.0

    if validated_metrics.get("dscr_meets_minimum") and validated_metrics["dscr_meets_minimum"].value is False:
        penalty += 6.0
    if validated_metrics.get("eligible_for_sba") and validated_metrics["eligible_for_sba"].value is False:
        penalty += 6.0
    if validated_metrics.get("single_customer_dependency") and validated_metrics["single_customer_dependency"].value is True:
        penalty += 4.0

    return penalty


def _compute_completeness_score(
    ingestion_output: IngestionOutput | None,
    agent_results: Mapping[str, AgentResult[Any]],
    missing_inputs: list[MissingInput],
) -> float:
    success_weight = sum(
        AGENT_WEIGHTS[agent_key]
        for agent_key in AGENT_WEIGHTS
        if agent_results.get(agent_key) and agent_results[agent_key].status == "success"
    )
    base = success_weight / sum(AGENT_WEIGHTS.values())
    required_missing = sum(1 for item in missing_inputs if item.required)
    optional_missing = len(missing_inputs) - required_missing
    failed_documents = len(ingestion_output.metadata.failed_documents) if ingestion_output is not None else 0
    total_documents = ingestion_output.metadata.total_documents if ingestion_output is not None else 0
    failed_ratio = (failed_documents / total_documents) if total_documents else 0.0
    penalty = min(0.4, (required_missing * 0.04) + (optional_missing * 0.015) + (failed_ratio * 0.1))
    return round(_clamp(base - penalty, 0.0, 1.0), 4)


def _compute_confidence_score(
    ingestion_output: IngestionOutput | None,
    agent_results: Mapping[str, AgentResult[Any]],
    missing_inputs: list[MissingInput],
    conflicts: list[ScoreConflict],
) -> float:
    weighted_confidence = 0.0
    total_weight = 0.0
    for agent_key, weight in AGENT_WEIGHTS.items():
        envelope = _agent_envelope(agent_results.get(agent_key))
        if envelope is None or envelope.confidence is None:
            continue
        weighted_confidence += float(envelope.confidence) * weight
        total_weight += weight
    base = (weighted_confidence / total_weight) if total_weight else 0.0
    if ingestion_output is not None and ingestion_output.metadata.overall_confidence is not None:
        base = (base * 0.8) + (float(ingestion_output.metadata.overall_confidence) * 0.2)
    required_missing = sum(1 for item in missing_inputs if item.required)
    penalty = min(0.45, (required_missing * 0.03) + (len(conflicts) * 0.05))
    return round(_clamp(base - penalty, 0.0, 1.0), 4)


def _technical_scorecard_recommendation(score: int | None, findings: list[NormalizedFinding]) -> str | None:
    if score is None:
        return None
    highest_severity = max((SEVERITY_PENALTIES[finding.severity] for finding in findings), default=0.0)
    if score >= 8 and highest_severity < SEVERITY_PENALTIES[Severity.HIGH]:
        return "strong"
    if score >= 6 and highest_severity < SEVERITY_PENALTIES[Severity.CRITICAL]:
        return "watch"
    return "high_risk"


def _build_technical_scorecards(agent_results: Mapping[str, AgentResult[Any]]) -> list[TechnicalScorecard]:
    scorecards: list[TechnicalScorecard] = []
    for agent_key, display_name in AGENT_DISPLAY_NAMES.items():
        result = agent_results.get(agent_key)
        envelope = _agent_envelope(result)
        if result and result.status == "success" and result.data:
            score = _agent_score(result)
            findings = list(envelope.findings) if envelope else []
            metrics = dict(envelope.normalized_metrics) if envelope else {}
            scorecards.append(
                TechnicalScorecard(
                    name=display_name,
                    score=score,
                    recommendation=_technical_scorecard_recommendation(score, findings),
                    findings=findings,
                    metrics=metrics,
                )
            )
        else:
            scorecards.append(TechnicalScorecard(name=display_name, recommendation="analysis_unavailable"))
    return scorecards


def _build_buyer_facing_dimensions(agent_results: Mapping[str, AgentResult[Any]]) -> list[BuyerFacingDimension]:
    dimensions: list[BuyerFacingDimension] = []
    for key, (label, primary_agent, supporting_agents) in BUYER_DIMENSION_GROUPS.items():
        agents = (primary_agent, *supporting_agents)
        scores = [score for score in (_agent_score(agent_results.get(agent_key)) for agent_key in agents) if score is not None]
        summaries = [summary for summary in (_agent_summary(agent_results.get(agent_key)) for agent_key in agents) if summary]
        available_count = sum(1 for agent_key in agents if agent_results.get(agent_key) and agent_results[agent_key].status == "success")
        if available_count == 0:
            dimensions.append(BuyerFacingDimension(key=key, label=label, status="unavailable", summary="Analysis unavailable."))
            continue
        status = "available" if available_count == len(agents) else "partial"
        dimensions.append(
            BuyerFacingDimension(
                key=key,
                label=label,
                score=round(sum(scores) / len(scores), 2) if scores else None,
                status=status,
                summary=" ".join(summaries[:2]) if summaries else None,
            )
        )
    return dimensions


def _deal_breakers(findings: list[NormalizedFinding], validated_metrics: Mapping[str, NormalizedMetric]) -> list[NormalizedFinding]:
    deal_breakers = [
        finding
        for finding in findings
        if finding.severity == Severity.CRITICAL or DeterministicTag.DEAL_BREAKER_CANDIDATE in finding.deterministic_tags
    ]
    dscr_metric = validated_metrics.get("dscr")
    if dscr_metric is not None and _coerce_number(dscr_metric.value) is not None and float(dscr_metric.value) < 1.0:
        deal_breakers.extend(
            [
                finding
                for finding in findings
                if finding.source_agent.value == "lending_affordability" and finding.severity in {Severity.HIGH, Severity.CRITICAL}
            ]
        )
    unique: dict[str, NormalizedFinding] = {finding.finding_id: finding for finding in deal_breakers}
    return list(unique.values())


def _worsen_recommendation(recommendation: str | None, steps: int = 1) -> str | None:
    if recommendation is None:
        return None
    index = RECOMMENDATION_ORDER.index(recommendation)
    return RECOMMENDATION_ORDER[min(len(RECOMMENDATION_ORDER) - 1, index + steps)]


def _recommendation_for_risk_score(
    risk_score: int | None,
    *,
    deal_breakers: list[NormalizedFinding],
    conflicts: list[ScoreConflict],
    completeness_score: float,
    confidence_score: float,
    validated_metrics: Mapping[str, NormalizedMetric],
) -> str | None:
    if risk_score is None:
        return None
    if risk_score <= 20:
        recommendation = "strong_buy"
    elif risk_score <= 45:
        recommendation = "buy"
    elif risk_score <= 65:
        recommendation = "conditional_buy"
    elif risk_score <= 80:
        recommendation = "caution"
    else:
        recommendation = "do_not_buy"

    critical_breakers = [finding for finding in deal_breakers if finding.severity == Severity.CRITICAL]
    if critical_breakers:
        recommendation = _worsen_recommendation(recommendation, 2)
    elif deal_breakers or len(conflicts) >= 2 or completeness_score < 0.45 or confidence_score < 0.45:
        recommendation = _worsen_recommendation(recommendation)

    dscr_metric = validated_metrics.get("dscr")
    dscr_value = _coerce_number(dscr_metric.value) if dscr_metric is not None else None
    if dscr_value is not None and dscr_value < 1.0:
        recommendation = _worsen_recommendation(recommendation)
    if validated_metrics.get("eligible_for_sba") and validated_metrics["eligible_for_sba"].value is False:
        recommendation = _worsen_recommendation(recommendation)
    return recommendation


def compute_pipeline_scorecard(
    ingestion_output: IngestionOutput | None,
    agent_results: Mapping[str, AgentResult[Any]],
) -> DeterministicScorecard:
    validated_metrics, conflicts, findings, envelope_missing_inputs = _resolve_validated_metrics(agent_results)
    missing_inputs = _collect_missing_inputs(ingestion_output, envelope_missing_inputs)
    completeness_score = _compute_completeness_score(ingestion_output, agent_results, missing_inputs)
    confidence_score = _compute_confidence_score(ingestion_output, agent_results, missing_inputs, conflicts)

    risk_score = _base_risk_score(agent_results)
    risk_score += _finding_penalty(findings)
    risk_score += _metric_penalty(validated_metrics)
    risk_score += min(12.0, len(conflicts) * 4.0)
    risk_score += min(15.0, sum(3.0 if item.required else 1.0 for item in missing_inputs))
    overall_risk_score = int(round(_clamp(risk_score, 1.0, 100.0)))

    deal_breakers = _deal_breakers(findings, validated_metrics)
    recommendation = _recommendation_for_risk_score(
        overall_risk_score,
        deal_breakers=deal_breakers,
        conflicts=conflicts,
        completeness_score=completeness_score,
        confidence_score=confidence_score,
        validated_metrics=validated_metrics,
    )

    return DeterministicScorecard(
        overall_risk_score=overall_risk_score,
        overall_recommendation=recommendation,
        buyer_facing_dimensions=_build_buyer_facing_dimensions(agent_results),
        technical_scorecards=_build_technical_scorecards(agent_results),
        deal_breakers=deal_breakers,
        conflicts=conflicts,
        completeness_score=completeness_score,
        confidence_score=confidence_score,
        validated_metrics=validated_metrics,
    )
