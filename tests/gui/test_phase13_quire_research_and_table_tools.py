"""Tests for Phase 13A Quire Research/Thesaurus pane and Interactive Table Pen & Eraser."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from atboffice.core.i18n import load_locale
from atboffice.modules.writer.models.document import Document, Paragraph, TextItem, ptext, reindex
from atboffice.modules.writer.views.caret_controller import DocPos
from atboffice.ui.shell.quire_window import QuireWindow


def test_quire_research_pane_thesaurus_insert_undo_and_doc_search(qapp: QApplication) -> None:
    """Triggering thesaurus/research looks up caret word, replaces undoably, and searches doc."""
    win = QuireWindow()
    try:
        win.resize(1200, 800)
        win.show()
        canvas = win.writer_view.canvas_view
        p1 = Paragraph(runs=[TextItem(text="A happy traveler walked happily.")])
        p2 = Paragraph(runs=[TextItem(text="Another traveler arrived later.")])
        canvas.doc = Document()
        canvas.doc.main.blocks = [p1, p2]
        reindex(canvas.doc)
        canvas.controller.doc = canvas.doc
        canvas.refresh_layout()

        # Position caret inside "happy" and trigger thesaurus (Shift+F7 / action)
        canvas.controller.set_pos(DocPos(p1.id, 4))
        act_thes = win.action_registry.get_action("thesaurus")
        act_res = win.action_registry.get_action("research")
        assert act_thes is not None and act_thes.isEnabled() is True
        assert act_res is not None and act_res.isEnabled() is True
        assert act_thes.shortcut().toString() == "Shift+F7"

        act_thes.trigger()
        qapp.processEvents()

        pane = win.research_pane
        assert win.task_pane_dock.isVisible() is True
        assert win.task_pane_dock.current_pane_id() == "research"
        assert pane.query_edit.text() == "happy"

        # Candidate synonym buttons should be rendered
        word_buttons = [
            b
            for b in pane.results_widget.findChildren(QToolButton)
            if isinstance(b.property("_thes_word"), str)
        ]
        assert len(word_buttons) >= 3
        chosen = next(
            b.property("_thes_word")
            for b in word_buttons
            if b.property("_thes_word").lower() != "happy"
        )

        # Undoable replace of "happy" under caret -> undo restores "happy"
        assert pane.insert_word(chosen) is True
        assert chosen in ptext(canvas.doc.main.blocks[0])
        assert "happy" not in ptext(canvas.doc.main.blocks[0])

        assert canvas.history.undo() is True
        canvas.refresh_layout()
        assert "A happy traveler" in ptext(canvas.doc.main.blocks[0])

        # Follow-up lookup + Go Back history
        pane.search("traveler")
        assert pane.btn_back.isEnabled() is True
        pane.go_back()
        assert pane.query_edit.text() == "happy"

        # Document search + click hit jumps selection across paragraphs
        pane.set_service("document")
        pane.search("traveler")
        hits = [
            b
            for b in pane.results_widget.findChildren(QToolButton)
            if "[traveler]" in b.text().lower()
        ]
        assert len(hits) == 2
        hits[1].click()
        assert canvas.controller.pos.para_id == p2.id
        assert canvas.controller.get_selected_text().lower() == "traveler"

        # Dynamic i18n retranslate
        load_locale("en")
        qapp.processEvents()
        assert pane.btn_go.text() == "Go"
        assert pane.btn_back.text() == "◄ Back"
    finally:
        load_locale("zh-CN")
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_quire_shift_f7_key_opens_research(qapp: QApplication) -> None:
    """Pressing Shift+F7 inside QuireWindow opens Research pane with thesaurus service."""
    win = QuireWindow()
    try:
        win.resize(1100, 760)
        win.show()
        canvas = win.writer_view.canvas_view
        p = Paragraph(runs=[TextItem(text="vivid clarity")])
        canvas.doc = Document()
        canvas.doc.main.blocks = [p]
        reindex(canvas.doc)
        canvas.controller.doc = canvas.doc
        canvas.refresh_layout()
        canvas.controller.set_pos(DocPos(p.id, 2))
        canvas.setFocus()
        qapp.processEvents()

        QTest.keyClick(win, Qt.Key.Key_F7, Qt.KeyboardModifier.ShiftModifier)
        qapp.processEvents()
        assert win.task_pane_dock.isVisible() is True
        assert win.task_pane_dock.current_pane_id() == "research"
        assert win.research_pane.query_edit.text() == "vivid"
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_split_cell_at_x_and_split_cell_rows_preserve_grid_and_roundtrip() -> None:
    """Pure model table splits conserve grid width/spans across rows and survive DOCX round-trip."""
    from atboffice.modules.writer.io.docx_reader import read_docx
    from atboffice.modules.writer.io.docx_writer import write_docx
    from atboffice.modules.writer.models.table import (
        create_simple_table,
        split_cell_at_x,
        split_cell_rows,
        table_map,
    )

    tbl = create_simple_table(2, 2, width=400.0)
    assert tbl.grid == [200.0, 200.0]

    # Vertical X split of row 0, cell 0 at x=80pt -> grid=[80, 120, 200], row 1 cell 0 spans 2
    right_cell = split_cell_at_x(tbl, 0, 0, 80.0)
    assert right_cell in tbl.rows[0].cells
    assert [round(w, 2) for w in tbl.grid] == [80.0, 120.0, 200.0]
    m1 = table_map(tbl)
    assert len(m1[0]) == 3
    assert sum(e.span for e in m1[0]) == 3
    assert sum(e.span for e in m1[1]) == 3
    assert m1[1][0].span == 2

    # Horizontal split of row 0, right column into 2 rows -> row count becomes 3
    created = split_cell_rows(tbl, tbl.rows[0].cells[-1], num_rows=2)
    assert len(created) == 2
    assert len(tbl.rows) == 3
    m2 = table_map(tbl)
    assert m2[0][0].rowspan == 2
    assert m2[1][0].is_hidden is True

    doc = Document()
    doc.main.blocks = [tbl, Paragraph(runs=[TextItem(text="after")])]
    reindex(doc)
    reopened = read_docx(write_docx(doc))
    rt_tbl = next(b for b in reopened.main.blocks if hasattr(b, "rows"))
    assert len(rt_tbl.rows) == 3
    assert len(rt_tbl.grid) == 3


def _doc_to_vp(canvas, page_idx: int, pt_doc):
    """Convert page-relative point coordinates into viewport pixel coordinates."""
    from PySide6.QtCore import QPointF

    rect = canvas.page_rect_canvas(page_idx)
    c_pt = QPointF(
        rect.left() + canvas.pt_to_px(pt_doc.x()),
        rect.top() + canvas.pt_to_px(pt_doc.y()),
    )
    return canvas.canvas_to_viewport(c_pt).toPoint()


def _first_table_cell_origin(canvas):
    """Return `(page_idx, page_origin_x_pt, page_origin_y_pt, table_layout)` for first table."""
    for p_idx, page in enumerate(canvas.pagination.pages):
        for reg in page.regions:
            for col in reg.columns:
                for frag in col.fragments:
                    if frag.table_layout is not None:
                        return (
                            p_idx,
                            page.body_left + col.left,
                            page.body_top + col.top + frag.top,
                            frag.table_layout,
                        )
    raise AssertionError("No TableLayout fragment found in pagination")


def test_canvas_draw_table_pen_eraser_escape_and_toolbar_sync(qapp: QApplication) -> None:
    """Interactive draw pen creates/splits tables undoably, eraser merges cells, Esc exits tool."""
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtTest import QTest

    win = QuireWindow()
    try:
        win.resize(1200, 820)
        win.show()
        canvas = win.writer_view.canvas_view
        p = Paragraph(runs=[TextItem(text="Canvas top paragraph")])
        canvas.doc = Document()
        canvas.doc.main.blocks = [p]
        reindex(canvas.doc)
        canvas.controller.doc = canvas.doc
        canvas.refresh_layout()
        qapp.processEvents()

        act_draw = win.action_registry.get_action("drawTable")
        act_erase = win.action_registry.get_action("eraser")
        assert act_draw is not None and act_erase is not None

        # 1. Activate draw tool via action -> checkable synced & tables toolbar shown in classic
        act_draw.trigger()
        qapp.processEvents()
        assert canvas.table_tool == "draw"
        assert act_draw.isChecked() is True
        assert act_erase.isChecked() is False
        assert win.toolbars["tables"].isVisible() is True

        # 2. Drag outside tables -> inserts undoable 1x1 table with dragged width/height
        page = canvas.pagination.pages[0]
        origin_px = _doc_to_vp(canvas, 0, QPointF(page.body_left + 10.0, page.body_top + 40.0))
        end_px = QPoint(origin_px.x() + 240, origin_px.y() + 80)
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=origin_px)
        QTest.mouseMove(canvas.viewport(), pos=end_px)
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=end_px)
        qapp.processEvents()

        tables = [b for b in canvas.doc.main.blocks if hasattr(b, "rows")]
        assert len(tables) == 1
        tbl = tables[0]
        assert len(tbl.rows) == 1 and len(tbl.grid) == 1
        assert tbl.grid[0] >= 100.0
        assert (tbl.rows[0].tr_pr.h or 0.0) >= 20.0

        # 3. Vertical drag inside the 1x1 cell -> splits into 2 columns cleanly
        p_idx, ox, oy, tl = _first_table_cell_origin(canvas)
        cell_vp_top = _doc_to_vp(
            canvas, p_idx, QPointF(ox + tl.x + tl.width * 0.45, oy + tl.y + 8.0)
        )
        cell_vp_bot = QPoint(cell_vp_top.x() + 2, cell_vp_top.y() + 45)
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=cell_vp_top)
        QTest.mouseMove(canvas.viewport(), pos=cell_vp_bot)
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=cell_vp_bot)
        qapp.processEvents()
        assert len(tables[0].rows[0].cells) == 2
        assert len(tables[0].grid) == 2

        # 4. Horizontal drag inside left cell -> splits row horizontally into 2 rows
        p_idx2, ox2, oy2, tl2 = _first_table_cell_origin(canvas)
        h_left = _doc_to_vp(canvas, p_idx2, QPointF(ox2 + tl2.x + 12.0, oy2 + tl2.y + 18.0))
        h_right = QPoint(h_left.x() + 60, h_left.y() + 2)
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=h_left)
        QTest.mouseMove(canvas.viewport(), pos=h_right)
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=h_right)
        qapp.processEvents()
        assert len(tables[0].rows) == 2

        # 5. Switch to eraser and click internal divider between the 2 top cells -> merges back to 1
        act_erase.trigger()
        qapp.processEvents()
        assert canvas.table_tool == "erase"
        assert act_erase.isChecked() is True
        assert act_draw.isChecked() is False

        p_idx3, ox3, oy3, tl3 = _first_table_cell_origin(canvas)
        divider_vp = _doc_to_vp(
            canvas,
            p_idx3,
            QPointF(ox3 + tl3.x + tl3.grid[0], oy3 + tl3.y + 10.0),
        )
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=divider_vp)
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=divider_vp)
        qapp.processEvents()
        assert len(tables[0].rows[0].cells) == 1

        # 6. Undo restores pre-merge state & Esc exits eraser tool
        assert canvas.history.undo() is True
        re_tables = [b for b in canvas.doc.main.blocks if hasattr(b, "rows")]
        assert len(re_tables[0].rows[0].cells) == 2

        canvas.setFocus()
        QTest.keyClick(canvas.viewport(), Qt.Key.Key_Escape)
        qapp.processEvents()
        assert canvas.table_tool is None
        assert act_erase.isChecked() is False
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()
