"""Phase 12 Wave 2 regression tests for Ledger scrollbar/tabbar chrome and tooltips."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

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
        # while reveal(60, 0) expands the scrollable extent automatically.
        vbar = view.grid.verticalScrollBar()
        assert vbar.maximum() <= vbar.pageStep() + 60
        view.grid.reveal(60, 0)
        assert vbar.value() > 0
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
