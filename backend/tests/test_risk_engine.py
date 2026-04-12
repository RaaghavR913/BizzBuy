from app.models.schemas import DealInfo, FinancialData, QuestionnaireData
from app.services.analysis_service import run_analysis


def test_analysis_returns_deterministic_report():
    financials = FinancialData(
        income_statement={
            "revenue": 850000,
            "cogs": 250000,
            "grossProfit": 600000,
            "operatingExpenses": 420000,
            "netIncome": 120000,
            "ownerSalary": 90000,
            "addBacks": [{"description": "Personal auto", "amount": 12000, "category": "personal_expense"}],
            "periods": ["2025"],
        },
        loan_terms={
            "loanAmount": 600000,
            "interestRate": 0.11,
            "termMonths": 120,
            "askingPrice": 750000,
        },
        parsing_notes=[],
        data_completeness=0.85,
    )
    questionnaire = QuestionnaireData(
        owner_dependence={
            "ownerSalesPercentage": 70,
            "ownerInvolvement": "full_time",
            "ownerHoldsRelationships": True,
            "survives90DayAbsence": "unlikely",
        },
        customer_concentration={
            "topCustomerRevenuePercent": 35,
            "top5CustomersRevenuePercent": 70,
            "contractType": "mostly_handshake",
            "averageCustomerTenure": "1_to_3_years",
        },
        revenue_quality={
            "recurringRevenuePercent": 15,
            "projectBasedPercent": 85,
            "revenueTrend": "flat",
            "knownUpcomingLosses": False,
        },
        employee_risk={
            "totalEmployees": 8,
            "missionCriticalEmployees": 3,
            "hasSOPs": False,
            "hasManagementLayer": False,
        },
        supplier_risk={
            "singleSupplierOver30Pct": False,
            "supplierAgreementsDocumented": True,
            "exclusiveVendorRelationships": False,
        },
        financial_risk={
            "hasAddBacks": True,
            "addBacksExceed30Pct": False,
            "pendingLiabilities": False,
        },
    )
    deal_info = DealInfo(
        asking_price=750000,
        business_type="hvac",
        years_in_operation=12,
        reason_for_sale="retirement",
    )

    report = run_analysis(financials, questionnaire, deal_info)

    assert report.executive_summary.risk_score > 0
    assert report.risk_assessment.dimensions
    assert report.final_recommendation.action in {"proceed", "proceed_with_caution", "walk_away"}
