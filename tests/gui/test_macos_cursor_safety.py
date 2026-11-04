"""Tests for macOS safe cursor adaptation in GridViewport and ObjectLayer."""

import sys
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    FloatingObject,
    HandleType,
    SpreadsheetObjectLayer,
)
from atboffice.platform.cursors import get_safe_cursor


@pytest.fixture
def viewport(qapp: QApplication) -> GridViewport:
    model = SheetDataModel()
    vp = GridViewport(model=model)
    vp.resize(800, 600)
    return vp


def test_grid_viewport_border_safe_cursor(viewport: GridViewport) -> None:
    """Hovering over selection border must use safe cursor (OpenHandCursor on macOS)."""
    viewport.selection.select_cell(1, 1)
    viewport.selection.extend_to(2, 2)

    pr = viewport.selection.primary_range
    sx = viewport.horizontalScrollBar().value()
    sy = viewport.verticalScrollBar().value()
    x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.min_c) - sx
    x2 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.max_c + 1) - sx
    y1 = viewport.col_header_height + viewport.geometry_mapper.row_pos(pr.min_r) - sy
    mid_x = (x1 + x2) // 2

    hit = viewport.hit_test(mid_x, y1)
    assert hit.zone == HitZone.BORDER

    hover = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(mid_x, y1),
        QPointF(mid_x, y1),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.mouseMoveEvent(hover)

    expected = get_safe_cursor(Qt.CursorShape.SizeAllCursor)
    actual = viewport.viewport().cursor().shape()
    assert actual == expected

    if sys.platform == "darwin":
        assert actual == Qt.CursorShape.OpenHandCursor
        assert actual != Qt.CursorShape.SizeAllCursor


def test_grid_viewport_drag_border_safe_cursor(viewport: GridViewport) -> None:
    """Starting range border drag must use safe cursor (OpenHandCursor on macOS)."""
    viewport.selection.select_cell(1, 1)
    viewport.selection.extend_to(2, 2)

    pr = viewport.selection.primary_range
    sx = viewport.horizontalScrollBar().value()
    sy = viewport.verticalScrollBar().value()
    x1 = viewport.row_header_width + viewport.geometry_mapper.col_pos(pr.min_c) - sx
    y1 = viewport.col_header_height + viewport.geometry_mapper.row_pos(pr.min_r) - sy
    grab_x = x1 + 10

    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(grab_x, y1),
        QPointF(grab_x, y1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    viewport.mousePressEvent(press)
    assert viewport.is_dragging
    assert viewport._drag_mode == HitZone.BORDER

    expected = get_safe_cursor(Qt.CursorShape.SizeAllCursor)
    actual = viewport.viewport().cursor().shape()
    assert actual == expected

    if sys.platform == "darwin":
        assert actual == Qt.CursorShape.OpenHandCursor
        assert actual != Qt.CursorShape.SizeAllCursor


def test_object_layer_body_safe_cursor(qapp: QApplication) -> None:
    """Hovering over object body must use safe cursor (OpenHandCursor on macOS)."""
    model = SheetDataModel(name="TestSheet")
    layer = SpreadsheetObjectLayer(model=model)
    layer.resize(800, 600)

    obj = FloatingObject(
        id=1,
        name="Shape1",
        anchor_type=AnchorType.ABSOLUTE,
        abs_rect=(100, 100, 150, 150),
    )
    layer.add_object(obj)
    layer.select_object(obj)

    # Center of object is (175, 175) -> HandleType.BODY
    hit_obj, handle = layer.hit_test(175, 175)
    assert hit_obj == obj
    assert handle == HandleType.BODY

    hover = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(175, 175),
        QPointF(175, 175),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    layer.mouseMoveEvent(hover)

    expected = get_safe_cursor(Qt.CursorShape.SizeAllCursor)
    actual = layer.cursor().shape()
    assert actual == expected

    if sys.platform == "darwin":
        assert actual == Qt.CursorShape.OpenHandCursor
        assert actual != Qt.CursorShape.SizeAllCursor
