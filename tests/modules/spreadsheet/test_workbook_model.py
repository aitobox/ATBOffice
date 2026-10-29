"""Unit tests for WorkbookModel multi-sheet container architecture."""

import pytest

from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import (
    WorkbookModel,
    is_valid_sheet_name,
)


class TestWorkbookModel:
    """Test suite for WorkbookModel lifecycle, mutations, and signals."""

    def test_default_workbook(self, qapp):
        wb = WorkbookModel()
        assert len(wb) == 1
        assert len(wb.sheets) == 1
        assert wb.active_sheet_index == 0
        assert wb.active_sheet.name == "Sheet1"
        assert wb[0] is wb.active_sheet

    def test_custom_initialization(self, qapp):
        s1 = SheetDataModel(name="Alpha")
        s2 = SheetDataModel(name="Beta")
        wb = WorkbookModel(sheets=[s1, s2])
        assert len(wb) == 2
        assert wb[0].name == "Alpha"
        assert wb[1].name == "Beta"
        assert wb.active_sheet_index == 0
        assert wb.active_sheet is s1

    def test_add_sheet_auto_naming(self, qapp):
        wb = WorkbookModel()
        added_signals = []
        wb.sheet_added.connect(lambda idx, name: added_signals.append((idx, name)))

        s2 = wb.add_sheet()
        assert s2.name == "Sheet2"
        assert len(wb) == 2
        assert wb[1] is s2
        assert added_signals == [(1, "Sheet2")]

        s3 = wb.add_sheet()
        assert s3.name == "Sheet3"
        assert len(wb) == 3

    def test_add_sheet_explicit_name_and_index(self, qapp):
        wb = WorkbookModel()
        s_custom = wb.add_sheet(name="Expenses", index=0)
        assert s_custom.name == "Expenses"
        assert len(wb) == 2
        assert wb[0] is s_custom
        assert wb[1].name == "Sheet1"
        # Since inserted before active_sheet (originally at 0), active_sheet_index bumped to 1
        assert wb.active_sheet_index == 1
        assert wb.active_sheet.name == "Sheet1"

    def test_name_validation(self):
        assert is_valid_sheet_name("Sales_2026") is True
        assert is_valid_sheet_name("") is False
        assert is_valid_sheet_name("   ") is False
        assert is_valid_sheet_name("A" * 31) is True
        assert is_valid_sheet_name("A" * 32) is False

        # Illegal chars: : \ / ? * [ ]
        for ch in [":", "\\", "/", "?", "*", "[", "]"]:
            assert is_valid_sheet_name(f"Sheet{ch}1") is False

        # Single quote start/end
        assert is_valid_sheet_name("'Sales'") is False
        assert is_valid_sheet_name("Sales'") is False
        assert is_valid_sheet_name("'Sales") is False

    def test_add_duplicate_sheet_name_raises(self, qapp):
        wb = WorkbookModel()
        with pytest.raises(ValueError, match="already exists"):
            wb.add_sheet("Sheet1")
        with pytest.raises(ValueError, match="already exists"):
            wb.add_sheet("sheet1")  # Case-insensitive

    def test_add_invalid_sheet_name_raises(self, qapp):
        wb = WorkbookModel()
        with pytest.raises(ValueError, match="Invalid sheet name"):
            wb.add_sheet("Test:Sheet")
        with pytest.raises(ValueError, match="Invalid sheet name"):
            wb.add_sheet("X" * 35)

    def test_remove_sheet(self, qapp):
        wb = WorkbookModel()
        s2 = wb.add_sheet("Sheet2")
        wb.add_sheet("Sheet3")
        assert len(wb) == 3

        removed_signals = []
        wb.sheet_removed.connect(lambda idx, name: removed_signals.append((idx, name)))

        # Remove middle sheet
        removed = wb.remove_sheet(1)
        assert removed is s2
        assert len(wb) == 2
        assert wb[0].name == "Sheet1"
        assert wb[1].name == "Sheet3"
        assert removed_signals == [(1, "Sheet2")]

    def test_remove_active_sheet_adjusts_active_index(self, qapp):
        wb = WorkbookModel()
        wb.add_sheet("Sheet2")
        wb.add_sheet("Sheet3")

        wb.set_active_sheet_index(1)  # active is Sheet2
        active_changed = []
        wb.active_sheet_changed.connect(lambda idx: active_changed.append(idx))

        # Remove current active sheet (index 1)
        wb.remove_sheet(1)
        # New active index should clamp to 1 (which is now Sheet3)
        assert wb.active_sheet_index == 1
        assert wb.active_sheet.name == "Sheet3"
        assert active_changed == [1]

    def test_remove_sheet_before_active_adjusts_index(self, qapp):
        wb = WorkbookModel()
        wb.add_sheet("Sheet2")
        wb.add_sheet("Sheet3")

        wb.set_active_sheet_index(2)  # active is Sheet3
        wb.remove_sheet(0)  # remove Sheet1
        assert wb.active_sheet_index == 1
        assert wb.active_sheet.name == "Sheet3"

    def test_cannot_remove_last_remaining_sheet(self, qapp):
        wb = WorkbookModel()
        assert len(wb) == 1
        with pytest.raises(ValueError, match="Cannot remove the only remaining worksheet"):
            wb.remove_sheet(0)

    def test_remove_sheet_out_of_bounds(self, qapp):
        wb = WorkbookModel()
        wb.add_sheet("Sheet2")
        with pytest.raises(IndexError):
            wb.remove_sheet(-1)
        with pytest.raises(IndexError):
            wb.remove_sheet(5)

    def test_rename_sheet(self, qapp):
        wb = WorkbookModel()
        wb.add_sheet("Sheet2")

        renamed_signals = []
        wb.sheet_renamed.connect(
            lambda idx, old_n, new_n: renamed_signals.append((idx, old_n, new_n))
        )

        wb.rename_sheet(0, "Summary")
        assert wb[0].name == "Summary"
        assert renamed_signals == [(0, "Sheet1", "Summary")]

        # No-op if same name
        wb.rename_sheet(0, "Summary")
        assert len(renamed_signals) == 1

        # Error if rename to existing sheet
        with pytest.raises(ValueError, match="already exists"):
            wb.rename_sheet(0, "sheet2")

    def test_move_sheet(self, qapp):
        wb = WorkbookModel()
        s2 = wb.add_sheet("Sheet2")
        s3 = wb.add_sheet("Sheet3")

        # Sheets: [Sheet1, Sheet2, Sheet3]
        wb.set_active_sheet_index(1)  # Active is Sheet2

        moved_signals = []
        wb.sheet_moved.connect(lambda f, t: moved_signals.append((f, t)))

        # Move Sheet2 (index 1) to index 0
        wb.move_sheet(1, 0)
        # Sheets should now be [Sheet2, Sheet1, Sheet3]
        assert wb[0] is s2
        assert wb[1].name == "Sheet1"
        assert wb[2] is s3
        # Active sheet must still be Sheet2, now at index 0
        assert wb.active_sheet is s2
        assert wb.active_sheet_index == 0
        assert moved_signals == [(1, 0)]

    def test_get_sheet_by_name_and_index(self, qapp):
        wb = WorkbookModel()
        s2 = wb.add_sheet("Data2026")

        assert wb.get_sheet_by_name("data2026") is s2
        assert wb.get_sheet_by_name("DATA2026") is s2
        assert wb.get_sheet_by_name("nonexistent") is None
        assert wb.get_sheet_by_name("") is None

        assert wb.sheet_index(s2) == 1
        dummy = SheetDataModel("Dummy")
        assert wb.sheet_index(dummy) == -1

    def test_set_active_sheet(self, qapp):
        wb = WorkbookModel()
        s2 = wb.add_sheet("Sheet2")

        wb.set_active_sheet(s2)
        assert wb.active_sheet_index == 1
        assert wb.active_sheet is s2

        dummy = SheetDataModel("Dummy")
        with pytest.raises(ValueError, match="not found"):
            wb.set_active_sheet(dummy)
