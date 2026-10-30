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
    cell_p = win.writer_view.canvas_view.get_current_table_context()["tbl"].rows[0].cells[0].blocks[0]
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



