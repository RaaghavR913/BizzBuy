"""Unit tests for evidence_utils.build_evidence_fields and the EvidenceReference validator."""
from __future__ import annotations

import pytest

from app.agents.evidence_utils import build_evidence_fields
from app.agents.schemas import DocumentSection, DocumentType, Timeframe
from app.models.schemas import EvidenceReference


def _make_section(**overrides) -> DocumentSection:
    base = dict(
        document_id="doc-1",
        document_type=DocumentType.PROFIT_AND_LOSS,
        section_kind="profit_and_loss",
        section_name="P&L Summary",
        timeframe=Timeframe(fiscal_year=2024, start_date="2024-01-01", end_date="2024-12-31"),
        extracted_data={"total_revenue": 500000, "rows": [{"A": 1, "B": 2}, {"A": 3, "B": 4}]},
        raw_text="Revenue | 500,000",
        confidence=0.95,
        source_format="spreadsheet",
    )
    base.update(overrides)
    return DocumentSection(**base)


def test_returns_only_primitives():
    """build_evidence_fields must never return non-primitive values."""
    section = _make_section()
    fields = build_evidence_fields(section)
    for key, val in fields.items():
        assert val is None or isinstance(val, (str, int, float, bool)), (
            f"Non-primitive value for key '{key}': {type(val)}"
        )


def test_rows_key_is_dropped():
    """The raw 'rows' list in extracted_data must not appear in the output."""
    section = _make_section()
    fields = build_evidence_fields(section)
    assert "rows" not in fields


def test_semantic_fields_promoted():
    """OCR-derived semantic fields should all be present when set on the section."""
    section = _make_section()
    fields = build_evidence_fields(section)

    assert fields["section_kind"] == "profit_and_loss"
    assert fields["section_name"] == "P&L Summary"
    assert fields["document_type"] == DocumentType.PROFIT_AND_LOSS.value
    assert fields["source_format"] == "spreadsheet"
    assert fields["fiscal_year"] == 2024
    assert fields["period_start"] == "2024-01-01"
    assert fields["period_end"] == "2024-12-31"


def test_primitive_extracted_data_scalars_carried_through():
    """Top-level primitive scalars from extracted_data (other than noisy keys) survive."""
    section = _make_section()
    fields = build_evidence_fields(section)
    assert fields.get("total_revenue") == 500000


def test_empty_section_returns_at_least_document_type():
    """A minimal section with no optional fields still returns document_type."""
    section = _make_section(
        section_kind=None,
        section_name=None,
        source_format=None,
        timeframe=Timeframe(),
        extracted_data={},
    )
    fields = build_evidence_fields(section)
    assert fields.get("document_type") == DocumentType.PROFIT_AND_LOSS.value


# --- EvidenceReference defensive validator ---

def test_evidence_reference_drops_list_value():
    """The belt-and-suspenders validator must drop list values silently."""
    ref = EvidenceReference(
        document_id="doc-1",
        extracted_fields={"rows": [{"A": 1}], "fiscal_year": 2024},
    )
    assert "rows" not in ref.extracted_fields
    assert ref.extracted_fields["fiscal_year"] == 2024


def test_evidence_reference_drops_dict_value():
    """Nested dicts must also be dropped without raising."""
    ref = EvidenceReference(
        document_id="doc-1",
        extracted_fields={"nested": {"foo": "bar"}, "name": "test"},
    )
    assert "nested" not in ref.extracted_fields
    assert ref.extracted_fields["name"] == "test"


def test_evidence_reference_accepts_valid_primitives():
    """All primitive types must pass through unchanged."""
    ref = EvidenceReference(
        document_id="doc-1",
        extracted_fields={
            "str_val": "hello",
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "none_val": None,
        },
    )
    assert ref.extracted_fields["str_val"] == "hello"
    assert ref.extracted_fields["int_val"] == 42
    assert ref.extracted_fields["float_val"] == pytest.approx(3.14)
    assert ref.extracted_fields["bool_val"] is True
    assert ref.extracted_fields["none_val"] is None


def test_evidence_reference_handles_non_dict_input():
    """A completely non-dict input should produce an empty dict instead of raising."""
    ref = EvidenceReference(document_id="doc-1", extracted_fields=None)  # type: ignore[arg-type]
    assert ref.extracted_fields == {}
