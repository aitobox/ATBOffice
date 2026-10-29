"""Tests for ActionRegistry command bus and ActionSpec."""

from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu, QToolBar, QWidget

from atboffice.core.action_registry import ActionRegistry, ActionSpec


def test_action_spec_defaults():
    spec = ActionSpec(id="file_save", label="&Save")
    assert spec.id == "file_save"
    assert spec.label == "&Save"
    assert spec.icon is None
    assert spec.tip == ""
    assert spec.shortcut is None
    assert spec.checkable is False
    assert spec.checked is False
    assert spec.enabled is True
    assert spec.is_split is False
    assert spec.is_drop is False
    assert spec.handler is None


def test_action_registry_register_and_get(qtbot):
    reg = ActionRegistry()
    spec = ActionSpec(
        id="spelling",
        label="&Spelling...",
        tip="Check document spelling",
        shortcut="F7",
        checkable=True,
        checked=True,
        enabled=True,
    )
    act = reg.register_action(spec)
    assert isinstance(act, QAction)
    assert act.text() == "&Spelling..."
    assert act.toolTip() == "Check document spelling"
    assert act.statusTip() == "Check document spelling"
    assert act.isCheckable() is True
    assert act.isChecked() is True
    assert act.isEnabled() is True
    assert act.shortcut() == QKeySequence("F7")

    # Retrieval
    assert reg.get_action("spelling") is act
    assert reg.has_action("spelling") is True
    assert reg.get_action("non_existent") is None
    assert reg.has_action("non_existent") is False


def test_action_registry_idempotent_registration(qtbot):
    reg = ActionRegistry()
    spec1 = ActionSpec(id="zoom", label="Zoom &In", tip="Zoom In")
    act1 = reg.register_action(spec1)

    # Re-register with updated label and tip
    spec2 = ActionSpec(id="zoom", label="Zoom &Out", tip="Zoom Out")
    act2 = reg.register_action(spec2)

    assert act1 is act2
    assert act1.text() == "Zoom &Out"
    assert act1.toolTip() == "Zoom Out"


def test_action_registry_state_sync_between_menu_and_toolbar(qtbot):
    win = QMainWindow()
    qtbot.addWidget(win)

    reg = ActionRegistry(parent=win)
    spec = ActionSpec(id="bold", label="&Bold", checkable=True, enabled=True)
    act = reg.register_action(spec)

    menu = QMenu("Format", win)
    menu.addAction(act)

    toolbar = QToolBar("Formatting", win)
    toolbar.addAction(act)

    # Initially enabled and unchecked
    assert act.isEnabled() is True
    assert act.isChecked() is False

    # Toggle through registry
    reg.set_enabled("bold", False)
    assert act.isEnabled() is False

    reg.set_checked("bold", True)
    assert act.isChecked() is True

    reg.set_enabled("bold", True)
    assert act.isEnabled() is True


def test_action_registry_custom_handler(qtbot):
    reg = ActionRegistry()
    invoked = []

    def on_click():
        invoked.append(True)

    spec = ActionSpec(id="custom_cmd", label="Run Custom", handler=on_click)
    act = reg.register_action(spec)

    act.trigger()
    assert len(invoked) == 1

    # Using trigger_action helper
    success = reg.trigger_action("custom_cmd")
    assert success is True
    assert len(invoked) == 2

    # Triggering unknown action
    assert reg.trigger_action("unknown") is False


def test_action_registry_fallback_to_statusbar(qtbot):
    win = QMainWindow()
    qtbot.addWidget(win)
    status_bar = win.statusBar()

    reg = ActionRegistry(parent=win)
    spec = ActionSpec(id="unwired", label="Unwired Action")
    act = reg.register_action(spec)

    act.trigger()
    msg = status_bar.currentMessage()
    assert "联调" in msg or "development" in msg.lower()


def test_action_registry_fallback_without_statusbar(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)

    reg = ActionRegistry(parent=widget)
    spec = ActionSpec(id="no_sb_action", label="No Status Bar Action")
    act = reg.register_action(spec)

    # Should safely handle missing statusBar without exception
    act.trigger()


def test_action_registry_batch_register(qtbot):
    reg = ActionRegistry()
    specs = [
        ActionSpec(id="act1", label="Action 1"),
        ActionSpec(id="act2", label="Action 2"),
    ]
    actions = reg.register_specs(specs)
    assert len(actions) == 2
    assert reg.has_action("act1") is True
    assert reg.has_action("act2") is True


def test_action_registry_set_handler(qtbot):
    reg = ActionRegistry()
    spec = ActionSpec(id="dynamic", label="Dynamic Action")
    act = reg.register_action(spec)

    called = []
    reg.set_handler("dynamic", lambda: called.append(42))
    act.trigger()
    assert called == [42]


def test_action_registry_retranslate_ui(qtbot):
    reg = ActionRegistry()
    spec = ActionSpec(id="save", label="&Save", tip="Save file")
    act = reg.register_action(spec)

    translations = {
        "&Save": "保存(&S)",
        "Save file": "保存当前文件",
    }

    def custom_tr(text: str) -> str:
        return translations.get(text, text)

    reg.retranslate_ui(tr_func=custom_tr)
    assert act.text() == "保存(&S)"
    assert act.toolTip() == "保存当前文件"
