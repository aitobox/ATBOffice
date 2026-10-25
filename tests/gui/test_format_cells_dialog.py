"""GUI automation tests for the 6-tab FormatCellsDialog."""

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.dialogs.format_cells import (
    AlignmentTab,
    BorderTab,
    FontTab,
    FormatCellsDialog,
    NumberFormatTab,
    PatternsTab,
    ProtectionTab,
)
from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    BorderStyle,
    CellData,
    SheetDataModel,
)


@pytest.fixture
def format_dialog(qapp: QApplication) -> FormatCellsDialog:
    dlg = FormatCellsDialog()
    return dlg


class TestFormatCellsDialogTabs:
    """Test all 6 tabs in FormatCellsDialog."""

    def test_dialog_tabs_initialization(self, format_dialog: FormatCellsDialog):
        assert format_dialog.tab_widget.count() == 6
        assert isinstance(format_dialog.tab_number, NumberFormatTab)
        assert isinstance(format_dialog.tab_alignment, AlignmentTab)
        assert isinstance(format_dialog.tab_font, FontTab)
        assert isinstance(format_dialog.tab_border, BorderTab)
        assert isinstance(format_dialog.tab_patterns, PatternsTab)
        assert isinstance(format_dialog.tab_protection, ProtectionTab)
        format_dialog.retranslate_ui()

    def test_tab_1_number_format(self, format_dialog: FormatCellsDialog):
        tab = format_dialog.tab_number

        # Check default category is General
        assert tab.get_category() == "General"
        assert tab.get_format_code() == "General"

        # Switch to Number
        tab.set_category("Number")
        tab.decimals_spin.setValue(3)
        tab.sep_check.setChecked(True)
        code = tab.get_format_code()
        assert "#,##0.000" in code

        # Switch to Currency
        tab.set_category("Currency")
        tab.symbol_combo.setCurrentText("¥")
        code = tab.get_format_code()
        assert "¥" in code

        # Switch to Percentage
        tab.set_category("Percentage")
        tab.decimals_spin.setValue(1)
        code = tab.get_format_code()
        assert "0.0%" in code

        # Switch to Custom
        tab.set_category("Custom")
        tab.custom_edit.setText("yyyy/mm/dd hh:mm")
        assert tab.get_format_code() == "yyyy/mm/dd hh:mm"

    def test_tab_2_alignment(self, format_dialog: FormatCellsDialog):
        tab = format_dialog.tab_alignment

        tab.combo_h.setCurrentText("居中")
        tab.combo_v.setCurrentText("靠上")
        tab.spin_indent.setValue(2)
        tab.check_wrap.setChecked(True)
        tab.check_shrink.setChecked(True)
        tab.check_merge.setChecked(True)
        tab.spin_rot.setValue(45)

        align_data = tab.get_alignment()
        assert align_data["align_h"] == "center"
        assert align_data["align_v"] == "top"
        assert align_data["indent"] == 2
        assert align_data["wrap_text"] is True
        assert align_data["shrink_to_fit"] is True
        assert align_data["merge_cells"] is True
        assert align_data["text_rotation"] == 45

    def test_tab_3_font(self, format_dialog: FormatCellsDialog):
        tab = format_dialog.tab_font

        tab.set_font_family("Courier New")
        tab.set_font_size(16)
        tab.set_bold(True)
        tab.set_italic(True)
        tab.combo_underline.setCurrentIndex(1)  # Single
        tab.check_strike.setChecked(True)
        tab.check_super.setChecked(True)

        font_data = tab.get_font()
        assert font_data["font_family"] == "Courier New"
        assert font_data["font_size"] == 16
        assert font_data["bold"] is True
        assert font_data["italic"] is True
        assert font_data["underline_style"] == "single"
        assert font_data["strike"] is True
        assert font_data["vert_align"] == "superscript"

        # Reset via Normal Font
        tab.btn_normal_font.click()
        reset_font = tab.get_font()
        assert reset_font["font_family"] == "Arial"
        assert reset_font["font_size"] == 10
        assert reset_font["bold"] is False
        assert reset_font["italic"] is False

    def test_tab_4_border(self, format_dialog: FormatCellsDialog):
        tab = format_dialog.tab_border

        # Select line style 'double'
        tab.set_line_style("double")
        tab.set_line_color("#0000FF")

        # Click Outline Preset
        tab.btn_preset_outline.click()
        borders = tab.get_borders()
        assert borders["top"] == BorderStyle("double", "#0000FF")
        assert borders["bottom"] == BorderStyle("double", "#0000FF")
        assert borders["left"] == BorderStyle("double", "#0000FF")
        assert borders["right"] == BorderStyle("double", "#0000FF")

        # Click None Preset
        tab.btn_preset_none.click()
        cleared = tab.get_borders()
        assert cleared["top"] is None
        assert cleared["bottom"] is None

        # Toggle individual border
        tab.toggle_border("top")
        assert tab.get_borders()["top"] == BorderStyle("double", "#0000FF")

    def test_tab_5_patterns(self, format_dialog: FormatCellsDialog):
        tab = format_dialog.tab_patterns

        tab.set_bg_color("#FFFF00")
        tab.set_pattern("pct50")
        tab.set_pattern_color("#FF0000")

        pat_data = tab.get_patterns()
        assert pat_data["bg_color"] == "#FFFF00"
        assert pat_data["pattern"] == "pct50"
        assert pat_data["pattern_color"] == "#FF0000"

        # No color click
        tab.btn_no_color.click()
        assert tab.get_patterns()["bg_color"] is None

    def test_tab_6_protection(self, format_dialog: FormatCellsDialog):
        tab = format_dialog.tab_protection

        assert tab.check_locked.isChecked() is True
        assert tab.check_hidden.isChecked() is False

        tab.check_locked.setChecked(False)
        tab.check_hidden.setChecked(True)

        prot_data = tab.get_protection()
        assert prot_data["locked"] is False
        assert prot_data["hidden"] is True


class TestFormatCellsDialogApplication:
    """Test applying FormatCellsDialog delta to SheetDataModel selection."""

    def test_apply_to_selection(self, qapp: QApplication):
        model = SheetDataModel()
        selection = SelectionModel()
        selection.select_cell(0, 0)
        selection.add_range(SelectionRange(0, 0, 1, 1))

        cell = CellData(value=500)
        model.set_cell(0, 0, cell)

        dlg = FormatCellsDialog(target_cell=cell, model=model, selection=selection)
        dlg.tab_number.set_category("Currency")
        dlg.tab_font.set_bold(True)
        dlg.tab_font.set_font_size(12)
        dlg.tab_alignment.combo_h.setCurrentText("居中")

        dlg.apply_to_selection()

        c00 = model.get_cell(0, 0)
        assert c00 is not None
        assert c00.value == 500
        assert "$" in c00.format_code or "¥" in c00.format_code
        assert c00.bold is True
        assert c00.font_size == 12
        assert c00.align_h == "center"

        # Also applied to uninitialized cell in range (0, 1)
        c01 = model.get_cell(0, 1)
        assert c01 is not None
        assert c01.bold is True
        assert c01.align_h == "center"

    def test_grid_viewport_and_main_window_integration(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
    ):
        from atboffice.modules.spreadsheet.view import SpreadsheetView
        from atboffice.ui.shell.main_window import MainWindow

        win = MainWindow()
        view = win.spreadsheet_view
        assert isinstance(view, SpreadsheetView)

        dialog_opened = []

        def mock_exec(dialog_self):
            dialog_opened.append(dialog_self)
            return True

        monkeypatch.setattr(FormatCellsDialog, "exec", mock_exec)

        # Trigger via MainWindow.format_cells()
        win.format_cells()
        assert len(dialog_opened) == 1
        assert isinstance(dialog_opened[0], FormatCellsDialog)

        # Trigger via GridViewport shortcut / method directly
        view.grid.open_format_cells_dialog(initial_tab=2)
        assert len(dialog_opened) == 2
        assert dialog_opened[1].tab_widget.currentIndex() == 2
