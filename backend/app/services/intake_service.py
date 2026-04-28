from __future__ import annotations

import csv as _csv_module
import json
import mimetypes
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile

from app.agents.schemas import DocumentType, MissingInput
from app.core.config import get_settings
from app.core.path_safety import UnsafePathError, resolve_backend_env_path, validate_sha256_hex
from app.services.section_kind import infer_section_kind, infer_sheet_kinds


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


class ArchiveLimitError(ValueError):
    """Raised when an Office document zip exceeds configured parser limits."""


def _validate_zip_archive(archive: ZipFile, label: str) -> None:
    settings = get_settings()
    entries = [info for info in archive.infolist() if not info.is_dir()]
    if len(entries) > settings.max_zip_entries:
        raise ArchiveLimitError(f"{label} archive contains too many entries.")

    total_uncompressed = 0
    for info in entries:
        total_uncompressed += max(0, info.file_size)
        if total_uncompressed > settings.max_zip_uncompressed_bytes:
            raise ArchiveLimitError(f"{label} archive exceeds the decompressed size limit.")


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
            _validate_zip_archive(archive, "DOCX")
            xml_content = archive.read("word/document.xml")
    except (BadZipFile, KeyError, ArchiveLimitError):
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
    """Parse DOCX bytes into newline-delimited text paragraphs (backward-compatible)."""
    narrative, _ = extract_docx_content(content)
    return narrative


def extract_docx_content(content: bytes) -> tuple[str, list[list[dict[str, Any]]]]:
    """Parse DOCX bytes into (narrative_text, tables).

    ``narrative_text`` contains paragraph text from outside tables.
    ``tables`` is a list of table row lists.  Each row is a dict with
    ``A``/``B``/``C``... column keys (1-indexed), compatible with
    ``_row_table`` in financial_data_extractor.
    """
    try:
        with ZipFile(BytesIO(content)) as archive:
            _validate_zip_archive(archive, "DOCX")
            xml_content = archive.read("word/document.xml")
    except (BadZipFile, KeyError, ArchiveLimitError):
        return "", []

    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError:
        return "", []

    NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ns = {"w": NS}

    body = root.find(f"{{{NS}}}body")
    if body is None:
        # Fallback: collect all paragraphs document-wide
        paragraphs = []
        for p in root.findall(".//w:p", ns):
            runs = [t.text or "" for t in p.findall(".//w:t", ns)]
            text = "".join(runs).strip()
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs), []

    paragraphs: list[str] = []
    tables: list[list[dict[str, Any]]] = []

    for child in body:
        local = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if local == "p":
            runs = [t.text or "" for t in child.findall(".//w:t", ns)]
            text = "".join(runs).strip()
            if text:
                paragraphs.append(text)

        elif local == "tbl":
            table_rows: list[dict[str, Any]] = []
            row_idx = 0
            for tr in child.findall(f".//{{{NS}}}tr"):
                row_idx += 1
                cells = tr.findall(f".//{{{NS}}}tc")
                row: dict[str, Any] = {"row_index": row_idx}
                for col_i, tc in enumerate(cells, start=1):
                    texts = [t.text or "" for t in tc.findall(f".//{{{NS}}}t")]
                    cell_text = "".join(texts).strip()
                    row[_col_letter(col_i)] = cell_text if cell_text else None
                table_rows.append(row)
            if table_rows:
                tables.append(table_rows)

    return "\n".join(paragraphs), tables


def _col_letter(n: int) -> str:
    """Convert 1-based column index to spreadsheet column letter (A, B, …, Z, AA, …)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _rows_to_local_text(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for row in rows:
        values = [
            str(value).strip()
            for column, value in sorted(row.items(), key=lambda item: _col_sort_key(str(item[0])))
            if column != "row_index" and value not in {None, ""}
        ]
        if values:
            lines.append(" | ".join(values))
    return "\n".join(lines)


def _col_sort_key(column: str) -> int:
    if column == "row_index":
        return -1
    total = 0
    for char in column.upper():
        if "A" <= char <= "Z":
            total = total * 26 + (ord(char) - ord("A") + 1)
    return total


def _parse_csv_content(
    content: bytes,
    *,
    is_tsv: bool = False,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Parse CSV/TSV bytes into (rows, raw_text, notes).

    Rows use the ``A``/``B``/``C``… key format expected by ``_row_table``.
    BOM-prefixed UTF-8 is handled transparently.
    """
    try:
        text = content.decode("utf-8-sig", errors="replace")
    except Exception:
        return [], "", ["CSV upload could not be decoded as UTF-8."]

    delimiter = "\t" if is_tsv else ","
    rows: list[dict[str, Any]] = []
    notes: list[str] = []

    try:
        reader = _csv_module.reader(StringIO(text), delimiter=delimiter)
        for row_index, csv_row in enumerate(reader, start=1):
            if not any(cell.strip() for cell in csv_row):
                continue  # skip blank lines
            row: dict[str, Any] = {"row_index": row_index}
            for col_idx, cell in enumerate(csv_row, start=1):
                row[_col_letter(col_idx)] = cell.strip() if cell.strip() else None
            rows.append(row)
    except _csv_module.Error as exc:
        notes.append(f"CSV parsing error: {exc}")
        return rows, text, notes

    ext = ".tsv" if is_tsv else ".csv"
    notes.append(f"Parsed {len(rows)} row(s) from {ext} file.")
    return rows, text, notes


def extract_xlsx_workbook(content: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        with ZipFile(BytesIO(content)) as archive:
            _validate_zip_archive(archive, "XLSX")
            shared_strings = _read_xlsx_shared_strings(archive)
            workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            workbook_rels = _read_xlsx_relationships(archive)
            namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

            sheets: list[dict[str, Any]] = []
            notes: list[str] = []
            for index, sheet in enumerate(workbook_root.findall(".//x:sheets/x:sheet", namespace)):
                sheet_name_attr = sheet.attrib.get("name") or f"Sheet {index + 1}"
                relation_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                target = workbook_rels.get(relation_id or "", "")

                # Build a prioritised list of candidate paths for this sheet.
                candidate_paths: list[str] = []
                if target:
                    # The normalised target from _read_xlsx_relationships
                    if target.startswith("xl/"):
                        candidate_paths.append(target)
                    else:
                        candidate_paths.append(f"xl/{target}")
                # Always include the positional fallback path.
                candidate_paths.append(f"xl/worksheets/sheet{index + 1}.xml")

                worksheet_root = None
                for path in candidate_paths:
                    try:
                        worksheet_root = ElementTree.fromstring(archive.read(path))
                        break
                    except (KeyError, ElementTree.ParseError):
                        continue

                if worksheet_root is None:
                    notes.append(f"Skipped workbook sheet {sheet_name_attr}: worksheet XML could not be parsed.")
                    continue

                rows = _read_xlsx_rows(worksheet_root, shared_strings)
                sheet_text = "\n".join(
                    " | ".join(str(value) for value in row.values() if value not in {None, ""})
                    for row in rows
                    if any(value not in {None, ""} for value in row.values())
                )
                sheets.append(
                    {
                        "name": sheet_name_attr,
                        "rows": rows,
                        "text": sheet_text,
                        "confidence": 0.8 if rows else 0.45,
                    }
                )
            return sheets, notes
    except ArchiveLimitError as exc:
        return [], [str(exc)]
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
            # Normalise path variants so all Target values resolve relative to xl/.
            # Strip leading "/" (absolute paths), then resolve ".." segments.
            normalized = target.lstrip("/")
            # Handle "../worksheets/sheetN.xml" style: resolve against xl/
            parts = normalized.split("/")
            resolved: list[str] = []
            for part in parts:
                if part == "..":
                    if resolved:
                        resolved.pop()
                elif part not in ("", "."):
                    resolved.append(part)
            relationships[rel_id] = "/".join(resolved)
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


async def _normalize_upload_files(
    files: list[UploadFile],
    file_types: list[str],
    *,
    file_hashes: list[str] | None,
    ocr_artifact_refs: list[str] | None,
) -> list[IntakeDocument]:
    from app.services.ocr_markdown_parser import build_sections_from_ocr

    documents: list[IntakeDocument] = []
    for index, upload in enumerate(files):
        declared = file_types[index] if index < len(file_types) else None
        file_hash = file_hashes[index] if file_hashes and index < len(file_hashes) else None
        ocr_ref = ocr_artifact_refs[index] if ocr_artifact_refs and index < len(ocr_artifact_refs) else None

        document = IntakeDocument(
            document_id=str(uuid4()),
            file_name=upload.filename or f"upload_{index + 1}",
            mime_type=upload.content_type or _guess_mime_type(upload.filename),
            declared_type=normalize_document_type(declared) if declared else None,
            canonical_type=normalize_document_type(declared),
            notes=[],
        )

        suffix = Path(document.file_name).suffix.lower()

        # ------------------------------------------------------------------
        # XLSX — multi-sheet workbook (unchanged path)
        # ------------------------------------------------------------------
        if (
            suffix == ".xlsx"
            or document.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ):
            content = await upload.read()
            document.size_bytes = len(content)
            document.sheets, extraction_notes = extract_xlsx_workbook(content)
            document.notes.extend(extraction_notes)

        # ------------------------------------------------------------------
        # CSV / TSV — parse into structured rows
        # ------------------------------------------------------------------
        elif suffix in {".csv", ".tsv"} or document.mime_type in {
            "text/csv",
            "text/tab-separated-values",
        }:
            content = await upload.read()
            document.size_bytes = len(content)
            rows, raw_text, notes = _parse_csv_content(
                content, is_tsv=(suffix == ".tsv" or document.mime_type == "text/tab-separated-values")
            )
            document.spreadsheet_rows = rows
            document.raw_text = raw_text
            document.notes.extend(notes)

        # ------------------------------------------------------------------
        # DOCX — extract tables AND narrative paragraphs
        # ------------------------------------------------------------------
        elif (
            suffix == ".docx"
            or document.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            content = await upload.read()
            document.size_bytes = len(content)
            narrative, docx_tables = extract_docx_content(content)
            document.raw_text = narrative
            if narrative.strip():
                document.sections.append(
                    {
                        "section_name": "Document Text",
                        "raw_text": narrative,
                        "extracted_data": {},
                        "confidence": 0.7,
                        "contentType": "text",
                        "sourceFormat": "docx",
                        "notes": ["Narrative text extracted from DOCX body."],
                    }
                )
            for table_idx, table_rows in enumerate(docx_tables):
                document.sections.append(
                    {
                        "section_name": f"Table {table_idx + 1}",
                        "raw_text": _rows_to_local_text(table_rows),
                        "extracted_data": {"rows": table_rows},
                        "confidence": 0.75,
                        "contentType": "table",
                        "sourceFormat": "docx",
                        "notes": [f"Extracted from DOCX table {table_idx + 1}."],
                    }
                )
            if docx_tables:
                document.notes.append(
                    f"Extracted {len(docx_tables)} structured table(s) from DOCX."
                )
            if not document.raw_text and not docx_tables:
                document.notes.append("DOCX upload could not be fully parsed.")

        # ------------------------------------------------------------------
        # Plain text / JSON — raw text only
        # ------------------------------------------------------------------
        elif document.mime_type.startswith("text/") or suffix in {".txt", ".json"}:
            content = await upload.read()
            document.size_bytes = len(content)
            document.raw_text = decode_text_content(content)

        # ------------------------------------------------------------------
        # PDF / image — content is NOT read here (OCR handled externally).
        # Structured sections come from the cached OCR artifact below.
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # OCR artifact fallback — applies to PDFs / images (and any other
        # format that produced no structured content above).
        # ------------------------------------------------------------------
        if not document.sections and not document.sheets and not document.spreadsheet_rows:
            cached_payload = _load_cached_ocr_payload(file_hash=file_hash, artifact_ref=ocr_ref)
            if cached_payload:
                document.sections = build_sections_from_ocr(
                    cached_payload, document.canonical_type
                )
                full_md = (
                    cached_payload.get("full_markdown")
                    or cached_payload.get("fullMarkdown")
                    or ""
                )
                if not document.raw_text:
                    document.raw_text = full_md
                document.notes.append(
                    f"Built {len(document.sections)} structured section(s) from cached OCR artifact."
                )
            else:
                # Last-resort: extract raw text only from OCR artifact
                cached_text = _load_cached_ocr_text(file_hash=file_hash, artifact_ref=ocr_ref)
                if cached_text and not document.raw_text:
                    document.raw_text = cached_text
                    document.notes.append("Reused cached OCR artifact text for ingestion.")

        documents.append(document)
    return documents


async def normalize_upload_files(
    files: list[UploadFile],
    file_types: list[str],
    *,
    file_hashes: list[str] | None = None,
    ocr_artifact_refs: list[str] | None = None,
) -> list[IntakeDocument]:
    return await _normalize_upload_files(
        files,
        file_types,
        file_hashes=file_hashes,
        ocr_artifact_refs=ocr_artifact_refs,
    )


def _load_cached_ocr_text(*, file_hash: str | None, artifact_ref: str | None) -> str:
    artifact_path = _safe_ocr_artifact_path(file_hash=file_hash, artifact_ref=artifact_ref)
    if artifact_path is None or not artifact_path.exists():
        return ""
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    full_markdown = payload.get("full_markdown") or payload.get("fullMarkdown")
    if isinstance(full_markdown, str) and full_markdown.strip():
        return full_markdown
    pages = payload.get("pages")
    if isinstance(pages, list):
        return "\n\n---\n\n".join(
            page.get("markdown", "")
            for page in pages
            if isinstance(page, dict) and isinstance(page.get("markdown"), str)
        ).strip()
    return ""


def _load_cached_ocr_payload(*, file_hash: str | None, artifact_ref: str | None) -> dict[str, Any] | None:
    """Return the full cached OCR artifact payload dict, or None if unavailable."""
    artifact_path = _safe_ocr_artifact_path(file_hash=file_hash, artifact_ref=artifact_ref)
    if artifact_path is None or not artifact_path.exists():
        return None
    try:
        return json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_ocr_artifact_path(*, file_hash: str | None, artifact_ref: str | None) -> Path | None:
    root = resolve_backend_env_path("BIZBUY_ARTIFACT_DIR", default_relative=".artifacts") / "ocr"
    if file_hash:
        try:
            return root / f"{validate_sha256_hex(file_hash)}.json"
        except UnsafePathError:
            return None
    if artifact_ref:
        ref = artifact_ref.strip()
        if ref.startswith("ocr:"):
            try:
                return root / f"{validate_sha256_hex(ref.removeprefix('ocr:'))}.json"
            except UnsafePathError:
                return None
        if len(ref) == 64:
            try:
                return root / f"{validate_sha256_hex(ref)}.json"
            except UnsafePathError:
                return None
    return None


def infer_missing_document_inputs(documents: list[IntakeDocument]) -> list[MissingInput]:
    available_types = {document.canonical_type for document in documents}
    available_kinds = {document_type.value for document_type in available_types}
    for document in documents:
        available_kinds.update(infer_sheet_kinds(document.sheets))
        if document.raw_text:
            available_kinds.add(
                infer_section_kind(
                    document_type=document.canonical_type,
                    raw_text=document.raw_text,
                )
            )
        for section in document.sections:
            explicit_kind = section.get("section_kind") or section.get("sectionKind")
            if explicit_kind:
                available_kinds.add(str(explicit_kind))
                continue
            rows = []
            extracted = section.get("extracted_data") or section.get("extractedData") or {}
            if isinstance(extracted, dict) and isinstance(extracted.get("rows"), list):
                rows = [row for row in extracted["rows"] if isinstance(row, dict)]
            available_kinds.add(
                infer_section_kind(
                    document_type=document.canonical_type,
                    section_name=section.get("sectionName") or section.get("section_name") or section.get("name"),
                    raw_text=section.get("raw_text") or section.get("rawText") or section.get("text"),
                    rows=rows,
                )
            )
    missing: list[MissingInput] = []

    required_individual = [
        (DocumentType.PROFIT_AND_LOSS, "profit_and_loss", "Profit and loss statements were not provided."),
        (DocumentType.BALANCE_SHEET, "balance_sheet", "Balance sheets were not provided."),
    ]
    for document_type, key, description in required_individual:
        if document_type.value not in available_kinds:
            missing.append(MissingInput(key=key, description=description, document_type=document_type, required=True))

    tax_types = {
        DocumentType.TAX_RETURN_1120S,
        DocumentType.TAX_RETURN_1040,
        DocumentType.TAX_RETURN_SCHEDULE_C,
    }
    if not ({document_type.value for document_type in tax_types}).intersection(available_kinds):
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
        if document_type.value not in available_kinds:
            missing.append(MissingInput(key=key, description=description, document_type=document_type, required=False))

    return missing
