"""Tests for DOCX Content Controls (SDT) and Revisions (Track Changes) Roundtrip Preservation.

Tests issue #286:
- poi__60316.docx: 27 content controls (sdt) in body and drawing textboxes must be preserved roundtrip.
- libreoffice__tdf125881.docx: ins and del revision tags must be preserved roundtrip.
- Relationships in word/_rels/document.xml.rels (customXml, etc.) must remain intact.
- Lossy saving protection: cancellation aborts saving without file corruption.
"""

from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from atboffice.modules.writer.io.docx_reader import read_docx
from atboffice.modules.writer.io.docx_writer import write_docx
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    SdtEndItem,
    SdtStartItem,
    TextItem,
)
from atboffice.modules.writer.models.properties import RevisionStamp, RunProperties


CORPUS_POI = Path("tests/docs/word/docx/poi__60316.docx")
CORPUS_TDF = Path("tests/docs/word/docx/libreoffice__tdf125881.docx")


def test_poi_60316_sdt_roundtrip_preservation():
    """Verify that all 27 content controls in poi__60316.docx are preserved on roundtrip."""
    assert CORPUS_POI.exists(), f"Missing corpus file: {CORPUS_POI}"

    # Read original
    doc = read_docx(CORPUS_POI)
    assert len(doc.main.blocks) > 0

    # Write out
    out_bytes = write_docx(doc)
    assert len(out_bytes) > 0

    # Inspect XML in saved archive
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml")
        root = ET.fromstring(doc_xml)
        sdts = list(root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdt"))
        assert len(sdts) == 27, f"Expected 27 sdt elements, got {len(sdts)}"

        # Check relationships in document.xml.rels
        rels_xml = zf.read("word/_rels/document.xml.rels")
        rels_root = ET.fromstring(rels_xml)
        custom_rels = [
            r for r in rels_root.iter("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
            if "customXml" in r.attrib.get("Type", "")
        ]
        assert len(custom_rels) >= 2, f"Expected customXml relationships preserved, got {len(custom_rels)}"

    # Re-open saved package and verify no crash
    doc2 = read_docx(io.BytesIO(out_bytes))
    assert len(doc2.main.blocks) == len(doc.main.blocks)


def test_tdf125881_revisions_roundtrip_preservation():
    """Verify that paragraph mark revisions (2 ins, 1 del) in libreoffice__tdf125881.docx are preserved."""
    assert CORPUS_TDF.exists(), f"Missing corpus file: {CORPUS_TDF}"

    doc = read_docx(CORPUS_TDF)
    out_bytes = write_docx(doc)

    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml")
        root = ET.fromstring(doc_xml)
        ins_elems = list(root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ins"))
        del_elems = list(root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}del"))

        assert len(ins_elems) >= 2, f"Expected at least 2 ins elements, got {len(ins_elems)}"
        assert len(del_elems) >= 1, f"Expected at least 1 del elements, got {len(del_elems)}"

    # Re-open saved package
    doc2 = read_docx(io.BytesIO(out_bytes))
    p0 = doc2.main.blocks[0]
    assert p0.mark_ins is not None
    assert p0.mark_ins.author == "Szerző"


def test_inline_sdt_synthetic_roundtrip():
    """Verify synthetic inline SDT item start and end markers roundtrip cleanly."""
    doc = Document()
    p = Paragraph()
    shell_xml = (
        '<w:sdt xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:sdtPr><w:alias w:val="Test Control"/><w:tag w:val="TEST"/></w:sdtPr>'
        '<w:sdtContent></w:sdtContent></w:sdt>'
    )
    control = {"key": "ctrl_test_1", "shell_xml": shell_xml, "alias": "Test Control", "tag": "TEST"}
    p.runs.append(SdtStartItem(control=control))
    p.runs.append(TextItem(text="Hello Inside Control"))
    p.runs.append(SdtEndItem(key="ctrl_test_1"))
    doc.main.blocks.append(p)

    out_bytes = write_docx(doc)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml")
        root = ET.fromstring(doc_xml)
        sdt = root.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdt")
        assert sdt is not None
        alias = sdt.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}alias")
        assert alias is not None
        assert alias.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") == "Test Control"


def test_run_revisions_synthetic_roundtrip():
    """Verify synthetic run-level ins and del revisions roundtrip cleanly."""
    doc = Document()
    p = Paragraph()
    ins_stamp = RevisionStamp(author="Alice", date="2026-11-05T12:00:00Z", id=101)
    del_stamp = RevisionStamp(author="Bob", date="2026-11-05T12:01:00Z", id=102)

    p.runs.append(TextItem(text="Inserted Text", r_pr=RunProperties(ins=ins_stamp)))
    p.runs.append(TextItem(text="Deleted Text", r_pr=RunProperties(del_rev=del_stamp)))
    doc.main.blocks.append(p)

    out_bytes = write_docx(doc)
    with zipfile.ZipFile(io.BytesIO(out_bytes)) as zf:
        doc_xml = zf.read("word/document.xml")
        root = ET.fromstring(doc_xml)
        ins = root.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ins")
        del_elem = root.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}del")
        assert ins is not None
        assert ins.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author") == "Alice"
        assert del_elem is not None
        assert del_elem.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author") == "Bob"


def test_lossy_save_prompt_cancellation(qapp, tmp_path):
    """Verify that saving a document with losses prompts the user, and user cancellation aborts save."""
    from unittest.mock import patch
    from PySide6.QtWidgets import QMessageBox
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    doc = Document()
    doc.losses.append("Unsupported ActiveX control")
    win.writer_view.canvas_view.set_document(doc)

    target_file = tmp_path / "test_lossy.docx"
    target_file.write_bytes(b"original content")

    # Simulate user clicking "No" (Cancel)
    with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No) as mock_warn:
        success = win.do_save(target_file)
        assert success is False
        assert mock_warn.called
        # Verify original file content was preserved untouched
        assert target_file.read_bytes() == b"original content"

    # Simulate user clicking "Yes" (Continue)
    with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes) as mock_warn:
        success = win.do_save(target_file)
        assert success is True
        assert mock_warn.called
        # Verify file was overwritten with valid docx
        assert target_file.read_bytes() != b"original content"
