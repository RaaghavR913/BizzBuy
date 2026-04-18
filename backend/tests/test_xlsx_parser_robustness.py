"""XLSX parser robustness: Target path normalisation and per-sheet error recovery."""
from __future__ import annotations

from app.services.intake_service import _read_xlsx_relationships
from unittest.mock import MagicMock
from xml.etree import ElementTree


def _make_rels_xml(targets: dict[str, str]) -> bytes:
    """Build a minimal workbook.xml.rels XML blob."""
    ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    root = ElementTree.Element(f"{{{ns}}}Relationships")
    for rel_id, target in targets.items():
        rel = ElementTree.SubElement(root, f"{{{ns}}}Relationship")
        rel.attrib["Id"] = rel_id
        rel.attrib["Target"] = target
        rel.attrib["Type"] = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    return ElementTree.tostring(root, encoding="unicode").encode()


def _make_archive(rels_bytes: bytes):
    archive = MagicMock()
    archive.read.return_value = rels_bytes
    return archive


# ---------------------------------------------------------------------------
# Target normalisation
# ---------------------------------------------------------------------------

def test_normal_relative_target():
    """Standard 'worksheets/sheet1.xml' resolves to 'xl/worksheets/sheet1.xml'."""
    archive = _make_archive(_make_rels_xml({"rId1": "worksheets/sheet1.xml"}))
    rels = _read_xlsx_relationships(archive)
    assert rels["rId1"] == "worksheets/sheet1.xml"


def test_absolute_target_stripped():
    """Leading '/' is stripped from absolute targets."""
    archive = _make_archive(_make_rels_xml({"rId1": "/xl/worksheets/sheet1.xml"}))
    rels = _read_xlsx_relationships(archive)
    # After stripping '/' → 'xl/worksheets/sheet1.xml'
    assert rels["rId1"] == "xl/worksheets/sheet1.xml"


def test_dotdot_target_resolved():
    """'../worksheets/sheet1.xml' is resolved to 'worksheets/sheet1.xml'."""
    archive = _make_archive(_make_rels_xml({"rId1": "../worksheets/sheet1.xml"}))
    rels = _read_xlsx_relationships(archive)
    assert rels["rId1"] == "worksheets/sheet1.xml"


def test_multiple_targets_all_normalised():
    archive = _make_archive(_make_rels_xml({
        "rId1": "worksheets/sheet1.xml",
        "rId2": "/xl/worksheets/sheet2.xml",
        "rId3": "../worksheets/sheet3.xml",
    }))
    rels = _read_xlsx_relationships(archive)
    assert "rId1" in rels
    assert "rId2" in rels
    assert "rId3" in rels
    # All should be normalised (no leading /)
    for path in rels.values():
        assert not path.startswith("/"), f"Path still starts with /: {path}"


def test_broken_rels_returns_empty():
    archive = MagicMock()
    archive.read.side_effect = KeyError("xl/_rels/workbook.xml.rels")
    rels = _read_xlsx_relationships(archive)
    assert rels == {}


def test_malformed_xml_returns_empty():
    archive = MagicMock()
    archive.read.return_value = b"NOT VALID XML <<<<"
    rels = _read_xlsx_relationships(archive)
    assert rels == {}
