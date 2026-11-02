"""Main view for the Quire word-processing module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtWidgets import QGridLayout, QStackedWidget, QVBoxLayout, QWidget

from atboffice.modules.writer.models.document import Document, Paragraph, all_paragraphs
from atboffice.modules.writer.models.mailmerge import MailMergeEngine
from atboffice.modules.writer.views.canvas_view import WriterCanvasView
from atboffice.modules.writer.views.outline_view import OutlineToolbar, OutlineViewWidget
from atboffice.modules.writer.views.reading_toolbar import ReadingLayoutToolbar
from atboffice.modules.writer.views.review_pane import ReviewPane, ReviewToolbar
from atboffice.modules.writer.views.ruler import (
    HorizontalRuler,
    RulerUnit,
    TabSelectorWidget,
    VerticalRuler,
)
from atboffice.modules.writer.views.view_modes import ViewMode

if TYPE_CHECKING:
    from atboffice.modules.writer.dialogs.word_count_dlg import WordCountDialog


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("WriterView", text)


class WriterView(QWidget):
    """Word 2003 styled document editing viewport widget with interactive dual rulers."""

    view_mode_changed = Signal(object)

    def __init__(self, doc: Document | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_mode: ViewMode = ViewMode.PRINT

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 0. Specialized Top Toolbars
        self.reading_toolbar = ReadingLayoutToolbar(parent=self)
        self.reading_toolbar.setVisible(False)
        root_layout.addWidget(self.reading_toolbar)

        self.outline_toolbar = OutlineToolbar(parent=self)
        self.outline_toolbar.setVisible(False)
        root_layout.addWidget(self.outline_toolbar)

        # Grid container for rulers, canvas, and panes
        grid_container = QWidget(self)
        layout = QGridLayout(grid_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        root_layout.addWidget(grid_container, 1)

        # 1. Corner tab selector button
        self.tab_selector = TabSelectorWidget(parent=grid_container)
        layout.addWidget(self.tab_selector, 0, 0)

        # 2. Horizontal ruler
        self.h_ruler = HorizontalRuler(parent=grid_container)
        layout.addWidget(self.h_ruler, 0, 1)

        # 3. Vertical ruler
        self.v_ruler = VerticalRuler(parent=grid_container)
        layout.addWidget(self.v_ruler, 1, 0)

        # 4. Center Stack: Canvas View (0) and Outline View (1)
        self.center_stack = QStackedWidget(grid_container)
        self.canvas_view = WriterCanvasView(doc=doc, parent=self.center_stack)
        self.center_stack.addWidget(self.canvas_view)

        self.outline_widget = OutlineViewWidget(
            doc=self.canvas_view.doc,
            controller=self.canvas_view.controller,
            parent=self.center_stack,
        )
        self.center_stack.addWidget(self.outline_widget)
        layout.addWidget(self.center_stack, 1, 1)

        # 5. Collapsible Reviewing Pane on the right
        self.review_pane = ReviewPane(doc=self.canvas_view.doc, parent=grid_container)
        self.review_pane.setVisible(False)
        layout.addWidget(self.review_pane, 0, 2, 2, 1)

        # 6. Reviewing Toolbar (floating / dockable toolbar)
        self.review_toolbar = ReviewToolbar(parent=self)
        self.review_toolbar.setVisible(False)

        # 7. Mail Merge engine instance
        self.mailmerge_engine = MailMergeEngine()
        self.canvas_view.doc.mailmerge_engine = self.mailmerge_engine

        # Wire ruler interactions and canvas attachments
        self.tab_selector.tab_kind_changed.connect(self.h_ruler.set_tab_selector_kind)
        self.h_ruler.attach_canvas(self.canvas_view)
        self.v_ruler.attach_canvas(self.canvas_view)

        # Wire canvas scroll, zoom, and cursor movements to rulers
        self.canvas_view.horizontalScrollBar().valueChanged.connect(self.h_ruler.update_scroll)
        self.canvas_view.verticalScrollBar().valueChanged.connect(self.v_ruler.update_scroll)
        self.canvas_view.zoom_changed.connect(self._on_zoom_changed)
        self.canvas_view.caret_moved.connect(self._on_caret_moved)
        self.canvas_view.controller.document_modified.connect(self._on_document_modified)

        # Wire outline toolbar & widget
        self.outline_toolbar.promote_requested.connect(self.outline_widget.promote_selected)
        self.outline_toolbar.demote_requested.connect(self.outline_widget.demote_selected)
        self.outline_toolbar.promote_h1_requested.connect(self.outline_widget.promote_selected_h1)
        self.outline_toolbar.demote_body_requested.connect(self.outline_widget.demote_selected_body)
        self.outline_toolbar.move_up_requested.connect(self.outline_widget.move_selected_up)
        self.outline_toolbar.move_down_requested.connect(self.outline_widget.move_selected_down)
        self.outline_toolbar.expand_requested.connect(self.outline_widget.expand_selected)
        self.outline_toolbar.collapse_requested.connect(self.outline_widget.collapse_selected)
        self.outline_toolbar.show_level_changed.connect(self.outline_widget.set_show_level)
        self.outline_toolbar.first_line_toggled.connect(self.outline_widget.set_first_line_only)
        self.outline_toolbar.show_formatting_toggled.connect(
            self.outline_widget.set_show_formatting
        )
        self.outline_toolbar.close_requested.connect(lambda: self.set_view_mode(ViewMode.PRINT))
        self.outline_widget.structure_changed.connect(self._on_outline_structure_changed)

        # Wire reading toolbar
        self.reading_toolbar.grow_font_requested.connect(self.canvas_view.zoom_in)
        self.reading_toolbar.shrink_font_requested.connect(self.canvas_view.zoom_out)
        self.reading_toolbar.close_requested.connect(lambda: self.set_view_mode(ViewMode.PRINT))

        # Wire review components
        self.review_toolbar.review_pane_toggled.connect(self.set_review_pane_visible)
        self.review_toolbar.markup_filter_changed.connect(self.review_pane.set_markup_filter)
        self.review_toolbar.accept_change_requested.connect(self._on_accept_change)
        self.review_toolbar.accept_all_requested.connect(self._on_accept_all_changes)
        self.review_toolbar.reject_change_requested.connect(self._on_reject_change)
        self.review_toolbar.reject_all_requested.connect(self._on_reject_all_changes)
        self.review_toolbar.delete_comment_requested.connect(self._on_delete_comment)
        self.review_toolbar.delete_all_comments_requested.connect(self._on_delete_all_comments)
        self.review_toolbar.new_comment_requested.connect(self._on_new_comment)
        self.review_toolbar.previous_requested.connect(self._on_prev_review_item)
        self.review_toolbar.next_requested.connect(self._on_next_review_item)
        self.review_pane.item_activated.connect(self._on_review_item_activated)

        self.retranslate_ui()

    def _on_outline_structure_changed(self) -> None:
        self.canvas_view.set_document(self.canvas_view.doc)
        self.canvas_view.controller.document_modified.emit()

    def _on_zoom_changed(self, zoom: float) -> None:
        self.h_ruler.update_zoom(zoom)
        self.v_ruler.update_zoom(zoom)

    def _on_caret_moved(self, para_id: int, offset: int) -> None:
        self.h_ruler.update_geometry_from_canvas()
        self.v_ruler.update_geometry_from_canvas()

    def _on_document_modified(self) -> None:
        self.h_ruler.update_geometry_from_canvas()
        self.v_ruler.update_geometry_from_canvas()
        self.review_pane.refresh_items()

    def _on_review_item_activated(self, para: Paragraph, start: int, end: int) -> None:
        """Focus and position caret on activated review item."""
        self.canvas_view.controller.set_caret(para.id, start)
        self.canvas_view.update()

    def _on_accept_change(self) -> None:
        """Accept change at current caret or selection."""
        doc = self.canvas_view.doc
        from atboffice.modules.writer.models.revision import accept_revision, list_revisions

        revs = list_revisions(doc)
        if revs:
            accept_revision(doc, revs[0])
            self.canvas_view.update()
            self.review_pane.refresh_items()

    def _on_accept_all_changes(self) -> None:
        """Accept all changes in document."""
        doc = self.canvas_view.doc
        from atboffice.modules.writer.models.revision import accept_all_revisions

        accept_all_revisions(doc)
        self.canvas_view.update()
        self.review_pane.refresh_items()

    def _on_reject_change(self) -> None:
        """Reject change at current caret or selection."""
        doc = self.canvas_view.doc
        from atboffice.modules.writer.models.revision import list_revisions, reject_revision

        revs = list_revisions(doc)
        if revs:
            reject_revision(doc, revs[0])
            self.canvas_view.update()
            self.review_pane.refresh_items()

    def _on_reject_all_changes(self) -> None:
        """Reject all changes in document."""
        doc = self.canvas_view.doc
        from atboffice.modules.writer.models.revision import reject_all_revisions

        reject_all_revisions(doc)
        self.canvas_view.update()
        self.review_pane.refresh_items()

    def _on_delete_comment(self) -> None:
        """Delete active or first comment in document."""
        doc = self.canvas_view.doc
        from atboffice.modules.writer.models.revision import delete_comment

        if doc.comments:
            first_id = next(iter(doc.comments.keys()))
            delete_comment(doc, first_id)
            self.canvas_view.update()
            self.review_pane.refresh_items()

    def _on_delete_all_comments(self) -> None:
        """Delete all comments in document."""
        doc = self.canvas_view.doc
        from atboffice.modules.writer.models.revision import delete_comment

        for cid in list(doc.comments.keys()):
            delete_comment(doc, cid)
        self.canvas_view.update()
        self.review_pane.refresh_items()

    def _on_new_comment(self) -> None:
        """Insert new comment at caret."""
        doc = self.canvas_view.doc
        from atboffice.modules.writer.models.revision import add_comment

        add_comment(doc, text="New Comment", author="Author")
        self.canvas_view.update()
        self.review_pane.refresh_items()

    def _on_prev_review_item(self) -> None:
        cur = self.review_pane.list_widget.currentRow()
        if cur > 0:
            self.review_pane.list_widget.setCurrentRow(cur - 1)

    def _on_next_review_item(self) -> None:
        cur = self.review_pane.list_widget.currentRow()
        if cur < self.review_pane.list_widget.count() - 1:
            self.review_pane.list_widget.setCurrentRow(cur + 1)

    def set_review_pane_visible(self, visible: bool) -> None:
        """Toggle Reviewing Pane visibility."""
        self.review_pane.setVisible(visible)
        self.review_toolbar.set_pane_state(visible)

    def set_review_toolbar_visible(self, visible: bool) -> None:
        """Toggle Reviewing Toolbar visibility."""
        self.review_toolbar.setVisible(visible)

    def set_view_mode(self, mode: ViewMode | str) -> None:
        """Switch active display mode (print, normal, web, reading, outline)."""
        if isinstance(mode, str):
            mode = ViewMode(mode)
        self.view_mode = mode
        self.canvas_view.set_view_mode(mode)
        if mode == ViewMode.OUTLINE:
            self.tab_selector.setVisible(False)
            self.h_ruler.setVisible(False)
            self.v_ruler.setVisible(False)
            self.outline_toolbar.setVisible(True)
            self.reading_toolbar.setVisible(False)
            self.outline_widget.set_document(self.canvas_view.doc)
            self.center_stack.setCurrentIndex(1)
        elif mode == ViewMode.READING:
            self.tab_selector.setVisible(False)
            self.h_ruler.setVisible(False)
            self.v_ruler.setVisible(False)
            self.outline_toolbar.setVisible(False)
            self.reading_toolbar.setVisible(True)
            self.center_stack.setCurrentIndex(0)
        elif mode == ViewMode.NORMAL:
            self.tab_selector.setVisible(False)
            self.h_ruler.setVisible(True)
            self.v_ruler.setVisible(False)
            self.outline_toolbar.setVisible(False)
            self.reading_toolbar.setVisible(False)
            self.center_stack.setCurrentIndex(0)
        elif mode == ViewMode.WEB:
            self.tab_selector.setVisible(False)
            self.h_ruler.setVisible(True)
            self.v_ruler.setVisible(False)
            self.outline_toolbar.setVisible(False)
            self.reading_toolbar.setVisible(False)
            self.center_stack.setCurrentIndex(0)
        else:  # PRINT or default
            self.tab_selector.setVisible(True)
            self.h_ruler.setVisible(True)
            self.v_ruler.setVisible(True)
            self.outline_toolbar.setVisible(False)
            self.reading_toolbar.setVisible(False)
            self.center_stack.setCurrentIndex(0)

        self.view_mode_changed.emit(self.view_mode)

    def scroll_to_page(self, page_idx: int) -> None:
        """Scroll document to page page_idx."""
        self.canvas_view.scroll_to_page(page_idx)

    def scroll_to_paragraph(self, para_id: int) -> bool:
        """Scroll document to paragraph with para_id."""
        if self.view_mode == ViewMode.OUTLINE:
            for p in all_paragraphs(self.canvas_view.doc):
                if p.id == para_id:
                    self.outline_widget.selected_para = p
                    self.outline_widget.update()
                    break
        return self.canvas_view.scroll_to_paragraph(para_id)

    def set_ruler_visible(self, visible: bool) -> None:
        """Toggle visibility of rulers and corner tab selector."""
        self.tab_selector.setVisible(visible)
        self.h_ruler.setVisible(visible)
        self.v_ruler.setVisible(visible)

    def set_ruler_unit(self, unit: RulerUnit | str) -> None:
        """Set measurement unit for both horizontal and vertical rulers."""
        self.h_ruler.set_unit(unit)
        self.v_ruler.set_unit(unit)

    def retranslate_ui(self) -> None:
        """Update localized UI strings."""
        self.tab_selector.retranslate_ui()
        self.h_ruler.retranslate_ui()
        self.v_ruler.retranslate_ui()
        self.canvas_view.retranslate_ui()
        self.review_pane.retranslate_ui()
        self.review_toolbar.retranslate_ui()
        self.outline_toolbar.retranslate_ui()
        self.reading_toolbar.retranslate_ui()

    def open_spelling_dialog(self) -> None:
        """Open Spelling and Grammar check modal dialog (F7)."""
        self.canvas_view.open_spelling_dialog()

    def create_word_count_dialog(self) -> WordCountDialog:
        """Create and return configured WordCountDialog instance."""
        from atboffice.modules.writer.dialogs.word_count_dlg import WordCountDialog

        selection_text = self.canvas_view.controller.get_selected_text()
        return WordCountDialog(
            doc=self.canvas_view.doc,
            selection_text=selection_text,
            pagination=getattr(self.canvas_view, "pagination", None),
            parent=self,
        )

    def open_word_count_dialog(self) -> WordCountDialog:
        """Open classic Word 2003 Word Count dialog."""
        dlg = self.create_word_count_dialog()
        dlg.exec()
        return dlg

    def open_mail_merge_wizard(self) -> None:
        """Open the Word 2003 classic Mail Merge Wizard."""
        from atboffice.modules.writer.dialogs.mailmerge_wizard import MailMergeWizardDialog

        self.canvas_view.doc.mailmerge_engine = self.mailmerge_engine
        dlg = MailMergeWizardDialog(
            doc=self.canvas_view.doc,
            engine=self.mailmerge_engine,
            writer_view=self,
            parent=self,
        )
        dlg.exec()

    def insert_merge_field(self) -> None:
        """Open Insert Merge Field dialog."""
        from atboffice.modules.writer.dialogs.mailmerge_wizard import InsertMergeFieldDialog

        dlg = InsertMergeFieldDialog(engine=self.mailmerge_engine, parent=self)

        def _on_field(name: str) -> None:
            controller = self.canvas_view.controller
            para = controller.caret_para
            offset = controller.caret_offset
            if para is not None:
                self.mailmerge_engine.insert_field(para, offset, name)
                self.canvas_view.update()

        dlg.field_selected.connect(_on_field)
        dlg.exec()

    def toggle_mail_merge_preview(self) -> bool:
        """Toggle mail merge preview mode on current document."""
        res = self.mailmerge_engine.toggle_preview(self.canvas_view.doc)
        self.canvas_view.update()
        return res

    def step_mail_merge_record(self, delta: int) -> int:
        """Navigate mail merge record in preview mode."""
        rec = self.mailmerge_engine.step(self.canvas_view.doc, delta)
        self.canvas_view.update()
        return rec
