"""GUI tests for Quire classic formatting dialogs."""

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.models.properties import (
    IndentProperties,
    NumberingRef,
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    SpacingProperties,
)
from atboffice.modules.writer.dialogs.font_dialog import FontDialog
from atboffice.modules.writer.dialogs.paragraph_dialog import ParagraphDialog


class TestFontDialog:
    def test_font_dialog_initialization(self, qapp: QApplication) -> None:
        props = RunProperties(
            font="Arial",
            font_ea="SimHei",
            sz=14.0,
            b=True,
            i=False,
            u="single",
            color="FF0000",
            strike=True,
        )
        dlg = FontDialog(props)
        assert dlg.windowTitle() == "字体"

        # Check values loaded
        res = dlg.get_properties()
        assert res.font == "Arial"
        assert res.font_ea == "SimHei"
        assert res.sz == 14.0
        assert res.b is True
        assert res.i is False
        assert res.u == "single"
        assert res.color == "FF0000"
        assert res.strike is True

    def test_effects_mutual_exclusion(self, qapp: QApplication) -> None:
        dlg = FontDialog()
        # Strikethrough vs Double strikethrough
        dlg.check_strike.setChecked(True)
        assert dlg.check_strike.isChecked()
        assert not dlg.check_dstrike.isChecked()

        dlg.check_dstrike.setChecked(True)
        assert not dlg.check_strike.isChecked()
        assert dlg.check_dstrike.isChecked()

        # Superscript vs Subscript
        dlg.check_superscript.setChecked(True)
        assert not dlg.check_subscript.isChecked()

        dlg.check_subscript.setChecked(True)
        assert not dlg.check_superscript.isChecked()

        # Small caps vs All caps
        dlg.check_all_caps.setChecked(True)
        assert not dlg.check_small_caps.isChecked()

        dlg.check_small_caps.setChecked(True)
        assert not dlg.check_all_caps.isChecked()

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = FontDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "字体"
        assert dlg.tab_widget.tabText(0) == "字体"
        assert dlg.tab_widget.tabText(1) == "字符间距"


class TestParagraphDialog:
    def test_paragraph_dialog_initialization(self, qapp: QApplication) -> None:
        p_props = ParagraphProperties(
            jc="center",
            ind=IndentProperties(left=18.0, right=18.0, first_line=24.0),
            sp=SpacingProperties(before=6.0, after=12.0, line=1.5, line_rule="auto"),
            widow_control=True,
            keep_next=True,
            keep_lines=False,
            page_break_before=False,
            outline_level=2,
        )
        dlg = ParagraphDialog(p_props)
        assert dlg.windowTitle() == "段落"

        res = dlg.get_properties()
        assert res.jc == "center"
        assert res.ind.left == 18.0
        assert res.ind.right == 18.0
        assert res.ind.first_line == 24.0
        assert res.sp.before == 6.0
        assert res.sp.after == 12.0
        assert res.sp.line == 1.5
        assert res.keep_next is True
        assert res.outline_level == 2

    def test_indent_special_modes(self, qapp: QApplication) -> None:
        dlg = ParagraphDialog()
        dlg.combo_indent_special.setCurrentIndex(1)  # 首行缩进
        dlg.spin_indent_by.setValue(21.0)
        res = dlg.get_properties()
        assert res.ind.first_line == 21.0

        dlg.combo_indent_special.setCurrentIndex(2)  # 悬挂缩进
        dlg.spin_indent_by.setValue(15.0)
        res = dlg.get_properties()
        assert res.ind.first_line == -15.0

        dlg.combo_indent_special.setCurrentIndex(0)  # (无)
        res = dlg.get_properties()
        assert res.ind.first_line == 0.0

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = ParagraphDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "段落"
        assert dlg.tab_widget.tabText(0) == "缩进和间距"
        assert dlg.tab_widget.tabText(1) == "换行和分页"

