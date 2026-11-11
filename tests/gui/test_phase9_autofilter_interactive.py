"""Interactive GUI tests for AutoFilter classic column dropdown with checkbox search tree.

Verifies Phase 9 requirements for Issue #338:
- FilterDropdownPopup component with instant search filter
- Select all search results behavior
- Numeric vs text unique value aggregation sorting
- Status bar "M of N records found"
- Undo/Redo of filter application without mutating cell contents
- Full i18n support
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.filter_model import AutoFilter, ColumnFilter
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.views.filter_dropdown import (
    FilterDropdown,
    FilterDropdownPopup,
)
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


@pytest.fixture
def sales_model() -> SheetDataModel:
    """Fixture providing a sample dataset for AutoFilter testing."""
    model = SheetDataModel()
    # Headers in Row 0
    model.set_cell_value(0, 0, "ID")
    model.set_cell_value(0, 1, "City")
    model.set_cell_value(0, 2, "Sales")

    # Data Rows 1 to 5
    data = [
        (1, 10, "Tokyo", 250),
        (2, 2, "Paris", 1200),
        (3, 100, "Tokyo", 30),
        (4, 1, "London", 800),
        (5, 20, "Paris", 450),
    ]
    for r, id_val, city_val, sales_val in data:
        model.set_cell_value(r, 0, id_val)
        model.set_cell_value(r, 1, city_val)
        model.set_cell_value(r, 2, sales_val)

    return model


class TestPhase9AutoFilterInteractive:
    """Interactive GUI test suite for Phase 9 AutoFilter enhancements."""

    def test_filter_dropdown_popup_alias(
        self, qapp: QApplication, sales_model: SheetDataModel
    ) -> None:
        """Verify FilterDropdownPopup is available and matches FilterDropdown."""
        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        popup = FilterDropdownPopup(sales_model, af, col=1)
        assert isinstance(popup, FilterDropdown)
        assert popup.search_edit is not None

    def test_filter_dropdown_search_instant_filtering(
        self, qapp: QApplication, sales_model: SheetDataModel
    ) -> None:
        """Verify search input filters displayed unique values in real time."""
        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        popup = FilterDropdownPopup(sales_model, af, col=1)  # City: London, Paris, Tokyo

        assert len(popup.value_items) == 3
        # Initially, all items are visible
        for item, _ in popup.value_items:
            assert not item.isHidden()

        # Type 'par' in search edit
        popup.search_edit.setText("par")

        # London and Tokyo should be hidden; Paris visible
        for item, val_str in popup.value_items:
            if val_str == "Paris":
                assert not item.isHidden()
            else:
                assert item.isHidden()

        # Label updates to "(Select All Search Results)"
        assert "(Select All Search Results)" in popup.item_select_all.text()

        # Clear search
        popup.search_edit.setText("")
        for item, _ in popup.value_items:
            assert not item.isHidden()
        assert "(Select All)" in popup.item_select_all.text()

    def test_filter_dropdown_select_all_search_results(
        self, qapp: QApplication, sales_model: SheetDataModel
    ) -> None:
        """Verify toggling select-all while searching affects only matching items."""
        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        popup = FilterDropdownPopup(sales_model, af, col=1)

        # Uncheck all initially
        popup.item_select_all.setCheckState(Qt.CheckState.Unchecked)
        for item, _ in popup.value_items:
            assert item.checkState() == Qt.CheckState.Unchecked

        # Filter for 'Tokyo'
        popup.search_edit.setText("Tokyo")
        # Click select-all search results
        popup.item_select_all.setCheckState(Qt.CheckState.Checked)

        # Only Tokyo should be checked; London & Paris remain unchecked
        for item, val_str in popup.value_items:
            if val_str == "Tokyo":
                assert item.checkState() == Qt.CheckState.Checked
            else:
                assert item.checkState() == Qt.CheckState.Unchecked

    def test_filter_dropdown_numeric_vs_text_sorting(
        self, qapp: QApplication, sales_model: SheetDataModel
    ) -> None:
        """Verify numeric IDs sort numerically (1, 2, 10, 20, 100) instead of alphabetically."""
        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        popup = FilterDropdownPopup(sales_model, af, col=0)  # ID column

        extracted = [val_str for _, val_str in popup.value_items]
        # In lexicographical sort, "100" would be before "2". In numeric sort, 1, 2, 10, 20, 100
        assert extracted == ["1", "2", "10", "20", "100"]

    def test_grid_viewport_filter_status_bar(
        self, qapp: QApplication, sales_model: SheetDataModel
    ) -> None:
        """Verify GridViewport updates status bar with 'M of N records found'."""
        vp = GridViewport(model=sales_model)
        vp.resize(800, 600)
        vp.toggle_auto_filter()

        af = sales_model.auto_filter
        assert af is not None

        # Filter City == 'Tokyo' (2 matching out of 5)
        vp._apply_column_filter(af, col=1, crit=ColumnFilter(values={"Tokyo"}))

        assert vp.last_status_message == "2 of 5 records found"
        # Rows 2, 4, 5 (Paris, London, Paris) should be hidden
        assert 2 in sales_model.geometry.hidden_rows
        assert 4 in sales_model.geometry.hidden_rows
        assert 5 in sales_model.geometry.hidden_rows
        # Rows 1 and 3 (Tokyo) should NOT be hidden
        assert 1 not in sales_model.geometry.hidden_rows
        assert 3 not in sales_model.geometry.hidden_rows

        # Clear filter
        vp._clear_column_filter(af, col=1)
        assert len(sales_model.geometry.hidden_rows) == 0
        assert vp.last_status_message == ""

    def test_grid_viewport_filter_undo_redo(
        self, qapp: QApplication, sales_model: SheetDataModel
    ) -> None:
        """Verify Undo/Redo of filter application without mutating cell contents."""
        vp = GridViewport(model=sales_model)
        vp.resize(800, 600)
        vp.toggle_auto_filter()
        af = sales_model.auto_filter
        assert af is not None

        # Capture original cell values
        original_cells = {k: v.value for k, v in sales_model.cells.items()}

        # 1. Apply filter on City == Paris (Rows 2 & 5 match, Rows 1, 3, 4 hidden)
        vp._apply_column_filter(af, col=1, crit=ColumnFilter(values={"Paris"}))
        assert vp.last_status_message == "2 of 5 records found"
        assert {1, 3, 4}.issubset(sales_model.geometry.hidden_rows)

        # 2. Undo filter
        vp.undo()
        # Verify hidden rows are cleared
        assert len(sales_model.geometry.hidden_rows) == 0
        # Verify cell values are completely intact and untouched
        for k, v in original_cells.items():
            assert sales_model.get_cell_value(k[0], k[1]) == v

        # 3. Redo filter
        vp.redo()
        assert {1, 3, 4}.issubset(sales_model.geometry.hidden_rows)
        assert vp.last_status_message == "2 of 5 records found"
        for k, v in original_cells.items():
            assert sales_model.get_cell_value(k[0], k[1]) == v

    def test_filter_dropdown_retranslate_ui(
        self, qapp: QApplication, sales_model: SheetDataModel
    ) -> None:
        """Verify retranslate_ui executes cleanly without error."""
        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        popup = FilterDropdownPopup(sales_model, af, col=1)
        popup.retranslate_ui()
