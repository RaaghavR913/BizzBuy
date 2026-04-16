from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile

from app.agents.schemas import DocumentType, MissingInput


LEGACY_DOCUMENT_TYPE_ALIASES: dict[str, DocumentType] = {
    "income_statement": DocumentType.PROFIT_AND_LOSS,
    "profit_and_loss_statement": DocumentType.PROFIT_AND_LOSS,
    "pnl": DocumentType.PROFIT_AND_LOSS,
    "balance_sheet": DocumentType.BALANCE_SHEET,
    "cash_flow": DocumentType.CASH_FLOW_STATEMENT,
    "cash_flow_statement": DocumentType.CASH_FLOW_STATEMENT,
    "loan_terms": DocumentType.OTHER,
    "tax_return": DocumentType.TAX_RETURN_1120S,
    "tax_returns": DocumentType.TAX_RETURN_1120S,
}


@dataclass(slots=True)
class IntakeDocument:
    document_id: str
    file_name: str
    mime_type: str
    declared_type: DocumentType | None
    canonical_type: DocumentType
    size_bytes: int | None = None
    raw_text: str | None = None
    sections: list[dict[str, Any]] = field(default_factory=list)
    spreadsheet_rows: list[dict[str, Any]] = field(default_factory=list)
    sheets: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def normalize_document_type(value: Any) -> DocumentType:
    if isinstance(value, DocumentType):
        return value
    if value is None:
        return DocumentType.OTHER

    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return LEGACY_DOCUMENT_TYPE_ALIASES.get(normalized, DocumentType(normalized) if normalized in DocumentType._value2member_map_ else DocumentType.OTHER)


def _guess_mime_type(file_name: str | None) -> str:
    guessed, _ = mimetypes.guess_type(file_name or "")
    return guessed or "application/octet-stream"


def decode_text_content(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="ignore")


def _extract_docx_text(content: bytes) -> str:
    try:
        with ZipFile(BytesIO(content)) as archive:
            xml_content = archive.read("word/document.xml")
    except (BadZipFile, KeyError):
        return ""

    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError:
        return ""

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        runs = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text = "".join(runs).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_docx_text(content: bytes) -> str:
    """Parse DOCX bytes into newline-delimited text paragraphs."""
    return _extract_docx_text(content)


def extract_xlsx_workbook(content: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        with ZipFile(BytesIO(content)) as archive:
            shared_strings = _read_xlsx_shared_strings(archive)
            workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            workbook_rels = _read_xlsx_relationships(archive)
            namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

            sheets: list[dict[str, Any]] = []
            notes: list[str] = []
            for index, sheet in enumerate(workbook_root.findall(".//x:sheets/x:sheet", namespace)):
                relation_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                target = workbook_rels.get(relation_id or "", "")
                if not target:
                    notes.append(f"Skipped workbook sheet {sheet.attrib.get('name') or index + 1}: missing worksheet relationship.")
                    continue

                worksheet_path = f"xl/{target}" if not target.startswith("xl/") else target
                try:
                    worksheet_root = ElementTree.fromstring(archive.read(worksheet_path))
                except (KeyError, ElementTree.ParseError):
                    notes.append(f"Skipped workbook sheet {sheet.attrib.get('name') or index + 1}: worksheet XML could not be parsed.")
                    continue

                rows = _read_xlsx_rows(worksheet_root, shared_strings)
                sheet_text = "\n".join(
                    " | ".join(str(value) for value in row.values() if value not in {None, ""})
                    for row in rows
                    if any(value not in {None, ""} for value in row.values())
                )
                sheets.append(
                    {
                        "name": sheet.attrib.get("name") or f"Sheet {index + 1}",
                        "rows": rows,
                        "text": sheet_text,
                        "confidence": 0.8 if rows else 0.45,
                    }
                )
            return sheets, notes
    except (BadZipFile, KeyError, ElementTree.ParseError):
        return [], ["XLSX upload could not be parsed into workbook sheets."]


def _read_xlsx_shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except (KeyError, ElementTree.ParseError):
        return []

    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: list[str] = []
    for string_item in root.findall(".//x:si", namespace):
        text_parts = [node.text or "" for node in string_item.findall(".//x:t", namespace)]
        values.append("".join(text_parts))
    return values


def _read_xlsx_relationships(archive: ZipFile) -> dict[str, str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except (KeyError, ElementTree.ParseError):
        return {}

    relationships: dict[str, str] = {}
    for rel in root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            relationships[rel_id] = target
    return relationships


def _read_xlsx_rows(root: ElementTree.Element, shared_strings: list[str]) -> list[dict[str, Any]]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    parsed_rows: list[dict[str, Any]] = []

    for row_index, row in enumerate(root.findall(".//x:sheetData/x:row", namespace), start=1):
        parsed_row: dict[str, Any] = {"row_index": row_index}
        for cell in row.findall("x:c", namespace):
            cell_ref = cell.attrib.get("r", "")
            column_key = "".join(char for char in cell_ref if char.isalpha()) or f"col_{len(parsed_row)}"
            parsed_row[column_key] = _read_xlsx_cell_value(cell, shared_strings, namespace)
        parsed_rows.append(parsed_row)
    return parsed_rows


def _read_xlsx_cell_value(
    cell: ElementTree.Element,
    shared_strings: list[str],
    namespace: dict[str, str],
) -> Any:
    cell_type = cell.attrib.get("t")
    value = cell.findtext("x:v", default="", namespaces=namespace)

    if cell_type == "inlineStr":
        inline_parts = [node.text or "" for node in cell.findall(".//x:is//x:t", namespace)]
        return "".join(inline_parts)

    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value

    if cell_type == "b":
        return value == "1"

    return value


def normalize_document_payload(document: dict[str, Any], index: int) -> IntakeDocument:
    file_name = (
        document.get("file_name")
        or document.get("fileName")
        or document.get("filename")
        or document.get("name")
        or f"document_{index + 1}"
    )
    declared_raw = (
        document.get("declared_type")
        or document.get("declaredType")
        or document.get("document_type")
        or document.get("documentType")
        or document.get("type")
    )
    canonical_raw = document.get("canonical_type") or document.get("canonicalType") or declared_raw
    mime_type = document.get("mime_type") or document.get("mimeType") or _guess_mime_type(file_name)
    document_id = str(document.get("document_id") or document.get("documentId") or document.get("id") or uuid4())

    spreadsheet_rows = document.get("rows") if isinstance(document.get("rows"), list) else []
    sheets = document.get("sheets") if isinstance(document.get("sheets"), list) else []
    sections = document.get("sections") if isinstance(document.get("sections"), list) else []
    raw_text = document.get("raw_text") or document.get("rawText") or document.get("text") or document.get("content")
    size_bytes = document.get("size_bytes") or document.get("sizeBytes")

    return IntakeDocument(
        document_id=document_id,
        file_name=file_name,
        mime_type=mime_type,
        declared_type=normalize_document_type(declared_raw) if declared_raw else None,
        canonical_type=normalize_document_type(canonical_raw),
        size_bytes=int(size_bytes) if isinstance(size_bytes, (int, float)) else None,
        raw_text=str(raw_text) if raw_text is not None else None,
        sections=sections,
        spreadsheet_rows=[row for row in spreadsheet_rows if isinstance(row, dict)],
        sheets=[sheet for sheet in sheets if isinstance(sheet, dict)],
        notes=[str(note) for note in document.get("notes", []) if isinstance(note, (str, int, float))],
    )


async def normalize_upload_files(files: list[UploadFile], file_types: list[str]) -> list[IntakeDocument]:
    documents: list[IntakeDocument] = []
    for index, upload in enumerate(files):
        declared = file_types[index] if index < len(file_types) else None
        document = IntakeDocument(
            document_id=str(uuid4()),
            file_name=upload.filename or f"upload_{index + 1}",
            mime_type=upload.content_type or _guess_mime_type(upload.filename),
            declared_type=normalize_document_type(declared) if declared else None,
            canonical_type=normalize_document_type(declared),
            notes=[],
        )

        suffix = Path(document.file_name).suffix.lower()
        if (
            document.mime_type.startswith("text/")
            or suffix in {".txt", ".csv", ".json", ".docx"}
            or document.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            content = await upload.read()
            document.size_bytes = len(content)
            if suffix == ".docx" or document.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                document.raw_text = extract_docx_text(content)
                if not document.raw_text:
                    document.notes.append("DOCX upload could not be fully parsed into text.")
            else:
                document.raw_text = decode_text_content(content)
        elif (
            suffix == ".xlsx"
            or document.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ):
            content = await upload.read()
            document.size_bytes = len(content)
            document.sheets, extraction_notes = extract_xlsx_workbook(content)
            document.notes.extend(extraction_notes)
        documents.append(document)
    return documents


def infer_missing_document_inputs(documents: list[IntakeDocument]) -> list[MissingInput]:
    available_types = {document.canonical_type for document in documents}
    missing: list[MissingInput] = []

    required_individual = [
        (DocumentType.PROFIT_AND_LOSS, "profit_and_loss", "Profit and loss statements were not provided."),
        (DocumentType.BALANCE_SHEET, "balance_sheet", "Balance sheets were not provided."),
    ]
    for document_type, key, description in required_individual:
        if document_type not in available_types:
            missing.append(MissingInput(key=key, description=description, document_type=document_type, required=True))

    tax_types = {
        DocumentType.TAX_RETURN_1120S,
        DocumentType.TAX_RETURN_1040,
        DocumentType.TAX_RETURN_SCHEDULE_C,
    }
    if not available_types.intersection(tax_types):
        missing.append(
            MissingInput(
                key="tax_returns",
                description="No business tax returns were provided.",
                document_type=DocumentType.TAX_RETURN_1120S,
                required=True,
                reason="At least one supported tax return is expected for diligence.",
            )
        )

    optional_recommended = [
        (DocumentType.CASH_FLOW_STATEMENT, "cash_flow_statement", "Cash flow statements were not provided."),
        (DocumentType.AR_AGING_REPORT, "ar_aging_report", "An A/R aging report was not provided."),
    ]
    for document_type, key, description in optional_recommended:
        if document_type not in available_types:
            missing.append(MissingInput(key=key, description=description, document_type=document_type, required=False))

    return missing
