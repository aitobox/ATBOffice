"""GUI coverage tests for Office 2003 Task Panes across Quire, Ledger, and Lectern.

Verifies:
1. Universal TaskPaneHeader dropdown menu navigation and pane switching.
2. Quire Styles and Formatting pane with one-click style application to active document selection.
3. Lectern Slide Layout pane with standard PowerPoint 2003 layout thumbnails and slide application.
4. Ledger Watch Window pane for real-time formula coordinate and cell value monitoring.
5. Action registry handlers and i18n retranslation across all module task panes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow

from atboffice.modules.presentation.panes import SlideLayoutPane
from atboffice.modules.spreadsheet.panes import WatchWindowPane
from atboffice.modules.writer.panes import StylesAndFormattingPane
from atboffice.ui.components.task_pane import TaskPaneDock
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


def test_task_pane_header_dropdown_switching(qtbot):
    """Verify task pane header dropdown lists all module panels and switches active pane."""
    win = QMainWindow()
    qtbot.addWidget(win)
    dock = TaskPaneDock(win)
    win.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    p_styles = QLabel("Styles Pane", dock)
    p_layout = QLabel("Layout Pane", dock)
    p_watch = QLabel("Watch Pane", dock)

    dock.register_pane("styles", "样式与格式", p_styles)
    dock.register_pane("slide_layout", "幻灯片版式", p_layout)
    dock.register_pane("watch_window", "监视窗口", p_watch)
    items = dock._build_menu_items()
    pane_ids = [item[0] for item in items]
    assert "getting-started" in pane_ids
    assert "new" in pane_ids
    assert "styles" in pane_ids
    assert "slide_layout" in pane_ids
    assert "watch_window" in pane_ids

    # Simulate dropdown switching to styles
    dock.header.pane_selected.emit("styles")
    assert dock.current_pane_id() == "styles"
    assert "样式与格式" in dock.header.btn_title.text()

    # Simulate dropdown switching to slide_layout
    dock.header.pane_selected.emit("slide_layout")
    assert dock.current_pane_id() == "slide_layout"
    assert "幻灯片版式" in dock.header.btn_title.text()

    # Simulate dropdown switching to watch_window
    dock.header.pane_selected.emit("watch_window")
    assert dock.current_pane_id() == "watch_window"
    assert "监视窗口" in dock.header.btn_title.text()

    # Verify back navigation
    dock.go_back()
    assert dock.current_pane_id() == "slide_layout"
    dock.go_back()
    assert dock.current_pane_id() == "styles"
    win.close()


def test_quire_styles_and_formatting_pane(qtbot):
    """Verify Quire Styles and Formatting pane one-click style application."""
    quire = QuireWindow()
    qtbot.addWidget(quire)

    dock = quire.task_pane_dock
    assert dock is not None
    assert "styles" in dock._registry

    pane = dock.get_pane("styles")
    assert isinstance(pane, StylesAndFormattingPane)

    canvas = quire.writer_view.canvas_view
    assert canvas.get_current_style_id() == "Normal"

    # Click Heading1 style card
    h1_card = pane._style_widgets.get("Heading1")
    assert h1_card is not None
    h1_card.click()

    assert canvas.get_current_style_id() == "Heading1"
    assert "Heading1" in pane.lbl_cur_style.text()

    # Click Heading2 style card
    h2_card = pane._style_widgets.get("Heading2")
    assert h2_card is not None
    h2_card.click()

    assert canvas.get_current_style_id() == "Heading2"
    assert "Heading2" in pane.lbl_cur_style.text()

    # Click Clear Formatting
    clear_card = pane._style_widgets.get("clear")
    assert clear_card is not None
    clear_card.click()

    assert canvas.get_current_style_id() == "Normal"
    assert "Normal" in pane.lbl_cur_style.text()

    # Test retranslation
    pane.retranslate_ui()
    assert pane.lbl_sel_heading.text() == "所选文字的格式:"

    quire.close()


def test_lectern_slide_layout_pane(qtbot):
    """Verify Lectern Slide Layout pane with 12+ layout thumbnails and application."""
    lectern = LecternWindow()
    qtbot.addWidget(lectern)

    dock = lectern.task_pane_dock
    assert dock is not None
    assert "slide_layout" in dock._registry

    pane = dock.get_pane("slide_layout")
    assert isinstance(pane, SlideLayoutPane)

    # Verify 12+ standard PowerPoint 2003 layouts are present
    assert len(pane.layout_cards) >= 12
    for core_key in ("title", "titleOnly", "text", "twoText", "blank", "content", "twoContent"):
        assert core_key in pane.layout_cards

    ws = lectern.presentation_view.workspace
    assert ws is not None
    assert ws.current_slide is not None

    # Apply 'blank' layout
    blank_card = pane.layout_cards["blank"]
    blank_card.click()
    assert ws.current_slide.layout == "blank"

    # Apply 'twoContent' layout
    two_content_card = pane.layout_cards["twoContent"]
    two_content_card.click()
    assert ws.current_slide.layout == "twoContent"

    # Test retranslation
    pane.retranslate_ui()
    assert pane.lbl_prompt.text() == "应用幻灯片版式:"

    lectern.close()


def test_ledger_watch_window_pane(qtbot):
    """Verify Ledger Watch Window pane monitoring cell formulas and coordinates."""
    ledger = LedgerWindow()
    qtbot.addWidget(ledger)

    dock = ledger.task_pane_dock
    assert dock is not None
    assert "watch_window" in dock._registry

    pane = dock.get_pane("watch_window")
    assert isinstance(pane, WatchWindowPane)

    sheet = ledger.spreadsheet_view.model
    assert sheet is not None

    # Set value and formula in cell (0, 0) and (1, 1)
    from atboffice.modules.spreadsheet.models.sheet_model import CellData
    sheet.set_cell(0, 0, CellData(value=50))
    sheet.set_cell(1, 1, CellData(value=100, formula="A1*2"))

    # Add watch for Sheet1!$B$2
    added = pane.add_watch(sheet.name, 1, 1, book_name="TestBook.xlsx", name="DoubleA1")
    assert added is True
    assert pane.table.rowCount() == 1

    # Check cell info in table
    assert pane.table.item(0, 0).text() == "TestBook.xlsx"
    assert pane.table.item(0, 1).text() == sheet.name
    assert pane.table.item(0, 2).text() == "DoubleA1"
    assert pane.table.item(0, 3).text() == "$B$2"
    assert pane.table.item(0, 4).text() == "100"
    assert pane.table.item(0, 5).text() == "=A1*2"

    # Verify duplicate add returns False
    assert pane.add_watch(sheet.name, 1, 1, book_name="TestBook.xlsx") is False

    # Test navigation signal on item click
    nav_targets = []
    pane.navigate_requested.connect(lambda s, r, c: nav_targets.append((s, r, c)))
    pane.table.item(0, 0).setSelected(True)
    pane._on_item_clicked(pane.table.item(0, 0))
    assert (sheet.name, 1, 1) in nav_targets

    # Test delete watch
    pane.table.setCurrentCell(0, 0)
    pane.delete_selected_watch()
    assert pane.table.rowCount() == 0

    # Test retranslation
    pane.retranslate_ui()
    assert pane.lbl_desc.text() == "监视单元格公式与当前计算值:"

    ledger.close()


def test_shell_action_handlers_for_task_panes(qtbot):
    """Verify action registry triggers for showing module task panes."""
    # 1. Quire
    quire = QuireWindow()
    qtbot.addWidget(quire)
    assert quire.action_registry.trigger_action("stylesPane") is True
    assert not quire.task_pane_dock.isHidden()
    assert quire.task_pane_dock.current_pane_id() == "styles"
    quire.close()

    # 2. Lectern
    lectern = LecternWindow()
    qtbot.addWidget(lectern)
    assert lectern.action_registry.trigger_action("slideLayout") is True
    assert not lectern.task_pane_dock.isHidden()
    assert lectern.task_pane_dock.current_pane_id() == "slide_layout"
    lectern.close()

    # 3. Ledger
    ledger = LedgerWindow()
    qtbot.addWidget(ledger)
    assert ledger.action_registry.trigger_action("watchPane") is True
    assert not ledger.task_pane_dock.isHidden()
    assert ledger.task_pane_dock.current_pane_id() == "watch_window"
    ledger.close()
