"""Tests for DOCX ingestion through the intake service."""
from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

import pytest

from app.services.intake_service import extract_docx_content, extract_docx_text


# ---------------------------------------------------------------------------
# Helpers to build minimal DOCX bytes in-memory
# ---------------------------------------------------------------------------

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_DOC_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _w(tag: str) -> str:
    return f"{{{_W_NS}}}{tag}"


def _make_paragraph(text: str) -> ElementTree.Element:
    p = ElementTree.Element(_w("p"))
    r = ElementTree.SubElement(p, _w("r"))
    t = ElementTree.SubElement(r, _w("t"))
    t.text = text
    return p


def _make_table(rows: list[list[str]]) -> ElementTree.Element:
    tbl = ElementTree.Element(_w("tbl"))
    for row_cells in rows:
        tr = ElementTree.SubElement(tbl, _w("tr"))
        for cell_text in row_cells:
            tc = ElementTree.SubElement(tr, _w("tc"))
            p = ElementTree.SubElement(tc, _w("p"))
            r = ElementTree.SubElement(p, _w("r"))
            t = ElementTree.SubElement(r, _w("t"))
            t.text = cell_text
    return tbl


def _build_docx(body_children: list[ElementTree.Element]) -> bytes:
    """Construct a minimal DOCX (ZIP + document.xml) with the given body elements."""
    root = ElementTree.Element(_w("document"))
    body = ElementTree.SubElement(root, _w("body"))
    for child in body_children:
        body.append(child)

    xml_bytes = ElementTree.tostring(root, encoding="unicode").encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", xml_bytes)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_extract_docx_text_paragraphs_only():
    """extract_docx_text returns paragraph text, unchanged from old behaviour."""
    content = _build_docx([
        _make_paragraph("Hello world"),
        _make_paragraph("Second paragraph"),
    ])
    text = extract_docx_text(content)
    assert "Hello world" in text
    assert "Second paragraph" in text


def test_extract_docx_content_paragraphs():
    content = _build_docx([
        _make_paragraph("Narrative text line 1"),
        _make_paragraph("Narrative text line 2"),
    ])
    narrative, tables = extract_docx_content(content)
    assert "Narrative text line 1" in narrative
    assert "Narrative text line 2" in narrative
    assert tables == []


def test_extract_docx_content_table():
    """Tables are extracted as row dicts with A/B/C column keys."""
    content = _build_docx([
        _make_table([
            ["Line Item", "2022", "2023"],
            ["Total Revenue", "1980000", "2180000"],
        ]),
    ])
    narrative, tables = extract_docx_content(content)
    assert len(tables) == 1
    header_row = tables[0][0]
    assert header_row["A"] == "Line Item"
    assert header_row["B"] == "2022"
    assert header_row["C"] == "2023"
    data_row = tables[0][1]
    assert data_row["A"] == "Total Revenue"
    assert data_row["B"] == "1980000"


def test_extract_docx_content_table_and_paragraphs():
    """Paragraphs before/after a table all land in narrative; table in tables list."""
    content = _build_docx([
        _make_paragraph("Intro paragraph"),
        _make_table([["Header", "Value"], ["Revenue", "100"]]),
        _make_paragraph("Closing paragraph"),
    ])
    narrative, tables = extract_docx_content(content)
    assert "Intro paragraph" in narrative
    assert "Closing paragraph" in narrative
    assert len(tables) == 1
    assert tables[0][0]["A"] == "Header"


def test_extract_docx_content_multiple_tables():
    content = _build_docx([
        _make_table([["P&L", "2024"], ["Revenue", "500"]]),
        _make_table([["Balance Sheet", "Amount"], ["Total Assets", "200"]]),
    ])
    narrative, tables = extract_docx_content(content)
    assert len(tables) == 2


def test_extract_docx_text_backward_compat():
    """extract_docx_text must stay backward-compatible (returns only narrative)."""
    content = _build_docx([
        _make_paragraph("Only text here"),
        _make_table([["Col", "Value"], ["Row", "1"]]),
    ])
    text = extract_docx_text(content)
    assert "Only text here" in text
    # Tables should NOT appear as raw row values in the narrative text
    # (table cells may appear because the old code read all <w:t> nodes)


def test_extract_docx_content_bad_zip():
    narrative, tables = extract_docx_content(b"not a zip file")
    assert narrative == ""
    assert tables == []


def test_extract_docx_row_index_sequential():
    content = _build_docx([
        _make_table([["A", "B"], ["C", "D"], ["E", "F"]]),
    ])
    _, tables = extract_docx_content(content)
    row_indices = [r["row_index"] for r in tables[0]]
    assert row_indices == [1, 2, 3]
