from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from app.agents.registry import AGENT_REGISTRY
from app.agents.schemas import AgentErrorPayload, AgentResult, PipelineInput, PipelineMetadata, PipelineState
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

MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}


def _make_abort_error(message: str) -> AgentResult[Any]:
    return AgentResult(
        status="error",
        error=AgentErrorPayload(
            agent_name="pipeline",
            error_type="unknown",
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            retry_count=0,
        ),
    )


def _result_tokens(result: AgentResult[Any] | None) -> int:
    if not result or result.status != "success":
        return 0
    return result.token_usage.input + result.token_usage.output


def _estimate_result_cost(result: AgentResult[Any] | None, registry_key: str) -> float:
    if not result or result.status != "success":
        return 0.0
    model_name = AGENT_REGISTRY[registry_key].model
    pricing = MODEL_PRICING.get(model_name)
    if not pricing:
        return 0.0
    return (
        (result.token_usage.input / 1_000_000) * pricing["input"]
        + (result.token_usage.output / 1_000_000) * pricing["output"]
    )


async def _run_in_executor(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


async def run_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    pipeline_input = PipelineInput(
        documents=payload.get("documents", []),
        asking_price=payload.get("asking_price", payload.get("askingPrice")),
        business_type=payload.get("business_type", payload.get("businessType")),
        location=payload.get("location"),
    )
    state = PipelineState(
        input=pipeline_input,
        metadata=PipelineMetadata(started_at=datetime.now(timezone.utc).isoformat()),
    )

    state.ingestion = await _run_in_executor(run_document_ingestion, pipeline_input.documents)
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
        state.metadata.completed_at = datetime.now(timezone.utc).isoformat()
        return state.model_dump(mode="json")

    ingestion_output = state.ingestion.data
    phase2 = await asyncio.gather(
        _run_in_executor(run_financial_analysis, ingestion_output),
        _run_in_executor(run_tax_compliance, ingestion_output),
        _run_in_executor(run_ar_collections, ingestion_output),
        _run_in_executor(run_customer_concentration, ingestion_output),
        _run_in_executor(run_ops_transferability, ingestion_output),
        _run_in_executor(run_lease_contract, ingestion_output),
        _run_in_executor(run_market_macro, ingestion_output, pipeline_input.business_type, pipeline_input.location),
        return_exceptions=True,
    )

    results: list[AgentResult[Any]] = []
    for item, name in zip(
        phase2,
        [
            "financial-analysis",
            "tax-compliance",
            "ar-collections",
            "customer-concentration",
            "operations-transferability",
            "lease-contract",
            "market-macro",
        ],
    ):
        if isinstance(item, Exception):
            results.append(_make_abort_error(f"{name} failed with exception: {item}"))
        else:
            results.append(item)

    (
        state.financial_analysis,
        state.tax_compliance,
        state.ar_collections,
        state.customer_concentration,
        state.operations_transferability,
        state.lease_contract,
        state.market_macro,
    ) = results

    if state.financial_analysis.status == "success" and state.financial_analysis.data:
        state.lending_affordability = await _run_in_executor(
            run_lending_affordability,
            ingestion_output,
            state.financial_analysis.data,
            pipeline_input.asking_price,
        )
    else:
        state.lending_affordability = _make_abort_error(
            "Cannot assess lending affordability because financial analysis did not complete successfully."
        )

    state.synthesis_report = await _run_in_executor(
        run_synthesis_report,
        {
            "financial_analysis": state.financial_analysis,
            "tax_compliance": state.tax_compliance,
            "ar_collections": state.ar_collections,
            "customer_concentration": state.customer_concentration,
            "operations_transferability": state.operations_transferability,
            "lease_contract": state.lease_contract,
            "market_macro": state.market_macro,
            "lending_affordability": state.lending_affordability,
        },
    )

    state.metadata.completed_at = datetime.now(timezone.utc).isoformat()
    state.metadata.total_tokens = sum(
        _result_tokens(result)
        for result in [
            state.ingestion,
            state.financial_analysis,
            state.tax_compliance,
            state.ar_collections,
            state.customer_concentration,
            state.operations_transferability,
            state.lease_contract,
            state.market_macro,
            state.lending_affordability,
            state.synthesis_report,
        ]
    )
    state.metadata.estimated_cost = sum(
        [
            _estimate_result_cost(state.ingestion, "document-ingestion"),
            _estimate_result_cost(state.financial_analysis, "financial-analysis"),
            _estimate_result_cost(state.tax_compliance, "tax-compliance"),
            _estimate_result_cost(state.ar_collections, "ar-collections"),
            _estimate_result_cost(state.customer_concentration, "customer-concentration"),
            _estimate_result_cost(state.operations_transferability, "operations-transferability"),
            _estimate_result_cost(state.lease_contract, "lease-contract"),
            _estimate_result_cost(state.market_macro, "market-macro"),
            _estimate_result_cost(state.lending_affordability, "lending-affordability"),
            _estimate_result_cost(state.synthesis_report, "synthesis-report"),
        ]
    )
    return state.model_dump(mode="json")
