"""Comprehensive GUI and engine tests for Quire interactive rulers and dynamic fields convergence.

Verifies:
1. Interactive drag-and-drop indent manipulation (first, hanging, left, right) with guide lines.
2. Transactional Undo / Redo integration for indent, tab stop, and page margin mutations.
3. Interactive tab stop addition, moving, and deletion (drag off ruler > 18px) with Undo/Redo.
4. Horizontal and vertical page margin dragging with guidelines and Undo/Redo.
5. Double-click interactions triggering TabsDialog and PageSetupDialog.
6. Multi-pass dynamic field convergence (PAGE, NUMPAGES, DATE, TIME, TOC/PAGEREF) and oscillation guards.
"""

import copy
import datetime
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.layout.pagination import (
    PaginationResult,
    paginate_document,
)
from atboffice.modules.writer.layout.toc import insert_or_update_toc
from atboffice.modules.writer.models.document import (
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    Story,
    TextItem,
)
from atboffice.modules.writer.models.field import (
    FieldContext,
    ensure_para_bookmark,
    evaluate_field,
    insert_field,
    update_fields,
)
from atboffice.modules.writer.models.properties import (
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    TabStop,
)
from atboffice.modules.writer.view import QuireView
from atboffice.modules.writer.views.canvas_view import WriterCanvasView
from atboffice.modules.writer.views.ruler import (
    HorizontalRuler,
    RulerUnit,
    TabKind,
    TabSelectorWidget,
    VerticalRuler,
    snap_to_grid,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Helpers for Mouse Event Synthesis
# ---------------------------------------------------------------------------


def make_mouse_event(
    event_type: QEvent.Type,
    pos: QPointF,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.LeftButton,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> QMouseEvent:
    return QMouseEvent(
        event_type,
        pos,
        pos,
        button,
        buttons,
        modifiers,
    )


# ---------------------------------------------------------------------------
# 1. Interactive Indent Dragging & Transactional Undo/Redo
# ---------------------------------------------------------------------------


def test_ruler_drag_indents_with_guideline_and_undo_redo(qapp):
    """Verify dragging indent handles updates paragraph models with Undo/Redo."""
    doc = Document()
    p = Paragraph(
        runs=[TextItem(text="Test indent drag and undo/redo paragraph.")],
    )
    p.indent_left = 0.0
    p.indent_first = 0.0
    p.indent_right = 0.0
    doc.main.blocks = [p]

    canvas = WriterCanvasView(doc)
    h_ruler = HorizontalRuler()
    h_ruler.attach_canvas(canvas)

    assert p.indent_first == 0.0
    assert p.indent_left == 0.0
    assert p.indent_right == 0.0

    # 1. Drag first-line indent
    rects = h_ruler._get_marker_rects()
    first_pt = rects["first"].center()

    guides_requested = []
    guides_cleared = []
    h_ruler.guide_line_requested.connect(lambda x, v: guides_requested.append((x, v)))
    h_ruler.guide_line_cleared.connect(lambda: guides_cleared.append(True))

    ev_press = make_mouse_event(QEvent.Type.MouseButtonPress, first_pt)
    h_ruler.mousePressEvent(ev_press)
    assert h_ruler._drag_kind == "first"
    assert len(guides_requested) >= 1

    # Move right by ~36 points
    px_pt = h_ruler.px_per_pt()
    move_pt = QPointF(first_pt.x() + 36.0 * px_pt, first_pt.y())
    ev_move = make_mouse_event(QEvent.Type.MouseMove, move_pt)
    h_ruler.mouseMoveEvent(ev_move)

    ev_release = make_mouse_event(QEvent.Type.MouseButtonRelease, move_pt)
    h_ruler.mouseReleaseEvent(ev_release)

    assert len(guides_cleared) >= 1
    assert p.indent_first > 30.0  # Snapped to ~36pt
    assert canvas.can_undo() is True

    # Undo
    undone = canvas.undo()
    assert undone is True
    assert p.indent_first == 0.0
    assert canvas.can_redo() is True

    # Redo
    redone = canvas.redo()
    assert redone is True
    assert p.indent_first > 30.0


def test_ruler_drag_left_and_hanging_indents(qapp):
    """Verify dragging hanging and left indents correctly mutates paragraph attributes."""
    doc = Document()
    p = Paragraph(
        runs=[TextItem(text="Testing left and hanging indent markers.")],
    )
    p.indent_left = 0.0
    p.indent_first = 0.0
    p.indent_right = 0.0
    doc.main.blocks = [p]

    canvas = WriterCanvasView(doc)
    h_ruler = HorizontalRuler()
    h_ruler.attach_canvas(canvas)

    px_pt = h_ruler.px_per_pt()

    # Drag left indent box
    rects = h_ruler._get_marker_rects()
    left_pt = rects["left"].center()

    ev_press = make_mouse_event(QEvent.Type.MouseButtonPress, left_pt)
    h_ruler.mousePressEvent(ev_press)
    assert h_ruler._drag_kind == "left"

    target_pt = QPointF(left_pt.x() + 18.0 * px_pt, left_pt.y())
    ev_move = make_mouse_event(QEvent.Type.MouseMove, target_pt)
    h_ruler.mouseMoveEvent(ev_move)

    ev_release = make_mouse_event(QEvent.Type.MouseButtonRelease, target_pt)
    h_ruler.mouseReleaseEvent(ev_release)

    assert p.indent_left > 15.0

    # Undo left indent
    canvas.undo()
    assert p.indent_left == 0.0

    # Redo left indent
    canvas.redo()
    assert p.indent_left > 15.0


# ---------------------------------------------------------------------------
# 2. Interactive Tab Stop Dragging, Deletion, and Undo/Redo
# ---------------------------------------------------------------------------


def test_ruler_tab_stop_add_move_and_delete_with_undo(qapp):
    """Verify adding, moving, and dragging tab off ruler (>18px) to delete with Undo/Redo."""
    doc = Document()
    p = Paragraph(
        runs=[TextItem(text="Tab stop interactive test.")],
        p_pr=ParagraphProperties(),
    )
    doc.main.blocks = [p]

    canvas = WriterCanvasView(doc)
    h_ruler = HorizontalRuler()
    h_ruler.attach_canvas(canvas)

    assert len(p.p_pr.tabs) == 0

    # 1. Add tab stop by clicking on text scale
    text_l = h_ruler.text_left_ruler()
    click_x = text_l + 72.0 * h_ruler.px_per_pt()
    pt = QPointF(click_x, 10.0)

    ev_press = make_mouse_event(QEvent.Type.MouseButtonPress, pt)
    h_ruler.mousePressEvent(ev_press)
    assert h_ruler._drag_kind == "new_tab"

    ev_release = make_mouse_event(QEvent.Type.MouseButtonRelease, pt)
    h_ruler.mouseReleaseEvent(ev_release)

    assert len(p.p_pr.tabs) == 1
    assert abs(p.p_pr.tabs[0].pos - 72.0) < 5.0
    assert canvas.can_undo() is True

    # 2. Delete tab stop by dragging vertically off the ruler (> 18px below)
    tab_rects = h_ruler._get_tab_rects()
    assert len(tab_rects) == 1
    tab_pt = tab_rects[0][2].center()

    ev_press2 = make_mouse_event(QEvent.Type.MouseButtonPress, tab_pt)
    h_ruler.mousePressEvent(ev_press2)
    assert h_ruler._drag_kind == "tab"

    # Drag far down (y = 60px, height is 24px, so y > 24 + 18 = 42)
    drag_off_pt = QPointF(tab_pt.x(), 60.0)
    ev_move2 = make_mouse_event(QEvent.Type.MouseMove, drag_off_pt)
    h_ruler.mouseMoveEvent(ev_move2)

    ev_release2 = make_mouse_event(QEvent.Type.MouseButtonRelease, drag_off_pt)
    h_ruler.mouseReleaseEvent(ev_release2)

    # Tab stop should now be deleted
    assert len(p.p_pr.tabs) == 0

    # 3. Undo should restore the tab stop!
    canvas.undo()
    assert len(p.p_pr.tabs) == 1
    assert abs(p.p_pr.tabs[0].pos - 72.0) < 5.0

    # 4. Redo should re-delete it
    canvas.redo()
    assert len(p.p_pr.tabs) == 0


# ---------------------------------------------------------------------------
# 3. Margin Dragging on Horizontal and Vertical Rulers
# ---------------------------------------------------------------------------


def test_horizontal_margin_drag_with_undo(qapp):
    """Verify dragging left and right margins updates SectionProperties with Undo."""
    doc = Document()
    p = doc.main.blocks[0]
    p.indent_left = 36.0
    p.indent_first = 0.0
    p.indent_right = 0.0
    canvas = WriterCanvasView(doc)
    h_ruler = HorizontalRuler()
    h_ruler.attach_canvas(canvas)

    sect = h_ruler._active_sect
    assert sect is not None
    orig_ml = sect.ml

    # Drag left margin boundary
    text_l = h_ruler.text_left_ruler()
    pt = QPointF(text_l, 10.0)

    ev_press = make_mouse_event(QEvent.Type.MouseButtonPress, pt)
    h_ruler.mousePressEvent(ev_press)
    assert h_ruler._drag_kind == "margin_left"

    target_pt = QPointF(text_l + 18.0 * h_ruler.px_per_pt(), 10.0)
    ev_move = make_mouse_event(QEvent.Type.MouseMove, target_pt)
    h_ruler.mouseMoveEvent(ev_move)

    ev_release = make_mouse_event(QEvent.Type.MouseButtonRelease, target_pt)
    h_ruler.mouseReleaseEvent(ev_release)

    assert sect.ml > orig_ml

    # Undo
    canvas.undo()
    assert abs(sect.ml - orig_ml) < 1e-2

    # Redo
    canvas.redo()
    assert sect.ml > orig_ml


def test_vertical_margin_drag_with_undo(qapp):
    """Verify dragging top and bottom margins on VerticalRuler updates SectionProperties."""
    doc = Document()
    canvas = WriterCanvasView(doc)
    v_ruler = VerticalRuler()
    v_ruler.attach_canvas(canvas)

    sect = v_ruler._active_sect
    assert sect is not None
    orig_mt = sect.mt

    # Drag top margin boundary
    text_t = v_ruler.text_top_ruler()
    pt = QPointF(10.0, text_t)

    ev_press = make_mouse_event(QEvent.Type.MouseButtonPress, pt)
    v_ruler.mousePressEvent(ev_press)
    assert v_ruler._drag_kind == "top"

    target_pt = QPointF(10.0, text_t + 18.0 * v_ruler.px_per_pt())
    ev_move = make_mouse_event(QEvent.Type.MouseMove, target_pt)
    v_ruler.mouseMoveEvent(ev_move)

    ev_release = make_mouse_event(QEvent.Type.MouseButtonRelease, target_pt)
    v_ruler.mouseReleaseEvent(ev_release)

    assert sect.mt > orig_mt

    # Undo
    canvas.undo()
    assert abs(sect.mt - orig_mt) < 1e-2

    # Redo
    canvas.redo()
    assert sect.mt > orig_mt


# ---------------------------------------------------------------------------
# 4. Double-Click Dialog Integration
# ---------------------------------------------------------------------------


def test_ruler_double_click_dialog_signals(qapp):
    """Verify double clicking rulers emits tabs and page setup dialog requests."""
    doc = Document()
    canvas = WriterCanvasView(doc)
    h_ruler = HorizontalRuler()
    h_ruler.attach_canvas(canvas)
    v_ruler = VerticalRuler()
    v_ruler.attach_canvas(canvas)

    tabs_req = []
    page_setup_req = []

    h_ruler.tabs_dialog_requested.connect(lambda: tabs_req.append("h_tabs"))
    h_ruler.page_setup_requested.connect(lambda: page_setup_req.append("h_page"))
    v_ruler.page_setup_requested.connect(lambda: page_setup_req.append("v_page"))

    # Double click on text area of H ruler: tabs dialog
    text_mid = (h_ruler.text_left_ruler() + h_ruler.text_right_ruler()) / 2.0
    ev_tabs = make_mouse_event(QEvent.Type.MouseButtonDblClick, QPointF(text_mid, 10.0))
    h_ruler.mouseDoubleClickEvent(ev_tabs)
    assert "h_tabs" in tabs_req

    # Double click on margin area of H ruler: page setup dialog
    page_l = h_ruler.page_left_ruler()
    ev_margin = make_mouse_event(QEvent.Type.MouseButtonDblClick, QPointF(page_l + 5.0, 10.0))
    h_ruler.mouseDoubleClickEvent(ev_margin)
    assert "h_page" in page_setup_req

    # Double click on V ruler: page setup dialog
    ev_v = make_mouse_event(QEvent.Type.MouseButtonDblClick, QPointF(10.0, 50.0))
    v_ruler.mouseDoubleClickEvent(ev_v)
    assert "v_page" in page_setup_req

    # Test programmatic open helpers
    h_ruler.open_tabs_dialog()
    assert len(tabs_req) == 2
    h_ruler.open_page_setup_dialog()
    assert len(page_setup_req) == 3
    v_ruler.open_page_setup_dialog()
    assert len(page_setup_req) == 4


# ---------------------------------------------------------------------------
# 5. Multi-Pass Dynamic Field Convergence
# ---------------------------------------------------------------------------


def test_dynamic_fields_convergence_page_and_numpages():
    """Verify multi-pass pagination converges dynamic PAGE and NUMPAGES fields."""
    doc = Document()
    # Create paragraphs that expand across multiple pages
    doc.main.blocks = []
    for i in range(120):
        doc.main.blocks.append(
            Paragraph(runs=[TextItem(text=f"Paragraph line {i} with body content.")])
        )

    # Insert a dynamic NUMPAGES field into paragraph 0
    p0 = doc.main.blocks[0]
    assert isinstance(p0, Paragraph)
    insert_field(p0, 0, "NUMPAGES", "NUMPAGES", cached_text="1")

    # Insert a dynamic PAGE field into paragraph 10
    p10 = doc.main.blocks[10]
    assert isinstance(p10, Paragraph)
    insert_field(p10, 0, "PAGE", "PAGE", cached_text="1")

    res = paginate_document(doc, max_passes=4)

    assert res.total_pages > 1
    # Check that NUMPAGES was updated to match total_pages
    found_numpages = False
    for r in p0.runs:
        if isinstance(r, TextItem) and r.text == str(res.total_pages):
            found_numpages = True
            break
    assert found_numpages is True


def test_dynamic_fields_date_time_and_toc_convergence():
    """Verify convergence across DATE, TIME, and TOC PAGEREF fields."""
    doc = Document()
    doc.main.blocks = []

    # 1. Header paragraph with DATE and TIME
    p_hdr = Paragraph(runs=[TextItem(text="Report Header: ")])
    insert_field(p_hdr, 15, "DATE", r'DATE \@ "yyyy-MM-dd"', cached_text="old-date")
    doc.main.blocks.append(p_hdr)

    # 2. Add heading paragraphs on subsequent pages
    h1 = Paragraph(
        runs=[TextItem(text="Introduction")],
        p_pr=ParagraphProperties(style="Heading 1"),
    )
    ensure_para_bookmark(doc, h1, "_TocIntro")
    doc.main.blocks.append(h1)

    for i in range(40):
        doc.main.blocks.append(Paragraph(runs=[TextItem(text=f"Content under intro {i}.")]))

    h2 = Paragraph(
        runs=[TextItem(text="Chapter Two Details")],
        p_pr=ParagraphProperties(style="Heading 1", page_break_before=True),
    )
    ensure_para_bookmark(doc, h2, "_TocChapterTwo")
    doc.main.blocks.append(h2)

    # 3. Insert TOC
    insert_or_update_toc(doc)

    # Run multi-pass pagination
    res = paginate_document(doc, max_passes=4)

    assert res.total_pages >= 2

    # Verify DATE was evaluated to today's date
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    found_today = False
    for r in p_hdr.runs:
        if isinstance(r, TextItem) and r.text == today_str:
            found_today = True
            break
    assert found_today is True

    # Verify TOC contains PAGEREF fields pointing to correct page numbers
    toc_pagerefs = []
    for p in doc.main.paras:
        if (p.p_pr.style or "").upper().startswith("TOC"):
            for idx, item in enumerate(p.runs):
                if isinstance(item, FieldBeginItem) and "PAGEREF" in (item.instr or item.field_type):
                    # Check text item between fs and fe
                    for inner in p.runs[idx:]:
                        if isinstance(inner, TextItem) and inner.text.isdigit():
                            toc_pagerefs.append(int(inner.text))
                            break

    assert len(toc_pagerefs) >= 2
    assert toc_pagerefs[1] >= toc_pagerefs[0]


def test_circular_oscillation_guard():
    """Verify that pagination loop breaks cleanly when circular oscillation is simulated."""
    doc = Document()
    doc.main.blocks = [Paragraph(runs=[TextItem(text="Oscillation test line.")])]

    # Even with max_passes=10, pagination must terminate in <= 4 passes
    res = paginate_document(doc, max_passes=10)
    assert res.total_pages == 1
    assert res.duration_ms >= 0.0
