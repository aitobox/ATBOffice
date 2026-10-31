"""Unit and integration tests for Ledger 8 toolbars cluster and ActionRegistry integration."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from atboffice.core.action_registry import ActionRegistry
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.ledger_window import LedgerWindow


def test_ledger_8_toolbars_exist(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    expected_keys = {
        "standard",
        "formatting",
        "borders",
        "auditing",
        "reviewing",
        "list",
        "chart",
        "drawing",
    }

    assert hasattr(win, "toolbars")
    assert isinstance(win.toolbars, dict)
    assert set(win.toolbars.keys()) == expected_keys

    for key, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar), f"Toolbar {key} must be an OfficeToolBar instance"
        assert tb.windowTitle(), f"Toolbar {key} must have a non-empty window title"


def test_drawing_toolbar_docked_at_top(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    drawing_tb = win.toolbars["drawing"]
    assert win.toolBarArea(drawing_tb) == Qt.ToolBarArea.TopToolBarArea
    assert win.toolBarArea(drawing_tb) != Qt.ToolBarArea.BottomToolBarArea


def test_action_registry_binding(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    assert hasattr(win, "action_registry")
    assert isinstance(win.action_registry, ActionRegistry)

    # Core actions must be registered in action_registry
    core_actions = [
        "new",
        "open",
        "save",
        "cut",
        "copy",
        "paste",
        "undo",
        "redo",
        "bold",
        "italic",
        "underline",
    ]
    for aid in core_actions:
        assert win.action_registry.has_action(aid), (
            f"Action {aid} should be registered in action_registry"
        )

    # Test triggering an action through the registry
    triggered_actions = []
    win.action_registry.action_triggered.connect(triggered_actions.append)

    win.action_registry.trigger_action("save")
    assert "save" in triggered_actions


def test_special_widgets_and_combos(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    # Formatting toolbar: font and size combos
    fmt_tb = win.toolbars["formatting"]
    combos = [w for w in fmt_tb.findChildren(QComboBox)]
    assert len(combos) >= 2  # font, size

    # Color pickers on formatting
    color_pickers = [w for w in fmt_tb.findChildren(ColorPickerButton)]
    assert len(color_pickers) >= 2  # fill color and font color

    # Standard toolbar: zoom combo
    std_tb = win.toolbars["standard"]
    std_combos = [w for w in std_tb.findChildren(QComboBox)]
    assert len(std_combos) >= 1  # zoom


def test_contextual_toolbar_visibility(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.show()

    # By default, standard and formatting are visible; contextual toolbars are hidden
    assert win.toolbars["standard"].isVisible()
    assert win.toolbars["formatting"].isVisible()
    assert not win.toolbars["drawing"].isVisible()
    assert not win.toolbars["chart"].isVisible()
    assert not win.toolbars["list"].isVisible()
    assert not win.toolbars["borders"].isVisible()
    assert not win.toolbars["auditing"].isVisible()
    assert not win.toolbars["reviewing"].isVisible()

    # 1. Enter chart context
    win.update_context_toolbars({"is_chart": True})
    assert win.toolbars["chart"].isVisible()

    win.update_context_toolbars({"is_chart": False})
    assert not win.toolbars["chart"].isVisible()

    # 2. Enter table context
    win.update_context_toolbars({"in_table": True})
    assert win.toolbars["list"].isVisible()

    win.update_context_toolbars({"in_table": False})
    assert not win.toolbars["list"].isVisible()

    # 3. Manual override: show borders
    win.set_toolbar_mode("borders", True)
    assert win.toolbars["borders"].isVisible()

    # 4. Manual override: force chart to False
    win.set_toolbar_mode("chart", False)
    win.update_context_toolbars({"is_chart": True})
    assert not win.toolbars["chart"].isVisible()


def test_retranslate_ui(qtbot) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)

    win.retranslate_ui()

    for key, tb in win.toolbars.items():
        assert tb.windowTitle(), f"Toolbar {key} title should remain non-empty after retranslate"
