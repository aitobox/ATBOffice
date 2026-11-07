"""Corpus regression test for libreoffice__cell-value.xlsx alignment."""

from pathlib import Path
import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx


def test_libreoffice_cell_value_alignments():
    """Verify that numbers in libreoffice__cell-value.xlsx are right-aligned and strings are left-aligned."""
    doc_path = Path("tests/docs/excel/xlsx/libreoffice__cell-value.xlsx")
    assert doc_path.exists(), f"Corpus file {doc_path} must exist"

    wb = read_xlsx(str(doc_path))
    assert len(wb.sheets) >= 1
    sheet = wb.sheets[0]

    # Row 0: Integers (-2012, -1, 0, 1, 2012)
    for c in range(5):
        cell = sheet.get_cell(0, c)
        assert cell is not None, f"Cell (0, {c}) should exist"
        assert isinstance(cell.value, (int, float)), f"Cell (0, {c}) should be numeric"
        assert cell.align_h == "general"
        assert cell.get_effective_align_h() == "right", f"Numeric cell (0, {c}) must be right-aligned"

    # Row 1: Floats (-3.14, -0.99, 0.01, 3.14)
    for c in range(4):
        cell = sheet.get_cell(1, c)
        assert cell is not None, f"Cell (1, {c}) should exist"
        assert isinstance(cell.value, float), f"Cell (1, {c}) should be float"
        assert cell.align_h == "general"
        assert cell.get_effective_align_h() == "right", f"Float cell (1, {c}) must be right-aligned"

    # Row 2: Text strings ('H', 'Hello, Calc!', etc.)
    cell_h = sheet.get_cell(2, 0)
    assert cell_h is not None and isinstance(cell_h.value, str)
    assert cell_h.get_effective_align_h() == "left"

    cell_hello = sheet.get_cell(2, 1)
    assert cell_hello is not None and isinstance(cell_hello.value, str)
    assert cell_hello.get_effective_align_h() == "left"

    cell_long = sheet.get_cell(2, 3)
    assert cell_long is not None and isinstance(cell_long.value, str)
    assert cell_long.get_effective_align_h() == "left"
