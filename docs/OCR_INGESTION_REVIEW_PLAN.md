# OCR Ingestion To Review Flow Investigation

## Problem Statement

The upload page can send sample company documents through the OCR/classification step, and the UI shows classification results. After clicking "Continue with these classifications", the review page still shows empty financial fields and missing-document warnings for profit and loss, balance sheet, tax returns, cash flow, and A/R aging.

The sample run in `backend/backend/.artifacts/0cdd9dca-01b2-4c24-904c-777df74078ce/ingestion_artifacts.json` proves that the system has already extracted usable document content:

- `PeakAir_Financials.xlsx` has three parsed sheet sections:
  - `P&L Statement`
  - `Balance Sheet`
  - `SDE Summary`
- `PeakAir_CustomerList_PPE.xlsx` has customer list and PPE rows.
- `PeakAir_LeaseAgreement.docx` has lease text.
- `PeakAir_TaxReturns.docx` has tax return text.

However, all five documents in that artifact are typed as `other`, and the review response still returns `incomeStatement: null`, `balanceSheet: null`, `loanTerms: null`, and `cashFlow: null`.

## Current Runtime Flow

1. The user uploads documents on `app/analyze/upload/page.tsx`.
2. `handleClassify` calls `ingestDocuments(files)`.
3. `lib/api-client.ts` posts those files to `POST /api/documents/ingest`.
4. `backend/app/api/routes/ingest_documents.py` reads each file, saves it under `uploads/<runId>/`, and calls `ocr_document(...)`.
5. `backend/app/agents/mistral_ocr_client.py` sends the file bytes to Mistral OCR using `mistral-ocr-2512`.
6. The route returns `ClassifiedFile` records with `detectedType`, `confidence`, `rationale`, and metadata.
7. The upload UI displays those classifications and lets the user override them.
8. `handleContinue` posts the original files plus selected types to `parseDocuments(files, effectiveTypes)`.
9. `lib/api-client.ts` posts to `POST /api/parse-documents`.
10. `backend/app/api/routes/parse_documents.py` calls `parse_documents(files, parsed_file_types)`.
11. `backend/app/services/document_parser.py` calls `normalize_upload_files`, then `ingest_and_persist_intake_documents`.
12. The review page reads only `extractedData` from this response for the financial form.

There are two important separations:

- `/documents/ingest` performs OCR classification.
- `/parse-documents` performs ingestion and review-page seeding.

The second step does not reuse the OCR `full_markdown`, OCR page content, or saved OCR result from the first step.

## Root Causes

### 1. The classification labels are not reaching `/parse-documents`

Frontend sends this form field:

```ts
formData.append('fileTypes', JSON.stringify(fileTypes));
```

Backend route expects this parameter:

```py
file_types: str = Form(default="[]")
```

With FastAPI, that means the backend is looking for `file_types`, not `fileTypes`. In the browser flow, `file_types` is absent, so the backend uses the default `[]`.

Then `normalize_upload_files` does this:

```py
declared = file_types[index] if index < len(file_types) else None
canonical_type = normalize_document_type(declared)
```

When `declared` is missing, `normalize_document_type(None)` returns `DocumentType.OTHER`.

This exactly matches the artifact:

```text
PeakAir_Financials.xlsx        document_type=other declared_type=null canonical_type=other
PeakAir_TaxReturns.docx        document_type=other declared_type=null canonical_type=other
PeakAir_LeaseAgreement.docx    document_type=other declared_type=null canonical_type=other
```

That is why missing-document inference reports P&L, balance sheet, and tax return as missing even though the files are present.

### 2. `/parse-documents` returns no populated `FinancialData`

`backend/app/services/document_parser.py` currently builds notes and completeness, but it never maps ingested sections into the legacy review-page shape:

```py
financial_data = FinancialData(
    income_statement=None,
    balance_sheet=None,
    loan_terms=None,
    cash_flow=None,
    parsing_notes=parsing_notes,
    data_completeness=completeness,
)
```

So even after fixing document type handoff, the review page will remain empty until a mapper populates:

- `FinancialData.income_statement`
- `FinancialData.balance_sheet`
- `FinancialData.loan_terms`
- `FinancialData.cash_flow`

The sample artifact already has enough rows to populate at least:

- Revenue: `983000`
- COGS / cost of revenue: `520990`
- Gross profit: `462010`
- Operating expenses: `359106`
- Net income: `102904`
- Owner salary: `172000`
- Depreciation and amortization: `18000`
- Interest expense on vehicle loans: `5880`
- SDE: `346045`
- Current assets: `173500`
- Current liabilities: `69000`
- Total assets: `313300`
- Total liabilities: `174000`
- Equity: `139300`
- Cash and equivalents: `41000`
- Accounts receivable: `98000`
- Inventory: `27500`
- Accounts payable: `28000`
- Asking price: `$1,150,000`

### 3. Multi-section documents are collapsed into one document type

`PeakAir_Financials.xlsx` contains P&L, balance sheet, and SDE sections. The current document model assigns one `document_type` to the whole file. If the file is classified as `profit_and_loss`, then the balance sheet section inside that same workbook is also treated as P&L unless section-level typing is added.

The current artifact has section names that are more precise than the document type:

```text
P&L Statement
Balance Sheet
SDE Summary
```

But `ingestion_service._sheet_section` sets each section's `document_type` from the parent document:

```py
document_type=document.canonical_type
```

That blocks downstream financial agents, which select sections by `section.document_type`.

For the first implementation pass, do not redesign the document model or implement true multi-section document typing. Instead, keep the document/section schema stable and add sheet-name-aware extraction so known workbook sections like `P&L Statement`, `Balance Sheet`, and `SDE Summary` can seed the review form even when their stored `section.document_type` is inherited from the parent file.

### 4. OCR classification taxonomy is narrower than the app taxonomy

`DocumentClassification` in `mistral_ocr_client.py` supports:

- P&L
- balance sheet
- cash flow
- tax return
- lease contract
- A/R aging
- bank statement
- acquisition document
- other

The app's canonical taxonomy also includes:

- customer list
- employee roster
- insurance policy
- equipment list

This explains why sample documents like `PeakAir_CustomerList_PPE.xlsx` and `PeakAir_EmployeeContracts.docx` often land as `other` unless the user overrides them. The fallback keyword classifier also does not identify customer lists, employee rosters, or equipment lists.

### 5. Structured fallback parses rows but does not normalize them into financial keys

XLSX/DOCX extraction produces raw rows and text sections. The deterministic agent layer expects normalized keys such as:

- `revenue`
- `cogs`
- `net_income`
- `current_assets`
- `total_liabilities`
- `owner_salary`

But the current workbook ingestion stores rows as column-letter dictionaries:

```json
{ "A": "Total Revenue", "B": "860000", "D": "926000", "F": "983000" }
```

That is human-readable, but not directly usable by deterministic metrics without another normalization layer.

### 6. The review page is driven by legacy `FinancialData`, not the pipeline output

The frontend stores both:

- `financialData`, used by `/analyze/review`.
- `pipelineDocuments`, used later by the agent pipeline.

The review form only initializes from `state.financialData`. It does not inspect `pipelineDocuments`, `ingestion_artifacts.json`, agent metrics, or OCR markdown. So any data that exists only in the ingestion artifact will not appear in the form.

## Recommended Repair Plan

### Phase 1: Fix the immediate type handoff bug

Goal: The document labels shown in the classification UI must be the same labels persisted in `pipelineDocuments`.

Implementation:

1. In `backend/app/api/routes/parse_documents.py`, accept both field names:

```py
file_types: str = Form(default="[]", alias="fileTypes")
```

or use two optional form fields and prefer `fileTypes` when present.

2. Add a regression test that calls the FastAPI route with a multipart form using `fileTypes`, not just a direct Python call with `file_types`.

3. Verify that a browser upload produces:

```text
PeakAir_Financials.xlsx canonical_type=profit_and_loss
PeakAir_LeaseAgreement.docx canonical_type=lease_agreement
PeakAir_TaxReturns.docx canonical_type=tax_return_1120s or tax_return_schedule_c
```

Expected result:

- Missing P&L warning should disappear if the financials workbook is classified as P&L.
- Tax warning should disappear if tax return is classified as a supported tax type.
- Lease classifications should survive into `pipelineDocuments` for downstream agents. The parse-page missing-input list does not currently require a lease document.
- The balance sheet warning may still remain for `PeakAir_Financials.xlsx` until the lightweight sheet-name-aware missing-input logic below is added, because the workbook has only one top-level document type.

This will not populate the review form by itself. It only preserves the user's selected labels into ingestion.

### Phase 2: Add lightweight sheet-name awareness, not full multi-section typing

Goal: Make the PeakAir workbook useful in one implementation pass without redesigning the document model.

Do not implement true multi-section documents yet. In this pass, avoid schema changes where one uploaded file becomes multiple top-level documents or every section gets an independently persisted canonical type consumed across the whole pipeline. Use a local section-kind helper for extraction and parse-time completeness instead.

Implementation:

1. Add a helper that infers a lightweight section kind from `section_name`, `raw_text`, and row labels:
   - Section name/title contains `profit & loss`, `p&l`, `income statement` -> `profit_and_loss`
   - Contains `balance sheet` -> `balance_sheet`
   - Contains `seller's discretionary earnings`, `SDE` -> `sde_summary`
   - Contains `tax return`, `Schedule C`, `gross receipts` -> `tax_return_schedule_c` or `tax_return_1040`
   - Contains `lease agreement`, `landlord`, `tenant`, `premises` -> `lease_agreement`
   - Contains `customer list`, `% of total rev`, `contract type`, `owner contact` -> `customer_list`
   - Contains `property, plant & equipment`, `asset description`, `book value`, `FMV` -> `equipment_list`
   - Contains `employee`, `non-compete`, `technician`, `salary` -> `employee_roster` or `contract`
2. Use this helper inside the financial extractor so it can find P&L, balance sheet, and SDE sheets even when stored section types still inherit the parent file type.
3. Use this helper in parse-time missing-input inference so a workbook sheet named `Balance Sheet` can count as balance-sheet evidence for the review-page warning.
4. Leave `DocumentInfo.document_type` and `DocumentSection.document_type` behavior unchanged in this pass. Full section-level typing remains a later pipeline improvement.

Expected result:

`PeakAir_Financials.xlsx` may still be stored as one top-level `profit_and_loss` document, but the parser should recognize:

```text
P&L Statement   inferred section kind=profit_and_loss
Balance Sheet   inferred section kind=balance_sheet
SDE Summary     inferred section kind=sde_summary
```

Deferred future work:

True section-level document typing should still be added later so downstream agents can filter by persisted section type. It is intentionally out of scope for the one-session repair plan.

### Phase 3: Normalize financial rows into `FinancialData`

Goal: The review page should be pre-populated from the ingestion artifact.

Implementation:

Create a backend service, for example:

```text
backend/app/services/financial_data_extractor.py
```

Responsibilities:

1. Accept `IngestionOutput`.
2. Find relevant sections by inferred section kind, section name, and existing section type where reliable.
3. Normalize rows from spreadsheets into a label/value model.
4. Choose the most recent period from columns such as `FY 2024`, `2024`, or the rightmost year column.
5. Populate `FinancialData`.
6. Emit parsing notes for every assumed mapping and every missing required value.

Suggested extraction functions:

```py
extract_income_statement(ingestion_output) -> IncomeStatement | None
extract_balance_sheet(ingestion_output) -> BalanceSheet | None
extract_cash_flow(ingestion_output) -> CashFlowStatement | None
extract_loan_terms_or_deal_info(ingestion_output) -> LoanTerms | None
```

For the PeakAir sample, map rows as follows:

Income statement:

- `Total Revenue` -> `revenue`
- `Total Cost of Revenue` or `Total COGS` -> `cogs`
- `Gross Profit` -> `gross_profit`
- `Total Operating Expenses` -> `operating_expenses`
- `Owner Salary & Benefits` -> `owner_salary`
- `Depreciation` -> `depreciation_amortization`
- `Net Income` -> `net_income`
- `EBITDA` -> `ebitda`

SDE summary:

- `Interest Expense on Vehicle Loans` -> `interest_expense`
- `One-Time Legal Fees` -> add-back category `one_time_expense`
- `Owner Health Insurance` -> add-back category `personal_expense`
- `Owner Vehicle (personal use)` -> add-back category `personal_expense`
- `Owner Cell Phone & Personal Expenses` -> add-back category `personal_expense`
- `Owner Retirement Contributions` -> add-back category `personal_expense`
- `Total SDE` -> `sde`
- `Asking Price (per listing)` -> `loan_terms.asking_price` or a companion deal-info suggestion

Balance sheet:

- `Total Current Assets` -> `current_assets`
- `Cash & Cash Equivalents` -> `cash_and_equivalents`
- `Accounts Receivable` -> `accounts_receivable`
- `Inventory - Parts & Supplies` -> `inventory`
- `Total Current Liabilities` -> `current_liabilities`
- `Accounts Payable` -> `accounts_payable`
- `TOTAL ASSETS` -> `total_assets`
- `TOTAL LIABILITIES` -> `total_liabilities`
- `Total Owner's Equity` -> `equity`

Expected result:

`/parse-documents` should return `extractedData.incomeStatement` and `extractedData.balanceSheet` with numeric values. The review page should display those values immediately.

### Phase 4: Persist and reuse OCR artifacts instead of discarding them

Goal: OCR should be part of ingestion, not only classification.

Current issue:

`/documents/ingest` returns classification rows but does not return or persist an OCR artifact reference for `/parse-documents` to consume. There is a TODO in `ingest_documents.py` to cache OCR by file hash.

Implementation:

1. Define an OCR artifact shape:

```json
{
  "fileHash": "...",
  "filename": "...",
  "ocrModel": "mistral-ocr-2512",
  "classification": { "...": "..." },
  "pages": [
    { "pageNumber": 1, "markdown": "..." }
  ],
  "fullMarkdown": "...",
  "costUsd": 0.002
}
```

2. Save it under the analysis/run artifact directory keyed by SHA-256 hash.
3. Return `ocrArtifactRef` and `fileHash` from `/documents/ingest`.
4. Send those refs into `/parse-documents`.
5. In `/parse-documents`, prefer cached OCR page markdown for image/PDF and DOCX files where available.
6. Avoid re-running OCR for the same file hash.

Expected result:

The pipeline should operate on a single artifact graph:

```text
uploaded file -> OCR artifact -> section-aware evidence -> normalized financial data -> review state -> agent pipeline
```

### Phase 5: Improve classification taxonomy and fallbacks

Goal: Sample company documents should categorize into useful canonical types without manual overrides.

Implementation:

1. Extend `DocumentClassification.document_type` to include app-level document types:
   - `customer_list`
   - `employee_roster`
   - `insurance_policy`
   - `equipment_list`
2. Update `_MISTRAL_TO_DETECTED_TYPE` and `_MISTRAL_TO_DOCUMENT_TYPE`.
3. Expand `_KEYWORD_TYPE_RULES` in `ingest_documents.py`.
4. Add a special rule for multi-purpose workbooks:
   - If an XLSX has sheets for P&L and balance sheet, return a primary type plus metadata about recognized sheet kinds. Do not add true multi-section typing in this pass.

Expected sample behavior:

```text
PeakAir_CustomerList_PPE.xlsx -> customer_list/equipment_list sections
PeakAir_EmployeeContracts.docx -> employee_roster or contract
PeakAir_Financials.xlsx -> P&L, balance sheet, SDE sections
PeakAir_LeaseAgreement.docx -> lease_agreement
PeakAir_TaxReturns.docx -> tax_return_schedule_c
```

### Phase 6: Align review-page deal info with extracted artifacts

Goal: Asking price, business type, years in operation, reason for sale, location, and industry should be pre-filled when evidence exists.

Implementation:

1. Add an optional backend response field:

```py
suggested_deal_info: DealInfo | None
```

or include asking price in `FinancialData.loan_terms.asking_price`.

2. Frontend `handleContinue` on upload should set both:

```ts
setFinancialData(result.extractedData)
setDealInfo(result.suggestedDealInfo ?? deriveDealInfoFromFinancialData(...))
```

3. For PeakAir:
   - Asking price from SDE summary: `1150000`
   - Business type from docs: HVAC/home services
   - Location from lease: Cedar Falls, IA
   - Reason for sale likely unknown unless explicitly found

## Test Plan

### Backend unit tests

Add tests for:

1. `/parse-documents` accepts `fileTypes` form alias.
2. `normalize_upload_files` preserves declared types from frontend classification.
3. Lightweight sheet-kind helper identifies P&L, balance sheet, and SDE sheets in one workbook.
4. Financial extractor maps PeakAir P&L rows to `IncomeStatement`.
5. Financial extractor maps PeakAir balance sheet rows to `BalanceSheet`.
6. SDE extractor maps add-backs and asking price.
7. Missing-input inference uses sheet-name-aware evidence, not only file-level types.

### Integration tests

Add a sample-company test using files from `sample company1`:

1. POST all five files through `/documents/ingest`.
2. POST the same files plus returned/overridden types through `/parse-documents`.
3. Assert:
   - P&L is not missing.
   - Balance sheet is not missing.
   - Tax return is not missing.
   - `extractedData.incomeStatement.revenue == 983000`.
   - `extractedData.incomeStatement.netIncome == 102904`.
   - `extractedData.balanceSheet.totalAssets == 313300`.
   - `extractedData.balanceSheet.totalLiabilities == 174000`.
   - `extractedData.loanTerms.askingPrice == 1150000` if using `loanTerms` for asking price.

### Frontend tests

Add tests for:

1. Upload page sends `fileTypes` and backend accepts it.
2. Review page initializes numeric inputs from non-null `FinancialData`.
3. User overrides are included in the parse request in the same order as files.

## Implementation Priority

1. Fix `fileTypes` / `file_types` alias mismatch.
2. Add regression test for multipart `fileTypes`.
3. Add lightweight sheet-name-aware inference for structured sections.
4. Add financial row mapper and populate `FinancialData`.
5. Cache and reuse OCR artifacts by file hash.
6. Expand OCR and fallback classification taxonomy.
7. Add sample-company integration tests.

## Why This Matters

The system currently has useful extracted content, but it is stranded in the wrong layer. OCR classification is visible to the user, ingestion artifacts contain the raw evidence, and downstream agents know how to reason over typed documents and sections, but the bridge between these layers is incomplete.

The one-session fix makes selected document labels survive into ingestion, adds lightweight section-name awareness, and maps structured rows into review-page defaults. A later product-grade pass should make the ingestion artifact the single source of truth for true section-level document types as well.
