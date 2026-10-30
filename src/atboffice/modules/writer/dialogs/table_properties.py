"""Classic Table Properties Dialog for Quire Writer."""

from __future__ import annotations

import copy

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.dialogs.borders_shading import BordersShadingDialog
from atboffice.modules.writer.models.document import Table
from atboffice.modules.writer.models.properties import (
    CellProperties,
    RowProperties,
    TableProperties,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("TablePropertiesDialog", text)


class TableOptionsDialog(QDialog):
    """Modal sub-dialog for default table cell margins and cell spacing."""

    def __init__(
        self,
        parent: QWidget | None = None,
        margins: dict[str, float] | None = None,
        spacing: float = 0.0,
        autoresize: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("表格选项"))
        self.setModal(True)
        self.setMinimumWidth(300)

        m = margins or {"t": 0.0, "b": 0.0, "l": 5.4, "r": 5.4}

        layout = QVBoxLayout(self)

        # Margins group
        self.group_margins = QGroupBox(safe_tr("默认单元格边距"), self)
        grid_m = QGridLayout(self.group_margins)
        self.label_top = QLabel(safe_tr("上(&T):"), self.group_margins)
        self.spin_top = QDoubleSpinBox(self.group_margins)
        self.spin_top.setRange(0.0, 100.0)
        self.spin_top.setValue(m.get("t", 0.0))
        self.spin_top.setSuffix(" pt")

        self.label_bottom = QLabel(safe_tr("下(&B):"), self.group_margins)
        self.spin_bottom = QDoubleSpinBox(self.group_margins)
        self.spin_bottom.setRange(0.0, 100.0)
        self.spin_bottom.setValue(m.get("b", 0.0))
        self.spin_bottom.setSuffix(" pt")

        self.label_left = QLabel(safe_tr("左(&L):"), self.group_margins)
        self.spin_left = QDoubleSpinBox(self.group_margins)
        self.spin_left.setRange(0.0, 100.0)
        self.spin_left.setValue(m.get("l", 5.4))
        self.spin_left.setSuffix(" pt")

        self.label_right = QLabel(safe_tr("右(&R):"), self.group_margins)
        self.spin_right = QDoubleSpinBox(self.group_margins)
        self.spin_right.setRange(0.0, 100.0)
        self.spin_right.setValue(m.get("r", 5.4))
        self.spin_right.setSuffix(" pt")

        grid_m.addWidget(self.label_top, 0, 0)
        grid_m.addWidget(self.spin_top, 0, 1)
        grid_m.addWidget(self.label_bottom, 1, 0)
        grid_m.addWidget(self.spin_bottom, 1, 1)
        grid_m.addWidget(self.label_left, 0, 2)
        grid_m.addWidget(self.spin_left, 0, 3)
        grid_m.addWidget(self.label_right, 1, 2)
        grid_m.addWidget(self.spin_right, 1, 3)
        layout.addWidget(self.group_margins)

        # Spacing group
        self.group_spacing = QGroupBox(safe_tr("默认单元格间距"), self)
        h_sp = QHBoxLayout(self.group_spacing)
        self.check_spacing = QCheckBox(safe_tr("允许单元格间距(&S)"), self.group_spacing)
        self.check_spacing.setChecked(spacing > 0.0)
        self.spin_spacing = QDoubleSpinBox(self.group_spacing)
        self.spin_spacing.setRange(0.0, 50.0)
        self.spin_spacing.setValue(spacing)
        self.spin_spacing.setSuffix(" pt")
        self.spin_spacing.setEnabled(spacing > 0.0)
        self.check_spacing.toggled.connect(self.spin_spacing.setEnabled)

        h_sp.addWidget(self.check_spacing)
        h_sp.addWidget(self.spin_spacing)
        layout.addWidget(self.group_spacing)

        # Options
        self.check_autoresize = QCheckBox(safe_tr("自动重调尺寸以适应内容(&W)"), self)
        self.check_autoresize.setChecked(autoresize)
        layout.addWidget(self.check_autoresize)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_settings(self) -> tuple[dict[str, float], float, bool]:
        mar = {
            "t": self.spin_top.value(),
            "b": self.spin_bottom.value(),
            "l": self.spin_left.value(),
            "r": self.spin_right.value(),
        }
        sp = self.spin_spacing.value() if self.check_spacing.isChecked() else 0.0
        return mar, sp, self.check_autoresize.isChecked()


class CellOptionsDialog(QDialog):
    """Modal sub-dialog for individual cell margins and wrapping."""

    def __init__(
        self,
        parent: QWidget | None = None,
        same_as_table: bool = True,
        margins: dict[str, float] | None = None,
        wrap_text: bool = True,
        fit_text: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("单元格选项"))
        self.setModal(True)
        self.setMinimumWidth(280)

        m = margins or {"t": 0.0, "b": 0.0, "l": 5.4, "r": 5.4}

        layout = QVBoxLayout(self)

        self.group_margins = QGroupBox(safe_tr("单元格边距"), self)
        grid_m = QGridLayout(self.group_margins)

        self.check_same = QCheckBox(safe_tr("与整张表格相同(&S)"), self.group_margins)
        self.check_same.setChecked(same_as_table)

        self.label_top = QLabel(safe_tr("上(&T):"), self.group_margins)
        self.spin_top = QDoubleSpinBox(self.group_margins)
        self.spin_top.setRange(0.0, 100.0)
        self.spin_top.setValue(m.get("t", 0.0))
        self.spin_top.setSuffix(" pt")

        self.label_bottom = QLabel(safe_tr("下(&B):"), self.group_margins)
        self.spin_bottom = QDoubleSpinBox(self.group_margins)
        self.spin_bottom.setRange(0.0, 100.0)
        self.spin_bottom.setValue(m.get("b", 0.0))
        self.spin_bottom.setSuffix(" pt")

        self.label_left = QLabel(safe_tr("左(&L):"), self.group_margins)
        self.spin_left = QDoubleSpinBox(self.group_margins)
        self.spin_left.setRange(0.0, 100.0)
        self.spin_left.setValue(m.get("l", 5.4))
        self.spin_left.setSuffix(" pt")

        self.label_right = QLabel(safe_tr("右(&R):"), self.group_margins)
        self.spin_right = QDoubleSpinBox(self.group_margins)
        self.spin_right.setRange(0.0, 100.0)
        self.spin_right.setValue(m.get("r", 5.4))
        self.spin_right.setSuffix(" pt")

        grid_m.addWidget(self.check_same, 0, 0, 1, 4)
        grid_m.addWidget(self.label_top, 1, 0)
        grid_m.addWidget(self.spin_top, 1, 1)
        grid_m.addWidget(self.label_bottom, 2, 0)
        grid_m.addWidget(self.spin_bottom, 2, 1)
        grid_m.addWidget(self.label_left, 1, 2)
        grid_m.addWidget(self.spin_left, 1, 3)
        grid_m.addWidget(self.label_right, 2, 2)
        grid_m.addWidget(self.spin_right, 2, 3)

        self.check_same.toggled.connect(self._on_same_toggled)
        self._on_same_toggled(same_as_table)
        layout.addWidget(self.group_margins)

        self.group_opt = QGroupBox(safe_tr("选项"), self)
        v_opt = QVBoxLayout(self.group_opt)
        self.check_wrap = QCheckBox(safe_tr("文字换行(&W)"), self.group_opt)
        self.check_wrap.setChecked(wrap_text)
        self.check_fit = QCheckBox(safe_tr("适应文字(&F)"), self.group_opt)
        self.check_fit.setChecked(fit_text)
        v_opt.addWidget(self.check_wrap)
        v_opt.addWidget(self.check_fit)
        layout.addWidget(self.group_opt)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_same_toggled(self, checked: bool) -> None:
        enable_custom = not checked
        self.spin_top.setEnabled(enable_custom)
        self.spin_bottom.setEnabled(enable_custom)
        self.spin_left.setEnabled(enable_custom)
        self.spin_right.setEnabled(enable_custom)

    def get_settings(self) -> tuple[bool, dict[str, float], bool, bool]:
        mar = {
            "t": self.spin_top.value(),
            "b": self.spin_bottom.value(),
            "l": self.spin_left.value(),
            "r": self.spin_right.value(),
        }
        return (
            self.check_same.isChecked(),
            mar,
            self.check_wrap.isChecked(),
            self.check_fit.isChecked(),
        )


class TablePropertiesDialog(QDialog):
    """Word 2003 classic Table Properties modal dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        table: Table | None = None,
        table_props: TableProperties | None = None,
        row_idx: int = 0,
        col_idx: int = 0,
        cell_props: CellProperties | None = None,
        active_tab: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("表格属性"))
        self.setModal(True)
        self.setMinimumWidth(440)

        self._table = table
        self._row_idx = max(0, row_idx)
        self._col_idx = max(0, col_idx)

        # Extract initial properties from table if present
        if table:
            self._tp = copy.deepcopy(table.tbl_pr)
            tot_w = sum(table.grid) if table.grid else 450.0
            r_idx = min(self._row_idx, len(table.rows) - 1) if table.rows else 0
            row = table.rows[r_idx] if table.rows else None
            self._rp = copy.deepcopy(row.tr_pr) if row else RowProperties()
            c_idx = min(self._col_idx, len(row.cells) - 1) if row and row.cells else 0
            cell = row.cells[c_idx] if row and row.cells else None
            self._cp = copy.deepcopy(cell.tc_pr) if cell else CellProperties()
            col_w = (
                table.grid[min(self._col_idx, len(table.grid) - 1)] if table.grid else tot_w / 3.0
            )
            self._col_w = col_w
        else:
            self._tp = copy.deepcopy(table_props) if table_props else TableProperties()
            self._rp = RowProperties()
            self._cp = copy.deepcopy(cell_props) if cell_props else CellProperties()
            tot_w = self._tp.w or 450.0
            self._col_w = tot_w / 3.0

        self._table_margins = dict(self._tp.cell_mar)
        self._cell_spacing = 0.0
        self._auto_resize = True

        self._cell_same_as_table = not bool(self._cp.tc_mar)
        self._cell_margins = dict(self._cp.tc_mar) or dict(self._table_margins)
        self._cell_wrap = True
        self._cell_fit = False

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        self.tab_widget = QTabWidget(self)

        # Tab 1: Table
        self.tab_table = QWidget()
        self._init_table_tab(tot_w)
        self.tab_widget.addTab(self.tab_table, safe_tr("表格"))

        # Tab 2: Row
        self.tab_row = QWidget()
        self._init_row_tab()
        self.tab_widget.addTab(self.tab_row, safe_tr("行"))

        # Tab 3: Column
        self.tab_column = QWidget()
        self._init_column_tab()
        self.tab_widget.addTab(self.tab_column, safe_tr("列"))

        # Tab 4: Cell
        self.tab_cell = QWidget()
        self._init_cell_tab()
        self.tab_widget.addTab(self.tab_cell, safe_tr("单元格"))

        if 0 <= active_tab < 4:
            self.tab_widget.setCurrentIndex(active_tab)

        main_layout.addWidget(self.tab_widget)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.retranslate_ui()

    def _init_table_tab(self, total_width: float) -> None:
        layout = QVBoxLayout(self.tab_table)
        layout.setSpacing(8)

        # Size Group
        self.group_table_size = QGroupBox(safe_tr("尺寸"), self.tab_table)
        row_size = QHBoxLayout(self.group_table_size)
        self.check_table_width = QCheckBox(safe_tr("指定宽度(&W):"), self.group_table_size)
        has_w = self._tp.w > 0.0
        self.check_table_width.setChecked(has_w)

        self.spin_table_width = QDoubleSpinBox(self.group_table_size)
        self.spin_table_width.setRange(9.0, 3000.0)
        self.spin_table_width.setValue(self._tp.w if has_w else total_width)
        self.spin_table_width.setSuffix(" pt")
        self.spin_table_width.setEnabled(has_w)
        self.check_table_width.toggled.connect(self.spin_table_width.setEnabled)

        self.label_table_unit = QLabel(safe_tr("度量单位:"), self.group_table_size)
        self.combo_table_unit = QComboBox(self.group_table_size)
        self.combo_table_unit.addItem(safe_tr("点/英寸/厘米"), "dxa")
        self.combo_table_unit.addItem(safe_tr("百分比"), "pct")

        row_size.addWidget(self.check_table_width)
        row_size.addWidget(self.spin_table_width)
        row_size.addWidget(self.label_table_unit)
        row_size.addWidget(self.combo_table_unit)
        layout.addWidget(self.group_table_size)

        # Alignment Group
        self.group_table_align = QGroupBox(safe_tr("对齐方式"), self.tab_table)
        row_align = QHBoxLayout(self.group_table_align)
        self.btn_group_align = QButtonGroup(self.tab_table)

        self.radio_align_left = QRadioButton(safe_tr("左对齐(&L)"), self.group_table_align)
        self.radio_align_center = QRadioButton(safe_tr("居中(&C)"), self.group_table_align)
        self.radio_align_right = QRadioButton(safe_tr("右对齐(&R)"), self.group_table_align)

        if self._tp.jc == "center":
            self.radio_align_center.setChecked(True)
        elif self._tp.jc in ("right", "end"):
            self.radio_align_right.setChecked(True)
        else:
            self.radio_align_left.setChecked(True)

        self.btn_group_align.addButton(self.radio_align_left, 0)
        self.btn_group_align.addButton(self.radio_align_center, 1)
        self.btn_group_align.addButton(self.radio_align_right, 2)

        self.label_indent = QLabel(safe_tr("左边缩进(&I):"), self.group_table_align)
        self.spin_table_indent = QDoubleSpinBox(self.group_table_align)
        self.spin_table_indent.setRange(0.0, 500.0)
        self.spin_table_indent.setValue(0.0)
        self.spin_table_indent.setSuffix(" pt")

        row_align.addWidget(self.radio_align_left)
        row_align.addWidget(self.radio_align_center)
        row_align.addWidget(self.radio_align_right)
        row_align.addWidget(self.label_indent)
        row_align.addWidget(self.spin_table_indent)
        layout.addWidget(self.group_table_align)

        # Text wrapping
        self.group_table_wrap = QGroupBox(safe_tr("文字环绕"), self.tab_table)
        row_wrap = QHBoxLayout(self.group_table_wrap)
        self.btn_group_wrap = QButtonGroup(self.tab_table)
        self.radio_wrap_none = QRadioButton(safe_tr("无(&N)"), self.group_table_wrap)
        self.radio_wrap_around = QRadioButton(safe_tr("环绕(&A)"), self.group_table_wrap)
        self.radio_wrap_none.setChecked(True)

        self.btn_group_wrap.addButton(self.radio_wrap_none, 0)
        self.btn_group_wrap.addButton(self.radio_wrap_around, 1)
        row_wrap.addWidget(self.radio_wrap_none)
        row_wrap.addWidget(self.radio_wrap_around)
        row_wrap.addStretch(1)
        layout.addWidget(self.group_table_wrap)

        # Sub-dialog buttons
        row_btns = QHBoxLayout()
        self.btn_borders_shading = QPushButton(safe_tr("边框和底纹(&B)..."), self.tab_table)
        self.btn_table_options = QPushButton(safe_tr("选项(&O)..."), self.tab_table)
        self.btn_borders_shading.clicked.connect(self._open_borders_shading)
        self.btn_table_options.clicked.connect(self._open_table_options)

        row_btns.addWidget(self.btn_borders_shading)
        row_btns.addWidget(self.btn_table_options)
        row_btns.addStretch(1)
        layout.addLayout(row_btns)
        layout.addStretch(1)

    def _init_row_tab(self) -> None:
        layout = QVBoxLayout(self.tab_row)
        layout.setSpacing(8)

        self.label_row_title = QLabel(
            f"{safe_tr('第')} {self._row_idx + 1} {safe_tr('行:')}", self.tab_row
        )
        self.label_row_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.label_row_title)

        # Size Group
        self.group_row_size = QGroupBox(safe_tr("尺寸"), self.tab_row)
        row_sz = QHBoxLayout(self.group_row_size)
        self.check_specify_height = QCheckBox(safe_tr("指定高度(&S):"), self.group_row_size)
        has_h = self._rp.h is not None and self._rp.h > 0
        self.check_specify_height.setChecked(has_h)

        self.spin_row_height = QDoubleSpinBox(self.group_row_size)
        self.spin_row_height.setRange(1.0, 1000.0)
        self.spin_row_height.setValue(self._rp.h or 14.4)
        self.spin_row_height.setSuffix(" pt")
        self.spin_row_height.setEnabled(has_h)
        self.check_specify_height.toggled.connect(self.spin_row_height.setEnabled)

        self.label_row_rule = QLabel(safe_tr("行高值是(&R):"), self.group_row_size)
        self.combo_row_rule = QComboBox(self.group_row_size)
        self.combo_row_rule.addItem(safe_tr("最小值"), "atLeast")
        self.combo_row_rule.addItem(safe_tr("固定值"), "exact")
        if self._rp.h_rule == "exact":
            self.combo_row_rule.setCurrentIndex(1)

        row_sz.addWidget(self.check_specify_height)
        row_sz.addWidget(self.spin_row_height)
        row_sz.addWidget(self.label_row_rule)
        row_sz.addWidget(self.combo_row_rule)
        layout.addWidget(self.group_row_size)

        # Options Group
        self.group_row_opts = QGroupBox(safe_tr("选项"), self.tab_row)
        v_opt = QVBoxLayout(self.group_row_opts)
        self.check_row_split = QCheckBox(safe_tr("允许跨页断行(&K)"), self.group_row_opts)
        self.check_row_split.setChecked(not self._rp.cant_split)

        self.check_row_header = QCheckBox(
            safe_tr("在各页顶端以标题行形式重复出现(&H)"), self.group_row_opts
        )
        self.check_row_header.setChecked(self._rp.tbl_header)

        v_opt.addWidget(self.check_row_split)
        v_opt.addWidget(self.check_row_header)
        layout.addWidget(self.group_row_opts)
        layout.addStretch(1)

    def _init_column_tab(self) -> None:
        layout = QVBoxLayout(self.tab_column)
        layout.setSpacing(8)

        self.label_col_title = QLabel(
            f"{safe_tr('第')} {self._col_idx + 1} {safe_tr('列:')}", self.tab_column
        )
        self.label_col_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.label_col_title)

        self.group_col_size = QGroupBox(safe_tr("尺寸"), self.tab_column)
        row_sz = QHBoxLayout(self.group_col_size)
        self.check_col_width = QCheckBox(safe_tr("指定宽度(&W):"), self.group_col_size)
        self.check_col_width.setChecked(True)

        self.spin_col_width = QDoubleSpinBox(self.group_col_size)
        self.spin_col_width.setRange(6.0, 1500.0)
        self.spin_col_width.setValue(self._col_w)
        self.spin_col_width.setSuffix(" pt")
        self.check_col_width.toggled.connect(self.spin_col_width.setEnabled)

        row_sz.addWidget(self.check_col_width)
        row_sz.addWidget(self.spin_col_width)
        row_sz.addStretch(1)
        layout.addWidget(self.group_col_size)
        layout.addStretch(1)

    def _init_cell_tab(self) -> None:
        layout = QVBoxLayout(self.tab_cell)
        layout.setSpacing(8)

        # Cell size
        self.group_cell_size = QGroupBox(safe_tr("尺寸"), self.tab_cell)
        row_sz = QHBoxLayout(self.group_cell_size)
        self.check_cell_width = QCheckBox(safe_tr("指定宽度(&W):"), self.group_cell_size)
        has_cw = self._cp.w > 0
        self.check_cell_width.setChecked(has_cw)

        self.spin_cell_width = QDoubleSpinBox(self.group_cell_size)
        self.spin_cell_width.setRange(6.0, 1500.0)
        self.spin_cell_width.setValue(self._cp.w or self._col_w)
        self.spin_cell_width.setSuffix(" pt")
        self.spin_cell_width.setEnabled(has_cw)
        self.check_cell_width.toggled.connect(self.spin_cell_width.setEnabled)

        row_sz.addWidget(self.check_cell_width)
        row_sz.addWidget(self.spin_cell_width)
        row_sz.addStretch(1)
        layout.addWidget(self.group_cell_size)

        # Cell vertical alignment
        self.group_cell_valign = QGroupBox(safe_tr("垂直对齐方式"), self.tab_cell)
        row_va = QHBoxLayout(self.group_cell_valign)
        self.btn_group_valign = QButtonGroup(self.tab_cell)

        self.radio_cell_valign_top = QRadioButton(safe_tr("顶端对齐(&T)"), self.group_cell_valign)
        self.radio_cell_valign_center = QRadioButton(safe_tr("居中(&C)"), self.group_cell_valign)
        self.radio_cell_valign_bottom = QRadioButton(
            safe_tr("底端对齐(&B)"), self.group_cell_valign
        )

        if self._cp.v_align == "center":
            self.radio_cell_valign_center.setChecked(True)
        elif self._cp.v_align == "bottom":
            self.radio_cell_valign_bottom.setChecked(True)
        else:
            self.radio_cell_valign_top.setChecked(True)

        self.btn_group_valign.addButton(self.radio_cell_valign_top, 0)
        self.btn_group_valign.addButton(self.radio_cell_valign_center, 1)
        self.btn_group_valign.addButton(self.radio_cell_valign_bottom, 2)

        row_va.addWidget(self.radio_cell_valign_top)
        row_va.addWidget(self.radio_cell_valign_center)
        row_va.addWidget(self.radio_cell_valign_bottom)
        layout.addWidget(self.group_cell_valign)

        # Cell options button
        row_opts = QHBoxLayout()
        self.btn_cell_options = QPushButton(safe_tr("选项(&O)..."), self.tab_cell)
        self.btn_cell_options.clicked.connect(self._open_cell_options)
        row_opts.addWidget(self.btn_cell_options)
        row_opts.addStretch(1)
        layout.addLayout(row_opts)
        layout.addStretch(1)

    def _open_borders_shading(self) -> None:
        dlg = BordersShadingDialog(self, borders=self._tp.borders, target_type="table")
        if dlg.exec():
            res = dlg.get_properties()
            self._tp.borders = res.get("borders", {})

    def _open_table_options(self) -> None:
        dlg = TableOptionsDialog(
            self,
            margins=self._table_margins,
            spacing=self._cell_spacing,
            autoresize=self._auto_resize,
        )
        if dlg.exec():
            self._table_margins, self._cell_spacing, self._auto_resize = dlg.get_settings()
            self._tp.cell_mar = self._table_margins

    def _open_cell_options(self) -> None:
        dlg = CellOptionsDialog(
            self,
            same_as_table=self._cell_same_as_table,
            margins=self._cell_margins,
            wrap_text=self._cell_wrap,
            fit_text=self._cell_fit,
        )
        if dlg.exec():
            self._cell_same_as_table, self._cell_margins, self._cell_wrap, self._cell_fit = (
                dlg.get_settings()
            )
            if self._cell_same_as_table:
                self._cp.tc_mar = {}
            else:
                self._cp.tc_mar = self._cell_margins

    def retranslate_ui(self) -> None:
        """Update all translatable strings dynamically."""
        self.setWindowTitle(safe_tr("表格属性"))
        self.tab_widget.setTabText(0, safe_tr("表格"))
        self.tab_widget.setTabText(1, safe_tr("行"))
        self.tab_widget.setTabText(2, safe_tr("列"))
        self.tab_widget.setTabText(3, safe_tr("单元格"))

        self.group_table_size.setTitle(safe_tr("尺寸"))
        self.check_table_width.setText(safe_tr("指定宽度(&W):"))
        self.label_table_unit.setText(safe_tr("度量单位:"))

        self.group_table_align.setTitle(safe_tr("对齐方式"))
        self.radio_align_left.setText(safe_tr("左对齐(&L)"))
        self.radio_align_center.setText(safe_tr("居中(&C)"))
        self.radio_align_right.setText(safe_tr("右对齐(&R)"))
        self.label_indent.setText(safe_tr("左边缩进(&I):"))

        self.group_table_wrap.setTitle(safe_tr("文字环绕"))
        self.radio_wrap_none.setText(safe_tr("无(&N)"))
        self.radio_wrap_around.setText(safe_tr("环绕(&A)"))

        self.btn_borders_shading.setText(safe_tr("边框和底纹(&B)..."))
        self.btn_table_options.setText(safe_tr("选项(&O)..."))

        self.group_row_size.setTitle(safe_tr("尺寸"))
        self.check_specify_height.setText(safe_tr("指定高度(&S):"))
        self.label_row_rule.setText(safe_tr("行高值是(&R):"))

        self.group_row_opts.setTitle(safe_tr("选项"))
        self.check_row_split.setText(safe_tr("允许跨页断行(&K)"))
        self.check_row_header.setText(safe_tr("在各页顶端以标题行形式重复出现(&H)"))

        self.group_col_size.setTitle(safe_tr("尺寸"))
        self.check_col_width.setText(safe_tr("指定宽度(&W):"))

        self.group_cell_size.setTitle(safe_tr("尺寸"))
        self.check_cell_width.setText(safe_tr("指定宽度(&W):"))

        self.group_cell_valign.setTitle(safe_tr("垂直对齐方式"))
        self.radio_cell_valign_top.setText(safe_tr("顶端对齐(&T)"))
        self.radio_cell_valign_center.setText(safe_tr("居中(&C)"))
        self.radio_cell_valign_bottom.setText(safe_tr("底端对齐(&B)"))

        self.btn_cell_options.setText(safe_tr("选项(&O)..."))

        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("取消"))

    def get_properties(self) -> dict:
        """Return dict of current properties."""
        # Align
        if self.radio_align_center.isChecked():
            jc = "center"
        elif self.radio_align_right.isChecked():
            jc = "right"
        else:
            jc = "left"
        self._tp.jc = jc

        # Table Width
        if self.check_table_width.isChecked():
            self._tp.w = float(self.spin_table_width.value())
            self._tp.w_type = str(self.combo_table_unit.currentData())
        else:
            self._tp.w = 0.0
            self._tp.w_type = "auto"

        # Row
        if self.check_specify_height.isChecked():
            self._rp.h = float(self.spin_row_height.value())
            self._rp.h_rule = str(self.combo_row_rule.currentData())
        else:
            self._rp.h = None
            self._rp.h_rule = "auto"
        self._rp.cant_split = not self.check_row_split.isChecked()
        self._rp.tbl_header = self.check_row_header.isChecked()

        # Cell
        if self.radio_cell_valign_center.isChecked():
            va = "center"
        elif self.radio_cell_valign_bottom.isChecked():
            va = "bottom"
        else:
            va = "top"
        self._cp.v_align = va

        if self.check_cell_width.isChecked():
            self._cp.w = float(self.spin_cell_width.value())
            self._cp.w_type = "dxa"

        return {
            "table_props": self._tp,
            "row_props": self._rp,
            "cell_props": self._cp,
            "col_width": self.spin_col_width.value() if self.check_col_width.isChecked() else None,
        }

    def apply_to_table(self, table: Table) -> None:
        """Atomically apply configured properties to a Table instance."""
        props = self.get_properties()
        tp: TableProperties = props["table_props"]
        rp: RowProperties = props["row_props"]
        cp: CellProperties = props["cell_props"]
        cw: float | None = props["col_width"]

        # Table level
        table.tbl_pr.jc = tp.jc
        table.tbl_pr.w = tp.w
        table.tbl_pr.w_type = tp.w_type
        table.tbl_pr.borders = tp.borders
        table.tbl_pr.cell_mar = tp.cell_mar

        # Row level
        r_idx = min(self._row_idx, len(table.rows) - 1) if table.rows else 0
        if 0 <= r_idx < len(table.rows):
            row = table.rows[r_idx]
            row.tr_pr.h = rp.h
            row.tr_pr.h_rule = rp.h_rule
            row.tr_pr.cant_split = rp.cant_split
            row.tr_pr.tbl_header = rp.tbl_header

            # Cell level
            c_idx = min(self._col_idx, len(row.cells) - 1) if row.cells else 0
            if 0 <= c_idx < len(row.cells):
                cell = row.cells[c_idx]
                cell.tc_pr.v_align = cp.v_align
                if cp.w > 0:
                    cell.tc_pr.w = cp.w
                cell.tc_pr.tc_mar = cp.tc_mar

        # Column level grid adjustment
        if cw is not None and table.grid:
            c_idx = min(self._col_idx, len(table.grid) - 1)
            if 0 <= c_idx < len(table.grid):
                table.grid[c_idx] = round(cw, 2)
                table.tbl_pr.w = sum(table.grid)
