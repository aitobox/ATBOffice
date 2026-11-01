"""Quire dedicated word-processing window with Word 2003 Luna menus and toolbars."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QComboBox, QMessageBox, QWidget

from atboffice.core.action_registry import ActionRegistry
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.core.search import SearchController, WriterSearchAdapter
from atboffice.modules.writer.layout.pagination import paginate_document
from atboffice.modules.writer.models.document import ilen
from atboffice.modules.writer.models.revision import is_tracking
from atboffice.modules.writer.view import WriterView
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.dialogs.find_replace_dialog import FindReplaceDialog
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu
from atboffice.ui.shell.quire_toolbars import (
    build_quire_toolbars,
    retranslate_quire_toolbars,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for QuireWindow."""
    return core_safe_tr(text)


class QuireWindow(BaseOfficeWindow):
    """Dedicated word-processing window embedding WriterView with Word 2003 styling."""

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

        # 4. Setup Office 2003 Luna toolbars
        self._setup_toolbars()
        self._bind_action_handlers()

        # 5. Connect document modifications and caret/selection to listeners
        self.writer_view.canvas_view.controller.document_modified.connect(
            self._on_document_modified
        )
        self.writer_view.canvas_view.caret_moved.connect(self._on_caret_moved)
        self.writer_view.canvas_view.controller.selection_changed.connect(
            self._sync_toolbar_states
        )

        # 6. Load file or set initial document title
        if file_path is not None:
            resolved = Path(file_path).resolve()
            self.current_file_path = resolved
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
        self.action_registry.set_handler(
            "wordCount", self.writer_view.open_word_count_dialog
        )

        # Zoom & view
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
        self.action_registry.set_handler("promoteH1", lambda: canvas.set_outline_level(1))
        self.action_registry.set_handler("promote", lambda: canvas.change_outline_level(-1))
        self.action_registry.set_handler("demote", lambda: canvas.change_outline_level(1))
        self.action_registry.set_handler("demoteBody", lambda: canvas.set_outline_level(None))
        self.action_registry.set_handler("moveUp", lambda: canvas.move_paragraph(-1))
        self.action_registry.set_handler("moveDown", lambda: canvas.move_paragraph(1))

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
        self.action_registry.set_handler(
            "tb_table_drop", lambda: canvas.insert_table(2, 2)
        )
        self.action_registry.set_handler(
            "insertTable_dialog", lambda: canvas.insert_table(2, 2)
        )
        self.action_registry.set_handler(
            "insertTable_col_left", lambda: canvas.insert_table_col(left=True)
        )
        self.action_registry.set_handler(
            "insertTable_row_above", lambda: canvas.insert_table_row(above=True)
        )
        self.action_registry.set_handler(
            "col_1",
            lambda: canvas.set_columns(1) if hasattr(canvas, "set_columns") else None,
        )
        self.action_registry.set_handler(
            "col_2",
            lambda: canvas.set_columns(2) if hasattr(canvas, "set_columns") else None,
        )
        self.action_registry.set_handler(
            "col_3",
            lambda: canvas.set_columns(3) if hasattr(canvas, "set_columns") else None,
        )

        # Formatting toolbar dropdowns and split actions
        self.action_registry.set_handler(
            "line_spacing_1_0", lambda: canvas.set_line_spacing(1.0)
        )
        self.action_registry.set_handler(
            "line_spacing_1_5", lambda: canvas.set_line_spacing(1.5)
        )
        self.action_registry.set_handler(
            "line_spacing_2_0", lambda: canvas.set_line_spacing(2.0)
        )
        self.action_registry.set_handler(
            "line_spacing_2_5", lambda: canvas.set_line_spacing(2.5)
        )
        self.action_registry.set_handler(
            "line_spacing_3_0", lambda: canvas.set_line_spacing(3.0)
        )
        self.action_registry.set_handler(
            "line_spacing_more", lambda: canvas.set_line_spacing(1.5)
        )
        self.action_registry.set_handler(
            "borderBtn", lambda: self.apply_border_preset("outside")
        )
        self.action_registry.set_handler(
            "border_none", lambda: self.apply_border_preset("none")
        )
        self.action_registry.set_handler(
            "border_all", lambda: self.apply_border_preset("all")
        )
        self.action_registry.set_handler(
            "border_outside", lambda: self.apply_border_preset("outside")
        )
        self.action_registry.set_handler(
            "border_bottom", lambda: self.apply_border_preset("bottom")
        )
        self.action_registry.set_handler(
            "border_top", lambda: self.apply_border_preset("top")
        )
        self.action_registry.set_handler(
            "border_left", lambda: self.apply_border_preset("left")
        )
        self.action_registry.set_handler(
            "border_right", lambda: self.apply_border_preset("right")
        )

        # Tables toolbar dropdowns and split actions
        self.action_registry.set_handler(
            "tbl_insert_table", lambda: canvas.insert_table(2, 2)
        )
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
        self.action_registry.set_handler(
            "tableBorderBtn", lambda: self.apply_table_border("all")
        )
        self.action_registry.set_handler(
            "tbl_border_all", lambda: self.apply_table_border("all")
        )
        self.action_registry.set_handler(
            "tbl_border_outside", lambda: self.apply_table_border("outside")
        )
        self.action_registry.set_handler(
            "tbl_border_none", lambda: self.apply_table_border("none")
        )
        self.action_registry.set_handler(
            "tbl_align_top", lambda: self.set_table_cell_valign("top")
        )
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
        self.action_registry.set_handler(
            "draw_nudge_up", lambda: self.nudge_selected_object(0, -1)
        )
        self.action_registry.set_handler(
            "draw_nudge_down", lambda: self.nudge_selected_object(0, 1)
        )
        self.action_registry.set_handler(
            "draw_align_left", lambda: self.align_selected_objects("left")
        )
        self.action_registry.set_handler(
            "draw_rotate_right", lambda: self.rotate_selected_object(90)
        )
        self.action_registry.set_handler(
            "as_lines", lambda: self.insert_shape("line")
        )
        self.action_registry.set_handler(
            "as_connectors", lambda: self.insert_shape("connector")
        )
        self.action_registry.set_handler(
            "as_basic", lambda: self.insert_shape("basic")
        )
        self.action_registry.set_handler(
            "as_arrows", lambda: self.insert_shape("arrow")
        )
        self.action_registry.set_handler(
            "as_flowchart", lambda: self.insert_shape("flowchart")
        )
        self.action_registry.set_handler(
            "as_stars", lambda: self.insert_shape("star")
        )
        self.action_registry.set_handler(
            "as_callouts", lambda: self.insert_shape("callout")
        )
        self.action_registry.set_handler(
            "drawLine", lambda: self.insert_shape("line")
        )
        self.action_registry.set_handler(
            "drawArrow", lambda: self.insert_shape("arrow")
        )
        self.action_registry.set_handler(
            "drawRect", lambda: self.insert_shape("rect")
        )
        self.action_registry.set_handler(
            "drawOval", lambda: self.insert_shape("oval")
        )
        self.action_registry.set_handler(
            "textBox", lambda: self.insert_shape("textbox")
        )

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
        self.set_modified(True)

    @property
    def default_doc_name(self) -> str:
        """Default document name for Quire documents."""
        return safe_tr("未命名文档")

    def update_window_title(self) -> None:
        """Set window title according to active document and dirty flag."""
        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else self.default_doc_name
        )
        self.setWindowTitle(f"{doc_name} — {self.app_name} [*]")

    def get_file_filter(self) -> str:
        """Return file filter pattern for Quire save/open dialogs."""
        return safe_tr(
            "所有支持的格式 (*.docx *.doc *.odt *.rtf *.txt *.html *.htm);;"
            "Word 文档 (*.docx);;"
            "Word 97-2003 文档 (*.doc);;"
            "HTML 网页 (*.html *.htm);;"
            "富文本格式 (*.rtf);;"
            "纯文本文件 (*.txt);;"
            "所有文件 (*.*)"
        )

    def do_save(self, path: Path) -> bool:
        """Serialize Quire document to destination path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower()
        if ext in {".html", ".htm"}:
            from atboffice.modules.writer.io.html_io import write_html

            write_html(self.writer_view.canvas_view.doc, path)
            return True
        if ext in {".docx", ".docm", ".dotx"}:
            from atboffice.modules.writer.io.docx_writer import write_docx

            write_docx(self.writer_view.canvas_view.doc, path)
            return True
        path.touch(exist_ok=True)
        return True

    def do_open(self, path: Path) -> bool:
        """Parse and load Quire document from disk."""
        ext = path.suffix.lower()
        if ext in {".html", ".htm"}:
            from atboffice.modules.writer.io.html_io import read_html

            doc = read_html(path)
            self.writer_view.canvas_view.doc = doc
            self.writer_view.canvas_view.update()
            return True
        if ext in {".docx", ".docm", ".dotx"}:
            from atboffice.modules.writer.io.docx_reader import read_docx

            doc = read_docx(path)
            self.writer_view.canvas_view.doc = doc
            self.writer_view.canvas_view.update()
            return True
        return True

    def _setup_toolbars(self) -> None:
        """Initialize Word 2003 Luna 10 toolbars cluster."""
        self.toolbars: dict[str, OfficeToolBar] = build_quire_toolbars(
            self, self.action_registry
        )

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
            elif cp.mode == "fill":
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
            "初号": 42.0, "小初": 36.0, "一号": 26.0, "小一": 24.0,
            "二号": 22.0, "小二": 18.0, "三号": 16.0, "小三": 15.0,
            "四号": 14.0, "小四": 12.0, "五号": 10.5, "小五": 9.0,
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
        if "1" in text:
            self.writer_view.canvas_view.set_outline_level(1)
        elif "2" in text:
            self.writer_view.canvas_view.set_outline_level(2)
        elif "3" in text:
            self.writer_view.canvas_view.set_outline_level(3)
        elif "正文" in text:
            self.writer_view.canvas_view.set_outline_level(None)

    def _on_zoom_combo_changed(self, text: str) -> None:
        if self._syncing_toolbars or not text:
            return
        clean = text.replace("%", "").strip()
        try:
            val = float(clean) / 100.0
            self.writer_view.canvas_view.set_zoom(val)
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
        """Update contextual toolbar visibility based on selection and document state."""
        ctx = context or {}
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

    def _on_caret_moved(self, para_id: int, offset: int) -> None:
        """Handle caret movement: sync toolbar controls and contextual visibility."""
        canvas = self.writer_view.canvas_view
        in_table = canvas.get_current_table_context() is not None
        has_revisions = bool(getattr(canvas.doc, "comments", [])) or is_tracking(canvas.doc)
        self.update_context_toolbars({
            "in_table": in_table,
            "has_revisions": has_revisions,
            "track_changes": is_tracking(canvas.doc),
        })
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

        pos = canvas.controller.pos
        p = canvas.controller._paragraph_by_id(pos.para_id)
        if p and p.p_pr:
            p.p_pr.borders = {"preset": preset}
            canvas.controller.document_modified.emit()
            canvas.update()
        self.show_status_message(safe_tr(f"应用边框: {preset}"))

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

        painter = QPainter(printer)
        scale = printer.resolution() / 72.0
        painter.scale(scale, scale)

        for p_idx, page in enumerate(pages):
            if p_idx > 0:
                printer.newPage()
            canvas.render_page_to_painter(painter, page)

        painter.end()

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
