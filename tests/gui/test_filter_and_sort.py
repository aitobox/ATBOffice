"""GUI tests for SortDialog, FilterDropdown, and AutoFilter GridViewport integration."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.dialogs.sort_dialog import SortDialog
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


@pytest.fixture
def populated_model() -> SheetDataModel:
    model = SheetDataModel()
    # Headers
    model.set_cell_value(0, 0, "Product")
    model.set_cell_value(0, 1, "Category")
    model.set_cell_value(0, 2, "Price")

    # Row 1
    model.set_cell_value(1, 0, "Laptop")
    model.set_cell_value(1, 1, "Electronics")
    model.set_cell_value(1, 2, 1200)

    # Row 2
    model.set_cell_value(2, 0, "Mouse")
    model.set_cell_value(2, 1, "Electronics")
    model.set_cell_value(2, 2, 25)

    # Row 3
    model.set_cell_value(3, 0, "Desk")
    model.set_cell_value(3, 1, "Furniture")
    model.set_cell_value(3, 2, 300)

    return model


class TestSortDialog:
    """GUI tests for SortDialog."""

    def test_sort_dialog_initialization(
        self, qapp: QApplication, populated_model: SheetDataModel
    ) -> None:
        dlg = SortDialog(populated_model, r1=0, c1=0, r2=3, c2=2)
        assert dlg.has_header() is True
        assert dlg.is_case_sensitive() is False

        # Primary combo has 3 columns: Product, Category, Price
        assert dlg.combo_primary.count() == 3
        assert dlg.combo_primary.itemText(0) == "Product"
        assert dlg.combo_primary.itemText(1) == "Category"
        assert dlg.combo_primary.itemText(2) == "Price"

        # Secondary & third combos have 4 items ((none) + 3 cols)
        assert dlg.combo_sec.count() == 4
        assert dlg.combo_sec.itemData(0) is None
        assert dlg.combo_third.count() == 4

        dlg.retranslate_ui()

    def test_sort_dialog_toggle_header(
        self, qapp: QApplication, populated_model: SheetDataModel
    ) -> None:
        dlg = SortDialog(populated_model, r1=0, c1=0, r2=3, c2=2)

        # Switch to No header row
        dlg.radio_no_header.setChecked(True)
        assert dlg.has_header() is False

        # Now items should be named Column A, Column B, Column C
        assert "A" in dlg.combo_primary.itemText(0)
        assert "B" in dlg.combo_primary.itemText(1)
        assert "C" in dlg.combo_primary.itemText(2)

    def test_sort_dialog_get_keys(
        self, qapp: QApplication, populated_model: SheetDataModel
    ) -> None:
        dlg = SortDialog(populated_model, r1=0, c1=0, r2=3, c2=2)

        # Primary: col 1 (Category), ascending
        dlg.combo_primary.setCurrentIndex(1)
        dlg.p_radio_asc.setChecked(True)

        # Secondary: col 2 (Price), descending (index 3 is Price)
        dlg.combo_sec.setCurrentIndex(3)
        dlg.sec_radio_desc.setChecked(True)

        # Third: none
        dlg.combo_third.setCurrentIndex(0)

        keys = dlg.get_sort_keys()
        assert len(keys) == 2
        assert keys[0] == (1, False)
        assert keys[1] == (2, True)


class TestFilterDropdown:
    """GUI tests for FilterDropdown and its dialogs."""

    def test_filter_dropdown_items(
        self, qapp: QApplication, populated_model: SheetDataModel
    ) -> None:
        from atboffice.modules.spreadsheet.models.filter_model import AutoFilter
        from atboffice.modules.spreadsheet.views.filter_dropdown import (
            FilterDropdown,
        )

        af = AutoFilter(r1=0, c1=0, r2=3, c2=2)
        dropdown = FilterDropdown(populated_model, af, col=1)  # Category column

        # Categories: Electronics, Furniture
        assert "Electronics" in dropdown.unique_values
        assert "Furniture" in dropdown.unique_values

        # Check list items: (Select All), Electronics, Furniture
        assert dropdown.list_widget.count() == 3

        # Test selecting unique value and applying
        # Uncheck Electronics, keep Furniture
        dropdown.value_items[0][0].setCheckState(Qt.CheckState.Unchecked)

        emitted_crit = []
        dropdown.filter_applied.connect(lambda crit: emitted_crit.append(crit))

        dropdown._on_apply_checked()
        assert len(emitted_crit) == 1
        assert "Furniture" in emitted_crit[0].values
        assert "Electronics" not in emitted_crit[0].values

    def test_top10_dialog(self, qapp: QApplication) -> None:
        from atboffice.modules.spreadsheet.views.filter_dropdown import (
            Top10FilterDialog,
        )

        dlg = Top10FilterDialog()
        dlg.spin_count.setValue(5)
        dlg.combo_top_bottom.setCurrentIndex(1)  # Bottom
        dlg.combo_kind.setCurrentIndex(1)  # Percent

        is_top, count, is_percent = dlg.get_criteria()
        assert is_top is False
        assert count == 5
        assert is_percent is True

    def test_custom_filter_dialog(self, qapp: QApplication) -> None:
        from atboffice.modules.spreadsheet.views.filter_dropdown import (
            CustomFilterDialog,
        )

        dlg = CustomFilterDialog(
            column_header="Price",
            unique_values=["25", "300", "1200"],
        )
        dlg.op1.setCurrentIndex(dlg.op1.findData("greaterThan"))
        dlg.val1.setCurrentText("100")

        dlg.op2.setCurrentIndex(dlg.op2.findData("lessThan"))
        dlg.val2.setCurrentText("1000")

        dlg.radio_and.setChecked(True)

        conds, is_and = dlg.get_custom_criteria()
        assert len(conds) == 2
        assert conds[0] == ("greaterThan", "100")
        assert conds[1] == ("lessThan", "1000")
        assert is_and is True


class TestGridViewportFilterIntegration:
    """GUI tests for AutoFilter and Sort integration inside GridViewport."""

    def test_viewport_toggle_autofilter(
        self, qapp: QApplication, populated_model: SheetDataModel
    ) -> None:
        from atboffice.modules.spreadsheet.views.grid_viewport import (
            GridViewport,
        )

        vp = GridViewport(model=populated_model)
        vp.resize(800, 600)

        assert getattr(populated_model, "auto_filter", None) is None

        # Toggle on
        vp.toggle_auto_filter()
        af = populated_model.auto_filter
        assert af is not None
        assert af.r1 == 0
        assert af.c1 == 0
        assert af.r2 == 3
        assert af.c2 == 2

        # Toggle off
        vp.toggle_auto_filter()
        assert populated_model.auto_filter is None

    def test_viewport_hit_filter_button(
        self, qapp: QApplication, populated_model: SheetDataModel
    ) -> None:
        from atboffice.modules.spreadsheet.views.grid_viewport import (
            GridViewport,
            HitZone,
        )

        vp = GridViewport(model=populated_model)
        vp.resize(800, 600)
        vp.toggle_auto_filter()

        # Cell (0, 0):
        # x is row_header_width (46) + col_pos(0) (0) = 46..46+64 = 110
        # Button is 16px wide at right edge: 110 - 16 - 1 = 93..109
        # y is col_header_height (22) + row_pos(0) (0) = 22..22+20 = 42
        # Button is 16px high at bottom edge: 42 - 16 - 1 = 25..41
        hit = vp.hit_test(100, 30)
        assert hit.zone == HitZone.FILTER_BUTTON
        assert hit.col == 0
        assert hit.row == 0

    def test_viewport_paint_with_autofilter(
        self, qapp: QApplication, populated_model: SheetDataModel
    ) -> None:
        from atboffice.modules.spreadsheet.models.filter_model import ColumnFilter
        from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport

        vp = GridViewport(model=populated_model)
        vp.resize(800, 600)
        vp.toggle_auto_filter()

        # Add active criteria on col 1 to test blue arrow painting branch
        populated_model.auto_filter.cols[1] = ColumnFilter(values={"Electronics"})

        # Repaint
        vp.viewport().update()
        qapp.processEvents()

