from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from app.agents.deterministic import AGENT_DISPLAY_NAMES
from app.agents.evidence_utils import build_evidence_fields
from app.agents.schemas import (
    AgentEnvelope,
    AgentResult,
    DeterministicScorecard,
    DocumentInfo,
    DocumentSection,
    DocumentType,
    IngestionOutput,
    NormalizedFinding,
    NormalizedMetric,
)

_NOISY_RAW_KEYS = {"rows", "tables", "raw_rows", "table", "cells"}
_PREFERRED_VALIDATED_METRICS = (
    "adjusted_sde",
    "revenue_latest",
    "revenue_growth_yoy",
    "gross_margin",
    "ebitda",
    "ebitda_margin",
    "working_capital",
    "dso",
)


def compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True, default=str)


def describe_user_message(user_message: str) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "user_message_chars": len(user_message),
        "prompt_sections": {},
    }
    if not user_message:
        diagnostics["prompt_chars"] = 0
        return diagnostics

    header, _, body = user_message.partition("\n")
    diagnostics["message_header"] = header.strip("# ").strip() or None
    stripped_body = body.strip()
    diagnostics["prompt_chars"] = len(user_message)
    if not stripped_body or not stripped_body.startswith("{"):
        return diagnostics

    try:
        payload = json.loads(stripped_body)
    except json.JSONDecodeError:
        return diagnostics

    diagnostics["prompt_sections"] = {
        str(key): len(compact_json(value))
        for key, value in payload.items()
    }

    evidence_count = _count_prompt_items(
        payload,
        {
            "evidence_pack",
            "snippet_pack",
            "context_snippets",
            "specialist_briefs",
            "deal_breakers",
            "top_findings",
        },
    )
    if evidence_count:
        diagnostics["evidence_count"] = evidence_count

    truncation = _collect_truncation_metadata(payload)
    if truncation:
        diagnostics["context_truncation"] = truncation

    return diagnostics


def build_financial_user_message(
    ingestion_output: IngestionOutput,
    metrics: Mapping[str, Any],
    *,
    warning: str | None = None,
) -> str:
    payload = {
        "metrics": metrics,
        "evidence_pack": _build_section_pack(
            ingestion_output,
            {"profit_and_loss", "balance_sheet", "cash_flow_statement", "sde_summary"},
            max_items=8,
            max_total_snippet_chars=2000,
            max_fields=10,
        ),
        "missing_data_notes": _notes(warning),
    }
    return "## Financial Context\n" + compact_json(_drop_empty(payload))


def build_tax_user_message(
    ingestion_output: IngestionOutput,
    metrics: Mapping[str, Any],
    *,
    missing_tax_returns: bool = False,
) -> str:
    notes = []
    if missing_tax_returns:
        notes.append(
            "No tax return documents were found. Confidence should be low, unreported income risk should be high, and the summary should state that tax returns must be obtained before close."
        )
    payload = {
        "metrics": metrics,
        "evidence_pack": _build_section_pack(
            ingestion_output,
            {"tax_return_1120s", "tax_return_1040", "tax_return_schedule_c", "profit_and_loss"},
            max_items=8,
            max_total_snippet_chars=1800,
            max_fields=10,
        ),
        "missing_data_notes": notes,
    }
    return "## Tax Context\n" + compact_json(_drop_empty(payload))


def build_ar_user_message(
    ingestion_output: IngestionOutput,
    metrics: Mapping[str, Any],
) -> str:
    payload = {
        "metrics": metrics,
        "evidence_pack": _build_section_pack(
            ingestion_output,
            {"ar_aging_report"},
            max_items=6,
            max_total_snippet_chars=1200,
            max_fields=10,
        ),
    }
    return "## AR Context\n" + compact_json(_drop_empty(payload))


def build_customer_user_message(
    ingestion_output: IngestionOutput,
    metrics: Mapping[str, Any],
) -> str:
    notes = []
    if not metrics.get("customers"):
        notes.append("No structured customer list was found in the provided documents. Use low confidence and explain the gap clearly.")
    payload = {
        "metrics": metrics if metrics.get("customers") else None,
        "snippet_pack": _build_section_pack(
            ingestion_output,
            {"customer_list", "contract"},
            max_items=5,
            max_total_snippet_chars=1600,
            max_fields=8,
        ),
        "missing_data_notes": notes,
    }
    return "## Customer Context\n" + compact_json(_drop_empty(payload))


def build_ops_user_message(
    ingestion_output: IngestionOutput,
    metrics: Mapping[str, Any],
) -> str:
    payload = {
        "metrics": metrics,
        "snippet_pack": _build_section_pack(
            ingestion_output,
            {"employee_roster", "insurance_policy", "equipment_list", "other"},
            max_items=5,
            max_total_snippet_chars=1600,
            max_fields=8,
        ),
    }
    return "## Operations Context\n" + compact_json(_drop_empty(payload))


def build_lease_user_message(
    ingestion_output: IngestionOutput,
    metrics: Mapping[str, Any],
) -> str:
    payload = {
        "metrics": metrics,
        "snippet_pack": _build_section_pack(
            ingestion_output,
            {"lease_agreement", "contract", "other"},
            max_items=6,
            max_total_snippet_chars=1800,
            max_fields=8,
        ),
    }
    return "## Lease & Contract Context\n" + compact_json(_drop_empty(payload))


def build_market_user_message(
    ingestion_output: IngestionOutput,
    *,
    business_type: str,
    location: str,
    revenue_range: str | None = None,
    employee_count: int | None = None,
) -> str:
    notes = []
    if business_type.startswith("Unknown"):
        notes.append("Business type was not provided directly and may need to be inferred from the documents.")
    if location.startswith("Unknown"):
        notes.append("Location was not provided directly and may need to be inferred from the documents.")
    if not any(section.raw_text.strip() for doc in ingestion_output.documents for section in doc.sections):
        notes.append("Document context is limited. If external market research is not available, lower confidence accordingly.")

    payload = {
        "business_profile": _drop_empty(
            {
                "business_type": business_type,
                "location": location,
                "annual_revenue_range": revenue_range,
                "employee_count": employee_count,
            }
        ),
        "uploaded_documents": [
            {
                "file_name": doc.file_name,
                "document_type": doc.document_type.value,
                "status": doc.status.value,
            }
            for doc in ingestion_output.documents
        ],
        "context_snippets": _build_section_pack(
            ingestion_output,
            {doc.document_type.value for doc in ingestion_output.documents},
            max_items=4,
            max_total_snippet_chars=1400,
            max_fields=6,
        ),
        "missing_data_notes": notes,
    }
    return "## Market Context\n" + compact_json(_drop_empty(payload))


def build_synthesis_user_message(
    scorecard: DeterministicScorecard,
    agent_results: Mapping[str, AgentResult[Any]],
    metrics: Mapping[str, Any],
) -> str:
    successful_agents = list(metrics.get("successful_agents", []))
    section_summaries = metrics.get("section_summaries", {})
    payload = {
        "deterministic_scorecard": _compact_scorecard(scorecard),
        "specialist_context": _drop_empty(
            {
                "available_analyses": successful_agents,
                "failed_analyses": list(metrics.get("failed_agents", []))[:6],
                "overall_completeness": metrics.get("completeness"),
                "red_flags": _unique_finding_briefs(
                    metrics.get("red_flags", []),
                    max_items=4,
                    max_description_chars=140,
                ),
                "green_flags": _unique_finding_briefs(
                    metrics.get("green_flags", []),
                    max_items=2,
                    max_description_chars=120,
                ),
                "specialist_briefs": [
                brief
                for key in successful_agents
                if (brief := _agent_brief(key, agent_results.get(key), section_summaries=section_summaries)) is not None
                ],
            }
        ),
    }
    return "## Synthesis Context\n" + compact_json(_drop_empty(payload))


def _compact_scorecard(scorecard: DeterministicScorecard) -> dict[str, Any]:
    validated_metrics = _select_validated_metrics(scorecard.validated_metrics, max_items=8)

    return _drop_empty(
        {
            "overall_risk_score": scorecard.overall_risk_score,
            "overall_recommendation": scorecard.overall_recommendation,
            "completeness_score": scorecard.completeness_score,
            "confidence_score": scorecard.confidence_score,
            "buyer_facing_dimensions": [
                _drop_empty(
                    {
                        "label": dimension.label,
                        "score": dimension.score,
                        "status": dimension.status,
                    }
                )
                for dimension in scorecard.buyer_facing_dimensions[:4]
            ],
            "deal_breakers": _unique_finding_briefs(
                scorecard.deal_breakers,
                max_items=4,
                max_description_chars=120,
            ),
            "conflicts": [
                _drop_empty(
                    {
                        "key": conflict.key,
                        "description": _clip_text(conflict.description, 120),
                        "conservative_value": conflict.conservative_value,
                    }
                )
                for conflict in scorecard.conflicts[:4]
            ],
            "validated_metrics": validated_metrics,
            "technical_scorecards": [
                _drop_empty(
                    {
                        "name": technical_scorecard.name,
                        "score": technical_scorecard.score,
                        "recommendation": technical_scorecard.recommendation,
                    }
                )
                for technical_scorecard in scorecard.technical_scorecards[:8]
            ],
        }
    )


def _agent_brief(
    agent_key: str,
    result: AgentResult[Any] | None,
    *,
    section_summaries: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not result or result.status != "success" or not result.data:
        return None
    data = result.data
    section_summary = (section_summaries or {}).get(agent_key, {})
    if isinstance(data, AgentEnvelope):
        return _drop_empty(
            {
                "agent": AGENT_DISPLAY_NAMES.get(agent_key, agent_key),
                "score": data.overall_score,
                "confidence": data.confidence,
                "summary": _clip_text(data.summary, 180),
                "top_findings": _unique_finding_briefs(data.findings, max_items=2, max_description_chars=120),
                "top_risks": list(section_summary.get("top_risks", []))[:2] if isinstance(section_summary, Mapping) else [],
                "missing_inputs": [item.description for item in data.missing_inputs[:2]],
            }
        )
    return _drop_empty(
        {
            "agent": AGENT_DISPLAY_NAMES.get(agent_key, agent_key),
            "score": getattr(data, "overall_score", None),
            "confidence": getattr(data, "confidence", None),
            "summary": _clip_text(getattr(data, "summary", None), 180),
        }
    )


def _select_validated_metrics(
    metrics: Mapping[str, NormalizedMetric],
    *,
    max_items: int,
) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key in _PREFERRED_VALIDATED_METRICS:
        metric = metrics.get(key)
        if metric is None:
            continue
        selected[key] = _compact_metric(metric)
        if len(selected) >= max_items:
            return selected

    for key, metric in metrics.items():
        if key in selected:
            continue
        selected[key] = _compact_metric(metric)
        if len(selected) >= max_items:
            break
    return selected


def _unique_finding_briefs(
    findings: Iterable[Any],
    *,
    max_items: int,
    max_description_chars: int,
) -> list[dict[str, Any]]:
    briefs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in findings:
        identity = _finding_identity(finding)
        if identity in seen:
            continue
        seen.add(identity)
        brief = _finding_brief(finding, max_description_chars=max_description_chars)
        if brief:
            briefs.append(brief)
        if len(briefs) >= max_items:
            break
    return briefs


def _finding_identity(finding: Any) -> str:
    finding_id = _value_from_item(finding, "finding_id", "id")
    if finding_id:
        return f"id:{finding_id}"
    title = _value_from_item(finding, "title")
    if title:
        return f"title:{str(title).strip().lower()}"
    description = _value_from_item(finding, "description")
    return f"description:{_clip_text(str(description or ''), 80)}"


def _build_section_pack(
    ingestion_output: IngestionOutput,
    document_types: Iterable[DocumentType | str],
    *,
    max_items: int,
    max_total_snippet_chars: int,
    max_fields: int,
) -> list[dict[str, Any]]:
    allowed = {item.value if isinstance(item, DocumentType) else item for item in document_types}
    section_entries: list[tuple[DocumentInfo, DocumentSection]] = []
    for doc in ingestion_output.documents:
        for section in doc.sections:
            if _section_matches(section, allowed, doc):
                section_entries.append((doc, section))

    section_entries.sort(
        key=lambda item: (
            -(item[1].timeframe.fiscal_year or -1),
            item[0].file_name,
            item[1].page or item[1].page_start or 0,
            item[1].section_name or item[1].section_id or "",
        )
    )

    remaining_chars = max_total_snippet_chars
    packed: list[dict[str, Any]] = []
    for doc, section in section_entries:
        if len(packed) >= max_items:
            break

        snippet = None
        cleaned_text = _clip_text(section.raw_text, min(320, remaining_chars))
        if cleaned_text:
            snippet = cleaned_text
            remaining_chars = max(0, remaining_chars - len(cleaned_text))

        key_fields = _limit_mapping(_preview_extracted_data(section), max_fields)
        item = _drop_empty(
            {
                "document": doc.file_name,
                "document_type": _section_type_value(section, doc),
                "section": section.section_name or section.section_id,
                "section_kind": section.section_kind,
                "fiscal_year": section.timeframe.fiscal_year,
                "page": section.page or section.page_start,
                "key_fields": key_fields,
                "snippet": snippet,
            }
        )
        if item:
            packed.append(item)
    return packed


def _preview_extracted_data(section: DocumentSection) -> dict[str, Any]:
    preview = _limit_mapping(build_evidence_fields(section), 8)
    if preview:
        return preview

    preview = {}
    for key, value in (section.extracted_data or {}).items():
        if key in _NOISY_RAW_KEYS:
            continue
        compact_value = _compact_value(value)
        if compact_value in (None, "", [], {}):
            continue
        preview[str(key)] = compact_value
        if len(preview) >= 8:
            break
    return preview


def _compact_value(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return _clip_text(value, 120)
    if isinstance(value, list):
        compact_items = [_compact_value(item) for item in value[:3]]
        if len(value) > 3:
            compact_items.append(f"... ({len(value) - 3} more)")
        return compact_items
    if isinstance(value, dict):
        compact_dict = {}
        for key, item in value.items():
            if key in _NOISY_RAW_KEYS:
                continue
            compact_item = _compact_value(item)
            if compact_item in (None, "", [], {}):
                continue
            compact_dict[str(key)] = compact_item
            if len(compact_dict) >= 4:
                break
        return compact_dict
    return _clip_text(str(value), 120)


def _compact_metric(metric: NormalizedMetric) -> dict[str, Any]:
    return _drop_empty(
        {
            "value": metric.value,
            "unit": metric.unit,
            "display_value": metric.display_value,
            "confidence": metric.confidence,
        }
    )


def _finding_brief(
    finding: NormalizedFinding | Any,
    *,
    max_description_chars: int = 180,
    max_title_chars: int = 120,
) -> dict[str, Any]:
    severity = _value_from_item(finding, "severity")
    severity_value = severity.value if hasattr(severity, "value") else severity
    return _drop_empty(
        {
            "id": _value_from_item(finding, "finding_id", "id"),
            "severity": severity_value,
            "title": _clip_text(_value_from_item(finding, "title"), max_title_chars),
            "description": _clip_text(_value_from_item(finding, "description"), max_description_chars),
        }
    )


def _value_from_item(item: Any, *names: str) -> Any:
    if isinstance(item, Mapping):
        for name in names:
            if name in item:
                return item[name]
        return None
    for name in names:
        value = getattr(item, name, None)
        if value is not None:
            return value
    return None


def _limit_mapping(data: Mapping[str, Any], max_items: int) -> dict[str, Any]:
    limited: dict[str, Any] = {}
    for key, value in data.items():
        if value in (None, "", [], {}):
            continue
        limited[key] = value
        if len(limited) >= max_items:
            break
    return limited


def _drop_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {key: _drop_empty(item) for key, item in value.items()}
        return {key: item for key, item in cleaned.items() if item not in (None, "", [], {})}
    if isinstance(value, list):
        cleaned = [_drop_empty(item) for item in value]
        return [item for item in cleaned if item not in (None, "", [], {})]
    return value


def _notes(*values: str | None) -> list[str]:
    return [value for value in values if value]


def _clip_text(value: str | None, max_chars: int) -> str | None:
    if not value:
        return None
    cleaned = " ".join(str(value).split())
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 3:
        return cleaned[:max_chars]
    return cleaned[: max_chars - 3] + "..."


def _section_type_value(section: DocumentSection, doc: DocumentInfo | None = None) -> str:
    if section.section_kind and section.section_kind != DocumentType.OTHER.value:
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


def _count_prompt_items(value: Any, keys: set[str]) -> int:
    if isinstance(value, dict):
        total = 0
        for key, item in value.items():
            if key in keys and isinstance(item, list):
                total += len(item)
            total += _count_prompt_items(item, keys)
        return total
    if isinstance(value, list):
        return sum(_count_prompt_items(item, keys) for item in value)
    return 0


def _collect_truncation_metadata(payload: Any) -> dict[str, Any]:
    truncated_fields: list[str] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, str):
            if value.endswith("...") or value.startswith("... ("):
                truncated_fields.append(path)
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                next_path = f"{path}.{key}" if path else str(key)
                walk(item, next_path)

    walk(payload, "")
    if not truncated_fields:
        return {}
    return {
        "truncated_field_count": len(truncated_fields),
        "truncated_fields": truncated_fields[:12],
    }
