# OCR Ingestion To Review Flow Implementation Report

This document records the implementation work completed from `docs/OCR_INGESTION_REVIEW_PLAN.md`.
It is intended as a maintainer handoff: what changed, why it changed, how the pieces fit together, what was verified, and what remains deliberately deferred.

## Executive Summary

The upload-to-review flow now preserves user-visible classification labels, recognizes useful workbook sections by sheet/content names, and maps structured financial rows into the legacy `FinancialData` shape used by the review page.

The PeakAir sample flow that previously produced:

```text
incomeStatement: null
balanceSheet: null
loanTerms: null
cashFlow: null
```

now seeds review data from `PeakAir_Financials.xlsx`, including:

```text
Revenue:                 983000
COGS:                    520990
Gross profit:            462010
Operating expenses:      359106
Net income:              102904
Owner salary:            172000
Depreciation:            18000
Interest expense:        5880
SDE:                     346045
Current assets:          173500
Current liabilities:     69000
Total assets:            313300
Total liabilities:       174000
Equity:                  139300
Accounts receivable:     98000
Asking price:            1150000
```

The implementation also adds OCR artifact caching by uploaded file hash and passes the resulting OCR references from the classification step into the parse step, so cached OCR markdown can be reused for PDF/image-like files instead of being discarded.

## Files Added

### `backend/app/services/section_kind.py`

Added a lightweight section-kind inference helper.

Purpose:

- Infer useful semantic types from section names, raw text, and spreadsheet row labels.
- Avoid changing the persisted `DocumentInfo` or `DocumentSection` schemas.
- Let downstream extraction use more precise local section kinds than the inherited parent document type.

Key functions:

- `infer_section_kind(...) -> str`
- `infer_sheet_kinds(sheets) -> list[str]`

Recognized section kinds include:

- `profit_and_loss`
- `balance_sheet`
- `sde_summary`
- `tax_return_schedule_c`
- `tax_return_1120s`
- `lease_agreement`
- `customer_list`
- `equipment_list`
- `employee_roster`
- `other`

Important design choice:

The helper prioritizes explicit sheet/content names such as `Balance Sheet`, `Customer List`, `PP&E Schedule`, and `SDE Summary` before falling back to inherited document type. This matters because a balance sheet section may include a phrase like `from P&L`, and a naive keyword scan would otherwise misclassify it as a P&L.

### `backend/app/services/financial_data_extractor.py`

Added a deterministic mapper from `IngestionOutput` into the legacy review-page financial models.

Purpose:

- Convert spreadsheet rows stored as column-letter dictionaries into normalized financial fields.
- Select the most recent period, such as `FY 2024`, from multi-year tables.
- Populate:
  - `IncomeStatement`
  - `BalanceSheet`
  - `LoanTerms`
  - `CashFlowStatement`, when supported rows exist
- Add parsing notes describing mapped sections and missing values.

Key functions and structures:

- `extract_financial_data(ingestion_output)`
- `_extract_income_statement(...)`
- `_extract_balance_sheet(...)`
- `_extract_loan_terms(...)`
- `_extract_cash_flow(...)`
- `RowTable`
- `RowValue`

The extractor uses `infer_section_kind(...)` to find the relevant P&L, balance sheet, SDE, and cash-flow sections even when `DocumentSection.document_type` still inherits the parent file type.

## Backend Route Changes

### `backend/app/api/routes/parse_documents.py`

Fixed the frontend/backend form-field mismatch.

Before:

```py
file_types: str = Form(default="[]")
```

The frontend sends:

```ts
formData.append('fileTypes', JSON.stringify(fileTypes));
```

FastAPI treats `file_types` and `fileTypes` as different field names, so the route was defaulting to `[]` in the browser flow. That caused every upload to normalize as `other`.

Now the route accepts both:

```py
file_types: str | None = Form(default=None)
fileTypes: str | None = Form(default=None)
```

It prefers the browser field, `fileTypes`, when present.

Additional parse form fields were added:

```py
file_hashes / fileHashes
ocr_artifact_refs / ocrArtifactRefs
```

These allow the parse route to receive OCR cache references from the classification route.

The route now passes these values into:

```py
parse_documents(
    files,
    parsed_file_types,
    file_hashes=parsed_file_hashes,
    ocr_artifact_refs=parsed_ocr_refs,
)
```

### `backend/app/api/routes/ingest_documents.py`

Added OCR artifact caching and expanded classification metadata.

New behavior:

1. Computes a SHA-256 hash for every uploaded file.
2. Checks for an existing OCR artifact at:

   ```text
   <BIZBUY_ARTIFACT_DIR or backend/.artifacts>/ocr/<sha256>.json
   ```

3. If a cached OCR result exists, it uses that instead of calling Mistral.
4. If no cached OCR result exists, it calls `ocr_document(...)` and writes the result to the artifact cache.
5. Returns both:

   ```json
   {
     "fileHash": "...",
     "ocrArtifactRef": "..."
   }
   ```

6. Keeps structured fallback metadata such as columns, row count, sheet count, and sheet kinds.

The response model `ClassifiedFile` now includes:

```py
file_hash: str | None = Field(default=None, alias="fileHash")
ocr_artifact_ref: str | None = Field(default=None, alias="ocrArtifactRef")
```

The structured classifier now also reports workbook sheet kinds when possible:

```json
{
  "sheetKinds": ["profit_and_loss", "balance_sheet", "sde_summary"]
}
```

The fallback keyword classifier was expanded to identify:

- `customer_list`
- `equipment_list`
- `employee_roster`
- `insurance_policy`
- `tax_return_schedule_c`

## Backend Service Changes

### `backend/app/services/document_parser.py`

The parse service now accepts OCR cache references and delegates them to upload normalization:

```py
parse_documents(
    files,
    file_types,
    file_hashes=None,
    ocr_artifact_refs=None,
)
```

After ingestion, it now calls:

```py
extracted_financials = extract_financial_data(ingestion_output)
```

Then it populates `FinancialData` from the extractor output:

```py
FinancialData(
    income_statement=extracted_financials.income_statement,
    balance_sheet=extracted_financials.balance_sheet,
    loan_terms=extracted_financials.loan_terms,
    cash_flow=extracted_financials.cash_flow,
    parsing_notes=parsing_notes,
    data_completeness=completeness,
)
```

Before this change, all four financial sections were explicitly returned as `None`.

### `backend/app/services/intake_service.py`

There were two major changes.

#### 1. Cached OCR reuse

`normalize_upload_files(...)` now accepts:

```py
file_hashes: list[str] | None = None
ocr_artifact_refs: list[str] | None = None
```

It attempts to load cached OCR markdown from the artifact cache. If cached OCR text exists, and the upload is a PDF or otherwise has no extracted raw text, that markdown becomes the intake document text.

The document also receives this note:

```text
Reused cached OCR artifact text for ingestion.
```

Path safety:

- Hash-based lookup only accepts 64-character hex SHA-256 strings.
- Artifact ref lookup is constrained under:

  ```text
  <BIZBUY_ARTIFACT_DIR or backend/.artifacts>/ocr/
  ```

- The ref must resolve to a `.json` file under that OCR artifact root.

#### 2. Sheet-aware missing-input inference

`infer_missing_document_inputs(...)` no longer relies only on top-level file types.

It now builds an `available_kinds` set from:

- top-level document canonical types
- inferred workbook sheet kinds
- raw text section kind inference
- explicit structured section kind inference

That means a single `profit_and_loss` workbook can also satisfy `balance_sheet` if it has a `Balance Sheet` sheet.

For the PeakAir workbook:

```text
P&L Statement -> profit_and_loss
Balance Sheet -> balance_sheet
SDE Summary   -> sde_summary
```

Expected effect:

- Missing P&L warning disappears.
- Missing balance-sheet warning disappears.
- Missing tax-return warning disappears when a supported tax type is passed from classification or override.
- Optional cash-flow and A/R aging warnings remain if those documents are not present.

## OCR Client Changes

### `backend/app/agents/mistral_ocr_client.py`

Extended the Mistral document annotation taxonomy to include app-level document types:

```py
"customer_list"
"employee_roster"
"insurance_policy"
"equipment_list"
```

This lets Mistral return classifications that are closer to the app's canonical taxonomy rather than forcing those files into `other`.

## Frontend Changes

### `lib/types.ts`

Extended `ClassifiedFileResult` to match the backend response:

```ts
extractedMetadata: {
  businessName: string | null;
  periodStart: string | null;
  periodEnd: string | null;
  currency: string | null;
  sheetKinds?: CanonicalDocumentType[];
};
fileHash?: string | null;
ocrArtifactRef?: string | null;
```

### `lib/api-client.ts`

`parseDocuments(...)` now optionally accepts and sends OCR cache metadata:

```ts
parseDocuments(
  files,
  fileTypes,
  fileHashes = [],
  ocrArtifactRefs = []
)
```

It still always sends:

```ts
fileTypes
```

It now conditionally sends:

```ts
fileHashes
ocrArtifactRefs
```

### `app/analyze/upload/page.tsx`

After classification, `handleContinue` now passes cache metadata into parse:

```ts
parseDocuments(
  files.map((f) => f.file),
  effectiveTypes,
  classifiedFiles.map((cf) => cf.fileHash),
  classifiedFiles.map((cf) => cf.ocrArtifactRef),
)
```

This preserves the link:

```text
classification result -> file hash -> OCR artifact -> parse ingestion
```

## Financial Mapping Details

### Income Statement

The extractor maps these row labels:

```text
Total Revenue                 -> revenue
Total Cost of Revenue          -> cogs
Total COGS                     -> cogs
Cost of Goods Sold             -> cogs
Gross Profit                   -> gross_profit
Total Operating Expenses       -> operating_expenses
Net Income                     -> net_income
Owner Salary & Benefits        -> owner_salary
Depreciation                   -> depreciation_amortization
EBITDA                         -> ebitda
```

It also records:

```text
periods
revenue_by_year
net_income_by_year
```

For PeakAir, the most recent year is detected as `2024`, so the extractor selects `FY 2024` values.

### SDE Summary

The extractor uses the SDE sheet for:

```text
Total SDE                         -> income_statement.sde
Interest Expense on Vehicle Loans -> income_statement.interest_expense
Owner Salary                      -> income_statement.owner_salary, fallback if P&L owner salary is missing
Depreciation & Amortization       -> income_statement.depreciation_amortization, fallback if P&L depreciation is missing
Asking Price (per listing)        -> loan_terms.asking_price
```

Add-backs are extracted from non-zero rows:

```text
One-Time Legal Fees                 -> one_time_expense
Owner Health Insurance              -> personal_expense
Owner Vehicle (personal use)        -> personal_expense
Owner Cell Phone & Personal Expenses -> personal_expense
Owner Retirement Contributions      -> personal_expense
```

In the PeakAir FY 2024 data, `One-Time Legal Fees` is `0`, so it is not added as an add-back for the selected latest year.

### Balance Sheet

The extractor maps:

```text
Total Current Assets          -> current_assets
Cash & Cash Equivalents       -> cash_and_equivalents
Accounts Receivable           -> accounts_receivable
Inventory - Parts & Supplies  -> inventory
Total Current Liabilities     -> current_liabilities
Accounts Payable              -> accounts_payable
TOTAL ASSETS                  -> total_assets
TOTAL LIABILITIES             -> total_liabilities
Total Owner's Equity          -> equity
```

### Cash Flow

The cash-flow mapper exists, but the PeakAir sample does not include a dedicated cash-flow statement.

Supported labels include:

```text
Operating Cash Flow
Net Cash Provided by Operating Activities
Investing Cash Flow
Net Cash Used in Investing Activities
Financing Cash Flow
Net Cash Provided by Financing Activities
Net Cash Flow
Net Change in Cash
Capital Expenditures
Free Cash Flow
```

## OCR Cache Details

### Artifact Location

OCR artifacts are stored under:

```text
<BIZBUY_ARTIFACT_DIR or backend/.artifacts>/ocr/<sha256>.json
```

### Stored Shape

The implementation stores the existing `IngestionResult` model as JSON. This includes:

```json
{
  "filename": "...",
  "file_hash": "...",
  "page_count": 1,
  "classification": {
    "document_type": "...",
    "confidence": 0.9,
    "reasoning": "...",
    "detected_period": "..."
  },
  "pages": [
    {
      "page_number": 1,
      "markdown": "...",
      "image_refs": []
    }
  ],
  "full_markdown": "...",
  "ocr_model": "mistral-ocr-2512",
  "processing_time_ms": 12,
  "cost_usd": 0.002
}
```

The shape is snake_case because it is produced by the backend Pydantic model. The parse-time reader accepts both `full_markdown` and `fullMarkdown`.

### Cache Lookup Behavior

Classification:

```text
uploaded file bytes -> SHA-256 -> OCR artifact path
```

If present, the route returns the cached classification and prepends:

```text
Cached OCR result.
```

to the rationale.

If absent, the route calls Mistral OCR, saves the artifact, and returns the OCR ref.

Parsing:

```text
fileHash / ocrArtifactRef -> OCR artifact -> full markdown -> raw_text
```

PDFs prefer cached OCR text. Other files use cached OCR text only if structured/text extraction did not already produce raw text.

## Tests Added Or Updated

### `backend/tests/test_parse_documents_route.py`

Added multipart regression coverage:

```py
test_parse_documents_route_accepts_frontend_filetypes_alias_multipart
```

This posts `fileTypes`, not `file_types`, through the real FastAPI route and asserts the pipeline document is typed as `profit_and_loss`.

Added workbook inference coverage:

```py
test_peakair_workbook_sheet_kind_inference
```

It reads `sample company1/PeakAir_Financials.xlsx` and asserts:

```py
[
    "profit_and_loss",
    "balance_sheet",
    "sde_summary",
]
```

Added cached OCR parse coverage:

```py
test_parse_documents_reuses_cached_ocr_text_by_file_hash
```

It creates a fake OCR artifact, posts a PDF plus `fileHashes` and `ocrArtifactRefs`, then verifies the pipeline section raw text comes from cached OCR markdown.

Added PeakAir integration-style parse coverage:

```py
test_peakair_parse_documents_seeds_review_financial_data
```

It posts all five `sample company1` files through `/api/parse-documents` with frontend-style `fileTypes`.

It asserts:

```text
P&L missing warning is absent
Balance sheet missing warning is absent
Tax return missing warning is absent
incomeStatement.revenue == 983000
incomeStatement.netIncome == 102904
incomeStatement.cogs == 520990
incomeStatement.sde == 346045
incomeStatement.interestExpense == 5880
balanceSheet.totalAssets == 313300
balanceSheet.totalLiabilities == 174000
balanceSheet.currentAssets == 173500
balanceSheet.accountsReceivable == 98000
loanTerms.askingPrice == 1150000
```

### `backend/tests/test_ingest_documents_route.py`

Updated tests to avoid temp directory permission issues in this Windows sandbox by writing route test files under `backend/.test-artifacts/ingest-documents-route/...`.

Added OCR cache coverage:

```py
test_ocr_result_is_cached_by_file_hash
```

It verifies:

- First classification calls OCR.
- Second classification of identical bytes uses the cached artifact.
- Both classifications return `profit_and_loss`.
- The second rationale starts with `Cached OCR result.`
- Both responses share the same `ocrArtifactRef`.

Existing structured fallback tests now also verify:

- `file_hash` is returned.
- `ocr_artifact_ref` is returned when OCR succeeds.

## Verification

Backend verification command:

```powershell
python -m pytest --cache-clear -q
```

Result:

```text
56 passed
```

Warnings observed:

- Existing Pydantic deprecation warnings for class-based `Config` in `ingest_documents.py`.
- Pytest cache warning because this sandbox cannot create some `.pytest_cache` files.

Frontend verification:

```powershell
npm run lint
```

Could not be run in this shell because `npm` is not available on PATH.

## Behavior Before And After

### Before

Browser upload flow:

```text
Classification UI displays detected labels.
User clicks Continue.
Frontend sends fileTypes.
Backend expects file_types.
Backend receives no types.
All files normalize to other.
Missing-document inference thinks P&L, balance sheet, and tax returns are absent.
document_parser returns income_statement=None and balance_sheet=None.
Review page initializes empty fields.
```

### After

Browser upload flow:

```text
Classification UI displays detected labels.
User clicks Continue.
Frontend sends fileTypes, fileHashes, and ocrArtifactRefs.
Backend accepts fileTypes.
Intake preserves declared/canonical document labels.
Missing-document inference uses both top-level types and inferred section kinds.
Financial extractor maps P&L, balance sheet, SDE, and asking-price rows.
document_parser returns populated FinancialData.
Review page initializes with extracted numeric values.
```

OCR flow:

```text
Classification computes SHA-256.
If OCR artifact exists, reuse it.
If not, call OCR and persist artifact.
Return fileHash and ocrArtifactRef.
Parse receives hash/ref.
Parse can seed raw text from cached OCR markdown.
```

## Deliberate Scope Boundaries

### True section-level document typing was not implemented

The stored `DocumentSection.document_type` still inherits the parent document canonical type.

For example, a `PeakAir_Financials.xlsx` file classified as `profit_and_loss` still persists all three sheet sections with `document_type=profit_and_loss`.

This implementation intentionally uses local, lightweight `section_kind` inference for extraction and completeness checks instead of changing the persisted schema.

Future work should add true section-level typing if downstream agents need to filter sections by persisted type.

### Deal info suggestions were only partially addressed

Asking price is now populated through:

```text
FinancialData.loan_terms.asking_price
```

The review page already initializes asking price from `state.financialData?.loanTerms?.askingPrice`.

This implementation did not add a separate `suggestedDealInfo` response field.

Still deferred:

- business type extraction
- industry extraction
- location extraction
- years in operation extraction
- reason for sale extraction

### OCR artifact graph is lightweight

OCR caching now exists and parse can reuse OCR markdown, but there is not yet a full artifact graph tying:

```text
uploaded file -> OCR artifact -> ingestion sections -> normalized metrics -> review state
```

The current implementation is compatible with that future direction but does not redesign artifact ownership or introduce a broader artifact registry.

### Frontend tests were not added

Backend tests cover the browser-facing multipart contract and parse response behavior.

No frontend test harness was added in this pass.

## Remaining Recommended Follow-Ups

1. Add true section-level canonical typing.

   Persist inferred section kind on each section, or introduce a new field such as `inferred_section_type`, then update downstream agents to use it.

2. Add `suggestedDealInfo`.

   Extract and return deal metadata such as business type, location, industry, years in operation, and reason for sale.

3. Add frontend tests.

   Suggested coverage:

   - Upload page passes `fileTypes`, `fileHashes`, and `ocrArtifactRefs`.
   - Review page initializes numeric fields from populated `FinancialData`.
   - User overrides preserve order relative to uploaded files.

4. Add OCR artifact cleanup/retention policy.

   The cache is content-addressed by hash and can grow indefinitely.

5. Convert `ingest_documents.py` response models to Pydantic v2 `ConfigDict`.

   This would remove the current class-based `Config` deprecation warnings.

6. Add richer row-mapping synonyms.

   The financial mapper handles the PeakAir sample and common labels, but more seller-provided workbook variants will need additional aliases.

7. Run frontend lint/type checks when Node/npm is available.

   Backend tests pass, but TypeScript linting could not be executed in the current shell.

## Current Git Notes

The implementation intentionally leaves pre-existing untracked artifact directories alone. They existed outside the code changes and were not removed as part of this work.

Primary code changes are in:

```text
app/analyze/upload/page.tsx
backend/app/agents/mistral_ocr_client.py
backend/app/api/routes/ingest_documents.py
backend/app/api/routes/parse_documents.py
backend/app/services/document_parser.py
backend/app/services/intake_service.py
backend/app/services/section_kind.py
backend/app/services/financial_data_extractor.py
lib/api-client.ts
lib/types.ts
```

Primary test changes are in:

```text
backend/tests/test_ingest_documents_route.py
backend/tests/test_parse_documents_route.py
```
