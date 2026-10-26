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
