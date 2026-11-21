"""Ledger grid zoom: painting, hit testing, editing and drawings honour the view zoom.

Grid geometry stays in unzoomed pixels and is scaled once at the paint/input
boundary (ledger/js/render.js multiplies the same geometry by the zoom).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.views.editor_controller import EditorController
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport, HitZone
from atboffice.modules.spreadsheet.views.object_layer import (
    CellAnchorPoint,
    FloatingObject,
    SpreadsheetObjectLayer,
)

ZOOMS = [0.5, 0.75, 1.5, 2.0]


def _grid(qtbot, sheet: SheetDataModel | None = None, w: int = 800, h: int = 500) -> GridViewport:
    vp = GridViewport(model=sheet or SheetDataModel())
    vp.resize(w, h)
    qtbot.addWidget(vp)
    return vp


def _mouse(vp: GridViewport, kind, pos: QPoint, buttons=Qt.MouseButton.LeftButton) -> None:
    is_move = kind == QMouseEvent.Type.MouseMove
    button = Qt.MouseButton.NoButton if is_move else Qt.MouseButton.LeftButton
    ev = QMouseEvent(
        kind,
        QPointF(pos),
        QPointF(vp.viewport().mapToGlobal(pos)),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    if kind == QMouseEvent.Type.MouseButtonPress:
        vp.mousePressEvent(ev)
    elif kind == QMouseEvent.Type.MouseMove:
        vp.mouseMoveEvent(ev)
    else:
        vp.mouseReleaseEvent(ev)


def _click(vp: GridViewport, pos: QPoint) -> None:
    _mouse(vp, QMouseEvent.Type.MouseButtonPress, pos)
    _mouse(vp, QMouseEvent.Type.MouseButtonRelease, pos, Qt.MouseButton.NoButton)


def _render(vp: GridViewport) -> QImage:
    img = QImage(vp.viewport().size(), QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        vp._render_paint_event(painter, None)
    finally:
        painter.end()
    return img


# ---------------------------------------------------------------- zoom state


def test_set_zoom_clamps_and_rounds_to_percent(qtbot) -> None:
    vp = _grid(qtbot)
    vp.set_zoom(0.01)
    assert vp.zoom == pytest.approx(0.10)
    vp.set_zoom(9)
    assert vp.zoom == pytest.approx(4.0)
    vp.set_zoom(0.7549)
    assert vp.zoom == pytest.approx(0.75)


def test_zoom_belongs_to_the_sheet(qtbot) -> None:
    a, b = SheetDataModel(), SheetDataModel()
    vp = _grid(qtbot, a)
    seen: list[float] = []
    vp.zoom_changed.connect(seen.append)
    vp.set_zoom(1.5)
    assert a.extra["zoom"] == 150
    assert a.view_state.zoom_scale == 150

    vp.set_model_and_selection(b, SelectionModel())
    assert vp.zoom == pytest.approx(1.0), "a sheet without a saved zoom shows 100%"
    vp.set_model_and_selection(a, SelectionModel())
    assert vp.zoom == pytest.approx(1.5)
    assert seen[-1] == pytest.approx(1.5)

    vp.set_zoom(1.0)
    assert "zoom" not in a.extra
    assert a.view_state.zoom_scale is None


def test_saved_zoom_scale_is_applied_on_open(qtbot) -> None:
    wb = read_xlsx("tests/docs/excel/xlsx/poi__49156.xlsx")
    sheet = wb.active_sheet
    assert sheet.extra["zoom"] == 75
    vp = _grid(qtbot, sheet)
    assert vp.zoom == pytest.approx(0.75)
    # Geometry is unchanged in grid units; it is scaled on screen.
    r, c = 9, 2
    dev = vp.device_cell_rect(r, c)
    assert dev.width() == pytest.approx(sheet.geometry.col_size(c) * 0.75, abs=1)
    assert dev.height() == pytest.approx(sheet.geometry.row_size(r) * 0.75, abs=1)


# ---------------------------------------------------------------- mapping


@pytest.mark.parametrize("z", ZOOMS)
def test_device_mapping_round_trips(qtbot, z: float) -> None:
    vp = _grid(qtbot)
    vp.set_zoom(z)
    rect = vp.cell_rect(3, 4)
    dev = vp.map_rect_to_device(rect)
    assert dev.x() == round(rect.x() * z)
    assert dev.width() == round((rect.x() + rect.width()) * z) - round(rect.x() * z)
    gx, gy = vp.map_from_device(dev.center().x(), dev.center().y())
    assert rect.contains(QPoint(gx, gy))


# ---------------------------------------------------------------- hit testing


@pytest.mark.parametrize("z", ZOOMS)
def test_click_selects_the_cell_under_the_mouse(qtbot, z: float) -> None:
    vp = _grid(qtbot)
    vp.set_zoom(z)
    for r, c in [(0, 0), (2, 1), (5, 3)]:
        dev = vp.device_cell_rect(r, c)
        assert dev.right() < vp.viewport().width() and dev.bottom() < vp.viewport().height()
        _click(vp, dev.center())
        assert vp.selection.active_cell == (r, c), (z, r, c)
        # One device pixel inside the far edge still belongs to the cell.
        inner = QPoint(dev.x() + dev.width() - 2, dev.y() + dev.height() - 2)
        hit = vp.hit_test(*vp.map_from_device(inner.x(), inner.y()))
        assert (hit.row, hit.col) == (r, c)


@pytest.mark.parametrize("z", [0.5, 2.0])
def test_headers_scale_with_zoom(qtbot, z: float) -> None:
    vp = _grid(qtbot)
    vp.set_zoom(z)
    # Inside the zoomed row header column.
    x = int(vp.row_header_width * z) - 2
    y = vp.device_cell_rect(4, 0).center().y()
    hit = vp.hit_test(*vp.map_from_device(x, y))
    assert hit.zone == HitZone.ROW_HEADER and hit.row == 4
    # Just right of the zoomed row header is a cell (at 2x the unzoomed header is wider).
    hit = vp.hit_test(*vp.map_from_device(int(vp.row_header_width * z) + 3, y))
    assert hit.zone == HitZone.CELL and hit.row == 4


@pytest.mark.parametrize("z", [0.5, 2.0])
def test_column_resize_grab_and_drag_at_zoom(qtbot, z: float) -> None:
    vp = _grid(qtbot)
    vp.set_zoom(z)
    geo = vp.geometry_mapper
    w0 = geo.col_size(1)
    edge_x = vp.device_cell_rect(0, 1).right() + 1
    hdr_y = int(vp.col_header_height * z) // 2
    # The grab tolerance stays ~3 screen pixels whatever the zoom.
    hit = vp.hit_test(*vp.map_from_device(edge_x + 2, hdr_y))
    assert hit.zone == HitZone.COL_RESIZE and hit.col == 1
    hit = vp.hit_test(*vp.map_from_device(edge_x + 8, hdr_y))
    assert hit.zone == HitZone.COL_HEADER

    _mouse(vp, QMouseEvent.Type.MouseButtonPress, QPoint(edge_x, hdr_y))
    _mouse(vp, QMouseEvent.Type.MouseMove, QPoint(edge_x + 40, hdr_y))
    end = QPoint(edge_x + 40, hdr_y)
    _mouse(vp, QMouseEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)
    # 40 screen pixels are 40 / z sheet pixels.
    assert geo.col_size(1) == pytest.approx(w0 + 40 / z, abs=2)


@pytest.mark.parametrize("z", [0.5, 2.0])
def test_frozen_panes_hit_test_after_scrolling(qtbot, z: float) -> None:
    sheet = SheetDataModel()
    vp = _grid(qtbot, sheet)
    vp.set_freeze_panes(2, 1)
    vp.set_zoom(z)
    vp.verticalScrollBar().setValue(200)
    vp.horizontalScrollBar().setValue(150)
    # Frozen cell keeps its place; a scrolled cell is wherever cell_rect says.
    for r, c in [(0, 0), (1, 0)]:
        dev = vp.device_cell_rect(r, c)
        hit = vp.hit_test(*vp.map_from_device(dev.center().x(), dev.center().y()))
        assert (hit.row, hit.col) == (r, c)
    fr = vp.device_cell_rect(1, 0)
    below = QPoint(fr.center().x(), fr.bottom() + 4)
    hit = vp.hit_test(*vp.map_from_device(below.x(), below.y()))
    assert hit.zone == HitZone.CELL
    assert hit.row >= 2, "first row below the freeze line is a scrolled row"
    dev = vp.device_cell_rect(hit.row, 0)
    assert dev.contains(below)


@pytest.mark.parametrize("z", [0.5, 2.0])
def test_scroll_range_and_reveal_use_zoomed_viewport(qtbot, z: float) -> None:
    vp = _grid(qtbot)
    vp.set_zoom(z)
    vh = vp.viewport().height()
    assert vp.verticalScrollBar().pageStep() == pytest.approx(vh / z - vp.col_header_height, abs=2)
    vp.reveal(60, 0)
    dev = vp.device_cell_rect(60, 0)
    assert dev.top() >= int(vp.col_header_height * z) - 1
    assert dev.bottom() <= vh + 1


# ---------------------------------------------------------------- painting


@pytest.mark.parametrize("z", [0.5, 2.0])
def test_paint_scales_cell_fill(qtbot, z: float) -> None:
    sheet = SheetDataModel()
    sheet.set_cell(2, 1, CellData(bg_color="#FF0000"))
    vp = _grid(qtbot, sheet)
    vp.set_zoom(z)
    img = _render(vp)
    dev = vp.device_cell_rect(2, 1)
    red = QColor(255, 0, 0)
    assert QColor(img.pixel(dev.x() + 3, dev.center().y())) == red
    assert QColor(img.pixel(dev.right() - 3, dev.center().y())) == red
    # Just outside the zoomed rect the fill must not leak.
    assert QColor(img.pixel(dev.right() + 4, dev.center().y())) != red
    assert QColor(img.pixel(dev.center().x(), dev.bottom() + 4)) != red


# ---------------------------------------------------------------- editor & drawings


@pytest.mark.parametrize("z", [0.75, 2.0])
def test_in_cell_editor_sits_on_the_zoomed_cell(qtbot, z: float) -> None:
    sheet = SheetDataModel()
    sheet.set_cell(3, 2, CellData(value="abc", font_size=10))
    sel = SelectionModel()
    vp = GridViewport(model=sheet, selection=sel)
    vp.resize(800, 500)
    qtbot.addWidget(vp)
    ctl = EditorController(viewport=vp, model=sheet, selection=sel)
    vp.editor_controller = ctl
    vp.set_zoom(z)
    sel.select_cell(3, 2)
    ctl.begin_edit(3, 2)
    QApplication.processEvents()
    dev = vp.device_cell_rect(3, 2)
    geo = ctl.in_cell_editor.geometry()
    assert geo.topLeft() == dev.topLeft()
    assert geo.height() >= dev.height()
    assert ctl.in_cell_editor.font().pointSizeF() == pytest.approx(10 * z)
    # Changing zoom while editing moves the editor with the cell.
    vp.set_zoom(1.0)
    assert ctl.in_cell_editor.geometry().topLeft() == vp.device_cell_rect(3, 2).topLeft()
    assert ctl.in_cell_editor.font().pointSizeF() == pytest.approx(10)


def test_object_layer_hit_test_follows_zoom(qtbot) -> None:
    sheet = SheetDataModel()
    sheet.drawings = []
    vp = _grid(qtbot, sheet)
    layer = SpreadsheetObjectLayer(model=sheet, parent=vp.viewport())
    layer.setGeometry(vp.viewport().rect())
    vp.object_layer = layer
    obj = FloatingObject(
        kind="rect",
        from_point=CellAnchorPoint(row=2, col=2),
        to_point=CellAnchorPoint(row=6, col=4),
    )
    layer.add_object(obj)
    vp.set_zoom(0.5)
    assert layer.zoom == pytest.approx(0.5)
    grid_rect = layer.get_object_rect(obj)
    dev = vp.map_rect_to_device(grid_rect)
    centre = layer._grid_pos(dev.center())
    assert layer.hit_test(centre.x(), centre.y())[0] is obj
    # Just past the zoomed rect misses, although it is inside the unzoomed one.
    past = QPoint(grid_rect.right() - 2, grid_rect.bottom() - 2)
    assert grid_rect.contains(past) and not dev.contains(past)
    far = layer._grid_pos(past)
    assert layer.hit_test(far.x(), far.y())[0] is None
