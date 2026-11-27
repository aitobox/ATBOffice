"""Classic Excel 2003 3-step Convert Text to Columns Wizard Dialog."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFontDatabase,
    QFontMetricsF,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.ui.styles.luna_2003 import theme_tokens, ui_font

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


class FixedWidthRulerWidget(QWidget):
    """Interactive monospace ruler and break-line editor for Fixed-Width Text to Columns."""

    breaks_changed = Signal(list)

    RULER_HEIGHT = 26
    LEFT_MARGIN = 12
    MAX_PREVIEW_LINES = 12

    def __init__(
        self,
        lines: list[str] | None = None,
        breaks: list[int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._lines: list[str] = list(lines or [])[: self.MAX_PREVIEW_LINES]
        self.breaks: list[int] = sorted({int(b) for b in (breaks or []) if int(b) > 0})
        self._dragging_break: int | None = None
        self._hover_break: int | None = None
        self._mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._mono_font.setPointSizeF(max(9.0, float(ui_font().pointSizeF())))
        self._ruler_font = ui_font(8.0)
        self.setMouseTracking(True)
        self.setMinimumHeight(130)
        self.retranslate_ui()

    def _char_width(self) -> float:
        return max(6.0, float(QFontMetricsF(self._mono_font).horizontalAdvance("M")))

    def _line_height(self) -> float:
        return max(15.0, float(QFontMetricsF(self._mono_font).height()) + 2.0)

    def _x_for_col(self, col: int) -> float:
        return self.LEFT_MARGIN + col * self._char_width()

    def _col_from_x(self, x: float) -> int:
        return max(1, round((x - self.LEFT_MARGIN) / self._char_width()))

    def _find_break_near(self, x: float, tolerance: float = 5.0) -> int | None:
        best: int | None = None
        best_dist = tolerance + 1.0
        for b in self.breaks:
            dist = abs(x - self._x_for_col(b))
            if dist <= tolerance and dist < best_dist:
                best = b
                best_dist = dist
        return best

    def set_lines(self, lines: list[str]) -> None:
        self._lines = list(lines)[: self.MAX_PREVIEW_LINES]
        self.updateGeometry()
        self.update()

    def set_breaks(self, breaks: list[int]) -> None:
        normalized = sorted({int(b) for b in breaks if int(b) > 0})
        if normalized != self.breaks:
            self.breaks = normalized
            self.update()

    def sizeHint(self) -> QSize:
        max_chars = max([40] + [len(ln) for ln in self._lines] + self.breaks)
        w = int(self.LEFT_MARGIN * 2 + (max_chars + 4) * self._char_width())
        h = int(self.RULER_HEIGHT + max(5, len(self._lines)) * self._line_height() + 8)
        return QSize(max(420, w), max(130, h))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        tok = theme_tokens()
        w = self.width()
        h = self.height()

        # Preview canvas background & border
        painter.fillRect(0, 0, w, h, QColor("#FFFFFF"))
        painter.fillRect(0, 0, w, self.RULER_HEIGHT, QColor(tok.face))
        painter.setPen(QPen(QColor(tok.tb_border), 1))
        painter.drawLine(0, self.RULER_HEIGHT, w, self.RULER_HEIGHT)

        # Ruler ticks and labels (0, 5, 10, ...)
        cw = self._char_width()
        max_cols = max(10, int((w - self.LEFT_MARGIN) / cw))
        painter.setFont(self._ruler_font)
        ruler_text_pen = QPen(QColor("#222222"), 1)
        tick_pen = QPen(QColor("#666666"), 1)
        for col in range(0, max_cols + 1):
            x = self._x_for_col(col)
            if col % 10 == 0:
                tick_h = 10
            elif col % 5 == 0:
                tick_h = 7
            else:
                tick_h = 4
            painter.setPen(tick_pen)
            painter.drawLine(QPointF(x, self.RULER_HEIGHT - tick_h), QPointF(x, self.RULER_HEIGHT))
            if col % 10 == 0 or (col % 5 == 0 and cw * 5 >= 24):
                painter.setPen(ruler_text_pen)
                painter.drawText(
                    QRectF(x - 10, 2, 24, self.RULER_HEIGHT - 10),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    str(col),
                )

        # Preview text lines (up to 12 lines)
        painter.save()
        painter.setClipRect(
            QRectF(1, self.RULER_HEIGHT + 1, max(0, w - 2), max(0, h - self.RULER_HEIGHT - 2))
        )
        painter.setFont(self._mono_font)
        painter.setPen(QPen(QColor("#111111"), 1))
        fm = QFontMetricsF(self._mono_font)
        lh = self._line_height()
        ascent = fm.ascent()
        for row_idx, line in enumerate(self._lines[: self.MAX_PREVIEW_LINES]):
            y = self.RULER_HEIGHT + 4 + row_idx * lh + ascent
            painter.drawText(QPointF(self.LEFT_MARGIN, y), line)
        painter.restore()

        # Vertical break lines + top triangles
        for b in self.breaks:
            bx = self._x_for_col(b)
            is_active = b in (self._dragging_break, self._hover_break)
            col_accent = QColor(tok.highlight) if is_active else QColor("#C62828")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(col_accent))
            tri = QPolygonF(
                [
                    QPointF(bx - 4.5, self.RULER_HEIGHT - 8),
                    QPointF(bx + 4.5, self.RULER_HEIGHT - 8),
                    QPointF(bx, self.RULER_HEIGHT - 1),
                ]
            )
            painter.drawPolygon(tri)
            painter.setPen(QPen(col_accent, 2.0 if is_active else 1.5))
            painter.drawLine(QPointF(bx, self.RULER_HEIGHT - 1), QPointF(bx, h - 1))

        # Outer frame
        painter.setPen(QPen(QColor(tok.tb_border), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, max(0, w - 1), max(0, h - 1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        x = event.position().x()
        hit = self._find_break_near(x)
        if hit is not None:
            self._dragging_break = hit
        else:
            col = self._col_from_x(x)
            if col not in self.breaks:
                self.breaks = sorted([*self.breaks, col])
                self._dragging_break = col
                self._hover_break = col
                self.breaks_changed.emit(list(self.breaks))
                self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        x = event.position().x()
        if self._dragging_break is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            new_col = self._col_from_x(x)
            if new_col != self._dragging_break:
                others = [b for b in self.breaks if b != self._dragging_break]
                if new_col not in others:
                    self.breaks = sorted([*others, new_col])
                    self._dragging_break = new_col
                    self._hover_break = new_col
                    self.breaks_changed.emit(list(self.breaks))
                    self.update()
            event.accept()
            return

        hover = self._find_break_near(x)
        if hover != self._hover_break:
            self._hover_break = hover
            self.setCursor(
                Qt.CursorShape.SplitHCursor if hover is not None else Qt.CursorShape.ArrowCursor
            )
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging_break is not None:
            self._dragging_break = None
            self.update()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._find_break_near(event.position().x())
            if hit is not None:
                self.breaks = [b for b in self.breaks if b != hit]
                self._dragging_break = None
                self._hover_break = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.breaks_changed.emit(list(self.breaks))
                self.update()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def retranslate_ui(self) -> None:
        self.setToolTip(safe_tr("单击插入分列线，拖动调整位置，双击删除分列线"))


class TextToColumnsWizard(QDialog):
    """Excel 2003 classic 3-step Text to Columns Wizard dialog."""

    completed = Signal(list)

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        selected_range: tuple[int, int, int, int] | None = None,
        sample_texts: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model
        self.selected_range = selected_range or (0, 0, 0, 0)
        self.current_step: int = 0

        # Collect raw text lines from selected cells or passed sample_texts
        self.raw_lines: list[str] = []
        if sample_texts:
            self.raw_lines = list(sample_texts)
        elif sheet_model is not None:
            r1, c1, r2, c2 = self.selected_range
            for r in range(r1, r2 + 1):
                cell_vals = [str(sheet_model.get_cell_value(r, c) or "") for c in range(c1, c2 + 1)]
                # Join row cells or take first column cell
                line = " ".join(v for v in cell_vals if v)
                self.raw_lines.append(line)

        if not self.raw_lines:
            self.raw_lines = ["Sample,Data,Row,1", "Another,Test,Row,2"]

        # Step 1 state
        self.is_delimited: bool = True
        self.start_row: int = 1
        self._syncing_breaks: bool = False

        # Step 2 state
        self.use_tab: bool = True
        self.use_semicolon: bool = False
        self.use_comma: bool = True
        self.use_space: bool = False
        self.use_other: bool = False
        self.other_char: str = ""
        self.consecutive_as_one: bool = False
        self.text_qualifier: str = '"'

        # Step 3 state
        self.column_formats: dict[int, str] = {}  # col_idx -> "General" | "Text" | "Date" | "Skip"
        self.selected_col: int = 0
        r1, c1 = self.selected_range[0], self.selected_range[1]
        self.destination: str = f"${cell_name(r1, c1)}"

        self._init_ui()
        self._update_step_view()

    def _init_ui(self) -> None:
        self.resize(650, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # Header instructions
        self.lbl_instruction = QLabel(self)
        self.lbl_instruction.setWordWrap(True)
        root_layout.addWidget(self.lbl_instruction)

        # Stacked pages
        self.stack = QStackedWidget(self)
        root_layout.addWidget(self.stack, 1)

        self.page1 = self._build_page1()
        self.page2 = self._build_page2()
        self.page3 = self._build_page3()

        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)

        # Navigation buttons
        btn_layout = QHBoxLayout()
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
    # Step 1: Delimited vs Fixed Width
    # -------------------------------------------------------------
    def _build_page1(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        grp_type = QGroupBox(safe_tr("原始数据类型:"), page)
        v_type = QVBoxLayout(grp_type)
        v_type.setSpacing(8)

        self.radio_delimited = QRadioButton(
            safe_tr("分隔符号 - 例如逗号或制表符等字符分割每个字段。(&D)"), grp_type
        )
        self.radio_delimited.setChecked(True)
        self.radio_fixed = QRadioButton(
            safe_tr("固定宽度 - 每列字段对齐，并在列间包含空格。(&W)"), grp_type
        )
        v_type.addWidget(self.radio_delimited)
        v_type.addWidget(self.radio_fixed)
        layout.addWidget(grp_type)

        h_start = QHBoxLayout()
        h_start.addWidget(QLabel(safe_tr("导入起始行(&R):")))
        self.spin_start_row = QSpinBox(page)
        self.spin_start_row.setRange(1, max(1, len(self.raw_lines)))
        self.spin_start_row.setValue(1)
        self.spin_start_row.valueChanged.connect(self._on_start_row_changed)
        h_start.addWidget(self.spin_start_row)
        h_start.addStretch(1)
        layout.addLayout(h_start)

        grp_preview = QGroupBox(safe_tr("选定区域数据的预览:"), page)
        v_p = QVBoxLayout(grp_preview)
        self.edit_p1_preview = QPlainTextEdit(grp_preview)
        self.edit_p1_preview.setReadOnly(True)
        self._refresh_p1_preview()
        v_p.addWidget(self.edit_p1_preview)
        layout.addWidget(grp_preview, 1)

        return page

    def _refresh_p1_preview(self) -> None:
        start = self.spin_start_row.value() - 1
        lines = self.raw_lines[start : start + 15]
        self.edit_p1_preview.setPlainText("\n".join(lines))

    def _on_start_row_changed(self, val: int) -> None:
        self.start_row = val
        self._refresh_p1_preview()
        if hasattr(self, "ruler_widget"):
            start = max(0, val - 1)
            self.ruler_widget.set_lines(self.raw_lines[start : start + 12])

    # -------------------------------------------------------------
    # Step 2: Delimiters
    # -------------------------------------------------------------
    def _build_page2(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        grp_delim = QGroupBox(safe_tr("分隔符号:"), page)
        self.grp_delim = grp_delim
        grid_d = QGridLayout(grp_delim)
        grid_d.setHorizontalSpacing(16)

        self.chk_tab = QCheckBox(safe_tr("Tab 键(&T)"), grp_delim)
        self.chk_semicolon = QCheckBox(safe_tr("分号(&M)"), grp_delim)
        self.chk_comma = QCheckBox(safe_tr("逗号(&C)"), grp_delim)
        self.chk_comma.setChecked(True)
        self.chk_space = QCheckBox(safe_tr("空格(&S)"), grp_delim)
        self.chk_other = QCheckBox(safe_tr("其他(&O):"), grp_delim)
        self.edit_other = QLineEdit(grp_delim)
        self.edit_other.setMaxLength(1)
        self.edit_other.setFixedWidth(30)

        grid_d.addWidget(self.chk_tab, 0, 0)
        grid_d.addWidget(self.chk_semicolon, 0, 1)
        grid_d.addWidget(self.chk_comma, 1, 0)
        grid_d.addWidget(self.chk_space, 1, 1)

        h_other = QHBoxLayout()
        h_other.addWidget(self.chk_other)
        h_other.addWidget(self.edit_other)
        h_other.addStretch(1)
        grid_d.addLayout(h_other, 2, 0)

        self.chk_consecutive = QCheckBox(safe_tr("连续分隔符号视为单个处理(&R)"), grp_delim)
        grid_d.addWidget(self.chk_consecutive, 3, 0, 1, 2)

        h_qual = QHBoxLayout()
        h_qual.addWidget(QLabel(safe_tr("文本识别符号(&Q):")))
        self.combo_qualifier = QComboBox(grp_delim)
        self.combo_qualifier.addItems(['"', "'", "{none}"])
        h_qual.addWidget(self.combo_qualifier)
        h_qual.addStretch(1)
        grid_d.addLayout(h_qual, 4, 0, 1, 2)

        for chk in (
            self.chk_tab,
            self.chk_semicolon,
            self.chk_comma,
            self.chk_space,
            self.chk_other,
            self.chk_consecutive,
        ):
            chk.stateChanged.connect(self._refresh_split_preview)
        self.edit_other.textChanged.connect(self._refresh_split_preview)
        self.combo_qualifier.currentIndexChanged.connect(self._refresh_split_preview)

        layout.addWidget(grp_delim)

        # Fixed width: column break positions (character offsets), Excel step 2 "分列线".
        self.grp_fixed = QGroupBox(safe_tr("分列线:"), page)
        v_fixed = QVBoxLayout(self.grp_fixed)
        self.lbl_fixed_hint = QLabel(
            safe_tr("输入分列线所在的字符位置，多个位置用逗号分隔（例如 4, 10）。"),
            self.grp_fixed,
        )
        self.lbl_fixed_hint.setWordWrap(True)
        self.ruler_widget = FixedWidthRulerWidget(lines=self.raw_lines[:12], parent=self.grp_fixed)
        self.ruler_widget.breaks_changed.connect(self._on_ruler_breaks_changed)
        self.edit_breaks = QLineEdit(self.grp_fixed)
        self.edit_breaks.setPlaceholderText(safe_tr("例如：4, 10"))
        self.edit_breaks.textChanged.connect(self._on_breaks_text_changed)
        v_fixed.addWidget(self.lbl_fixed_hint)
        v_fixed.addWidget(self.ruler_widget)
        v_fixed.addWidget(self.edit_breaks)
        self.grp_fixed.setVisible(False)
        layout.addWidget(self.grp_fixed)

        grp_p2 = QGroupBox(safe_tr("数据预览:"), page)
        v_p2 = QVBoxLayout(grp_p2)
        self.table_p2 = QTableWidget(grp_p2)
        self.table_p2.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        v_p2.addWidget(self.table_p2)
        layout.addWidget(grp_p2, 1)

        return page

    # -------------------------------------------------------------
    # Step 3: Column Data Format
    # -------------------------------------------------------------
    def _build_page3(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        grp_fmt = QGroupBox(safe_tr("列数据格式:"), page)
        v_fmt = QVBoxLayout(grp_fmt)
        self.radio_fmt_general = QRadioButton(
            safe_tr("常规(&G) - “常规”数值转为数字，日期转为日期，其余转为文本。"), grp_fmt
        )
        self.radio_fmt_general.setChecked(True)
        self.radio_fmt_text = QRadioButton(safe_tr("文本(&T)"), grp_fmt)
        self.radio_fmt_date = QRadioButton(safe_tr("日期(&D):"), grp_fmt)
        self.combo_date_fmt = QComboBox(grp_fmt)
        self.combo_date_fmt.addItems(["YMD", "MDY", "DMY"])
        self.radio_fmt_skip = QRadioButton(safe_tr("不导入此列，跳过(&S)"), grp_fmt)

        v_fmt.addWidget(self.radio_fmt_general)
        v_fmt.addWidget(self.radio_fmt_text)

        h_d = QHBoxLayout()
        h_d.addWidget(self.radio_fmt_date)
        h_d.addWidget(self.combo_date_fmt)
        h_d.addStretch(1)
        v_fmt.addLayout(h_d)

        v_fmt.addWidget(self.radio_fmt_skip)
        layout.addWidget(grp_fmt)

        # Connect format radio changes
        for r_btn in (
            self.radio_fmt_general,
            self.radio_fmt_text,
            self.radio_fmt_date,
            self.radio_fmt_skip,
        ):
            r_btn.toggled.connect(self._on_format_changed)

        h_dest = QHBoxLayout()
        h_dest.addWidget(QLabel(safe_tr("目标区域(&D):")))
        self.edit_dest = QLineEdit(self.destination, page)
        h_dest.addWidget(self.edit_dest)
        layout.addLayout(h_dest)

        grp_p3 = QGroupBox(safe_tr("数据预览:"), page)
        v_p3 = QVBoxLayout(grp_p3)
        self.table_p3 = QTableWidget(grp_p3)
        self.table_p3.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_p3.currentCellChanged.connect(self._on_p3_cell_selected)
        v_p3.addWidget(self.table_p3)
        layout.addWidget(grp_p3, 1)

        return page

    # -------------------------------------------------------------
    # Parsing Engine & Preview
    # -------------------------------------------------------------
    def _get_delimiters(self) -> list[str]:
        delims = []
        if self.chk_tab.isChecked():
            delims.append("\t")
        if self.chk_semicolon.isChecked():
            delims.append(";")
        if self.chk_comma.isChecked():
            delims.append(",")
        if self.chk_space.isChecked():
            delims.append(" ")
        if self.chk_other.isChecked() and self.edit_other.text():
            delims.append(self.edit_other.text())
        return delims or [","]

    def get_fixed_breaks(self) -> list[int]:
        """Parse the column break positions typed for fixed-width splitting."""
        breaks: list[int] = []
        for part in re.split(r"[,;\s]+", self.edit_breaks.text()):
            if part.isdigit() and int(part) > 0:
                breaks.append(int(part))
        return sorted(set(breaks))

    def _on_breaks_text_changed(self) -> None:
        if self._syncing_breaks:
            return
        self._syncing_breaks = True
        try:
            self.ruler_widget.set_breaks(self.get_fixed_breaks())
        finally:
            self._syncing_breaks = False
        self._refresh_split_preview()

    def _on_ruler_breaks_changed(self, breaks: list[int]) -> None:
        if self._syncing_breaks:
            return
        self._syncing_breaks = True
        try:
            self.edit_breaks.setText(", ".join(str(b) for b in breaks))
        finally:
            self._syncing_breaks = False
        self._refresh_split_preview()

    def _split_line(self, line: str) -> list[str]:
        if self.radio_fixed.isChecked():
            from atboffice.modules.spreadsheet.tools.data_tools import split_fixed_width

            return split_fixed_width(line, self.get_fixed_breaks())
        delims = self._get_delimiters()
        pattern = "|".join(re.escape(d) for d in delims)
        if self.chk_consecutive.isChecked():
            pattern = f"({pattern})+"

        parts = re.split(pattern, line)
        return [p.strip("\"'") for p in parts]

    def _refresh_split_preview(self) -> None:
        start = self.spin_start_row.value() - 1
        lines = self.raw_lines[start : start + 20]
        rows: list[list[str]] = [self._split_line(line_text) for line_text in lines]

        max_cols = max((len(r) for r in rows), default=1)
        for tbl in (self.table_p2, self.table_p3):
            tbl.clear()
            tbl.setRowCount(len(rows))
            tbl.setColumnCount(max_cols)

            headers = []
            for c in range(max_cols):
                fmt = self.column_formats.get(c, safe_tr("常规"))
                headers.append(fmt)
            tbl.setHorizontalHeaderLabels(headers)

            for r_idx, row in enumerate(rows):
                for c_idx in range(max_cols):
                    val = row[c_idx] if c_idx < len(row) else ""
                    tbl.setItem(r_idx, c_idx, QTableWidgetItem(val))

    def _on_p3_cell_selected(self, row: int, col: int, prev_row: int, prev_col: int) -> None:
        self.selected_col = col
        fmt = self.column_formats.get(col, "General")
        if fmt == "General":
            self.radio_fmt_general.setChecked(True)
        elif fmt == "Text":
            self.radio_fmt_text.setChecked(True)
        elif fmt.startswith("Date"):
            self.radio_fmt_date.setChecked(True)
        elif fmt == "Skip":
            self.radio_fmt_skip.setChecked(True)

    def _on_format_changed(self) -> None:
        if self.radio_fmt_general.isChecked():
            fmt = "General"
            header = safe_tr("常规")
        elif self.radio_fmt_text.isChecked():
            fmt = "Text"
            header = safe_tr("文本")
        elif self.radio_fmt_date.isChecked():
            fmt = f"Date({self.combo_date_fmt.currentText()})"
            header = safe_tr("日期")
        else:
            fmt = "Skip"
            header = safe_tr("跳过")

        self.column_formats[self.selected_col] = fmt
        hdr = self.table_p3.horizontalHeaderItem(self.selected_col)
        if hdr is not None:
            hdr.setText(header)

    # -------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------
    def _update_step_view(self) -> None:
        self.stack.setCurrentIndex(self.current_step)
        titles = [
            safe_tr("文本分列向导 - 3 步骤之 1"),
            safe_tr("文本分列向导 - 3 步骤之 2"),
            safe_tr("文本分列向导 - 3 步骤之 3"),
        ]
        instructions = [
            safe_tr("文本向导能够确定您的数据是由分隔符分隔的还是由固定宽度分隔的。"),
            safe_tr("此屏幕允许您设置数据中包含的分隔符。可以在下方的预览窗口中查看分割效果。"),
            safe_tr("此屏幕允许您选定每列并设置列数据格式。"),
        ]
        self.setWindowTitle(titles[self.current_step])
        self.lbl_instruction.setText(instructions[self.current_step])
        self.btn_back.setEnabled(self.current_step > 0)
        self.btn_next.setEnabled(self.current_step < 2)

        if self.current_step == 1:
            fixed = self.radio_fixed.isChecked()
            self.is_delimited = not fixed
            self.grp_delim.setVisible(not fixed)
            self.grp_fixed.setVisible(fixed)
            start = max(0, self.spin_start_row.value() - 1)
            self.ruler_widget.set_lines(self.raw_lines[start : start + 12])
            if fixed and not self.edit_breaks.text().strip():
                from atboffice.modules.spreadsheet.tools.data_tools import suggest_fixed_breaks

                guess = suggest_fixed_breaks(self.raw_lines)
                self.edit_breaks.setText(", ".join(str(b) for b in guess))
            else:
                self.ruler_widget.set_breaks(self.get_fixed_breaks())
            self._refresh_split_preview()
        elif self.current_step == 2:
            self._refresh_split_preview()

    def _on_back(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
            self._update_step_view()

    def _on_next(self) -> None:
        if self.current_step < 2:
            self.current_step += 1
            self._update_step_view()

    def get_split_result(self) -> list[list[Any]]:
        """Return the parsed matrix of row cells."""
        start = self.spin_start_row.value() - 1
        lines = self.raw_lines[start:]
        result: list[list[Any]] = []
        for line in lines:
            row_vals = self._split_line(line)
            processed_row = []
            for col_idx, val in enumerate(row_vals):
                fmt = self.column_formats.get(col_idx, "General")
                if fmt == "Skip":
                    continue
                elif fmt == "Text":
                    processed_row.append(str(val))
                else:  # General: try numeric
                    val_str = str(val).strip()
                    try:
                        if "." in val_str:
                            processed_row.append(float(val_str))
                        else:
                            processed_row.append(int(val_str))
                    except ValueError:
                        processed_row.append(val_str)
            result.append(processed_row)
        return result

    def _on_finish(self) -> None:
        parsed_rows = self.get_split_result()
        # If model is available, write back starting from destination cell
        if self.sheet_model is not None:
            dest_text = self.edit_dest.text().replace("$", "").strip()
            dest_r, dest_c = self.selected_range[0], self.selected_range[1]
            from atboffice.modules.spreadsheet.calc.goal_seek import parse_cell_reference

            ref = parse_cell_reference(dest_text)
            if ref:
                dest_r, dest_c = ref[1], ref[2]

            for r_offset, row_data in enumerate(parsed_rows):
                for c_offset, val in enumerate(row_data):
                    self.sheet_model.set_cell_value(dest_r + r_offset, dest_c + c_offset, val)

        self.completed.emit(parsed_rows)
        self.accept()

    def retranslate_ui(self) -> None:
        self.btn_cancel.setText(safe_tr("取消(&C)"))
        self.btn_back.setText(safe_tr("< 上一步(&B)"))
        self.btn_next.setText(safe_tr("下一步(&N) >"))
        self.btn_finish.setText(safe_tr("完成(&F)"))
        self.grp_fixed.setTitle(safe_tr("分列线:"))
        self.lbl_fixed_hint.setText(
            safe_tr("输入分列线所在的字符位置，多个位置用逗号分隔（例如 4, 10）。")
        )
        self.edit_breaks.setPlaceholderText(safe_tr("例如：4, 10"))
        self.ruler_widget.retranslate_ui()
        self._update_step_view()
