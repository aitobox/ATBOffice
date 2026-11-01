"""Integration tests for Quire toolbar wiring and canvas formatting."""

from __future__ import annotations

from atboffice.modules.writer.models.document import Document
from atboffice.modules.writer.views.canvas_view import WriterCanvasView
from atboffice.modules.writer.views.caret_controller import DocPos, Selection


def test_paragraph_formatting(qtbot) -> None:
    doc = Document()
    canvas = WriterCanvasView(doc=doc)
    qtbot.addWidget(canvas)

    # 1. Alignment
    canvas.set_paragraph_alignment("center")
    p = canvas.doc.main.paras[0]
    assert p.p_pr.jc == "center"

    canvas.set_paragraph_alignment("right")
    assert p.p_pr.jc == "right"

    # 2. Indentation
    initial_indent = p.p_pr.ind.left if p.p_pr.ind else 0.0
    canvas.change_indent(36.0)
    assert p.p_pr.ind.left == initial_indent + 36.0

    canvas.change_indent(-36.0)
    assert p.p_pr.ind.left == initial_indent

    # 3. Line spacing
    canvas.set_line_spacing(2.0)
    assert p.p_pr.sp.line == 2.0


def test_character_formatting(qtbot) -> None:
    doc = Document()
    canvas = WriterCanvasView(doc=doc)
    qtbot.addWidget(canvas)

    # Insert text "Hello world"
    canvas.controller.insert_text("Hello world")
    p = canvas.doc.main.paras[0]

    # Select "Hello" (offset 0 to 5)
    canvas.controller.pos = DocPos(p.id, 5)
    canvas.controller.selection = Selection(DocPos(p.id, 0), DocPos(p.id, 5))

    # Toggle bold
    canvas.toggle_character_format("bold")
    assert any(getattr(r, "text", "") == "Hello" and r.r_pr.b for r in p.runs)

    # Toggle italic
    canvas.toggle_character_format("italic")
    assert any(getattr(r, "text", "") == "Hello" and r.r_pr.i for r in p.runs)

    # Toggle underline
    canvas.toggle_character_format("underline")
    assert any(getattr(r, "text", "") == "Hello" and r.r_pr.u != "none" for r in p.runs)

    # Font family & size
    canvas.set_font_family("Arial")
    assert any(getattr(r, "text", "") == "Hello" and r.r_pr.font == "Arial" for r in p.runs)

    canvas.set_font_size(18.0)
    assert any(getattr(r, "text", "") == "Hello" and r.r_pr.sz == 18.0 for r in p.runs)


def test_list_style_toggle(qtbot) -> None:
    doc = Document()
    canvas = WriterCanvasView(doc=doc)
    qtbot.addWidget(canvas)

    p = canvas.doc.main.paras[0]
    assert p.p_pr.num is None

    # Toggle bullet list
    canvas.toggle_list_style("bullet")
    assert p.p_pr.num is not None

    # Toggle off
    canvas.toggle_list_style("bullet")
    assert p.p_pr.num is None

    # Toggle numbering
    canvas.toggle_list_style("number")
    assert p.p_pr.num is not None


def test_table_operations(qtbot) -> None:
    doc = Document()
    canvas = WriterCanvasView(doc=doc)
    qtbot.addWidget(canvas)

    assert canvas.get_current_table_context() is None

    # Insert table
    canvas.insert_table(2, 2)
    ctx = canvas.get_current_table_context()
    assert ctx is not None
    tbl = ctx["tbl"]
    assert len(tbl.rows) == 2
    assert len(tbl.grid) == 2

    # Insert row & col
    canvas.insert_table_row(above=False)
    assert len(tbl.rows) == 3

    canvas.insert_table_col(left=False)
    assert len(tbl.grid) == 3

    # Delete row & col
    canvas.delete_table_row()
    assert len(tbl.rows) == 2

    canvas.delete_table_col()
    assert len(tbl.grid) == 2

    # Distribute rows & cols
    canvas.distribute_table_rows()
    assert all(r.tr_pr.h == 24.0 for r in tbl.rows)

    canvas.distribute_table_cols()
    assert tbl.grid[0] == tbl.grid[1]


def test_revision_and_outline_operations(qtbot) -> None:
    doc = Document()
    canvas = WriterCanvasView(doc=doc)
    qtbot.addWidget(canvas)

    # 1. Track changes
    tracking = canvas.toggle_track_changes()
    assert tracking is True

    # 2. Comment
    canvas.insert_comment(author="Reviewer", text="Looks good")
    assert len(canvas.doc.comments) > 0

    # 3. Outline level
    canvas.set_outline_level(3)
    p = canvas.doc.main.paras[0]
    assert p.p_pr.outline_level == 3

    # Promote (level - 1)
    canvas.change_outline_level(-1)
    assert p.p_pr.outline_level == 2

    # Demote (level + 1)
    canvas.change_outline_level(1)
    assert p.p_pr.outline_level == 3


def test_quire_window_toolbar_actions_wired(qtbot) -> None:
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)

    # 1. Trigger alignCenter
    win.action_registry.trigger_action("alignCenter")
    p = win.writer_view.canvas_view.doc.main.paras[0]
    assert p.p_pr.jc == "center"

    # 2. Trigger incIndent
    initial_indent = p.p_pr.ind.left if p.p_pr.ind else 0.0
    win.action_registry.trigger_action("incIndent")
    assert p.p_pr.ind.left == initial_indent + 36.0

    # 3. Trigger bold
    win.action_registry.trigger_action("bold")
    assert p.r_pr.b is True

    # 4. Trigger bullets
    win.action_registry.trigger_action("bullets")
    assert p.p_pr.num is not None

    # 5. Trigger trackChanges
    win.action_registry.trigger_action("trackChanges")
    from atboffice.modules.writer.models.revision import is_tracking
    assert is_tracking(win.writer_view.canvas_view.doc) is True


def test_quire_window_caret_sync_and_table_context(qtbot) -> None:
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)
    win.show()

    # Tables toolbar initially hidden
    assert not win.toolbars["tables"].isVisible()

    # Insert table
    win.writer_view.canvas_view.insert_table(2, 2)

    # After inserting table, caret is placed inside table
    # Move caret to cell paragraph to trigger sync
    ctx = win.writer_view.canvas_view.get_current_table_context()
    cell_p = ctx["tbl"].rows[0].cells[0].blocks[0]
    win.writer_view.canvas_view.caret_moved.emit(cell_p.id, 0)

    # Tables toolbar should now be automatically visible
    assert win.toolbars["tables"].isVisible()


def test_quire_window_table_actions_via_registry(qtbot) -> None:
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)

    # Insert table
    win.writer_view.canvas_view.insert_table(2, 2)
    ctx = win.writer_view.canvas_view.get_current_table_context()
    tbl = ctx["tbl"]

    # Trigger distRows & distCols via action_registry
    win.action_registry.trigger_action("distRows")
    assert all(r.tr_pr.h == 24.0 for r in tbl.rows)

    win.action_registry.trigger_action("distCols")
    assert tbl.grid[0] == tbl.grid[1]

    # Trigger splitCells
    win.action_registry.trigger_action("splitCells")
    assert len(tbl.rows[0].cells) > 2


def test_quire_window_combos_and_toggles(qtbot) -> None:
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)
    win.show()

    # 1. Font combo change
    win.font_combo.setCurrentText("Arial")
    p = win.writer_view.canvas_view.doc.main.paras[0]
    assert p.r_pr.font == "Arial"

    # 2. Size combo change
    win.size_combo.setCurrentText("16")
    assert p.r_pr.sz == 16.0

    # 3. Zoom combo change
    win.zoom_combo.setCurrentText("200%")
    assert round(win.writer_view.canvas_view._zoom, 1) == 2.0

    # 4. Outline combo change
    win.outline_level_combo.setCurrentIndex(1)  # Level 2
    assert p.p_pr.outline_level == 2

    # 5. Toolbar toggles
    initial_drawing_visible = win.toolbars["drawing"].isVisible()
    win.action_registry.trigger_action("tb_drawing")
    assert win.toolbars["drawing"].isVisible() != initial_drawing_visible


def test_quire_toolbar_dropdown_and_split_wiring(qtbot) -> None:
    """Verify Quire dropdown and split buttons are properly instantiated and wired."""
    from atboffice.ui.components.toolbar_buttons import (
        OfficeDropDownButton,
        OfficeSplitButton,
    )
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)

    # 1. Dropdown buttons present across toolbars
    drop_buttons = win.findChildren(OfficeDropDownButton)
    assert len(drop_buttons) >= 10

    # 2. Split buttons present across toolbars
    split_buttons = win.findChildren(OfficeSplitButton)
    assert len(split_buttons) >= 4

    # 3. Action registry contains wired items from menus
    expected_actions = [
        "undo_empty",
        "redo_empty",
        "insertTable_dialog",
        "insertTable_col_left",
        "insertTable_row_above",
        "col_1",
        "col_2",
        "col_3",
        "line_spacing_1_0",
        "line_spacing_1_5",
        "line_spacing_2_0",
        "line_spacing_3_0",
        "border_none",
        "border_all",
        "border_outside",
        "border_bottom",
        "tbl_insert_table",
        "tbl_insert_col_left",
        "tbl_insert_row_above",
        "tbl_align_top",
        "tbl_align_center",
        "tbl_align_bottom",
        "rev_accept_selected",
        "rev_accept_all",
        "rev_reject_selected",
        "rev_reject_all",
        "draw_order_front",
        "draw_order_back",
        "as_lines",
        "as_basic",
        "as_arrows",
    ]
    for aid in expected_actions:
        assert win.action_registry.has_action(aid), f"Missing action {aid} in action_registry"


def test_quire_toolbar_actions_trigger_and_state(qtbot) -> None:
    """Verify triggering dropdown/split actions mutates document/canvas state."""
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)
    canvas = win.writer_view.canvas_view

    # 1. Test line spacing trigger
    win.action_registry.trigger_action("line_spacing_1_5")
    p = canvas.doc.main.paras[0]
    assert p.p_pr.sp.line == 1.5

    win.action_registry.trigger_action("line_spacing_2_0")
    assert p.p_pr.sp.line == 2.0

    # 2. Test border preset on paragraph
    win.action_registry.trigger_action("border_all")
    assert p.p_pr.borders == {"preset": "all"}

    win.action_registry.trigger_action("border_none")
    assert p.p_pr.borders == {"preset": "none"}

    # 3. Test table insertion and table cell alignment via dropdown actions
    win.action_registry.trigger_action("tbl_insert_table")
    ctx = canvas.get_current_table_context()
    assert ctx is not None

    win.action_registry.trigger_action("tbl_align_center")
    cell = ctx["tbl"].rows[ctx["row_idx"]].cells[ctx["col_idx"]]
    assert cell.tc_pr.valign == "center"

    # 4. Test column insertion
    initial_cols = len(ctx["tbl"].grid)
    win.action_registry.trigger_action("tbl_insert_col_left")
    assert len(ctx["tbl"].grid) == initial_cols + 1

    # 5. Test autoshapes trigger
    win.action_registry.trigger_action("as_basic")
    win.action_registry.trigger_action("draw_order_front")


def test_quire_toolbar_context_state_switching(qtbot) -> None:
    """Verify contextual enable/disable state transitions.

    Tests state changes when entering/leaving tables and revisions.
    """
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)
    win.show()
    canvas = win.writer_view.canvas_view

    # 1. Outside table: table actions should be disabled
    act_merge = win.action_registry.get_action("mergeCells")
    act_split = win.action_registry.get_action("splitCells")
    act_dist = win.action_registry.get_action("distRows")
    assert not act_merge.isEnabled()
    assert not act_split.isEnabled()
    assert not act_dist.isEnabled()

    # Tables toolbar is hidden outside table
    assert not win.toolbars["tables"].isVisible()

    # 2. Insert table: table actions become enabled and tables toolbar visible
    canvas.insert_table(2, 2)
    ctx = canvas.get_current_table_context()
    cell_p = ctx["tbl"].rows[0].cells[0].blocks[0]
    canvas.caret_moved.emit(cell_p.id, 0)

    assert win.toolbars["tables"].isVisible()
    assert act_merge.isEnabled()
    assert act_split.isEnabled()
    assert act_dist.isEnabled()

    # 3. Revisions enable/disable
    act_accept = win.action_registry.get_action("acceptChange")
    act_reject = win.action_registry.get_action("rejectChange")
    assert not act_accept.isEnabled()
    assert not act_reject.isEnabled()

    # Add a comment / revision
    canvas.insert_comment(author="Editor", text="Check this")
    canvas.caret_moved.emit(cell_p.id, 0)
    assert act_accept.isEnabled()
    assert act_reject.isEnabled()


def test_quire_toolbars_7_language_dynamic_retranslate(qtbot) -> None:
    """Verify Quire toolbars and dropdowns dynamically retranslate across 7 languages."""
    from atboffice.core.i18n import load_locale
    from atboffice.ui.components.toolbar_buttons import OfficeDropDownButton
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    qtbot.addWidget(win)

    for locale in ["en", "zh_CN", "zh_TW", "ja", "fr", "de", "es"]:
        load_locale(locale)
        win.retranslate_ui()

        for name, tb in win.toolbars.items():
            assert tb.windowTitle(), f"Toolbar {name} has empty title in {locale}"
            for btn in tb.findChildren(OfficeDropDownButton):
                tip = btn.toolTip()
                assert tip, f"Dropdown button in {name} has empty tooltip in {locale}"




