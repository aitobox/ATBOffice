"""Unit tests for cell alignment resolution under General format and explicit overrides."""

import datetime
from decimal import Decimal
import pytest

from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel


class TestCellAlignmentResolution:
    """Test suite verifying default and explicit alignment rules matching Excel."""

    def test_numeric_defaults_to_right(self):
        """Numbers (int, float, Decimal) in General format should be right-aligned."""
        for val in [0, 42, -2012, 3.14, -0.99, Decimal("123.45")]:
            cell = CellData(value=val, align_h="general")
            assert cell.get_effective_align_h() == "right"

    def test_date_and_time_defaults_to_right(self):
        """Date and time objects in General format should be right-aligned."""
        cell_date = CellData(value=datetime.date(2026, 11, 7), align_h="general")
        assert cell_date.get_effective_align_h() == "right"

        cell_dt = CellData(value=datetime.datetime(2026, 11, 7, 9, 30), align_h="general")
        assert cell_dt.get_effective_align_h() == "right"

        cell_time = CellData(value=datetime.time(9, 30, 0), align_h="general")
        assert cell_time.get_effective_align_h() == "right"

    def test_boolean_defaults_to_center(self):
        """Boolean values (True, False, or string representations) should be center-aligned."""
        for val in [True, False, "TRUE", "FALSE"]:
            cell = CellData(value=val, align_h="general")
            assert cell.get_effective_align_h() == "center"

    def test_error_values_default_to_center(self):
        """Standard Excel errors should be center-aligned."""
        errors = [
            "#NULL!",
            "#DIV/0!",
            "#VALUE!",
            "#REF!",
            "#NAME?",
            "#NUM!",
            "#N/A",
            "#SPILL!",
            "#CALC!",
            "#GETTING_DATA",
        ]
        for err in errors:
            cell = CellData(value=err, align_h="general")
            assert cell.get_effective_align_h() == "center"

    def test_text_defaults_to_left(self):
        """Standard text strings in General format should be left-aligned."""
        for text in ["Hello", "World", "Calc is great", "123 Main St"]:
            cell = CellData(value=text, align_h="general")
            assert cell.get_effective_align_h() == "left"

    def test_explicit_alignments_override_default(self):
        """Explicit horizontal alignments must override default type-based alignments."""
        # Number explicitly left-aligned
        cell_num_left = CellData(value=100, align_h="left")
        assert cell_num_left.get_effective_align_h() == "left"

        # Number explicitly center-aligned
        cell_num_center = CellData(value=100, align_h="center")
        assert cell_num_center.get_effective_align_h() == "center"

        # Text explicitly right-aligned
        cell_text_right = CellData(value="Header", align_h="right")
        assert cell_text_right.get_effective_align_h() == "right"

        # Boolean explicitly left-aligned
        cell_bool_left = CellData(value=True, align_h="left")
        assert cell_bool_left.get_effective_align_h() == "left"

        # Error explicitly right-aligned
        cell_err_right = CellData(value="#N/A", align_h="right")
        assert cell_err_right.get_effective_align_h() == "right"

    def test_rtl_text_direction(self):
        """RTL text direction should align General text to the right, while preserving numbers and explicit alignment."""
        # Normal text in RTL becomes right-aligned
        cell_rtl_text = CellData(value="مرحبا", align_h="general", text_direction="rtl")
        assert cell_rtl_text.get_effective_align_h() == "right"

        # Numbers in RTL remain right-aligned
        cell_rtl_num = CellData(value=42, align_h="general", text_direction="rtl")
        assert cell_rtl_num.get_effective_align_h() == "right"

        # Booleans in RTL remain centered
        cell_rtl_bool = CellData(value=True, align_h="general", text_direction="rtl")
        assert cell_rtl_bool.get_effective_align_h() == "center"

        # Explicit left in RTL remains left
        cell_rtl_left = CellData(value="مرحبا", align_h="left", text_direction="rtl")
        assert cell_rtl_left.get_effective_align_h() == "left"

    def test_vertical_alignment_resolution(self):
        """Vertical alignment resolution should handle top, center, bottom."""
        for v in ["top", "center", "bottom"]:
            cell = CellData(value="Sample", align_v=v)
            assert cell.get_effective_align_v() == v

    def test_sheet_data_model_effective_alignment(self):
        """SheetDataModel should provide convenient access to effective alignment."""
        sheet = SheetDataModel()
        sheet.set_cell(0, 0, CellData(value=-2012, align_h="general"))
        sheet.set_cell(0, 1, CellData(value="Title", align_h="general"))
        sheet.set_cell(0, 2, CellData(value=True, align_h="general"))
        sheet.set_cell(0, 3, CellData(value="#N/A", align_h="general"))

        assert sheet.get_effective_alignment(0, 0) == ("right", "bottom")
        assert sheet.get_effective_alignment(0, 1) == ("left", "bottom")
        assert sheet.get_effective_alignment(0, 2) == ("center", "bottom")
        assert sheet.get_effective_alignment(0, 3) == ("center", "bottom")

        # Empty cell
        assert sheet.get_effective_alignment(10, 10) == ("left", "bottom")
