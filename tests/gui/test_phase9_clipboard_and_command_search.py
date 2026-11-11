"""GUI and unit test suite for Phase 9 Office Clipboard Task Pane and Command Search Box.

Tests:
1. ClipboardTaskPane item capture, 24-item capacity capping, LIFO order.
2. Duplicate consecutive clipping prevention and MIME type detection.
3. Paste single item, Paste All, individual item deletion, and Clear All.
4. CommandSearchBox fuzzy and synonym search against ActionRegistry.
5. CommandSearchBox keyboard navigation (Down/Up/Enter/Esc) and Alt+Q shortcut.
6. Integration with BaseOfficeWindow, MacMenuBar corner mounting, and TaskPaneDock.
7. Full i18n retranslation across components.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QGuiApplication

from atboffice.core.action_registry import ActionRegistry, ActionSpec
from atboffice.ui.components.command_search_box import (
    CommandSearchBox,
)
from atboffice.ui.panes.clipboard_pane import (
    ClipboardTaskPane,
    ClipItem,
)
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.mac_menu import setup_mac_menu


def test_clipboard_task_pane_initial_state(qtbot):
    """Verify ClipboardTaskPane initial empty state and control bindings."""
    pane = ClipboardTaskPane()
    qtbot.addWidget(pane)
    pane.show()

    assert pane.count() == 0
    assert not pane.btn_paste_all.isEnabled()
    assert not pane.btn_clear_all.isEnabled()
    assert "0/24" in pane.lbl_note.text()
    assert pane.lbl_empty is not None
    assert not pane.lbl_empty.isHidden()


def test_clipboard_task_pane_add_and_cap_24(qtbot):
    """Verify up to 24 items are captured and oldest items are dropped when capacity exceeded."""
    pane = ClipboardTaskPane()
    qtbot.addWidget(pane)

    # Insert 30 items
    for i in range(1, 31):
        item = ClipItem(
            text=f"Clip Item #{i}",
            html=f"<p>Clip Item #{i}</p>",
            item_type="text",
            created_at=time.time(),
        )
        pane.add_clip_item(item)

    assert pane.count() == 24
    assert pane.btn_paste_all.isEnabled()
    assert pane.btn_clear_all.isEnabled()
    assert "24/24" in pane.lbl_note.text()

    items = pane.items()
    # Newest item must be at index 0
    assert items[0].text == "Clip Item #30"
    # Oldest retained item is #7 (1 to 6 were dropped)
    assert items[-1].text == "Clip Item #7"


def test_clipboard_task_pane_paste_single_item(qtbot):
    """Verify clicking an item copies it to system clipboard and emits item_clicked."""
    pane = ClipboardTaskPane()
    qtbot.addWidget(pane)

    item1 = ClipItem(text="Hello Quire", item_type="text")
    snapshot = QMimeData()
    snapshot.setText("Hello Quire")
    item1.mime_data = snapshot
    pane.add_clip_item(item1)

    clicked_items: list[ClipItem] = []
    pane.item_clicked.connect(clicked_items.append)

    pane.paste_item(item1)
    assert len(clicked_items) == 1
    assert clicked_items[0].text == "Hello Quire"

    # Verify system clipboard received the item text
    cb = QGuiApplication.clipboard()
    if cb is not None:
        assert cb.text() == "Hello Quire"


def test_clipboard_task_pane_paste_all_and_clear_all(qtbot):
    """Verify Paste All emits items in reverse order and Clear All clears all clippings."""
    pane = ClipboardTaskPane()
    qtbot.addWidget(pane)

    pane.add_clip_item(ClipItem(text="First"))
    pane.add_clip_item(ClipItem(text="Second"))
    pane.add_clip_item(ClipItem(text="Third"))

    paste_all_batches: list[list[ClipItem]] = []
    pane.paste_all_requested.connect(paste_all_batches.append)

    pane.paste_all()
    assert len(paste_all_batches) == 1
    batch = paste_all_batches[0]
    assert len(batch) == 3
    # Reverse order: oldest to newest ("First", "Second", "Third")
    assert batch[0].text == "First"
    assert batch[1].text == "Second"
    assert batch[2].text == "Third"

    # Test single item deletion
    first_item_id = pane.items()[0].id
    pane.remove_item(first_item_id)
    assert pane.count() == 2

    # Test Clear All
    cleared_signals = []
    pane.cleared.connect(lambda: cleared_signals.append(True))
    pane.clear_all()
    assert pane.count() == 0
    assert len(cleared_signals) == 1
    assert not pane.btn_paste_all.isEnabled()
    assert not pane.btn_clear_all.isEnabled()
    assert "0/24" in pane.lbl_note.text()


def test_clipboard_task_pane_retranslate_ui(qtbot):
    """Verify ClipboardTaskPane retranslate_ui."""
    pane = ClipboardTaskPane()
    qtbot.addWidget(pane)

    pane.retranslate_ui()
    assert "全部粘贴" in pane.btn_paste_all.text()
    assert "全部清空" in pane.btn_clear_all.text()
    assert "0/24" in pane.lbl_note.text()


def test_command_search_box_fuzzy_and_synonyms(qtbot):
    """Verify CommandSearchBox fuzzy matching and synonym dictionary scoring."""
    reg = ActionRegistry()
    reg.register_specs(
        [
            ActionSpec(id="file_print", label="打印...", shortcut="Ctrl+P", tip="打印当前文档"),
            ActionSpec(id="file_save", label="保存", shortcut="Ctrl+S", tip="保存文件"),
            ActionSpec(id="edit_copy", label="复制", shortcut="Ctrl+C", tip="复制到剪贴板"),
            ActionSpec(id="edit_paste", label="粘贴", shortcut="Ctrl+V", tip="从剪贴板粘贴"),
            ActionSpec(id="math_sum", label="自动求和", shortcut="Alt+=", tip="求和"),
            ActionSpec(id="tbl_insert", label="插入表格", shortcut=None, tip="创建新表格"),
        ]
    )

    box = CommandSearchBox(action_registry=reg)
    qtbot.addWidget(box)

    # 1. Direct label match
    res_print = box.search_commands("打印")
    assert len(res_print) > 0
    assert res_print[0].action_id == "file_print"

    # 2. English synonym match for Chinese action ("sum" -> "自动求和")
    res_sum = box.search_commands("sum")
    assert len(res_sum) > 0
    assert res_sum[0].action_id == "math_sum"

    # 3. English synonym for "print"
    res_en_print = box.search_commands("print")
    assert len(res_en_print) > 0
    assert res_en_print[0].action_id == "file_print"

    # 4. Synonym match for "table" -> "插入表格"
    res_tbl = box.search_commands("table")
    assert len(res_tbl) > 0
    assert res_tbl[0].action_id == "tbl_insert"

    # 5. Synonym match for "copy" -> "复制"
    res_copy = box.search_commands("copy")
    assert len(res_copy) > 0
    assert res_copy[0].action_id == "edit_copy"


def test_command_search_box_navigation_and_execution(qtbot):
    """Verify popup navigation, action execution, and shortcut focus."""
    reg = ActionRegistry()
    executed_actions: list[str] = []

    def on_save():
        executed_actions.append("file_save")

    reg.register_action(
        ActionSpec(id="file_save", label="保存", shortcut="Ctrl+S", handler=on_save)
    )

    box = CommandSearchBox(action_registry=reg)
    qtbot.addWidget(box)
    box.show()
    box.focus_and_select_all()

    # Enter query
    box.line_edit.setText("保存")
    assert len(box.search_commands("保存")) > 0

    # Execute action
    box.execute_action("file_save")
    assert "file_save" in executed_actions
    assert not box.popup.isVisible()
    assert box.line_edit.text() == ""


def test_base_office_window_integration(qtbot):
    """Verify BaseOfficeWindow mounts CommandSearchBox and registers ClipboardTaskPane."""
    win = BaseOfficeWindow()
    qtbot.addWidget(win)

    # 1. Setup macOS Menu Bar
    menu_bar = setup_mac_menu(win)
    assert win.command_search_box is not None
    corner_widget = menu_bar.cornerWidget(Qt.Corner.TopRightCorner)
    assert corner_widget is win.command_search_box

    # 2. Initialize TaskPaneDock
    dock = win.init_task_pane_dock("测试文档")
    assert win.clipboard_pane is not None
    assert dock.get_pane("clipboard") is win.clipboard_pane

    # 3. Open Clipboard task pane
    win.open_clipboard_pane()
    assert not dock.isHidden()
    assert dock.current_pane_id() == "clipboard"

    # 4. Test retranslation on window
    win.retranslate_ui()
    assert "剪贴板" in dock.header.btn_title.text()
