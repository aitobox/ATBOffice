"""Comprehensive GUI unit tests for Quire view modes, outline view, and navigation panes."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    TextItem,
    plain_text,
    reindex,
)
from atboffice.modules.writer.view import WriterView
from atboffice.modules.writer.views import (
    CloseFullScreenBar,
    DocumentMapPane,
    OutlineToolbar,
    OutlineViewWidget,
    QuireNavDock,
    ReadingLayoutToolbar,
    ThumbnailsPane,
    ViewMode,
    demote_paragraph,
    demote_to_body_text,
    heading_level,
    move_paragraph,
    promote_paragraph,
    promote_to_heading_1,
)
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture
def sample_document() -> Document:
    """Create a sample document with headings and body paragraphs."""
    doc = Document()
    doc.main.blocks.clear()

    # Heading 1
    h1 = Paragraph()
    h1.p_pr.style = "Heading1"
    h1.runs.append(TextItem("Chapter 1: Introduction"))
    doc.main.blocks.append(h1)

    # Body 1
    p1 = Paragraph()
    p1.p_pr.style = "Normal"
    p1.runs.append(TextItem("This is the introductory text of the document."))
    doc.main.blocks.append(p1)

    # Heading 2
    h2 = Paragraph()
    h2.p_pr.style = "Heading2"
    h2.runs.append(TextItem("Section 1.1: Background"))
    doc.main.blocks.append(h2)

    # Body 2
    p2 = Paragraph()
    p2.p_pr.style = "Normal"
    p2.runs.append(TextItem("Background details and specifications."))
    doc.main.blocks.append(p2)

    reindex(doc)
    return doc


class TestViewModes:
    def test_view_mode_switching(self, qapp: QApplication, sample_document: Document) -> None:
        view = WriterView(doc=sample_document)
        view.resize(900, 700)
        view.show()

        # Default is PRINT
        assert view.view_mode == ViewMode.PRINT
        assert view.tab_selector.isVisible()
        assert view.h_ruler.isVisible()
        assert view.v_ruler.isVisible()
        assert not view.outline_toolbar.isVisible()
        assert not view.reading_toolbar.isVisible()
        assert view.center_stack.currentIndex() == 0

        # Switch to NORMAL view
        view.set_view_mode(ViewMode.NORMAL)
        assert view.view_mode == ViewMode.NORMAL
        assert not view.v_ruler.isVisible()
        assert view.h_ruler.isVisible()
        assert not view.tab_selector.isVisible()
        assert not view.outline_toolbar.isVisible()
        assert not view.reading_toolbar.isVisible()
        assert view.canvas_view.view_mode == ViewMode.NORMAL

        # Switch to WEB view
        view.set_view_mode(ViewMode.WEB)
        assert view.view_mode == ViewMode.WEB
        assert not view.v_ruler.isVisible()
        assert view.h_ruler.isVisible()
        assert view.canvas_view.view_mode == ViewMode.WEB

        # Switch to READING view
        view.set_view_mode(ViewMode.READING)
        assert view.view_mode == ViewMode.READING
        assert not view.v_ruler.isVisible()
        assert not view.h_ruler.isVisible()
        assert view.reading_toolbar.isVisible()
        assert not view.outline_toolbar.isVisible()
        assert view.canvas_view.view_mode == ViewMode.READING

        # Switch to OUTLINE view
        view.set_view_mode(ViewMode.OUTLINE)
        assert view.view_mode == ViewMode.OUTLINE
        assert not view.v_ruler.isVisible()
        assert not view.h_ruler.isVisible()
        assert view.outline_toolbar.isVisible()
        assert not view.reading_toolbar.isVisible()
        assert view.center_stack.currentIndex() == 1

        # Switch back to PRINT view
        view.set_view_mode(ViewMode.PRINT)
        assert view.view_mode == ViewMode.PRINT
        assert view.tab_selector.isVisible()
        assert view.h_ruler.isVisible()
        assert view.v_ruler.isVisible()
        assert view.center_stack.currentIndex() == 0

        # Verify document integrity preserved
        assert len(view.canvas_view.doc.main.blocks) == 4
        assert "Chapter 1" in plain_text(view.canvas_view.doc.main.blocks[0])


class TestOutlineLogic:
    def test_heading_level_detection(self, sample_document: Document) -> None:
        blocks = sample_document.main.blocks
        assert heading_level(sample_document, blocks[0]) == 1
        assert heading_level(sample_document, blocks[1]) == 0
        assert heading_level(sample_document, blocks[2]) == 2
        assert heading_level(sample_document, blocks[3]) == 0

    def test_promote_and_demote(self, sample_document: Document) -> None:
        blocks = sample_document.main.blocks
        h2 = blocks[2]

        # Promote Heading 2 -> Heading 1
        new_lvl = promote_paragraph(sample_document, h2)
        assert new_lvl == 1
        assert h2.p_pr.style == "Heading1"
        assert heading_level(sample_document, h2) == 1

        # Demote Heading 1 -> Heading 2
        new_lvl = demote_paragraph(sample_document, h2)
        assert new_lvl == 2
        assert h2.p_pr.style == "Heading2"
        assert heading_level(sample_document, h2) == 2

        # Demote to body text
        demote_to_body_text(sample_document, h2)
        assert heading_level(sample_document, h2) == 0

        # Promote to Heading 1 directly
        promote_to_heading_1(sample_document, h2)
        assert heading_level(sample_document, h2) == 1

    def test_move_paragraph_up_and_down(self, sample_document: Document) -> None:
        doc = sample_document
        blocks = doc.main.blocks
        h2 = blocks[2]
        p2 = blocks[3]

        # Move Section 1.1 UP (swaps with p1)
        ok = move_paragraph(doc, h2, -1)
        assert ok
        assert doc.main.blocks[1] == h2
        assert doc.main.blocks[2].runs[0].text.startswith("This is the introductory")

        # Move Section 1.1 DOWN back to original position
        ok = move_paragraph(doc, h2, 1)
        assert ok
        assert doc.main.blocks[2] == h2
        assert doc.main.blocks[3] == p2

    def test_outline_widget_and_toolbar(
        self, qapp: QApplication, sample_document: Document
    ) -> None:
        widget = OutlineViewWidget(doc=sample_document)
        widget.resize(600, 400)
        widget.show()

        # Check initial state
        assert len(widget.collapsed_ids) == 0
        h1 = sample_document.main.blocks[0]

        # Collapse h1
        widget.toggle_collapse(h1)
        assert h1.id in widget.collapsed_ids

        # Expand h1
        widget.toggle_collapse(h1)
        assert h1.id not in widget.collapsed_ids

        # Toolbar
        tb = OutlineToolbar()
        tb.set_current_level(1)
        assert tb._combo_outline_level.currentIndex() == 1

        tb.retranslate_ui()
        assert "大纲工具栏" in tb.windowTitle()


class TestNavigationPanes:
    def test_document_map_pane(self, qapp: QApplication, sample_document: Document) -> None:
        pane = DocumentMapPane(doc=sample_document)
        pane.resize(250, 400)

        # Has 2 headings (Chapter 1 and Section 1.1)
        assert pane.tree.topLevelItemCount() == 1  # Chapter 1 is top-level
        ch1_item = pane.tree.topLevelItem(0)
        assert "Chapter 1" in ch1_item.text(0)
        assert ch1_item.childCount() == 1
        assert "Section 1.1" in ch1_item.child(0).text(0)

        # Caret sync
        pane.sync_caret_para(sample_document.main.blocks[2])
        assert pane.tree.currentItem() == ch1_item.child(0)

        # Empty document placeholder
        empty_doc = Document()
        empty_doc.main.blocks.clear()
        reindex(empty_doc)
        pane.set_document(empty_doc)
        assert pane.tree.topLevelItemCount() == 1
        assert "(无标题)" in pane.tree.topLevelItem(0).text(0)

    def test_thumbnails_pane(self, qapp: QApplication, sample_document: Document) -> None:
        view = WriterView(doc=sample_document)
        pane = ThumbnailsPane(doc=sample_document, canvas_view=view.canvas_view)
        pane.resize(250, 400)

        assert pane.list_widget.count() >= 1
        first_item = pane.list_widget.item(0)
        assert first_item.text() == "1"
        assert not first_item.icon().isNull()

        # Selection
        pane.set_current_page(0)
        assert pane.list_widget.currentRow() == 0

    def test_quire_nav_dock(self, qapp: QApplication, sample_document: Document) -> None:
        dock = QuireNavDock(doc=sample_document)
        assert dock.active_mode() == "doc_map"

        # Switch to thumbnails
        dock.show_thumbnails()
        assert dock.active_mode() == "thumbnails"
        assert dock.stack.currentIndex() == 1

        # Switch to document map
        dock.show_document_map()
        assert dock.active_mode() == "doc_map"
        assert dock.stack.currentIndex() == 0

        dock.retranslate_ui()
        assert "导航" in dock.windowTitle()


class TestQuireWindowViewsIntegration:
    def test_window_view_actions_and_dock(
        self, qapp: QApplication, sample_document: Document
    ) -> None:
        win = QuireWindow()
        win.writer_view.canvas_view.set_document(sample_document)
        win.show()

        # 1. Check navigation dock initialization
        assert hasattr(win, "nav_dock")
        assert not win.nav_dock.isVisible()

        win.toggle_document_map()
        assert win.nav_dock.isVisible()
        assert win.nav_dock.active_mode() == "doc_map"

        win.toggle_thumbnails()
        assert win.nav_dock.isVisible()
        assert win.nav_dock.active_mode() == "thumbnails"

        win.toggle_thumbnails()
        assert not win.nav_dock.isVisible()

        # 2. View modes via window
        win.switch_view_mode(ViewMode.NORMAL)
        assert win.writer_view.view_mode == ViewMode.NORMAL
        act_normal = win.action_registry.get_action("view_normal")
        if act_normal:
            assert act_normal.isChecked()

        win.switch_view_mode(ViewMode.OUTLINE)
        assert win.writer_view.view_mode == ViewMode.OUTLINE
        act_outline = win.action_registry.get_action("view_outline")
        if act_outline:
            assert act_outline.isChecked()

        win.switch_view_mode(ViewMode.READING)
        assert win.writer_view.view_mode == ViewMode.READING
        act_reading = win.action_registry.get_action("view_reading")
        if act_reading:
            assert act_reading.isChecked()

        win.switch_view_mode(ViewMode.PRINT)
        assert win.writer_view.view_mode == ViewMode.PRINT
        act_print = win.action_registry.get_action("view_print")
        if act_print:
            assert act_print.isChecked()

        # 3. Full screen toggle
        assert not win._is_fullscreen_mode
        win.toggle_fullscreen()
        assert win._is_fullscreen_mode
        assert win.fullscreen_bar.isVisible()

        # Exit full screen via Esc key event
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        )
        win.keyPressEvent(esc_event)
        assert not win._is_fullscreen_mode
        assert not win.fullscreen_bar.isVisible()

        win.close()

    def test_reading_toolbar_and_scroll_navigation(
        self, qapp: QApplication, sample_document: Document
    ) -> None:
        view = WriterView(doc=sample_document)
        view.resize(900, 700)
        view.show()

        view.set_view_mode(ViewMode.READING)
        initial_zoom = view.canvas_view.zoom

        # Grow font
        view.reading_toolbar._btn_grow.click()
        assert view.canvas_view.zoom > initial_zoom

        # Shrink font
        view.reading_toolbar._btn_shrink.click()
        assert view.canvas_view.zoom <= initial_zoom + 0.05

        # Close reading layout returns to PRINT
        view.reading_toolbar._btn_close.click()
        assert view.view_mode == ViewMode.PRINT

        # Scroll to paragraph
        h2 = sample_document.main.blocks[2]
        ok = view.scroll_to_paragraph(h2.id)
        assert ok
        assert view.canvas_view.controller.pos.para_id == h2.id

        # Scroll to page
        view.scroll_to_page(0)

    def test_retranslate_ui_coverage(self, qapp: QApplication, sample_document: Document) -> None:
        view = WriterView(doc=sample_document)
        view.retranslate_ui()

        tb_outline = OutlineToolbar()
        tb_outline.retranslate_ui()
        assert "大纲工具栏" in tb_outline.windowTitle()

        tb_read = ReadingLayoutToolbar()
        tb_read.retranslate_ui()
        assert "阅读版式工具栏" in tb_read.windowTitle()

        fs_bar = CloseFullScreenBar()
        fs_bar.retranslate_ui()
        assert "全屏" in fs_bar.windowTitle()

        dock = QuireNavDock(doc=sample_document)
        dock.retranslate_ui()
        assert "导航" in dock.windowTitle()
