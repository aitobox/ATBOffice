"""Unit and integration tests for Lectern 10 toolbars cluster and ActionRegistry integration."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from atboffice.core.action_registry import ActionRegistry
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.lectern_window import LecternWindow


def test_lectern_10_toolbars_exist(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)

    expected_keys = {
        "standard",
        "formatting",
        "sorter",
        "master",
        "outlining",
        "diagram",
        "tables",
        "picture",
        "wordart",
        "drawing",
    }

    assert hasattr(win, "toolbars")
    assert isinstance(win.toolbars, dict)
    assert set(win.toolbars.keys()) == expected_keys

    for key, tb in win.toolbars.items():
        assert isinstance(tb, OfficeToolBar), f"Toolbar {key} must be an OfficeToolBar instance"
        assert tb.windowTitle(), f"Toolbar {key} must have a non-empty window title"


def test_drawing_toolbar_docked_at_bottom(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)

    drawing_tb = win.toolbars["drawing"]
    assert win.toolBarArea(drawing_tb) == Qt.ToolBarArea.BottomToolBarArea


def test_action_registry_binding(qtbot) -> None:
    win = LecternWindow()
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
        "new_slide",
        "start_slideshow",
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
    win = LecternWindow()
    qtbot.addWidget(win)

    # Formatting toolbar: font and size combos
    fmt_tb = win.toolbars["formatting"]
    combos = [w for w in fmt_tb.findChildren(QComboBox)]
    assert len(combos) >= 2  # font, size

    # Color pickers on formatting and drawing
    fmt_color_pickers = [w for w in fmt_tb.findChildren(ColorPickerButton)]
    assert len(fmt_color_pickers) >= 1  # font color

    draw_tb = win.toolbars["drawing"]
    draw_color_pickers = [w for w in draw_tb.findChildren(ColorPickerButton)]
    assert len(draw_color_pickers) >= 3  # fill, line, font

    # Standard toolbar: zoom combo
    std_tb = win.toolbars["standard"]
    std_combos = [w for w in std_tb.findChildren(QComboBox)]
    assert len(std_combos) >= 1  # zoom


def test_contextual_toolbar_visibility(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()

    # By default in normal view, standard, formatting and drawing are visible
    assert win.toolbars["standard"].isVisible()
    assert win.toolbars["formatting"].isVisible()
    assert win.toolbars["drawing"].isVisible()

    # Contextual and other view toolbars are hidden
    assert not win.toolbars["sorter"].isVisible()
    assert not win.toolbars["master"].isVisible()
    assert not win.toolbars["outlining"].isVisible()
    assert not win.toolbars["tables"].isVisible()
    assert not win.toolbars["picture"].isVisible()
    assert not win.toolbars["wordart"].isVisible()
    assert not win.toolbars["diagram"].isVisible()

    # 1. Switch to Sorter view mode
    win.set_view_mode("sorter")
    assert win.toolbars["sorter"].isVisible()
    assert not win.toolbars["formatting"].isVisible()
    assert not win.toolbars["drawing"].isVisible()

    # 2. Switch to Master view mode
    win.set_view_mode("master")
    assert win.toolbars["master"].isVisible()
    assert not win.toolbars["sorter"].isVisible()

    # 3. Switch back to Normal view mode
    win.set_view_mode("normal")
    assert not win.toolbars["master"].isVisible()
    assert not win.toolbars["sorter"].isVisible()
    assert win.toolbars["formatting"].isVisible()

    # 4. Contextual selection updates
    win.update_context_toolbars({"is_table": True})
    assert win.toolbars["tables"].isVisible()

    win.update_context_toolbars({"is_table": False, "is_picture": True})
    assert not win.toolbars["tables"].isVisible()
    assert win.toolbars["picture"].isVisible()

    win.update_context_toolbars({"is_picture": False, "is_diagram": True})
    assert not win.toolbars["picture"].isVisible()
    assert win.toolbars["diagram"].isVisible()

    win.update_context_toolbars({"is_diagram": False, "is_wordart": True})
    assert not win.toolbars["diagram"].isVisible()
    assert win.toolbars["wordart"].isVisible()

    win.update_context_toolbars({"is_wordart": False, "is_outline": True})
    assert not win.toolbars["wordart"].isVisible()
    assert win.toolbars["outlining"].isVisible()


def test_retranslate_ui(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)

    win.retranslate_ui()
    for key, tb in win.toolbars.items():
        assert tb.windowTitle(), f"Toolbar {key} title must remain localized after retranslate_ui"
