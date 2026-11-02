"""Tests for Quire Missing Dialog Clusters (Phase 6, Task 603).

Covers:
1. Formatting & Page Setup: BreakDialog, DropCapDialog, TextDirectionDialog,
   WatermarkDialog, PageNumbersDialog, ChangeCaseDialog, DocumentThemeDialog.
2. References: FootnoteDialog, CaptionDialog, CrossRefDialog, IndexTablesDialog,
   BookmarkDialog, HyperlinkDialog, DateTimeDialog, FieldDialog, SymbolDialog.
3. Tools & Options: AutoCorrectDialog, QuireOptionsDialog, CustomizeDialog,
   EnvelopesLabelsDialog, LetterWizardDialog, AutoSummarizeDialog, HyphenationDialog.
4. Table Operations: InsertCellsDialog, DeleteCellsDialog, SplitCellsDialog,
   TableAutoFormatDialog, TableSortDialog, TableFormulaDialog.
5. Window integration and action registry bindings.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

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
from atboffice.ui.shell.quire_window import QuireWindow


class TestPageFormattingDialogs:
    def test_break_dialog(self, qapp: QApplication) -> None:
        dlg = BreakDialog()
        assert dlg.windowTitle() == "分隔符"
        cat, b_type = dlg.get_break_type()
        assert cat == "break"
        assert b_type == "page"

        # Check section break
        dlg.radio_next_page.setChecked(True)
        cat, b_type = dlg.get_break_type()
        assert cat == "section"
        assert b_type == "nextPage"

        dlg.retranslate_ui()
        assert dlg.windowTitle() == "分隔符"

    def test_drop_cap_dialog(self, qapp: QApplication) -> None:
        dlg = DropCapDialog(initial_position="dropped", initial_lines=4, initial_distance=0.5)
        assert dlg.windowTitle() == "首字下沉"
        data = dlg.get_drop_cap_data()
        assert data["position"] == "dropped"
        assert data["lines"] == 4
        assert data["distance_cm"] == 0.5

        dlg.radio_margin.setChecked(True)
        dlg.spin_lines.setValue(5)
        data = dlg.get_drop_cap_data()
        assert data["position"] == "margin"
        assert data["lines"] == 5

        dlg.retranslate_ui()

    def test_text_direction_dialog(self, qapp: QApplication) -> None:
        dlg = TextDirectionDialog(initial_direction="horz")
        assert dlg.get_direction() == "horz"

        dlg.radio_vert.setChecked(True)
        assert dlg.get_direction() == "vert"

        dlg.radio_vert270.setChecked(True)
        assert dlg.get_direction() == "vert270"

        dlg.retranslate_ui()

    def test_watermark_dialog(self, qapp: QApplication) -> None:
        dlg = WatermarkDialog(watermark_type="none")
        data = dlg.get_watermark_data()
        assert data["type"] == "none"

        dlg.radio_text.setChecked(True)
        dlg.combo_text.setEditText("CONFIDENTIAL")
        dlg.combo_size.setCurrentText("48")
        dlg.radio_horizontal.setChecked(True)
        data = dlg.get_watermark_data()
        assert data["type"] == "text"
        assert data["text"] == "CONFIDENTIAL"
        assert data["size"] == "48"
        assert data["layout"] == "horizontal"

        dlg.retranslate_ui()

    def test_page_numbers_dialog(self, qapp: QApplication) -> None:
        dlg = PageNumbersDialog(position="footer", alignment="center")
        settings = dlg.get_page_number_settings()
        assert settings["position"] == "footer"
        assert settings["alignment"] == "center"
        assert settings["show_first_page"] is True

        dlg.radio_start_at.setChecked(True)
        dlg.spin_start_at.setValue(5)
        settings = dlg.get_page_number_settings()
        assert settings["continue_numbering"] is False
        assert settings["start_at"] == 5

        dlg.retranslate_ui()

    def test_change_case_dialog(self, qapp: QApplication) -> None:
        dlg = ChangeCaseDialog()
        assert dlg.get_case_mode() == "sentence"

        dlg.radio_upper.setChecked(True)
        assert dlg.get_case_mode() == "upper"

        dlg.radio_title.setChecked(True)
        assert dlg.get_case_mode() == "title"

        dlg.retranslate_ui()

    def test_document_theme_dialog(self, qapp: QApplication) -> None:
        dlg = DocumentThemeDialog(current_theme="Apex")
        assert dlg.get_selected_theme() == "Apex"
        dlg.list_themes.setCurrentRow(0)
        assert dlg.get_selected_theme() == "Office"
        dlg.retranslate_ui()


class TestReferenceDialogs:
    def test_footnote_dialog(self, qapp: QApplication) -> None:
        dlg = FootnoteDialog()
        settings = dlg.get_footnote_settings()
        assert settings["type"] == "footnote"
        assert settings["start_at"] == 1

        dlg.radio_en.setChecked(True)
        settings = dlg.get_footnote_settings()
        assert settings["type"] == "endnote"

        dlg.retranslate_ui()

    def test_caption_dialog(self, qapp: QApplication) -> None:
        dlg = CaptionDialog()
        dlg.edit_caption.setText("System Architecture")
        dlg.combo_label.setCurrentText("图表")
        data = dlg.get_caption_data()
        assert data["caption"] == "System Architecture"
        assert data["label"] == "图表"
        assert data["position"] == "below"

        dlg.retranslate_ui()

    def test_cross_ref_dialog(self, qapp: QApplication) -> None:
        dlg = CrossRefDialog()
        data = dlg.get_cross_ref_data()
        assert "ref_type" in data
        assert "target" in data
        dlg.retranslate_ui()

    def test_index_tables_dialog(self, qapp: QApplication) -> None:
        dlg = IndexTablesDialog()
        dlg.tab_widget.setCurrentIndex(1)  # TOC
        data = dlg.get_index_tables_data()
        assert data["active_tab"] == 1
        assert data["toc_show_pages"] is True
        assert data["toc_levels"] == 3
        dlg.retranslate_ui()

    def test_bookmark_dialog(self, qapp: QApplication) -> None:
        dlg = BookmarkDialog(initial_bookmarks=["Intro", "Chapter1"])
        assert dlg.get_bookmarks() == ["Intro", "Chapter1"]
        dlg.edit_name.setText("Conclusion")
        dlg._add_bookmark()
        assert "Conclusion" in dlg.get_bookmarks()

        dlg.list_bookmarks.setCurrentRow(0)
        assert dlg.get_selected_bookmark() == "Intro"
        dlg._delete_bookmark()
        assert "Intro" not in dlg.get_bookmarks()
        dlg.retranslate_ui()

    def test_hyperlink_dialog(self, qapp: QApplication) -> None:
        dlg = HyperlinkDialog(initial_text="Google", initial_address="https://google.com")
        data = dlg.get_hyperlink_data()
        assert data["text"] == "Google"
        assert data["target"] == "https://google.com"
        assert data["kind"] == "external"

        dlg.tab_widget.setCurrentIndex(2)  # Email
        dlg.edit_email.setText("test@example.com")
        dlg.edit_subject.setText("Hello")
        data = dlg.get_hyperlink_data()
        assert data["kind"] == "email"
        assert "test@example.com" in data["target"]

        dlg.retranslate_ui()

    def test_date_time_dialog(self, qapp: QApplication) -> None:
        dlg = DateTimeDialog()
        fmt, update = dlg.get_selected_format()
        assert len(fmt) > 0
        assert update is False
        dlg.retranslate_ui()

    def test_field_dialog(self, qapp: QApplication) -> None:
        dlg = FieldDialog()
        data = dlg.get_field_data()
        assert len(data["name"]) > 0
        assert data["code"].startswith("{")
        dlg.retranslate_ui()

    def test_symbol_dialog(self, qapp: QApplication) -> None:
        dlg = SymbolDialog()
        ch = dlg.get_selected_character()
        assert len(ch) > 0
        dlg.tab_widget.setCurrentIndex(1)
        ch_spec = dlg.get_selected_character()
        assert len(ch_spec) > 0
        dlg.retranslate_ui()


class TestToolsDialogs:
    def test_autocorrect_dialog(self, qapp: QApplication) -> None:
        dlg = AutoCorrectDialog()
        settings = dlg.get_autocorrect_settings()
        assert settings["sentence_cap"] is True
        assert settings["replace_type"] is True
        assert "(c)" in settings["rules"]
        assert settings["rules"]["(c)"] == "©"

        dlg.edit_replace.setText("btw")
        dlg.edit_with.setText("by the way")
        dlg._add_rule()
        settings = dlg.get_autocorrect_settings()
        assert "btw" in settings["rules"]
        assert settings["rules"]["btw"] == "by the way"

        dlg.retranslate_ui()

    def test_quire_options_dialog(self, qapp: QApplication) -> None:
        dlg = QuireOptionsDialog()
        assert dlg.tab_widget.count() == 10
        data = dlg.get_options_data()
        assert data["startup_pane"] is True
        assert data["autorecover_min"] == 10
        assert data["recent_count"] == 4
        dlg.retranslate_ui()

    def test_customize_dialog(self, qapp: QApplication) -> None:
        dlg = CustomizeDialog()
        assert dlg.tab_widget.count() == 4
        assert dlg.list_tbs.count() > 0
        dlg.retranslate_ui()

    def test_envelopes_labels_dialog(self, qapp: QApplication) -> None:
        dlg = EnvelopesLabelsDialog()
        dlg.edit_delivery.setPlainText("123 Main St")
        data = dlg.get_envelope_data()
        assert data["tab"] == "envelopes"
        assert data["delivery"] == "123 Main St"
        dlg.retranslate_ui()

    def test_letter_wizard_dialog(self, qapp: QApplication) -> None:
        dlg = LetterWizardDialog()
        assert dlg.tab_widget.count() == 4
        data = dlg.get_letter_data()
        assert data["date_line"] is True
        dlg.retranslate_ui()

    def test_autosummarize_dialog(self, qapp: QApplication) -> None:
        dlg = AutoSummarizeDialog()
        dlg.radio_new.setChecked(True)
        data = dlg.get_summarize_data()
        assert data["mode"] == "new"
        dlg.retranslate_ui()

    def test_hyphenation_dialog(self, qapp: QApplication) -> None:
        dlg = HyphenationDialog()
        dlg.chk_auto.setChecked(True)
        dlg.spin_zone.setValue(24.0)
        settings = dlg.get_hyphenation_settings()
        assert settings["auto"] is True
        assert settings["zone_pt"] == 24.0
        dlg.retranslate_ui()


class TestTableDialogs:
    def test_insert_cells_dialog(self, qapp: QApplication) -> None:
        dlg = InsertCellsDialog()
        assert dlg.get_action() == "down"
        dlg.radio_row.setChecked(True)
        assert dlg.get_action() == "row"
        dlg.retranslate_ui()

    def test_delete_cells_dialog(self, qapp: QApplication) -> None:
        dlg = DeleteCellsDialog()
        assert dlg.get_action() == "left"
        dlg.radio_col.setChecked(True)
        assert dlg.get_action() == "col"
        dlg.retranslate_ui()

    def test_split_cells_dialog(self, qapp: QApplication) -> None:
        dlg = SplitCellsDialog(default_cols=3, default_rows=2, can_merge=True)
        cols, rows, merge = dlg.get_dimensions()
        assert cols == 3
        assert rows == 2
        assert merge is True
        dlg.retranslate_ui()

    def test_table_autoformat_dialog(self, qapp: QApplication) -> None:
        dlg = TableAutoFormatDialog(current_style="Table Colorful 1")
        data = dlg.get_format_settings()
        assert data["style"] == "Table Colorful 1"
        assert data["borders"] is True
        assert data["heading_rows"] is True
        dlg.retranslate_ui()

    def test_table_sort_dialog(self, qapp: QApplication) -> None:
        dlg = TableSortDialog(column_count=4)
        criteria = dlg.get_sort_criteria()
        assert criteria["has_header"] is True
        assert criteria["key1"]["ascending"] is True
        dlg.retranslate_ui()

    def test_table_formula_dialog(self, qapp: QApplication) -> None:
        dlg = TableFormulaDialog(default_formula="=SUM(ABOVE)")
        formula, num_fmt = dlg.get_formula_data()
        assert formula == "=SUM(ABOVE)"
        dlg._on_function_selected(3)  # AVERAGE
        formula, num_fmt = dlg.get_formula_data()
        assert "AVERAGE" in formula
        dlg.retranslate_ui()


class TestQuireWindowActionBindings:
    def test_quire_window_dialog_action_handlers(self, qapp: QApplication) -> None:
        win = QuireWindow()
        expected_actions = [
            "break",
            "dropCap",
            "textDirection",
            "watermark",
            "pageNumbers",
            "changeCase",
            "theme",
            "footnote",
            "caption",
            "crossReference",
            "indexTables",
            "bookmark",
            "hyperlink",
            "dateTime",
            "field",
            "symbol",
            "autoCorrect",
            "customize",
            "options",
            "envelopes",
            "letterWizard",
            "autoSummarize",
            "hyphenation",
            "insertCells",
            "deleteCells",
            "splitCells_dialog",
            "tableAutoFormat",
            "tableSort",
            "tableFormula",
        ]
        for act in expected_actions:
            handler = win.action_registry._handlers.get(act)
            assert handler is not None, f"Handler for {act} should be registered"
            assert callable(handler), f"Handler for {act} should be callable"
        win.close()
