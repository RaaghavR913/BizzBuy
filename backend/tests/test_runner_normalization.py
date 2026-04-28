from __future__ import annotations

from app.agents import runners
from app.agents.schemas import (
    AgentEnvelope,
    AgentResult,
    AgingBucket,
    AgingBucketName,
    ARCollectionsOutput,
    BalanceSheet,
    CashFlow,
    CollectibilityFlag,
    ComplianceFlag,
    ConcentrationRisk,
    DeductionAnalysis,
    DocumentInfo,
    DocumentSection,
    DocumentType,
    EntityStructure,
    EntityType,
    ExpenseAnalysis,
    FinancialAnalysisOutput,
    FinancialRisk,
    IngestionMetadata,
    IngestionOutput,
    Profitability,
    RevenueAnalysis,
    RevenueComparison,
    Severity,
    SdeAddBack,
    TaxComplianceOutput,
    Timeframe,
    Trend,
    WriteOffRisk,
    BuyerRequirements,
    DealStructure,
    AffordabilityAnalysis,
    SuggestedPriceRange,
    DeterministicScorecard,
    LendingAffordabilityOutput,
    LendingRisk,
    ContractType,
    RiskLevel,
    CustomerRecord,
    CustomerContractRisk,
    CustomerMetrics,
    CustomerConcentrationOutput,
    Criticality,
    KeyPersonnel,
    LicenseInfo,
    InsuranceInfo,
    EquipmentItem,
    OpsRisk,
    OwnerDependence,
    EmployeeSummary,
    EquipmentSummary,
    OpsTransferabilityOutput,
    Condition,
    EscalationType,
    RenewalOption,
    RentEscalation,
    LeaseDetails,
    OtherContract,
    LeaseRisk,
    LeaseContractOutput,
    MarketTrend,
    Density,
    Impact,
    Horizon,
    IndustryOverview,
    LocalMarket,
    MacroFactor,
    MarketThreat,
    MarketOpportunity,
    MarketMacroOutput,
    SBA7aAnalysis,
    RedFlag,
    GreenFlag,
    SectionSummaries,
    SectionSummary,
    NextStep,
    NormalizedMetric,
)


def _section(
    document_id: str,
    document_type: DocumentType,
    year: int | None,
    extracted_data: dict,
    raw_text: str,
    section_kind: str | None = None,
) -> DocumentSection:
    return DocumentSection(
        document_id=document_id,
        document_type=document_type,
        section_kind=section_kind,
        timeframe=Timeframe(fiscal_year=year),
        extracted_data=extracted_data,
        raw_text=raw_text,
        confidence=0.9,
    )


def _ingestion_output(documents: list[DocumentInfo]) -> IngestionOutput:
    return IngestionOutput(
        documents=documents,
        metadata=IngestionMetadata(
            total_documents=len(documents),
            successfully_parsed=len(documents),
            failed_documents=[],
            warnings=[],
        ),
    )


def test_relevant_sections_uses_section_identity_not_parent_document_type() -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="financials-1",
                file_name="financials.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                document_type=DocumentType.PROFIT_AND_LOSS,
                sections=[
                    _section("financials-1", DocumentType.PROFIT_AND_LOSS, 2024, {"revenue": 1000}, "", "profit_and_loss"),
                    _section("financials-1", DocumentType.BALANCE_SHEET, 2024, {"total_assets": 900}, "", "balance_sheet"),
                    _section("financials-1", DocumentType.PROFIT_AND_LOSS, 2024, {"sde": 300}, "", "sde_summary"),
                ],
            )
        ]
    )

    balance_sections = runners._relevant_sections(ingestion, {"balance_sheet"})
    tax_support_sections = runners._relevant_sections(ingestion, {"profit_and_loss"})
    financial_sections = runners._relevant_sections(ingestion, {"profit_and_loss", "balance_sheet", "sde_summary"})

    assert [section.section_kind for section in balance_sections] == ["balance_sheet"]
    assert [section.section_kind for section in tax_support_sections] == ["profit_and_loss"]
    assert [section.section_kind for section in financial_sections] == ["profit_and_loss", "balance_sheet", "sde_summary"]


def test_copy_result_preserves_diagnostics() -> None:
    original = AgentResult(
        status="success",
        data={"raw": True},
        diagnostics={"prompt_chars": 321, "prompt_sections": {"metrics": 12}},
    )

    copied = runners._copy_result(original, {"normalized": True})

    assert copied.data == {"normalized": True}
    assert copied.diagnostics == {"prompt_chars": 321, "prompt_sections": {"metrics": 12}}
    assert copied.diagnostics is not original.diagnostics


def _financial_output() -> FinancialAnalysisOutput:
    return FinancialAnalysisOutput(
        revenue_analysis=RevenueAnalysis(
            annual_figures=[],
            growth_rate=0.2,
            trend=Trend.INCREASING,
            seasonality_notes="Stable seasonality.",
        ),
        expense_analysis=ExpenseAnalysis(annual_figures=[], largest_categories=["Payroll"]),
        profitability=Profitability(
            gross_margin=0.5,
            net_margin=0.1,
            ebitda=130,
            adjusted_ebitda=150,
            sde=170,
            sde_add_backs=[SdeAddBack(description="Owner salary", amount=40, justification="Owner add-back")],
        ),
        cash_flow=CashFlow(
            operating_cash_flow=130,
            free_cash_flow=110,
            cash_flow_vs_net_income=True,
        ),
        balance_sheet=BalanceSheet(
            total_assets=900,
            total_liabilities=400,
            equity=500,
            current_ratio=2.5,
            debt_to_equity=0.8,
            working_capital=180,
        ),
        risks=[
            FinancialRisk(
                id="fin-1",
                category="earnings_quality",
                severity=Severity.HIGH,
                title="Aggressive add-backs",
                description="Owner add-backs require validation.",
                evidence="Owner salary add-back",
                financial_impact=25000,
                recommendation="Validate adjustments.",
            )
        ],
        overall_score=7,
        confidence=0.88,
        summary="Financials look workable with one major diligence item.",
    )


def test_financial_runner_emits_normalized_envelope(monkeypatch) -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="pl-2024",
                file_name="pnl-2024.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.PROFIT_AND_LOSS,
                sections=[
                    _section(
                        "pl-2024",
                        DocumentType.PROFIT_AND_LOSS,
                        2024,
                        {
                            "revenue": 1200,
                            "cogs": 600,
                            "net_income": 100,
                            "depreciation": 10,
                            "interest_expense": 5,
                            "income_tax": 15,
                            "owner_salary": 40,
                            "owner_benefits": 10,
                            "one_time_expenses": 5,
                            "operating_expenses": 450,
                        },
                        "Revenue 1200 Net income 100 Owner salary 40",
                    )
                ],
            ),
            DocumentInfo(
                document_id="bs-2024",
                file_name="balance-sheet.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.BALANCE_SHEET,
                sections=[
                    _section(
                        "bs-2024",
                        DocumentType.BALANCE_SHEET,
                        2024,
                        {"current_assets": 300, "current_liabilities": 120, "total_assets": 900, "total_liabilities": 400, "equity": 500},
                        "Current assets 300 Current liabilities 120",
                    )
                ],
            ),
            DocumentInfo(
                document_id="cf-2024",
                file_name="cashflow.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.CASH_FLOW_STATEMENT,
                sections=[
                    _section(
                        "cf-2024",
                        DocumentType.CASH_FLOW_STATEMENT,
                        2024,
                        {"operating_cash_flow": 130, "capital_expenditures": -20},
                        "Operating cash flow 130 Capex 20",
                    )
                ],
            ),
        ]
    )

    monkeypatch.setattr(
        runners,
        "call_agent",
        lambda *_args, **_kwargs: AgentResult(status="success", data=_financial_output()),
    )

    result = runners.run_financial_analysis(ingestion)

    assert result.status == "success"
    assert isinstance(result.data, AgentEnvelope)
    assert result.data.normalized_metrics["revenue_latest"].value == 1200
    assert result.data.normalized_metrics["working_capital"].value == 180
    assert result.data.findings[0].category.value == "earnings_quality"
    assert result.data.findings[0].metric_impact["financial_impact_usd"] == 25000
    assert result.data.evidence[0].document_id == "pl-2024"
    assert isinstance(result.data.raw_domain_output, FinancialAnalysisOutput)


def test_financial_runner_compacts_row_dump_in_prompt(monkeypatch) -> None:
    captured: dict[str, str] = {}
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="pl-2024",
                file_name="pnl-2024.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                document_type=DocumentType.PROFIT_AND_LOSS,
                sections=[
                    _section(
                        "pl-2024",
                        DocumentType.PROFIT_AND_LOSS,
                        2024,
                        {
                            "revenue": 1200,
                            "net_income": 100,
                            "rows": [
                                {"label": f"ROW-{idx}", "amount": idx}
                                for idx in range(40)
                            ],
                        },
                        "Revenue 1200 Net income 100",
                    )
                ],
            )
        ]
    )

    def fake_call_agent(_config, _prompt, user_message, _schema):
        captured["user_message"] = user_message
        return AgentResult(status="success", data=_financial_output())

    monkeypatch.setattr(runners, "call_agent", fake_call_agent)

    result = runners.run_financial_analysis(ingestion)

    assert result.status == "success"
    assert "evidence_pack" in captured["user_message"]
    assert '"rows"' not in captured["user_message"]
    assert "ROW-39" not in captured["user_message"]
    assert "Revenue 1200 Net income 100" not in captured["user_message"]
    assert '"revenue":1200' in captured["user_message"]


def test_tax_runner_marks_missing_tax_returns(monkeypatch) -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="pl-2024",
                file_name="pnl-2024.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.PROFIT_AND_LOSS,
                sections=[_section("pl-2024", DocumentType.PROFIT_AND_LOSS, 2024, {"revenue": 1200}, "Revenue 1200")],
            )
        ]
    )

    tax_output = TaxComplianceOutput(
        revenue_comparison=[],
        deduction_analysis=[DeductionAnalysis(category="Travel", amount=1000, flagged=False)],
        entity_structure=EntityStructure(type=EntityType.S_CORP, tax_filing_type="1120S", state_filings=["TX"]),
        compliance_flags=[],
        unreported_income_risk="high",
        overall_score=3,
        confidence=0.35,
        summary="No tax returns were provided.",
    )

    monkeypatch.setattr(
        runners,
        "call_agent",
        lambda *_args, **_kwargs: AgentResult(status="success", data=tax_output),
    )

    result = runners.run_tax_compliance(ingestion)

    assert result.status == "success"
    assert isinstance(result.data, AgentEnvelope)
    assert result.data.normalized_metrics["tax_returns_present"].value is False
    assert result.data.missing_inputs[0].key == "tax_returns"
    assert any(finding.missing_data for finding in result.data.findings)


def test_lending_runner_accepts_financial_envelope_and_emits_missing_asking_price(monkeypatch) -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="pl-2024",
                file_name="pnl-2024.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.PROFIT_AND_LOSS,
                sections=[_section("pl-2024", DocumentType.PROFIT_AND_LOSS, 2024, {"revenue": 1200}, "Revenue 1200")],
            )
        ]
    )

    financial_envelope = AgentEnvelope(
        agent_name="financial_analysis",
        status="success",
        summary="Financial summary",
        confidence=0.88,
        overall_score=7,
        raw_domain_output=_financial_output(),
    )
    lending_output = LendingAffordabilityOutput(
        sba7a=SBA7aAnalysis(
            eligible_for_sba=True,
            max_loan_amount=5000000,
            interest_rate=0.105,
            term_years=10,
            monthly_payment=9800,
            annual_debt_service=117600,
            dscr=1.45,
            dscr_meets_minimum=True,
            down_payment_required=102000,
            down_payment_percent=0.2,
            total_project_cost=510000,
        ),
        affordability_analysis=AffordabilityAnalysis(
            asking_price=510000,
            adjusted_sde=170000,
            sde_multiple=3.0,
            is_reasonably_priced=True,
            suggested_price_range=SuggestedPriceRange(low=425000, high=595000),
        ),
        buyer_requirements=BuyerRequirements(
            minimum_down_payment=102000,
            estimated_closing_costs=18000,
            total_cash_needed=165000,
            minimum_post_close_liquidity=45000,
        ),
        deal_structure=DealStructure(
            recommended_structure="SBA with seller note",
            seller_financing_component=25000,
            earnout_component=None,
            rationale="Balances debt service and cash needed.",
        ),
        risks=[
            LendingRisk(
                id="lend-1",
                severity=Severity.MEDIUM,
                title="Tight liquidity",
                description="Buyer liquidity is only modestly above target.",
                recommendation="Maintain extra post-close reserves.",
            )
        ],
        overall_score=7,
        confidence=0.81,
        summary="Financeable at the modeled price.",
    )

    monkeypatch.setattr(
        runners,
        "call_agent",
        lambda *_args, **_kwargs: AgentResult(status="success", data=lending_output),
    )

    result = runners.run_lending_affordability(ingestion, financial_envelope, asking_price=None)

    assert result.status == "success"
    assert isinstance(result.data, AgentEnvelope)
    assert result.data.normalized_metrics["dscr"].value == 1.45
    assert result.data.normalized_metrics["total_cash_needed"].value == 165000
    assert result.data.missing_inputs[0].key == "asking_price"


def test_lending_runner_uses_document_asking_price_without_missing_input(monkeypatch) -> None:
    captured: dict[str, str] = {}
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="cim-1",
                file_name="cim.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                document_type=DocumentType.CONTRACT,
                sections=[
                    _section(
                        "cim-1",
                        DocumentType.CONTRACT,
                        None,
                        {"rows": [{"row_index": 1, "A": "Asking Price", "B": "$1,300,000"}]},
                        "Asking Price | $1,300,000",
                    )
                ],
            )
        ]
    )
    financial_envelope = AgentEnvelope(
        agent_name="financial_analysis",
        status="success",
        summary="Financial summary",
        confidence=0.88,
        overall_score=7,
        raw_domain_output=_financial_output(),
    )
    lending_output = LendingAffordabilityOutput(
        sba7a=SBA7aAnalysis(
            eligible_for_sba=True,
            max_loan_amount=5000000,
            interest_rate=0.105,
            term_years=10,
            monthly_payment=24900,
            annual_debt_service=298800,
            dscr=1.9,
            dscr_meets_minimum=True,
            down_payment_required=260000,
            down_payment_percent=0.2,
            total_project_cost=1300000,
        ),
        affordability_analysis=AffordabilityAnalysis(
            asking_price=1300000,
            adjusted_sde=170000,
            sde_multiple=7.65,
            is_reasonably_priced=False,
            suggested_price_range=SuggestedPriceRange(low=425000, high=595000),
        ),
        buyer_requirements=BuyerRequirements(
            minimum_down_payment=260000,
            estimated_closing_costs=36000,
            total_cash_needed=338500,
            minimum_post_close_liquidity=45000,
        ),
        deal_structure=DealStructure(
            recommended_structure="Reprice or require seller financing",
            seller_financing_component=250000,
            earnout_component=None,
            rationale="Price is high relative to SDE.",
        ),
        risks=[],
        overall_score=4,
        confidence=0.81,
        summary="Document asking price is expensive at current SDE.",
    )

    def fake_call_agent(_config, _prompt, user_message, _schema):
        captured["user_message"] = user_message
        return AgentResult(status="success", data=lending_output)

    monkeypatch.setattr(runners, "call_agent", fake_call_agent)

    result = runners.run_lending_affordability(ingestion, financial_envelope, asking_price=None)

    assert result.status == "success"
    assert isinstance(result.data, AgentEnvelope)
    assert result.data.normalized_metrics["asking_price"].value == 1300000
    assert result.data.normalized_metrics["asking_price_source"].value == "document"
    assert result.data.missing_inputs == []
    assert '"value":1300000.0' in captured["user_message"]
    assert '"source":"document"' in captured["user_message"]


def test_customer_runner_adds_contract_gap_and_normalized_metrics(monkeypatch) -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="customers-1",
                file_name="customers.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                document_type=DocumentType.CUSTOMER_LIST,
                sections=[
                    _section(
                        "customers-1",
                        DocumentType.CUSTOMER_LIST,
                        2024,
                        {
                            "customers": [
                                {"name": "Alpha Co", "annualRevenue": 700},
                                {"name": "Beta Co", "annualRevenue": 300},
                            ]
                        },
                        "Alpha Co 700 Beta Co 300",
                    )
                ],
            )
        ]
    )

    customer_output = CustomerConcentrationOutput(
        customers=[
            CustomerRecord(
                name="Alpha Co",
                annual_revenue=700,
                revenue_percent=70,
                contract_type=ContractType.ANNUAL,
                auto_renew=False,
                churn_risk=RiskLevel.MEDIUM,
            ),
            CustomerRecord(
                name="Beta Co",
                annual_revenue=300,
                revenue_percent=30,
                contract_type=ContractType.MONTH_TO_MONTH,
                auto_renew=False,
                churn_risk=RiskLevel.HIGH,
            ),
        ],
        concentration_metrics=CustomerMetrics(
            herfindahl_index=5800,
            top_customer_percent=70,
            top5_percent=100,
            top10_percent=100,
        ),
        contract_risks=[
            CustomerContractRisk(
                id="cust-1",
                severity=Severity.HIGH,
                customer_name="Alpha Co",
                title="Major customer concentration",
                description="Alpha Co represents 70% of revenue with limited contractual protection.",
            )
        ],
        single_customer_dependency=True,
        overall_score=4,
        confidence=0.73,
        summary="Revenue concentration is high.",
    )

    monkeypatch.setattr(
        runners,
        "call_agent",
        lambda *_args, **_kwargs: AgentResult(status="success", data=customer_output),
    )

    result = runners.run_customer_concentration(ingestion)

    assert result.status == "success"
    assert isinstance(result.data, AgentEnvelope)
    assert result.data.normalized_metrics["top_customer_revenue_pct"].value == 70.0
    assert result.data.findings[0].category.value == "contract_durability"
    assert {item.key for item in result.data.missing_inputs} == {"customer_contracts"}
    assert any(finding.missing_data for finding in result.data.findings)


def test_ops_runner_marks_missing_employee_roster(monkeypatch) -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="insurance-1",
                file_name="insurance.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.INSURANCE_POLICY,
                sections=[
                    _section(
                        "insurance-1",
                        DocumentType.INSURANCE_POLICY,
                        2024,
                        {"policies": [{"type": "General Liability", "provider": "Carrier", "annualPremium": 12000, "adequate": True}]},
                        "General Liability policy annual premium 12000",
                    )
                ],
            )
        ]
    )

    ops_output = OpsTransferabilityOutput(
        owner_dependence=OwnerDependence(
            weekly_hours_worked=45,
            roles_performed=["Sales", "Operations"],
            has_delegated_management=False,
            transition_time_estimate="6 months",
            score=3,
        ),
        employees=EmployeeSummary(
            headcount=2,
            key_personnel=[
                KeyPersonnel(
                    name="Jordan",
                    role="Estimator",
                    tenure="4 years",
                    criticality=Criticality.HIGH,
                    retention_risk=Criticality.HIGH,
                )
            ],
        ),
        licenses=[LicenseInfo(type="State License", holder="Owner", transferable=True)],
        insurance=[InsuranceInfo(type="General Liability", provider="Carrier", annual_premium=12000, adequate=True)],
        equipment=EquipmentSummary(
            total_estimated_value=50000,
            items=[
                EquipmentItem(
                    name="Truck",
                    condition=Condition.GOOD,
                    estimated_age="3 years",
                    estimated_value=50000,
                    replacement_needed=False,
                )
            ],
        ),
        risks=[
            OpsRisk(
                id="ops-1",
                severity=Severity.HIGH,
                category="owner dependence",
                title="Owner is central to operations",
                description="The owner still performs core operating functions.",
                recommendation="Build a delegated management layer.",
            )
        ],
        overall_score=4,
        confidence=0.69,
        summary="Transferability is constrained by owner dependence.",
    )

    monkeypatch.setattr(
        runners,
        "call_agent",
        lambda *_args, **_kwargs: AgentResult(status="success", data=ops_output),
    )

    result = runners.run_ops_transferability(ingestion)

    assert result.status == "success"
    assert isinstance(result.data, AgentEnvelope)
    assert result.data.normalized_metrics["owner_dependence_score"].value == 3
    assert result.data.normalized_metrics["transferable_license_count"].value == 0
    assert {item.key for item in result.data.missing_inputs} == {"employee_roster"}
    assert any(finding.missing_data for finding in result.data.findings)


def test_lease_runner_adds_missing_key_contracts(monkeypatch) -> None:
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="lease-1",
                file_name="lease.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.LEASE_AGREEMENT,
                sections=[
                    _section(
                        "lease-1",
                        DocumentType.LEASE_AGREEMENT,
                        2024,
                        {"monthlyRent": 8500, "leaseEnd": "2028-12-31T00:00:00Z"},
                        "Monthly rent 8500 lease end 2028-12-31T00:00:00Z",
                    )
                ],
            )
        ]
    )

    lease_output = LeaseContractOutput(
        lease=LeaseDetails(
            landlord="Main Street LLC",
            monthly_rent=8500,
            annual_rent=102000,
            lease_start="2024-01-01",
            lease_end="2028-12-31",
            remaining_months=32,
            is_transferable=False,
            assignment_clause="Landlord consent required",
            rent_escalation=RentEscalation(type=EscalationType.FIXED, rate=0.03, schedule="Annual"),
            renewal_options=[RenewalOption(term="5 years", conditions="Market rent reset")],
            restrictions=["Landlord approval required for assignment"],
        ),
        non_compete=None,
        other_contracts=[
            OtherContract(
                type="Vendor agreement",
                counterparty="Key Supplier",
                term="3 years",
                transferable=False,
                key_terms=["Change of control notice"],
                risks=["Non-transferable without consent"],
            )
        ],
        risks=[
            LeaseRisk(
                id="lease-1",
                severity=Severity.HIGH,
                title="Lease assignment consent required",
                description="Landlord consent is required before transfer.",
                recommendation="Obtain landlord consent before close.",
            )
        ],
        overall_score=5,
        confidence=0.77,
        summary="Lease transferability needs attention.",
    )

    monkeypatch.setattr(
        runners,
        "call_agent",
        lambda *_args, **_kwargs: AgentResult(status="success", data=lease_output),
    )

    result = runners.run_lease_contract(ingestion)

    assert result.status == "success"
    assert isinstance(result.data, AgentEnvelope)
    assert result.data.normalized_metrics["assignment_clause_risk"].value is True
    assert result.data.normalized_metrics["key_contracts_non_transferable_count"].value == 1
    assert {item.key for item in result.data.missing_inputs} == {"key_contracts"}
    assert result.data.evidence[0].document_id == "lease-1"


def test_market_runner_declares_missing_context_when_inputs_are_thin(monkeypatch) -> None:
    ingestion = _ingestion_output([])

    market_output = MarketMacroOutput(
        industry_overview=IndustryOverview(
            name="Unknown",
            trend=MarketTrend.STABLE,
            key_drivers=["Stable replacement demand"],
        ),
        local_market=LocalMarket(
            area="Unknown",
            competitor_density=Density.MEDIUM,
            demand_outlook="Mixed",
        ),
        macro_factors=[MacroFactor(factor="Interest rates", impact=Impact.NEGATIVE, description="Borrowing costs remain elevated.")],
        threats=[
            MarketThreat(
                id="market-1",
                severity=Severity.MEDIUM,
                title="Higher financing costs",
                description="Elevated rates may reduce buyer demand.",
                timeframe=Horizon.NEAR_TERM,
            )
        ],
        opportunities=[MarketOpportunity(id="opp-1", title="Recurring demand", description="Repair demand remains resilient.", timeframe=Horizon.MEDIUM_TERM)],
        overall_score=6,
        confidence=0.42,
        summary="Macro conditions are serviceable but context is thin.",
    )

    monkeypatch.setattr(
        runners,
        "call_agent",
        lambda *_args, **_kwargs: AgentResult(status="success", data=market_output),
    )

    result = runners.run_market_macro(ingestion)

    assert result.status == "success"
    assert isinstance(result.data, AgentEnvelope)
    assert result.data.normalized_metrics["industry_trend"].value == "stable"
    assert result.data.normalized_metrics["threat_count_high_or_critical"].value == 0
    assert {item.key for item in result.data.missing_inputs} == {"document_context", "business_type", "location"}
    assert any(finding.missing_data for finding in result.data.findings)


def test_market_runner_preserves_full_document_context_in_prompt(monkeypatch) -> None:
    captured: dict[str, str] = {}
    long_text = ("Service area includes Phoenix and Tucson. " * 120) + "TAIL_MARKER_SHOULD_NOT_APPEAR"
    ingestion = _ingestion_output(
        [
            DocumentInfo(
                document_id="ops-1",
                file_name="operations-notes.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.OTHER,
                sections=[
                    _section(
                        "ops-1",
                        DocumentType.OTHER,
                        2024,
                        {"notes": "Service area expansion"},
                        long_text,
                    )
                ],
            )
        ]
    )

    market_output = MarketMacroOutput(
        industry_overview=IndustryOverview(
            name="Home Services",
            trend=MarketTrend.STABLE,
            key_drivers=["Replacement demand"],
        ),
        local_market=LocalMarket(
            area="Phoenix, AZ",
            competitor_density=Density.MEDIUM,
            demand_outlook="Stable",
        ),
        macro_factors=[MacroFactor(factor="Rates", impact=Impact.NEGATIVE, description="Financing remains expensive.")],
        threats=[],
        opportunities=[],
        overall_score=6,
        confidence=0.52,
        summary="Market context is usable.",
    )

    def fake_call_agent(_config, _prompt, user_message, _schema):
        captured["user_message"] = user_message
        return AgentResult(status="success", data=market_output)

    monkeypatch.setattr(runners, "call_agent", fake_call_agent)

    result = runners.run_market_macro(ingestion)

    assert result.status == "success"
    assert "context_snippets" in captured["user_message"]
    assert "TAIL_MARKER_SHOULD_NOT_APPEAR" in captured["user_message"]
    assert len(captured["user_message"]) > 5000


def test_synthesis_runner_uses_deterministic_scorecard_as_authoritative_context(monkeypatch) -> None:
    captured: dict[str, str] = {}
    scorecard = DeterministicScorecard(
        overall_risk_score=63,
        overall_recommendation="conditional_buy",
        completeness_score=0.82,
        confidence_score=0.77,
    )
    agent_results = {
        "financial_analysis": AgentResult(
            status="success",
            data=AgentEnvelope(
                agent_name="financial_analysis",
                status="success",
                summary="Margins are solid but add-backs need validation.",
                confidence=0.86,
                overall_score=7,
            ),
        )
    }

    def fake_call_agent(_config, _prompt, user_message, _schema):
        captured["user_message"] = user_message
        return AgentResult(
            status="success",
            data=runners.SynthesisReportOutput(
                executive_summary="The coded recommendation is supportable, but diligence should stay tight around earnings quality.",
                red_flags=[
                    RedFlag(
                        id="financial-1",
                        severity=Severity.HIGH,
                        source="financial",
                        title="Add-backs need validation",
                        description="Reported earnings include adjustments that need support.",
                    )
                ],
                green_flags=[
                    GreenFlag(
                        id="financial-green",
                        source="financial",
                        title="Core profitability is intact",
                        description="Baseline operating performance still appears workable.",
                    )
                ],
                section_summaries=SectionSummaries(
                    financial=SectionSummary(score=7, summary="Financials are workable.", top_risks=["Validate add-backs"]),
                    tax=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    ar=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    customer=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    operations=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    lease=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    market=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    lending=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                ),
                next_steps=[NextStep(priority=1, action="Request add-back support", reason="This is the main driver behind the coded caution.")],
                deal_terms_suggestion="Keep price discipline and tie any premium to diligence support.",
            ),
        )

    monkeypatch.setattr(runners, "call_agent", fake_call_agent)

    result = runners.run_synthesis_report(scorecard, agent_results)

    assert result.status == "success"
    assert "## Synthesis Context" in captured["user_message"]
    assert '"overall_risk_score":63' in captured["user_message"]
    assert '"overall_recommendation":"conditional_buy"' in captured["user_message"]
    assert "suggested_recommendation_band" not in captured["user_message"]


def test_synthesis_runner_preserves_full_specialist_context(monkeypatch) -> None:
    captured: dict[str, str] = {}
    scorecard = DeterministicScorecard(
        overall_risk_score=58,
        overall_recommendation="buy",
        completeness_score=0.9,
        confidence_score=0.81,
        validated_metrics={
            f"metric_{idx:02d}": NormalizedMetric(value=idx)
            for idx in range(15)
        },
    )
    agent_results = {
        "financial_analysis": AgentResult(
            status="success",
            data=AgentEnvelope(
                agent_name="financial_analysis",
                status="success",
                summary="Core profitability is solid, but add-backs need support.",
                confidence=0.84,
                overall_score=7,
                raw_domain_output={"huge_blob": "RAW_DOMAIN_TEXT_SHOULD_NOT_APPEAR"},
            ),
        )
    }

    def fake_call_agent(_config, _prompt, user_message, _schema):
        captured["user_message"] = user_message
        return AgentResult(
            status="success",
            data=runners.SynthesisReportOutput(
                executive_summary="Healthy base case with one diligence holdback.",
                red_flags=[],
                green_flags=[],
                section_summaries=SectionSummaries(
                    financial=SectionSummary(score=7, summary="Financials are workable.", top_risks=["Validate add-backs"]),
                    tax=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    ar=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    customer=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    operations=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    lease=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    market=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                    lending=SectionSummary(score=1, summary="Analysis unavailable.", top_risks=["Analysis did not complete."]),
                ),
                next_steps=[NextStep(priority=1, action="Validate add-backs", reason="Primary diligence item")],
                deal_terms_suggestion="Tie any premium to verified earnings support.",
            ),
        )

    monkeypatch.setattr(runners, "call_agent", fake_call_agent)

    result = runners.run_synthesis_report(scorecard, agent_results)

    assert result.status == "success"
    assert '"metric_00"' in captured["user_message"]
    assert '"metric_13"' in captured["user_message"]
    assert "RAW_DOMAIN_TEXT_SHOULD_NOT_APPEAR" not in captured["user_message"]
    assert "specialist_briefs" in captured["user_message"]
    assert "section_summaries" not in captured["user_message"]
