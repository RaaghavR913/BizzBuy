from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from app.agents.registry import AGENT_REGISTRY
from app.agents.schemas import (
    AgentErrorPayload,
    AgentResult,
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
from app.services.clarification_service import build_clarification_evidence, store_clarification_answers
from app.services.report_assembler import assemble_summary_report
from app.services.scoring_engine import compute_pipeline_scorecard

MODEL_PRICING = {
    "claude-sonnet-4-6": {"type": "per_token", "input": 3.00, "output": 15.00},
    "claude-opus-4-6":   {"type": "per_token", "input": 5.00, "output": 25.00},
    "mistral-ocr-2512":  {"type": "per_page",  "rate": 0.002},
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


def _emit_progress(
    progress_callback: Callable[[str, str, float], None] | None,
    stage: str,
    message: str,
    progress: float,
) -> None:
    if progress_callback is not None:
        progress_callback(stage, message, progress)


def _stage_metric(
    *,
    result: AgentResult[Any],
    attempts: int,
    timeout_seconds: float,
    registry_key: str,
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
    )


async def _execute_stage(
    *,
    stage_key: str,
    registry_key: str,
    func,
    args: tuple[Any, ...],
    metadata: PipelineMetadata,
    timeout_seconds: float,
    retry_attempts: int,
) -> AgentResult[Any]:
    attempts = 0
    last_result: AgentResult[Any] | None = None

    while attempts <= retry_attempts:
        attempts += 1
        attempt_started = time.perf_counter()
        try:
            result = await asyncio.wait_for(_run_in_executor(func, *args), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            result = _make_agent_error(
                agent_name=stage_key,
                error_type="timeout",
                message=f"{stage_key} timed out after {timeout_seconds:.1f}s.",
                retry_count=attempts - 1,
                latency_ms=int((time.perf_counter() - attempt_started) * 1000),
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

        last_result = result
        if result.status == "success":
            break

    final_result = last_result or _make_agent_error(
        agent_name=stage_key,
        error_type="unknown",
        message=f"{stage_key} did not return a result.",
        retry_count=max(0, attempts - 1),
    )
    metadata.stage_metrics[stage_key] = _stage_metric(
        result=final_result,
        attempts=attempts,
        timeout_seconds=timeout_seconds,
        registry_key=registry_key,
    )
    if final_result.status != "success" and stage_key not in metadata.partial_failures:
        metadata.partial_failures.append(stage_key)
    return final_result


def _refresh_metadata_totals(metadata: PipelineMetadata) -> None:
    metadata.total_tokens = sum(metric.total_tokens for metric in metadata.stage_metrics.values())
    metadata.estimated_cost = round(sum(metric.estimated_cost for metric in metadata.stage_metrics.values()), 6)
    metadata.total_latency_ms = sum(metric.latency_ms for metric in metadata.stage_metrics.values())


def _specialist_specs(
    ingestion_output: Any,
    pipeline_input: PipelineInput,
) -> list[tuple[str, str, Any, tuple[Any, ...]]]:
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


async def run_pipeline(
    payload: Dict[str, Any],
    progress_callback: Callable[[str, str, float], None] | None = None,
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
            },
        ),
    )
    clarification_evidence = build_clarification_evidence(
        pipeline_input.clarifications,
        analysis_id=pipeline_input.analysis_id,
    )

    _emit_progress(progress_callback, "ingestion", "Ingesting uploaded documents.", 0.12)
    state.ingestion = await _execute_stage(
        stage_key="ingestion",
        registry_key="document-ingestion",
        func=run_document_ingestion,
        args=(pipeline_input.documents,),
        metadata=state.metadata,
        timeout_seconds=settings.pipeline_stage_timeout_seconds,
        retry_attempts=settings.pipeline_retry_attempts,
    )
    if state.ingestion.status != "success" or not state.ingestion.data:
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
        return assemble_summary_report(
            ingestion_output=None,
            agent_results={},
            scorecard=state.scorecard,
            synthesis_result=state.synthesis_report,
            metadata=state.metadata,
            analysis_id=pipeline_input.analysis_id,
            clarification_evidence=clarification_evidence,
            include_deep_review=(pipeline_input.report_depth == "deep"),
        ).model_dump(mode="json", by_alias=True)

    ingestion_output = state.ingestion.data
    _emit_progress(progress_callback, "ingestion_complete", "Document ingestion complete.", 0.28)
    if pipeline_input.analysis_id and pipeline_input.clarifications:
        store_clarification_answers(pipeline_input.analysis_id, pipeline_input.clarifications)

    _emit_progress(progress_callback, "specialist_analysis", "Running specialist analysis agents.", 0.42)
    specialist_specs = _specialist_specs(ingestion_output, pipeline_input)
    specialist_results = await asyncio.gather(
        *[
            _execute_stage(
                stage_key=stage_key,
                registry_key=registry_key,
                func=func,
                args=args,
                metadata=state.metadata,
                timeout_seconds=settings.pipeline_stage_timeout_seconds,
                retry_attempts=settings.pipeline_retry_attempts,
            )
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

    _emit_progress(progress_callback, "specialist_analysis_complete", "Specialist analysis completed.", 0.78)
    if state.financial_analysis.status == "success" and state.financial_analysis.data:
        _emit_progress(progress_callback, "lending", "Computing lending affordability.", 0.86)
        state.lending_affordability = await _execute_stage(
            stage_key="lending_affordability",
            registry_key="lending-affordability",
            func=run_lending_affordability,
            args=(ingestion_output, state.financial_analysis.data, pipeline_input.asking_price),
            metadata=state.metadata,
            timeout_seconds=settings.pipeline_stage_timeout_seconds,
            retry_attempts=settings.pipeline_retry_attempts,
        )
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
            timeout_seconds=settings.pipeline_stage_timeout_seconds,
            registry_key="lending-affordability",
        )
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

    _emit_progress(progress_callback, "scoring", "Building the deterministic scorecard.", 0.92)
    state.scorecard = compute_pipeline_scorecard(ingestion_output, specialist_results_map)

    if not settings.pipeline_allow_partial_failures and state.metadata.partial_failures:
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
            timeout_seconds=settings.pipeline_stage_timeout_seconds,
            registry_key="synthesis-report",
        )
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
            timeout_seconds=settings.pipeline_stage_timeout_seconds,
            registry_key="synthesis-report",
        )
        if "synthesis_report" not in state.metadata.partial_failures:
            state.metadata.partial_failures.append("synthesis_report")
    else:
        _emit_progress(progress_callback, "synthesis", "Assembling the final report.", 0.97)
        state.synthesis_report = await _execute_stage(
            stage_key="synthesis_report",
            registry_key="synthesis-report",
            func=run_synthesis_report,
            args=(state.scorecard, specialist_results_map),
            metadata=state.metadata,
            timeout_seconds=settings.pipeline_stage_timeout_seconds,
            retry_attempts=settings.pipeline_retry_attempts,
        )

    state.metadata.completed_at = _timestamp()
    _refresh_metadata_totals(state.metadata)
    state.metadata.total_latency_ms = max(
        state.metadata.total_latency_ms,
        int((time.perf_counter() - pipeline_started) * 1000),
    )

    if state.metadata.partial_failures:
        _emit_progress(progress_callback, "completed_with_warnings", "Analysis completed with partial failures.", 1.0)
    else:
        _emit_progress(progress_callback, "completed", "Analysis complete.", 1.0)

    return assemble_summary_report(
        ingestion_output=ingestion_output,
        agent_results=specialist_results_map,
        scorecard=state.scorecard,
        synthesis_result=state.synthesis_report,
        metadata=state.metadata,
        analysis_id=pipeline_input.analysis_id,
        clarification_evidence=clarification_evidence,
        include_deep_review=(pipeline_input.report_depth == "deep"),
    ).model_dump(mode="json", by_alias=True)
