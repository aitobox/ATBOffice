"""Unit & GUI tests for Quire Writer classic modal dialogs:
- InsertTableDialog
- TabsDialog
- BordersShadingDialog
- ColumnsDialog
- TablePropertiesDialog
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from atboffice.modules.writer.dialogs.borders_shading import BordersShadingDialog
from atboffice.modules.writer.dialogs.columns_dialog import ColumnsDialog
from atboffice.modules.writer.dialogs.insert_table import InsertTableDialog
from atboffice.modules.writer.dialogs.table_properties import TablePropertiesDialog
from atboffice.modules.writer.dialogs.tabs_dialog import TabsDialog
from atboffice.modules.writer.models.properties import (
    TabStop,
)
from atboffice.modules.writer.models.table import create_simple_table


class TestInsertTableDialog:
    def test_default_values(self, qapp: QApplication) -> None:
        dlg = InsertTableDialog()
        cols, rows, fit, cw = dlg.get_dimensions()
        assert cols == 5
        assert rows == 2
        assert fit == "fixed"
        assert dlg.windowTitle() == "插入表格"

    def test_custom_dimensions_and_autofit(self, qapp: QApplication) -> None:
        dlg = InsertTableDialog(initial_cols=3, initial_rows=4)
        dlg.spin_cols.setValue(6)
        dlg.spin_rows.setValue(8)
        dlg.radio_contents.setChecked(True)

        cols, rows, fit, cw = dlg.get_dimensions()
        assert cols == 6
        assert rows == 8
        assert fit == "contents"

    def test_fixed_col_width(self, qapp: QApplication) -> None:
        dlg = InsertTableDialog()
        dlg.radio_fixed.setChecked(True)
        dlg.spin_col_width.setValue(72.0)
        cols, rows, fit, cw = dlg.get_dimensions()
        assert fit == "fixed"
        assert cw == 72.0

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = InsertTableDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "插入表格"
        assert "表格尺寸" in dlg.group_size.title()


class TestTabsDialog:
    def test_initial_tabs_and_add(self, qapp: QApplication) -> None:
        init_tabs = [TabStop(pos=36.0, align="left", leader="none")]
        dlg = TabsDialog(tabs=init_tabs, default_tab=36.0)

        # Verify initial tabs loaded
        tabs = dlg.get_tabs()
        assert len(tabs) == 1
        assert tabs[0].pos == 36.0

        # Add a new tab stop at 72.0 pt, center, dot leader
        dlg.edit_pos.setText("72 pt")
        dlg.radio_center.setChecked(True)
        dlg.radio_dot.setChecked(True)
        dlg.btn_set.click()

        tabs = dlg.get_tabs()
        assert len(tabs) == 2
        assert tabs[0].pos == 36.0
        assert tabs[1].pos == 72.0
        assert tabs[1].align == "center"
        assert tabs[1].leader == "dot"

    def test_clear_and_clear_all(self, qapp: QApplication) -> None:
        init_tabs = [
            TabStop(pos=36.0, align="left", leader="none"),
            TabStop(pos=72.0, align="right", leader="hyphen"),
        ]
        dlg = TabsDialog(tabs=init_tabs)
        assert len(dlg.get_tabs()) == 2

        # Select first and clear
        dlg.list_tabs.setCurrentRow(0)
        dlg.btn_clear.click()
        assert len(dlg.get_tabs()) == 1
        assert dlg.get_tabs()[0].pos == 72.0

        # Clear all
        dlg.btn_clear_all.click()
        assert len(dlg.get_tabs()) == 0

    def test_default_tab_stops(self, qapp: QApplication) -> None:
        dlg = TabsDialog(default_tab=48.0)
        assert dlg.get_default_tab() == 48.0
        dlg.spin_default.setValue(24.0)
        assert dlg.get_default_tab() == 24.0

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = TabsDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "制表位"
        assert "对齐方式" in dlg.group_align.title()
        assert "前导符" in dlg.group_leader.title()


class TestBordersShadingDialog:
    def test_borders_presets(self, qapp: QApplication) -> None:
        dlg = BordersShadingDialog(target_type="table")
        assert dlg.windowTitle() == "边框和底纹"

        # Apply Box preset
        dlg.preset_box.click()
        props = dlg.get_properties()
        bds = props["borders"]
        assert "top" in bds and bds["top"].val == "single"
        assert "bottom" in bds and bds["bottom"].val == "single"
        assert "left" in bds and bds["left"].val == "single"
        assert "right" in bds and bds["right"].val == "single"
        assert "insideH" not in bds or bds["insideH"] is None

        # Apply All preset
        dlg.preset_all.click()
        props = dlg.get_properties()
        bds = props["borders"]
        assert bds["insideH"] is not None
        assert bds["insideV"] is not None

        # Apply None preset
        dlg.preset_none.click()
        props = dlg.get_properties()
        assert not any(props["borders"].values())

    def test_shading_and_patterns(self, qapp: QApplication) -> None:
        dlg = BordersShadingDialog(target_type="cell")
        dlg.tab_widget.setCurrentIndex(2)  # Shading tab

        # Set fill color
        dlg.set_fill_color("#FFE082")
        # Set pattern
        dlg.combo_pattern.setCurrentText("50%")

        props = dlg.get_properties()
        shd = props["shading"]
        assert shd.fill.upper() in ("FFE082", "#FFE082")
        assert shd.val == "pct50"

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = BordersShadingDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "边框和底纹"
        assert dlg.tab_widget.tabText(0) == "边框"
        assert dlg.tab_widget.tabText(1) == "页面边框"
        assert dlg.tab_widget.tabText(2) == "底纹"


class TestColumnsDialog:
    def test_columns_presets(self, qapp: QApplication) -> None:
        dlg = ColumnsDialog()
        assert dlg.windowTitle() == "分栏"

        # Click Two columns preset
        dlg.btn_preset_two.click()
        cols = dlg.get_columns()
        assert cols.num == 2
        assert cols.equal_width is True

        # Click Three columns preset
        dlg.btn_preset_three.click()
        cols = dlg.get_columns()
        assert cols.num == 3

        # Click Left preset (unequal columns)
        dlg.btn_preset_left.click()
        cols = dlg.get_columns()
        assert cols.num == 2
        assert cols.equal_width is False
        assert len(cols.widths) == 2
        assert cols.widths[0] < cols.widths[1]

    def test_line_between_and_apply_to(self, qapp: QApplication) -> None:
        dlg = ColumnsDialog()
        dlg.check_sep.setChecked(True)
        dlg.combo_apply.setCurrentIndex(1)  # Whole document

        cols = dlg.get_columns()
        assert cols.sep is True
        assert dlg.get_apply_to() == "all"

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = ColumnsDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "分栏"
        assert "预设" in dlg.group_presets.title()
        assert "宽度和间距" in dlg.group_width_spacing.title()


class TestTablePropertiesDialog:
    def test_dialog_tabs_and_apply_to_table(self, qapp: QApplication) -> None:
        table = create_simple_table(rows=3, cols=3, width=450.0)
        dlg = TablePropertiesDialog(table=table, row_idx=0, col_idx=0)
        assert dlg.windowTitle() == "表格属性"
        assert dlg.tab_widget.count() == 4
        assert dlg.tab_widget.tabText(0) == "表格"
        assert dlg.tab_widget.tabText(1) == "行"
        assert dlg.tab_widget.tabText(2) == "列"
        assert dlg.tab_widget.tabText(3) == "单元格"

        # 1. Table tab: change alignment to center
        dlg.radio_align_center.setChecked(True)

        # 2. Row tab: specify height and cantSplit
        dlg.check_specify_height.setChecked(True)
        dlg.spin_row_height.setValue(36.0)
        dlg.combo_row_rule.setCurrentIndex(1)  # exactly
        dlg.check_row_split.setChecked(False)  # disallow split across pages
        dlg.check_row_header.setChecked(True)  # repeat as header

        # 3. Column tab: preferred width
        dlg.check_col_width.setChecked(True)
        dlg.spin_col_width.setValue(120.0)

        # 4. Cell tab: vertical alignment center
        dlg.radio_cell_valign_center.setChecked(True)

        # Apply to table
        dlg.apply_to_table(table)

        assert table.tbl_pr.jc == "center"
        row0 = table.rows[0].tr_pr
        assert row0.h == 36.0
        assert row0.h_rule == "exact"
        assert row0.cant_split is True
        assert row0.tbl_header is True

        cell0 = table.rows[0].cells[0].tc_pr
        assert cell0.v_align == "center"

    def test_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = TablePropertiesDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "表格属性"
        assert dlg.tab_widget.tabText(0) == "表格"
        assert dlg.tab_widget.tabText(1) == "行"
        assert dlg.tab_widget.tabText(2) == "列"
        assert dlg.tab_widget.tabText(3) == "单元格"
