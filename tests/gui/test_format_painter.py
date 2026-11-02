"""GUI tests for Format Painter state machine (single-click vs sticky double-click).

Ported from .vibeoffice/tests/ui/painter.test.mjs.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.ui.shell.ledger_window import LedgerWindow


def test_format_painter_single_click_one_off(qtbot):
    """Single click format painter applies to target cell and automatically disarms."""
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(800, 600)
    win.show()

    model = win.spreadsheet_view.model
    grid = win.spreadsheet_view.grid
    assert grid is not None

    # Source cell (0, 0) formatted with Bold, Italic, and Custom Font
    model.set_cell(
        0, 0, CellData(value="Source", bold=True, italic=True, font_family="Arial", font_size=14.0)
    )
    # Target cell (1, 1) default
    model.set_cell(1, 1, CellData(value="Target", bold=False, italic=False))

    grid.selection.select_cell(0, 0)

    # 1. Arm single-click painter
    win.toggle_format_painter(double_click=False)
    assert getattr(win, "_format_painter_active", False) is True
    assert getattr(win, "_format_painter_sticky", False) is False

    # 2. Apply to target cell (1, 1)
    win.apply_format_painter_to_range(1, 1, 1, 1)

    target_cell = model.get_cell(1, 1)
    assert target_cell is not None
    assert target_cell.bold is True
    assert target_cell.italic is True
    assert target_cell.font_family == "Arial"
    assert target_cell.font_size == 14.0

    # Auto-disarmed after single application
    assert getattr(win, "_format_painter_active", False) is False


def test_format_painter_sticky_double_click_and_escape(qtbot):
    """Double click format painter stays active across multiple cells until Escape is pressed.

    Matches .vibeoffice painter.test.mjs:
    'a double-clicked painter stays on until Esc'.
    """
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(800, 600)
    win.show()

    model = win.spreadsheet_view.model
    grid = win.spreadsheet_view.grid
    assert grid is not None

    model.set_cell(0, 0, CellData(value="Source", bold=True, bg_color="#FFEEDD"))
    model.set_cell(1, 0, CellData(value="Target 1"))
    model.set_cell(2, 0, CellData(value="Target 2"))

    grid.selection.select_cell(0, 0)

    # 1. Arm sticky painter (double-click)
    win.toggle_format_painter(double_click=True)
    assert getattr(win, "_format_painter_active", False) is True
    assert getattr(win, "_format_painter_sticky", False) is True

    # 2. Paint target 1
    win.apply_format_painter_to_range(1, 0, 1, 0)
    assert model.get_cell(1, 0).bold is True
    assert getattr(win, "_format_painter_active", False) is True  # Still active!

    # 3. Paint target 2
    win.apply_format_painter_to_range(2, 0, 2, 0)
    assert model.get_cell(2, 0).bold is True
    assert getattr(win, "_format_painter_active", False) is True  # Still active!

    # 4. Press Escape to disarm
    esc_event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    grid.keyPressEvent(esc_event)

    assert getattr(win, "_format_painter_active", False) is False
    assert getattr(win, "_format_painter_sticky", False) is False
