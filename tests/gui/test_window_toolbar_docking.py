"""GUI layout regression tests verifying application window toolbar docking.

Ensures that:
1. Quire, Ledger, and Lectern windows dock all command bars exclusively in TopToolBarArea.
2. Zero toolbars reside in BottomToolBarArea, eliminating bloated text button footers.
3. The bottom area strictly contains only the status bar and intended native controls
   (such as Ledger's worksheet tab bar).
4. Dynamic toggling preserves top docking without migrating to bottom.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolBar, QToolButton

from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


def test_quire_window_toolbar_docking(qtbot) -> None:
    """Assert QuireWindow docks all toolbars at the top and keeps bottom pure."""
    win = QuireWindow()
    qtbot.addWidget(win)

    # 1. Assert every toolbar is in TopToolBarArea
    for name, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar)
        area = win.toolBarArea(tb)
        assert area == Qt.ToolBarArea.TopToolBarArea, (
            f"Quire toolbar '{name}' is in area {area}, expected TopToolBarArea"
        )
        assert area != Qt.ToolBarArea.BottomToolBarArea, (
            f"Quire toolbar '{name}' must not be in BottomToolBarArea"
        )

    # 2. Assert no toolbar is located in the bottom dock area
    for child in win.findChildren(QToolBar):
        assert win.toolBarArea(child) != Qt.ToolBarArea.BottomToolBarArea

    # 3. Assert status bar is present at bottom
    assert win.statusBar() is not None


def test_ledger_window_toolbar_docking(qtbot) -> None:
    """Assert LedgerWindow docks drawing and all toolbars at top, keeping sheet tabs at bottom."""
    win = LedgerWindow()
    qtbot.addWidget(win)

    # 1. Assert every toolbar is in TopToolBarArea
    for name, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar)
        area = win.toolBarArea(tb)
        assert area == Qt.ToolBarArea.TopToolBarArea, (
            f"Ledger toolbar '{name}' is in area {area}, expected TopToolBarArea"
        )
        assert area != Qt.ToolBarArea.BottomToolBarArea, (
            f"Ledger toolbar '{name}' must not be in BottomToolBarArea"
        )

    # 2. Assert no toolbar is in BottomToolBarArea
    for child in win.findChildren(QToolBar):
        assert win.toolBarArea(child) != Qt.ToolBarArea.BottomToolBarArea

    # 3. Bottom controls: Sheet tab bar and status bar exist
    assert hasattr(win, "sheet_tab_bar") and win.sheet_tab_bar is not None
    assert win.statusBar() is not None


def test_lectern_window_toolbar_docking(qtbot) -> None:
    """Assert LecternWindow docks all toolbars at top, keeping slide viewport clean."""
    win = LecternWindow()
    qtbot.addWidget(win)

    # 1. Assert every toolbar is in TopToolBarArea
    for name, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar)
        area = win.toolBarArea(tb)
        assert area == Qt.ToolBarArea.TopToolBarArea, (
            f"Lectern toolbar '{name}' is in area {area}, expected TopToolBarArea"
        )
        assert area != Qt.ToolBarArea.BottomToolBarArea, (
            f"Lectern toolbar '{name}' must not be in BottomToolBarArea"
        )

    # 2. Assert no toolbar is in BottomToolBarArea
    for child in win.findChildren(QToolBar):
        assert win.toolBarArea(child) != Qt.ToolBarArea.BottomToolBarArea

    # 3. Status bar is present
    assert win.statusBar() is not None


def test_dynamic_drawing_toggle_stays_in_top(qtbot) -> None:
    """Assert toggling drawing toolbar on/off preserves TopToolBarArea across all windows."""
    # Test Quire
    quire_win = QuireWindow()
    qtbot.addWidget(quire_win)
    quire_win.show()
    draw_tb = quire_win.toolbars["drawing"]

    # Toggle off
    quire_win.set_toolbar_mode("drawing", False)
    assert not draw_tb.isVisible()
    # Toggle on
    quire_win.set_toolbar_mode("drawing", True)
    assert draw_tb.isVisible()
    assert quire_win.toolBarArea(draw_tb) == Qt.ToolBarArea.TopToolBarArea

    # Test Ledger
    ledger_win = LedgerWindow()
    qtbot.addWidget(ledger_win)
    ledger_win.show()
    draw_tb_ledger = ledger_win.toolbars["drawing"]

    # Toggle on
    ledger_win.set_toolbar_mode("drawing", True)
    assert draw_tb_ledger.isVisible()
    assert ledger_win.toolBarArea(draw_tb_ledger) == Qt.ToolBarArea.TopToolBarArea

    # Test Lectern
    lectern_win = LecternWindow()
    qtbot.addWidget(lectern_win)
    lectern_win.show()
    draw_tb_lectern = lectern_win.toolbars["drawing"]

    # Toggle off and on
    lectern_win.set_toolbar_mode("drawing", False)
    assert not draw_tb_lectern.isVisible()
    lectern_win.set_toolbar_mode("drawing", True)
    assert draw_tb_lectern.isVisible()
    assert lectern_win.toolBarArea(draw_tb_lectern) == Qt.ToolBarArea.TopToolBarArea


def test_toolbar_button_height_metrics(qtbot) -> None:
    """Assert toolbar buttons converge to compact Office 2003 height metrics (<= 32px)."""
    win = QuireWindow()
    qtbot.addWidget(win)

    for tb_name in ["standard", "formatting", "drawing"]:
        tb = win.toolbars.get(tb_name)
        assert tb is not None
        for btn in tb.findChildren(QToolButton):
            hint = btn.sizeHint()
            if hint.isValid() and hint.height() > 0:
                assert hint.height() <= 32, (
                    f"Button {btn} in {tb_name} has oversized height {hint.height()}px"
                )
