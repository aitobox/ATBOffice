"""GUI tests for Quire WriterCanvasView and CaretController."""

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent
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
from atboffice.modules.writer.views.canvas_view import WriterCanvasView
from atboffice.modules.writer.views.caret_controller import (
    DocPos,
    Selection,
)


@pytest.fixture
def canvas(qapp: QApplication) -> WriterCanvasView:
    doc = Document()
    doc.main.blocks.clear()
    p1 = Paragraph()
    p1.runs.append(TextItem("The quick brown fox jumps over the lazy dog."))
    doc.main.blocks.append(p1)
    reindex(doc)

    view = WriterCanvasView(doc=doc)
    view.resize(900, 700)
    return view


class TestCanvasInitialization:
    def test_init_and_retranslate(self, canvas: WriterCanvasView) -> None:
        assert canvas.doc is not None
        assert canvas.pagination is not None
        assert canvas.controller is not None
        assert canvas.zoom == 1.0

        canvas.retranslate_ui()
        assert canvas.toolTip() == "页面编辑画布 (Word 2003 视图)"
        assert "Word 2003" in canvas.viewport().accessibleDescription()

    def test_default_page_geometry(self, canvas: WriterCanvasView) -> None:
        rect = canvas.page_rect_canvas(0)
        assert rect.width() > 0
        assert rect.height() > 0
        assert rect.left() >= 0


class TestZoomAndScaling:
    def test_zoom_in_and_out(self, canvas: WriterCanvasView) -> None:
        initial_zoom = canvas.zoom
        canvas.zoom_in()
        assert canvas.zoom > initial_zoom

        canvas.zoom_out()
        assert canvas.zoom == initial_zoom

    def test_zoom_clamping(self, canvas: WriterCanvasView) -> None:
        canvas.set_zoom(0.1)
        assert canvas.zoom == 0.5  # Clamped to min 50%

        canvas.set_zoom(10.0)
        assert canvas.zoom == 4.0  # Clamped to max 400%

    def test_coordinate_roundtrip(self, canvas: WriterCanvasView) -> None:
        pt = 72.0
        px = canvas.pt_to_px(pt)
        recovered_pt = canvas.px_to_pt(px)
        assert abs(recovered_pt - pt) < 1e-4


class TestCaretCoordinateMappingAndHitTesting:
    def test_pos_to_canvas(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        page_idx, pt, h = ctrl.pos_to_canvas(DocPos(p.id, 0))

        assert page_idx == 0
        assert pt.x() >= 70.0  # Near left margin
        assert pt.y() >= 60.0  # Near top margin
        assert h >= 12.0

    def test_canvas_to_pos_binary_search(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]

        # Get canvas coordinate of character 10
        _, pt10, _ = ctrl.pos_to_canvas(DocPos(p.id, 10))
        # Hit test slightly near pt10
        detected_pos = ctrl.canvas_to_pos(0, QPointF(pt10.x(), pt10.y() + 5.0))
        assert detected_pos.para_id == p.id
        assert detected_pos.offset == 10

    def test_click_outside_margins_snaps(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]

        # Click far to the left of the page (x = 5pt)
        pos_left = ctrl.canvas_to_pos(0, QPointF(5.0, 100.0))
        assert pos_left.para_id == p.id
        assert pos_left.offset == 0

        # Click far to the right of the page (x = 550pt)
        pos_right = ctrl.canvas_to_pos(0, QPointF(550.0, 100.0))
        assert pos_right.para_id == p.id
        assert pos_right.offset == plen(p)


class TestCaretNavigation:
    def test_arrow_left_right(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p.id, 0))

        ctrl.move_right()
        assert ctrl.pos.offset == 1

        ctrl.move_right(extend=True)
        assert ctrl.pos.offset == 2
        assert not ctrl.selection.is_collapsed
        assert ctrl.selection.anchor.offset == 1
        assert ctrl.selection.focus.offset == 2

        ctrl.move_left()
        assert ctrl.pos.offset == 1
        assert ctrl.selection.is_collapsed

    def test_home_and_end(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p.id, 5))

        ctrl.move_line_start()
        assert ctrl.pos.offset == 0

        ctrl.move_line_end()
        assert ctrl.pos.offset == plen(p)

    def test_move_doc_start_and_end(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        ctrl.move_doc_end()
        assert ctrl.pos.offset == plen(all_paragraphs(canvas.doc)[-1])

        ctrl.move_doc_start()
        assert ctrl.pos.offset == 0

    def test_up_down_preferred_x(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        ctrl.move_down()
        assert ctrl.preferred_x is not None


class TestSelectionModes:
    def test_word_selection(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        # "The quick brown..." 'quick' starts at 4, ends at 9
        ctrl.select_word_at(DocPos(p.id, 6))

        assert not ctrl.selection.is_collapsed
        assert ctrl.selection.anchor.offset == 4
        assert ctrl.selection.focus.offset == 9

    def test_paragraph_selection(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        ctrl.select_paragraph_at(DocPos(p.id, 10))

        assert not ctrl.selection.is_collapsed
        assert ctrl.selection.anchor.offset == 0
        assert ctrl.selection.focus.offset == plen(p)

    def test_select_all(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        ctrl.select_all()

        p = all_paragraphs(canvas.doc)[0]
        assert not ctrl.selection.is_collapsed
        assert ctrl.selection.anchor.offset == 0
        assert ctrl.selection.focus.offset == plen(p)


class TestEditingOperations:
    def test_typing_insertion(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p.id, 4))  # Before 'quick'

        ctrl.insert_text("super ")
        p_updated = all_paragraphs(canvas.doc)[0]
        assert "super quick" in ptext(p_updated)
        assert ctrl.pos.offset == 10

    def test_backspace_deletion(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p.id, 4))

        ctrl.delete_backspace()
        p_updated = all_paragraphs(canvas.doc)[0]
        assert ptext(p_updated).startswith("Thequick")
        assert ctrl.pos.offset == 3

    def test_paragraph_split_and_merge(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p.id, 4))

        # Split into two paragraphs with Enter
        ctrl.insert_paragraph_break()
        paras = all_paragraphs(canvas.doc)
        assert len(paras) == 2
        assert ptext(paras[0]) == "The "
        assert ptext(paras[1]).startswith("quick")
        assert ctrl.pos.para_id == paras[1].id
        assert ctrl.pos.offset == 0

        # Backspace at start of second paragraph merges them back
        ctrl.delete_backspace()
        paras_after = all_paragraphs(canvas.doc)
        assert len(paras_after) == 1
        assert ptext(paras_after[0]).startswith("The quick")
        assert ctrl.pos.para_id == paras_after[0].id
        assert ctrl.pos.offset == 4

    def test_delete_selection(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        ctrl.selection = Selection(DocPos(p.id, 0), DocPos(p.id, 4))
        ctrl.delete_selection()

        p_updated = all_paragraphs(canvas.doc)[0]
        assert ptext(p_updated).startswith("quick")
        assert ctrl.pos.offset == 0


class TestKeyboardShortcuts:
    def test_typing_key_event(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        p = all_paragraphs(canvas.doc)[0]
        ctrl.set_pos(DocPos(p.id, 0))

        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_X,
            Qt.KeyboardModifier.NoModifier,
            "X",
        )
        handled = ctrl.handle_key_event(event)
        assert handled is True
        assert ptext(all_paragraphs(canvas.doc)[0]).startswith("XThe")


class TestBlinkTimer:
    def test_reset_blink(self, canvas: WriterCanvasView) -> None:
        ctrl = canvas.controller
        ctrl.caret_visible = False
        ctrl.reset_blink()
        assert ctrl.caret_visible is True


class TestTableInteraction:
    def test_canvas_with_table(self, canvas: WriterCanvasView) -> None:
        from atboffice.modules.writer.models.table import create_simple_table

        tbl = create_simple_table(rows=2, cols=2, width=300.0)
        canvas.doc.main.blocks.append(tbl)
        reindex(canvas.doc)
        canvas.set_document(canvas.doc)

        assert canvas.pagination.total_pages >= 1
        # Check that page 0 has table fragment
        frags = [
            frag
            for reg in canvas.pagination.pages[0].regions
            for col in reg.columns
            for frag in col.fragments
            if getattr(frag, "table_layout", None) is not None
        ]
        assert len(frags) == 1
        assert frags[0].table_layout.table is tbl

    def test_canvas_table_divider_hover_and_resize(self, canvas: WriterCanvasView) -> None:
        from PySide6.QtCore import QPoint

        from atboffice.modules.writer.models.table import create_simple_table

        canvas.doc.main.blocks.clear()
        tbl = create_simple_table(rows=2, cols=2, width=200.0)
        canvas.doc.main.blocks.append(tbl)
        reindex(canvas.doc)
        canvas.set_document(canvas.doc)

        tl = canvas.pagination.pages[0].regions[0].columns[0].fragments[0].table_layout
        col0_w = tl.grid[0]
        page_rect = canvas.page_rect_canvas(0)

        # Coordinate of column divider
        div_x = int(page_rect.left() + canvas.pt_to_px(canvas.doc.sect.ml + col0_w))
        div_y = int(page_rect.top() + canvas.pt_to_px(canvas.doc.sect.mt + 10.0))
        pt = QPoint(div_x, div_y)

        hit = canvas._hit_test_table_divider(pt)
        assert hit is not None
        assert hit["kind"] == "col"
        assert hit["index"] == 0

        # Simulate resize drag
        canvas._resizing_table = True
        canvas._resize_info = hit
        canvas._resize_guide_pos = pt

        # Simulate release 20px to the right
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QMouseEvent

        release_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(div_x + 20, div_y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        canvas.mouseReleaseEvent(release_event)

        assert canvas._resizing_table is False
        # Column 0 width should have expanded
        assert tbl.grid[0] > col0_w
