from __future__ import annotations

from app.agents.schemas import DocumentSection

# Keys that contain raw spreadsheet/table row dumps.
# These are already represented in DocumentSection.raw_text (the evidence snippet)
# and must NOT be passed into EvidenceReference.extracted_fields, which only
# accepts primitive scalar values (str | int | float | bool | None).
_NOISY_RAW_KEYS = {"rows", "tables", "raw_rows", "table", "cells"}


def build_evidence_fields(section: DocumentSection) -> dict[str, str | float | int | bool | None]:
    """Return OCR-derived semantic metadata for use as EvidenceReference.extracted_fields.

    Promotes the structured scalar fields the OCR parser already wrote onto the
    DocumentSection (section_kind, section_name, document_type, source_format,
    fiscal_year, period_start, period_end) and discards the raw spreadsheet row
    dump that is stored in extracted_data["rows"]. That row content is already
    represented in section.raw_text which becomes the evidence snippet.
    """
    fields: dict[str, str | float | int | bool | None] = {}

    if section.section_kind:
        fields["section_kind"] = section.section_kind
    if section.section_name:
        fields["section_name"] = section.section_name
    if section.document_type:
        fields["document_type"] = section.document_type.value
    if section.source_format:
        fields["source_format"] = section.source_format

    timeframe = section.timeframe
    if timeframe:
        if timeframe.fiscal_year is not None:
            fields["fiscal_year"] = timeframe.fiscal_year
        if timeframe.start_date:
            fields["period_start"] = str(timeframe.start_date)
        if timeframe.end_date:
            fields["period_end"] = str(timeframe.end_date)

    # Carry through any top-level primitive scalars the OCR parser may have
    # attached to extracted_data, but skip the noisy row/table arrays and
    # any key that we already populated above.
    for key, value in (section.extracted_data or {}).items():
        if key in _NOISY_RAW_KEYS or key in fields:
            continue
        if value is None or isinstance(value, (str, int, float, bool)):
            fields[key] = value

    return fields
