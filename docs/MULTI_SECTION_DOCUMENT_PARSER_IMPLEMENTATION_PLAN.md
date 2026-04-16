# Multi-Section Document Parser Implementation Plan

This plan is the handoff for implementing true section-aware parsing with the smallest practical change set.

Audience: a GPT-5.4 high-reasoning Codex agent with a large context budget.

Read these two documents first:

- `docs/OCR_INGESTION_REVIEW_PLAN.md`
- `docs/OCR_INGESTION_REVIEW_IMPLEMENTATION_REPORT.md`

The prior work already fixed classification handoff, OCR artifact caching, lightweight section-kind inference, missing-input inference, and review-page financial seeding. The remaining product gap is that multi-section uploaded documents are not first-class enough for the agent pipeline. A workbook can contain P&L, balance sheet, SDE, customer list, and equipment sections, but downstream agents still often filter by parent document type.

## Goal

Make each meaningful section of an uploaded document carry a durable section identity, while the user still sees the uploaded files exactly as files.

In practical terms:

- Keep one `DocumentInfo` per uploaded file.
- Keep the file-level `DocumentInfo.document_type` as the primary classification shown to the user.
- Add/persist section-level identity on each `DocumentSection`.
- Use section-level identity when agents select, summarize, compute metrics, and build evidence.
- Preserve section-level identity through the frontend `pipelineDocuments` round trip.
- Keep implementation simple and unintrusive. Do not redesign the whole artifact graph, upload UI, or analysis pipeline.

## Core Design

File type is a fallback. Section type is authoritative for analysis.

Example:

```json
{
  "file_name": "PeakAir_Financials.xlsx",
  "document_type": "profit_and_loss",
  "sections": [
    {
      "section_name": "P&L Statement",
      "document_type": "profit_and_loss",
      "section_kind": "profit_and_loss"
    },
    {
      "section_name": "Balance Sheet",
      "document_type": "balance_sheet",
      "section_kind": "balance_sheet"
    },
    {
      "section_name": "SDE Summary",
      "document_type": "profit_and_loss",
      "section_kind": "sde_summary"
    }
  ]
}
```

The user still sees one uploaded file: `PeakAir_Financials.xlsx`. Internally, agents receive the sections matching their specialty.

## Non-Goals

Do not:

- Split one uploaded file into multiple top-level `DocumentInfo` objects.
- Change the upload UI so users must classify every sheet/page manually.
- Introduce a new database or artifact registry.
- Replace OCR or workbook parsing.
- Rewrite all agent prompts.
- Make a large frontend redesign.
- Remove existing review-page `FinancialData` extraction.

This should be a targeted section-typing pass.

## Current Code Facts

Important files:

- `backend/app/agents/schemas.py`
  - Defines `DocumentType`, `DocumentSection`, `DocumentInfo`, `IngestionOutput`, evidence models, pipeline input.
- `backend/app/services/section_kind.py`
  - Already infers lightweight section kinds such as `profit_and_loss`, `balance_sheet`, `sde_summary`, `customer_list`, `equipment_list`, and `lease_agreement`.
- `backend/app/services/intake_service.py`
  - Normalizes upload files into `IntakeDocument`.
  - Parses XLSX into `document.sheets`.
  - Reuses OCR artifact markdown for PDFs and low-text uploads.
  - Infers missing documents using `infer_section_kind`.
- `backend/app/services/ingestion_service.py`
  - Converts `IntakeDocument` into `DocumentInfo` and `DocumentSection`.
  - Current issue: `_normalize_section`, `_sheet_section`, `_rows_section`, and `_text_section` assign `section.document_type = document.canonical_type`.
- `backend/app/services/financial_data_extractor.py`
  - Already uses `infer_section_kind(...)` to seed the review page.
  - This should continue working, but can be simplified or hardened after sections persist their own kind.
- `backend/app/agents/runners.py`
  - Agent prompt payloads select evidence by document type through helper functions like `_relevant_sections`, `_raw_data_summary`, `_raw_text_summary`, and `_make_evidence_references`.
- `backend/app/agents/deterministic.py`
  - Deterministic metrics still check `section.document_type.value` or `doc.document_type.value`.
- `lib/types.ts`
  - Frontend type for `PipelineDocumentPayload` does not currently include `section_kind`.
- `lib/api-client.ts`
  - Sends `pipelineDocuments` back to `/pipeline` and `/analyses`.

Critical round trip:

1. `/api/parse-documents` returns `pipelineDocuments`.
2. Frontend stores them.
3. Frontend posts the same `pipelineDocuments` to `/api/pipeline` or `/api/analyses`.
4. `run_document_ingestion` calls `ingest_and_persist_document_payloads`.
5. `normalize_document_payload` and `_normalize_section` rebuild sections.
6. Current bug: section identity can be lost because `_normalize_section` resets the section type to the parent canonical type.

## Desired Data Contract

Add a new optional field to `DocumentSection`:

```py
section_kind: Optional[str] = None
```

Reason for string instead of enum:

- Most section kinds are canonical `DocumentType` values.
- `sde_summary` is not a `DocumentType`.
- This avoids adding fake document types just to route analysis.

Keep `document_type: DocumentType` on `DocumentSection`, but set it to the best canonical section type whenever possible.

Mapping:

| Inferred section kind | Section `document_type` |
| --- | --- |
| `profit_and_loss` | `DocumentType.PROFIT_AND_LOSS` |
| `balance_sheet` | `DocumentType.BALANCE_SHEET` |
| `cash_flow_statement` | `DocumentType.CASH_FLOW_STATEMENT` |
| `tax_return_1120s` | `DocumentType.TAX_RETURN_1120S` |
| `tax_return_1040` | `DocumentType.TAX_RETURN_1040` |
| `tax_return_schedule_c` | `DocumentType.TAX_RETURN_SCHEDULE_C` |
| `ar_aging_report` | `DocumentType.AR_AGING_REPORT` |
| `customer_list` | `DocumentType.CUSTOMER_LIST` |
| `contract` | `DocumentType.CONTRACT` |
| `lease_agreement` | `DocumentType.LEASE_AGREEMENT` |
| `employee_roster` | `DocumentType.EMPLOYEE_ROSTER` |
| `insurance_policy` | `DocumentType.INSURANCE_POLICY` |
| `equipment_list` | `DocumentType.EQUIPMENT_LIST` |
| `sde_summary` | parent type if financial, otherwise `DocumentType.PROFIT_AND_LOSS` |
| `other` | parent document type |

For `sde_summary`, prefer `DocumentType.PROFIT_AND_LOSS` because it belongs in financial/SDE analysis and should be visible to the financial agent.

## Implementation Phases

### Phase 1: Add Section Identity To Schema

File: `backend/app/agents/schemas.py`

Change `DocumentSection`:

```py
class DocumentSection(BaseModel):
    ...
    section_kind: Optional[str] = None
```

No migration is needed because this is a Pydantic artifact shape with an optional field.

Also update frontend type:

File: `lib/types.ts`

Inside `PipelineDocumentPayload.sections[]`, add:

```ts
section_kind?: string | null;
```

If the frontend receives camelCase by alias in some code path, optionally accept:

```ts
sectionKind?: string | null;
```

However, the current parse response uses `model_dump(mode="json")`, not `by_alias=True`, so snake case is the important field.

### Phase 2: Centralize Effective Section Typing

Create or extend a small helper. Preferred minimal path: extend `backend/app/services/section_kind.py`.

Add functions:

```py
def normalize_section_kind(value: Any) -> str:
    ...

def document_type_for_section_kind(
    section_kind: str,
    *,
    fallback: DocumentType,
) -> DocumentType:
    ...

def infer_effective_section_identity(
    *,
    parent_document_type: DocumentType,
    explicit_section_kind: str | None = None,
    explicit_document_type: DocumentType | str | None = None,
    section_name: str | None = None,
    raw_text: str | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> tuple[DocumentType, str]:
    ...
```

Suggested behavior:

1. If `explicit_section_kind` is present and non-empty, normalize and trust it.
2. Else infer using `infer_section_kind(...)`.
3. If inference returns `other` but `explicit_document_type` is a real type, use that as kind.
4. If still `other`, use the parent document type as the section `document_type`, and `other` as `section_kind`.
5. Map recognized kinds to a canonical section `document_type` with `document_type_for_section_kind`.

Keep this helper pure and easy to test.

### Phase 3: Assign Section Type In Ingestion

File: `backend/app/services/ingestion_service.py`

Update:

- `_normalize_section`
- `_sheet_section`
- `_rows_section`
- `_text_section`

Each should compute:

```py
section_document_type, section_kind = infer_effective_section_identity(...)
```

Then pass:

```py
document_type=section_document_type,
section_kind=section_kind,
```

Specifics:

#### `_sheet_section`

Use:

- parent type: `document.canonical_type`
- section name: `sheet.get("name")`
- raw text: `sheet.get("text")`
- rows: parsed spreadsheet rows
- explicit kind: `sheet.get("section_kind")` or `sheet.get("sectionKind")`
- explicit document type: `sheet.get("document_type")` or `sheet.get("documentType")`

Expected PeakAir result:

- `P&L Statement`: `document_type=profit_and_loss`, `section_kind=profit_and_loss`
- `Balance Sheet`: `document_type=balance_sheet`, `section_kind=balance_sheet`
- `SDE Summary`: `document_type=profit_and_loss`, `section_kind=sde_summary`

#### `_normalize_section`

This is the most important round-trip fix.

Currently it ignores incoming section type. Change it so an already-parsed section sent from the frontend keeps its identity.

Read incoming values:

```py
explicit_section_kind = section.get("section_kind") or section.get("sectionKind")
explicit_document_type = section.get("document_type") or section.get("documentType")
```

Then infer effective identity using explicit values plus section name/raw text/rows.

This preserves section identity when:

```text
/parse-documents -> frontend pipelineDocuments -> /pipeline -> run_document_ingestion
```

#### `_rows_section`

Rows-only uploads should infer from row labels:

```py
rows=document.spreadsheet_rows
```

#### `_text_section`

For now, infer from the whole raw text:

```py
raw_text=document.raw_text
```

Do not implement complex text splitting here unless tests prove it is needed. The unintrusive path is to type the single section better first.

### Phase 4: Optional Text Section Splitting, Only If Small

This phase is optional and should be implemented only if it stays simple.

File: `backend/app/services/intake_service.py` or a new `backend/app/services/text_section_splitter.py`.

Purpose: split OCR/DOCX text into multiple sections when headings are obvious.

Simple heuristic:

- Scan lines.
- Treat a line as a heading if it is short, mostly title-like, and matches known section keywords:
  - `profit and loss`
  - `p&l`
  - `income statement`
  - `balance sheet`
  - `cash flow`
  - `schedule c`
  - `tax return`
  - `lease agreement`
  - `customer list`
  - `employee roster`
  - `equipment`
  - `insurance`
  - `seller's discretionary earnings`
  - `sde`
- Build section dictionaries:

```py
{
    "sectionName": heading,
    "rawText": section_text,
    "contentType": "text",
}
```

Guardrails:

- Only split if at least two recognized headings are found.
- Do not split into tiny fragments under about 200 characters unless the heading is strongly recognized.
- Keep original unsplit text if splitting would lose content.
- Add a document note like `"Split OCR/text content into N inferred sections."`

This gives OCR PDFs with multiple statements a path to multiple typed sections. But if it gets messy, skip this phase and ship section typing first.

### Phase 5: Normalize Spreadsheet Sections For Agents

The review page already gets values through `financial_data_extractor.py`, but the agent pipeline metrics rely on `section.extracted_data` directly. For agents to be useful, sections should include normalized keys in addition to raw rows.

Minimal path:

1. Do not remove `rows`.
2. Add normalized fields to `extracted_data` for recognized financial sections during ingestion or immediately after ingestion.
3. Reuse existing logic from `financial_data_extractor.py` where practical.

Preferred implementation:

Create a small service:

```text
backend/app/services/section_data_normalizer.py
```

Function:

```py
def normalize_section_extracted_data(section: DocumentSection) -> dict[str, Any]:
    ...
```

It should return a merged dict:

```py
{
    **section.extracted_data,
    "revenue": 983000,
    "cogs": 520990,
    ...
}
```

Run this in `ingestion_service._build_sections` after building sections, or inside each section builder before returning.

Keep the first pass narrow:

#### Profit And Loss

Map common aliases:

- `Total Revenue`, `Revenue`, `Gross Revenue` -> `revenue`
- `Total Cost of Revenue`, `Total COGS`, `Cost of Goods Sold` -> `cogs`
- `Gross Profit` -> `gross_profit`
- `Total Operating Expenses`, `Operating Expenses` -> `operating_expenses`
- `Net Income`, `Net Profit` -> `net_income`
- `Owner Salary & Benefits`, `Owner Salary` -> `owner_salary`
- `Depreciation & Amortization`, `Depreciation` -> `depreciation_amortization`
- `Interest Expense` -> `interest_expense`
- `EBITDA` -> `ebitda`

#### SDE Summary

Use `section_kind == "sde_summary"`:

- `Total SDE` -> `sde`
- `Interest Expense on Vehicle Loans`, `Interest Expense` -> `interest_expense`
- `Owner Salary` -> `owner_salary`
- `Depreciation & Amortization` -> `depreciation_amortization`
- `Asking Price (per listing)`, `Asking Price` -> `asking_price`
- Add-backs list if easy, otherwise leave raw rows for the financial agent.

#### Balance Sheet

- `Total Current Assets` -> `current_assets`
- `Cash & Cash Equivalents`, `Cash` -> `cash_and_equivalents`
- `Accounts Receivable` -> `accounts_receivable`
- `Inventory - Parts & Supplies`, `Inventory` -> `inventory`
- `Total Current Liabilities` -> `current_liabilities`
- `Accounts Payable` -> `accounts_payable`
- `TOTAL ASSETS`, `Total Assets` -> `total_assets`
- `TOTAL LIABILITIES`, `Total Liabilities` -> `total_liabilities`
- `Total Owner's Equity`, `Equity` -> `equity`

#### Cash Flow

- `Operating Cash Flow`, `Net Cash Provided by Operating Activities` -> `operating_cash_flow`
- `Investing Cash Flow`, `Net Cash Used in Investing Activities` -> `investing_cash_flow`
- `Financing Cash Flow`, `Net Cash Provided by Financing Activities` -> `financing_cash_flow`
- `Net Cash Flow`, `Net Change in Cash` -> `net_cash_flow`
- `Capital Expenditures`, `CapEx` -> `capital_expenditures`
- `Free Cash Flow` -> `free_cash_flow`

#### Customer List And Equipment List

Do not overbuild. For first pass:

- Preserve `rows`.
- If the section is `customer_list`, optionally add `customers` from rows if columns are recognizable.
- If the section is `equipment_list`, optionally add `equipment` from rows if columns are recognizable.

Important: The existing deterministic customer and ops code already looks for `rows`, so typing these sections correctly may be enough for now.

### Phase 6: Update Agent Section Selection

File: `backend/app/agents/runners.py`

Update helper functions to use effective section type.

Add helper:

```py
def _section_type_value(section: DocumentSection, doc: DocumentInfo | None = None) -> str:
    if section.section_kind and section.section_kind in DocumentType._value2member_map_:
        return section.section_kind
    if section.document_type:
        return section.document_type.value
    if doc:
        return doc.document_type.value
    return DocumentType.OTHER.value
```

For `sde_summary`, decide by caller:

- Financial agent should include it.
- Tax, AR, lease, customer, ops should not include it unless explicitly requested.

Update:

- `_relevant_sections`
- `_raw_data_summary`
- `_raw_text_summary`
- `_make_evidence_references`

Current `_relevant_sections` includes all sections from a matching parent document. Change it to include sections whose effective type or kind matches the requested set.

Suggested:

```py
def _section_matches(section, allowed: set[str]) -> bool:
    if section.document_type.value in allowed:
        return True
    if section.section_kind in allowed:
        return True
    return False
```

Then iterate all documents and all sections.

For `_raw_data_summary`, include section labels:

```text
### PeakAir_Financials.xlsx / Balance Sheet (balance_sheet, kind=balance_sheet)
[FYunknown] {"total_assets": 313300, ...}
```

For `_make_evidence_references`, include the section's extracted fields and snippet as it does now, but select by section type/kind.

Update `run_financial_analysis`:

```py
relevant_doc_types = {"profit_and_loss", "balance_sheet", "cash_flow_statement", "sde_summary"}
```

This lets SDE summary reach the financial agent.

Do not include `sde_summary` in prompts for unrelated agents.

### Phase 7: Update Deterministic Metrics

File: `backend/app/agents/deterministic.py`

Add a local helper:

```py
def section_kind(section: DocumentSection) -> str:
    return getattr(section, "section_kind", None) or section.document_type.value

def section_is(section: DocumentSection, *kinds: str) -> bool:
    effective = section_kind(section)
    return effective in kinds or section.document_type.value in kinds
```

Update checks:

- `compute_financial_metrics`
  - P&L sections: `profit_and_loss`
  - SDE sections: include `sde_summary` for SDE/add-back fields.
  - Balance sections: `balance_sheet`
  - Cash flow sections: `cash_flow_statement`
- `compute_tax_metrics`
  - Financial sections: `profit_and_loss`
  - Tax sections: tax return kinds.
- `compute_ar_metrics`
  - AR sections: `ar_aging_report`
  - Revenue for DSO: `profit_and_loss`
- `compute_customer_metrics`
  - Use section-level `customer_list`, not only parent doc type.
- `compute_ops_metrics`
  - Use section-level `employee_roster`, `equipment_list`, `insurance_policy`.
- `compute_lease_metrics`
  - Use section-level `lease_agreement` and `contract`.
- `infer_business_context`
  - When checking lease, use section-level lease identity.

Important: Some functions currently loop `for doc in ingestion_output.documents` and check `doc.document_type.value`. Change only the places that need section-level matching. Keep unrelated code stable.

### Phase 8: Preserve Artifact And Evidence Shape

File: `backend/app/services/analysis_repository.py`

`build_stored_ingestion_artifacts` uses `section.model_dump(...)` indirectly through `ingestion_output`, so the new optional `section_kind` field should persist automatically.

Evidence references do not need a schema change. They should continue to include:

- `document_id`
- `file_name`
- `section_id`
- `page`
- `snippet`
- `extracted_fields`
- `confidence`

If useful, include `section_kind` in `extracted_fields`:

```py
extracted_fields={**section.extracted_data, "_section_kind": section.section_kind}
```

But this is optional. Avoid changing evidence schema unless necessary.

### Phase 9: Tests

Add targeted tests. Do not rely only on integration output.

#### 1. Schema Round Trip

File: `backend/tests/test_section_kind_ingestion.py` or similar.

Test:

- Build a `DocumentSection` with `section_kind="balance_sheet"`.
- `model_dump(mode="json")` includes `section_kind`.
- `DocumentSection.model_validate(...)` restores it.

#### 2. Workbook Section Typing

Use `sample company1/PeakAir_Financials.xlsx` if available in the repo/test environment. Existing tests already reference it, so follow that pattern.

Assert after `/api/parse-documents`:

- One returned pipeline document for `PeakAir_Financials.xlsx`.
- File-level `document_type` is still `profit_and_loss`.
- Section `P&L Statement` has:
  - `document_type == "profit_and_loss"`
  - `section_kind == "profit_and_loss"`
- Section `Balance Sheet` has:
  - `document_type == "balance_sheet"`
  - `section_kind == "balance_sheet"`
- Section `SDE Summary` has:
  - `section_kind == "sde_summary"`
  - `document_type == "profit_and_loss"` or another documented financial fallback.

#### 3. Frontend Pipeline Round Trip Preservation

Backend-only test is enough.

Construct a payload shaped like the parse response:

```py
{
    "file_name": "Financials.xlsx",
    "document_type": "profit_and_loss",
    "sections": [
        {"section_name": "Balance Sheet", "document_type": "balance_sheet", "section_kind": "balance_sheet", ...}
    ]
}
```

Call `ingest_document_payloads` or `run_document_ingestion`.

Assert the section remains `balance_sheet`, not reset to parent `profit_and_loss`.

This is the most important regression test.

#### 4. Agent Selection Test

Test `_relevant_sections` indirectly through deterministic metrics or directly if acceptable.

Input:

- One document with parent `profit_and_loss`
- Three sections:
  - P&L
  - Balance Sheet
  - SDE Summary

Assert:

- Financial metrics see P&L and balance sheet fields.
- Balance sheet metrics are populated.
- Data years available is not zero.

#### 5. Customer/Equipment Section Test

Input:

- One parent document classified as `customer_list`.
- Sections:
  - `Customer List`, kind `customer_list`
  - `PP&E Schedule`, kind `equipment_list`

Assert:

- `compute_customer_metrics` sees customers from customer section.
- `compute_ops_metrics` sees equipment from equipment section.

This proves one workbook can feed two agents.

#### 6. Existing Parse Integration

Update existing PeakAir parse test to additionally assert section kinds.

Keep all existing assertions:

- P&L missing warning absent.
- Balance sheet missing warning absent.
- Tax return missing warning absent.
- `incomeStatement.revenue == 983000`
- `balanceSheet.totalAssets == 313300`
- `loanTerms.askingPrice == 1150000`

### Phase 10: Verification Commands

Run backend tests:

```powershell
python -m pytest --cache-clear -q
```

If full suite is slow or blocked, at minimum run:

```powershell
python -m pytest -q backend/tests/test_parse_documents_route.py backend/tests/test_agent_deterministic.py backend/tests/test_runner_normalization.py
```

Frontend lint may be unavailable in this Windows shell because `npm` may not be on PATH. If available:

```powershell
npm run lint
```

If unavailable, state that clearly in the final answer.

## Minimal Code Strategy

Prefer this order:

1. Add `section_kind` to schema and TS type.
2. Add helper functions to `section_kind.py`.
3. Update section builders in `ingestion_service.py`.
4. Fix `_normalize_section` round trip.
5. Update runners helper filters.
6. Update deterministic helper filters.
7. Add narrow tests.
8. Only then consider text splitting or broader normalization.

Do not start with text splitting. The highest-value fix is preserving and using section identity.

## Suggested Helper Implementation Details

In `section_kind.py`, keep known values centralized:

```py
SECTION_KIND_TO_DOCUMENT_TYPE = {
    "profit_and_loss": DocumentType.PROFIT_AND_LOSS,
    "balance_sheet": DocumentType.BALANCE_SHEET,
    "cash_flow_statement": DocumentType.CASH_FLOW_STATEMENT,
    "tax_return_1120s": DocumentType.TAX_RETURN_1120S,
    "tax_return_1040": DocumentType.TAX_RETURN_1040,
    "tax_return_schedule_c": DocumentType.TAX_RETURN_SCHEDULE_C,
    "ar_aging_report": DocumentType.AR_AGING_REPORT,
    "customer_list": DocumentType.CUSTOMER_LIST,
    "contract": DocumentType.CONTRACT,
    "lease_agreement": DocumentType.LEASE_AGREEMENT,
    "employee_roster": DocumentType.EMPLOYEE_ROSTER,
    "insurance_policy": DocumentType.INSURANCE_POLICY,
    "equipment_list": DocumentType.EQUIPMENT_LIST,
    "sde_summary": DocumentType.PROFIT_AND_LOSS,
}
```

Use `normalize_document_type(...)` from `intake_service.py` only if it does not introduce a circular import. If circular, do not import it. Keep a tiny local normalizer in `section_kind.py`.

Avoid import cycles:

- `intake_service.py` imports `section_kind.py`.
- Therefore `section_kind.py` should not import `intake_service.py`.

## Prompt Payload Expectations

Agents should continue to analyze only their specialty areas. The user should not see internal section routing.

Financial agent should receive:

- P&L sections.
- Balance sheet sections.
- Cash flow sections.
- SDE summary sections.

Tax agent should receive:

- Tax return sections.
- P&L sections for revenue reconciliation.

AR agent should receive:

- AR aging sections.
- P&L sections for DSO revenue support.

Customer concentration agent should receive:

- Customer list sections.
- Contract sections if present.

Operations agent should receive:

- Employee roster sections.
- Equipment list sections.
- Insurance policy sections.
- License-like extracted data.

Lease and contract agent should receive:

- Lease agreement sections.
- Contract sections.

Market agent may receive broad document context, unchanged.

Lending agent does not need direct raw document selection. It uses financial analysis plus asking price.

## Example Agent Raw Data Summary

Target summary format:

```text
### PeakAir_Financials.xlsx / P&L Statement (profit_and_loss, kind=profit_and_loss)
[FYunknown] {"revenue": 983000, "cogs": 520990, "net_income": 102904, "rows": [...]}

### PeakAir_Financials.xlsx / Balance Sheet (balance_sheet, kind=balance_sheet)
[FYunknown] {"total_assets": 313300, "total_liabilities": 174000, "current_assets": 173500, "rows": [...]}

### PeakAir_Financials.xlsx / SDE Summary (profit_and_loss, kind=sde_summary)
[FYunknown] {"sde": 346045, "interest_expense": 5880, "asking_price": 1150000, "rows": [...]}
```

This is enough for agents to understand exactly why the section is in their prompt.

## Failure Modes To Avoid

- Losing `section_kind` after `pipelineDocuments` are posted back to `/pipeline`.
- Including every section from a parent P&L document in financial analysis even when a section is actually customer/equipment data.
- Excluding balance sheet data because the parent workbook is classified as P&L.
- Treating `sde_summary` as `other` and hiding it from financial/lending analysis.
- Removing raw `rows` while adding normalized keys.
- Breaking old payloads that do not have `section_kind`.
- Adding non-optional schema fields that invalidate stored artifacts.

## Backward Compatibility

Old artifacts and old frontend payloads will not have `section_kind`.

Required behavior:

- If `section_kind` is missing, infer it from section name/text/rows.
- If inference is weak, fall back to existing section/document type behavior.
- Do not make missing `section_kind` an error.

## Acceptance Criteria

The implementation is complete when:

1. `/api/parse-documents` returns one pipeline document per uploaded file.
2. Multi-section workbook sections have independent `section_kind`.
3. Recognized sections have appropriate `section.document_type`.
4. Frontend `pipelineDocuments` can carry `section_kind`.
5. Re-posting `pipelineDocuments` to `/pipeline` preserves section identity.
6. Financial agent receives P&L, balance sheet, cash flow, and SDE sections even if they came from one workbook.
7. Customer and operations agents can receive different sections from the same workbook.
8. Existing review-page financial extraction still works.
9. Existing tests pass.
10. New tests cover section typing and round-trip preservation.

## Final Notes For The Implementing Agent

Be conservative. This is a routing and preservation fix, not a new ingestion platform.

The smallest successful patch likely touches:

- `backend/app/agents/schemas.py`
- `backend/app/services/section_kind.py`
- `backend/app/services/ingestion_service.py`
- `backend/app/agents/runners.py`
- `backend/app/agents/deterministic.py`
- `lib/types.ts`
- `backend/tests/...`

Only add `section_data_normalizer.py` or text splitting if doing so keeps the patch clearer than adding logic inline.

When in doubt, preserve raw data and add metadata rather than replacing existing behavior.
