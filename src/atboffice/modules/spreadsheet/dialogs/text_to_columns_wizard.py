"""Classic Excel 2003 3-step Convert Text to Columns Wizard Dialog."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
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

from atboffice.modules.spreadsheet.calc.references import cell_name

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Safely translate TextToColumnsWizard UI text."""
    return QCoreApplication.translate("TextToColumnsWizard", text)


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
                cell_vals = [
                    str(sheet_model.get_cell_value(r, c) or "")
                    for c in range(c1, c2 + 1)
                ]
                # Join row cells or take first column cell
                line = " ".join(v for v in cell_vals if v)
                self.raw_lines.append(line)

        if not self.raw_lines:
            self.raw_lines = ["Sample,Data,Row,1", "Another,Test,Row,2"]

        # Step 1 state
        self.is_delimited: bool = True
        self.start_row: int = 1

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

    # -------------------------------------------------------------
    # Step 2: Delimiters
    # -------------------------------------------------------------
    def _build_page2(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        grp_delim = QGroupBox(safe_tr("分隔符号:"), page)
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

        for chk in (self.chk_tab, self.chk_semicolon, self.chk_comma, self.chk_space, self.chk_other, self.chk_consecutive):
            chk.stateChanged.connect(self._refresh_split_preview)
        self.edit_other.textChanged.connect(self._refresh_split_preview)
        self.combo_qualifier.currentIndexChanged.connect(self._refresh_split_preview)

        layout.addWidget(grp_delim)

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
        for r_btn in (self.radio_fmt_general, self.radio_fmt_text, self.radio_fmt_date, self.radio_fmt_skip):
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

    def _split_line(self, line: str) -> list[str]:
        delims = self._get_delimiters()
        pattern = "|".join(re.escape(d) for d in delims)
        if self.chk_consecutive.isChecked():
            pattern = f"({pattern})+"

        qual = self.combo_qualifier.currentText()
        if qual in ('"', "'"):
            # Simple quoted-token split
            regex = f'{qual}([^{qual}]*){qual}|(?:(?<={pattern})|^)([^{"".join(delims)}]*)(?={pattern}|$)'

        parts = re.split(pattern, line)
        return [p.strip('"\'') for p in parts]

    def _refresh_split_preview(self) -> None:
        start = self.spin_start_row.value() - 1
        lines = self.raw_lines[start : start + 20]
        rows: list[list[str]] = [self._split_line(l) for l in lines]

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
        self.table_p3.horizontalHeaderItem(self.selected_col).setText(header)

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
        self._update_step_view()
