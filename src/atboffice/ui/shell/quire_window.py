"""Quire dedicated word-processing window with Word 2003 Luna menus and toolbars."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QComboBox, QDialog, QMessageBox, QWidget

from atboffice.core.action_registry import ActionRegistry
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.core.search import SearchController, WriterSearchAdapter
from atboffice.modules.writer.dialogs import (
    AutoCorrectDialog,
    AutoSummarizeDialog,
    BookmarkDialog,
    BreakDialog,
    CaptionDialog,
    ChangeCaseDialog,
    CrossRefDialog,
    CustomizeDialog,
    DateTimeDialog,
    DeleteCellsDialog,
    DocumentThemeDialog,
    DropCapDialog,
    EnvelopesLabelsDialog,
    FieldDialog,
    FootnoteDialog,
    HyperlinkDialog,
    HyphenationDialog,
    IndexTablesDialog,
    InsertCellsDialog,
    LetterWizardDialog,
    PageNumbersDialog,
    QuireOptionsDialog,
    SplitCellsDialog,
    SymbolDialog,
    TableAutoFormatDialog,
    TableFormulaDialog,
    TableSortDialog,
    TextDirectionDialog,
    WatermarkDialog,
)
from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.models.document import ilen
from atboffice.modules.writer.models.revision import is_tracking
from atboffice.modules.writer.view import WriterView
from atboffice.modules.writer.views import (
    CloseFullScreenBar,
    QuireNavDock,
    ViewMode,
    doc_actions,
)
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.dialogs.find_replace_dialog import FindReplaceDialog
from atboffice.ui.shell.base_window import BaseOfficeWindow, UnsupportedSaveFormatError
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu
from atboffice.ui.shell.quire_toolbars import (
    build_quire_toolbars,
    retranslate_quire_toolbars,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for QuireWindow."""
    return core_safe_tr(text)


def _document_plain_text(doc: Any) -> str:
    """Flatten a Quire document to plain text: one line per paragraph, tab-separated cells."""
    from atboffice.modules.writer.models.document import Paragraph, Table, plain_text

    lines: list[str] = []

    def walk(blocks: Any) -> None:
        for block in blocks or []:
            if isinstance(block, Paragraph):
                lines.append(plain_text(block))
            elif isinstance(block, Table):
                for row in block.rows:
                    cell_texts = []
                    for cell in row.cells:
                        cell_lines: list[str] = []
                        for inner in cell.blocks or []:
                            if isinstance(inner, Paragraph):
                                cell_lines.append(plain_text(inner))
                        cell_texts.append(" ".join(t for t in cell_lines if t))
                    lines.append("\t".join(cell_texts))

    main = getattr(doc, "main", None)
    walk(getattr(main, "blocks", None))
    return "\n".join(lines) + ("\n" if lines else "")


class QuireWindow(BaseOfficeWindow):
    """Dedicated word-processing window embedding WriterView with Word 2003 styling."""

    recovery_suffix = ".docx"

    def __init__(
        self,
        file_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self.app_name = "ATBOffice Quire"
        self.app_type = "quire"
        super().__init__(parent)
        self.resize(1100, 750)
        self._syncing_toolbars: bool = False

        # 1. Embed WriterView first so canvas is ready for action registration
        self.writer_view = WriterView(parent=self)
        self.setCentralWidget(self.writer_view)

        # 2. Action Registry command bus
        self.action_registry = ActionRegistry(self)

        # Search Controller & Adapter
        self.search_controller = SearchController(self)
        self.search_adapter = WriterSearchAdapter(
            doc=self.writer_view.canvas_view.doc,
            caret_controller=self.writer_view.canvas_view.controller,
            writer_view=self.writer_view,
        )
        self.search_controller.set_adapter(self.search_adapter)
        self._find_replace_dialog: FindReplaceDialog | None = None

        # 3. Setup native macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        # 4. Initialize universal TaskPaneDock
        self.init_task_pane_dock(safe_tr("文档"))
        self._setup_quire_task_panes()

        # Initialize Quire Left Navigation Dock (Document Map & Thumbnails)
        self.nav_dock = QuireNavDock(
            doc=self.writer_view.canvas_view.doc,
            canvas_view=self.writer_view.canvas_view,
            controller=self.writer_view.canvas_view.controller,
            parent=self,
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.nav_dock)
        self.nav_dock.hide()
        self.nav_dock.visibilityChanged.connect(self._on_nav_dock_visibility_changed)
        self.nav_dock.doc_map_pane.heading_selected.connect(self.writer_view.scroll_to_paragraph)
        self.nav_dock.thumbnails_pane.page_selected.connect(self.writer_view.scroll_to_page)

        # Initialize Floating Full Screen Bar
        self.fullscreen_bar = CloseFullScreenBar(parent=self)
        self.fullscreen_bar.close_full_screen_requested.connect(self.exit_full_screen)
        self.fullscreen_bar.hide()
        self._is_fullscreen_mode: bool = False
        self._prev_view_mode: ViewMode = ViewMode.PRINT
        self._saved_toolbars_visible: list[tuple[Any, bool]] = []

        # Wire view mode and reading toolbar signals
        self.writer_view.view_mode_changed.connect(self._on_view_mode_changed)
        self.writer_view.reading_toolbar.toggle_doc_map_requested.connect(self.toggle_document_map)
        self.writer_view.reading_toolbar.toggle_thumbnails_requested.connect(self.toggle_thumbnails)
        self.writer_view.reading_toolbar.find_requested.connect(self.open_find_dialog)
        self.writer_view.reading_toolbar.research_requested.connect(self.toggle_task_pane)

        # 5. Setup Office 2003 Luna toolbars
        self._setup_toolbars()
        self._bind_action_handlers()

        # 5. Connect document modifications and caret/selection to listeners
        self.writer_view.canvas_view.controller.document_modified.connect(
            self._on_document_modified
        )
        # Caret moves refresh toolbars/context immediately. Selection-only changes are
        # coalesced into one deferred refresh, which a caret move in the same
        # keystroke cancels, so each edit syncs the toolbars once instead of 2-3 times.
        self._caret_ui_timer = QTimer(self)
        self._caret_ui_timer.setSingleShot(True)
        self._caret_ui_timer.setInterval(0)
        self._caret_ui_timer.timeout.connect(self._flush_caret_ui_sync)
        self.writer_view.canvas_view.caret_moved.connect(self._on_caret_moved)
        self.writer_view.canvas_view.controller.selection_changed.connect(
            self._schedule_caret_ui_sync
        )

        # 6. Load file or set initial document title
        if file_path is not None:
            p = Path(file_path)
            if p.exists() or p.is_symlink():
                self.open_file(p)
            else:
                self.current_file_path = p.resolve()
                self.update_window_title()
        else:
            self.update_window_title()

        self.set_modified(False)
        self._sync_toolbar_states()
        self.menu_bar.retranslate_ui()

    def _bind_action_handlers(self) -> None:
        """Bind window callbacks to core action IDs in ActionRegistry."""
        canvas = self.writer_view.canvas_view

        # Standard file & edit
        self.action_registry.set_handler("new", self.new_file)
        self.action_registry.set_handler("open", self.open_file_dialog)
        self.action_registry.set_handler("save", self.save_file)
        self.action_registry.set_handler("print", self.print_document)
        self.action_registry.set_handler("printPreview", self.print_preview)
        self.action_registry.set_handler("cut", self.cut)
        self.action_registry.set_handler("copy", self.copy)
        self.action_registry.set_handler("paste", self.paste)
        self.action_registry.set_handler("undo", self.undo)
        self.action_registry.set_handler("redo", self.redo)
        self.action_registry.set_handler("find", self.open_find_dialog)
        self.action_registry.set_handler("replace", self.open_replace_dialog)
        self.action_registry.set_handler("spelling", self.writer_view.open_spelling_dialog)
        self.action_registry.set_handler(
            "tools_word_count", self.writer_view.open_word_count_dialog
        )
        self.action_registry.set_handler("wordCount", self.writer_view.open_word_count_dialog)

        # Zoom & view
        self.action_registry.set_handler("taskPane", self.toggle_task_pane)
        self.action_registry.set_handler("stylesPane", lambda: self.show_task_pane("styles"))
        self.action_registry.set_handler(
            "styles_and_formatting", lambda: self.show_task_pane("styles")
        )
        self.action_registry.set_handler(
            "view_normal", lambda: self.switch_view_mode(ViewMode.NORMAL)
        )
        self.action_registry.set_handler("view_web", lambda: self.switch_view_mode(ViewMode.WEB))
        self.action_registry.set_handler(
            "view_print", lambda: self.switch_view_mode(ViewMode.PRINT)
        )
        self.action_registry.set_handler(
            "view_reading", lambda: self.switch_view_mode(ViewMode.READING)
        )
        self.action_registry.set_handler(
            "view_outline", lambda: self.switch_view_mode(ViewMode.OUTLINE)
        )
        self.action_registry.set_handler("view_fullscreen", self.toggle_fullscreen)
        self.action_registry.set_handler("view_doc_map", self.toggle_document_map)
        self.action_registry.set_handler("view_thumbnails", self.toggle_thumbnails)
        self.action_registry.set_handler("view_ruler", self.toggle_rulers)
        self.action_registry.set_handler(
            "promoteH1", self.writer_view.outline_widget.promote_selected_h1
        )
        self.action_registry.set_handler(
            "promote", self.writer_view.outline_widget.promote_selected
        )
        self.action_registry.set_handler("demote", self.writer_view.outline_widget.demote_selected)
        self.action_registry.set_handler(
            "demoteBody", self.writer_view.outline_widget.demote_selected_body
        )
        self.action_registry.set_handler("moveUp", self.writer_view.outline_widget.move_selected_up)
        self.action_registry.set_handler(
            "moveDown", self.writer_view.outline_widget.move_selected_down
        )
        self.action_registry.set_handler("expand", self.writer_view.outline_widget.expand_selected)
        self.action_registry.set_handler(
            "collapse", self.writer_view.outline_widget.collapse_selected
        )
        self.action_registry.set_handler("properties", self.show_document_properties_dialog)
        self.action_registry.set_handler("zoom_in", self.zoom_in)
        self.action_registry.set_handler("zoom_out", self.zoom_out)
        self.action_registry.set_handler("zoom_reset", self.zoom_reset)
        self.action_registry.set_handler("help", self.show_about)
        self.action_registry.set_handler("tb_tables", self._toggle_tables_toolbar)
        self.action_registry.set_handler("tb_drawing", self._toggle_drawing_toolbar)

        # Character formatting
        self.action_registry.set_handler("bold", self._toggle_bold)
        self.action_registry.set_handler("italic", self._toggle_italic)
        self.action_registry.set_handler("underline", self._toggle_underline)

        # Paragraph alignment & indent
        self.action_registry.set_handler(
            "alignLeft", lambda: canvas.set_paragraph_alignment("left")
        )
        self.action_registry.set_handler(
            "alignCenter", lambda: canvas.set_paragraph_alignment("center")
        )
        self.action_registry.set_handler(
            "alignRight", lambda: canvas.set_paragraph_alignment("right")
        )
        self.action_registry.set_handler("justify", lambda: canvas.set_paragraph_alignment("both"))
        self.action_registry.set_handler("incIndent", lambda: canvas.change_indent(36.0))
        self.action_registry.set_handler("decIndent", lambda: canvas.change_indent(-36.0))

        # Lists
        self.action_registry.set_handler("bullets", lambda: canvas.toggle_list_style("bullet"))
        self.action_registry.set_handler("numbering", lambda: canvas.toggle_list_style("number"))

        # Table operations
        self.action_registry.set_handler("mergeCells", canvas.merge_table_cells)
        self.action_registry.set_handler("splitCells", lambda: canvas.split_table_cells(1, 2))
        self.action_registry.set_handler("distRows", canvas.distribute_table_rows)
        self.action_registry.set_handler("distCols", canvas.distribute_table_cols)
        self.action_registry.set_handler("sortAsc", lambda: canvas.sort_table(ascending=True))
        self.action_registry.set_handler("sortDesc", lambda: canvas.sort_table(ascending=False))
        self.action_registry.set_handler("autoSum", canvas.auto_sum_table)

        # Review & Revisions
        self.action_registry.set_handler("trackChanges", canvas.toggle_track_changes)
        self.action_registry.set_handler("acceptChange", canvas.accept_current_revision)
        self.action_registry.set_handler("rejectChange", canvas.reject_current_revision)
        self.action_registry.set_handler("insertComment", canvas.insert_comment)
        self.action_registry.set_handler(
            "reviewingPane",
            lambda: self.writer_view.set_review_pane_visible(
                not self.writer_view.review_pane.isVisible()
            ),
        )

        # Outlining
        # Outline commands act on the outline pane in Outline view, else on the caret
        # paragraph in the canvas (the earlier pane-only bindings were overwritten here).
        outline = self.writer_view.outline_widget
        for aid, pane_cmd, canvas_cmd in (
            ("promoteH1", outline.promote_selected_h1, lambda: canvas.set_outline_level(1)),
            ("promote", outline.promote_selected, lambda: canvas.change_outline_level(-1)),
            ("demote", outline.demote_selected, lambda: canvas.change_outline_level(1)),
            ("demoteBody", outline.demote_selected_body,
             lambda: canvas.set_outline_level(None)),
            ("moveUp", outline.move_selected_up, lambda: canvas.move_paragraph(-1)),
            ("moveDown", outline.move_selected_down, lambda: canvas.move_paragraph(1)),
        ):
            self.action_registry.set_handler(
                aid, lambda p=pane_cmd, c=canvas_cmd: self._outline_dispatch(p, c)
            )

        # Mail merge
        self.action_registry.set_handler("mmMainDoc", self.writer_view.open_mail_merge_wizard)
        self.action_registry.set_handler("mmOpenSource", self.writer_view.open_mail_merge_wizard)
        self.action_registry.set_handler("mmRecipients", self.writer_view.open_mail_merge_wizard)
        self.action_registry.set_handler("mmAddress", self.writer_view.insert_merge_field)
        self.action_registry.set_handler("mmGreeting", self.writer_view.insert_merge_field)
        self.action_registry.set_handler("mmInsertField", self.writer_view.insert_merge_field)
        self.action_registry.set_handler("mmViewData", self.writer_view.toggle_mail_merge_preview)
        self.action_registry.set_handler(
            "mmFirst", lambda: self.writer_view.step_mail_merge_record(-9999)
        )
        self.action_registry.set_handler(
            "mmPrev", lambda: self.writer_view.step_mail_merge_record(-1)
        )
        self.action_registry.set_handler(
            "mmNext", lambda: self.writer_view.step_mail_merge_record(1)
        )
        self.action_registry.set_handler(
            "mmLast", lambda: self.writer_view.step_mail_merge_record(9999)
        )
        self.action_registry.set_handler("insertWordArt", self.open_wordart_gallery)
        self.action_registry.set_handler("wa_insert", self.open_wordart_gallery)
        self.action_registry.set_handler("wordartGallery", self.open_wordart_gallery)
        self.action_registry.set_handler("wordartEdit", self.open_wordart_gallery)

        # Standard toolbar dropdowns
        self.action_registry.set_handler("tb_table_drop", lambda: canvas.insert_table(2, 2))
        self.action_registry.set_handler("insertTable_dialog", lambda: canvas.insert_table(2, 2))
        self.action_registry.set_handler(
            "insertTable_col_left", lambda: canvas.insert_table_col(left=True)
        )
        self.action_registry.set_handler(
            "insertTable_row_above", lambda: canvas.insert_table_row(above=True)
        )
        self.action_registry.set_handler(
            "col_1",
            lambda: self._apply_dialog(lambda: doc_actions.set_columns(canvas, 1)),
        )
        self.action_registry.set_handler(
            "col_2",
            lambda: self._apply_dialog(lambda: doc_actions.set_columns(canvas, 2)),
        )
        self.action_registry.set_handler(
            "col_3",
            lambda: self._apply_dialog(lambda: doc_actions.set_columns(canvas, 3)),
        )

        # Formatting toolbar dropdowns and split actions
        self.action_registry.set_handler("line_spacing_1_0", lambda: canvas.set_line_spacing(1.0))
        self.action_registry.set_handler("line_spacing_1_5", lambda: canvas.set_line_spacing(1.5))
        self.action_registry.set_handler("line_spacing_2_0", lambda: canvas.set_line_spacing(2.0))
        self.action_registry.set_handler("line_spacing_2_5", lambda: canvas.set_line_spacing(2.5))
        self.action_registry.set_handler("line_spacing_3_0", lambda: canvas.set_line_spacing(3.0))
        self.action_registry.set_handler("line_spacing_more", lambda: canvas.set_line_spacing(1.5))
        self.action_registry.set_handler("borderBtn", lambda: self.apply_border_preset("outside"))
        self.action_registry.set_handler("border_none", lambda: self.apply_border_preset("none"))
        self.action_registry.set_handler("border_all", lambda: self.apply_border_preset("all"))
        self.action_registry.set_handler(
            "border_outside", lambda: self.apply_border_preset("outside")
        )
        self.action_registry.set_handler(
            "border_bottom", lambda: self.apply_border_preset("bottom")
        )
        self.action_registry.set_handler("border_top", lambda: self.apply_border_preset("top"))
        self.action_registry.set_handler("border_left", lambda: self.apply_border_preset("left"))
        self.action_registry.set_handler("border_right", lambda: self.apply_border_preset("right"))

        # Tables toolbar dropdowns and split actions
        self.action_registry.set_handler("tbl_insert_table", lambda: canvas.insert_table(2, 2))
        self.action_registry.set_handler(
            "tbl_insert_col_left", lambda: canvas.insert_table_col(left=True)
        )
        self.action_registry.set_handler(
            "tbl_insert_col_right", lambda: canvas.insert_table_col(left=False)
        )
        self.action_registry.set_handler(
            "tbl_insert_row_above", lambda: canvas.insert_table_row(above=True)
        )
        self.action_registry.set_handler(
            "tbl_insert_row_below", lambda: canvas.insert_table_row(above=False)
        )
        self.action_registry.set_handler("tableBorderBtn", lambda: self.apply_table_border("all"))
        self.action_registry.set_handler("tbl_border_all", lambda: self.apply_table_border("all"))
        self.action_registry.set_handler(
            "tbl_border_outside", lambda: self.apply_table_border("outside")
        )
        self.action_registry.set_handler("tbl_border_none", lambda: self.apply_table_border("none"))
        self.action_registry.set_handler("tbl_align_top", lambda: self.set_table_cell_valign("top"))
        self.action_registry.set_handler(
            "tbl_align_center", lambda: self.set_table_cell_valign("center")
        )
        self.action_registry.set_handler(
            "tbl_align_bottom", lambda: self.set_table_cell_valign("bottom")
        )

        # Reviewing toolbar dropdowns and split actions
        self.action_registry.set_handler(
            "rev_accept_selected",
            lambda: canvas.accept_current_revision(all_revisions=False),
        )
        self.action_registry.set_handler(
            "rev_accept_all", lambda: canvas.accept_current_revision(all_revisions=True)
        )
        self.action_registry.set_handler(
            "rev_reject_selected",
            lambda: canvas.reject_current_revision(all_revisions=False),
        )
        self.action_registry.set_handler(
            "rev_reject_all", lambda: canvas.reject_current_revision(all_revisions=True)
        )
        self.action_registry.set_handler(
            "rev_delete_all_comments", lambda: setattr(canvas.doc, "comments", [])
        )

        # Drawing toolbar dropdowns and object actions
        self.action_registry.set_handler(
            "draw_order_front", lambda: self.reorder_selected_object("front")
        )
        self.action_registry.set_handler(
            "draw_order_back", lambda: self.reorder_selected_object("back")
        )
        self.action_registry.set_handler("draw_nudge_up", lambda: self.nudge_selected_object(0, -1))
        self.action_registry.set_handler(
            "draw_nudge_down", lambda: self.nudge_selected_object(0, 1)
        )
        self.action_registry.set_handler(
            "draw_align_left", lambda: self.align_selected_objects("left")
        )
        self.action_registry.set_handler(
            "draw_rotate_right", lambda: self.rotate_selected_object(90)
        )
        self.action_registry.set_handler("as_lines", lambda: self.insert_shape("line"))
        self.action_registry.set_handler("as_connectors", lambda: self.insert_shape("connector"))
        self.action_registry.set_handler("as_basic", lambda: self.insert_shape("basic"))
        self.action_registry.set_handler("as_arrows", lambda: self.insert_shape("arrow"))
        self.action_registry.set_handler("as_flowchart", lambda: self.insert_shape("flowchart"))
        self.action_registry.set_handler("as_stars", lambda: self.insert_shape("star"))
        self.action_registry.set_handler("as_callouts", lambda: self.insert_shape("callout"))
        self.action_registry.set_handler("drawLine", lambda: self.insert_shape("line"))
        self.action_registry.set_handler("drawArrow", lambda: self.insert_shape("arrow"))
        self.action_registry.set_handler("drawRect", lambda: self.insert_shape("rect"))
        self.action_registry.set_handler("drawOval", lambda: self.insert_shape("oval"))
        self.action_registry.set_handler("textBox", lambda: self.insert_shape("textbox"))

        # Missing Quire dialog clusters (Phase 6)
        # Cluster 1: Formatting & Page Setup
        self.action_registry.set_handler("break", self.open_break_dialog)
        self.action_registry.set_handler("dropCap", self.open_drop_cap_dialog)
        self.action_registry.set_handler("textDirection", self.open_text_direction_dialog)
        self.action_registry.set_handler("watermark", self.open_watermark_dialog)
        self.action_registry.set_handler("pageNumbers", self.open_page_numbers_dialog)
        self.action_registry.set_handler("changeCase", self.open_change_case_dialog)
        self.action_registry.set_handler("theme", self.open_document_theme_dialog)

        # Cluster 2: References & Markers
        self.action_registry.set_handler("footnote", self.open_footnote_dialog)
        self.action_registry.set_handler("caption", self.open_caption_dialog)
        self.action_registry.set_handler("crossReference", self.open_cross_ref_dialog)
        self.action_registry.set_handler("indexTables", self.open_index_tables_dialog)
        self.action_registry.set_handler("bookmark", self.open_bookmark_dialog)
        self.action_registry.set_handler("hyperlink", self.open_hyperlink_dialog)
        self.action_registry.set_handler("dateTime", self.open_date_time_dialog)
        self.action_registry.set_handler("field", self.open_field_dialog)
        self.action_registry.set_handler("symbol", self.open_symbol_dialog)

        # Cluster 3: Tools & Options
        self.action_registry.set_handler("autoCorrect", self.open_autocorrect_dialog)
        self.action_registry.set_handler("autocorrect", self.open_autocorrect_dialog)
        self.action_registry.set_handler("customize", self.open_customize_dialog)
        self.action_registry.set_handler("options", self.open_quire_options_dialog)
        self.action_registry.set_handler("envelopes", self.open_envelopes_labels_dialog)
        self.action_registry.set_handler("letterWizard", self.open_letter_wizard_dialog)
        self.action_registry.set_handler("autoSummarize", self.open_autosummarize_dialog)
        self.action_registry.set_handler("hyphenation", self.open_hyphenation_dialog)

        # Cluster 4: Table Operations
        self.action_registry.set_handler("insertCells", self.open_insert_cells_dialog)
        self.action_registry.set_handler("deleteCells", self.open_delete_cells_dialog)
        self.action_registry.set_handler("splitCells_dialog", self.open_split_cells_dialog)
        self.action_registry.set_handler("tableAutoFormat", self.open_table_autoformat_dialog)
        self.action_registry.set_handler("sort", self.open_table_sort_dialog)
        self.action_registry.set_handler("tableSort", self.open_table_sort_dialog)
        self.action_registry.set_handler("formula", self.open_table_formula_dialog)
        self.action_registry.set_handler("tableFormula", self.open_table_formula_dialog)
        self._bind_menu_dialog_handlers()
        from atboffice.ui.shell.quire_commands import bind_quire_toolbar_commands

        self.toolbar_commands = bind_quire_toolbar_commands(self)


    def _outline_dispatch(self, pane_cmd: Any, canvas_cmd: Any) -> None:
        if getattr(self.writer_view, "view_mode", None) == ViewMode.OUTLINE:
            pane_cmd()
        else:
            canvas_cmd()

    # --- Format / Table / Tools menu dialogs ----------------------------------------
    def _bind_menu_dialog_handlers(self) -> None:
        """Bind the menu bar's Format/Table/Insert/Tools commands (issue #443)."""
        canvas = self.writer_view.canvas_view
        reg = self.action_registry
        reg.set_handler("format_font", self.open_font_dialog)
        reg.set_handler("format_paragraph", self.open_paragraph_dialog)
        reg.set_handler("format_borders", self.open_borders_dialog)
        reg.set_handler("format_tabs", self.writer_view._on_tabs_dialog_requested)
        reg.set_handler("tools_language", self.open_language_dialog)
        reg.set_handler("table_insert", self.open_insert_table_dialog)
        reg.set_handler("table_delete", self.open_delete_cells_dialog)
        reg.set_handler("table_select", lambda: doc_actions.select_table(canvas))
        reg.set_handler("table_properties", self.open_table_properties_dialog)
        reg.set_handler("insert_page_break", lambda: self._apply_dialog(
            lambda: doc_actions.insert_page_break(canvas)))
        reg.set_handler("insert_page_number", self.open_page_numbers_dialog)
        reg.set_handler("insert_date_time", self.open_date_time_dialog)
        reg.set_handler("insert_symbol", self.open_symbol_dialog)
        reg.set_handler("columns", self.open_columns_dialog)
        reg.set_handler("col_left", lambda: self._apply_dialog(
            lambda: doc_actions.set_columns(canvas, "left")))
        reg.set_handler("col_right", lambda: self._apply_dialog(
            lambda: doc_actions.set_columns(canvas, "right")))
        # Toolbar IDs that name the same commands as the View menu.
        reg.register_alias("docMap", "view_doc_map")
        reg.register_alias("viewReading", "view_reading")
        reg.set_handler("pageSetup", self.writer_view._on_page_setup_requested)

    def _selection_run_props(self) -> Any:
        from atboffice.modules.writer.models.properties import RunProperties

        p = doc_actions.current_paragraph(self.writer_view.canvas_view)
        if p is None:
            return RunProperties()
        return doc_actions._caret_r_pr(p, self.writer_view.canvas_view.controller.pos.offset)

    def open_font_dialog(self) -> Any:
        from atboffice.modules.writer.dialogs.font_dialog import FontDialog

        canvas = self.writer_view.canvas_view
        dlg = FontDialog(props=self._selection_run_props(), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new = dlg.get_properties()
            fields = ("font", "font_ea", "font_cs", "sz", "b", "i", "u", "color", "vert",
                      "strike", "dstrike", "caps", "small_caps", "spacing", "highlight")

            def apply(r_pr: Any) -> None:
                for name in fields:
                    if hasattr(new, name):
                        setattr(r_pr, name, getattr(new, name))

            self._apply_dialog(lambda: canvas.format_range(apply))
        return dlg

    def open_paragraph_dialog(self) -> Any:
        from atboffice.modules.writer.dialogs.paragraph_dialog import ParagraphDialog

        canvas = self.writer_view.canvas_view
        p = doc_actions.current_paragraph(canvas)
        dlg = ParagraphDialog(props=p.p_pr if p is not None else None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and p is not None:
            new = dlg.get_properties()

            def apply() -> None:
                for para in self._selected_paragraphs():
                    for name in ("jc", "ind", "sp", "keep_next", "keep_lines",
                                 "page_break_before", "widow_control", "outline_level"):
                        setattr(para.p_pr, name, copy.deepcopy(getattr(new, name)))

            self._apply_dialog(apply)
        return dlg

    def _selected_paragraphs(self) -> list[Any]:
        canvas = self.writer_view.canvas_view
        ctrl = canvas.controller
        if ctrl.selection.is_collapsed:
            p = doc_actions.current_paragraph(canvas)
            return [p] if p is not None else []
        start, end = ctrl.selection.ordered_range(canvas.doc)
        paras = canvas.doc.all_paras()
        ids = [x.id for x in paras]
        try:
            a, b = ids.index(start.para_id), ids.index(end.para_id)
        except ValueError:
            return []
        return paras[a : b + 1]

    def open_borders_dialog(self) -> Any:
        from atboffice.modules.writer.dialogs.borders_shading import BordersShadingDialog

        canvas = self.writer_view.canvas_view
        ctx = canvas.get_current_table_context()
        dlg = BordersShadingDialog(
            parent=self,
            borders=dict(ctx["tbl"].tbl_pr.borders) if ctx else None,
            target_type="table" if ctx else "paragraph",
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            props = dlg.get_properties()

            def apply() -> None:
                borders = copy.deepcopy(props.get("borders") or {})
                shading = props.get("shading")
                if ctx is not None and props.get("apply_to") in (None, "table"):
                    ctx["tbl"].tbl_pr.borders = borders
                elif ctx is not None and props.get("apply_to") == "cell":
                    ctx["cell"].tc_pr.borders = borders
                    if shading is not None:
                        ctx["cell"].tc_pr.shd = copy.deepcopy(shading)
                else:
                    for para in self._selected_paragraphs():
                        para.p_pr.borders = copy.deepcopy(borders)
                        if shading is not None:
                            para.p_pr.shd = copy.deepcopy(shading)  # type: ignore[attr-defined]

            self._apply_dialog(apply)
        return dlg

    def open_columns_dialog(self) -> Any:
        from atboffice.modules.writer.dialogs.columns_dialog import ColumnsDialog

        canvas = self.writer_view.canvas_view
        sect = canvas.doc.sect
        dlg = ColumnsDialog(parent=self, cols=sect.cols, page_width=sect.pg_w,
                            margins=(sect.ml, sect.mr))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cols = dlg.get_columns()
            self._apply_dialog(lambda: setattr(canvas.doc.sect, "cols", copy.deepcopy(cols)))
        return dlg

    def open_insert_table_dialog(self) -> Any:
        from atboffice.modules.writer.dialogs.insert_table import InsertTableDialog

        canvas = self.writer_view.canvas_view
        dlg = InsertTableDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cols, rows, _fit, _width = dlg.get_dimensions()
            self._apply_dialog(lambda: canvas.insert_table(rows=rows, cols=cols))
        return dlg

    def open_table_properties_dialog(self) -> Any:
        from atboffice.modules.writer.dialogs.table_properties import TablePropertiesDialog

        canvas = self.writer_view.canvas_view
        ctx = canvas.get_current_table_context()
        if ctx is None:
            self.statusBar().showMessage(safe_tr("请先将光标置于表格中"), 3000)
            return None
        dlg = TablePropertiesDialog(
            parent=self,
            table=ctx["tbl"],
            table_props=ctx["tbl"].tbl_pr,
            row_idx=ctx["row_idx"],
            col_idx=ctx["col_idx"],
            cell_props=ctx["cell"].tc_pr,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: dlg.apply_to_table(ctx["tbl"]))
        return dlg

    def open_language_dialog(self) -> str | None:
        from PySide6.QtWidgets import QInputDialog

        languages = [
            ("English (United States)", "en-US"), ("English (United Kingdom)", "en-GB"),
            ("中文(中国)", "zh-CN"), ("中文(台湾)", "zh-TW"), ("日本語", "ja-JP"),
            ("한국어", "ko-KR"), ("Deutsch", "de-DE"), ("Français", "fr-FR"),
            ("Español", "es-ES"), ("Русский", "ru-RU"),
        ]
        labels = [name for name, _ in languages]
        choice, ok = QInputDialog.getItem(
            self, safe_tr("语言"), safe_tr("将所选文字标记为(&M):"), labels, 0, False
        )
        if not ok:
            return None
        code = dict(languages)[choice]
        canvas = self.writer_view.canvas_view
        self._apply_dialog(lambda: doc_actions.set_language(canvas, code))
        return code

    # --- Applying dialog results -------------------------------------------------
    def _apply_dialog(self, mutate: Any) -> Any:
        """Apply a dialog's result to the document as one undoable, repainted edit."""
        canvas = self.writer_view.canvas_view
        result = canvas.run_undoable(mutate)
        self.set_modified(True)
        self._sync_toolbar_states()
        return result

    def _apply_index_tables(self, dlg: Any) -> None:
        canvas = self.writer_view.canvas_view
        data = dlg.get_index_tables_data()
        tab = dlg.tab_widget.tabText(int(data.get("active_tab", 1)))
        if tab == safe_tr("目录"):
            self._apply_dialog(lambda: doc_actions.insert_table_of_contents(canvas, data))
        elif tab == safe_tr("图表目录"):
            label = data.get("tof_caption") or "Figure"
            self._apply_dialog(
                lambda: doc_actions.insert_field(canvas, f'TOC \\c "{label}"', label, "TOC")
            )
        elif tab == safe_tr("引文目录"):
            category = data.get("toa_category") or "1"
            self._apply_dialog(
                lambda: doc_actions.insert_field(canvas, f"TOA \\c {category}", "", "TOA")
            )
        else:
            self._apply_dialog(lambda: doc_actions.insert_field(canvas, "INDEX", "", "INDEX"))

    def _apply_bookmarks(self, dlg: Any) -> None:
        canvas = self.writer_view.canvas_view
        wanted = dlg.get_bookmarks()
        existing = doc_actions.document_bookmarks(canvas.doc)

        def sync() -> bool:
            changed = False
            for name in existing:
                if name not in wanted:
                    changed = doc_actions.delete_bookmark(canvas, name) or changed
            for name in wanted:
                if name not in existing:
                    changed = doc_actions.add_bookmark(canvas, name) or changed
            return changed

        if wanted != existing:
            self._apply_dialog(sync)
        target = dlg.get_selected_bookmark()
        if target and target in doc_actions.document_bookmarks(canvas.doc):
            canvas.jump_to_bookmark(target)

    def _apply_autocorrect(self, settings: dict[str, Any]) -> None:
        from atboffice.core.settings import get_app_settings

        app_settings = get_app_settings()
        for key, setting in (
            ("smart_quotes", "autocorrect/smart_quotes"),
            ("replace_type", "autocorrect/replace_text_as_you_type"),
            ("smart_fractions", "autocorrect/fractions"),
            ("two_caps", "autocorrect/two_initial_caps"),
            ("sentence_cap", "autocorrect/capitalize_sentences"),
            ("table_cell_cap", "autocorrect/capitalize_table_cells"),
            ("day_cap", "autocorrect/capitalize_days"),
            ("caps_lock", "autocorrect/caps_lock"),
        ):
            if key in settings:
                app_settings.set_value(setting, bool(settings[key]))
        rules = settings.get("rules") or {}
        engine = getattr(self.writer_view.canvas_view.controller, "autocorrect", None)
        if engine is not None and rules:
            engine.typos = dict(rules)

    def _apply_quire_options(self, data: dict[str, Any]) -> None:
        from atboffice.core.settings import get_app_settings

        app_settings = get_app_settings()
        for key, value in data.items():
            if key == "password":
                continue  # never persisted in plain settings
            app_settings.set_value(f"quire/{key}", value)
        canvas = self.writer_view.canvas_view
        if "spell_check" in data:
            canvas.doc.hide_spelling_errors = not bool(data["spell_check"])
            canvas.viewport().update()
        if "status_bar" in data and getattr(self, "status_bar", None) is not None:
            self.status_bar.setVisible(bool(data["status_bar"]))

    def _apply_split_cells(self, dims: tuple[int, int, bool]) -> None:
        rows, cols, _merge_first = dims
        canvas = self.writer_view.canvas_view
        if canvas.get_current_table_context() is None:
            return
        self._apply_dialog(lambda: canvas.split_table_cells(num_rows=rows, num_cols=cols))

    def _apply_table_sort(self, criteria: dict[str, Any]) -> None:
        canvas = self.writer_view.canvas_view
        ascending = bool((criteria.get("key1") or {}).get("ascending", True))
        self._apply_dialog(lambda: canvas.sort_table(ascending=ascending))

    # --- Quire Missing Dialog Cluster Openers ---
    def open_break_dialog(self) -> BreakDialog:
        dlg = BreakDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: doc_actions.insert_break(canvas, *dlg.get_break_type()))
        return dlg

    def open_drop_cap_dialog(self) -> DropCapDialog:
        dlg = DropCapDialog(parent=self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: doc_actions.apply_drop_cap(canvas, dlg.get_drop_cap_data()))
        return dlg

    def open_text_direction_dialog(self) -> TextDirectionDialog:
        dlg = TextDirectionDialog(parent=self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.apply_text_direction(canvas, dlg.get_direction())
            )
        return dlg

    def open_watermark_dialog(self) -> WatermarkDialog:
        dlg = WatermarkDialog(parent=self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.apply_watermark(canvas, dlg.get_watermark_data())
            )
        return dlg

    def open_page_numbers_dialog(self) -> PageNumbersDialog:
        dlg = PageNumbersDialog(parent=self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.apply_page_numbers(canvas, dlg.get_page_number_settings())
            )
        return dlg

    def open_change_case_dialog(self) -> ChangeCaseDialog:
        dlg = ChangeCaseDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: doc_actions.change_case(canvas, dlg.get_case_mode()))
        return dlg

    def open_document_theme_dialog(self) -> DocumentThemeDialog:
        dlg = DocumentThemeDialog(parent=self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: canvas.doc.settings.__setitem__("theme", dlg.get_selected_theme())
            )
        return dlg

    def open_footnote_dialog(self) -> FootnoteDialog:
        dlg = FootnoteDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.insert_footnote(canvas, dlg.get_footnote_settings())
            )
        return dlg

    def open_caption_dialog(self) -> CaptionDialog:
        dlg = CaptionDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: doc_actions.insert_caption(canvas, dlg.get_caption_data()))
        return dlg

    def open_cross_ref_dialog(self) -> CrossRefDialog:
        dlg = CrossRefDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.insert_cross_reference(canvas, dlg.get_cross_ref_data())
            )
        return dlg

    def open_index_tables_dialog(self) -> IndexTablesDialog:
        dlg = IndexTablesDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_index_tables(dlg)
        return dlg

    def open_bookmark_dialog(self) -> BookmarkDialog:
        dlg = BookmarkDialog(
            initial_bookmarks=doc_actions.document_bookmarks(self.writer_view.canvas_view.doc),
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_bookmarks(dlg)
        return dlg

    def open_hyperlink_dialog(self) -> HyperlinkDialog:
        dlg = HyperlinkDialog(parent=self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.insert_hyperlink(canvas, dlg.get_hyperlink_data())
            )
        return dlg

    def open_date_time_dialog(self) -> DateTimeDialog:
        dlg = DateTimeDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.insert_date_time(canvas, *dlg.get_selected_format())
            )
        return dlg

    def open_field_dialog(self) -> FieldDialog:
        dlg = FieldDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.insert_field_from_dialog(canvas, dlg.get_field_data())
            )
        return dlg

    def open_symbol_dialog(self) -> SymbolDialog:
        dlg = SymbolDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.insert_symbol(canvas, dlg.get_selected_character())
            )
        return dlg

    def open_autocorrect_dialog(self) -> AutoCorrectDialog:
        dlg = AutoCorrectDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_autocorrect(dlg.get_autocorrect_settings())
        return dlg

    def open_customize_dialog(self) -> CustomizeDialog:
        dlg = CustomizeDialog(self)
        dlg.exec()
        return dlg

    def open_quire_options_dialog(self) -> QuireOptionsDialog:
        dlg = QuireOptionsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_quire_options(dlg.get_options_data())
        return dlg

    def open_envelopes_labels_dialog(self) -> EnvelopesLabelsDialog:
        dlg = EnvelopesLabelsDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: doc_actions.insert_envelope(canvas, dlg.get_envelope_data()))
        return dlg

    def open_letter_wizard_dialog(self) -> LetterWizardDialog:
        dlg = LetterWizardDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: doc_actions.insert_letter(canvas, dlg.get_letter_data()))
        return dlg

    def open_autosummarize_dialog(self) -> AutoSummarizeDialog:
        dlg = AutoSummarizeDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: doc_actions.auto_summarize(canvas, dlg.get_summarize_data()))
        return dlg

    def open_hyphenation_dialog(self) -> HyphenationDialog:
        dlg = HyphenationDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.apply_hyphenation(canvas, dlg.get_hyphenation_settings())
            )
        return dlg

    def open_insert_cells_dialog(self) -> InsertCellsDialog:
        dlg = InsertCellsDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            doc_actions.table_insert_cells(canvas, dlg.get_action())
        return dlg

    def open_delete_cells_dialog(self) -> DeleteCellsDialog:
        dlg = DeleteCellsDialog(self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            doc_actions.table_delete_cells(canvas, dlg.get_action())
        return dlg

    def open_split_cells_dialog(self) -> SplitCellsDialog:
        dlg = SplitCellsDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_split_cells(dlg.get_dimensions())
        return dlg

    def open_table_autoformat_dialog(self) -> TableAutoFormatDialog:
        dlg = TableAutoFormatDialog(parent=self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(
                lambda: doc_actions.table_autoformat(canvas, dlg.get_format_settings())
            )
        return dlg

    def open_table_sort_dialog(self) -> TableSortDialog:
        dlg = TableSortDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_table_sort(dlg.get_sort_criteria())
        return dlg

    def open_table_formula_dialog(self) -> TableFormulaDialog:
        dlg = TableFormulaDialog(parent=self)
        canvas = self.writer_view.canvas_view
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_dialog(lambda: doc_actions.table_formula(canvas, *dlg.get_formula_data()))
        return dlg

    def _ensure_find_replace_dialog(self) -> FindReplaceDialog:
        """Create or return existing FindReplaceDialog instance."""
        if self._find_replace_dialog is None:
            self._find_replace_dialog = FindReplaceDialog(
                controller=self.search_controller, parent=self
            )
        return self._find_replace_dialog

    def open_find_dialog(self) -> None:
        """Display the Find and Replace dialog on Find tab."""
        dlg = self._ensure_find_replace_dialog()
        dlg.show_find()

    def open_replace_dialog(self) -> None:
        """Display the Find and Replace dialog on Replace tab."""
        dlg = self._ensure_find_replace_dialog()
        dlg.show_replace()

    def _on_document_modified(self) -> None:
        """Mark document as modified when content edits occur."""
        self._doc_revision = getattr(self, "_doc_revision", 0) + 1
        self.set_modified(True)

    @property
    def default_doc_name(self) -> str:
        """Default document name for Quire documents."""
        return safe_tr("未命名文档")

    def update_window_title(self) -> None:
        """Set window title according to active document and dirty flag."""
        if self.current_file_path is not None:
            doc_name = self.current_file_path.name
        elif getattr(self, "active_template", None) is not None:
            tag = safe_tr("基于模板")
            doc_name = f"{self.default_doc_name} [{tag}: {self.active_template.name}]"
        else:
            doc_name = self.default_doc_name
        self.setWindowTitle(f"{doc_name} — {self.app_name} [*]")

    def get_file_filter(self) -> str:
        """Return file filter pattern for Quire save/open dialogs."""
        return safe_tr(
            "所有支持的格式 (*.docx *.docm *.dotx *.html *.htm *.rtf *.md *.markdown *.txt);;"
            "Word 文档 (*.docx *.docm *.dotx);;"
            "HTML 网页 (*.html *.htm);;"
            "富文本格式 (*.rtf);;"
            "Markdown 文档 (*.md *.markdown);;"
            "纯文本文件 (*.txt);;"
            "Word 97-2003 文档 (*.doc *.dot);;"
            "所有文件 (*.*)"
        )

    def _apply_template_result(self, result: Any) -> None:
        """Apply generated template Document model to Quire canvas."""
        if result is not None:
            from atboffice.modules.writer.models.document import Document

            if isinstance(result, Document):
                self.writer_view.canvas_view.set_document(result)

    def new_file(self) -> bool:
        """Create a new untitled blank document on canvas."""
        if not super().new_file():
            return False
        from atboffice.modules.writer.models.document import Document

        self.writer_view.canvas_view.set_document(Document())
        return True

    def do_save(self, path: Path) -> bool:
        """Serialize Quire document to destination path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower()
        if ext in {".doc", ".dot"}:
            return False
        if ext in {".html", ".htm"}:
            from atboffice.modules.writer.io.html_io import write_html

            write_html(self.writer_view.canvas_view.doc, path)
            return True
        doc = self.writer_view.canvas_view.doc
        if ext in {".docx", ".docm", ".dotx"}:
            from atboffice.modules.writer.io.docx_writer import write_docx

            if not self.confirm_compatibility_losses(getattr(doc, "losses", None)):
                return False
            write_docx(doc, path)
            return True
        if ext == ".rtf":
            from atboffice.modules.writer.io.rtf_io import write_rtf

            path.write_bytes(write_rtf(doc))
            return True
        if ext in {".md", ".markdown"}:
            from atboffice.modules.writer.io.markdown_io import write_markdown

            md_text, _images = write_markdown(doc)
            path.write_text(md_text, encoding="utf-8")
            return True
        if ext == ".zip":
            from atboffice.modules.writer.io.markdown_io import write_markdown_zip

            path.write_bytes(write_markdown_zip(doc))
            return True
        if ext == ".txt":
            path.write_text(_document_plain_text(doc), encoding="utf-8")
            return True
        raise UnsupportedSaveFormatError(ext)

    def do_open(self, path: Path) -> bool:
        """Parse and load Quire document from disk with transactional rollback."""
        if path.stat().st_size == 0:
            from atboffice.modules.writer.models.document import Document, Paragraph

            candidate_doc = Document()
            candidate_doc.main.blocks.append(Paragraph())
            self.writer_view.canvas_view.set_document(candidate_doc)
            return True

        ext = path.suffix.lower()

        is_xml_or_html = False
        is_rtf_header = False
        try:
            with open(path, "rb") as f:
                raw_lead = f.read(64)
                if raw_lead.startswith(b"\xef\xbb\xbf"):
                    raw_lead = raw_lead[3:]
                lead = raw_lead.lstrip()
                if lead.startswith((b"<", b"\xff\xfe<\x00", b"\xfe\xff\x00<")):
                    is_xml_or_html = True
                elif lead.startswith(b"{\\rtf"):
                    is_rtf_header = True
        except Exception:
            pass

        # 1. Check if legacy or disguised binary document
        self.check_legacy_or_disguised_file(path, "quire")

        # 2. Check for encrypted package
        decrypted_bytes, is_enc = self.try_decrypt_if_encrypted(path)

        # 3. Parse candidate document
        candidate_doc = None
        if ext in {".html", ".htm"} or (ext in {".doc", ".dot", ".xml"} and is_xml_or_html):
            from atboffice.modules.writer.io.html_io import read_html

            candidate_doc = read_html(path)
        elif ext == ".rtf" or (ext in {".doc", ".dot"} and is_rtf_header):
            from atboffice.modules.writer.io.rtf_io import RtfReader

            candidate_doc = RtfReader().read(path.read_bytes())
        elif ext in {".md", ".markdown"}:
            from atboffice.modules.writer.io.markdown_io import MarkdownReader

            candidate_doc = MarkdownReader().read(path.read_text(encoding="utf-8"))
        elif ext == ".txt":
            from atboffice.modules.writer.models.document import (
                Document,
                Paragraph,
                Story,
                TextItem,
            )

            candidate_doc = Document()
            candidate_doc.main = Story(kind="main", blocks=[])
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not lines:
                lines = [""]
            for line in lines:
                p = Paragraph()
                p.runs.append(TextItem(text=line))
                candidate_doc.main.blocks.append(p)
        elif ext in {".docx", ".docm", ".dotx"} or is_enc:
            from atboffice.modules.writer.io.docx_reader import read_docx

            source = decrypted_bytes if is_enc and decrypted_bytes is not None else path
            candidate_doc = read_docx(source)
        else:
            return False

        if candidate_doc is None:
            return False

        # 4. Transactional UI binding with rollback
        old_doc = self.writer_view.canvas_view.doc
        try:
            self.writer_view.canvas_view.set_document(candidate_doc)
            if hasattr(self, "nav_dock") and self.nav_dock is not None:
                self.nav_dock.set_document(candidate_doc)
        except Exception as bind_err:
            try:
                self.writer_view.canvas_view.set_document(old_doc)
                if hasattr(self, "nav_dock") and self.nav_dock is not None:
                    self.nav_dock.set_document(old_doc)
            except Exception:
                pass
            raise bind_err

        return True

    def _setup_toolbars(self) -> None:
        """Initialize Word 2003 Luna 10 toolbars cluster."""
        self.toolbars: dict[str, OfficeToolBar] = build_quire_toolbars(self, self.action_registry)

        # Row 1: Standard toolbar
        if "standard" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["standard"])

        # Row 2: Formatting toolbar
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        if "formatting" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["formatting"])

        # Row 3: Drawing toolbar and contextual toolbars
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        if "drawing" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["drawing"])

        for name in [
            "tables",
            "reviewing",
            "outlining",
            "headerFooter",
            "picture",
            "mailMerge",
            "wordart",
        ]:
            if name in self.toolbars:
                self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars[name])

        # Backward compatibility aliases
        self.toolbar_standard = self.toolbars["standard"]
        self.toolbar_formatting = self.toolbars["formatting"]
        self.act_bold = self.action_registry.get_action("bold")
        self.act_italic = self.action_registry.get_action("italic")
        self.act_underline = self.action_registry.get_action("underline")

        # Color picker compatibility references
        for cp in self.toolbars["formatting"].findChildren(ColorPickerButton):
            if cp.mode == "font":
                self.btn_font_color = cp
            elif cp.mode in ("highlight", "fill"):
                self.btn_highlight_color = cp

        # Default display modes for all 10 toolbars
        self.toolbar_modes: dict[str, bool | str] = {
            "standard": True,
            "formatting": True,
            "drawing": True,
            "tables": "auto",
            "reviewing": "auto",
            "picture": "auto",
            "outlining": "auto",
            "headerFooter": "auto",
            "mailMerge": False,
            "wordart": "auto",
        }

        # Apply initial contextual visibility
        self.update_context_toolbars({})

        # Wire special widgets (combos, color pickers, dropdown menus)
        self._wire_toolbar_widgets()

    def _wire_toolbar_widgets(self) -> None:
        """Connect toolbar combo boxes, color pickers, and menus to canvas."""
        canvas = self.writer_view.canvas_view

        # Formatting toolbar widgets
        fmt_tb = self.toolbars.get("formatting")
        if fmt_tb:
            font_combo = fmt_tb.findChild(QComboBox, "Quire_FontCombo")
            if font_combo:
                self.font_combo = font_combo
                font_combo.currentTextChanged.connect(self._on_font_combo_changed)

            size_combo = fmt_tb.findChild(QComboBox, "Quire_SizeCombo")
            if size_combo:
                self.size_combo = size_combo
                size_combo.currentTextChanged.connect(self._on_size_combo_changed)

            style_combo = fmt_tb.findChild(QComboBox, "Quire_StyleCombo")
            if style_combo:
                self.style_combo = style_combo
                style_combo.currentTextChanged.connect(self._on_style_combo_changed)

        # Standard toolbar zoom combo
        std_tb = self.toolbars.get("standard")
        if std_tb:
            zoom_combo = std_tb.findChild(QComboBox, "Quire_ZoomCombo")
            if zoom_combo:
                self.zoom_combo = zoom_combo
                zoom_combo.currentTextChanged.connect(self._on_zoom_combo_changed)

        # Outline toolbar level combo
        ol_tb = self.toolbars.get("outlining")
        if ol_tb:
            ol_combo = ol_tb.findChild(QComboBox, "Quire_OutlineLevelCombo")
            if ol_combo:
                self.outline_level_combo = ol_combo
                ol_combo.currentIndexChanged.connect(self._on_outline_combo_changed)

        # Color pickers
        if hasattr(self, "btn_font_color"):
            self.btn_font_color.color_applied.connect(canvas.set_font_color)
        if hasattr(self, "btn_highlight_color"):
            self.btn_highlight_color.color_applied.connect(canvas.set_highlight_color)

    def _on_font_combo_changed(self, text: str) -> None:
        if self._syncing_toolbars or not text:
            return
        self.writer_view.canvas_view.set_font_family(text.strip())

    def _on_size_combo_changed(self, text: str) -> None:
        if self._syncing_toolbars or not text:
            return
        pt_map = {
            "初号": 42.0,
            "小初": 36.0,
            "一号": 26.0,
            "小一": 24.0,
            "二号": 22.0,
            "小二": 18.0,
            "三号": 16.0,
            "小三": 15.0,
            "四号": 14.0,
            "小四": 12.0,
            "五号": 10.5,
            "小五": 9.0,
        }
        val = pt_map.get(text.strip())
        if val is None:
            try:
                val = float(text.replace("pt", "").strip())
            except ValueError:
                return
        self.writer_view.canvas_view.set_font_size(val)

    def _on_style_combo_changed(self, text: str) -> None:
        if self._syncing_toolbars or not text:
            return
        style_ids = {
            safe_tr("正文"): "Normal", safe_tr("标题 1"): "Heading1",
            safe_tr("标题 2"): "Heading2", safe_tr("标题 3"): "Heading3",
            safe_tr("副标题"): "Subtitle", safe_tr("页眉"): "Header", safe_tr("页脚"): "Footer",
        }
        style_id = style_ids.get(text)
        if style_id is None:
            return
        canvas = self.writer_view.canvas_view
        self._apply_dialog(lambda: canvas.apply_style(style_id))

    def _on_zoom_combo_changed(self, text: str) -> None:
        if self._syncing_toolbars or not text:
            return
        canvas = self.writer_view.canvas_view
        if text in (safe_tr("页宽"), safe_tr("整页")):
            pages = getattr(canvas.pagination, "pages", None) or []
            if not pages:
                return
            page = pages[0]
            vp = canvas.viewport()
            ratio = canvas.pt_to_px_ratio
            fit_w = (vp.width() - 48) / max(1.0, page.width * ratio)
            if text == safe_tr("页宽"):
                canvas.set_zoom(fit_w)
            else:
                fit_h = (vp.height() - 40) / max(1.0, page.height * ratio)
                canvas.set_zoom(min(fit_w, fit_h))
            return
        clean = text.replace("%", "").strip()
        try:
            val = float(clean) / 100.0
            canvas.set_zoom(val)
        except ValueError:
            pass

    def _on_outline_combo_changed(self, index: int) -> None:
        if self._syncing_toolbars:
            return
        if 0 <= index < 9:
            self.writer_view.canvas_view.set_outline_level(index + 1)
        else:
            self.writer_view.canvas_view.set_outline_level(None)

    def _toggle_tables_toolbar(self) -> None:
        curr = self.toolbars["tables"].isVisible()
        self.set_toolbar_mode("tables", not curr)

    def _toggle_drawing_toolbar(self) -> None:
        curr = self.toolbars["drawing"].isVisible()
        self.set_toolbar_mode("drawing", not curr)

    def set_toolbar_mode(self, name: str, mode: bool | str) -> None:
        """Set toolbar visibility mode: True, False, or 'auto'."""
        self.toolbar_modes[name] = mode
        if isinstance(mode, bool) and name in self.toolbars:
            self.toolbars[name].setVisible(mode)

    def update_context_toolbars(self, context: dict[str, Any] | None = None) -> None:
        """Update contextual toolbar visibility based on selection and document state.

        Context keys persist between calls (e.g. header/footer editing stays on while
        the caret moves) until a later call changes them.
        """
        ctx = {**getattr(self, "_toolbar_context", {}), **(context or {})}
        self._toolbar_context = ctx
        for name, mode in self.toolbar_modes.items():
            tb = self.toolbars.get(name)
            if tb is None:
                continue

            if mode is True:
                target_visible = True
            elif mode is False:
                target_visible = False
            else:  # "auto"
                if name == "tables":
                    target_visible = bool(ctx.get("in_table"))
                elif name == "picture":
                    target_visible = bool(ctx.get("is_picture"))
                elif name == "wordart":
                    target_visible = bool(ctx.get("is_wordart"))
                elif name == "outlining":
                    target_visible = ctx.get("view") == "outline"
                elif name == "headerFooter":
                    target_visible = bool(ctx.get("hf_edit"))
                elif name == "reviewing":
                    target_visible = bool(ctx.get("has_revisions") or ctx.get("track_changes"))
                else:
                    target_visible = False

            tb.setVisible(target_visible)

    def _schedule_caret_ui_sync(self, *_: Any) -> None:
        """Queue one caret-driven UI refresh (toolbars, context bars, side panes)."""
        timer = getattr(self, "_caret_ui_timer", None)
        if timer is None:
            self._flush_caret_ui_sync()
            return
        timer.start()

    def _flush_caret_ui_sync(self) -> None:
        """Run the queued caret-driven UI refresh for the current caret position."""
        if getattr(self, "_is_closed", False):
            return
        controller = self.writer_view.canvas_view.controller
        if self._caret_sync_key() == getattr(self, "_last_caret_sync_key", None):
            return  # the caret refresh in this keystroke already covered this state
        pos = controller.pos
        self._on_caret_moved(pos.para_id, pos.offset)

    def _end_caret_sync_turn(self) -> None:
        self._caret_sync_in_turn = False

    def _caret_sync_key(self) -> tuple[Any, ...]:
        controller = self.writer_view.canvas_view.controller
        sel = controller.selection
        return (
            getattr(self, "_doc_revision", 0),
            controller.pos.para_id,
            controller.pos.offset,
            getattr(sel.anchor, "para_id", None),
            getattr(sel.anchor, "offset", None),
            getattr(sel.focus, "para_id", None),
            getattr(sel.focus, "offset", None),
        )

    def _on_caret_moved(self, para_id: int, offset: int) -> None:
        """Handle caret movement: sync toolbar controls and contextual visibility."""
        timer = getattr(self, "_caret_ui_timer", None)
        if timer is not None:
            timer.stop()  # this refresh supersedes any queued selection refresh
        # One edit emits caret_changed several times (repaginate + blink reset);
        # identical refreshes within the same event-loop turn are skipped.
        key = self._caret_sync_key()
        if key == getattr(self, "_last_caret_sync_key", None) and getattr(
            self, "_caret_sync_in_turn", False
        ):
            return
        self._last_caret_sync_key = key
        if not getattr(self, "_caret_sync_in_turn", False):
            self._caret_sync_in_turn = True
            QTimer.singleShot(0, self, self._end_caret_sync_turn)
        canvas = self.writer_view.canvas_view
        in_table = canvas.get_current_table_context() is not None
        has_revisions = bool(getattr(canvas.doc, "comments", [])) or is_tracking(canvas.doc)
        self.update_context_toolbars(
            {
                "in_table": in_table,
                "has_revisions": has_revisions,
                "track_changes": is_tracking(canvas.doc),
            }
        )
        if hasattr(self, "nav_dock") and self.nav_dock.isVisible():
            p = canvas.controller._paragraph_by_id(para_id)
            self.nav_dock.doc_map_pane.sync_caret_para(p)
        if hasattr(self, "styles_pane"):
            self.styles_pane.update_current_style(canvas.get_current_style_id())
        self._sync_toolbar_states()

    def _setup_quire_task_panes(self) -> None:
        """Register Quire specific task panes (Styles and Formatting)."""
        if not self.task_pane_dock:
            return

        from atboffice.modules.writer.panes import StylesAndFormattingPane

        doc = getattr(self.writer_view.canvas_view, "doc", None)
        self.styles_pane = StylesAndFormattingPane(doc=doc, parent=self.task_pane_dock)
        self.styles_pane.apply_style_requested.connect(
            self.writer_view.canvas_view.apply_style
        )
        self.styles_pane.clear_formatting_requested.connect(
            self.writer_view.canvas_view.clear_formatting
        )

        self.task_pane_dock.register_pane(
            "styles",
            safe_tr("样式与格式"),
            self.styles_pane,
        )

    def switch_view_mode(self, mode: ViewMode | str) -> None:
        """Switch Quire view display mode (print, normal, web, reading, outline)."""
        if isinstance(mode, str):
            mode = ViewMode(mode)
        self.writer_view.set_view_mode(mode)
        self._sync_toolbar_states()

    def toggle_document_map(self) -> None:
        """Toggle left Document Map navigation pane."""
        if self.nav_dock.isVisible() and self.nav_dock.active_mode() == "doc_map":
            self.nav_dock.hide()
        else:
            self.nav_dock.show_document_map()
        self._sync_toolbar_states()

    def toggle_thumbnails(self) -> None:
        """Toggle left Thumbnails navigation pane."""
        if self.nav_dock.isVisible() and self.nav_dock.active_mode() == "thumbnails":
            self.nav_dock.hide()
        else:
            self.nav_dock.show_thumbnails()
        self._sync_toolbar_states()

    def toggle_rulers(self) -> None:
        """Toggle rulers visibility."""
        vis = not self.writer_view.h_ruler.isVisible()
        self.writer_view.set_ruler_visible(vis)
        self._sync_toolbar_states()

    def toggle_fullscreen(self) -> None:
        """Toggle Full Screen mode."""
        if self._is_fullscreen_mode:
            self.exit_full_screen()
        else:
            self.enter_full_screen()

    def enter_full_screen(self) -> None:
        """Enter full screen view: hide chrome and show floating toolbar."""
        if self._is_fullscreen_mode:
            return
        self._is_fullscreen_mode = True
        self._prev_view_mode = self.writer_view.view_mode

        self._saved_toolbars_visible = []
        for tb in self.findChildren(OfficeToolBar):
            self._saved_toolbars_visible.append((tb, tb.isVisible()))
            tb.hide()

        if self.menuBar():
            self.menuBar().hide()
        if self.statusBar():
            self.statusBar().hide()

        self.showFullScreen()

        self.fullscreen_bar.show()
        self.fullscreen_bar.raise_()
        self._reposition_fullscreen_bar()
        self._sync_toolbar_states()

    def exit_full_screen(self) -> None:
        """Exit full screen mode and restore menus and toolbars."""
        if not self._is_fullscreen_mode:
            return
        self._is_fullscreen_mode = False
        self.fullscreen_bar.hide()

        if self.menuBar():
            self.menuBar().show()
        if self.statusBar():
            self.statusBar().show()

        for tb, was_vis in self._saved_toolbars_visible:
            tb.setVisible(was_vis)
        self._saved_toolbars_visible.clear()

        self.showNormal()
        self.switch_view_mode(self._prev_view_mode)

    def _reposition_fullscreen_bar(self) -> None:
        if self.fullscreen_bar.isVisible():
            geo = self.geometry()
            self.fullscreen_bar.move(geo.right() - self.fullscreen_bar.width() - 40, geo.top() + 40)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_is_fullscreen_mode") and self._is_fullscreen_mode:
            self._reposition_fullscreen_bar()

    def keyPressEvent(self, event: Any) -> None:
        if getattr(self, "_is_fullscreen_mode", False) and event.key() == Qt.Key.Key_Escape:
            self.exit_full_screen()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_view_mode_changed(self, mode: ViewMode) -> None:
        self._sync_toolbar_states()

    def _on_nav_dock_visibility_changed(self, visible: bool) -> None:
        self._sync_toolbar_states()

    def show_status_message(self, message: str, timeout: int = 2000) -> None:
        """Show message on status bar."""
        sb = self.statusBar()
        if sb:
            sb.showMessage(message, timeout)

    def reorder_selected_object(self, direction: str) -> None:
        """Reorder selected drawing object ('front' or 'back')."""
        canvas = self.writer_view.canvas_view
        if hasattr(canvas, "reorder_selected_object"):
            canvas.reorder_selected_object(direction)
        self.show_status_message(safe_tr(f"已调整对象叠放次序: {direction}"))

    def nudge_selected_object(self, dx: int, dy: int) -> None:
        """Nudge selected drawing object by (dx, dy) pixels."""
        canvas = self.writer_view.canvas_view
        if hasattr(canvas, "nudge_selected_object"):
            canvas.nudge_selected_object(dx, dy)
        self.show_status_message(safe_tr("微移对象"))

    def align_selected_objects(self, alignment: str) -> None:
        """Align selected drawing objects ('left', 'center', 'right', 'top', etc.)."""
        canvas = self.writer_view.canvas_view
        if hasattr(canvas, "align_selected_objects"):
            canvas.align_selected_objects(alignment)
        self.show_status_message(safe_tr(f"对齐对象: {alignment}"))

    def rotate_selected_object(self, angle: float) -> None:
        """Rotate selected drawing object by angle in degrees."""
        canvas = self.writer_view.canvas_view
        if hasattr(canvas, "rotate_selected_object"):
            canvas.rotate_selected_object(angle)
        self.show_status_message(safe_tr(f"旋转对象: {angle}°"))

    def insert_shape(self, shape_type: str) -> None:
        """Insert or activate shape drawing mode ('line', 'basic', 'arrow', etc.)."""
        canvas = self.writer_view.canvas_view
        if hasattr(canvas, "insert_shape"):
            canvas.insert_shape(shape_type)
        self.show_status_message(safe_tr(f"插入自选图形: {shape_type}"))

    def apply_border_preset(self, preset: str) -> None:
        """Apply border preset ('none', 'all', 'outside', 'bottom', 'top', 'left', 'right')."""
        canvas = self.writer_view.canvas_view
        ctx = canvas.get_current_table_context()
        if ctx is not None:
            self.apply_table_border(preset)
            return

        from atboffice.modules.writer.models.properties import BorderProperties

        sides = {
            "none": (),
            "all": ("top", "left", "bottom", "right", "between"),
            "outside": ("top", "left", "bottom", "right"),
            "top": ("top",), "bottom": ("bottom",), "left": ("left",), "right": ("right",),
            "inside": ("between",),
        }.get(preset)
        if sides is None:
            return

        def apply() -> None:
            for para in self._selected_paragraphs():
                if preset == "none":
                    para.p_pr.borders = {}
                    continue
                borders = dict(para.p_pr.borders) if preset not in ("all", "outside") else {}
                for side in sides:
                    borders[side] = BorderProperties(val="single", sz=0.5, color="auto")
                para.p_pr.borders = borders

        self._apply_dialog(apply)
        self.show_status_message(safe_tr("已应用边框"))

    def apply_table_border(self, border_type: str) -> None:
        """Apply border styling to active table."""
        canvas = self.writer_view.canvas_view
        ctx = canvas.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        if hasattr(tbl, "tbl_pr") and tbl.tbl_pr:
            tbl.tbl_pr.borders = {"type": border_type}
        canvas.controller.document_modified.emit()
        canvas.update()
        self.show_status_message(safe_tr(f"应用表格边框: {border_type}"))

    def set_table_cell_valign(self, align: str) -> None:
        """Set vertical alignment of current table cell ('top', 'center', 'bottom')."""
        canvas = self.writer_view.canvas_view
        ctx = canvas.get_current_table_context()
        if not ctx:
            return
        row_idx = ctx["row_idx"]
        col_idx = ctx["col_idx"]
        cell = ctx["tbl"].rows[row_idx].cells[col_idx]
        if hasattr(cell, "tc_pr") and cell.tc_pr:
            cell.tc_pr.valign = align
        canvas.controller.document_modified.emit()
        canvas.update()
        self.show_status_message(safe_tr(f"单元格对齐: {align}"))

    def _sync_toolbar_states(self) -> None:
        """Synchronize toolbar toggle buttons and combos with current selection/caret formatting."""
        if not hasattr(self, "writer_view") or not hasattr(self, "action_registry"):
            return

        self._syncing_toolbars = True
        try:
            canvas = self.writer_view.canvas_view
            pos = canvas.controller.pos
            p = canvas.controller._paragraph_by_id(pos.para_id)
            if not p:
                return

            r_pr = p.r_pr
            if p.runs:
                cur_off = 0
                for r in p.runs:
                    r_len = ilen(r)
                    if cur_off <= pos.offset <= cur_off + r_len:
                        if r.r_pr:
                            r_pr = r.r_pr
                        break
                    cur_off += r_len

            # 1. Bold, Italic, Underline
            act_b = self.action_registry.get_action("bold")
            if act_b:
                act_b.setChecked(bool(r_pr and r_pr.b))

            act_i = self.action_registry.get_action("italic")
            if act_i:
                act_i.setChecked(bool(r_pr and r_pr.i))

            act_u = self.action_registry.get_action("underline")
            if act_u:
                act_u.setChecked(bool(r_pr and r_pr.u and r_pr.u != "none"))

            # 2. Paragraph alignment
            jc = p.p_pr.jc if p.p_pr and p.p_pr.jc else "left"
            for aid, target_jc in [
                ("alignLeft", "left"),
                ("alignCenter", "center"),
                ("alignRight", "right"),
                ("justify", "both"),
            ]:
                act = self.action_registry.get_action(aid)
                if act:
                    act.setChecked(jc == target_jc)

            # 3. Lists
            has_num = p.p_pr and p.p_pr.num is not None
            num_id = p.p_pr.num.id if has_num else None
            act_bullets = self.action_registry.get_action("bullets")
            if act_bullets:
                act_bullets.setChecked(num_id == "1")

            act_numbering = self.action_registry.get_action("numbering")
            if act_numbering:
                act_numbering.setChecked(num_id == "2")

            # 4. Track changes
            act_tc = self.action_registry.get_action("trackChanges")
            if act_tc:
                act_tc.setChecked(is_tracking(canvas.doc))

            # 5. Combos sync
            if hasattr(self, "font_combo") and r_pr and r_pr.font:
                self.font_combo.blockSignals(True)
                self.font_combo.setCurrentText(r_pr.font)
                self.font_combo.blockSignals(False)

            if hasattr(self, "size_combo") and r_pr and r_pr.sz:
                self.size_combo.blockSignals(True)
                sz_str = f"{r_pr.sz:g}"
                rev_map = {10.5: "五号", 12.0: "小四", 14.0: "四号", 16.0: "三号"}
                self.size_combo.setCurrentText(rev_map.get(r_pr.sz, sz_str))
                self.size_combo.blockSignals(False)

            # 6. Contextual enable/disable for Table actions
            table_actions = [
                "mergeCells",
                "splitCells",
                "distRows",
                "distCols",
                "sortAsc",
                "sortDesc",
                "autoSum",
                "tbl_insert_col_left",
                "tbl_insert_col_right",
                "tbl_insert_row_above",
                "tbl_insert_row_below",
                "tbl_align_top",
                "tbl_align_center",
                "tbl_align_bottom",
                "tableBorderBtn",
            ]
            in_table = canvas.get_current_table_context() is not None
            for aid in table_actions:
                act = self.action_registry.get_action(aid)
                if act:
                    act.setEnabled(in_table)

            # 7. Contextual enable/disable for Review actions
            has_revisions = bool(getattr(canvas.doc, "comments", [])) or is_tracking(canvas.doc)
            for aid in [
                "acceptChange",
                "rejectChange",
                "rev_accept_selected",
                "rev_accept_all",
                "rev_reject_selected",
                "rev_reject_all",
            ]:
                act = self.action_registry.get_action(aid)
                if act:
                    act.setEnabled(has_revisions)

            # 8. View modes radio sync
            vm = self.writer_view.view_mode
            for act_name, target_vm in [
                ("view_normal", ViewMode.NORMAL),
                ("view_web", ViewMode.WEB),
                ("view_print", ViewMode.PRINT),
                ("view_reading", ViewMode.READING),
                ("view_outline", ViewMode.OUTLINE),
            ]:
                act = self.action_registry.get_action(act_name)
                if act:
                    act.setChecked(vm == target_vm)

            # 9. Document map, thumbnails, and ruler sync
            act_dm = self.action_registry.get_action("view_doc_map")
            if act_dm and hasattr(self, "nav_dock"):
                is_dm = self.nav_dock.isVisible() and self.nav_dock.active_mode() == "doc_map"
                act_dm.setChecked(is_dm)

            act_th = self.action_registry.get_action("view_thumbnails")
            if act_th and hasattr(self, "nav_dock"):
                is_th = self.nav_dock.isVisible() and self.nav_dock.active_mode() == "thumbnails"
                act_th.setChecked(is_th)

            act_ruler = self.action_registry.get_action("view_ruler")
            if act_ruler:
                act_ruler.setChecked(self.writer_view.h_ruler.isVisible())
        finally:
            self._syncing_toolbars = False

    def _toggle_bold(self) -> None:
        """Toggle bold formatting on selection."""
        self.writer_view.canvas_view.toggle_character_format("bold")
        self._sync_toolbar_states()

    def _toggle_italic(self) -> None:
        """Toggle italic formatting on selection."""
        self.writer_view.canvas_view.toggle_character_format("italic")
        self._sync_toolbar_states()

    def _toggle_underline(self) -> None:
        """Toggle underline formatting on selection."""
        self.writer_view.canvas_view.toggle_character_format("underline")
        self._sync_toolbar_states()

    def zoom_in(self) -> None:
        """Zoom in document canvas."""
        self.writer_view.canvas_view.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out document canvas."""
        self.writer_view.canvas_view.zoom_out()

    def zoom_reset(self) -> None:
        """Reset document zoom level to 100%."""
        self.writer_view.canvas_view.set_zoom(1.0)

    def render_to_printer(self, printer: QPrinter) -> None:
        """Render paginated Quire document in full vector fidelity onto target printer."""
        canvas = self.writer_view.canvas_view
        if not canvas.pagination or not canvas.pagination.pages:
            canvas.pagination = paginate_document(canvas.doc)

        pages = canvas.pagination.pages
        if not pages:
            return

        from atboffice.ui.printing.printer_setup import (
            begin_points_painter,
            configure_page,
            new_page,
        )

        # Each page keeps its section's own paper size and orientation, full page.
        configure_page(printer, pages[0].width, pages[0].height)
        painter = begin_points_painter(printer)
        try:
            for p_idx, page in enumerate(pages):
                if p_idx > 0:
                    new_page(printer, page.width, page.height)
                canvas.render_page_to_painter(painter, page)
        finally:
            painter.end()

    def open_page_setup(self) -> bool:
        """File > Page Setup (also the Print Preview "Page Setup" button)."""
        self.writer_view._on_page_setup_requested()
        return True  # re-rendering the preview is cheap; always refresh

    def show_about(self) -> None:
        """Show about dialog for ATBOffice Quire."""
        QMessageBox.about(
            self,
            safe_tr("关于 ATBOffice Quire"),
            safe_tr("<h3>ATBOffice Quire</h3><p>经典 Word 2003 风格原生文字处理与排版引擎。</p>"),
        )

    def retranslate_ui(self) -> None:
        """Update localized UI strings when application language changes."""
        super().retranslate_ui()
        if hasattr(self, "toolbars"):
            retranslate_quire_toolbars(self.toolbars, safe_tr)
        if hasattr(self, "action_registry"):
            self.action_registry.retranslate_ui(safe_tr)
        if hasattr(self, "styles_pane"):
            self.styles_pane.retranslate_ui()
        if hasattr(self, "toolbar_standard"):
            self.toolbar_standard.setWindowTitle(safe_tr("常用"))
        if hasattr(self, "toolbar_formatting"):
            self.toolbar_formatting.setWindowTitle(safe_tr("格式"))
        if hasattr(self, "btn_font_color"):
            self.btn_font_color.setToolTip(safe_tr("字体颜色"))
            self.btn_font_color.setStatusTip(safe_tr("更改文本字体颜色"))
        if hasattr(self, "btn_highlight_color"):
            self.btn_highlight_color.setToolTip(safe_tr("突出显示"))
            self.btn_highlight_color.setStatusTip(safe_tr("突出显示所选文本"))
        if hasattr(self, "writer_view"):
            self.writer_view.retranslate_ui()
        if hasattr(self, "menu_bar"):
            self.menu_bar.retranslate_ui()
