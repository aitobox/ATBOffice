"""End-to-end GUI tests for StartCenter and TaskPane template interactions."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QDialog

from atboffice.core.window_manager import WindowManager
from atboffice.ui.dialogs.templates_dialog import TemplatesDialog
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.shell.start_center import StartCenterWindow, TemplateCard


def test_start_center_template_cards_exist(qtbot):
    """Verify StartCenter has cards for Quire, Ledger, and all 4 Lectern templates."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    # Switch to templates page
    win.stacked_widget.setCurrentIndex(1)
    cards = win.page_templates.findChildren(TemplateCard)
    assert len(cards) >= 11  # Quire(3) + Ledger(3) + Lectern(5)

    lectern_card_tids = [getattr(c, "template_id", None) for c in cards]
    assert "status" in lectern_card_tids
    assert "meeting" in lectern_card_tids
    assert "lesson" in lectern_card_tids
    assert "event" in lectern_card_tids


def test_start_center_card_clicks_instantiate_templates(qtbot):
    """Verify clicking template cards calls WindowManager to open window with template."""
    win = StartCenterWindow()
    qtbot.addWidget(win)

    cards = win.page_templates.findChildren(TemplateCard)
    status_card = next(c for c in cards if getattr(c, "template_id", None) == "status")
    assert status_card is not None

    wm = WindowManager.get_instance()
    with patch.object(wm, "open_lectern") as mock_open_lectern:
        # Simulate click
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10.0, 10.0),
            QPointF(10.0, 10.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        status_card.mousePressEvent(event)
        mock_open_lectern.assert_called_once_with(template_id="status")


def test_templates_dialog_app_filter_and_selection(qtbot):
    """Verify TemplatesDialog filters by app, displays metadata preview, and allows selection."""
    dlg = TemplatesDialog(app="lectern")
    qtbot.addWidget(dlg)

    # Should only contain lectern templates in the current list
    assert dlg.list_widget.count() == 4
    item_texts = [dlg.list_widget.item(i).text() for i in range(dlg.list_widget.count())]
    assert any("项目状态汇报" in t for t in item_texts)
    assert any("团队例会" in t for t in item_texts)

    # First item should be selected by default and preview updated
    assert dlg.get_selected_template_id() is not None
    assert "项目状态汇报" in dlg.lbl_preview_title.text() or "Status" in dlg.lbl_preview_title.text()
    assert dlg.btn_create.isEnabled()

    # Select second item
    dlg.list_widget.setCurrentRow(1)
    sel_id = dlg.get_selected_template_id()
    assert sel_id in ("status", "meeting", "lesson", "event")

    # Double click item accepts dialog
    dlg.list_widget.itemDoubleClicked.emit(dlg.list_widget.currentItem())
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_task_pane_templates_action_in_lectern_window(qtbot):
    """Verify TaskPane 'templates' action opens dialog and loads template in LecternWindow."""
    win = LecternWindow()
    qtbot.addWidget(win)

    # Mock TemplatesDialog returning Accepted with 'meeting' template
    with patch("atboffice.ui.dialogs.templates_dialog.TemplatesDialog.exec", return_value=QDialog.DialogCode.Accepted), \
         patch("atboffice.ui.dialogs.templates_dialog.TemplatesDialog.get_selected_template_id", return_value="meeting"):
        win._on_task_pane_action("templates")

    assert win.active_template is not None
    assert win.active_template.id == "meeting"
    assert len(win.presentation.slides) == 6
    assert "团队例会" in win.windowTitle() or "Meeting" in win.windowTitle()


def test_task_pane_templates_action_in_quire_window(qtbot):
    """Verify TaskPane 'templates' action opens dialog and loads template in QuireWindow."""
    win = QuireWindow()
    qtbot.addWidget(win)

    with patch("atboffice.ui.dialogs.templates_dialog.TemplatesDialog.exec", return_value=QDialog.DialogCode.Accepted), \
         patch("atboffice.ui.dialogs.templates_dialog.TemplatesDialog.get_selected_template_id", return_value="memo"):
        win._on_task_pane_action("templates")

    assert win.active_template is not None
    assert win.active_template.id == "memo"
    assert "备忘录" in win.windowTitle() or "Memo" in win.windowTitle()


def test_task_pane_templates_action_in_ledger_window(qtbot):
    """Verify TaskPane 'templates' action opens dialog and loads template in LedgerWindow."""
    win = LedgerWindow()
    qtbot.addWidget(win)

    with patch("atboffice.ui.dialogs.templates_dialog.TemplatesDialog.exec", return_value=QDialog.DialogCode.Accepted), \
         patch("atboffice.ui.dialogs.templates_dialog.TemplatesDialog.get_selected_template_id", return_value="budget"):
        win._on_task_pane_action("templates")

    assert win.active_template is not None
    assert win.active_template.id == "budget"
    assert "预算" in win.windowTitle() or "Budget" in win.windowTitle()


def test_task_pane_templates_action_cancelled_leaves_state_intact(qtbot):
    """Verify cancelling TemplatesDialog does not change active document."""
    win = LecternWindow()
    qtbot.addWidget(win)

    with patch("atboffice.ui.dialogs.templates_dialog.TemplatesDialog.exec", return_value=QDialog.DialogCode.Rejected):
        win._on_task_pane_action("templates")

    assert win.active_template is None
    assert len(win.presentation.slides) == 1
