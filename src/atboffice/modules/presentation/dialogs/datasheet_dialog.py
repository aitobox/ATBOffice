"""Datasheet Editor Dialog and Chart Preview Widget for DrawingML charts."""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.chart.model import (
    CH_KINDS,
    CH_PALETTE,
    ChartData,
    SeriesData,
)
from atboffice.modules.presentation.chart.painter import ChartPainter
from atboffice.modules.presentation.chart.renderers.common import resolve_color


def safe_tr(text: str) -> str:
    """Translate UI text with fallbacks."""
    app = QApplication.instance()
    if app:
        translated = app.translate("DatasheetDialog", text)
        if translated and translated != text:
            return translated
    return text


class ChartPreviewWidget(QWidget):
    """Live interactive preview widget displaying current chart state."""

    def __init__(self, chart: ChartData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chart = chart
        self.setMinimumSize(320, 240)
        self.setStyleSheet(
            "background-color: #FAFAFA; border: 1px solid #D9D9D9; border-radius: 4px;"
        )

    def set_chart(self, chart: ChartData) -> None:
        self.chart = chart
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        ChartPainter.paint_chart(painter, self.chart, rect)


class DatasheetDialog(QDialog):
    """Dialog for editing chart data, categories, series, types, and legend settings."""

    chartUpdated = Signal(object)

    def __init__(
        self,
        chart: ChartData | dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if isinstance(chart, ChartData):
            self.chart = copy.deepcopy(chart)
        elif isinstance(chart, dict):
            self.chart = ChartData.from_dict(chart)
        else:
            self.chart = ChartData.create_sample()

        self._updating_table = False
        self._init_ui()
        self.retranslate_ui()
        self._populate_controls()
        self._populate_table()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("图表与数据表编辑器"))
        self.resize(880, 560)
        self.setMinimumSize(720, 440)

        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left panel: Configuration & Datasheet Table
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Properties group
        self.prop_group = QGroupBox(self)
        prop_layout = QVBoxLayout(self.prop_group)

        # Row 1: Chart type
        r1 = QHBoxLayout()
        self.lbl_type = QLabel(self)
        self.cb_type = QComboBox(self)
        for kind_id, display_name in CH_KINDS:
            self.cb_type.addItem(display_name, kind_id)
        self.cb_type.currentIndexChanged.connect(self._on_type_changed)
        r1.addWidget(self.lbl_type)
        r1.addWidget(self.cb_type, 1)
        prop_layout.addLayout(r1)

        # Row 2: Title
        r2 = QHBoxLayout()
        self.lbl_title = QLabel(self)
        self.txt_title = QLineEdit(self)
        self.txt_title.textChanged.connect(self._on_title_changed)
        r2.addWidget(self.lbl_title)
        r2.addWidget(self.txt_title, 1)
        prop_layout.addLayout(r2)

        # Row 3: Legend & Options
        r3 = QHBoxLayout()
        self.lbl_legend = QLabel(self)
        self.cb_legend = QComboBox(self)
        self.cb_legend.addItem(safe_tr("靠右 (Right)"), "r")
        self.cb_legend.addItem(safe_tr("靠底 (Bottom)"), "b")
        self.cb_legend.addItem(safe_tr("靠顶 (Top)"), "t")
        self.cb_legend.addItem(safe_tr("靠左 (Left)"), "l")
        self.cb_legend.addItem(safe_tr("无图例 (None)"), "none")
        self.cb_legend.currentIndexChanged.connect(self._on_legend_changed)

        self.chk_grid = QCheckBox(self)
        self.chk_grid.toggled.connect(self._on_grid_toggled)

        self.chk_labels = QCheckBox(self)
        self.chk_labels.toggled.connect(self._on_labels_toggled)

        r3.addWidget(self.lbl_legend)
        r3.addWidget(self.cb_legend)
        r3.addWidget(self.chk_grid)
        r3.addWidget(self.chk_labels)
        prop_layout.addLayout(r3)

        left_layout.addWidget(self.prop_group)

        # Datasheet Table Group
        self.ds_group = QGroupBox(self)
        ds_layout = QVBoxLayout(self.ds_group)

        # Table
        self.table = QTableWidget(self)
        self.table.cellChanged.connect(self._on_cell_changed)
        ds_layout.addWidget(self.table)

        # Table Toolbar buttons
        btn_row = QHBoxLayout()
        self.btn_add_col = QPushButton(self)
        self.btn_add_col.clicked.connect(self._add_column)
        self.btn_del_col = QPushButton(self)
        self.btn_del_col.clicked.connect(self._delete_column)
        self.btn_add_row = QPushButton(self)
        self.btn_add_row.clicked.connect(self._add_row)
        self.btn_del_row = QPushButton(self)
        self.btn_del_row.clicked.connect(self._delete_row)

        btn_row.addWidget(self.btn_add_col)
        btn_row.addWidget(self.btn_del_col)
        btn_row.addWidget(self.btn_add_row)
        btn_row.addWidget(self.btn_del_row)
        ds_layout.addLayout(btn_row)

        left_layout.addWidget(self.ds_group, 1)

        # Right panel: Live Preview
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_preview_cap = QLabel(self)
        self.preview_widget = ChartPreviewWidget(self.chart, self)
        right_layout.addWidget(self.lbl_preview_cap)
        right_layout.addWidget(self.preview_widget, 1)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, 1)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def retranslate_ui(self) -> None:
        """Apply vivid, localized text to all UI controls."""
        self.setWindowTitle(safe_tr("图表与数据表编辑器"))
        self.prop_group.setTitle(safe_tr("图表基本属性与布局"))
        self.lbl_type.setText(safe_tr("图表类型 (&T):"))
        self.lbl_title.setText(safe_tr("图表标题 (&H):"))
        self.txt_title.setPlaceholderText(safe_tr("请输入图表标题..."))
        self.lbl_legend.setText(safe_tr("图例位置 (&L):"))
        self.chk_grid.setText(safe_tr("显示网格线 (&G)"))
        self.chk_grid.setToolTip(safe_tr("在数值轴上绘制水平参考网格线"))
        self.chk_labels.setText(safe_tr("显示数据标签 (&D)"))
        self.chk_labels.setToolTip(safe_tr("在各个数据点或柱体上方标记数值或百分比"))

        self.ds_group.setTitle(safe_tr("数据表 (Datasheet)"))
        self.btn_add_col.setText(safe_tr("添加类别列 (&C)"))
        self.btn_del_col.setText(safe_tr("删除类别列"))
        self.btn_add_row.setText(safe_tr("添加系列行 (&R)"))
        self.btn_del_row.setText(safe_tr("删除系列行"))
        self.lbl_preview_cap.setText(safe_tr("实时渲染预览 (Live Preview):"))

    def _populate_controls(self) -> None:
        idx = self.cb_type.findData(self.chart.kind)
        if idx >= 0:
            self.cb_type.setCurrentIndex(idx)

        self.txt_title.setText(self.chart.title)

        l_idx = self.cb_legend.findData(self.chart.legend)
        if l_idx >= 0:
            self.cb_legend.setCurrentIndex(l_idx)

        self.chk_grid.setChecked(self.chart.grid_y)
        self.chk_labels.setChecked(self.chart.labels)

    def _populate_table(self) -> None:
        self._updating_table = True
        cats = self.chart.cats or ["Category 1"]
        series = self.chart.series or []

        self.table.setColumnCount(len(cats) + 1)
        self.table.setRowCount(len(series))

        # Horizontal headers: "Series Name / Color" + Categories
        headers = [safe_tr("系列名称 / 颜色")] + cats
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for ri, s in enumerate(series):
            # Column 0: Series Name
            s_name = s.name or f"Series {ri+1}"
            name_item = QTableWidgetItem(s_name)
            col = resolve_color(s.color or CH_PALETTE[ri % len(CH_PALETTE)])
            name_item.setBackground(col.lighter(170))
            self.table.setItem(ri, 0, name_item)

            # Columns 1..N: Values
            for ci in range(len(cats)):
                val = s.vals[ci] if ci < len(s.vals) else 0.0
                val_item = QTableWidgetItem(str(val))
                val_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(ri, ci + 1, val_item)

        self._updating_table = False

    def _on_type_changed(self) -> None:
        kind = self.cb_type.currentData()
        if kind:
            self.chart.kind = kind
            self._refresh_preview()

    def _on_title_changed(self, text: str) -> None:
        self.chart.title = text
        self._refresh_preview()

    def _on_legend_changed(self) -> None:
        leg = self.cb_legend.currentData()
        if leg:
            self.chart.legend = leg
            self._refresh_preview()

    def _on_grid_toggled(self, checked: bool) -> None:
        self.chart.grid_y = checked
        self._refresh_preview()

    def _on_labels_toggled(self, checked: bool) -> None:
        self.chart.labels = checked
        self._refresh_preview()

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating_table:
            return
        item = self.table.item(row, col)
        if not item:
            return

        text = item.text().strip()
        if col == 0:
            if row < len(self.chart.series):
                self.chart.series[row].name = text
        else:
            cat_idx = col - 1
            if row < len(self.chart.series):
                try:
                    val = float(text)
                except ValueError:
                    val = 0.0
                while len(self.chart.series[row].vals) <= cat_idx:
                    self.chart.series[row].vals.append(0.0)
                self.chart.series[row].vals[cat_idx] = val

        self._refresh_preview()

    def _add_column(self) -> None:
        new_cat = f"Cat {len(self.chart.cats) + 1}"
        self.chart.cats.append(new_cat)
        for s in self.chart.series:
            s.vals.append(0.0)
        self._populate_table()
        self._refresh_preview()

    def _delete_column(self) -> None:
        if len(self.chart.cats) <= 1:
            return
        self.chart.cats.pop()
        for s in self.chart.series:
            if s.vals:
                s.vals.pop()
        self._populate_table()
        self._refresh_preview()

    def _add_row(self) -> None:
        n_cats = len(self.chart.cats)
        new_color = CH_PALETTE[len(self.chart.series) % len(CH_PALETTE)]
        new_series = SeriesData(
            name=f"Series {len(self.chart.series) + 1}",
            vals=[0.0] * n_cats,
            color=new_color,
        )
        self.chart.series.append(new_series)
        self._populate_table()
        self._refresh_preview()

    def _delete_row(self) -> None:
        if len(self.chart.series) <= 1:
            return
        self.chart.series.pop()
        self._populate_table()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        self.preview_widget.set_chart(self.chart)
        self.chartUpdated.emit(self.chart)

    def get_chart_data(self) -> ChartData:
        return self.chart
