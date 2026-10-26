"""GUI tests for Quire classic formatting dialogs."""

from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.dialogs.bullets_numbering import BulletsNumberingDialog
from atboffice.modules.writer.dialogs.font_dialog import FontDialog
from atboffice.modules.writer.dialogs.page_setup import PageSetupDialog
from atboffice.modules.writer.dialogs.paragraph_dialog import ParagraphDialog
from atboffice.modules.writer.models.properties import (
    IndentProperties,
    ParagraphProperties,
    RunProperties,
    SectionProperties,
    SpacingProperties,
)


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


class TestPageSetupDialog:
    def test_page_setup_initialization(self, qapp: QApplication) -> None:
        sect = SectionProperties(
            pg_w=595.3,
            pg_h=841.9,
            orient="portrait",
            mt=72.0,
            mb=72.0,
            ml=90.0,
            mr=90.0,
            gutter=10.0,
            hdr=36.0,
            ftr=36.0,
            title_pg=True,
            v_align="center",
            sect_type="nextPage",
        )
        dlg = PageSetupDialog(sect)
        assert dlg.windowTitle() == "页面设置"

        res = dlg.get_properties()
        assert abs(res.pg_w - 595.3) < 0.5
        assert abs(res.pg_h - 841.9) < 0.5
        assert res.orient == "portrait"
        assert res.mt == 72.0
        assert res.mb == 72.0
        assert res.ml == 90.0
        assert res.mr == 90.0
        assert res.gutter == 10.0
        assert res.title_pg is True
        assert res.v_align == "center"

    def test_orientation_switch(self, qapp: QApplication) -> None:
        sect = SectionProperties(pg_w=612.0, pg_h=792.0, orient="portrait")
        dlg = PageSetupDialog(sect)

        dlg.radio_landscape.setChecked(True)
        res = dlg.get_properties()
        assert res.orient == "landscape"
        assert res.pg_w >= res.pg_h  # width should be larger in landscape

        dlg.radio_portrait.setChecked(True)
        res = dlg.get_properties()
        assert res.orient == "portrait"
        assert res.pg_h >= res.pg_w  # height should be larger in portrait

    def test_paper_size_preset_selection(self, qapp: QApplication) -> None:
        dlg = PageSetupDialog()
        # Find A4 in paper size
        idx = dlg.combo_paper_size.findData("A4")
        if idx >= 0:
            dlg.combo_paper_size.setCurrentIndex(idx)
            res = dlg.get_properties()
            assert abs(res.pg_w - 595.3) < 1.0 or abs(res.pg_h - 841.9) < 1.0

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = PageSetupDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "页面设置"
        assert dlg.tab_widget.tabText(0) == "页边距"
        assert dlg.tab_widget.tabText(1) == "纸张"
        assert dlg.tab_widget.tabText(2) == "版式"


class TestBulletsNumberingDialog:
    def test_bullets_numbering_initialization(self, qapp: QApplication) -> None:
        dlg = BulletsNumberingDialog()
        assert dlg.windowTitle() == "项目符号和编号"
        assert dlg.tab_widget.tabText(0) == "项目符号"
        assert dlg.tab_widget.tabText(1) == "编号"
        assert dlg.tab_widget.tabText(2) == "多级符号"

    def test_select_bullet_gallery_item(self, qapp: QApplication) -> None:
        dlg = BulletsNumberingDialog()
        dlg.tab_widget.setCurrentIndex(0)
        # Select bullet item 1 (e.g. solid circle)
        dlg.select_item("bullet", 1)
        res = dlg.get_result()
        assert res["kind"] == "bullet"
        assert res["char"] in ("●", "•")

    def test_select_numbered_gallery_item(self, qapp: QApplication) -> None:
        dlg = BulletsNumberingDialog()
        dlg.tab_widget.setCurrentIndex(1)
        # Select numbered item 1 (1. 2. 3.)
        dlg.select_item("number", 1)
        dlg.radio_restart.setChecked(True)
        res = dlg.get_result()
        assert res["kind"] == "number"
        assert res["restart"] is True
        assert res["format"] == "1. 2. 3."

    def test_select_none_item(self, qapp: QApplication) -> None:
        dlg = BulletsNumberingDialog()
        dlg.select_item("bullet", 0)  # None
        res = dlg.get_result()
        assert res["kind"] == "none"

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = BulletsNumberingDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "项目符号和编号"
        assert dlg.tab_widget.tabText(0) == "项目符号"
        assert dlg.tab_widget.tabText(1) == "编号"
        assert dlg.tab_widget.tabText(2) == "多级符号"
        assert dlg.btn_reset.text() == "重新设置(&R)"
        assert dlg.btn_customize.text() == "自定义(&Z)..."



