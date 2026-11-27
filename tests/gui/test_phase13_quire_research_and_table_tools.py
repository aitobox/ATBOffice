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
