"""GUI tests for virtualized GridViewport."""

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def viewport(qapp: QApplication) -> GridViewport:
    model = SheetDataModel()
    vp = GridViewport(model=model)
    vp.resize(800, 600)
    return vp


class TestGridViewportInitialization:
    def test_init_and_retranslate(self, viewport: GridViewport) -> None:
        assert viewport.model is not None
        assert viewport.selection is not None
        assert viewport.geometry_mapper is not None
        viewport.retranslate_ui()


class TestCoordinateAndHitTesting:
    def test_hit_corner(self, viewport: GridViewport) -> None:
        # Corner box is 0..row_header_width, 0..col_header_height
        res = viewport.hit_test(10, 10)
        assert res.zone == HitZone.CORNER

    def test_hit_col_header(self, viewport: GridViewport) -> None:
        # Above col_header_height, right of row_header_width
        x = viewport.row_header_width + 20
        y = 10
        res = viewport.hit_test(x, y)
        assert res.zone == HitZone.COL_HEADER
        assert res.col == 0

    def test_hit_col_resize(self, viewport: GridViewport) -> None:
        # Right border of column 0
        w0 = viewport.geometry_mapper.col_size(0)
        border_x = viewport.row_header_width + w0
        res = viewport.hit_test(border_x, 10)
        assert res.zone == HitZone.COL_RESIZE
        assert res.col == 0

    def test_hit_row_header(self, viewport: GridViewport) -> None:
        # Left of row_header_width, below col_header_height
        x = 10
        y = viewport.col_header_height + 10
        res = viewport.hit_test(x, y)
        assert res.zone == HitZone.ROW_HEADER
        assert res.row == 0

    def test_hit_cell(self, viewport: GridViewport) -> None:
        x = viewport.row_header_width + 10
        y = viewport.col_header_height + 10
        res = viewport.hit_test(x, y)
        assert res.zone == HitZone.CELL
        assert (res.row, res.col) == (0, 0)


class TestMouseSelectionInteractions:
    def test_click_select_cell(self, viewport: GridViewport) -> None:
        x = viewport.row_header_width + 100
        y = viewport.col_header_height + 50
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(event)
        target_cell = viewport.cell_at_pos(x, y)
        assert viewport.selection.active_cell == target_cell

    def test_click_col_header_selects_column(self, viewport: GridViewport) -> None:
        x = viewport.row_header_width + 20
        y = 10
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(event)
        assert viewport.selection.is_col_selected(0)
        assert viewport.selection.ranges[0].min_c == 0
        assert viewport.selection.ranges[0].max_c == 0

    def test_click_row_header_selects_row(self, viewport: GridViewport) -> None:
        x = 10
        y = viewport.col_header_height + 10
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(event)
        assert viewport.selection.is_row_selected(0)
        assert viewport.selection.ranges[0].min_r == 0
        assert viewport.selection.ranges[0].max_r == 0

    def test_click_corner_selects_all(self, viewport: GridViewport) -> None:
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.mousePressEvent(event)
        assert viewport.selection.ranges[0].min_r == 0
        assert viewport.selection.ranges[0].min_c == 0
        assert viewport.selection.is_selected(100, 50)


class TestColumnAutoFitAndResize:
    def test_resize_column(self, viewport: GridViewport) -> None:
        viewport.geometry_mapper.set_col_width(0, 120)
        assert viewport.geometry_mapper.col_size(0) == 120

    def test_autofit_column(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(
            0, 0, CellData(value="Super Long Text Content That Requires Wider Column")
        )
        orig_w = viewport.geometry_mapper.col_size(0)
        viewport.auto_fit_column(0)
        new_w = viewport.geometry_mapper.col_size(0)
        assert new_w > orig_w


class TestTextRightOverflow:
    def test_overflow_calculation_empty_neighbor(self, viewport: GridViewport) -> None:
        # Cell (0, 0) has long text, cell (0, 1) is empty
        viewport.model.set_cell(
            0, 0, CellData(value="Very long text overflowing into empty neighbors")
        )
        # Check right overflow column span
        span = viewport.calculate_overflow_span(0, 0, text_width=180, col_width=64)
        assert span >= 2  # can overflow into column 1 and beyond

    def test_overflow_blocked_by_occupied_neighbor(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(0, 0, CellData(value="Very long text"))
        viewport.model.set_cell(0, 1, CellData(value="Blocked!"))
        span = viewport.calculate_overflow_span(0, 0, text_width=180, col_width=64)
        assert span == 1  # Strictly blocked to column 0


class TestKeyboardNavigation:
    def test_arrow_keys(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(0, 0)
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Down,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.keyPressEvent(event)
        assert viewport.selection.active_cell == (1, 0)

        event_right = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Right,
            Qt.KeyboardModifier.NoModifier,
        )
        viewport.keyPressEvent(event_right)
        assert viewport.selection.active_cell == (1, 1)

    def test_ctrl_a_select_all(self, viewport: GridViewport) -> None:
        viewport.selection.select_cell(2, 2)
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_A,
            Qt.KeyboardModifier.ControlModifier,
        )
        viewport.keyPressEvent(event)
        assert viewport.selection.is_selected(0, 0)
        assert viewport.selection.is_selected(999, 100)
