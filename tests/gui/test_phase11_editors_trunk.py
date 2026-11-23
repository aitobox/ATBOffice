"""Issue #447: editor trunk gaps across Quire, Ledger and Lectern."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import Slide, Transition
from atboffice.modules.spreadsheet.models.sheet_model import Table, TableColumn
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    TextItem,
)
from atboffice.modules.writer.models.document import Table as WTable
from atboffice.modules.writer.models.drawing import (
    FloatProperties,
    PictureItem,
    PositionH,
    PositionV,
)
from atboffice.modules.writer.models.properties import RevisionStamp, RunProperties

# ============================================================================ Quire


def _portions(canvas):
    return [
        po
        for pg in canvas.pagination.pages
        for reg in pg.regions
        for col in reg.columns
        for fr in col.fragments
        for ln in fr.lines
        for po in ln.portions
        if po.text
    ]


@pytest.fixture
def quire(qapp):
    from atboffice.ui.shell.quire_window import QuireWindow

    win = QuireWindow()
    win.resize(1200, 900)
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def _tracked_doc() -> Document:
    doc = Document()
    p = Paragraph()
    p.runs = [
        TextItem("Keep "),
        TextItem("added ", RunProperties(ins=RevisionStamp(author="Ann"))),
        TextItem("removed", RunProperties(del_rev=RevisionStamp(author="Bob"))),
    ]
    doc.main.blocks = [p]
    return doc


def test_quire_track_changes_inline_markup_and_display_modes(quire):
    from atboffice.modules.writer.layout import revisions
    from atboffice.ui.shell.quire_commands import QuireToolbarCommands

    canvas = quire.writer_view.canvas_view
    canvas.set_document(_tracked_doc())
    cmds = QuireToolbarCommands(quire)

    def text():
        return "".join(po.text for po in _portions(canvas))

    cmds.set_revision_view("final_markup")
    assert text() == "Keep added removed"
    styled = {po.text.strip(): po for po in _portions(canvas)}
    assert styled["added"].underline and not styled["added"].strikethrough
    assert styled["removed"].strikethrough
    assert styled["added"].color != styled["removed"].color  # distinct author colours
    assert revisions.author_color(RevisionStamp(author="Ann")) in revisions.AUTHOR_COLORS

    cmds.set_revision_view("final")
    assert text() == "Keep added "
    cmds.set_revision_view("original")
    assert text() == "Keep removed"
    cmds.set_revision_view("original_markup")
    assert text() == "Keep added removed"
    styled = {po.text.strip(): po for po in _portions(canvas)}
    assert styled["added"].strikethrough and not styled["removed"].strikethrough

    # Show > Insertions and Deletions off: same text, no markup
    cmds.set_revision_view("final_markup")
    cmds.toggle_show("show_ins_del")
    styled = {po.text.strip(): po for po in _portions(canvas)}
    assert text() == "Keep added removed"
    assert not styled["added"].underline and not styled["removed"].strikethrough


def _long_doc(paras: int = 120) -> Document:
    doc = Document()
    doc.main.blocks = [Paragraph(runs=[TextItem(f"Paragraph {i} " * 6)]) for i in range(paras)]
    return doc


def test_quire_view_modes_differ_in_layout(quire, qapp):
    from atboffice.modules.writer.views.view_modes import ViewMode

    canvas = quire.writer_view.canvas_view
    canvas.set_document(_long_doc())
    qapp.processEvents()
    assert len(canvas.pagination.pages) > 1

    quire.switch_view_mode(ViewMode.PRINT)
    print_size = canvas.total_canvas_size()
    print_slots = [canvas.page_rect_canvas(i) for i in range(2)]
    assert print_slots[1].top() > print_slots[0].bottom()  # gap between paper pages

    quire.switch_view_mode(ViewMode.NORMAL)
    slots = canvas.page_slots()
    # Normal: body areas stacked without margins -> the next page starts where the
    # visible text of the previous one ends.
    assert slots[1][1].top() == pytest.approx(slots[0][1].bottom(), abs=1.0)
    assert canvas.total_canvas_size().height() < print_size.height()

    quire.switch_view_mode(ViewMode.WEB)
    qapp.processEvents()
    assert len(canvas.pagination.pages) == 1  # one long reflowed page

    quire.switch_view_mode(ViewMode.READING)
    qapp.processEvents()
    if len(canvas.pagination.pages) > 1:
        slots = canvas.page_slots()
        assert slots[1][0].left() > slots[0][0].right()  # side by side
        assert slots[1][0].top() == pytest.approx(slots[0][0].top())

    quire.switch_view_mode(ViewMode.PRINT)
    assert canvas.total_canvas_size() == print_size


def _vp(canvas, page_idx, x_pt, y_pt) -> QPoint:
    r = canvas.page_rect_canvas(page_idx)
    return QPoint(
        int(r.left() + canvas.pt_to_px(x_pt) - canvas.horizontalScrollBar().value()),
        int(r.top() + canvas.pt_to_px(y_pt) - canvas.verticalScrollBar().value()),
    )


def test_quire_floating_picture_select_move_resize_and_undo(quire):
    canvas = quire.writer_view.canvas_view
    doc = Document()
    pic = PictureItem(
        width=100,
        height=80,
        float_pr=FloatProperties(
            pos_h=PositionH(rel="page", offset=200), pos_v=PositionV(rel="page", offset=300)
        ),
    )
    doc.main.blocks = [Paragraph(runs=[TextItem("Hello "), pic])]
    canvas.set_document(doc)
    vp = canvas.viewport()
    left = Qt.MouseButton.LeftButton
    none = Qt.KeyboardModifier.NoModifier

    QTest.mousePress(vp, left, none, _vp(canvas, 0, 250, 340))
    assert canvas.selected_float() is pic
    QTest.mouseMove(vp, _vp(canvas, 0, 280, 360))
    QTest.mouseRelease(vp, left, none, _vp(canvas, 0, 280, 360))
    assert pic.float_pr.pos_h.offset == pytest.approx(230, abs=1.5)
    assert pic.float_pr.pos_v.offset == pytest.approx(320, abs=1.5)

    fb = canvas.pagination.pages[0].float_boxes[0]
    corner = _vp(canvas, 0, fb.x + fb.w, fb.y + fb.h)
    QTest.mousePress(vp, left, none, corner)
    QTest.mouseMove(vp, corner + QPoint(30, 20))
    QTest.mouseRelease(vp, left, none, corner + QPoint(30, 20))
    assert pic.width > 110 and pic.height > 90

    canvas.undo()
    restored = canvas.doc.main.blocks[0].runs[1]
    assert restored.width == pytest.approx(100)

    # Clicking plain text deselects
    QTest.mouseClick(vp, left, none, _vp(canvas, 0, 95, 80))
    assert canvas.selected_float() is None


def test_quire_aligned_float_becomes_absolute_on_move():
    from atboffice.modules.writer.views import float_edit

    pic = PictureItem(
        width=50,
        height=50,
        float_pr=FloatProperties(pos_h=PositionH(rel="margin", align="center")),
    )
    float_edit.apply_move(pic, 120.0, 40.0, 10.0, 5.0)
    assert pic.float_pr.pos_h.rel == "page" and pic.float_pr.pos_h.align is None
    assert pic.float_pr.pos_h.offset == 130.0
    assert pic.float_pr.pos_v.offset == 5.0  # paragraph-relative offset kept


def test_quire_header_double_click_enters_header_footer_mode(quire):
    canvas = quire.writer_view.canvas_view
    canvas.set_document(_tracked_doc())
    seen = []
    canvas.header_footer_requested.connect(seen.append)
    page = canvas.pagination.pages[0]
    vp = canvas.viewport()

    QTest.mouseDClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                      _vp(canvas, 0, 200, page.body_top / 2))
    assert seen == ["hdr"] and canvas.hf_edit_kind == "hdr"
    assert quire.toolbar_commands.hf_kind == "hdr"  # the Header and Footer toolbar follows

    QTest.mouseDClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                      _vp(canvas, 0, 200, page.height - page.body_bottom_gap / 2))
    assert seen[-1] == "ftr" and canvas.hf_edit_kind == "ftr"

    # Double-click in the body leaves header/footer editing
    QTest.mouseDClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                      _vp(canvas, 0, page.body_left + 5, page.body_top + 5))
    assert canvas.hf_edit_kind is None
    assert canvas.header_footer_zone(0, QPointF(200, page.body_top + 20)) is None


def test_quire_ruler_shows_table_column_markers(quire):
    from atboffice.modules.writer.views.caret_controller import DocPos

    canvas = quire.writer_view.canvas_view
    doc = Document()
    tbl = WTable(grid=[100.0, 150.0], rows=[Row(cells=[Cell(), Cell()])])
    doc.main.blocks = [Paragraph(runs=[TextItem("Before")]), tbl, Paragraph()]
    canvas.set_document(doc)
    ruler = quire.writer_view.h_ruler

    canvas.controller.set_pos(DocPos(doc.main.blocks[0].id, 0))
    ruler.update_geometry_from_canvas()
    assert ruler.table_markers == []

    cell_para = canvas.doc.main.blocks[1].rows[0].cells[0].blocks[0]
    canvas.controller.set_pos(DocPos(cell_para.id, 0))
    ruler.update_geometry_from_canvas()
    marks = ruler.table_markers
    assert len(marks) == 3
    assert marks[1] - marks[0] == pytest.approx(100.0)
    assert marks[2] - marks[1] == pytest.approx(150.0)
    assert not ruler.grab().isNull()


# ============================================================================ Ledger


def _wb():
    wb = WorkbookModel()
    return wb, wb.sheets[0]


def test_ledger_dynamic_array_spills_and_reports_spill_collision():
    from atboffice.modules.spreadsheet.calc import grid_spill

    wb, sh = _wb()
    sh.ensure_cell(0, 0).formula = "SEQUENCE(3,2)"
    sh.ensure_cell(0, 4).formula = "SUM(A1:B3)"
    wb.recalculate()
    assert [[sh.get_cell_value(r, c) for c in range(2)] for r in range(3)] == [
        [1, 2], [3, 4], [5, 6]]
    assert sh.get_cell_value(0, 4) == 21
    assert grid_spill.spill_rect_at(sh, 2, 1) == (0, 0, 2, 1)

    sh.set_cell_value(2, 1, "block")
    wb.recalculate()
    assert str(sh.get_cell_value(0, 0)) == "#SPILL!"
    assert sh.get_cell_value(1, 0) in (None, "")

    sh.set_cell_value(2, 1, None)
    wb.recalculate()
    assert sh.get_cell_value(0, 0) == 1 and sh.get_cell_value(2, 1) == 6


def test_ledger_structured_references_and_implicit_intersection():
    wb, sh = _wb()
    for r, (q, a) in enumerate([("Qty", "Amount"), (2, 10), (3, 20), (4, 30)]):
        sh.set_cell_value(r, 0, q)
        sh.set_cell_value(r, 1, a)
    sh.tables.append(Table(id=1, name="Table1", r1=0, c1=0, r2=3, c2=1, ref="A1:B4",
                           columns=[TableColumn(id=1, name="Qty"),
                                    TableColumn(id=2, name="Amount")]))
    formulas = {
        (0, 4): "SUM(Table1[Amount])",
        (1, 2): "Table1[@Qty]*2",
        (2, 2): "Table1[[#This Row],[Amount]]",
        (0, 5): "ROWS(Table1[#All])",
        (0, 6): "SUM(Table1[[Qty]:[Amount]])",
        (2, 7): "@B1:B4",
    }
    for (r, c), f in formulas.items():
        sh.ensure_cell(r, c).formula = f
    wb.recalculate()
    assert sh.get_cell_value(0, 4) == 60
    assert sh.get_cell_value(1, 2) == 4
    assert sh.get_cell_value(2, 2) == 20
    assert sh.get_cell_value(0, 5) == 4
    assert sh.get_cell_value(0, 6) == 69
    assert sh.get_cell_value(2, 7) == 20


def test_ledger_outline_grouping_collapse_and_levels():
    from atboffice.modules.spreadsheet.models import outline

    _wb_, sh = _wb()
    assert outline.group(sh, "row", 1, 3)
    grp = outline.groups(sh, "row")[0]
    outline.set_collapsed(sh, "row", grp, True)
    assert outline.is_collapsed(sh, "row", grp)
    outline.show_level(sh, "row", 2)
    assert not outline.is_collapsed(sh, "row", grp)
    assert outline.ungroup(sh, "row", 1, 3)
    assert outline.max_level(sh, "row") == 0


def test_ledger_html_round_trip(tmp_path: Path):
    from atboffice.modules.spreadsheet.io import html_io

    wb, sh = _wb()
    sh.set_cell_value(0, 0, "Name")
    sh.set_cell_value(0, 1, "Score")
    sh.set_cell_value(1, 0, "A & B <x>")
    sh.set_cell_value(1, 1, 42)
    out = tmp_path / "book.html"
    html_io.write_html(wb, out)
    tables = html_io.read_html_file(out)
    assert tables
    _wb2, sh2 = _wb()
    html_io.import_table(sh2, tables[0])
    assert sh2.get_cell_value(1, 0) == "A & B <x>"
    assert sh2.get_cell_value(1, 1) == 42


@pytest.fixture
def ledger(qapp):
    from atboffice.ui.shell.ledger_window import LedgerWindow

    win = LedgerWindow()
    win.resize(1000, 700)
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def test_ledger_window_split_and_outline_gutter(ledger, qapp):
    from atboffice.modules.spreadsheet.models import outline

    view = ledger.spreadsheet_view
    grid = view.grid
    for r in range(10):
        grid.model.set_cell_value(r, 0, r)
    outline.group(grid.model, "row", 1, 3)
    grid.outline_changed()
    qapp.processEvents()
    assert grid.viewportMargins().left() > 0
    toggle = next(b for b in grid.outline_gutter.buttons() if b[1] == "toggle-row")
    assert grid.outline_gutter.click(toggle[0].center())
    assert outline.is_collapsed(grid.model, "row", outline.groups(grid.model, "row")[0])

    assert view.toggle_split() is True
    assert view.toggle_split() is False


def test_ledger_page_break_drag_adds_manual_break(ledger, qapp):
    grid = ledger.spreadsheet_view.grid
    for r in range(200):
        grid.model.set_cell_value(r, 0, r)
    grid.set_view_mode("page_break")
    qapp.processEvents()
    rows, _cols = grid.page_break_bounds()
    assert len(rows) >= 3  # at least two pages
    first_break = rows[1]
    grid._page_break_drag = {"axis": "row", "index": first_break, "target": first_break - 5}
    assert grid.finish_page_break_drag() is True
    assert first_break - 5 in grid.model.view_state.row_breaks
    rows2, _ = grid.page_break_bounds()
    assert rows2[1] == first_break - 5


# ============================================================================ Lectern


def test_lectern_reveal_clip_progress():
    from atboffice.modules.presentation.slideshow.transitions import reveal_clip

    assert reveal_clip("wipe", "l", 1.0, 100, 50) is None
    assert reveal_clip("wipe", "l", 0.0, 100, 50).isEmpty()
    half = reveal_clip("wipe", "l", 0.5, 100, 50).boundingRect()
    assert 0 < half.width() * half.height() < 100 * 50
    for kind in ("blinds", "box", "split", "wheel", "circle", "diamond", "checkerboard"):
        clip = reveal_clip(kind, None, 0.5, 100, 50)
        assert clip is None or not clip.isEmpty()


def _presentation() -> Presentation:
    pres = Presentation()
    pres.slides = [Slide(id="s1"), Slide(id="s2", transition=Transition(type="fade"))]
    return pres


def test_lectern_live_transition_preview_plays_and_stops(qapp):
    from atboffice.modules.presentation.views.live_preview import preview_overlay

    pres = _presentation()
    view = QGraphicsView(QGraphicsScene(0, 0, pres.w, pres.h))
    view.resize(500, 320)
    view.show()
    qapp.processEvents()
    overlay = preview_overlay(view)
    assert preview_overlay(view) is overlay
    duration = overlay.play_transition(pres, pres.slides[1], pres.slides[0])
    assert duration > 0 and overlay.is_playing() and overlay.isVisible()
    frame = overlay.render_at(duration // 2)
    assert isinstance(frame, QImage) and not frame.isNull()
    finished = []
    overlay.finished.connect(lambda: finished.append(True))
    overlay.stop()
    assert finished and not overlay.is_playing() and not overlay.isVisible()
    # No builds on the slide: nothing to play
    assert overlay.play_animations(pres, pres.slides[0]) == 0
    view.close()


class _FakeShow(QWidget):
    slideChanged = Signal(int)
    showEnded = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.current_slide_index = 0

    def next_slide(self) -> None:
        self.current_slide_index += 1
        self.slideChanged.emit(self.current_slide_index)


def test_lectern_rehearsal_records_and_saves_timings(qapp):
    from atboffice.modules.presentation.slideshow.rehearsal import attach_rehearsal, fmt

    pres = _presentation()
    show = _FakeShow()
    rec = attach_rehearsal(show, pres, ask_keep=lambda _ms: True)
    assert rec.hud.isVisible() or show.isHidden()
    QTest.qWait(30)
    rec.set_paused(True)
    paused_at = rec.slide_elapsed()
    QTest.qWait(30)
    assert rec.slide_elapsed() == paused_at
    rec.set_paused(False)
    show.next_slide()
    QTest.qWait(20)
    saved = []
    rec.timings_saved.connect(saved.append)
    show.showEnded.emit()
    assert set(saved[0]) == {0, 1}
    assert pres.slides[0].transition.after is not None
    assert pres.slides[1].transition.after is not None
    assert rec.finish() == {}  # already finished
    assert fmt(3_725_000) == "1:02:05"


def test_lectern_rehearsal_discarded_keeps_old_timings(qapp):
    from atboffice.modules.presentation.slideshow.rehearsal import attach_rehearsal

    pres = _presentation()
    pres.slides[0].transition.after = 9.0
    show = _FakeShow()
    rec = attach_rehearsal(show, pres, ask_keep=lambda _ms: False)
    assert rec.finish() == {}
    assert pres.slides[0].transition.after == 9.0


def test_lectern_media_playback_without_media_reports_clean_fallback(qapp):
    from atboffice.modules.presentation.views.media_playback import MediaPlayback, fmt_ms

    class _Item:
        media_bytes = b""
        media_path = ""
        extension = "mp3"

    owner = QObject()
    pb = MediaPlayback(_Item(), lambda: None, owner)
    assert pb.play() is False
    assert pb.error in ("no-media", "unavailable")
    assert pb.position() == 0 and pb.duration() == 0 and pb.fraction() == 0.0
    pb.release()
    assert fmt_ms(75_000) == "01:15"


def test_quire_delete_key_removes_selected_float(quire):
    canvas = quire.writer_view.canvas_view
    doc = Document()
    pic = PictureItem(width=60, height=60, float_pr=FloatProperties(
        pos_h=PositionH(rel="page", offset=200), pos_v=PositionV(rel="page", offset=300)))
    doc.main.blocks = [Paragraph(runs=[TextItem("Text"), pic])]
    canvas.set_document(doc)
    QTest.mouseClick(canvas.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, _vp(canvas, 0, 230, 330))
    assert canvas.selected_float() is pic
    QTest.keyClick(canvas, Qt.Key.Key_Delete)
    assert canvas.selected_float() is None
    assert [r for r in canvas.doc.main.blocks[0].runs if isinstance(r, PictureItem)] == []
    assert not canvas.pagination.pages[0].float_boxes
    canvas.undo()
    assert any(isinstance(r, PictureItem) for r in canvas.doc.main.blocks[0].runs)
