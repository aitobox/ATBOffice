"""Regression and acceptance tests for TASK-706 / Issue #240:
Lossless XLSX/XLSM default save roundtrip, VBA macro preservation (SHA-256 identical),
and ECMA-376 feature preservation (comments, charts, protection, custom XML).
"""

from __future__ import annotations

import hashlib
import io
import shutil
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.vfs.opc import PackageWriter

XLSX_CORPUS = Path("tests/docs/excel/xlsx")


def test_macro_xlsm_gui_save_unedited(qtbot, tmp_path: Path):
    """macro-button-form-control.xlsm unedited GUI save chain:
    Retains vbaProject.bin byte-for-byte (identical SHA), content type, and rels.
    """
    orig_path = XLSX_CORPUS / "libreoffice__macro-button-form-control.xlsm"
    assert orig_path.exists(), f"Corpus file missing: {orig_path}"

    test_file = tmp_path / "macro_unedited.xlsm"
    shutil.copy2(orig_path, test_file)

    with zipfile.ZipFile(orig_path) as z_orig:
        orig_vba = z_orig.read("xl/vbaProject.bin")
        orig_vba_sha = hashlib.sha256(orig_vba).hexdigest()

    win = LedgerWindow()
    qtbot.addWidget(win)

    # 1. Open file in GUI
    opened = win.open_file(test_file)
    assert opened is True
    assert win.current_file_path == test_file
    assert len(win.spreadsheet_view.workbook) >= 1

    # 2. Save file in GUI without any edits
    saved = win.save_file()
    assert saved is True

    # 3. Verify file on disk
    with zipfile.ZipFile(test_file) as z_saved:
        assert "xl/vbaProject.bin" in z_saved.namelist(), "vbaProject.bin was dropped"
        saved_vba = z_saved.read("xl/vbaProject.bin")
        saved_vba_sha = hashlib.sha256(saved_vba).hexdigest()
        assert (
            saved_vba_sha == orig_vba_sha
        ), f"vbaProject.bin SHA mismatch: {saved_vba_sha} vs {orig_vba_sha}"

        # Verify Content Types
        ct_xml = z_saved.read("[Content_Types].xml").decode("utf-8")
        assert (
            'ContentType="application/vnd.ms-excel.sheet.macroEnabled.main+xml"'
            in ct_xml
        ), "Missing macroEnabled workbook content type"
        assert (
            'ContentType="application/vnd.ms-office.vbaProject"' in ct_xml
        ), "Missing vbaProject content type"
        assert (
            ".rels" not in ct_xml or 'PartName="/_rels' not in ct_xml
        ), "Invalid .rels override found in [Content_Types].xml"

        # Verify workbook relationships
        wb_rels = z_saved.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        assert (
            "relationships/vbaProject" in wb_rels
        ), "Missing vbaProject relationship in workbook.xml.rels"
        assert (
            'Target="vbaProject.bin"' in wb_rels
        ), "Invalid vbaProject target in workbook.xml.rels"

    # 4. Verify clean reopen without error
    reopened_wb = read_xlsx(test_file)
    assert len(reopened_wb) >= 1
    assert reopened_wb.extra.get("is_macro_enabled") is True


def test_macro_xlsm_gui_save_edited_cell(qtbot, tmp_path: Path):
    """macro-button-form-control.xlsm single-cell edit GUI save chain:
    Retains vbaProject.bin SHA, controls, and rels while persisting modified cell data.
    """
    orig_path = XLSX_CORPUS / "libreoffice__macro-button-form-control.xlsm"
    assert orig_path.exists(), f"Corpus file missing: {orig_path}"

    test_file = tmp_path / "macro_edited.xlsm"
    shutil.copy2(orig_path, test_file)

    with zipfile.ZipFile(orig_path) as z_orig:
        orig_vba = z_orig.read("xl/vbaProject.bin")
        orig_vba_sha = hashlib.sha256(orig_vba).hexdigest()

    win = LedgerWindow()
    qtbot.addWidget(win)

    # 1. Open file in GUI
    opened = win.open_file(test_file)
    assert opened is True

    # 2. Edit a single cell (e.g. A1 = 777)
    active_sheet = win.spreadsheet_view.workbook.active_sheet
    active_sheet.set_cell_value(0, 0, 777)
    win.spreadsheet_view.workbook.dirty = True
    win.set_modified(True)

    # 3. Save file in GUI
    saved = win.save_file()
    assert saved is True

    # 4. Verify file on disk
    with zipfile.ZipFile(test_file) as z_saved:
        assert "xl/vbaProject.bin" in z_saved.namelist(), "vbaProject.bin was dropped"
        saved_vba = z_saved.read("xl/vbaProject.bin")
        saved_vba_sha = hashlib.sha256(saved_vba).hexdigest()
        assert (
            saved_vba_sha == orig_vba_sha
        ), f"vbaProject.bin SHA changed after cell edit: {saved_vba_sha} vs {orig_vba_sha}"

        # Verify sheet1 preserved controls and drawings
        s1_xml = z_saved.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert (
            "legacyDrawing" in s1_xml
        ), "legacyDrawing tag dropped from worksheet"
        assert "control" in s1_xml, "control tag dropped from worksheet"
        assert "777" in s1_xml, "Edited value 777 not found in worksheet XML"

        # Verify sheet1 rels preserved ctrlProp and vmlDrawing
        s1_rels = z_saved.read("xl/worksheets/_rels/sheet1.xml.rels").decode(
            "utf-8"
        )
        assert (
            "relationships/vmlDrawing" in s1_rels
        ), "vmlDrawing rel dropped from sheet1.xml.rels"
        assert (
            "relationships/ctrlProp" in s1_rels
        ), "ctrlProp rel dropped from sheet1.xml.rels"

    # 5. Verify clean reopen and updated cell retrieval
    reopened_wb = read_xlsx(test_file)
    assert reopened_wb[0].get_cell_value(0, 0) == 777
    assert reopened_wb.extra.get("is_macro_enabled") is True


def test_corpus_comments_preservation(tmp_path: Path):
    """poi__SimpleWithComments.xlsx: preserves comments, VML drawings, and relationships."""
    path = XLSX_CORPUS / "poi__SimpleWithComments.xlsx"
    assert path.exists()

    raw = path.read_bytes()
    wb = read_xlsx(raw)
    saved_bytes = write_xlsx(wb)

    with zipfile.ZipFile(io.BytesIO(saved_bytes)) as z:
        names = z.namelist()
        assert "xl/comments1.xml" in names, "comments1.xml was dropped"
        assert "xl/drawings/vmlDrawing1.vml" in names, "vmlDrawing1.vml was dropped"

        s1_rels = z.read("xl/worksheets/_rels/sheet1.xml.rels").decode("utf-8")
        assert (
            "relationships/comments" in s1_rels
        ), "Missing comments relationship in sheet1"
        assert (
            "relationships/vmlDrawing" in s1_rels
        ), "Missing vmlDrawing relationship in sheet1"


def test_corpus_charts_drawings_preservation(tmp_path: Path):
    """poi__60509.xlsx: preserves charts, drawings, calcChain, and relationships."""
    path = XLSX_CORPUS / "poi__60509.xlsx"
    assert path.exists()

    raw = path.read_bytes()
    wb = read_xlsx(raw)
    saved_bytes = write_xlsx(wb)

    with zipfile.ZipFile(io.BytesIO(saved_bytes)) as z:
        names = z.namelist()
        assert "xl/charts/chart1.xml" in names, "chart1.xml was dropped"
        assert "xl/drawings/drawing1.xml" in names, "drawing1.xml was dropped"
        assert "xl/calcChain.xml" in names, "calcChain.xml was dropped"

        wb_rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        assert (
            "relationships/calcChain" in wb_rels
        ), "Missing calcChain relationship in workbook.xml.rels"


def test_corpus_protection_preservation(tmp_path: Path):
    """libreoffice__enhanced-protection.xlsx: preserves sheet protection and protected ranges."""
    path = XLSX_CORPUS / "libreoffice__enhanced-protection.xlsx"
    assert path.exists()

    raw = path.read_bytes()
    wb = read_xlsx(raw)
    saved_bytes = write_xlsx(wb)

    with zipfile.ZipFile(io.BytesIO(saved_bytes)) as z:
        s1_xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert (
            "<sheetProtection" in s1_xml
        ), "sheetProtection dropped from sheet1.xml"
        assert (
            "<protectedRanges" in s1_xml
        ), "protectedRanges dropped from sheet1.xml"


def test_corpus_custom_xml_preservation(tmp_path: Path):
    """libreoffice__tdf113621.xlsx: preserves custom XML items, docProps, and rels."""
    path = XLSX_CORPUS / "libreoffice__tdf113621.xlsx"
    assert path.exists()

    raw = path.read_bytes()
    wb = read_xlsx(raw)
    saved_bytes = write_xlsx(wb)

    with zipfile.ZipFile(io.BytesIO(saved_bytes)) as z:
        names = z.namelist()
        assert "customXml/item1.xml" in names, "customXml/item1.xml dropped"
        assert "customXml/item2.xml" in names, "customXml/item2.xml dropped"
        assert "customXml/item3.xml" in names, "customXml/item3.xml dropped"
        assert "docProps/custom.xml" in names, "docProps/custom.xml dropped"

        wb_rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        assert (
            "relationships/customXml" in wb_rels
        ), "customXml rels dropped from workbook.xml.rels"


def test_faulty_write_does_not_corrupt_original(tmp_path: Path, monkeypatch):
    """Verify atomic save failure does not damage or truncate original file."""
    test_file = tmp_path / "precious.xlsx"
    test_data = b"PREVIOUS_VALID_CONTENT_HEADER_12345"
    test_file.write_bytes(test_data)

    writer = PackageWriter()

    # Simulate catastrophic error during byte serialization
    def fail_to_bytes():
        raise RuntimeError("Simulated serialization crash")

    monkeypatch.setattr(writer, "to_bytes", fail_to_bytes)

    with pytest.raises(RuntimeError, match="Simulated serialization crash"):
        writer.save(test_file)

    # Original file must remain 100% intact
    assert (
        test_file.read_bytes() == test_data
    ), "Original file was corrupted or truncated by failed write"
