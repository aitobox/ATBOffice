"""Classic Excel 2003 4-step Chart Wizard Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def safe_tr(text: str) -> str:
    """Safely translate ChartWizard UI string."""
    return QCoreApplication.translate("ChartWizardDialog", text)


CHART_TYPES = [
    {
        "id": "column",
        "name": "柱形图",
        "name_en": "Column",
        "desc": "柱形图用于显示一段时间内的数据变化或比较各项之间的大小关系。",
        "subtypes": [
            ("clustered", "簇状柱形图", "比较各项目的值。"),
            ("stacked", "堆积柱形图", "比较各项目所占总量的比重。"),
            ("percent_stacked", "百分比堆积柱形图", "比较各项在每个类别中所占的百分比。"),
            ("3d_clustered", "三维簇状柱形图", "以三维立体方式展示各项目数值。"),
        ],
    },
    {
        "id": "bar",
        "name": "条形图",
        "name_en": "Bar",
        "desc": "条形图用于显示多个项目之间的比较情况。",
        "subtypes": [
            ("clustered_bar", "簇状条形图", "水平比较各项的值。"),
            ("stacked_bar", "堆积条形图", "水平展示各项目所占总量的比重。"),
            ("percent_stacked_bar", "百分比堆积条形图", "水平比较各项所占百分比。"),
        ],
    },
    {
        "id": "line",
        "name": "折线图",
        "name_en": "Line",
        "desc": "折线图按相同的间隔显示数据的连续变化趋势。",
        "subtypes": [
            ("line_plain", "折线图", "显示随时间或类别的趋势。"),
            ("stacked_line", "堆积折线图", "显示每一数值所占大小随时间变化的趋势。"),
            ("line_markers", "数据点折线图", "在每个数据值处带有明显标记的折线图。"),
        ],
    },
    {
        "id": "pie",
        "name": "饼图",
        "name_en": "Pie",
        "desc": "饼图显示组成数据系列的项目在总和中所占的比例。",
        "subtypes": [
            ("pie_2d", "饼图", "显示每一数值相对于总数值的大小。"),
            ("pie_exploded", "分离型饼图", "突出显示每一个扇区所占比例。"),
            ("pie_3d", "三维饼图", "以三维视觉效果展示扇形比例。"),
        ],
    },
    {
        "id": "scatter",
        "name": "散点图",
        "name_en": "XY (Scatter)",
        "desc": "散点图用于比较成对的数值，显示若干数据系列中各数值之间的关系。",
        "subtypes": [
            ("scatter_points", "无折线散点图", "仅比较成对的值并标出数据点。"),
            ("scatter_smooth", "平滑线散点图", "用平滑曲线连接各数据点。"),
            ("scatter_lines", "折线散点图", "用直线连接各数据点。"),
        ],
    },
    {
        "id": "area",
        "name": "面积图",
        "name_en": "Area",
        "desc": "面积图强调数量随时间变化的程度，并可用于引起对总值趋势的注意。",
        "subtypes": [
            ("area_2d", "面积图", "显示随时间或类别变化的值的趋势。"),
            ("stacked_area", "堆积面积图", "显示每一数值所占总量的趋势。"),
        ],
    },
    {
        "id": "doughnut",
        "name": "圆环图",
        "name_en": "Doughnut",
        "desc": "像饼图一样，圆环图显示部分与整体的关系，但它可以包含多个数据系列。",
        "subtypes": [
            ("doughnut_standard", "圆环图", "在同心环中显示数据系列。"),
            ("doughnut_exploded", "分离型圆环图", "突出显示圆环中的各个扇区。"),
        ],
    },
    {
        "id": "radar",
        "name": "雷达图",
        "name_en": "Radar",
        "desc": "雷达图比较若干数据系列的综合值。",
        "subtypes": [
            ("radar_standard", "雷达图", "显示数值相对于中心点的变化。"),
            ("radar_markers", "数据点雷达图", "显示带有数据标记的雷达图。"),
            ("radar_filled", "填充雷达图", "用颜色填充雷达图所覆盖的区域。"),
        ],
    },
]


class ChartSamplePreviewWidget(QWidget):
    """Small thumbnail / sample preview widget for chart subtypes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chart_type: str = "column"
        self.sub_type: str = "clustered"
        self.setFixedSize(140, 100)
        self.setStyleSheet("background-color: white; border: 1px solid #7F9DB9;")

    def set_chart_info(self, chart_type: str, sub_type: str) -> None:
        self.chart_type = chart_type
        self.sub_type = sub_type
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor("#FFFFFF"))
        # Border
        painter.setPen(QPen(QColor("#7F9DB9"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        # Draw miniature axes
        painter.setPen(QPen(QColor("#888888"), 1))
        painter.drawLine(15, 15, 15, h - 15)
        painter.drawLine(15, h - 15, w - 15, h - 15)

        # Draw schematic sample based on chart_type
        if self.chart_type in ("column", "3d_column"):
            # Bars
            colors = [QColor("#4F81BD"), QColor("#C0504D"), QColor("#9BBB59")]
            x = 22
            bar_w = 8
            heights = [40, 25, 55, 30, 45, 60]
            for i, ht in enumerate(heights):
                col = colors[i % len(colors)]
                painter.fillRect(x, h - 15 - ht, bar_w, ht, col)
                painter.setPen(QPen(col.darker(120), 1))
                painter.drawRect(x, h - 15 - ht, bar_w, ht)
                x += bar_w + (4 if i % 3 == 2 else 1)
        elif self.chart_type == "bar":
            colors = [QColor("#4F81BD"), QColor("#C0504D")]
            y = 20
            bar_h = 7
            widths = [50, 70, 40, 85, 60, 90]
            for i, wd in enumerate(widths):
                col = colors[i % len(colors)]
                painter.fillRect(15, y, wd, bar_h, col)
                painter.setPen(QPen(col.darker(120), 1))
                painter.drawRect(15, y, wd, bar_h)
                y += bar_h + (4 if i % 2 == 1 else 1)
        elif self.chart_type in ("line", "scatter"):
            # Line
            painter.setPen(QPen(QColor("#4F81BD"), 2))
            pts = [(20, h - 30), (45, h - 65), (75, h - 40), (105, h - 75), (125, h - 50)]
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            painter.setBrush(QBrush(QColor("#C0504D")))
            for pt in pts:
                painter.drawEllipse(pt[0] - 2, pt[1] - 2, 4, 4)
        elif self.chart_type in ("pie", "doughnut"):
            # Pie
            rect = (w // 2 - 30, h // 2 - 30, 60, 60)
            painter.setBrush(QBrush(QColor("#4F81BD")))
            painter.drawPie(*rect, 0 * 16, 120 * 16)
            painter.setBrush(QBrush(QColor("#C0504D")))
            painter.drawPie(*rect, 120 * 16, 100 * 16)
            painter.setBrush(QBrush(QColor("#9BBB59")))
            painter.drawPie(*rect, 220 * 16, 140 * 16)
            if self.chart_type == "doughnut":
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.drawEllipse(w // 2 - 12, h // 2 - 12, 24, 24)
        else:
            # Default area
            painter.setBrush(QBrush(QColor(79, 129, 189, 100)))
            painter.setPen(QPen(QColor("#4F81BD"), 1))
            poly = [
                (15, h - 15),
                (35, h - 45),
                (65, h - 30),
                (95, h - 60),
                (125, h - 50),
                (125, h - 15),
            ]
            from PySide6.QtCore import QPoint
            from PySide6.QtGui import QPolygon
            painter.drawPolygon(QPolygon([QPoint(px, py) for px, py in poly]))


class ChartWizardDialog(QDialog):
    """Excel 2003 Classic 4-step Chart Wizard."""

    chart_created = Signal(object, str)

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        workbook_model: WorkbookModel | None = None,
        initial_range: str = "$A$1:$D$5",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model
        self.workbook_model = workbook_model
        self.initial_range = initial_range
        self.current_step: int = 0  # 0..3

        # Selection state
        self.selected_type_id: str = "column"
        self.selected_subtype_id: str = "clustered"
        self.data_range: str = initial_range
        self.series_in_rows: bool = False  # False = columns, True = rows

        self._syncing_series: bool = False
        self.series_list: list[dict[str, str]] = [
            {
                "name": "=Sheet1!$B$1",
                "values": "=Sheet1!$B$2:$B$5",
                "x_values": "=Sheet1!$A$2:$A$5",
            },
            {
                "name": "=Sheet1!$C$1",
                "values": "=Sheet1!$C$2:$C$5",
                "x_values": "=Sheet1!$A$2:$A$5",
            },
        ]

        # Chart Options state
        self.chart_title: str = ""
        self.x_axis_title: str = ""
        self.y_axis_title: str = ""
        self.show_legend: bool = True
        self.legend_placement: str = "right"
        self.show_major_x_grid: bool = False
        self.show_major_y_grid: bool = True
        self.data_labels_type: str = "none"
        self.show_data_table: bool = False

        # Location state
        self.location_as_new_sheet: bool = False
        self.new_sheet_name: str = "Chart1"
        self.existing_sheet_name: str = ""

        if sheet_model and hasattr(sheet_model, "name"):
            self.existing_sheet_name = sheet_model.name

        self._init_ui()
        self._update_step_view()

    def _init_ui(self) -> None:
        self.resize(620, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # Stacked pages
        self.stack = QStackedWidget(self)
        root_layout.addWidget(self.stack, 1)

        self.page1 = self._build_page1()
        self.page2 = self._build_page2()
        self.page3 = self._build_page3()
        self.page4 = self._build_page4()

        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)
        self.stack.addWidget(self.page4)

        # Bottom navigation button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_cancel = QPushButton(safe_tr("取消(&C)"), self)
        self.btn_back = QPushButton(safe_tr("< 上一步(&B)"), self)
        self.btn_next = QPushButton(safe_tr("下一步(&N) >"), self)
        self.btn_finish = QPushButton(safe_tr("完成(&F)"), self)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_back.clicked.connect(self._on_back)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_finish.clicked.connect(self._on_finish)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_next)
        btn_layout.addWidget(self.btn_finish)

        root_layout.addLayout(btn_layout)

    # -------------------------------------------------------------
    # Step 1: Chart Type
    # -------------------------------------------------------------
    def _build_page1(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs_type = QTabWidget(page)
        tab_standard = QWidget()
        tab_layout = QHBoxLayout(tab_standard)
        tab_layout.setContentsMargins(8, 8, 8, 8)
        tab_layout.setSpacing(10)

        # Left: Chart types list
        left_box = QGroupBox(safe_tr("图表类型(&T):"), tab_standard)
        left_layout = QVBoxLayout(left_box)
        self.list_types = QListWidget(left_box)
        for item in CHART_TYPES:
            w_item = QListWidgetItem(f"{item['name']} ({item['name_en']})")
            w_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.list_types.addItem(w_item)
        self.list_types.setCurrentRow(0)
        self.list_types.currentRowChanged.connect(self._on_type_changed)
        left_layout.addWidget(self.list_types)
        tab_layout.addWidget(left_box, 1)

        # Right: Sub-types list + preview + description
        right_box = QGroupBox(safe_tr("子图表类型(&S):"), tab_standard)
        right_layout = QVBoxLayout(right_box)

        sub_top = QHBoxLayout()
        self.list_subtypes = QListWidget(right_box)
        self.list_subtypes.currentRowChanged.connect(self._on_subtype_changed)
        sub_top.addWidget(self.list_subtypes, 1)

        self.preview_sample = ChartSamplePreviewWidget(right_box)
        sub_top.addWidget(self.preview_sample)
        right_layout.addLayout(sub_top, 2)

        self.lbl_desc = QLabel(right_box)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet(
            "background-color: #F7F7F7; border: 1px solid #C0C0C0; padding: 6px;"
        )
        right_layout.addWidget(self.lbl_desc, 1)

        tab_layout.addWidget(right_box, 2)
        self.tabs_type.addTab(tab_standard, safe_tr("标准类型"))

        layout.addWidget(self.tabs_type)
        self._populate_subtypes(0)
        return page

    def _on_type_changed(self, row: int) -> None:
        if 0 <= row < len(CHART_TYPES):
            self.selected_type_id = CHART_TYPES[row]["id"]
            self._populate_subtypes(row)

    def _populate_subtypes(self, type_row: int) -> None:
        self.list_subtypes.clear()
        if not (0 <= type_row < len(CHART_TYPES)):
            return
        t_data = CHART_TYPES[type_row]
        for sub in t_data["subtypes"]:
            item = QListWidgetItem(sub[1])
            item.setData(Qt.ItemDataRole.UserRole, sub[0])
            self.list_subtypes.addItem(item)
        self.list_subtypes.setCurrentRow(0)

    def _on_subtype_changed(self, row: int) -> None:
        t_row = self.list_types.currentRow()
        if not (0 <= t_row < len(CHART_TYPES)):
            return
        subtypes = CHART_TYPES[t_row]["subtypes"]
        if 0 <= row < len(subtypes):
            self.selected_subtype_id = subtypes[row][0]
            self.lbl_desc.setText(f"<b>{subtypes[row][1]}</b>: {subtypes[row][2]}")
            self.preview_sample.set_chart_info(self.selected_type_id, self.selected_subtype_id)

    # -------------------------------------------------------------
    # Step 2: Source Data
    # -------------------------------------------------------------
    def _build_page2(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs_source = QTabWidget(page)

        # Tab 1: Data Range
        tab_range = QWidget()
        v_range = QVBoxLayout(tab_range)
        v_range.setSpacing(12)

        grp_range = QGroupBox(safe_tr("数据区域(&D):"), tab_range)
        h_range = QHBoxLayout(grp_range)
        self.edit_data_range = QLineEdit(self.data_range, grp_range)
        h_range.addWidget(self.edit_data_range)
        v_range.addWidget(grp_range)

        grp_series = QGroupBox(safe_tr("系列产生在:"), tab_range)
        h_series = QHBoxLayout(grp_series)
        self.radio_series_rows = QRadioButton(safe_tr("行(&R)"), grp_series)
        self.radio_series_cols = QRadioButton(safe_tr("列(&C)"), grp_series)
        self.radio_series_cols.setChecked(True)
        h_series.addWidget(self.radio_series_rows)
        h_series.addWidget(self.radio_series_cols)
        h_series.addStretch(1)
        v_range.addWidget(grp_series)
        v_range.addStretch(1)
        self.tabs_source.addTab(tab_range, safe_tr("数据区域"))

        # Tab 2: Series
        tab_series = QWidget()
        h_s = QHBoxLayout(tab_series)
        s_left = QVBoxLayout()
        self.list_series = QListWidget(tab_series)
        for idx, s in enumerate(self.series_list):
            name = s.get("name") or safe_tr(f"系列{idx + 1}")
            self.list_series.addItem(name)
        self.list_series.setCurrentRow(0)
        self.list_series.currentRowChanged.connect(self._on_series_selection_changed)
        s_left.addWidget(self.list_series)

        s_btn_layout = QHBoxLayout()
        self.btn_add_series = QPushButton(safe_tr("添加(&A)"), tab_series)
        self.btn_del_series = QPushButton(safe_tr("删除(&R)"), tab_series)
        self.btn_add_series.clicked.connect(self._on_add_series)
        self.btn_del_series.clicked.connect(self._on_del_series)
        s_btn_layout.addWidget(self.btn_add_series)
        s_btn_layout.addWidget(self.btn_del_series)
        s_left.addLayout(s_btn_layout)
        h_s.addLayout(s_left, 1)

        s_right = QGridLayout()
        s_right.addWidget(QLabel(safe_tr("名称(&N):")), 0, 0)
        first_name = self.series_list[0]["name"] if self.series_list else ""
        self.edit_series_name = QLineEdit(first_name, tab_series)
        self.edit_series_name.textChanged.connect(self._on_series_name_changed)
        s_right.addWidget(self.edit_series_name, 0, 1)

        s_right.addWidget(QLabel(safe_tr("值(&V):")), 1, 0)
        first_values = self.series_list[0]["values"] if self.series_list else ""
        self.edit_series_values = QLineEdit(first_values, tab_series)
        self.edit_series_values.textChanged.connect(self._on_series_values_changed)
        s_right.addWidget(self.edit_series_values, 1, 1)

        s_right.addWidget(QLabel(safe_tr("分类(X)轴标志(&T):")), 2, 0)
        first_x = self.series_list[0]["x_values"] if self.series_list else ""
        self.edit_series_x = QLineEdit(first_x, tab_series)
        self.edit_series_x.textChanged.connect(self._on_series_x_changed)
        s_right.addWidget(self.edit_series_x, 2, 1)
        h_s.addLayout(s_right, 2)

        self.tabs_source.addTab(tab_series, safe_tr("系列"))
        layout.addWidget(self.tabs_source)
        return page

    def _on_series_selection_changed(self, row: int) -> None:
        if self._syncing_series or not (0 <= row < len(self.series_list)):
            return
        self._syncing_series = True
        s = self.series_list[row]
        self.edit_series_name.setText(s.get("name", ""))
        self.edit_series_values.setText(s.get("values", ""))
        self.edit_series_x.setText(s.get("x_values", ""))
        self._syncing_series = False

    def _on_series_name_changed(self, text: str) -> None:
        if self._syncing_series:
            return
        row = self.list_series.currentRow()
        if 0 <= row < len(self.series_list):
            self.series_list[row]["name"] = text
            item = self.list_series.item(row)
            if item is not None:
                item.setText(text or safe_tr(f"系列{row + 1}"))

    def _on_series_values_changed(self, text: str) -> None:
        if self._syncing_series:
            return
        row = self.list_series.currentRow()
        if 0 <= row < len(self.series_list):
            self.series_list[row]["values"] = text

    def _on_series_x_changed(self, text: str) -> None:
        if self._syncing_series:
            return
        row = self.list_series.currentRow()
        if 0 <= row < len(self.series_list):
            self.series_list[row]["x_values"] = text

    def _on_add_series(self) -> None:
        idx = len(self.series_list) + 1
        new_name = safe_tr(f"系列{idx}")
        new_s = {"name": new_name, "values": "", "x_values": ""}
        self.series_list.append(new_s)
        self.list_series.addItem(new_name)
        self.list_series.setCurrentRow(len(self.series_list) - 1)

    def _on_del_series(self) -> None:
        if len(self.series_list) <= 1:
            return
        row = self.list_series.currentRow()
        if 0 <= row < len(self.series_list):
            self._syncing_series = True
            del self.series_list[row]
            self.list_series.takeItem(row)
            next_row = min(row, len(self.series_list) - 1)
            self._syncing_series = False
            self.list_series.setCurrentRow(next_row)

    # -------------------------------------------------------------
    # Step 3: Chart Options
    # -------------------------------------------------------------
    def _build_page3(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs_options = QTabWidget(page)

        # Tab 1: Titles
        tab_titles = QWidget()
        grid_titles = QGridLayout(tab_titles)
        grid_titles.addWidget(QLabel(safe_tr("图表标题(&T):")), 0, 0)
        self.edit_title = QLineEdit(tab_titles)
        grid_titles.addWidget(self.edit_title, 0, 1)

        grid_titles.addWidget(QLabel(safe_tr("分类(X)轴(&C):")), 1, 0)
        self.edit_x_title = QLineEdit(tab_titles)
        grid_titles.addWidget(self.edit_x_title, 1, 1)

        grid_titles.addWidget(QLabel(safe_tr("数值(Y)轴(&V):")), 2, 0)
        self.edit_y_title = QLineEdit(tab_titles)
        grid_titles.addWidget(self.edit_y_title, 2, 1)
        self.tabs_options.addTab(tab_titles, safe_tr("标题"))

        # Tab 2: Axes
        tab_axes = QWidget()
        v_axes = QVBoxLayout(tab_axes)
        grp_x = QGroupBox(safe_tr("分类(X)轴"), tab_axes)
        v_x = QVBoxLayout(grp_x)
        self.check_axis_x = QCheckBox(safe_tr("自动(&A)"), grp_x)
        self.check_axis_x.setChecked(True)
        v_x.addWidget(self.check_axis_x)
        v_axes.addWidget(grp_x)

        grp_y = QGroupBox(safe_tr("数值(Y)轴"), tab_axes)
        v_y = QVBoxLayout(grp_y)
        self.check_axis_y = QCheckBox(safe_tr("自动(&U)"), grp_y)
        self.check_axis_y.setChecked(True)
        v_y.addWidget(self.check_axis_y)
        v_axes.addWidget(grp_y)
        v_axes.addStretch(1)
        self.tabs_options.addTab(tab_axes, safe_tr("坐标轴"))

        # Tab 3: Gridlines
        tab_grids = QWidget()
        v_grids = QVBoxLayout(tab_grids)
        self.check_major_x_grid = QCheckBox(safe_tr("分类(X)轴主要网格线(&M)"), tab_grids)
        self.check_major_y_grid = QCheckBox(safe_tr("数值(Y)轴主要网格线(&J)"), tab_grids)
        self.check_major_y_grid.setChecked(True)
        v_grids.addWidget(self.check_major_x_grid)
        v_grids.addWidget(self.check_major_y_grid)
        v_grids.addStretch(1)
        self.tabs_options.addTab(tab_grids, safe_tr("网格线"))

        # Tab 4: Legend
        tab_legend = QWidget()
        v_leg = QVBoxLayout(tab_legend)
        self.check_show_legend = QCheckBox(safe_tr("显示图例(&S)"), tab_legend)
        self.check_show_legend.setChecked(True)
        v_leg.addWidget(self.check_show_legend)

        grp_pos = QGroupBox(safe_tr("位置:"), tab_legend)
        g_pos = QGridLayout(grp_pos)
        self.radio_leg_bottom = QRadioButton(safe_tr("底部(&B)"), grp_pos)
        self.radio_leg_corner = QRadioButton(safe_tr("右上角(&C)"), grp_pos)
        self.radio_leg_top = QRadioButton(safe_tr("顶部(&T)"), grp_pos)
        self.radio_leg_right = QRadioButton(safe_tr("靠右(&R)"), grp_pos)
        self.radio_leg_left = QRadioButton(safe_tr("靠左(&L)"), grp_pos)
        self.radio_leg_right.setChecked(True)
        g_pos.addWidget(self.radio_leg_bottom, 0, 0)
        g_pos.addWidget(self.radio_leg_corner, 0, 1)
        g_pos.addWidget(self.radio_leg_top, 1, 0)
        g_pos.addWidget(self.radio_leg_right, 1, 1)
        g_pos.addWidget(self.radio_leg_left, 2, 0)
        v_leg.addWidget(grp_pos)
        v_leg.addStretch(1)
        self.tabs_options.addTab(tab_legend, safe_tr("图例"))

        # Tab 5: Data Labels
        tab_labels = QWidget()
        v_labels = QVBoxLayout(tab_labels)
        grp_labels = QGroupBox(safe_tr("数据标签包括:"), tab_labels)
        v_lbl_grp = QVBoxLayout(grp_labels)
        self.radio_lbl_none = QRadioButton(safe_tr("无(&N)"), grp_labels)
        self.radio_lbl_series = QRadioButton(safe_tr("系列名称(&S)"), grp_labels)
        self.radio_lbl_cat = QRadioButton(safe_tr("类别名称(&C)"), grp_labels)
        self.radio_lbl_val = QRadioButton(safe_tr("值(&V)"), grp_labels)
        self.radio_lbl_pct = QRadioButton(safe_tr("百分比(&P)"), grp_labels)
        self.radio_lbl_none.setChecked(True)
        for r in (
            self.radio_lbl_none,
            self.radio_lbl_series,
            self.radio_lbl_cat,
            self.radio_lbl_val,
            self.radio_lbl_pct,
        ):
            v_lbl_grp.addWidget(r)
        v_labels.addWidget(grp_labels)
        v_labels.addStretch(1)
        self.tabs_options.addTab(tab_labels, safe_tr("数据标志"))

        # Tab 6: Data Table
        tab_table = QWidget()
        v_table = QVBoxLayout(tab_table)
        self.check_show_data_table = QCheckBox(safe_tr("显示数据表(&D)"), tab_table)
        self.check_show_legend_keys = QCheckBox(safe_tr("显示图例项标示(&S)"), tab_table)
        v_table.addWidget(self.check_show_data_table)
        v_table.addWidget(self.check_show_legend_keys)
        v_table.addStretch(1)
        self.tabs_options.addTab(tab_table, safe_tr("数据表"))

        layout.addWidget(self.tabs_options)
        return page

    # -------------------------------------------------------------
    # Step 4: Chart Location
    # -------------------------------------------------------------
    def _build_page4(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        grp_loc = QGroupBox(safe_tr("将图表放置于:"), page)
        v_loc = QVBoxLayout(grp_loc)
        v_loc.setSpacing(10)

        h_new = QHBoxLayout()
        self.radio_loc_new = QRadioButton(safe_tr("作为新工作表插入(&A):"), grp_loc)
        self.edit_new_sheet_name = QLineEdit("Chart1", grp_loc)
        h_new.addWidget(self.radio_loc_new)
        h_new.addWidget(self.edit_new_sheet_name)
        v_loc.addLayout(h_new)

        h_obj = QHBoxLayout()
        self.radio_loc_obj = QRadioButton(safe_tr("作为其中的对象插入(&O):"), grp_loc)
        self.radio_loc_obj.setChecked(True)
        self.combo_sheets = QComboBox(grp_loc)
        if self.workbook_model and hasattr(self.workbook_model, "sheets"):
            for s in self.workbook_model.sheets:
                self.combo_sheets.addItem(s.name)
        elif self.existing_sheet_name:
            self.combo_sheets.addItem(self.existing_sheet_name)
        else:
            self.combo_sheets.addItem("Sheet1")
        h_obj.addWidget(self.radio_loc_obj)
        h_obj.addWidget(self.combo_sheets)
        v_loc.addLayout(h_obj)

        layout.addWidget(grp_loc)
        layout.addStretch(1)
        return page

    # -------------------------------------------------------------
    # Step Navigation & Handlers
    # -------------------------------------------------------------
    def _update_step_view(self) -> None:
        self.stack.setCurrentIndex(self.current_step)
        titles = [
            safe_tr("图表向导 - 4 步骤之 1 - 图表类型"),
            safe_tr("图表向导 - 4 步骤之 2 - 图表源数据"),
            safe_tr("图表向导 - 4 步骤之 3 - 图表选项"),
            safe_tr("图表向导 - 4 步骤之 4 - 图表位置"),
        ]
        self.setWindowTitle(titles[self.current_step])
        self.btn_back.setEnabled(self.current_step > 0)
        self.btn_next.setEnabled(self.current_step < 3)

    def _on_back(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step_view()

    def _on_next(self) -> None:
        if self.current_step < 3:
            self.current_step += 1
            self._update_step_view()

    def _on_finish(self) -> None:
        # Gather all parameters
        self.data_range = self.edit_data_range.text().strip()
        self.series_in_rows = self.radio_series_rows.isChecked()
        self.chart_title = self.edit_title.text().strip()
        self.x_axis_title = self.edit_x_title.text().strip()
        self.y_axis_title = self.edit_y_title.text().strip()
        self.show_legend = self.check_show_legend.isChecked()
        self.show_major_x_grid = self.check_major_x_grid.isChecked()
        self.show_major_y_grid = self.check_major_y_grid.isChecked()
        self.show_data_table = self.check_show_data_table.isChecked()
        self.location_as_new_sheet = self.radio_loc_new.isChecked()
        self.new_sheet_name = self.edit_new_sheet_name.text().strip() or "Chart1"
        self.existing_sheet_name = self.combo_sheets.currentText() or "Sheet1"

        # Construct FloatingObject
        chart_obj = FloatingObject(
            id=101,
            name=self.chart_title or f"Chart ({self.selected_type_id})",
            kind="chart",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=1, row=2),
            to_point=CellAnchorPoint(col=8, row=16),
            text=self.chart_title or safe_tr("图表"),
        )

        # Attach to sheet model drawings if requested as object in sheet
        if not self.location_as_new_sheet and self.sheet_model is not None:
            if not hasattr(self.sheet_model, "drawings"):
                self.sheet_model.drawings = []
            chart_obj.id = len(self.sheet_model.drawings) + 1
            self.sheet_model.drawings.append(chart_obj)

        target = self.new_sheet_name if self.location_as_new_sheet else self.existing_sheet_name
        self.chart_created.emit(chart_obj, target)
        self.accept()

    def get_chart_spec(self) -> dict[str, Any]:
        """Return full chart configuration dictionary."""
        return {
            "type": self.selected_type_id,
            "sub_type": self.selected_subtype_id,
            "data_range": self.data_range,
            "series_in": "rows" if self.series_in_rows else "columns",
            "title": self.chart_title,
            "x_axis_title": self.x_axis_title,
            "y_axis_title": self.y_axis_title,
            "show_legend": self.show_legend,
            "legend_placement": self.legend_placement,
            "show_major_x_grid": self.show_major_x_grid,
            "show_major_y_grid": self.show_major_y_grid,
            "data_labels": self.data_labels_type,
            "show_data_table": self.show_data_table,
            "as_new_sheet": self.location_as_new_sheet,
            "sheet_name": (
                self.new_sheet_name if self.location_as_new_sheet else self.existing_sheet_name
            ),
            "series": [dict(s) for s in self.series_list],
        }

    def set_sheet_model(self, sheet_model: SheetDataModel | None) -> None:
        """Switch target sheet model cleanly without retaining stale reference."""
        self.sheet_model = sheet_model
        if sheet_model and hasattr(sheet_model, "name"):
            self.existing_sheet_name = sheet_model.name
            if hasattr(self, "combo_sheets"):
                idx = self.combo_sheets.findText(sheet_model.name)
                if idx >= 0:
                    self.combo_sheets.setCurrentIndex(idx)
                else:
                    self.combo_sheets.addItem(sheet_model.name)
                    self.combo_sheets.setCurrentText(sheet_model.name)

    def retranslate_ui(self) -> None:
        """Update all text strings dynamically for i18n."""
        self.btn_cancel.setText(safe_tr("取消(&C)"))
        self.btn_back.setText(safe_tr("< 上一步(&B)"))
        self.btn_next.setText(safe_tr("下一步(&N) >"))
        self.btn_finish.setText(safe_tr("完成(&F)"))
        if hasattr(self, "btn_add_series"):
            self.btn_add_series.setText(safe_tr("添加(&A)"))
        if hasattr(self, "btn_del_series"):
            self.btn_del_series.setText(safe_tr("删除(&R)"))
        self._update_step_view()
