"""GUI automation tests for In-Cell Editor, FormulaBar, and AutoCalculate StatusBar."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
)
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.spreadsheet.views.editor_controller import (
    HIGHLIGHT_PALETTE,
    EditorMode,
)
from atboffice.modules.spreadsheet.views.formula_bar import FormulaBar
from atboffice.ui.components.status_bar import StatusBar
from atboffice.ui.shell.main_window import MainWindow


@pytest.fixture
def spreadsheet_view(qapp: QApplication) -> SpreadsheetView:
    view = SpreadsheetView()
    view.resize(900, 600)
    return view


@pytest.fixture
def status_bar(qapp: QApplication) -> StatusBar:
    sb = StatusBar()
    sb.resize(600, 30)
    return sb


class TestFormulaBar:
    """Test FormulaBar component controls, events, and navigation."""

    def test_initial_state_and_retranslate(self, qapp: QApplication) -> None:
        fb = FormulaBar()
        assert fb.name_box.text() == ""
        assert not fb.btn_cancel.isEnabled()
        assert not fb.btn_commit.isEnabled()
        assert fb.formula_input.text() == ""
        fb.retranslate_ui()

    def test_name_box_navigation(self, qapp: QApplication) -> None:
        fb = FormulaBar()
        nav_coords: list[tuple[int, int]] = []
        range_coords: list[tuple[int, int, int, int]] = []

        fb.navigate_requested.connect(lambda r, c: nav_coords.append((r, c)))
        fb.range_navigate_requested.connect(
            lambda r1, c1, r2, c2: range_coords.append((r1, c1, r2, c2))
        )

        # Single cell jump
        fb.name_box.setText("B5")
        fb._on_name_box_return()
        assert len(nav_coords) == 1
        assert nav_coords[0] == (4, 1)

        # Range jump
        fb.name_box.setText("A1:C10")
        fb._on_name_box_return()
        assert len(range_coords) == 1
        assert range_coords[0] == (0, 0, 9, 2)

    def test_button_signals(self, qapp: QApplication) -> None:
        fb = FormulaBar()
        fb.set_editing_state(True)
        canceled = False
        committed = False
        fx_clicked = False

        def on_cancel():
            nonlocal canceled
            canceled = True

        def on_commit():
            nonlocal committed
            committed = True

        def on_fx():
            nonlocal fx_clicked
            fx_clicked = True

        fb.cancel_requested.connect(on_cancel)
        fb.commit_requested.connect(on_commit)
        fb.fx_requested.connect(on_fx)

        fb.btn_cancel.click()
        assert canceled
        fb.btn_commit.click()
        assert committed
        fb.btn_fx.click()
        assert fx_clicked


class TestEditorControllerAndTwoWayBinding:
    """Test in-cell editor, FormulaBar synchronization, and commit/cancel."""

    def test_activate_via_double_click_and_f2(
        self, spreadsheet_view: SpreadsheetView, qtbot
    ) -> None:
        view = spreadsheet_view
        ctrl = view.editor_controller
        assert not ctrl.is_active

        # Double click cell (1, 1)
        view.grid.cell_double_clicked.emit(1, 1)
        assert ctrl.is_active
        assert ctrl.active_row == 1
        assert ctrl.active_col == 1
        assert not ctrl.in_cell_editor.isHidden()
        assert view.formula_bar.btn_commit.isEnabled()

        ctrl.cancel()
        assert not ctrl.is_active
        assert ctrl.in_cell_editor.isHidden()

        # Press F2
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_F2,
            Qt.KeyboardModifier.NoModifier,
        )
        view.grid.keyPressEvent(event)
        assert ctrl.is_active
        ctrl.cancel()

    def test_two_way_text_synchronization(
        self, spreadsheet_view: SpreadsheetView
    ) -> None:
        view = spreadsheet_view
        ctrl = view.editor_controller

        # Begin edit
        ctrl.begin_edit(0, 0, mode=EditorMode.EDIT)

        # 1. Type in in-cell editor -> FormulaBar updates
        ctrl.in_cell_editor.setText("Alpha")
        assert view.formula_bar.text() == "Alpha"

        # 2. Type in FormulaBar -> in-cell editor updates
        view.formula_bar.formula_input.setText("Beta")
        assert ctrl.in_cell_editor.text() == "Beta"

        ctrl.commit()
        assert view.model.get_cell_value(0, 0) == "Beta"

    def test_commit_number_and_formula(
        self, spreadsheet_view: SpreadsheetView
    ) -> None:
        view = spreadsheet_view
        ctrl = view.editor_controller

        # Commit numeric value
        ctrl.begin_edit(0, 0, mode=EditorMode.EDIT)
        ctrl.in_cell_editor.setText("123.45")
        ctrl.commit()
        assert view.model.get_cell_value(0, 0) == 123.45

        # Commit formula: =10+20
        ctrl.begin_edit(0, 1, mode=EditorMode.EDIT)
        ctrl.in_cell_editor.setText("=10+20")
        ctrl.commit()
        cell = view.model.get_cell(0, 1)
        assert cell is not None
        assert cell.formula == "10+20"
        assert cell.value == 30.0

    def test_cancel_reverts_original_value(
        self, spreadsheet_view: SpreadsheetView
    ) -> None:
        view = spreadsheet_view
        ctrl = view.editor_controller

        view.model.set_cell_value(2, 2, "Original")
        ctrl.begin_edit(2, 2, mode=EditorMode.EDIT)
        ctrl.in_cell_editor.setText("Modified")
        ctrl.cancel()

        assert view.model.get_cell_value(2, 2) == "Original"
        assert not ctrl.is_active


class TestPointModeAndReferenceHighlighting:
    """Test formula Point Mode and colored reference highlights."""

    def test_point_cell_and_range_insertion(
        self, spreadsheet_view: SpreadsheetView
    ) -> None:
        view = spreadsheet_view
        ctrl = view.editor_controller

        # Start formula
        ctrl.begin_edit(0, 0, mode=EditorMode.ENTER, initial_text="=")
        assert ctrl.mode == EditorMode.POINT

        # Point at cell (1, 1) -> B2
        ctrl.point_at(1, 1, 1, 1)
        assert ctrl.in_cell_editor.text() == "=B2"
        assert len(ctrl.highlights) == 1
        assert ctrl.highlights[0].r1 == 1
        assert ctrl.highlights[0].c1 == 1
        assert ctrl.highlights[0].color == HIGHLIGHT_PALETTE[0]

        # Drag over range (1, 1) to (3, 2) -> B2:C4
        ctrl.point_at(1, 1, 3, 2)
        assert ctrl.in_cell_editor.text() == "=B2:C4"
        assert len(ctrl.highlights) == 1
        assert ctrl.highlights[0].r2 == 3
        assert ctrl.highlights[0].c2 == 2

        # Append operator and point another cell
        ctrl.in_cell_editor.setText("=B2:C4 + ")
        ctrl.point_at(5, 5, 5, 5)  # F6
        assert ctrl.in_cell_editor.text() == "=B2:C4 + F6"
        assert len(ctrl.highlights) == 2
        assert ctrl.highlights[0].color == HIGHLIGHT_PALETTE[0]
        assert ctrl.highlights[1].color == HIGHLIGHT_PALETTE[1]

        ctrl.commit()
        assert not ctrl.is_active
        assert len(ctrl.highlights) == 0


class TestAutoCalculateStatusBar:
    """Test StatusBar mode transitions and selection aggregation."""

    def test_mode_indicator(self, status_bar: StatusBar) -> None:
        sb = status_bar
        sb.set_mode("ready")
        assert "就绪" in sb.lbl_mode.text()

        sb.set_mode("edit")
        assert "编辑" in sb.lbl_mode.text()

        sb.set_mode("point")
        assert "点选" in sb.lbl_mode.text()

    def test_autocalculate_aggregations(self, qapp: QApplication) -> None:
        sb = StatusBar()
        model = SheetDataModel()
        sel = SelectionModel()

        # Populate test numbers
        model.set_cell_value(0, 0, 10)
        model.set_cell_value(0, 1, 20)
        model.set_cell_value(1, 0, 30)
        model.set_cell_value(1, 1, "text")

        # Select range (0, 0) to (1, 1)
        sel.select_cell(0, 0)
        sel.extend_to(1, 1)

        # 1. Sum (Default)
        sb.set_calc_function("SUM")
        sb.update_calculation(model, sel)
        assert "求和=60" in sb.lbl_calc.text()

        # 2. Average
        sb.set_calc_function("AVERAGE")
        assert "平均值=20" in sb.lbl_calc.text()

        # 3. Count nums
        sb.set_calc_function("COUNT")
        assert "数值计数=3" in sb.lbl_calc.text()

        # 4. Count all
        sb.set_calc_function("COUNTA")
        assert "计数=4" in sb.lbl_calc.text()

        # 5. Max
        sb.set_calc_function("MAX")
        assert "最大值=30" in sb.lbl_calc.text()

        # 6. Min
        sb.set_calc_function("MIN")
        assert "最小值=10" in sb.lbl_calc.text()

        # 7. None
        sb.set_calc_function("NONE")
        assert sb.lbl_calc.text() == ""

    def test_single_cell_selection_hides_autocalc(
        self, qapp: QApplication
    ) -> None:
        sb = StatusBar()
        model = SheetDataModel()
        sel = SelectionModel()
        model.set_cell_value(0, 0, 100)

        sel.select_cell(0, 0)
        sb.set_calc_function("SUM")
        sb.update_calculation(model, sel)
        assert sb.lbl_calc.text() == ""


class TestMainWindowIntegration:
    """Test full integration with MainWindow shell."""

    def test_main_window_has_status_bar_and_formula_bar(
        self, qapp: QApplication
    ) -> None:
        win = MainWindow()
        assert win.status_bar is not None
        assert win.spreadsheet_view.formula_bar is not None
        assert win.spreadsheet_view.editor_controller is not None
