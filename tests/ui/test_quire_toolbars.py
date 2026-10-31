"""Unit and integration tests for Quire 10 toolbars cluster and ActionRegistry integration."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from atboffice.core.action_registry import ActionRegistry
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.quire_window import QuireWindow


def test_quire_10_toolbars_exist(qtbot) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)

    expected_keys = {
        "standard",
        "formatting",
        "tables",
        "reviewing",
        "outlining",
        "headerFooter",
        "drawing",
        "mailMerge",
        "picture",
        "wordart",
    }

    assert hasattr(win, "toolbars")
    assert isinstance(win.toolbars, dict)
    assert set(win.toolbars.keys()) == expected_keys

    for key, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar), f"Toolbar {key} must be an OfficeToolBar instance"
        assert tb.windowTitle(), f"Toolbar {key} must have a non-empty window title"


def test_drawing_toolbar_docked_at_top(qtbot) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)

    drawing_tb = win.toolbars["drawing"]
    assert win.toolBarArea(drawing_tb) == Qt.ToolBarArea.TopToolBarArea
    assert win.toolBarArea(drawing_tb) != Qt.ToolBarArea.BottomToolBarArea


def test_action_registry_binding(qtbot) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)

    assert hasattr(win, "action_registry")
    assert isinstance(win.action_registry, ActionRegistry)

    # Core actions must be registered in action_registry
    core_actions = [
        "new", "open", "save", "cut", "copy", "paste",
        "undo", "redo", "bold", "italic", "underline",
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
    win = QuireWindow()
    qtbot.addWidget(win)

    # Formatting toolbar: font combos and color pickers
    fmt_tb = win.toolbars["formatting"]
    combos = [w for w in fmt_tb.findChildren(QComboBox)]
    assert len(combos) >= 3  # style, font, size

    color_pickers = [w for w in fmt_tb.findChildren(ColorPickerButton)]
    assert len(color_pickers) >= 2  # font color and highlight

    # Standard toolbar: zoom combo
    std_tb = win.toolbars["standard"]
    std_combos = [w for w in std_tb.findChildren(QComboBox)]
    assert len(std_combos) >= 1  # zoom


def test_contextual_toolbar_visibility(qtbot) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)
    win.show()

    # By default, standard, formatting and drawing are visible; contextual toolbars are hidden
    assert win.toolbars["standard"].isVisible()
    assert win.toolbars["formatting"].isVisible()
    assert win.toolbars["drawing"].isVisible()
    assert not win.toolbars["tables"].isVisible()
    assert not win.toolbars["picture"].isVisible()
    assert not win.toolbars["wordart"].isVisible()
    assert not win.toolbars["outlining"].isVisible()
    assert not win.toolbars["headerFooter"].isVisible()
    assert not win.toolbars["reviewing"].isVisible()

    # 1. Enter table context
    win.update_context_toolbars({"in_table": True})
    assert win.toolbars["tables"].isVisible()

    # Leave table context
    win.update_context_toolbars({"in_table": False})
    assert not win.toolbars["tables"].isVisible()

    # 2. Select image
    win.update_context_toolbars({"is_picture": True})
    assert win.toolbars["picture"].isVisible()

    win.update_context_toolbars({"is_picture": False})
    assert not win.toolbars["picture"].isVisible()

    # 3. Select wordart
    win.update_context_toolbars({"is_wordart": True})
    assert win.toolbars["wordart"].isVisible()

    win.update_context_toolbars({"is_wordart": False})
    assert not win.toolbars["wordart"].isVisible()

    # 4. Outline view
    win.update_context_toolbars({"view": "outline"})
    assert win.toolbars["outlining"].isVisible()

    win.update_context_toolbars({"view": "normal"})
    assert not win.toolbars["outlining"].isVisible()

    # 5. Header/Footer edit
    win.update_context_toolbars({"hf_edit": True})
    assert win.toolbars["headerFooter"].isVisible()

    win.update_context_toolbars({"hf_edit": False})
    assert not win.toolbars["headerFooter"].isVisible()

    # 6. Manual override: force tables to False
    win.set_toolbar_mode("tables", False)
    win.update_context_toolbars({"in_table": True})
    assert not win.toolbars["tables"].isVisible()


def test_retranslate_ui(qtbot) -> None:
    win = QuireWindow()
    qtbot.addWidget(win)

    # Calling retranslate_ui should execute cleanly and refresh titles
    win.retranslate_ui()
    assert win.toolbars["standard"].windowTitle()
    assert win.toolbars["formatting"].windowTitle()
