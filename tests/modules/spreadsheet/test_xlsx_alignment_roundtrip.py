"""Tests for OOXML alignment and text direction (readingOrder) serialization roundtrip."""

import tempfile
from pathlib import Path

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def test_xlsx_alignment_and_reading_order_roundtrip():
    """Verify that text direction (RTL/LTR) and horizontal alignment roundtrip without loss."""
    sheet = SheetDataModel("AlignmentTest")
    wb = WorkbookModel(sheets=[sheet])

    # Cell (0, 0): RTL text with General alignment
    sheet.set_cell(0, 0, CellData(value="مرحبا", align_h="general", text_direction="rtl"))

    # Cell (0, 1): LTR text
    sheet.set_cell(0, 1, CellData(value="Hello", align_h="general", text_direction="ltr"))

    # Cell (0, 2): Explicit right alignment
    sheet.set_cell(0, 2, CellData(value="Label", align_h="right"))

    # Cell (0, 3): Explicit center alignment
    sheet.set_cell(0, 3, CellData(value=123, align_h="center"))

    # Cell (0, 4): Number in General format
    sheet.set_cell(0, 4, CellData(value=-2012, align_h="general"))

    # Cell (0, 5): Boolean in General format
    sheet.set_cell(0, 5, CellData(value=True, align_h="general"))

    # Write out to temporary file
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        write_xlsx(wb, str(tmp_path))

        # Read back
        wb_read = read_xlsx(str(tmp_path))
        sh_read = wb_read.sheets[0]

        # Verify (0, 0): RTL preserved, effective alignment is right
        c00 = sh_read.get_cell(0, 0)
        assert c00 is not None
        assert c00.text_direction == "rtl"
        assert c00.align_h == "general"
        assert c00.get_effective_align_h() == "right"

        # Verify (0, 1): LTR preserved, effective alignment is left
        c01 = sh_read.get_cell(0, 1)
        assert c01 is not None
        assert c01.text_direction == "ltr"
        assert c01.get_effective_align_h() == "left"

        # Verify (0, 2): Explicit right alignment preserved
        c02 = sh_read.get_cell(0, 2)
        assert c02 is not None
        assert c02.align_h == "right"
        assert c02.get_effective_align_h() == "right"

        # Verify (0, 3): Explicit center alignment on number preserved
        c03 = sh_read.get_cell(0, 3)
        assert c03 is not None
        assert c03.align_h == "center"
        assert c03.get_effective_align_h() == "center"

        # Verify (0, 4): Number in General format remains General, effective right
        c04 = sh_read.get_cell(0, 4)
        assert c04 is not None
        assert c04.align_h == "general"
        assert c04.get_effective_align_h() == "right"

        # Verify (0, 5): Boolean in General format remains General, effective center
        c05 = sh_read.get_cell(0, 5)
        assert c05 is not None
        assert c05.align_h == "general"
        assert c05.get_effective_align_h() == "center"

    finally:
        if tmp_path.exists():
            tmp_path.unlink()
