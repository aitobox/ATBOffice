"""Unit tests for Office 2003 toolbar buttons (OfficeSplitButton, OfficeDropDownButton)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.components.toolbar_buttons import OfficeDropDownButton, OfficeSplitButton


def test_split_button_init(qtbot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)

    action = QAction("Test Action", widget)
    menu = QMenu("Test Menu", widget)
    menu.addAction("Sub Item")

    btn = OfficeSplitButton(action=action, menu=menu, parent=widget)
    qtbot.addWidget(btn)

    assert btn.defaultAction() == action
    assert btn.menu() == menu
    assert btn.popupMode() == OfficeSplitButton.ToolButtonPopupMode.MenuButtonPopup


def test_split_button_trigger_action(qtbot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)

    triggered = False

    def on_triggered() -> None:
        nonlocal triggered
        triggered = True

    action = QAction("Undo", widget)
    action.triggered.connect(on_triggered)
    menu = QMenu("Undo History", widget)

    btn = OfficeSplitButton(action=action, menu=menu, parent=widget)
    qtbot.addWidget(btn)
    btn.show()

    # Click the main button area (left side)
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton, pos=QPoint(5, 10))
    assert triggered is True


def test_split_button_disabled_state(qtbot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)

    action = QAction("Redo", widget)
    action.setEnabled(False)
    menu = QMenu("Redo History", widget)

    btn = OfficeSplitButton(action=action, menu=menu, parent=widget)
    qtbot.addWidget(btn)

    assert btn.isEnabled() is False

    action.setEnabled(True)
    assert btn.isEnabled() is True


def test_dropdown_button_init(qtbot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)

    menu = QMenu("Color Menu", widget)
    btn = OfficeDropDownButton(text="Font Color(&F)", icon=None, menu=menu, parent=widget)
    qtbot.addWidget(btn)

    assert btn.menu() == menu
    assert btn.popupMode() == OfficeDropDownButton.ToolButtonPopupMode.InstantPopup
    assert "Font Color" in btn.text()


def test_toolbar_integration(qtbot) -> None:
    tb = OfficeToolBar("Standard", None)
    qtbot.addWidget(tb)

    action = QAction("Save", tb)
    menu = QMenu("Save Options", tb)

    split_btn = tb.add_split_action(action, menu)
    assert isinstance(split_btn, OfficeSplitButton)
    assert split_btn.defaultAction() == action
    assert split_btn.menu() == menu

    drop_menu = QMenu("Align", tb)
    drop_btn = tb.add_drop_button("Align", None, drop_menu)
    assert isinstance(drop_btn, OfficeDropDownButton)
    assert drop_btn.menu() == drop_menu


def test_button_painting_and_sizing(qtbot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)

    action = QAction("Format Painter", widget)
    menu = QMenu(widget)
    menu.addAction("Option 1")

    split_btn = OfficeSplitButton(action=action, menu=menu, parent=widget)
    drop_btn = OfficeDropDownButton(text="Shapes", icon=None, menu=menu, parent=widget)

    qtbot.addWidget(split_btn)
    qtbot.addWidget(drop_btn)

    split_btn.show()
    drop_btn.show()

    # Trigger repaint and verify size hints
    split_btn.repaint()
    drop_btn.repaint()

    assert split_btn.sizeHint().height() >= 22
    assert drop_btn.sizeHint().height() >= 22


def test_empty_init_and_dynamic_menu(qtbot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)

    split_btn = OfficeSplitButton(parent=widget)
    drop_btn = OfficeDropDownButton(parent=widget)

    assert split_btn.defaultAction() is None
    assert split_btn.menu() is None

    action = QAction("New", widget)
    menu = QMenu("New Menu", widget)

    split_btn.setDefaultAction(action)
    split_btn.setMenu(menu)

    assert split_btn.defaultAction() == action
    assert split_btn.menu() == menu

    drop_btn.setMenu(menu)
    assert drop_btn.menu() == menu
