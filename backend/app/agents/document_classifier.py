from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

import anthropic
from pydantic import ValidationError

from app.agents.schemas import DocumentType

CLASSIFIER_MODEL = "claude-sonnet-4-6"
MAX_RETRIES = 1
MAX_TEXT_PREVIEW_CHARS = 8000
MAX_CSV_ROWS = 30

DOCUMENT_CLASSIFIER_PROMPT = """
You are a document classification engine for BizBuy, an AI-powered small business acquisition
due diligence tool. Your job is to look at a single uploaded file and determine what type of
business document it is.

Allowed detectedType values (use exactly one):

- profit_and_loss: Income statement, P&L, statement of operations, earnings summary
- balance_sheet: Statement of financial position, assets and liabilities summary
- cash_flow_statement: Statement of cash flows, cash receipts and disbursements
- tax_return_1120s: IRS Form 1120-S (S-Corporation tax return)
- tax_return_1040: IRS Form 1040 (individual return with business schedules)
- tax_return_schedule_c: IRS Schedule C (sole proprietor profit or loss)
- ar_aging_report: Accounts receivable aging, outstanding invoices by age bucket
- customer_list: Customer roster, revenue by customer, client list
- contract: Customer or vendor contract, service agreement, purchase order
- lease_agreement: Commercial lease, rental agreement, sublease
- employee_roster: Employee list, payroll register, org chart
- insurance_policy: Business insurance declaration, certificate of insurance
- equipment_list: Fixed asset register, equipment inventory, depreciation schedule
- other: Business document that does not fit the categories above
- unknown: Cannot determine the document type from the content provided

Rules:
- Return ONLY a JSON object matching the schema. No prose, no markdown fences, no explanation outside the JSON.
- Use "unknown" when you genuinely cannot tell. Do not guess.
- Keep confidence honest: 0.9+ only when the document clearly and unambiguously matches a type.
- suggestedAlternatives: list up to 3 other types that could plausibly apply, in descending likelihood.
- extractedMetadata: pull these fields if clearly visible in the document; use null if not found.
""".strip()

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "detectedType": {
            "type": "string",
            "enum": [
                "profit_and_loss", "balance_sheet", "cash_flow_statement",
                "tax_return_1120s", "tax_return_1040", "tax_return_schedule_c",
                "ar_aging_report", "customer_list", "contract", "lease_agreement",
                "employee_roster", "insurance_policy", "equipment_list",
                "other", "unknown",
            ],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string", "maxLength": 400},
        "suggestedAlternatives": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "extractedMetadata": {
            "type": "object",
            "properties": {
                "businessName": {"type": ["string", "null"]},
                "periodStart": {"type": ["string", "null"]},
                "periodEnd": {"type": ["string", "null"]},
                "currency": {"type": ["string", "null"]},
            },
            "required": ["businessName", "periodStart", "periodEnd", "currency"],
        },
    },
    "required": ["detectedType", "confidence", "rationale", "suggestedAlternatives", "extractedMetadata"],
}

TOOL_NAME = "classify_document"


from pydantic import BaseModel, Field
from typing import List, Optional


class ExtractedMetadata(BaseModel):
    business_name: Optional[str] = Field(None, alias="businessName")
    period_start: Optional[str] = Field(None, alias="periodStart")
    period_end: Optional[str] = Field(None, alias="periodEnd")
    currency: Optional[str] = None

    class Config:
        populate_by_name = True


class DocumentClassification(BaseModel):
    detected_type: str = Field(..., alias="detectedType")
    confidence: float = Field(..., ge=0, le=1)
    rationale: str = Field(..., max_length=400)
    suggested_alternatives: List[str] = Field(default_factory=list, alias="suggestedAlternatives")
    extracted_metadata: ExtractedMetadata = Field(..., alias="extractedMetadata")

    class Config:
        populate_by_name = True


def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return anthropic.Anthropic(api_key=api_key)


def _build_content_blocks(
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
) -> list[dict[str, Any]]:
    suffix = Path(file_name).suffix.lower()

    if mime_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        media_type = mime_type if mime_type.startswith("image/") else f"image/{suffix.lstrip('.')}"
        if media_type == "image/jpg":
            media_type = "image/jpeg"
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(file_bytes).decode("ascii"),
                },
            },
            {"type": "text", "text": f"Classify this image of a business document. Filename: {file_name}"},
        ]

    if mime_type == "application/pdf" or suffix == ".pdf":
        return [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.b64encode(file_bytes).decode("ascii"),
                },
            },
            {"type": "text", "text": f"Classify this PDF business document. Filename: {file_name}"},
        ]

    if suffix in {".csv", ".txt"} or mime_type.startswith("text/"):
        text = _decode_text(file_bytes)
        preview = _text_preview(text, file_name)
        return [{"type": "text", "text": preview}]

    if suffix == ".xlsx" or "spreadsheet" in mime_type:
        from app.services.intake_service import _extract_xlsx_workbook
        sheets, _ = _extract_xlsx_workbook(file_bytes)
        preview = _spreadsheet_preview(sheets, file_name)
        return [{"type": "text", "text": preview}]

    text = _decode_text(file_bytes)
    preview = _text_preview(text, file_name)
    return [{"type": "text", "text": preview}]


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="ignore")


def _text_preview(text: str, file_name: str) -> str:
    lines = text.splitlines()
    header_lines = lines[:MAX_CSV_ROWS + 1]
    preview = "\n".join(header_lines)
    if len(preview) > MAX_TEXT_PREVIEW_CHARS:
        preview = preview[:MAX_TEXT_PREVIEW_CHARS] + "\n... (truncated)"
    return f"Classify this text document. Filename: {file_name}\n\n---\n{preview}"


def _spreadsheet_preview(sheets: list[dict[str, Any]], file_name: str) -> str:
    parts = [f"Classify this spreadsheet. Filename: {file_name}\n"]
    for sheet in sheets[:3]:
        parts.append(f"\n## Sheet: {sheet.get('name', 'Unnamed')}")
        rows = sheet.get("rows", [])
        for row in rows[:MAX_CSV_ROWS]:
            values = [str(v) for k, v in row.items() if k != "row_index" and v not in {None, ""}]
            if values:
                parts.append(" | ".join(values))
    result = "\n".join(parts)
    if len(result) > MAX_TEXT_PREVIEW_CHARS:
        result = result[:MAX_TEXT_PREVIEW_CHARS] + "\n... (truncated)"
    return result


def _guess_mime(file_name: str) -> str:
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed or "application/octet-stream"


def classify_single_file(
    file_bytes: bytes,
    file_name: str,
    mime_type: str | None = None,
) -> DocumentClassification:
    effective_mime = mime_type or _guess_mime(file_name)
    content_blocks = _build_content_blocks(file_bytes, file_name, effective_mime)
    client = _get_client()

    tool = {
        "name": TOOL_NAME,
        "description": "Submit the document classification result.",
        "input_schema": CLASSIFICATION_SCHEMA,
    }

    last_output: str | None = None
    last_errors: str | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            messages: list[dict[str, Any]] = [{"role": "user", "content": content_blocks}]

            if attempt > 0 and last_errors:
                messages.append({
                    "role": "user",
                    "content": (
                        f"Your previous classification was invalid. Validation errors:\n{last_errors}\n\n"
                        f"Previous output:\n{last_output}\n\nPlease fix and try again."
                    ),
                })

            response = client.messages.create(
                model=CLASSIFIER_MODEL,
                max_tokens=1024,
                temperature=0.0,
                system=DOCUMENT_CLASSIFIER_PROMPT,
                tools=[tool],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=messages,
            )

            tool_block = next(
                (block for block in response.content if block.type == "tool_use" and block.name == TOOL_NAME),
                None,
            )
            if not tool_block:
                last_output = "No tool_use block"
                last_errors = "Model did not return a tool_use block."
                continue

            last_output = json.dumps(tool_block.input, indent=2)
            classification = DocumentClassification(**tool_block.input)
            return classification

        except ValidationError as exc:
            last_errors = str(exc)
            continue
        except Exception as exc:
            if attempt < MAX_RETRIES:
                continue
            raise

    return DocumentClassification(
        detectedType="unknown",
        confidence=0.0,
        rationale="Classification failed after retries.",
        suggestedAlternatives=[],
        extractedMetadata=ExtractedMetadata(
            businessName=None, periodStart=None, periodEnd=None, currency=None,
        ),
    )


def detected_type_to_document_type(detected_type: str) -> DocumentType:
    mapping: dict[str, DocumentType] = {
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
        "other": DocumentType.OTHER,
        "unknown": DocumentType.OTHER,
    }
    return mapping.get(detected_type, DocumentType.OTHER)
