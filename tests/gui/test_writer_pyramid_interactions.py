"""Tier 2 Regression Suite: PySide6 GUI & Canvas Viewport Interactions for Quire.

Covers:
1. Multi-page document navigation with CaretController (Arrow, Home/End, DocStart/End).
2. Mouse canvas interactions: click positioning, drag selection, double/triple click.
3. Interactive text editing: typing, Backspace deletion, paragraph split and merge.
4. Interactive Horizontal/Vertical Ruler: indents, tab stops, margin updates.
5. Zooming, viewport scaling clamping (50% ~ 400%), and accessibility / i18n.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    all_paragraphs,
    plen,
    ptext,
    reindex,
)
from atboffice.modules.writer.models.properties import SectionProperties
from atboffice.modules.writer.view import WriterView
from atboffice.modules.writer.views.caret_controller import DocPos


@pytest.fixture
def multi_page_view(qtbot: pytest.FixtureRequest, qapp: QApplication) -> WriterView:
    """Create a WriterView with a multi-page document."""
    doc = Document()
    doc.sect = SectionProperties(
        pg_w=400.0,
        pg_h=300.0,
        mt=30.0,
        mb=30.0,
        ml=40.0,
        mr=40.0,
    )
    # 8 paragraphs with multiple lines each to yield 3+ pages
    paras = []
    for i in range(8):
        p = Paragraph()
        p.runs.append(
            TextItem(
                f"Paragraph {i}: The quick brown fox jumps over the lazy dog "
                "repeatedly on multiple lines.\n"
                f"Second sentence of paragraph {i} to consume page height."
            )
        )
        paras.append(p)
    doc.main.blocks = paras
    reindex(doc)

    view = WriterView(doc=doc)
    qtbot.addWidget(view)
    view.resize(900, 700)
    view.show()
    return view


class TestPyramidMultiPageNavigation:
    """Validate cross-page caret movement and bounds handling."""

    def test_multi_page_vertical_navigation(self, multi_page_view: WriterView) -> None:
        canvas = multi_page_view.canvas_view
        ctrl = canvas.controller

        assert canvas.pagination.total_pages >= 2

        # Start at document beginning
        ctrl.move_doc_start()
        start_pos = ctrl.pos
        assert start_pos.offset == 0

        # Move down repeatedly across multiple lines and page boundary
        for _ in range(12):
            ctrl.move_down()

        assert ctrl.pos.offset > 0 or ctrl.pos.para_id != start_pos.para_id
        assert ctrl.preferred_x is not None

        # Jump to document end
        ctrl.move_doc_end()
        paras = all_paragraphs(canvas.doc)
        last_para = paras[-1]
        assert ctrl.pos.para_id == last_para.id
        assert ctrl.pos.offset == plen(last_para)

    def test_horizontal_line_boundary_navigation(self, multi_page_view: WriterView) -> None:
        canvas = multi_page_view.canvas_view
        ctrl = canvas.controller

        p0 = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p0.id, 5))

        # Home moves to line start
        ctrl.move_line_start()
        assert ctrl.pos.offset == 0

        # End moves to line/paragraph end
        ctrl.move_line_end()
        assert ctrl.pos.offset > 0

        # Moving left and right step by step
        cur_offset = ctrl.pos.offset
        ctrl.move_left()
        assert ctrl.pos.offset == cur_offset - 1
        ctrl.move_right()
        assert ctrl.pos.offset == cur_offset


class TestPyramidMouseInteractions:
    """Validate mouse clicking, drag selection, and multi-click word/paragraph selections."""

    def test_mouse_drag_rubberband_selection(self, multi_page_view: WriterView) -> None:
        canvas = multi_page_view.canvas_view
        ctrl = canvas.controller
        p0 = all_paragraphs(canvas.doc)[0]

        # Convert offsets 0 and 20 into viewport pixel coordinates
        p_idx0, pt0_doc, _ = ctrl.pos_to_canvas(DocPos(p0.id, 0))
        p_idx20, pt20_doc, _ = ctrl.pos_to_canvas(DocPos(p0.id, 20))

        page_rect = canvas.page_rect_canvas(p_idx0)
        scroll_x = canvas.horizontalScrollBar().value()
        scroll_y = canvas.verticalScrollBar().value()

        vp_x0 = page_rect.left() - scroll_x + canvas.pt_to_px(pt0_doc.x()) + 2.0
        vp_y0 = page_rect.top() - scroll_y + canvas.pt_to_px(pt0_doc.y()) + 4.0

        vp_x20 = page_rect.left() - scroll_x + canvas.pt_to_px(pt20_doc.x()) + 2.0
        vp_y20 = page_rect.top() - scroll_y + canvas.pt_to_px(pt20_doc.y()) + 4.0

        p1 = QPoint(int(vp_x0), int(vp_y0))
        p2 = QPoint(int(vp_x20), int(vp_y20))

        # 1. Mouse press at start of text
        press_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            p1,
            p1,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        canvas.mousePressEvent(press_ev)

        assert ctrl.pos.para_id == p0.id

        # 2. Mouse drag move to offset 20
        move_ev = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            p2,
            p2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        canvas.mouseMoveEvent(move_ev)

        assert not ctrl.selection.is_collapsed

        # 3. Mouse release
        release_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            p2,
            p2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        canvas.mouseReleaseEvent(release_ev)

        sel = ctrl.selection
        assert not sel.is_collapsed
        assert sel.anchor.para_id == p0.id
        assert sel.focus.para_id == p0.id
        assert abs(sel.focus.offset - sel.anchor.offset) > 0

    def test_double_and_triple_click_selections(self, multi_page_view: WriterView) -> None:
        canvas = multi_page_view.canvas_view
        ctrl = canvas.controller
        p0 = all_paragraphs(canvas.doc)[0]

        # Word selection
        ctrl.select_word_at(DocPos(p0.id, 12))
        assert not ctrl.selection.is_collapsed
        assert ctrl.selection.anchor.para_id == p0.id
        assert ctrl.selection.focus.para_id == p0.id

        # Paragraph selection
        ctrl.select_paragraph_at(DocPos(p0.id, 5))
        assert not ctrl.selection.is_collapsed
        assert ctrl.selection.anchor.offset == 0
        assert ctrl.selection.focus.offset == plen(p0)

        # Select all
        ctrl.select_all()
        assert not ctrl.selection.is_collapsed
        assert ctrl.selection.anchor.offset == 0


class TestPyramidEditingInteractions:
    """Validate typing, deletion, paragraph split, and merge."""

    def test_typing_and_backspace_editing(self, multi_page_view: WriterView) -> None:
        canvas = multi_page_view.canvas_view
        ctrl = canvas.controller
        p0 = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p0.id, 0))

        # Insert prefix text
        ctrl.insert_text("★ Prefix: ")
        updated_p0 = all_paragraphs(canvas.doc)[0]
        assert ptext(updated_p0).startswith("★ Prefix: ")

        # Backspace delete character by character
        ctrl.delete_backspace()
        assert not ptext(all_paragraphs(canvas.doc)[0]).startswith("★ Prefix: ")

    def test_paragraph_enter_split_and_backspace_merge(self, multi_page_view: WriterView) -> None:
        canvas = multi_page_view.canvas_view
        ctrl = canvas.controller
        initial_para_count = len(all_paragraphs(canvas.doc))

        p0 = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p0.id, 10))

        # Split paragraph with Enter
        ctrl.insert_paragraph_break()
        paras = all_paragraphs(canvas.doc)
        assert len(paras) == initial_para_count + 1

        # Backspace at start of newly split paragraph merges them back
        assert ctrl.pos.offset == 0
        ctrl.delete_backspace()
        paras_after = all_paragraphs(canvas.doc)
        assert len(paras_after) == initial_para_count


class TestPyramidRulerAndMarginInteractions:
    """Validate horizontal ruler indents, tab stops, and vertical ruler margin dragging."""

    def test_horizontal_ruler_indents(self, multi_page_view: WriterView) -> None:
        h_ruler = multi_page_view.h_ruler
        canvas = multi_page_view.canvas_view
        p0 = all_paragraphs(canvas.doc)[0]

        rects = h_ruler._get_marker_rects()
        assert "first" in rects
        first_pt = rects["first"].center()

        # Drag first line indent marker
        press_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            first_pt,
            first_pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        h_ruler.mousePressEvent(press_ev)
        assert h_ruler._drag_kind == "first"

        # Move 36 pt to the right
        move_pt = QPointF(first_pt.x() + 48.0, first_pt.y())
        move_ev = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            move_pt,
            move_pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        h_ruler.mouseMoveEvent(move_ev)

        release_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            move_pt,
            move_pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        h_ruler.mouseReleaseEvent(release_ev)

        assert abs(p0.p_pr.ind.first_line - 36.0) < 2.0

    def test_horizontal_ruler_tab_stops(self, multi_page_view: WriterView) -> None:
        h_ruler = multi_page_view.h_ruler
        canvas = multi_page_view.canvas_view
        p0 = all_paragraphs(canvas.doc)[0]

        # Click ruler body to add a tab stop at text left + 100 px
        text_l = h_ruler.text_left_ruler()
        click_pt = QPointF(text_l + 100.0, 12.0)

        press_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            click_pt,
            click_pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        h_ruler.mousePressEvent(press_ev)
        assert h_ruler._drag_kind == "new_tab"

        release_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            click_pt,
            click_pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        h_ruler.mouseReleaseEvent(release_ev)
        assert len(p0.p_pr.tabs) >= 1

    def test_vertical_ruler_margins(self, multi_page_view: WriterView) -> None:
        v_ruler = multi_page_view.v_ruler
        canvas = multi_page_view.canvas_view

        text_t = v_ruler.text_top_ruler()
        press_pt = QPointF(12.0, text_t)

        press_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            press_pt,
            press_pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        v_ruler.mousePressEvent(press_ev)
        assert v_ruler._drag_kind == "top"

        # Drag top margin down by 24 px (18 pt)
        move_pt = QPointF(12.0, text_t + 24.0)
        move_ev = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            move_pt,
            move_pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        v_ruler.mouseMoveEvent(move_ev)

        release_ev = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            move_pt,
            move_pt,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        v_ruler.mouseReleaseEvent(release_ev)

        assert canvas.doc.sect.mt > 30.0


class TestPyramidZoomAndAccessibility:
    """Validate zoom clamping and i18n accessibility retranslation."""

    def test_zoom_levels_and_clamping(self, multi_page_view: WriterView) -> None:
        canvas = multi_page_view.canvas_view

        canvas.set_zoom(1.5)
        assert canvas.zoom == pytest.approx(1.5)

        # Min clamp (0.5)
        canvas.set_zoom(0.1)
        assert canvas.zoom == pytest.approx(0.5)

        # Max clamp (4.0)
        canvas.set_zoom(10.0)
        assert canvas.zoom == pytest.approx(4.0)

    def test_retranslate_ui_accessibility(self, multi_page_view: WriterView) -> None:
        multi_page_view.retranslate_ui()
        assert multi_page_view.canvas_view.toolTip() != ""
        assert multi_page_view.h_ruler.toolTip() != ""
        assert multi_page_view.v_ruler.toolTip() != ""
