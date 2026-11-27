"""Phase 12 Wave 2 regression tests for Ledger scrollbar/tabbar chrome and tooltips."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel, SheetViewState
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
)
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


def test_ledger_chrome_geometry_and_scrollbar_theme(qapp: QApplication) -> None:
    """Verify Ledger keeps a 18px bottom tab strip and proportional light scrollbars."""
    win = LedgerWindow()
    try:
        win.resize(1200, 800)
        win.show()
        qapp.processEvents()

        view = win.spreadsheet_view
        assert view.sheet_tab_bar.height() == 18
        assert view.grid.horizontalScrollBar().height() >= view.sheet_tab_bar.height()

        grid_w = view.grid.width()
        tab_w = view.sheet_tab_bar.width()
        assert int(grid_w * 0.50) <= tab_w <= int(grid_w * 0.72), (tab_w, grid_w)

        qss = view.grid.styleSheet()
        assert "#FAFAFA" in qss
        assert "#C1C1C1" in qss

        # Empty sheet scrollbar thumb should stay proportional (~1 viewport of spare range)
        # while reveal(60, 0) expands and reveal(0, 0) shrinks the scrollable extent again.
        vbar = view.grid.verticalScrollBar()
        initial_max = vbar.maximum()
        assert initial_max <= vbar.pageStep() + 60
        view.grid.reveal(60, 0)
        assert vbar.value() > 0
        assert vbar.maximum() > initial_max
        view.grid.reveal(0, 0)
        assert vbar.value() == 0
        assert vbar.maximum() == initial_max

        # Shrinking window below 320px clamps sheet_tab_bar cleanly instead of leaving stale width.
        win.resize(260, 600)
        qapp.processEvents()
        assert view.sheet_tab_bar.width() <= 200
        assert view.sheet_tab_bar.width() < view.grid.width()
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_used_scroll_extent_handles_tuple_merges_and_all_drawing_anchors(
    qapp: QApplication,
) -> None:
    """Verify 4-tuple merges and TWO_CELL/ONE_CELL/ABSOLUTE drawings extend scroll range."""
    win = LedgerWindow()
    try:
        win.resize(800, 600)
        win.show()
        qapp.processEvents()
        grid = win.spreadsheet_view.grid
        geo = grid.geometry_mapper

        # 4-tuple merge (r1, c1, r2, c2)
        grid.model.merges = [(0, 0, 85, 22)]
        bottom, right = grid._used_scroll_extent()
        assert bottom >= geo.row_pos(86)
        assert right >= geo.col_pos(23)

        # TWO_CELL drawing
        grid.model.merges = []
        grid.model.drawings = [
            FloatingObject(
                anchor_type=AnchorType.TWO_CELL,
                to_point=CellAnchorPoint(row=90, col=30),
            )
        ]
        bottom, right = grid._used_scroll_extent()
        assert bottom >= geo.row_pos(91)
        assert right >= geo.col_pos(31)

        # ONE_CELL drawing
        grid.model.drawings = [
            FloatingObject(
                anchor_type=AnchorType.ONE_CELL,
                from_point=CellAnchorPoint(row=5, col=4, row_off=10, col_off=20),
                abs_rect=(0, 0, 900, 1200),
            )
        ]
        bottom, right = grid._used_scroll_extent()
        assert bottom >= geo.row_pos(5) + 10 + 1200
        assert right >= geo.col_pos(4) + 20 + 900

        # ABSOLUTE drawing
        grid.model.drawings = [
            FloatingObject(
                anchor_type=AnchorType.ABSOLUTE,
                abs_rect=(400, 500, 1500, 1800),
            )
        ]
        bottom, right = grid._used_scroll_extent()
        assert bottom >= 2300
        assert right >= 1900
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_top_left_cell_preserves_dual_axis_scroll(qapp: QApplication) -> None:
    """Verify applying SheetViewState.top_left_cell='E20' sets both scroll axes."""
    win = LedgerWindow()
    try:
        win.resize(900, 700)
        win.show()
        qapp.processEvents()
        grid = win.spreadsheet_view.grid
        model = SheetDataModel(name="Scrolled")
        model.view_state = SheetViewState(top_left_cell="E20")
        grid.set_model_and_selection(model, SelectionModel())

        assert grid.verticalScrollBar().value() == grid.geometry_mapper.row_pos(19)
        assert grid.horizontalScrollBar().value() == grid.geometry_mapper.col_pos(4)
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_insert_comment_tooltip_is_app_specific(qapp: QApplication) -> None:
    """Verify Quire's insertComment action does not leak Ledger cell wording."""
    q_win = QuireWindow()
    l_win = LedgerWindow()
    try:
        q_act = q_win.action_registry.get_action("insertComment")
        l_act = l_win.action_registry.get_action("insertComment")
        assert q_act is not None and l_act is not None
        assert "单元格" not in q_act.toolTip()
        assert "单元格" not in q_act.statusTip()
        assert "批注" in l_act.toolTip()
    finally:
        for w in (q_win, l_win):
            w.set_modified(False)
            w.close()
        qapp.processEvents()
