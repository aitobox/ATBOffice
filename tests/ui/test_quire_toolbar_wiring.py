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

