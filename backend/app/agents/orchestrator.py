from __future__ import annotations

import asyncio
import inspect
import logging
import time
from datetime import datetime, timezone
from functools import partial
from typing import Any, Callable, Dict

from app.agents.registry import AGENT_REGISTRY
from app.agents.schemas import (
    AgentErrorPayload,
    AgentResult,
    DocumentType,
    IngestionOutput,
    PipelineInput,
    PipelineMetadata,
    PipelineStageMetric,
    PipelineState,
)
from app.agents.runners import (
    run_ar_collections,
    run_customer_concentration,
    run_document_ingestion,
    run_financial_analysis,
    run_lease_contract,
    run_lending_affordability,
    run_market_macro,
    run_ops_transferability,
    run_tax_compliance,
    run_synthesis_report,
)
from app.core.config import get_settings
from app.services.analysis_repository import get_analysis_artifact_repository
from app.services.clarification_service import build_clarification_evidence, store_clarification_answers
from app.services.report_assembler import assemble_summary_report
from app.services.scoring_engine import compute_pipeline_scorecard

logger = logging.getLogger(__name__)

MODEL_PRICING = {
    "openai/gpt-5-mini": {"type": "per_token", "input": 0.25, "output": 2.0},
    "z-ai/glm-5.1":     {"type": "per_token", "input": 0.95, "output": 3.15},
    "mistral-ocr-2512": {"type": "per_page",  "rate": 0.002},
}

_DEFAULT_PROMPT_DEBUG_STAGES = {
    "ingestion",
    "financial_analysis",
    "tax_compliance",
    "ar_collections",
    "customer_concentration",
    "operations_transferability",
    "lease_contract",
    "market_macro",
    "lending_affordability",
    "synthesis_report",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_agent_error(
    *,
    agent_name: str,
    error_type: str,
    message: str,
    retry_count: int,
    latency_ms: int | None = None,
    status: str = "error",
) -> AgentResult[Any]:
    return AgentResult(
        status=status,
        error=AgentErrorPayload(
            agent_name=agent_name,
            error_type=error_type,
            message=message,
            timestamp=_timestamp(),
            retry_count=retry_count,
        ),
        latency_ms=latency_ms,
    )


def _make_abort_error(message: str) -> AgentResult[Any]:
    return _make_agent_error(
        agent_name="pipeline",
        error_type="unknown",
        message=message,
        retry_count=0,
    )


def _result_tokens(result: AgentResult[Any] | None) -> int:
    if not result or result.status != "success":
        return 0
    return result.token_usage.input + result.token_usage.output


def _estimate_result_cost(result: AgentResult[Any] | None, registry_key: str) -> float:
    if not result or result.status != "success":
        return 0.0
    if result.cost_usd > 0.0:
        return result.cost_usd
    model_name = AGENT_REGISTRY[registry_key].model
    pricing = MODEL_PRICING.get(model_name)
    if not pricing or pricing.get("type") != "per_token":
        return 0.0
    return (
        (result.token_usage.input / 1_000_000) * pricing["input"]
        + (result.token_usage.output / 1_000_000) * pricing["output"]
    )


async def _run_in_executor(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


def _resolve_stage_timeout(registry_key: str, default_timeout_seconds: float) -> float | None:
    config = AGENT_REGISTRY.get(registry_key)
    if config and config.timeout_seconds is not None:
        configured_timeout = float(config.timeout_seconds)
        return configured_timeout if configured_timeout > 0 else None
    return float(default_timeout_seconds) if default_timeout_seconds > 0 else None


def _emit_progress(
    progress_callback: Callable[..., None] | None,
    stage: str,
    message: str,
    progress: float,
    completed_agents: list[str] | None = None,
    running_agents: list[str] | None = None,
    queued_agents: list[str] | None = None,
    agent_statuses: dict[str, str] | None = None,
    fallback_mode_active: bool | None = None,
) -> None:
    if progress_callback is not None:
        progress_callback(
            stage,
            message,
            progress,
            completed_agents or [],
            running_agents=running_agents or [],
            queued_agents=queued_agents or [],
            agent_statuses=agent_statuses or {},
            fallback_mode_active=bool(fallback_mode_active),
        )


def _stage_metric(
    *,
    result: AgentResult[Any],
    attempts: int,
    timeout_seconds: float | None,
    registry_key: str,
    queued_at: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    timed_out: bool = False,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
) -> PipelineStageMetric:
    return PipelineStageMetric(
        attempts=attempts,
        retries_applied=max(0, attempts - 1),
        status=result.status,
        latency_ms=result.latency_ms or 0,
        total_tokens=_result_tokens(result),
        estimated_cost=_estimate_result_cost(result, registry_key),
        timeout_seconds=timeout_seconds,
        error_type=result.error.error_type if result.error else None,
        error_message=result.error.message if result.error else None,
        queued_at=queued_at,
        started_at=started_at,
        completed_at=completed_at,
        timed_out=timed_out,
        fallback_used=fallback_used or bool(result.diagnostics.get("fallback_used")),
        fallback_reason=fallback_reason,
        prompt_chars=result.diagnostics.get("prompt_chars"),
        response_chars=result.diagnostics.get("response_chars"),
        evidence_count=result.diagnostics.get("evidence_count"),
        model=result.diagnostics.get("model"),
        schema_chars=result.diagnostics.get("schema_chars"),
        token_usage_known=bool(result.diagnostics.get("token_usage_known", True)),
        token_usage_unknown_due_to_timeout=bool(result.diagnostics.get("token_usage_unknown_due_to_timeout", False)),
        provider_response_received=bool(result.diagnostics.get("provider_response_received", False)),
        provider_usage_received=bool(result.diagnostics.get("usage_received", False)),
        request_started_at=result.diagnostics.get("request_started_at"),
        request_finished_at=result.diagnostics.get("request_finished_at"),
        tool_call_found=bool(result.diagnostics.get("tool_call_found", False)),
        validation_passed=bool(result.diagnostics.get("validation_passed", False)),
        prompt_sections=dict(result.diagnostics.get("prompt_sections", {})),
        context_truncation=dict(result.diagnostics.get("context_truncation", {})),
    )


def _selected_prompt_debug_stages(settings: Any) -> set[str]:
    configured = {
        str(stage).strip()
        for stage in getattr(settings, "pipeline_prompt_debug_stages", []) or []
        if str(stage).strip()
    }
    return configured or set(_DEFAULT_PROMPT_DEBUG_STAGES)


def _supports_diagnostic_context(func: Any) -> bool:
    try:
        return "diagnostic_context" in inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False


def _finalize_result_diagnostics(
    result: AgentResult[Any],
    diagnostic_context: dict[str, Any],
    *,
    timed_out: bool,
    fallback_used: bool,
) -> AgentResult[Any]:
    context_diagnostics = {
        key: value
        for key, value in diagnostic_context.items()
        if key != "capture_prompt_bodies"
    }
    diagnostics = dict(context_diagnostics)
    diagnostics.update(result.diagnostics)
    provider_usage_received = bool(diagnostics.get("usage_received", False))
    token_usage_known = bool(diagnostics.get("token_usage_known", False)) or provider_usage_received or bool(
        result.token_usage.input or result.token_usage.output
    )
    diagnostics["provider_response_received"] = bool(diagnostics.get("provider_response_received", False))
    diagnostics["usage_received"] = provider_usage_received
    diagnostics["token_usage_known"] = token_usage_known
    diagnostics["token_usage_unknown_due_to_timeout"] = bool(timed_out and not token_usage_known)
    diagnostics["timed_out"] = bool(timed_out)
    diagnostics["fallback_used"] = bool(fallback_used or diagnostics.get("fallback_used"))
    return result.model_copy(update={"diagnostics": diagnostics})


async def _execute_stage(
    *,
    stage_key: str,
    registry_key: str,
    func,
    args: tuple[Any, ...],
    metadata: PipelineMetadata,
    timeout_seconds: float | None,
    retry_attempts: int,
    queued_at: str | None = None,
    timeout_fallback: Callable[[], AgentResult[Any]] | None = None,
    capture_prompt_bodies: bool = False,
) -> AgentResult[Any]:
    attempts = 0
    last_result: AgentResult[Any] | None = None
    first_started_at: str | None = None
    completed_at: str | None = None
    timed_out = False
    fallback_used = False
    fallback_reason: str | None = None
    diagnostic_context: dict[str, Any] = {"capture_prompt_bodies": capture_prompt_bodies}

    while attempts <= retry_attempts:
        attempts += 1
        attempt_started = time.perf_counter()
        attempt_started_at = _timestamp()
        if first_started_at is None:
            first_started_at = attempt_started_at
        try:
            stage_callable = (
                partial(func, *args, diagnostic_context=diagnostic_context)
                if _supports_diagnostic_context(func)
                else partial(func, *args)
            )
            setattr(stage_callable, "__name__", getattr(func, "__name__", "stage_callable"))
            if timeout_seconds is None:
                result = await _run_in_executor(stage_callable)
            else:
                result = await asyncio.wait_for(_run_in_executor(stage_callable), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            timed_out = True
            latency_ms = int((time.perf_counter() - attempt_started) * 1000)
            timeout_label = f"{timeout_seconds:.1f}s" if timeout_seconds is not None else "the configured limit"
            if timeout_fallback is not None:
                try:
                    result = timeout_fallback()
                    if result is None:
                        raise RuntimeError("timeout fallback returned no result")
                    fallback_used = True
                    fallback_reason = f"{stage_key} timed out after {timeout_label} and used a deterministic fallback."
                    if result.latency_ms is None:
                        result = result.model_copy(update={"latency_ms": latency_ms})
                except Exception as fallback_exc:
                    result = _make_agent_error(
                        agent_name=stage_key,
                        error_type="timeout",
                        message=(
                            f"{stage_key} timed out after {timeout_label}, and fallback generation failed: {fallback_exc}"
                        ),
                        retry_count=attempts - 1,
                        latency_ms=latency_ms,
                    )
            else:
                result = _make_agent_error(
                    agent_name=stage_key,
                    error_type="timeout",
                    message=f"{stage_key} timed out after {timeout_label}.",
                    retry_count=attempts - 1,
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            result = _make_agent_error(
                agent_name=stage_key,
                error_type="exception",
                message=f"{stage_key} raised an exception: {exc}",
                retry_count=attempts - 1,
                latency_ms=int((time.perf_counter() - attempt_started) * 1000),
            )

        if result.latency_ms is None:
            result = result.model_copy(update={"latency_ms": int((time.perf_counter() - attempt_started) * 1000)})

        result = _finalize_result_diagnostics(
            result,
            diagnostic_context,
            timed_out=timed_out,
            fallback_used=fallback_used,
        )
        last_result = result
        if result.status == "success" or fallback_used:
            break

    final_result = last_result or _make_agent_error(
        agent_name=stage_key,
        error_type="unknown",
        message=f"{stage_key} did not return a result.",
        retry_count=max(0, attempts - 1),
    )
    completed_at = _timestamp()
    metadata.stage_metrics[stage_key] = _stage_metric(
        result=final_result,
        attempts=attempts,
        timeout_seconds=timeout_seconds,
        registry_key=registry_key,
        queued_at=queued_at,
        started_at=first_started_at,
        completed_at=completed_at,
        timed_out=timed_out,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )
    if (
        final_result.status not in {"success", "skipped", "not_applicable"}
        or timed_out
        or fallback_used
    ) and stage_key not in metadata.partial_failures:
        metadata.partial_failures.append(stage_key)
    return final_result


def _refresh_metadata_totals(metadata: PipelineMetadata) -> None:
    metadata.total_tokens = sum(metric.total_tokens for metric in metadata.stage_metrics.values())
    metadata.estimated_cost = round(sum(metric.estimated_cost for metric in metadata.stage_metrics.values()), 6)
    metadata.summed_stage_latency_ms = sum(metric.latency_ms for metric in metadata.stage_metrics.values())


def _critical_path_report(metadata: PipelineMetadata) -> dict[str, Any]:
    specialist_keys = {
        "financial_analysis",
        "tax_compliance",
        "ar_collections",
        "customer_concentration",
        "operations_transferability",
        "lease_contract",
        "market_macro",
    }
    specialist_metrics = [
        (stage_key, metric)
        for stage_key, metric in metadata.stage_metrics.items()
        if stage_key in specialist_keys and metric.status not in {"not_applicable", "skipped"}
    ]
    slowest_specialist = None
    if specialist_metrics:
        slowest_specialist = max(specialist_metrics, key=lambda item: item[1].latency_ms)

    report: dict[str, Any] = {
        "wall_clock_ms": metadata.total_latency_ms,
        "summed_stage_latency_ms": metadata.summed_stage_latency_ms,
        "parallelism_ratio": round(
            metadata.summed_stage_latency_ms / metadata.total_latency_ms,
            2,
        )
        if metadata.total_latency_ms
        else None,
    }
    if slowest_specialist is not None:
        report["slowest_specialist_stage"] = slowest_specialist[0]
        report["slowest_specialist_latency_ms"] = slowest_specialist[1].latency_ms
    if "synthesis_report" in metadata.stage_metrics:
        report["synthesis_latency_ms"] = metadata.stage_metrics["synthesis_report"].latency_ms
    return report


def _serialize_prompt_debug_artifact(
    analysis_id: str,
    metadata: PipelineMetadata,
    stage_results: dict[str, AgentResult[Any]],
    *,
    selected_stages: set[str],
    include_prompt_bodies: bool,
) -> dict[str, object]:
    stages: dict[str, object] = {}
    for stage_key in selected_stages:
        metric = metadata.stage_metrics.get(stage_key)
        result = stage_results.get(stage_key)
        diagnostics = result.diagnostics if result else {}
        if metric is None and not diagnostics:
            continue

        stage_payload: dict[str, object] = {
            "status": metric.status if metric else (result.status if result else "unknown"),
            "timedOut": metric.timed_out if metric else bool(diagnostics.get("timed_out", False)),
            "fallbackUsed": metric.fallback_used if metric else bool(diagnostics.get("fallback_used", False)),
            "model": (metric.model if metric else None) or diagnostics.get("model"),
            "promptChars": (metric.prompt_chars if metric else None) or diagnostics.get("prompt_chars"),
            "systemPromptChars": diagnostics.get("system_prompt_chars"),
            "userMessageChars": diagnostics.get("user_message_chars"),
            "schemaChars": (metric.schema_chars if metric else None) or diagnostics.get("schema_chars"),
            "responseChars": (metric.response_chars if metric else None) or diagnostics.get("response_chars"),
            "evidenceCount": (metric.evidence_count if metric else None) or diagnostics.get("evidence_count"),
            "promptSections": dict((metric.prompt_sections if metric else {}) or diagnostics.get("prompt_sections", {})),
            "contextTruncation": dict((metric.context_truncation if metric else {}) or diagnostics.get("context_truncation", {})),
            "attemptCount": diagnostics.get("attempt_count"),
            "requestStartedAt": (metric.request_started_at if metric else None) or diagnostics.get("request_started_at"),
            "requestFinishedAt": (metric.request_finished_at if metric else None) or diagnostics.get("request_finished_at"),
            "providerResponseReceived": (
                metric.provider_response_received if metric else bool(diagnostics.get("provider_response_received", False))
            ),
            "usageReceived": (
                metric.provider_usage_received if metric else bool(diagnostics.get("usage_received", False))
            ),
            "toolCallFound": metric.tool_call_found if metric else bool(diagnostics.get("tool_call_found", False)),
            "validationPassed": metric.validation_passed if metric else bool(diagnostics.get("validation_passed", False)),
            "tokenUsageKnown": (
                metric.token_usage_known if metric else bool(diagnostics.get("token_usage_known", False))
            ),
            "tokenUsageUnknownDueToTimeout": (
                metric.token_usage_unknown_due_to_timeout
                if metric
                else bool(diagnostics.get("token_usage_unknown_due_to_timeout", False))
            ),
        }
        if include_prompt_bodies:
            if diagnostics.get("system_prompt") is not None:
                stage_payload["systemPrompt"] = diagnostics.get("system_prompt")
            if diagnostics.get("user_message") is not None:
                stage_payload["userMessage"] = diagnostics.get("user_message")
        stages[stage_key] = stage_payload

    return {
        "analysisId": analysis_id,
        "generatedAt": metadata.completed_at or _timestamp(),
        "stages": stages,
    }


def _detected_doc_types(ingestion_output: IngestionOutput) -> set[str]:
    """Return the set of document type values present in the ingestion output."""
    return {doc.document_type.value for doc in ingestion_output.documents}


# Maps each specialist key to the document types that make it applicable.
# market_macro is always applicable (uses all docs for context).
_AGENT_REQUIRED_DOC_TYPES: dict[str, set[str]] = {
    "financial_analysis": {
        DocumentType.PROFIT_AND_LOSS.value,
        DocumentType.BALANCE_SHEET.value,
        DocumentType.CASH_FLOW_STATEMENT.value,
        "sde_summary",
    },
    "tax_compliance": {
        DocumentType.TAX_RETURN_1120S.value,
        DocumentType.TAX_RETURN_1040.value,
        DocumentType.TAX_RETURN_SCHEDULE_C.value,
        # P&L is also used by tax for reconciliation — include it so the agent
        # can flag the absence of actual tax returns.
        DocumentType.PROFIT_AND_LOSS.value,
    },
    "ar_collections": {
        DocumentType.AR_AGING_REPORT.value,
    },
    "customer_concentration": {
        DocumentType.CUSTOMER_LIST.value,
        DocumentType.CONTRACT.value,
    },
    "operations_transferability": {
        DocumentType.EMPLOYEE_ROSTER.value,
        DocumentType.INSURANCE_POLICY.value,
        DocumentType.EQUIPMENT_LIST.value,
    },
    "lease_contract": {
        DocumentType.LEASE_AGREEMENT.value,
        DocumentType.CONTRACT.value,
    },
    # market_macro is intentionally absent — it always runs.
}

_NOT_APPLICABLE_MESSAGES: dict[str, str] = {
    "financial_analysis": "No financial documents (P&L, balance sheet, cash flow) were uploaded; financial analysis is not applicable.",
    "tax_compliance": "No tax return or financial documents were uploaded; tax compliance analysis is not applicable.",
    "ar_collections": "No AR aging report was uploaded; AR collections analysis is not applicable.",
    "customer_concentration": "No customer list or contracts were uploaded; customer concentration analysis is not applicable.",
    "operations_transferability": "No operational documents (employee roster, insurance, equipment list) were uploaded; operations analysis is not applicable.",
    "lease_contract": "No lease agreement or contracts were uploaded; lease & contract analysis is not applicable.",
}


def _make_not_applicable(agent_key: str) -> AgentResult[Any]:
    return AgentResult(
        status="not_applicable",
        error=AgentErrorPayload(
            agent_name=agent_key,
            error_type="not_applicable",
            message=_NOT_APPLICABLE_MESSAGES.get(agent_key, f"{agent_key} is not applicable to the uploaded documents."),
            timestamp=_timestamp(),
            retry_count=0,
        ),
    )


def _specialist_specs(
    ingestion_output: IngestionOutput,
    pipeline_input: PipelineInput,
) -> list[tuple[str, str, Any, tuple[Any, ...]]]:
    """Return all specialist specs; routing is handled in _tracked_specialist via applicable_keys."""
    return [
        ("financial_analysis", "financial-analysis", run_financial_analysis, (ingestion_output,)),
        ("tax_compliance", "tax-compliance", run_tax_compliance, (ingestion_output,)),
        ("ar_collections", "ar-collections", run_ar_collections, (ingestion_output,)),
        ("customer_concentration", "customer-concentration", run_customer_concentration, (ingestion_output,)),
        ("operations_transferability", "operations-transferability", run_ops_transferability, (ingestion_output,)),
        ("lease_contract", "lease-contract", run_lease_contract, (ingestion_output,)),
        (
            "market_macro",
            "market-macro",
            run_market_macro,
            (ingestion_output, pipeline_input.business_type, pipeline_input.location),
        ),
    ]


def _applicable_specialist_keys(detected_doc_types: set[str]) -> set[str]:
    """Return the set of specialist keys that have at least one relevant document present."""
    applicable: set[str] = {"market_macro"}  # always applicable
    for agent_key, required_types in _AGENT_REQUIRED_DOC_TYPES.items():
        if required_types & detected_doc_types:
            applicable.add(agent_key)
    return applicable


async def run_pipeline(
    payload: Dict[str, Any],
    progress_callback: Callable[..., None] | None = None,
) -> Dict[str, Any]:
    settings = get_settings()
    pipeline_started = time.perf_counter()
    pipeline_input = PipelineInput(
        documents=payload.get("documents", []),
        asking_price=payload.get("asking_price", payload.get("askingPrice")),
        business_type=payload.get("business_type", payload.get("businessType")),
        location=payload.get("location"),
        analysis_id=payload.get("analysis_id", payload.get("analysisId")),
        clarifications=payload.get("clarifications", []),
        report_depth=payload.get("report_depth", payload.get("reportDepth")),
    )
    state = PipelineState(
        input=pipeline_input,
        metadata=PipelineMetadata(
            started_at=_timestamp(),
            rollout_flags={
                "pipeline_enabled": settings.pipeline_enabled,
                "analysis_jobs_enabled": settings.analysis_jobs_enabled,
                "allow_partial_failures": settings.pipeline_allow_partial_failures,
                "enable_synthesis": settings.pipeline_enable_synthesis,
                "retry_attempts": settings.pipeline_retry_attempts,
                "stage_timeout_seconds": settings.pipeline_stage_timeout_seconds,
                "prompt_debug_artifacts_enabled": settings.pipeline_prompt_debug_artifacts_enabled,
                "prompt_debug_include_bodies": getattr(settings, "pipeline_prompt_debug_include_bodies", False),
                "prompt_debug_stages": sorted(_selected_prompt_debug_stages(settings)),
            },
        ),
    )
    prompt_debug_stages = _selected_prompt_debug_stages(settings)
    running_agents: set[str] = set()
    completed_agents: list[str] = []
    fallback_mode_active = False
    agent_statuses: dict[str, str] = {"ingestion": "queued"}
    clarification_evidence = build_clarification_evidence(
        pipeline_input.clarifications,
        analysis_id=pipeline_input.analysis_id,
    )

    logger.info(
        "Pipeline started: analysis_id=%s docs=%d",
        pipeline_input.analysis_id,
        len(pipeline_input.documents),
    )

    _emit_progress(
        progress_callback,
        "ingestion",
        "Ingesting uploaded documents.",
        0.12,
        completed_agents=list(completed_agents),
        running_agents=["ingestion"],
        agent_statuses={"ingestion": "running"},
        fallback_mode_active=fallback_mode_active,
    )
    agent_statuses["ingestion"] = "running"
    state.ingestion = await _execute_stage(
        stage_key="ingestion",
        registry_key="document-ingestion",
        func=run_document_ingestion,
        args=(pipeline_input.documents, pipeline_input.analysis_id),
        metadata=state.metadata,
        timeout_seconds=_resolve_stage_timeout("document-ingestion", settings.pipeline_stage_timeout_seconds),
        retry_attempts=settings.pipeline_retry_attempts,
        queued_at=state.metadata.started_at,
        capture_prompt_bodies=False,
    )
    agent_statuses["ingestion"] = state.ingestion.status
    if state.ingestion.status != "success" or not state.ingestion.data:
        logger.warning("Pipeline aborted at ingestion: analysis_id=%s", pipeline_input.analysis_id)
        abort = _make_abort_error("Pipeline aborted: document ingestion failed.")
        state.financial_analysis = abort
        state.tax_compliance = abort
        state.ar_collections = abort
        state.customer_concentration = abort
        state.operations_transferability = abort
        state.lease_contract = abort
        state.market_macro = abort
        state.lending_affordability = abort
        state.synthesis_report = abort
        state.metadata.completed_at = _timestamp()
        _refresh_metadata_totals(state.metadata)
        state.metadata.total_latency_ms = int((time.perf_counter() - pipeline_started) * 1000)
        state.metadata.critical_path = _critical_path_report(state.metadata)
        return assemble_summary_report(
            ingestion_output=None,
            agent_results={},
            scorecard=state.scorecard,
            synthesis_result=state.synthesis_report,
            metadata=state.metadata,
            analysis_id=pipeline_input.analysis_id,
            clarification_evidence=clarification_evidence,
            include_deep_review=(pipeline_input.report_depth == "deep"),
            deterministic_fallback=None,
        ).model_dump(mode="json", by_alias=True)

    ingestion_output = state.ingestion.data
    _emit_progress(
        progress_callback,
        "ingestion_complete",
        "Document ingestion complete.",
        0.28,
        completed_agents=list(completed_agents),
        running_agents=list(running_agents),
        agent_statuses=dict(agent_statuses),
        fallback_mode_active=fallback_mode_active,
    )
    if pipeline_input.analysis_id and pipeline_input.clarifications:
        store_clarification_answers(pipeline_input.analysis_id, pipeline_input.clarifications)

    # ── Smart agent routing ──────────────────────────────────────────────────────
    # Determine which specialists are relevant given the uploaded document types.
    detected_doc_types = _detected_doc_types(ingestion_output)
    applicable_keys = _applicable_specialist_keys(detected_doc_types)
    logger.info(
        "Detected doc types: %s | Applicable agents: %s | analysis_id=%s",
        sorted(detected_doc_types),
        sorted(applicable_keys),
        pipeline_input.analysis_id,
    )

    # ── Specialist agents (parallel) ────────────────────────────────────────────
    # Track each completion to emit per-agent progress with a shared list.
    _total_applicable = len(applicable_keys)
    specialist_specs = _specialist_specs(ingestion_output, pipeline_input)
    for stage_key, *_ in specialist_specs:
        agent_statuses[stage_key] = "queued" if stage_key in applicable_keys else "not_applicable"

    async def _tracked_specialist(
        stage_key: str,
        registry_key: str,
        func: Any,
        args: tuple[Any, ...],
    ) -> AgentResult[Any]:
        nonlocal fallback_mode_active
        # Skip agents not applicable to the uploaded documents.
        if stage_key not in applicable_keys:
            result = _make_not_applicable(stage_key)
            state.metadata.stage_metrics[stage_key] = _stage_metric(
                result=result,
                attempts=0,
                timeout_seconds=_resolve_stage_timeout(registry_key, settings.pipeline_stage_timeout_seconds),
                registry_key=registry_key,
                queued_at=_timestamp(),
                completed_at=_timestamp(),
            )
            agent_statuses[stage_key] = "not_applicable"
            logger.info(
                "Specialist skipped (not applicable): %s analysis_id=%s",
                stage_key,
                pipeline_input.analysis_id,
            )
            return result

        queued_at = _timestamp()
        running_agents.add(stage_key)
        agent_statuses[stage_key] = "running"
        _emit_progress(
            progress_callback,
            "specialists_started",
            "Running specialist analysis agents in parallel.",
            0.42,
            list(completed_agents),
            running_agents=sorted(running_agents),
            queued_agents=sorted(agent for agent in applicable_keys if agent not in running_agents and agent not in completed_agents),
            agent_statuses=dict(agent_statuses),
            fallback_mode_active=fallback_mode_active,
        )
        result = await _execute_stage(
            stage_key=stage_key,
            registry_key=registry_key,
            func=func,
            args=args,
            metadata=state.metadata,
            timeout_seconds=_resolve_stage_timeout(registry_key, settings.pipeline_stage_timeout_seconds),
            retry_attempts=settings.pipeline_retry_attempts,
            queued_at=queued_at,
            capture_prompt_bodies=bool(
                getattr(settings, "pipeline_prompt_debug_include_bodies", False)
                and stage_key in prompt_debug_stages
            ),
        )
        running_agents.discard(stage_key)
        completed_agents.append(stage_key)
        agent_statuses[stage_key] = result.status
        if state.metadata.stage_metrics.get(stage_key) and state.metadata.stage_metrics[stage_key].fallback_used:
            fallback_mode_active = True
        label = stage_key.replace("_", " ").title()
        prog = 0.28 + 0.50 * len(completed_agents) / max(_total_applicable, 1)
        logger.info(
            "Specialist complete: %s (%d/%d) status=%s analysis_id=%s",
            stage_key,
            len(completed_agents),
            _total_applicable,
            result.status,
            pipeline_input.analysis_id,
        )
        _emit_progress(
            progress_callback,
            "n_of_m_specialists_completed",
            f"{label} complete.",
            round(prog, 2),
            list(completed_agents),
            running_agents=sorted(running_agents),
            queued_agents=sorted(agent for agent in applicable_keys if agent not in running_agents and agent not in completed_agents),
            agent_statuses=dict(agent_statuses),
            fallback_mode_active=fallback_mode_active,
        )
        return result

    specialist_results = await asyncio.gather(
        *[
            _tracked_specialist(stage_key, registry_key, func, args)
            for stage_key, registry_key, func, args in specialist_specs
        ]
    )

    (
        state.financial_analysis,
        state.tax_compliance,
        state.ar_collections,
        state.customer_concentration,
        state.operations_transferability,
        state.lease_contract,
        state.market_macro,
    ) = specialist_results

    _emit_progress(
        progress_callback,
        "specialist_analysis_complete",
        "Specialist analysis completed.",
        0.78,
        list(completed_agents),
        running_agents=sorted(running_agents),
        queued_agents=[],
        agent_statuses=dict(agent_statuses),
        fallback_mode_active=fallback_mode_active,
    )
    if state.financial_analysis.status == "success" and state.financial_analysis.data:
        agent_statuses["lending_affordability"] = "running"
        _emit_progress(
            progress_callback,
            "lending",
            "Computing lending affordability.",
            0.86,
            list(completed_agents),
            running_agents=["lending_affordability"],
            agent_statuses=dict(agent_statuses),
            fallback_mode_active=fallback_mode_active,
        )
        state.lending_affordability = await _execute_stage(
            stage_key="lending_affordability",
            registry_key="lending-affordability",
            func=run_lending_affordability,
            args=(ingestion_output, state.financial_analysis.data, pipeline_input.asking_price),
            metadata=state.metadata,
            timeout_seconds=_resolve_stage_timeout("lending-affordability", settings.pipeline_stage_timeout_seconds),
            retry_attempts=settings.pipeline_retry_attempts,
            queued_at=_timestamp(),
            capture_prompt_bodies=bool(
                getattr(settings, "pipeline_prompt_debug_include_bodies", False)
                and "lending_affordability" in prompt_debug_stages
            ),
        )
        agent_statuses["lending_affordability"] = state.lending_affordability.status
    else:
        state.lending_affordability = _make_agent_error(
            agent_name="lending_affordability",
            error_type="dependency",
            message="Cannot assess lending affordability because financial analysis did not complete successfully.",
            retry_count=0,
            status="skipped",
        )
        state.metadata.stage_metrics["lending_affordability"] = _stage_metric(
            result=state.lending_affordability,
            attempts=1,
            timeout_seconds=_resolve_stage_timeout("lending-affordability", settings.pipeline_stage_timeout_seconds),
            registry_key="lending-affordability",
            queued_at=_timestamp(),
            completed_at=_timestamp(),
        )
        agent_statuses["lending_affordability"] = state.lending_affordability.status
        if "lending_affordability" not in state.metadata.partial_failures:
            state.metadata.partial_failures.append("lending_affordability")

    specialist_results_map = {
        "financial_analysis": state.financial_analysis,
        "tax_compliance": state.tax_compliance,
        "ar_collections": state.ar_collections,
        "customer_concentration": state.customer_concentration,
        "operations_transferability": state.operations_transferability,
        "lease_contract": state.lease_contract,
        "market_macro": state.market_macro,
        "lending_affordability": state.lending_affordability,
    }

    # ── Determine if any applicable specialist succeeded ─────────────────────────
    applicable_successes = [
        k for k, r in specialist_results_map.items()
        if k in applicable_keys and r.status == "success"
    ]
    all_applicable_failed = len(applicable_successes) == 0

    _emit_progress(
        progress_callback,
        "scoring",
        "Building the deterministic scorecard.",
        0.92,
        list(completed_agents),
        agent_statuses=dict(agent_statuses),
        fallback_mode_active=fallback_mode_active,
    )
    state.scorecard = compute_pipeline_scorecard(ingestion_output, specialist_results_map)

    # ── Save a partial report now (before synthesis) so polling clients can ──
    # render whatever is already available while synthesis runs.
    if pipeline_input.analysis_id:
        try:
            from app.services.analysis_repository import get_analysis_artifact_repository
            _partial = assemble_summary_report(
                ingestion_output=ingestion_output,
                agent_results=specialist_results_map,
                scorecard=state.scorecard,
                synthesis_result=None,
                metadata=state.metadata,
                analysis_id=pipeline_input.analysis_id,
                clarification_evidence=clarification_evidence,
                include_deep_review=False,
                deterministic_fallback=None,
            ).model_dump(mode="json", by_alias=True)
            get_analysis_artifact_repository().save_analysis_report(pipeline_input.analysis_id, _partial)
            logger.info("Partial report saved: analysis_id=%s", pipeline_input.analysis_id)
            from app.services.analysis_jobs import broadcast_job_snapshot

            broadcast_job_snapshot(pipeline_input.analysis_id)
        except Exception as _e:
            logger.warning("Could not save partial report: %s", _e)

    # ── Synthesis guard: skip synthesis when no applicable agent succeeded ───────
    if all_applicable_failed:
        state.synthesis_report = _make_agent_error(
            agent_name="synthesis_report",
            error_type="skipped",
            message="Synthesis skipped: no applicable specialist agents completed successfully.",
            retry_count=0,
            status="skipped",
        )
        state.metadata.stage_metrics["synthesis_report"] = _stage_metric(
            result=state.synthesis_report,
            attempts=0,
            timeout_seconds=_resolve_stage_timeout("synthesis-report", settings.pipeline_stage_timeout_seconds),
            registry_key="synthesis-report",
            queued_at=_timestamp(),
            completed_at=_timestamp(),
        )
        agent_statuses["synthesis_report"] = state.synthesis_report.status
        if "synthesis_report" not in state.metadata.partial_failures:
            state.metadata.partial_failures.append("synthesis_report")
    elif not settings.pipeline_allow_partial_failures and state.metadata.partial_failures:
        state.synthesis_report = _make_agent_error(
            agent_name="synthesis_report",
            error_type="rollout_guard",
            message="Synthesis skipped because rollout policy blocks partial specialist failures.",
            retry_count=0,
            status="skipped",
        )
        state.metadata.stage_metrics["synthesis_report"] = _stage_metric(
            result=state.synthesis_report,
            attempts=1,
            timeout_seconds=_resolve_stage_timeout("synthesis-report", settings.pipeline_stage_timeout_seconds),
            registry_key="synthesis-report",
            queued_at=_timestamp(),
            completed_at=_timestamp(),
        )
        agent_statuses["synthesis_report"] = state.synthesis_report.status
        if "synthesis_report" not in state.metadata.partial_failures:
            state.metadata.partial_failures.append("synthesis_report")
    elif not settings.pipeline_enable_synthesis:
        state.synthesis_report = _make_agent_error(
            agent_name="synthesis_report",
            error_type="rollout_flag",
            message="Narrative synthesis skipped by rollout flag.",
            retry_count=0,
            status="skipped",
        )
        state.metadata.stage_metrics["synthesis_report"] = _stage_metric(
            result=state.synthesis_report,
            attempts=1,
            timeout_seconds=_resolve_stage_timeout("synthesis-report", settings.pipeline_stage_timeout_seconds),
            registry_key="synthesis-report",
            queued_at=_timestamp(),
            completed_at=_timestamp(),
        )
        agent_statuses["synthesis_report"] = state.synthesis_report.status
        if "synthesis_report" not in state.metadata.partial_failures:
            state.metadata.partial_failures.append("synthesis_report")
    else:
        agent_statuses["synthesis_report"] = "running"
        _emit_progress(
            progress_callback,
            "synthesis_started",
            "Assembling the final report.",
            0.97,
            list(completed_agents),
            running_agents=["synthesis_report"],
            agent_statuses=dict(agent_statuses),
            fallback_mode_active=fallback_mode_active,
        )
        state.synthesis_report = await _execute_stage(
            stage_key="synthesis_report",
            registry_key="synthesis-report",
            func=run_synthesis_report,
            args=(state.scorecard, specialist_results_map),
            metadata=state.metadata,
            timeout_seconds=_resolve_stage_timeout("synthesis-report", settings.pipeline_stage_timeout_seconds),
            retry_attempts=settings.pipeline_retry_attempts,
            queued_at=_timestamp(),
            capture_prompt_bodies=bool(
                getattr(settings, "pipeline_prompt_debug_include_bodies", False)
                and "synthesis_report" in prompt_debug_stages
            ),
        )
        agent_statuses["synthesis_report"] = state.synthesis_report.status
        if state.metadata.stage_metrics.get("synthesis_report") and state.metadata.stage_metrics["synthesis_report"].fallback_used:
            fallback_mode_active = True

    state.metadata.completed_at = _timestamp()
    _refresh_metadata_totals(state.metadata)
    state.metadata.total_latency_ms = int((time.perf_counter() - pipeline_started) * 1000)
    state.metadata.critical_path = _critical_path_report(state.metadata)
    if pipeline_input.analysis_id and settings.pipeline_prompt_debug_artifacts_enabled:
        try:
            repository = get_analysis_artifact_repository()
            prompt_debug_stage_results = {
                "ingestion": state.ingestion,
                "financial_analysis": state.financial_analysis,
                "tax_compliance": state.tax_compliance,
                "ar_collections": state.ar_collections,
                "customer_concentration": state.customer_concentration,
                "operations_transferability": state.operations_transferability,
                "lease_contract": state.lease_contract,
                "market_macro": state.market_macro,
                "lending_affordability": state.lending_affordability,
                "synthesis_report": state.synthesis_report,
            }
            ref = repository.save_prompt_debug_artifact(
                pipeline_input.analysis_id,
                _serialize_prompt_debug_artifact(
                    pipeline_input.analysis_id,
                    state.metadata,
                    prompt_debug_stage_results,
                    selected_stages=prompt_debug_stages,
                    include_prompt_bodies=bool(getattr(settings, "pipeline_prompt_debug_include_bodies", False)),
                ),
            )
            state.metadata.debug_artifacts["prompt_debug"] = ref
        except Exception as debug_exc:
            logger.warning("Could not save prompt debug artifact: %s", debug_exc)

    if state.metadata.partial_failures:
        _emit_progress(
            progress_callback,
            "completed_with_warnings",
            "Analysis completed with partial failures.",
            1.0,
            list(completed_agents),
            running_agents=[],
            queued_agents=[],
            agent_statuses=dict(agent_statuses),
            fallback_mode_active=fallback_mode_active,
        )
    else:
        _emit_progress(
            progress_callback,
            "completed",
            "Analysis complete.",
            1.0,
            list(completed_agents),
            running_agents=[],
            queued_agents=[],
            agent_statuses=dict(agent_statuses),
            fallback_mode_active=fallback_mode_active,
        )

    total_ms = int((time.perf_counter() - pipeline_started) * 1000)
    logger.info(
        "Pipeline complete: analysis_id=%s elapsed_ms=%d partial_failures=%d applicable_successes=%d",
        pipeline_input.analysis_id,
        total_ms,
        len(state.metadata.partial_failures),
        len(applicable_successes),
    )

    return assemble_summary_report(
        ingestion_output=ingestion_output,
        agent_results=specialist_results_map,
        scorecard=state.scorecard,
        synthesis_result=state.synthesis_report,
        metadata=state.metadata,
        analysis_id=pipeline_input.analysis_id,
        clarification_evidence=clarification_evidence,
        include_deep_review=(pipeline_input.report_depth == "deep"),
        deterministic_fallback=None,
    ).model_dump(mode="json", by_alias=True)
