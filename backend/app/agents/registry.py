from __future__ import annotations

from typing import Dict, List, Optional

from app.agents.schemas import (
    ARCollectionsOutput,
    CustomerConcentrationOutput,
    IngestionOutput,
    FinancialAnalysisOutput,
    LeaseContractOutput,
    LendingAffordabilityOutput,
    MarketMacroOutput,
    OpsTransferabilityOutput,
    TaxComplianceOutput,
    SynthesisReportOutput,
)


class PipelinePhase(str):
    INGESTION = "ingestion"
    PARALLEL_ANALYSIS = "parallel_analysis"
    LENDING = "lending"
    SYNTHESIS = "synthesis"


class AgentConfig:
    def __init__(
        self,
        name: str,
        prompt_key: str,
        schema_class,
        model: str,
        phase: PipelinePhase,
        depends_on: List[str],
        max_tokens: Optional[int] = None,
    ):
        self.name = name
        self.prompt_key = prompt_key
        self.schema_class = schema_class
        self.model = model
        self.phase = phase
        self.depends_on = depends_on
        self.max_tokens = max_tokens or 4096


AGENT_REGISTRY: Dict[str, AgentConfig] = {
    'document-ingestion': AgentConfig(
        name='document-ingestion',
        prompt_key='DOCUMENT_INGESTION_PROMPT',
        schema_class=IngestionOutput,
        model='claude-sonnet-4-6',
        phase=PipelinePhase.INGESTION,
        depends_on=[],
        max_tokens=8192,
    ),
    'financial-analysis': AgentConfig(
        name='financial-analysis',
        prompt_key='FINANCIAL_ANALYSIS_PROMPT',
        schema_class=FinancialAnalysisOutput,
        model='claude-sonnet-4-6',
        phase=PipelinePhase.PARALLEL_ANALYSIS,
        depends_on=['document-ingestion'],
        max_tokens=8192,
    ),
    'tax-compliance': AgentConfig(
        name='tax-compliance',
        prompt_key='TAX_COMPLIANCE_PROMPT',
        schema_class=TaxComplianceOutput,
        model='claude-sonnet-4-6',
        phase=PipelinePhase.PARALLEL_ANALYSIS,
        depends_on=['document-ingestion'],
        max_tokens=4096,
    ),
    'ar-collections': AgentConfig(
        name='ar-collections',
        prompt_key='AR_COLLECTIONS_PROMPT',
        schema_class=ARCollectionsOutput,
        model='claude-sonnet-4-6',
        phase=PipelinePhase.PARALLEL_ANALYSIS,
        depends_on=['document-ingestion'],
        max_tokens=4096,
    ),
    'customer-concentration': AgentConfig(
        name='customer-concentration',
        prompt_key='CUSTOMER_CONCENTRATION_PROMPT',
        schema_class=CustomerConcentrationOutput,
        model='claude-sonnet-4-6',
        phase=PipelinePhase.PARALLEL_ANALYSIS,
        depends_on=['document-ingestion'],
        max_tokens=4096,
    ),
    'operations-transferability': AgentConfig(
        name='operations-transferability',
        prompt_key='OPERATIONS_TRANSFERABILITY_PROMPT',
        schema_class=OpsTransferabilityOutput,
        model='claude-sonnet-4-6',
        phase=PipelinePhase.PARALLEL_ANALYSIS,
        depends_on=['document-ingestion'],
        max_tokens=4096,
    ),
    'lease-contract': AgentConfig(
        name='lease-contract',
        prompt_key='LEASE_CONTRACT_PROMPT',
        schema_class=LeaseContractOutput,
        model='claude-sonnet-4-6',
        phase=PipelinePhase.PARALLEL_ANALYSIS,
        depends_on=['document-ingestion'],
        max_tokens=4096,
    ),
    'market-macro': AgentConfig(
        name='market-macro',
        prompt_key='MARKET_MACRO_PROMPT',
        schema_class=MarketMacroOutput,
        model='claude-sonnet-4-6',
        phase=PipelinePhase.PARALLEL_ANALYSIS,
        depends_on=['document-ingestion'],
        max_tokens=4096,
    ),
    'lending-affordability': AgentConfig(
        name='lending-affordability',
        prompt_key='LENDING_AFFORDABILITY_PROMPT',
        schema_class=LendingAffordabilityOutput,
        model='claude-opus-4-6',
        phase=PipelinePhase.LENDING,
        depends_on=['financial-analysis'],
        max_tokens=4096,
    ),
    'synthesis-report': AgentConfig(
        name='synthesis-report',
        prompt_key='SYNTHESIS_REPORT_PROMPT',
        schema_class=SynthesisReportOutput,
        model='claude-opus-4-6',
        phase=PipelinePhase.SYNTHESIS,
        depends_on=[
            'document-ingestion',
            'financial-analysis',
            'tax-compliance',
            'ar-collections',
            'customer-concentration',
            'operations-transferability',
            'lease-contract',
            'market-macro',
            'lending-affordability',
        ],
        max_tokens=8192,
    ),
}
