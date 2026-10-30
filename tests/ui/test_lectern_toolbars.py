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


def test_drawing_toolbar_shape_creation(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)

    ws = win.presentation_view.workspace
    scene = ws.scene

    # 1. Activate drawRect tool
    win.action_registry.trigger_action("drawRect")
    assert win.action_registry.get_action("drawRect").isChecked()
    assert scene.current_tool == {"kind": "shape", "geom": "rect"}

    # Simulate drawing rectangle
    initial_count = len(ws.current_slide.shapes)
    sh_rect = scene._create_shape_from_tool(
        scene.current_tool,
        scene.views()[0].mapToScene(10, 10),
        scene.views()[0].mapToScene(110, 80),
    )
    assert len(ws.current_slide.shapes) == initial_count + 1
    assert sh_rect.geom == "rect"

    # 2. Activate drawOval tool
    win.action_registry.trigger_action("drawOval")
    assert win.action_registry.get_action("drawOval").isChecked()
    sh_oval = scene._create_shape_from_tool(
        scene.current_tool,
        scene.views()[0].mapToScene(20, 20),
        scene.views()[0].mapToScene(80, 80),
    )
    assert sh_oval.geom == "ellipse"

    # 3. Activate drawArrow tool
    win.action_registry.trigger_action("drawArrow")
    assert win.action_registry.get_action("drawArrow").isChecked()
    sh_arrow = scene._create_shape_from_tool(
        scene.current_tool,
        scene.views()[0].mapToScene(50, 50),
        scene.views()[0].mapToScene(150, 80),
    )
    assert sh_arrow.geom == "rightArrow"

    # 4. Activate drawLine tool
    win.action_registry.trigger_action("drawLine")
    assert win.action_registry.get_action("drawLine").isChecked()
    sh_line = scene._create_shape_from_tool(
        scene.current_tool,
        scene.views()[0].mapToScene(0, 0),
        scene.views()[0].mapToScene(100, 100),
    )
    assert sh_line.type == "line"

    # 5. Activate textBox tool
    win.action_registry.trigger_action("textBox")
    assert win.action_registry.get_action("textBox").isChecked()
    sh_text = scene._create_shape_from_tool(
        scene.current_tool,
        scene.views()[0].mapToScene(30, 30),
        scene.views()[0].mapToScene(150, 60),
    )
    assert sh_text.type == "text"
    assert sh_text.text is not None

    # 6. Reset with selectObjects
    win.action_registry.trigger_action("selectObjects")
    assert scene.current_tool is None
    assert win.action_registry.get_action("selectObjects").isChecked()


def test_layer_arrangement_and_grouping(qtbot) -> None:
    from atboffice.modules.presentation.models.shape import Shape

    win = LecternWindow()
    qtbot.addWidget(win)

    ws = win.presentation_view.workspace
    slide = ws.current_slide
    slide.shapes.clear()

    s1 = Shape(id="s1", name="Shape 1", x=10, y=10, w=50, h=50)
    s2 = Shape(id="s2", name="Shape 2", x=30, y=30, w=50, h=50)
    s3 = Shape(id="s3", name="Shape 3", x=50, y=50, w=50, h=50)
    slide.shapes.extend([s1, s2, s3])
    ws.scene.load_slide(slide)

    assert slide.shapes == [s1, s2, s3]

    # Select s1 and bring to front
    item1 = ws.scene.get_shape_item("s1")
    assert item1 is not None
    item1.setSelected(True)

    win.action_registry.trigger_action("bringFront")
    assert slide.shapes == [s2, s3, s1]

    # Send s1 back
    win.action_registry.trigger_action("sendBack")
    assert slide.shapes == [s1, s2, s3]

    # Bring s1 forward
    win.action_registry.trigger_action("bringForward")
    assert slide.shapes == [s2, s1, s3]

    # Send s1 backward
    win.action_registry.trigger_action("sendBackward")
    assert slide.shapes == [s1, s2, s3]

    # Group s1 and s2
    item1 = ws.scene.get_shape_item("s1")
    item2 = ws.scene.get_shape_item("s2")
    assert item1 is not None and item2 is not None
    ws.scene.clearSelection()
    item1.setSelected(True)
    item2.setSelected(True)

    win.action_registry.trigger_action("group")
    assert len(slide.shapes) == 2
    grp = [s for s in slide.shapes if s.type == "group"][0]
    assert len(grp.kids) == 2

    # Ungroup
    grp_item = ws.scene.get_shape_item(grp.id)
    assert grp_item is not None
    ws.scene.clearSelection()
    grp_item.setSelected(True)

    win.action_registry.trigger_action("ungroup")
    assert len(slide.shapes) == 3


def test_shape_alignment_actions(qtbot) -> None:
    from atboffice.modules.presentation.models.shape import Shape

    win = LecternWindow()
    qtbot.addWidget(win)

    ws = win.presentation_view.workspace
    slide = ws.current_slide
    slide.shapes.clear()

    s1 = Shape(id="s1", name="Shape 1", x=10, y=20, w=50, h=50)
    s2 = Shape(id="s2", name="Shape 2", x=100, y=80, w=50, h=50)
    slide.shapes.extend([s1, s2])
    ws.scene.load_slide(slide)

    item1 = ws.scene.get_shape_item("s1")
    item2 = ws.scene.get_shape_item("s2")
    assert item1 is not None and item2 is not None

    item1.setSelected(True)
    item2.setSelected(True)

    # Align left
    win.action_registry.trigger_action("alignLeft")
    assert round(item1.pos().x(), 1) == 10.0
    assert round(item2.pos().x(), 1) == 10.0

    # Align top
    win.action_registry.trigger_action("alignTop")
    assert round(item1.pos().y(), 1) == 20.0
    assert round(item2.pos().y(), 1) == 20.0


def test_view_mode_switching_actions(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()

    ws = win.presentation_view.workspace

    # Switch to sorter
    win.action_registry.trigger_action("viewSorter")
    assert ws.view_mode == "sorter"
    assert win.toolbars["sorter"].isVisible()

    # Switch to master
    win.action_registry.trigger_action("viewMaster")
    assert ws.view_mode == "master"
    assert win.toolbars["master"].isVisible()

    # Close master
    win.action_registry.trigger_action("closeMaster")
    assert ws.view_mode == "normal"
    assert not win.toolbars["master"].isVisible()

    # Switch to normal
    win.action_registry.trigger_action("viewNormal")
    assert ws.view_mode == "normal"


def test_smartart_diagram_toolbar_actions(qtbot) -> None:
    from atboffice.modules.presentation.models.shape import Shape
    from atboffice.modules.presentation.smartart.engine import relayout

    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()

    ws = win.presentation_view.workspace
    slide = ws.current_slide
    slide.shapes.clear()

    diag = Shape(
        id="diag_1",
        type="group",
        name="ProcessDiagram",
        x=50,
        y=50,
        w=400,
        h=200,
        sa={
            "layout": "process",
            "items": [
                {"id": "n1", "text": "Step 1", "level": 0},
                {"id": "n2", "text": "Step 2", "level": 0},
            ],
        },
    )
    relayout(diag)
    slide.shapes.append(diag)
    ws.scene.load_slide(slide)

    item = ws.scene.get_shape_item(diag.id)
    assert item is not None
    item.setSelected(True)

    # Diagram toolbar auto-shown
    assert win.toolbars["diagram"].isVisible()

    # Add shape
    initial_items_count = len(diag.sa["items"])
    win.action_registry.trigger_action("diagramAddShape")
    assert len(diag.sa["items"]) == initial_items_count + 1

    # Demote & Promote
    win.action_registry.trigger_action("diagramDemote")
    from atboffice.modules.presentation.smartart.item import outline
    tree = outline(diag.sa["items"])
    assert tree[-1]["level"] == 1

    win.action_registry.trigger_action("diagramPromote")
    tree = outline(diag.sa["items"])
    assert tree[-1]["level"] == 0

    # Convert to regular shapes
    win.action_registry.trigger_action("diagramToShapes")
    assert diag.sa is None


def test_slideshow_actions_invoked(qtbot, monkeypatch) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)

    called = []

    def mock_start(from_current=False, fullscreen=True):
        called.append((from_current, fullscreen))

    monkeypatch.setattr(win.presentation_view, "start_slideshow", mock_start)

    win.action_registry.trigger_action("start_slideshow")
    assert (False, True) in called

    win.action_registry.trigger_action("start_slideshow_current")
    assert (True, True) in called

