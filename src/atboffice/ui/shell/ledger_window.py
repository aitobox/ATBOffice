"""Ledger dedicated spreadsheet window with Excel 2003 Luna menus, formula bar, and status bar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QComboBox, QDialog, QMessageBox, QWidget

from atboffice.core.action_registry import ActionRegistry
from atboffice.core.i18n import safe_tr
from atboffice.core.search import SearchController, SpreadsheetSearchAdapter
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.fullscreen_bar import CloseFullScreenBar
from atboffice.ui.components.status_bar import StatusBar
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.dialogs.find_replace_dialog import FindReplaceDialog
from atboffice.ui.shell.base_window import BaseOfficeWindow, UnsupportedSaveFormatError
from atboffice.ui.shell.ledger_auditing import LedgerAuditingMixin
from atboffice.ui.shell.ledger_common import (  # noqa: F401  re-exported
    _cell_edit,
)
from atboffice.ui.shell.ledger_data import LedgerDataMixin
from atboffice.ui.shell.ledger_formatting import LedgerFormattingMixin
from atboffice.ui.shell.ledger_objects import LedgerObjectsMixin
from atboffice.ui.shell.ledger_toolbars import (
    build_ledger_toolbars,
    retranslate_ledger_toolbars,
)
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu


class LedgerWindow(
    LedgerFormattingMixin,
    LedgerAuditingMixin,
    LedgerDataMixin,
    LedgerObjectsMixin,
    BaseOfficeWindow,
):
    """Dedicated spreadsheet window embedding SpreadsheetView with Excel 2003 styling."""

    recovery_suffix = ".xlsx"

    def __init__(
        self,
        file_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self.app_name = "ATBOffice Ledger"
        self.app_type = "ledger"
        super().__init__(parent)
        self.resize(1100, 720)

        # 1. Action Registry command bus
        self.action_registry = ActionRegistry(self)
        self._bind_action_handlers()

        # 2. Embed SpreadsheetView
        self.spreadsheet_view = SpreadsheetView(parent=self)
        self.setCentralWidget(self.spreadsheet_view)
        self.formula_bar = self.spreadsheet_view.formula_bar

        # Search Controller & Adapter
        self.search_controller = SearchController(self)
        self.search_adapter = SpreadsheetSearchAdapter(
            model=self.spreadsheet_view.model,
            selection=self.spreadsheet_view.selection,
            spreadsheet_view=self.spreadsheet_view,
        )
        self.search_controller.set_adapter(self.search_adapter)
        self._find_replace_dialog: FindReplaceDialog | None = None
        self._watch_window: Any | None = None

        # 3. Setup native macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        # 4. Initialize universal TaskPaneDock
        self.init_task_pane_dock(safe_tr("工作簿"))
        self._setup_ledger_task_panes()

        # 5. Setup Office 2003 Luna toolbars
        self._setup_toolbars()

        # 5.1 Full Screen Bar and View Mode State
        self.is_read_only_import: bool = False
        self._is_fullscreen_mode: bool = False
        self._prev_view_mode: str = "normal"
        self._saved_toolbars_visible: list[tuple[Any, bool]] = []
        self._saved_formula_bar_visible: bool = True
        self.fullscreen_bar = CloseFullScreenBar(parent=self)
        self.fullscreen_bar.close_full_screen_requested.connect(self.exit_full_screen)

        # 5.2 Setup AutoCalculate status bar
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        # 6. Connect spreadsheet selection and mode signals to status bar & dirty hook
        self.spreadsheet_view.selection_changed.connect(self._update_spreadsheet_status)
        self.spreadsheet_view.active_cell_changed.connect(self._update_spreadsheet_status)
        self.spreadsheet_view.editor_controller.mode_changed.connect(self.status_bar.set_mode)
        self.spreadsheet_view.editor_controller.cell_committed.connect(
            lambda *_: self.set_modified(True)
        )

        # 7. Load file or set initial document title
        if file_path is not None:
            p = Path(file_path)
            if p.exists() or p.is_symlink():
                self.open_file(p)
            else:
                self.current_file_path = p.resolve()
                self.update_window_title()
        else:
            self.update_window_title()

        # 8. Ledger menu/toolbar commands (menu ID reconciliation, Clear, Name, ...)
        from atboffice.ui.shell.ledger_commands import bind_ledger_commands

        self.ledger_commands = bind_ledger_commands(self)
        self._setup_ledger_context_pane()
        self.attach_undo_history()
        self.bind_undo_service()

        self.set_modified(False)
        self.menu_bar.retranslate_ui()
        # Menus and toolbars offer only the commands this window implements.
        self.action_registry.hide_unhandled_actions()
        if self.is_ribbon_mode():
            self._sync_theme_chrome(self.current_theme)

    def build_ribbon_spec(self) -> Any:
        """Lazily build the declarative Paper 2016 Ribbon specification for Ledger."""
        from atboffice.ui.shell.ledger_ribbon import build_ledger_ribbon_spec

        return build_ledger_ribbon_spec(self)

    def _setup_ledger_context_pane(self) -> None:
        """Register RB.follow contextual tool panes for charts, pictures, and drawings."""
        from atboffice.ui.panes.context_tools_pane import ContextToolSection, ContextToolSet

        sets = [
            ContextToolSet(
                set_id="chart",
                title="图表工具",
                sections=(
                    ContextToolSection(
                        "图表类型",
                        (
                            "chart_type_column",
                            "chart_type_line",
                            "chart_type_pie",
                            "chart_type_bar",
                        ),
                    ),
                    ContextToolSection(
                        "设计与格式",
                        ("chartWizard", "formatObject", "bringToFront", "sendToBack"),
                    ),
                ),
            ),
            ContextToolSet(
                set_id="picture",
                title="图片工具",
                sections=(
                    ContextToolSection(
                        "对象与排列",
                        ("formatObject", "bringToFront", "sendToBack", "insertPicture"),
                    ),
                ),
            ),
            ContextToolSet(
                set_id="drawing",
                title="绘图工具",
                sections=(
                    ContextToolSection("插入形状", ("insertShape", "insertTextBox")),
                    ContextToolSection(
                        "格式与排列",
                        ("formatObject", "bringToFront", "sendToBack"),
                    ),
                ),
            ),
        ]
        self.init_context_pane_follow(sets)

    def _bind_action_handlers(self) -> None:
        """Bind window callbacks to core action IDs in ActionRegistry."""
        self.action_registry.set_handler("new", self.new_file)
        self.action_registry.set_handler("open", self.open_file_dialog)
        self.action_registry.set_handler("save", self.save_file)
        self.action_registry.set_handler("properties", self.show_document_properties_dialog)
        self.action_registry.set_handler("taskPane", self.toggle_task_pane)
        self.action_registry.set_handler("watchPane", self.open_watch_pane)
        self.action_registry.set_handler("watch_window_pane", self.open_watch_pane)
        self.action_registry.set_handler("cut", self.cut)
        self.action_registry.set_handler("copy", self.copy)
        self.action_registry.set_handler("paste", self.paste)
        self.action_registry.set_handler("pasteSpecial", self.paste_special)
        self.action_registry.set_handler("undo", self.undo)
        self.action_registry.set_handler("redo", self.redo)
        self.action_registry.set_handler("bold", self._toggle_bold)
        self.action_registry.set_handler("italic", self._toggle_italic)
        self.action_registry.set_handler("underline", self._toggle_underline)
        self.action_registry.set_handler("format_cells", self.format_cells)
        self.action_registry.set_handler("find", self.open_find_dialog)
        self.action_registry.set_handler("replace", self.open_replace_dialog)
        self.action_registry.set_handler("view_normal", self.set_normal_view)
        self.action_registry.set_handler("view_page_break", self.set_page_break_view)
        self.action_registry.set_handler("view_fullscreen", self.toggle_fullscreen)

        # Standard toolbar actions
        self.action_registry.set_handler("autoSum", self.auto_sum)
        self.action_registry.set_handler("autoSum_sum", lambda: self.auto_sum("SUM"))
        self.action_registry.set_handler("autoSum_average", lambda: self.auto_sum("AVERAGE"))
        self.action_registry.set_handler("autoSum_count", lambda: self.auto_sum("COUNT"))
        self.action_registry.set_handler("autoSum_max", lambda: self.auto_sum("MAX"))
        self.action_registry.set_handler("autoSum_min", lambda: self.auto_sum("MIN"))
        self.action_registry.set_handler("autoSum_more", self.open_function_wizard)
        self.action_registry.set_handler("sortAsc", lambda: self.quick_sort(desc=False))
        self.action_registry.set_handler("sortDesc", lambda: self.quick_sort(desc=True))
        self.action_registry.set_handler("tb_drawing", self.toggle_drawing_toolbar)
        self.action_registry.set_handler("chartWizard", self.chart_wizard)
        self.action_registry.set_handler("formatPainter", self.toggle_format_painter)
        self.action_registry.set_handler("hyperlink", self.insert_hyperlink)
        self.action_registry.set_handler("print", self.print_workbook)
        self.action_registry.set_handler("printPreview", self.print_preview)
        self.action_registry.set_handler("spelling", self.check_spelling)
        self.action_registry.set_handler("help", self.show_about)

        # Formatting toolbar actions
        self.action_registry.set_handler("alignLeft", lambda: self.set_horizontal_alignment("left"))
        self.action_registry.set_handler(
            "alignCenter", lambda: self.set_horizontal_alignment("center")
        )
        self.action_registry.set_handler(
            "alignRight", lambda: self.set_horizontal_alignment("right")
        )
        self.action_registry.set_handler("mergeCenter", self.toggle_merge_and_center)
        self.action_registry.set_handler(
            "currencyStyle", lambda: self.apply_number_format("$#,##0.00")
        )
        self.action_registry.set_handler("percentStyle", lambda: self.apply_number_format("0%"))
        self.action_registry.set_handler("commaStyle", lambda: self.apply_number_format("#,##0.00"))
        self.action_registry.set_handler("incDecimal", lambda: self.change_decimal_places(1))
        self.action_registry.set_handler("decDecimal", lambda: self.change_decimal_places(-1))
        self.action_registry.set_handler("incIndent", lambda: self.change_cell_indent(1))
        self.action_registry.set_handler("decIndent", lambda: self.change_cell_indent(-1))
        self.action_registry.set_handler("bordersApply", lambda: self.apply_border_preset("all"))
        self.action_registry.set_handler(
            "border_bottom", lambda: self.apply_border_preset("bottom")
        )
        self.action_registry.set_handler("border_top", lambda: self.apply_border_preset("top"))
        self.action_registry.set_handler("border_left", lambda: self.apply_border_preset("left"))
        self.action_registry.set_handler("border_right", lambda: self.apply_border_preset("right"))
        self.action_registry.set_handler("border_none", lambda: self.apply_border_preset("none"))
        self.action_registry.set_handler("border_all", lambda: self.apply_border_preset("all"))
        self.action_registry.set_handler(
            "border_thick_box", lambda: self.apply_border_preset("thickOutline")
        )
        self.action_registry.set_handler(
            "border_bottom_double", lambda: self.apply_border_preset("bottomDouble")
        )

        # Borders toolbar actions
        self.action_registry.set_handler(
            "bordersPalette", lambda: self.apply_border_preset("outline")
        )
        self.action_registry.set_handler(
            "border_pal_none", lambda: self.apply_border_preset("none")
        )
        self.action_registry.set_handler(
            "border_pal_bottom", lambda: self.apply_border_preset("bottom")
        )
        self.action_registry.set_handler("border_pal_top", lambda: self.apply_border_preset("top"))
        self.action_registry.set_handler("border_pal_all", lambda: self.apply_border_preset("all"))
        self.action_registry.set_handler(
            "border_pal_outside", lambda: self.apply_border_preset("outline")
        )
        self.action_registry.set_handler(
            "border_pal_thick", lambda: self.apply_border_preset("thickOutline")
        )
        self.action_registry.set_handler("borderNone", lambda: self.apply_border_preset("none"))
        self.action_registry.set_handler(
            "borderOutline", lambda: self.apply_border_preset("outline")
        )
        self.action_registry.set_handler(
            "borderThickOutline", lambda: self.apply_border_preset("thickOutline")
        )
        self.action_registry.set_handler("eraseBorder", lambda: self.apply_border_preset("none"))
        self.action_registry.set_handler("border_color_auto", lambda: self.apply_border_color(None))
        self.action_registry.set_handler(
            "border_color_black", lambda: self.apply_border_color("#000000")
        )
        self.action_registry.set_handler(
            "border_color_red", lambda: self.apply_border_color("#FF0000")
        )
        self.action_registry.set_handler(
            "border_color_blue", lambda: self.apply_border_color("#0000FF")
        )
        self.action_registry.set_handler(
            "border_color_gray", lambda: self.apply_border_color("#808080")
        )

        # Auditing & Reviewing toolbar actions
        self.action_registry.set_handler("traceError", self.trace_error)
        self.action_registry.set_handler("tracePrecedents", self.trace_precedents)
        self.action_registry.set_handler("traceDependents", self.trace_dependents)
        self.action_registry.set_handler("removeArrows", self.remove_arrows)
        self.action_registry.set_handler("insertComment", self.insert_comment)
        self.action_registry.set_handler("validation", self.data_validation)
        self.action_registry.set_handler("validation_dlg", self.data_validation)
        self.action_registry.set_handler("circleInvalid", self.circle_invalid)
        self.action_registry.set_handler("clearCircles", self.clear_circles)
        self.action_registry.set_handler("watchWindow", self.watch_window)
        self.action_registry.set_handler("evaluateFormula", self.evaluate_formula)
        self.action_registry.set_handler("goalSeek", self.open_goal_seek)
        self.action_registry.set_handler("tools_goal_seek", self.open_goal_seek)
        self.action_registry.set_handler("rev_insertComment", self.insert_comment)
        self.action_registry.set_handler("showHideComment", self.show_hide_comment)
        self.action_registry.set_handler("deleteComment", self.delete_comment)
        self.action_registry.set_handler("showComments", self.toggle_show_all_comments)

        # List & Chart actions
        self.action_registry.set_handler("insertRows", self.insert_rows)
        self.action_registry.set_handler("insertCols", self.insert_columns)
        self.action_registry.set_handler("deleteRows", self.delete_rows)
        self.action_registry.set_handler("deleteCols", self.delete_columns)
        self.action_registry.set_handler(
            "sortDlg", lambda: self.spreadsheet_view.grid.open_sort_dialog()
        )
        self.action_registry.set_handler("autoFilter", self.toggle_auto_filter)
        self.action_registry.set_handler("convertToRange", self.convert_table_to_range)
        self.action_registry.set_handler("totalRow", self.toggle_total_row)
        self.action_registry.set_handler("formatObject", self.format_selected_object)
        self.action_registry.set_handler("chart_type_column", lambda: self.set_chart_type("column"))
        self.action_registry.set_handler("chart_type_line", lambda: self.set_chart_type("line"))
        self.action_registry.set_handler("chart_type_pie", lambda: self.set_chart_type("pie"))
        self.action_registry.set_handler("chart_type_bar", lambda: self.set_chart_type("bar"))
        self.action_registry.set_handler("chart_type_area", lambda: self.set_chart_type("area"))
        self.action_registry.set_handler(
            "chart_type_scatter", lambda: self.set_chart_type("scatter")
        )
        self.action_registry.set_handler("chart_type_radar", lambda: self.set_chart_type("radar"))
        self.action_registry.set_handler("data_pivottable", self.open_pivot_wizard)
        self.action_registry.set_handler("pivotTable", self.open_pivot_wizard)
        self.action_registry.set_handler("pivot_fields_pane", self.open_pivot_fields_pane)

        # Drawing toolbar actions
        self.action_registry.set_handler("bringToFront", self.bring_to_front)
        self.action_registry.set_handler("sendToBack", self.send_to_back)
        self.action_registry.set_handler("insertShape", lambda: self.insert_shape("rect"))
        self.action_registry.set_handler("insertTextBox", self.insert_textbox)
        self.action_registry.set_handler("insertPicture", self.insert_picture)
        self.action_registry.set_handler("insertWordArt", self.open_wordart_gallery)
        self.action_registry.set_handler("wordartGallery", self.open_wordart_gallery)

        # Phase 6 dialog actions
        self.action_registry.set_handler("insertChart", self.open_chart_wizard)
        self.action_registry.set_handler("insert_chart", self.open_chart_wizard)
        self.action_registry.set_handler("textToColumns", self.open_text_to_columns_wizard)
        self.action_registry.set_handler("data_text_to_columns", self.open_text_to_columns_wizard)
        self.action_registry.set_handler("subtotals", self.open_subtotal_dialog)
        self.action_registry.set_handler("data_subtotals", self.open_subtotal_dialog)
        self.action_registry.set_handler("consolidate", self.open_consolidate_dialog)
        self.action_registry.set_handler("data_consolidate", self.open_consolidate_dialog)
        self.action_registry.set_handler("scenarios", self.open_scenario_manager)
        self.action_registry.set_handler("tools_scenarios", self.open_scenario_manager)
        self.action_registry.set_handler("dataTable", self.open_data_table_dialog)
        self.action_registry.set_handler("data_table", self.open_data_table_dialog)
        self.action_registry.set_handler("protectSheet", self.open_protect_sheet_dialog)
        self.action_registry.set_handler("tools_protect_sheet", self.open_protect_sheet_dialog)
        self.action_registry.set_handler("protectWorkbook", self.open_protect_workbook_dialog)
        self.action_registry.set_handler(
            "tools_protect_workbook", self.open_protect_workbook_dialog
        )
        self.action_registry.set_handler("advancedFilter", self.open_advanced_filter_dialog)
        self.action_registry.set_handler("data_advanced_filter", self.open_advanced_filter_dialog)
        self.action_registry.set_handler("options", self.open_options_dialog)
        self.action_registry.set_handler("tools_options", self.open_options_dialog)

    def _ensure_find_replace_dialog(self) -> FindReplaceDialog:
        """Create or return existing FindReplaceDialog instance."""
        if self._find_replace_dialog is None:
            self._find_replace_dialog = FindReplaceDialog(
                controller=self.search_controller, parent=self
            )
        return self._find_replace_dialog

    def open_find_dialog(self) -> None:
        """Display the Find and Replace dialog on Find tab."""
        # Ensure adapter is pointing to the current active sheet
        self.search_adapter.model = self.spreadsheet_view.model
        self.search_adapter.selection = self.spreadsheet_view.selection
        dlg = self._ensure_find_replace_dialog()
        dlg.show_find()

    def open_replace_dialog(self) -> None:
        """Display the Find and Replace dialog on Replace tab."""
        self.search_adapter.model = self.spreadsheet_view.model
        self.search_adapter.selection = self.spreadsheet_view.selection
        dlg = self._ensure_find_replace_dialog()
        dlg.show_replace()

    def _update_spreadsheet_status(self, *_: Any) -> None:
        """Forward spreadsheet selection updates to the status bar and context toolbars."""
        self.status_bar.update_calculation(
            self.spreadsheet_view.model, self.spreadsheet_view.selection
        )
        self._sync_formatting_toolbar_states()
        self.update_context_toolbars({})

    @property
    def workbook(self) -> Any:
        """Access the active WorkbookModel bound to SpreadsheetView."""
        return getattr(self.spreadsheet_view, "workbook", None)

    @property
    def sheet_tab_bar(self) -> Any:
        """Access the bottom SheetTabBar embedded in SpreadsheetView."""
        return getattr(self.spreadsheet_view, "sheet_tab_bar", None)

    @property
    def default_doc_name(self) -> str:
        """Default document name for Ledger workbooks."""
        return safe_tr("未命名工作簿")

    def update_window_title(self) -> None:
        """Set window title according to active workbook and dirty flag."""
        if self.current_file_path is not None:
            doc_name = self.current_file_path.name
        elif getattr(self, "active_template", None) is not None:
            tag = safe_tr("基于模板")
            doc_name = f"{self.default_doc_name} [{tag}: {self.active_template.name}]"
        else:
            doc_name = self.default_doc_name
        self.setWindowTitle(f"{doc_name} — {self.app_name} [*]")

    def get_file_filter(self) -> str:
        """Return file filter pattern for Ledger save/open dialogs."""
        return safe_tr(
            "所有支持的格式 (*.xlsx *.xlsm *.xls *.xlt *.csv *.tsv *.xml *.xmlss *.html *.htm);;"
            "Excel 工作簿 (*.xlsx *.xlsm);;"
            "网页 (*.html *.htm);;"
            "CSV 逗号分隔文本 (*.csv);;"
            "TSV 制表符分隔文本 (*.tsv);;"
            "XML 电子表格 (*.xml *.xmlss);;"
            "Excel 97-2003 工作簿 (*.xls *.xlt);;"
            "所有文件 (*.*)"
        )

    def _apply_template_result(self, result: Any) -> None:
        """Apply generated template WorkbookModel to Ledger spreadsheet view."""
        if result is not None:
            from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

            if isinstance(result, WorkbookModel):
                self.spreadsheet_view.workbook = result

    def new_file(self) -> bool:
        """Create a new blank workbook document."""
        if not super().new_file():
            return False
        from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

        self.is_read_only_import = False
        self.spreadsheet_view.workbook = WorkbookModel()
        return True

    def save_file(
        self,
        file_path: str | Path | None = None,
        confirm_overwrite: bool = True,
    ) -> bool:
        """Save workbook while enforcing read-only constraint on imported .xls/.xlt files."""
        if isinstance(file_path, bool):
            file_path = None

        target = Path(file_path).resolve() if file_path is not None else self.current_file_path
        if target is not None and target.suffix.lower() in {".xls", ".xlt"}:
            QMessageBox.warning(
                self,
                safe_tr("只读导入格式"),
                safe_tr(
                    "“{name}”是旧版 Excel 97–2003 (.xls) 格式，仅支持只读导入，"
                    "不支持直接覆盖保存。\n请使用“另存为”将其保存为现代 .xlsx 格式。"
                ).format(name=target.name),
            )
            return False

        saved = super().save_file(file_path, confirm_overwrite=confirm_overwrite)
        if saved:
            self.is_read_only_import = False
        return saved

    def do_save(self, path: Path) -> bool:
        """Serialize Ledger workbook to destination path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower()
        if ext in {".xls", ".xlt"}:
            return False
        if ext in {".xlsx", ".xlsm", ".xltx"}:
            from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx

            workbook = self.spreadsheet_view.workbook
            if not self.confirm_compatibility_losses(getattr(workbook, "losses", None)):
                return False
            write_xlsx(workbook, path)
            return True
        if ext in {".csv", ".tsv"}:
            from atboffice.modules.spreadsheet.io.csv_io import write_csv

            delimiter = "\t" if ext == ".tsv" else ","
            write_csv(self.spreadsheet_view.model, path, delimiter=delimiter)
            return True
        if ext in {".xml", ".xmlss"}:
            from atboffice.modules.spreadsheet.io.xmlss_io import write_xmlss

            write_xmlss(self.spreadsheet_view.workbook, path)
            return True
        if ext in {".html", ".htm"}:
            from atboffice.modules.spreadsheet.io.html_io import write_html

            write_html(self.spreadsheet_view.workbook, path)
            return True
        raise UnsupportedSaveFormatError(ext)

    def do_open(self, path: Path) -> bool:
        """Parse and load Ledger workbook from disk with transactional rollback."""
        if path.stat().st_size == 0:
            from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
            from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

            candidate_wb = WorkbookModel(sheets=[SheetDataModel(name="Sheet1")])
            self.spreadsheet_view.workbook = candidate_wb
            self.spreadsheet_view.grid.viewport().update()
            self.is_read_only_import = False
            return True

        ext = path.suffix.lower()

        # Check if file has XML/HTML markup header (like XML Spreadsheet 2003)
        is_xml_markup = False
        try:
            with open(path, "rb") as f:
                raw_lead = f.read(64)
                if raw_lead.startswith(b"\xef\xbb\xbf"):
                    raw_lead = raw_lead[3:]
                lead = raw_lead.lstrip()
                if lead.startswith((b"<", b"\xff\xfe<\x00", b"\xfe\xff\x00<")):
                    is_xml_markup = True
        except Exception:
            pass

        from atboffice.modules.spreadsheet.io.xls_reader import is_xls_supported, read_xls
        from atboffice.ui.shell.base_window import FileOpenCancelled, FileOpenWarningHandled

        is_binary_xls = (ext in {".xls", ".xlt"}) and not is_xml_markup
        allow_excel97 = is_binary_xls and is_xls_supported()

        # 1. Check if legacy or disguised binary workbook
        self.check_legacy_or_disguised_file(path, "ledger", allow_excel97=allow_excel97)

        # 2. Check for encrypted package
        decrypted_bytes, is_enc = self.try_decrypt_if_encrypted(path)

        # 3. Parse into candidate workbook
        candidate_wb = None
        if ext in {".xlsx", ".xlsm", ".xltx"} or is_enc:
            from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx

            source = decrypted_bytes if is_enc and decrypted_bytes is not None else path
            candidate_wb = read_xlsx(source)
        elif ext in {".csv", ".tsv"}:
            from atboffice.modules.spreadsheet.io.csv_io import read_csv
            from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
            from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

            delimiter = "\t" if ext == ".tsv" else ","
            new_sheet = SheetDataModel(name=path.stem or "Sheet1")
            read_csv(path, model=new_sheet, delimiter=delimiter)
            candidate_wb = WorkbookModel(sheets=[new_sheet])
        elif ext in {".html", ".htm"}:
            from atboffice.modules.spreadsheet.io.html_io import import_table, read_html_file
            from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
            from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

            tables = read_html_file(path) or []
            sheets = []
            for n, table in enumerate(tables or [None], start=1):
                sheet = SheetDataModel(name=f"Sheet{n}")
                if table is not None:
                    import_table(sheet, table)
                sheets.append(sheet)
            candidate_wb = WorkbookModel(sheets=sheets)
        elif ext in {".xml", ".xmlss"} or (ext in {".xls", ".xlt"} and is_xml_markup):
            from atboffice.modules.spreadsheet.io.xmlss_io import read_xmlss_workbook

            candidate_wb = read_xmlss_workbook(path.read_bytes())
        elif is_binary_xls:
            if not is_xls_supported():
                self.check_legacy_or_disguised_file(path, "ledger", allow_excel97=False)
                return False
            try:
                try:
                    candidate_wb = read_xls(path)
                except PermissionError:
                    # Not openable with Excel's default password: ask for the real one.
                    pwd = self.prompt_for_package_password(path.name)
                    if pwd is None:
                        raise FileOpenCancelled("User cancelled password prompt") from None
                    candidate_wb = read_xls(path, password=pwd)
            except InterruptedError:
                self.status_bar.showMessage(safe_tr("已取消打开工作簿。"), 5000)
                return False
            except PermissionError as p_err:
                QMessageBox.warning(
                    self,
                    safe_tr("打开失败"),
                    safe_tr("密码不正确，无法打开文档。"),
                )
                raise FileOpenWarningHandled(f"Encrypted XLS workbook: {path.name}") from p_err
            except Exception as exc:
                raise ValueError(f"Corrupt or unreadable XLS workbook: {exc}") from exc
        else:
            return False

        if candidate_wb is None:
            return False

        # 4. Transactional UI binding with rollback
        old_wb = self.spreadsheet_view.workbook
        try:
            self.spreadsheet_view.workbook = candidate_wb
            self.spreadsheet_view.grid.viewport().update()
        except Exception as bind_err:
            try:
                self.spreadsheet_view.workbook = old_wb
                self.spreadsheet_view.grid.viewport().update()
            except Exception:
                pass
            raise bind_err

        self.is_read_only_import = bool(is_binary_xls)
        if is_binary_xls:
            self.status_bar.showMessage(
                safe_tr(
                    "已成功导入 Excel 97–2003 (.xls) 工作簿（只读导入模式）。"
                    "旧版格式不支持直接覆盖保存，建议另存为 .xlsx 格式。"
                ),
                10000,
            )

        return True

    def _setup_toolbars(self) -> None:
        """Initialize Excel 2003 Luna 8 toolbars cluster."""
        self.toolbars: dict[str, OfficeToolBar] = build_ledger_toolbars(self, self.action_registry)

        # Row 1: Standard toolbar
        if "standard" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["standard"])

        # Row 2: Formatting toolbar
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        if "formatting" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["formatting"])

        # Row 3: Drawing and other contextual toolbars
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        for name in [
            "drawing",
            "borders",
            "auditing",
            "reviewing",
            "list",
            "chart",
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
                self.btn_font_color.color_applied.connect(self._apply_font_color)
            elif cp.mode == "fill":
                self.btn_fill_color = cp
                self.btn_fill_color.color_applied.connect(self._apply_fill_color)

        # Connect combos on formatting toolbar
        fmt_tb = self.toolbars.get("formatting")
        if fmt_tb:
            font_combo = fmt_tb.findChild(QComboBox, "Ledger_FontCombo")
            if font_combo:
                font_combo.currentTextChanged.connect(self._apply_font_family)
            size_combo = fmt_tb.findChild(QComboBox, "Ledger_SizeCombo")
            if size_combo:
                size_combo.currentTextChanged.connect(self._apply_font_size)

        # Connect zoom combo on standard toolbar
        std_tb = self.toolbars.get("standard")
        if std_tb:
            zoom_combo = std_tb.findChild(QComboBox, "Ledger_ZoomCombo")
            if zoom_combo:
                zoom_combo.currentTextChanged.connect(self._apply_zoom)
                grid = getattr(self.spreadsheet_view, "grid", None)
                if grid is not None and hasattr(grid, "zoom_changed"):
                    # Show the active sheet's zoom (a file may open at 75%).
                    grid.zoom_changed.connect(
                        lambda z, combo=zoom_combo: self._sync_zoom_combo(combo, z)
                    )
                    self._sync_zoom_combo(zoom_combo, grid.zoom)

        # Connect drawing toolbar fill color and z-order drop actions
        draw_tb = self.toolbars.get("drawing")
        if draw_tb:
            draw_fill = draw_tb.findChild(ColorPickerButton, "Ledger_DrawFillColor")
            if draw_fill:
                draw_fill.color_applied.connect(self._apply_drawing_fill_color)

        # Connect object layer selection to context toolbars
        if hasattr(self.spreadsheet_view, "object_layer") and self.spreadsheet_view.object_layer:
            self.spreadsheet_view.object_layer.object_selected.connect(self._on_object_selected)

        # Default display modes for all 8 toolbars
        self.toolbar_modes: dict[str, bool | str] = {
            "standard": True,
            "formatting": True,
            "drawing": False,
            "borders": False,
            "auditing": False,
            "reviewing": False,
            "list": "auto",
            "chart": "auto",
        }

        # Apply initial contextual visibility
        self.update_context_toolbars({})
        act_format_obj = self.action_registry.get_action("formatObject")
        if act_format_obj:
            act_format_obj.setEnabled(False)

    def set_toolbar_mode(self, name: str, mode: bool | str) -> None:
        """Set toolbar visibility mode: True, False, or 'auto'."""
        self.toolbar_modes[name] = mode
        if isinstance(mode, bool) and name in self.toolbars:
            self.toolbars[name].setVisible(mode)

    def update_context_toolbars(self, context: dict[str, Any] | None = None) -> None:
        """Update contextual toolbar visibility based on selection and document state."""
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
                if name == "chart":
                    target_visible = bool(ctx.get("is_chart"))
                elif name == "list":
                    target_visible = bool(ctx.get("in_table"))
                else:
                    target_visible = False

            if self.is_ribbon_mode():
                self._classic_toolbar_visibility[name] = target_visible
                tb.setVisible(False)
            else:
                tb.setVisible(target_visible)

        ribbon = getattr(self, "_ribbon_bar", None)
        if ribbon is not None:
            ribbon.refresh_context()

    def show_about(self) -> None:
        """Show about dialog for ATBOffice Ledger."""
        QMessageBox.about(
            self,
            safe_tr("关于 ATBOffice Ledger"),
            safe_tr(
                "<h3>ATBOffice Ledger</h3><p>经典 Excel 2003 风格跨平台原生电子表格与计算引擎。</p>"
            ),
        )

    def _on_workbook_changed(self, wb: Any) -> None:
        """Reset or rebind Ledger task panes when workbook instance changes."""
        if hasattr(self, "watch_pane") and self.watch_pane:
            self.watch_pane.workbook = wb
            self.watch_pane.refresh_watches()
        if hasattr(self, "pivot_fields_pane") and self.pivot_fields_pane:
            self.pivot_fields_pane.bind_pivot_report(None, wb)

    def open_options_dialog(self) -> None:
        """Open Excel 2003 classic Ledger Options dialog."""
        from atboffice.modules.spreadsheet.dialogs.options_dialog import LedgerOptionsDialog

        dlg = LedgerOptionsDialog(parent=self)
        dlg.exec()

    def print_workbook(self) -> None:
        """Print current workbook sheets."""
        self.print_document()

    def print_preview(self, printer: QPrinter | None = None) -> bool:
        """Open print preview window."""
        return super().print_preview(printer)

    def render_to_printer(
        self,
        printer: QPrinter,
        repeat_header_rows: int | None = None,
        show_gridlines: bool | None = None,
    ) -> None:
        """Print / preview / PDF the active sheet using its File > Page Setup settings."""
        import dataclasses

        from atboffice.modules.spreadsheet.printing.render import render_sheet
        from atboffice.modules.spreadsheet.printing.setup import get_print_setup

        grid = self.spreadsheet_view.grid
        sheet = grid.model
        setup = dataclasses.replace(get_print_setup(sheet))
        if repeat_header_rows:
            setup.title_rows = (0, repeat_header_rows - 1)
        if show_gridlines is not None:
            setup.gridlines = show_gridlines
        path = self.current_file_path
        render_sheet(
            printer,
            grid,
            sheet,
            setup,
            file_name=path.name if path else self.default_doc_name,
            file_path=str(path) if path else "",
            show_margins=bool(getattr(self, "_preview_show_margins", False)),
        )

    def open_page_setup(self) -> bool:
        """File > Page Setup for the active sheet; returns True when settings changed."""
        from atboffice.modules.spreadsheet.dialogs.page_setup_dialog import (
            LedgerPageSetupDialog,
        )
        from atboffice.modules.spreadsheet.printing.setup import (
            get_print_setup,
            set_print_setup,
        )

        sheet = self.spreadsheet_view.grid.model
        before = get_print_setup(sheet)
        dlg = LedgerPageSetupDialog(before, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        if dlg.setup == before:
            return False
        set_print_setup(sheet, dlg.setup)
        self.set_modified(True)
        self.spreadsheet_view.grid.viewport().update()
        return True

    def print_preview_extras(self, panel: Any) -> None:
        """Excel 2003 preview buttons: Margins and Page Break Preview."""
        from PySide6.QtWidgets import QToolButton

        margins = QToolButton()
        margins.setObjectName("previewMarginsButton")
        margins.setCheckable(True)
        margins.setChecked(bool(getattr(self, "_preview_show_margins", False)))
        margins.setText(safe_tr("页边距(&M)"))
        margins.setToolTip(safe_tr("显示或隐藏页边距线"))

        def toggle_margins(checked: bool) -> None:
            self._preview_show_margins = checked
            panel.refresh()

        margins.toggled.connect(toggle_margins)
        page_break = QToolButton()
        page_break.setObjectName("previewPageBreakButton")
        page_break.setText(safe_tr("分页预览(&V)"))
        page_break.setToolTip(safe_tr("关闭打印预览并切换到分页预览"))

        def to_page_break() -> None:
            panel.close_preview()
            self.set_view_mode("page_break")

        page_break.clicked.connect(lambda _c=False: to_page_break())
        panel.add_extra_widget(margins)
        panel.add_extra_widget(page_break)

    def check_spelling(self) -> None:
        """Tools > Spelling: check worksheet text cells with the offline SpellEngine."""
        commands = getattr(self, "ledger_commands", None)
        if commands is not None:
            commands.check_spelling()

    def document_widget(self) -> QWidget | None:
        return self.spreadsheet_view.grid

    def undo_service(self) -> Any | None:
        view = getattr(self, "spreadsheet_view", None)
        grid = getattr(view, "grid", None)
        return getattr(grid, "history", None)

    def after_undo_redo(self) -> None:
        super().after_undo_redo()
        self._refresh_after_cell_edit()

    def compat_model_losses(self) -> list[Any]:
        return list(getattr(self.spreadsheet_view.workbook, "losses", None) or [])

    def save_losses(self, target: Path) -> list[Any]:
        from atboffice.core.compat import ledger_losses

        return ledger_losses(
            self.spreadsheet_view.workbook, self.spreadsheet_view.grid.model, target
        )

    def render_thumbnail(self, width: int = 240) -> Any:
        """Top-left of the active sheet (cells, fills, borders) as printed."""
        from PySide6.QtGui import QColor, QImage, QPainter

        grid = getattr(self.spreadsheet_view, "grid", None)
        if grid is None:
            return None
        geo = grid.model.geometry
        rows, cols = 24, 8
        w_px = geo.col_pos(cols) - geo.col_pos(0)
        h_px = geo.row_pos(rows) - geo.row_pos(0)
        scale = width / max(1.0, float(w_px))
        img = QImage(width, max(1, int(h_px * scale)), QImage.Format.Format_ARGB32)
        img.fill(QColor("#FFFFFF"))
        painter = QPainter(img)
        painter.scale(scale, scale)
        grid.paint_print_region(painter, 0, rows - 1, 0, cols - 1, gridlines=True)
        painter.end()
        return img

    def set_view_mode(self, mode: str, prompt_welcome: bool = False) -> None:
        """Switch spreadsheet view mode ('normal' or 'page_break')."""
        if hasattr(self, "spreadsheet_view") and hasattr(self.spreadsheet_view, "grid"):
            self.spreadsheet_view.grid.set_view_mode(mode, prompt_welcome=prompt_welcome)
        if hasattr(self, "action_registry") and self.action_registry:
            self.action_registry.set_checked("view_normal", mode == "normal")
            self.action_registry.set_checked("view_page_break", mode == "page_break")

    def set_normal_view(self) -> None:
        """Switch to Normal grid view."""
        self.set_view_mode("normal")

    def set_page_break_view(self) -> None:
        """Switch to Page Break Preview mode."""
        self.set_view_mode("page_break")

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
        self._prev_view_mode = getattr(self.spreadsheet_view, "view_mode", "normal")

        self._saved_toolbars_visible = []
        for tb in self.findChildren(OfficeToolBar):
            self._saved_toolbars_visible.append((tb, tb.isVisible()))
            tb.hide()

        if self.menuBar():
            self.menuBar().hide()
        if self.statusBar():
            self.statusBar().hide()

        if hasattr(self, "spreadsheet_view") and hasattr(self.spreadsheet_view, "formula_bar"):
            self._saved_formula_bar_visible = self.spreadsheet_view.formula_bar.isVisible()
            self.spreadsheet_view.formula_bar.hide()

        self.showFullScreen()

        self.fullscreen_bar.show()
        self.fullscreen_bar.raise_()
        self._reposition_fullscreen_bar()

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

        if hasattr(self, "spreadsheet_view") and hasattr(self.spreadsheet_view, "formula_bar"):
            self.spreadsheet_view.formula_bar.setVisible(self._saved_formula_bar_visible)

        self.showNormal()

    def _reposition_fullscreen_bar(self) -> None:
        if hasattr(self, "fullscreen_bar") and self.fullscreen_bar.isVisible():
            geo = self.geometry()
            self.fullscreen_bar.move(
                geo.right() - self.fullscreen_bar.width() - 40,
                geo.top() + 40,
            )

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

    def retranslate_ui(self) -> None:
        """Update localized UI strings when application language changes."""
        super().retranslate_ui()
        if hasattr(self, "action_registry") and self.action_registry:
            self.action_registry.retranslate_ui(safe_tr)
        if hasattr(self, "toolbars") and self.toolbars:
            retranslate_ledger_toolbars(self.toolbars, safe_tr)
        if hasattr(self, "btn_font_color") and self.btn_font_color:
            self.btn_font_color.setToolTip(safe_tr("字体颜色"))
            self.btn_font_color.setStatusTip(safe_tr("更改文本字体颜色"))
        if hasattr(self, "btn_fill_color") and self.btn_fill_color:
            self.btn_fill_color.setToolTip(safe_tr("填充颜色"))
            self.btn_fill_color.setStatusTip(safe_tr("更改单元格背景颜色"))
        if hasattr(self, "spreadsheet_view") and self.spreadsheet_view:
            self.spreadsheet_view.retranslate_ui()
        if hasattr(self, "menu_bar") and self.menu_bar:
            self.menu_bar.retranslate_ui()
        if hasattr(self, "fullscreen_bar") and self.fullscreen_bar:
            self.fullscreen_bar.retranslate_ui()
        if hasattr(self, "watch_pane") and self.watch_pane:
            self.watch_pane.retranslate_ui()
        if hasattr(self, "pivot_fields_pane") and self.pivot_fields_pane:
            self.pivot_fields_pane.retranslate_ui()
