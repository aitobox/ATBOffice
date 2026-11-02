"""Integration tests for Lectern toolbar wiring, action registration, contextual enablement,
formatting handlers, and 7-language dynamic retranslation.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from atboffice.core.i18n import get_i18n_manager
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.text import Paragraph, TextBody, TextRun
from atboffice.ui.components.toolbar_buttons import OfficeDropDownButton
from atboffice.ui.shell.lectern_toolbars import _LECTERN_DROP_AIDS, _LECTERN_KNOWN_ITEM_AIDS
from atboffice.ui.shell.lectern_window import LecternWindow


def test_lectern_dropdown_and_split_actions_registered(qtbot) -> None:
    """Verify all dropdown buttons and submenu actions in baseline matrix
    are registered in ActionRegistry."""
    win = LecternWindow()
    qtbot.addWidget(win)

    # 1. All dropdown actions in _LECTERN_DROP_AIDS must be registered
    for aid in _LECTERN_DROP_AIDS:
        act = win.action_registry.get_action(aid)
        assert act is not None, f"Dropdown action {aid} was not registered in ActionRegistry"
        assert act.text() != "", f"Dropdown action {aid} has empty label"

    # 2. All submenu items in _LECTERN_KNOWN_ITEM_AIDS must be registered
    for key, (aid, default_label, enabled, checkable) in _LECTERN_KNOWN_ITEM_AIDS.items():
        act = win.action_registry.get_action(aid)
        assert act is not None, f"Submenu action {aid} was not registered in ActionRegistry"
        assert act.text() != "", f"Submenu action {aid} has empty label"
        if checkable:
            assert act.isCheckable(), f"Submenu action {aid} should be checkable"


def test_lectern_selection_context_enablement(qtbot) -> None:
    """Verify contextual enablement for shapes, groups, tables, pictures, WordArt, and diagrams."""
    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()

    ws = win.presentation_view.workspace
    slide = ws.current_slide
    slide.shapes.clear()
    ws.scene.load_slide(slide)

    # Initially no selection
    ws.scene.clearSelection()
    win._sync_toolbar_states()

    act_grp = win.action_registry.get_action("group")
    act_ungrp = win.action_registry.get_action("ungroup")
    act_regrp = win.action_registry.get_action("regroup")
    assert act_grp is not None and not act_grp.isEnabled()
    assert act_ungrp is not None and not act_ungrp.isEnabled()
    assert act_regrp is not None and not act_regrp.isEnabled()

    # Step 1: Add two shapes
    sh1 = Shape(id="s1", type="rect", name="Rect 1", x=10, y=10, w=100, h=100)
    sh2 = Shape(id="s2", type="rect", name="Rect 2", x=150, y=10, w=100, h=100)
    slide.shapes.extend([sh1, sh2])
    ws.scene.load_slide(slide)

    # Select single shape
    item1 = ws.scene.get_shape_item(sh1.id)
    item2 = ws.scene.get_shape_item(sh2.id)
    assert item1 is not None and item2 is not None

    item1.setSelected(True)
    item2.setSelected(False)
    win._sync_toolbar_states()

    assert not act_grp.isEnabled()
    act_bring_front = win.action_registry.get_action("bringFront")
    assert act_bring_front is not None and act_bring_front.isEnabled()

    # Select both shapes
    item2.setSelected(True)
    win._sync_toolbar_states()
    assert act_grp.isEnabled()

    # Group shapes
    win.action_registry.trigger_action("group")
    win._sync_toolbar_states()
    assert act_ungrp.isEnabled()

    # Ungroup shapes
    win.action_registry.trigger_action("ungroup")
    win._sync_toolbar_states()
    assert act_regrp.isEnabled()

    # Regroup shapes
    win.action_registry.trigger_action("regroup")
    win._sync_toolbar_states()
    assert act_ungrp.isEnabled()

    # Step 2: Contextual enablement for Table
    slide.shapes.clear()
    table_shape = Shape(
        id="t1",
        type="table",
        name="Table 1",
        x=50,
        y=50,
        w=300,
        h=200,
        tbl={"rows": 2, "cols": 2},
    )
    slide.shapes.append(table_shape)
    ws.scene.load_slide(slide)

    t_item = ws.scene.get_shape_item(table_shape.id)
    assert t_item is not None
    t_item.setSelected(True)
    win._sync_toolbar_states()

    act_tbl_merge = win.action_registry.get_action("tableMergeCells")
    act_tbl_dist_rows = win.action_registry.get_action("distRows")
    assert act_tbl_merge is not None and act_tbl_merge.isEnabled()
    assert act_tbl_dist_rows is not None and act_tbl_dist_rows.isEnabled()

    # Step 3: Contextual enablement for Picture
    slide.shapes.clear()
    pic_shape = Shape(
        id="p1",
        type="image",
        name="Image 1",
        x=50,
        y=50,
        w=200,
        h=200,
        media_item={"src": "dummy.png"},
    )
    slide.shapes.append(pic_shape)
    ws.scene.load_slide(slide)

    p_item = ws.scene.get_shape_item(pic_shape.id)
    assert p_item is not None
    p_item.setSelected(True)
    win._sync_toolbar_states()

    act_pic_crop = win.action_registry.get_action("picCrop")
    act_pic_rotate = win.action_registry.get_action("rotateLeft")
    assert act_pic_crop is not None and act_pic_crop.isEnabled()
    assert act_pic_rotate is not None and act_pic_rotate.isEnabled()

    # Step 4: Contextual enablement for WordArt
    slide.shapes.clear()
    wa_shape = Shape(
        id="w1",
        type="wordart",
        name="WordArt 1",
        x=50,
        y=50,
        w=200,
        h=50,
    )
    slide.shapes.append(wa_shape)
    ws.scene.load_slide(slide)

    w_item = ws.scene.get_shape_item(wa_shape.id)
    assert w_item is not None
    w_item.setSelected(True)
    win._sync_toolbar_states()

    act_wa_edit = win.action_registry.get_action("wordartEdit")
    act_wa_height = win.action_registry.get_action("waSameHeight")
    assert act_wa_edit is not None and act_wa_edit.isEnabled()
    assert act_wa_height is not None and act_wa_height.isEnabled()


def test_lectern_text_formatting_actions(qtbot) -> None:
    """Verify font bold, italic, underline, size stepping, and alignment actions."""
    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()

    ws = win.presentation_view.workspace
    slide = ws.current_slide
    slide.shapes.clear()

    text_model = TextBody(
        paragraphs=[
            Paragraph(
                runs=[
                    TextRun(
                        text="Test Paragraph",
                        font="Arial",
                        size=18.0,
                        bold=False,
                        italic=False,
                        underline=False,
                    )
                ],
                props={"algn": "l"},
            )
        ]
    )
    shape = Shape(
        id="txt_1", type="text", name="TextBox", x=50, y=50, w=300, h=100, text=text_model
    )
    slide.shapes.append(shape)
    ws.scene.load_slide(slide)

    item = ws.scene.get_shape_item(shape.id)
    assert item is not None
    item.setSelected(True)
    win._sync_toolbar_states()

    # 1. Bold toggle
    act_b = win.action_registry.get_action("bold")
    assert act_b is not None and not act_b.isChecked()
    win.action_registry.trigger_action("bold")
    assert shape.text.paragraphs[0].runs[0].bold is True
    assert act_b.isChecked()

    # 2. Italic toggle
    act_i = win.action_registry.get_action("italic")
    assert act_i is not None and not act_i.isChecked()
    win.action_registry.trigger_action("italic")
    assert shape.text.paragraphs[0].runs[0].italic is True
    assert act_i.isChecked()

    # 3. Underline toggle
    act_u = win.action_registry.get_action("underline")
    assert act_u is not None and not act_u.isChecked()
    win.action_registry.trigger_action("underline")
    assert shape.text.paragraphs[0].runs[0].underline is True
    assert act_u.isChecked()

    # 4. Font stepping (growFont / shrinkFont)
    orig_size = shape.text.paragraphs[0].runs[0].size
    win.action_registry.trigger_action("growFont")
    assert shape.text.paragraphs[0].runs[0].size > orig_size
    new_size = shape.text.paragraphs[0].runs[0].size
    win.action_registry.trigger_action("shrinkFont")
    assert shape.text.paragraphs[0].runs[0].size < new_size

    # 5. Alignment
    win.action_registry.trigger_action("alignCenter")
    assert shape.text.paragraphs[0].props.get("algn") == "ctr"
    act_al_ctr = win.action_registry.get_action("alignCenter")
    assert act_al_ctr is not None and act_al_ctr.isChecked()


def test_lectern_table_and_picture_actions(qtbot) -> None:
    """Verify table insertion, picture manipulation, and toolbar toggling."""
    win = LecternWindow()
    qtbot.addWidget(win)
    win.show()

    ws = win.presentation_view.workspace
    slide = ws.current_slide
    slide.shapes.clear()

    # 1. Insert table via toolbar action
    win.action_registry.trigger_action("insertTable")
    assert len(slide.shapes) == 1
    tbl_shape = slide.shapes[0]
    assert tbl_shape.type == "table"
    assert tbl_shape.tbl is not None
    assert len(tbl_shape.tbl["rows"]) == 2
    assert len(tbl_shape.tbl["cols"]) == 2

    # 2. Picture manipulation (rotation)
    pic_shape = Shape(id="p1", type="image", name="Pic", x=10, y=10, w=100, h=100)
    slide.shapes.append(pic_shape)
    ws.scene.load_slide(slide)
    p_item = ws.scene.get_shape_item("p1")
    assert p_item is not None
    p_item.setSelected(True)
    win._sync_toolbar_states()

    rot_init = pic_shape.rot
    win.action_registry.trigger_action("rotateLeft")
    assert pic_shape.rot == (rot_init - 90.0) % 360.0

    # 3. Toggle tables toolbar
    tbl_tb = win.toolbars.get("tables")
    assert tbl_tb is not None
    initial_visible = tbl_tb.isVisible()
    win.action_registry.trigger_action("tb_tables")
    assert tbl_tb.isVisible() != initial_visible

    # 4. Color / grayscale mode toggle
    win.action_registry.trigger_action("view_grayscale")
    act_gray = win.action_registry.get_action("view_grayscale")
    assert act_gray is not None and act_gray.isChecked()


def test_lectern_7_language_deep_retranslate(qtbot) -> None:
    """Verify dynamic UI retranslation across all 7 supported languages without errors."""
    win = LecternWindow()
    qtbot.addWidget(win)

    mgr = get_i18n_manager()
    languages = ["zh-CN", "zh-Hant", "en", "ja", "ko", "fr", "de"]

    for lang in languages:
        mgr.set_locale(lang)
        win.retranslate_ui()

        # Check window title
        assert win.windowTitle() != ""

        # Check all 10 toolbars have non-empty window titles
        for name, tb in win.toolbars.items():
            assert tb.windowTitle() != "", f"Toolbar '{name}' has empty title in language {lang}"

        # Check dropdown buttons have non-empty text or tooltip
        for name, tb in win.toolbars.items():
            for child in tb.findChildren(OfficeDropDownButton):
                assert child.text() != "" or child.toolTip() != "", (
                    f"DropDown button {child.objectName()} in {name} is empty in {lang}"
                )

        # Check comboboxes are populated
        fmt_tb = win.toolbars.get("formatting")
        if fmt_tb:
            size_combo = fmt_tb.findChild(QComboBox, "Lectern_SizeCombo")
            if size_combo:
                assert size_combo.count() > 0

        # Check random sample of actions in action registry have non-empty text
        for aid in ("new", "open", "save", "bold", "italic", "underline", "group", "ungroup"):
            act = win.action_registry.get_action(aid)
            if act:
                assert act.text() != "", f"Action {aid} has empty text in language {lang}"

    # Reset back to default zh-CN
    mgr.set_locale("zh-CN")
    win.retranslate_ui()
