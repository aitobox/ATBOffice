"""Number format tab for FormatCellsDialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.drawing.numfmt import format_value


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("NumberFormatTab", text)


CATEGORIES = [
    ("General", "常规"),
    ("Number", "数值"),
    ("Currency", "货币"),
    ("Accounting", "会计专用"),
    ("Date", "日期"),
    ("Time", "时间"),
    ("Percentage", "百分比"),
    ("Fraction", "分数"),
    ("Scientific", "科学记数"),
    ("Text", "文本"),
    ("Special", "特殊"),
    ("Custom", "自定义"),
]

DATE_FORMATS = [
    'yyyy-mm-dd',
    'yyyy"年"m"月"d"日"',
    "m/d/yyyy",
    "d-mmm-yy",
    'yyyy"年"m"月"',
    'm"月"d"日"',
    "yyyy-mm-dd hh:mm:ss",
]

TIME_FORMATS = [
    "h:mm AM/PM",
    "h:mm:ss AM/PM",
    "hh:mm",
    "hh:mm:ss",
    "[h]:mm:ss",
]

FRACTION_FORMATS = [
    "# ?/?",
    "# ??/??",
    "# ???/???",
    "# ?/2",
    "# ?/4",
    "# ?/8",
    "# ?/16",
    "# ?/10",
    "# ?/100",
]

SPECIAL_FORMATS = [
    ("000000", "邮政编码"),
    ("[<=9999999]###-####;(###) ###-####", "电话号码"),
    ("000000000000000000", "身份证号"),
]

CUSTOM_DEFAULT_CODES = [
    "General",
    "0",
    "0.00",
    "#,##0",
    "#,##0.00",
    "#,##0_);(#,##0)",
    "#,##0_);[Red](#,##0)",
    "#,##0.00_);(#,##0.00)",
    "#,##0.00_);[Red](#,##0.00)",
    '"$"#,##0_);("$"#,##0)',
    '"$"#,##0_);[Red]("$"#,##0)',
    '"$"#,##0.00_);("$"#,##0.00)',
    '"$"#,##0.00_);[Red]("$"#,##0.00)',
    "0%",
    "0.00%",
    "0.00E+00",
    "##0.0E+0",
    "# ?/?",
    "# ??/??",
    "yyyy-mm-dd",
    "h:mm:ss",
    "@",
]


class NumberFormatTab(QWidget):
    """Tab 1: Number formatting options."""

    def __init__(
        self,
        current_format: str = "General",
        sample_value: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sample_value = sample_value if sample_value is not None else 1234.5
        self._current_format = current_format or "General"

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Left column: Category List
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)
        self.lbl_category = QLabel(safe_tr("分类(&C):"))
        self.cat_list = QListWidget()
        self.cat_list.setFixedWidth(130)
        for cat_en, cat_zh in CATEGORIES:
            item = QListWidgetItem(safe_tr(cat_zh))
            item.setData(Qt.ItemDataRole.UserRole, cat_en)
            self.cat_list.addItem(item)
        left_layout.addWidget(self.lbl_category)
        left_layout.addWidget(self.cat_list)
        main_layout.addLayout(left_layout)

        # Right column: Sample Box + Options + Description
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)

        # Sample box
        self.sample_group = QGroupBox(safe_tr("示例"))
        sample_inner = QVBoxLayout(self.sample_group)
        self.sample_label = QLabel()
        self.sample_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.sample_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 4px;"
        )
        sample_inner.addWidget(self.sample_label)
        right_layout.addWidget(self.sample_group)

        # Stacked options
        self.options_stack = QStackedWidget()
        self._build_options_panels()
        right_layout.addWidget(self.options_stack, 1)

        # Description
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #555555; padding-top: 4px;")
        right_layout.addWidget(self.desc_label)

        main_layout.addLayout(right_layout, 1)

        self.cat_list.currentRowChanged.connect(self._on_category_changed)
        self._select_category_for_code(self._current_format)
        self.update_sample()

    def _build_options_panels(self) -> None:
        """Create option panels for all categories."""
        # 0. General
        self.panel_general = QWidget()
        self.options_stack.addWidget(self.panel_general)

        # 1. Number
        self.panel_number = QWidget()
        n_layout = QVBoxLayout(self.panel_number)
        n_layout.setContentsMargins(0, 0, 0, 0)
        n_form = QFormLayout()
        self.decimals_spin = QSpinBox()
        self.decimals_spin.setRange(0, 30)
        self.decimals_spin.setValue(2)
        self.decimals_spin.valueChanged.connect(self._on_option_changed)
        self.lbl_decimals = QLabel(safe_tr("小数位数(&D):"))
        n_form.addRow(self.lbl_decimals, self.decimals_spin)

        self.sep_check = QCheckBox(safe_tr("使用千位分隔符 (,) (&U)"))
        self.sep_check.setChecked(False)
        self.sep_check.toggled.connect(self._on_option_changed)
        n_form.addRow(self.sep_check)
        n_layout.addLayout(n_form)

        self.lbl_neg = QLabel(safe_tr("负数(&N):"))
        self.neg_list = QListWidget()
        self.neg_list.setMaximumHeight(85)
        self.neg_list.addItems(
            ["-1234.10", "1234.10", "(1234.10)", "(1234.10)"]
        )
        self.neg_list.item(1).setForeground(QColor("#FF0000"))
        self.neg_list.item(3).setForeground(QColor("#FF0000"))
        self.neg_list.setCurrentRow(0)
        self.neg_list.currentRowChanged.connect(self._on_option_changed)
        n_layout.addWidget(self.lbl_neg)
        n_layout.addWidget(self.neg_list)
        self.options_stack.addWidget(self.panel_number)

        # 2. Currency
        self.panel_currency = QWidget()
        c_layout = QVBoxLayout(self.panel_currency)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_form = QFormLayout()
        self.curr_decimals_spin = QSpinBox()
        self.curr_decimals_spin.setRange(0, 30)
        self.curr_decimals_spin.setValue(2)
        self.curr_decimals_spin.valueChanged.connect(self._on_option_changed)
        self.decimals_spin.valueChanged.connect(self.curr_decimals_spin.setValue)
        c_form.addRow(safe_tr("小数位数(&D):"), self.curr_decimals_spin)

        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["$", "¥", "€", "£", safe_tr("无")])
        self.symbol_combo.currentIndexChanged.connect(self._on_option_changed)
        self.lbl_symbol = QLabel(safe_tr("货币符号(&S):"))
        c_form.addRow(self.lbl_symbol, self.symbol_combo)
        c_layout.addLayout(c_form)

        self.lbl_curr_neg = QLabel(safe_tr("负数(&N):"))
        self.curr_neg_list = QListWidget()
        self.curr_neg_list.setMaximumHeight(85)
        self.curr_neg_list.addItems(
            ["-$1,234.10", "$1,234.10", "($1,234.10)", "($1,234.10)"]
        )
        self.curr_neg_list.item(1).setForeground(QColor("#FF0000"))
        self.curr_neg_list.item(3).setForeground(QColor("#FF0000"))
        self.curr_neg_list.setCurrentRow(0)
        self.curr_neg_list.currentRowChanged.connect(self._on_option_changed)
        c_layout.addWidget(self.lbl_curr_neg)
        c_layout.addWidget(self.curr_neg_list)
        self.options_stack.addWidget(self.panel_currency)

        # 3. Accounting
        self.panel_accounting = QWidget()
        a_layout = QFormLayout(self.panel_accounting)
        a_layout.setContentsMargins(0, 0, 0, 0)
        self.acc_decimals_spin = QSpinBox()
        self.acc_decimals_spin.setRange(0, 30)
        self.acc_decimals_spin.setValue(2)
        self.acc_decimals_spin.valueChanged.connect(self._on_option_changed)
        self.decimals_spin.valueChanged.connect(self.acc_decimals_spin.setValue)
        a_layout.addRow(safe_tr("小数位数(&D):"), self.acc_decimals_spin)
        self.acc_symbol_combo = QComboBox()
        self.acc_symbol_combo.addItems(["$", "¥", "€", "£", safe_tr("无")])
        self.acc_symbol_combo.currentIndexChanged.connect(
            self._on_option_changed
        )
        a_layout.addRow(safe_tr("货币符号(&S):"), self.acc_symbol_combo)
        self.options_stack.addWidget(self.panel_accounting)

        # 4. Date
        self.panel_date = QWidget()
        d_layout = QVBoxLayout(self.panel_date)
        d_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_date_type = QLabel(safe_tr("类型(&T):"))
        self.date_list = QListWidget()
        self.date_list.addItems(DATE_FORMATS)
        self.date_list.setCurrentRow(0)
        self.date_list.currentRowChanged.connect(self._on_option_changed)
        d_layout.addWidget(self.lbl_date_type)
        d_layout.addWidget(self.date_list)
        self.options_stack.addWidget(self.panel_date)

        # 5. Time
        self.panel_time = QWidget()
        t_layout = QVBoxLayout(self.panel_time)
        t_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_time_type = QLabel(safe_tr("类型(&T):"))
        self.time_list = QListWidget()
        self.time_list.addItems(TIME_FORMATS)
        self.time_list.setCurrentRow(0)
        self.time_list.currentRowChanged.connect(self._on_option_changed)
        t_layout.addWidget(self.lbl_time_type)
        t_layout.addWidget(self.time_list)
        self.options_stack.addWidget(self.panel_time)

        # 6. Percentage
        self.panel_percent = QWidget()
        p_layout = QFormLayout(self.panel_percent)
        p_layout.setContentsMargins(0, 0, 0, 0)
        self.percent_decimals_spin = QSpinBox()
        self.percent_decimals_spin.setRange(0, 30)
        self.percent_decimals_spin.setValue(2)
        self.percent_decimals_spin.valueChanged.connect(self._on_option_changed)
        self.decimals_spin.valueChanged.connect(self.percent_decimals_spin.setValue)
        p_layout.addRow(safe_tr("小数位数(&D):"), self.percent_decimals_spin)
        self.options_stack.addWidget(self.panel_percent)

        # 7. Fraction
        self.panel_fraction = QWidget()
        fr_layout = QVBoxLayout(self.panel_fraction)
        fr_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_fraction = QLabel(safe_tr("类型(&T):"))
        self.fraction_list = QListWidget()
        self.fraction_list.addItems(FRACTION_FORMATS)
        self.fraction_list.setCurrentRow(0)
        self.fraction_list.currentRowChanged.connect(self._on_option_changed)
        fr_layout.addWidget(self.lbl_fraction)
        fr_layout.addWidget(self.fraction_list)
        self.options_stack.addWidget(self.panel_fraction)

        # 8. Scientific
        self.panel_sci = QWidget()
        s_layout = QFormLayout(self.panel_sci)
        s_layout.setContentsMargins(0, 0, 0, 0)
        self.sci_decimals_spin = QSpinBox()
        self.sci_decimals_spin.setRange(0, 30)
        self.sci_decimals_spin.setValue(2)
        self.sci_decimals_spin.valueChanged.connect(self._on_option_changed)
        self.decimals_spin.valueChanged.connect(self.sci_decimals_spin.setValue)
        self.options_stack.addWidget(self.panel_sci)

        # 9. Text
        self.panel_text = QWidget()
        self.options_stack.addWidget(self.panel_text)

        # 10. Special
        self.panel_special = QWidget()
        sp_layout = QVBoxLayout(self.panel_special)
        sp_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_special = QLabel(safe_tr("类型(&T):"))
        self.special_list = QListWidget()
        for code, label in SPECIAL_FORMATS:
            item = QListWidgetItem(safe_tr(label))
            item.setData(Qt.ItemDataRole.UserRole, code)
            self.special_list.addItem(item)
        self.special_list.setCurrentRow(0)
        self.special_list.currentRowChanged.connect(self._on_option_changed)
        sp_layout.addWidget(self.lbl_special)
        sp_layout.addWidget(self.special_list)
        self.options_stack.addWidget(self.panel_special)

        # 11. Custom
        self.panel_custom = QWidget()
        cu_layout = QVBoxLayout(self.panel_custom)
        cu_layout.setContentsMargins(0, 0, 0, 0)
        cu_form = QFormLayout()
        self.custom_edit = QLineEdit("General")
        self.custom_edit.textChanged.connect(self._on_custom_edit_changed)
        cu_form.addRow(safe_tr("类型(&T):"), self.custom_edit)
        cu_layout.addLayout(cu_form)

        self.custom_list = QListWidget()
        self.custom_list.addItems(CUSTOM_DEFAULT_CODES)
        self.custom_list.itemClicked.connect(
            lambda item: self.custom_edit.setText(item.text())
        )
        cu_layout.addWidget(self.custom_list)
        self.options_stack.addWidget(self.panel_custom)

    def _select_category_for_code(self, code: str) -> None:
        """Find appropriate category from format code."""
        if not code or code == "General":
            self.set_category("General")
            return
        if code == "@":
            self.set_category("Text")
            return
        if "%" in code:
            self.set_category("Percentage")
            return
        if "E+" in code or "E-" in code:
            self.set_category("Scientific")
            return
        if "?" in code and "/" in code:
            self.set_category("Fraction")
            return
        if any(sym in code for sym in ["$", "¥", "€", "£"]):
            if "_(" in code or "*) " in code:
                self.set_category("Accounting")
            else:
                self.set_category("Currency")
            return
        if any(
            token in code
            for token in ["yyyy", "yy", "mmm", "ddd", "m/d", "d-m"]
        ):
            self.set_category("Date")
            return
        if any(token in code for token in ["h:mm", "hh:mm", "AM/PM", "ss"]):
            self.set_category("Time")
            return
        if any(
            code.startswith(fmt)
            for fmt in ["0", "0.", "#,##0", "#,##0.", "0.0"]
        ):
            self.set_category("Number")
            return

        self.set_category("Custom")
        self.custom_edit.setText(code)

    def get_category(self) -> str:
        item = self.cat_list.currentItem()
        return (
            item.data(Qt.ItemDataRole.UserRole)
            if item is not None
            else "General"
        )

    def set_category(self, cat_en: str) -> None:
        for i in range(self.cat_list.count()):
            item = self.cat_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == cat_en:
                self.cat_list.setCurrentRow(i)
                break

    def _on_category_changed(self, row: int) -> None:
        if row < 0:
            return
        self.options_stack.setCurrentIndex(row)
        cat_en = self.get_category()

        descriptions = {
            "General": safe_tr(
                "常规单元格格式不包含任何特定的数字格式。"
            ),
            "Number": safe_tr(
                "数值格式用于一般数字的显示。货币和会计专用格式提供货币值计算的专用格式。"
            ),
            "Currency": safe_tr(
                "货币格式用于表示一般货币数值。使用会计专用格式可以使一列中的货币符号和十进制小数点对齐。"
            ),
            "Accounting": safe_tr(
                "会计专用格式可使一列中的货币符号和十进制小数点对齐。"
            ),
            "Date": safe_tr(
                "日期格式将日期和时间系列数值显示为日期值。"
            ),
            "Time": safe_tr(
                "时间格式将日期和时间系列数值显示为时间值。"
            ),
            "Percentage": safe_tr(
                "百分比格式将单元格数值乘以 100，并以带有百分号 (%) 的形式显示结果。"
            ),
            "Fraction": safe_tr(
                "分数格式根据指定的分母显示小数部分。"
            ),
            "Scientific": safe_tr(
                "科学记数格式以指数形式显示数字（例如 1.23E+03）。"
            ),
            "Text": safe_tr(
                "在文本单元格格式中，即使单元格中包含数字，也按文本形式处理。输入内容将原样显示。"
            ),
            "Special": safe_tr(
                "特殊格式用于跟踪列表和数据库中的特定数据值。"
            ),
            "Custom": safe_tr(
                "以现有格式代码为基础，输入自定义的数字格式代码。"
            ),
        }
        self.desc_label.setText(descriptions.get(cat_en, ""))
        self.update_sample()

    def _on_option_changed(self) -> None:
        self.update_sample()

    def _on_custom_edit_changed(self, text: str) -> None:
        self.update_sample()

    def get_format_code(self) -> str:
        cat = self.get_category()
        if cat == "General":
            return "General"
        elif cat == "Number":
            dec = self.decimals_spin.value()
            sep = self.sep_check.isChecked()
            neg_idx = self.neg_list.currentRow()
            dec_str = ("." + "0" * dec) if dec > 0 else ""
            int_str = "#,##0" if sep else "0"
            base = int_str + dec_str

            if neg_idx == 1:
                return f"{base};[Red]{base}"
            elif neg_idx == 2:
                return f"{base};({base})"
            elif neg_idx == 3:
                return f"{base};[Red]({base})"
            return base

        elif cat == "Currency":
            dec = self.curr_decimals_spin.value()
            sym = self.symbol_combo.currentText()
            sym_part = f'"{sym}"' if sym and sym != safe_tr("无") else ""
            neg_idx = self.curr_neg_list.currentRow()
            dec_str = ("." + "0" * dec) if dec > 0 else ""
            base = f"{sym_part}#,##0{dec_str}"

            if neg_idx == 1:
                return f"{base};[Red]{base}"
            elif neg_idx == 2:
                return f"{base};({base})"
            elif neg_idx == 3:
                return f"{base};[Red]({base})"
            return base

        elif cat == "Accounting":
            dec = self.acc_decimals_spin.value()
            sym = self.acc_symbol_combo.currentText()
            sym_part = f'"{sym}"' if sym and sym != safe_tr("无") else ""
            dec_str = ("." + "0" * dec) if dec > 0 else ""
            return (
                f'_({sym_part}* #,##0{dec_str}_);_({sym_part}* (#,##0{dec_str});_({sym_part}* "-"??_);_(@_)'
            )

        elif cat == "Date":
            item = self.date_list.currentItem()
            return item.text() if item is not None else "yyyy-mm-dd"

        elif cat == "Time":
            item = self.time_list.currentItem()
            return item.text() if item is not None else "h:mm:ss"

        elif cat == "Percentage":
            dec = self.percent_decimals_spin.value()
            return ("0." + "0" * dec + "%") if dec > 0 else "0%"

        elif cat == "Fraction":
            item = self.fraction_list.currentItem()
            return item.text() if item is not None else "# ?/?"

        elif cat == "Scientific":
            dec = self.sci_decimals_spin.value()
            return ("0." + "0" * dec + "E+00") if dec > 0 else "0E+00"

        elif cat == "Text":
            return "@"

        elif cat == "Special":
            item = self.special_list.currentItem()
            return (
                item.data(Qt.ItemDataRole.UserRole)
                if item is not None
                else "000000"
            )

        elif cat == "Custom":
            code = self.custom_edit.text().strip()
            return code if code else "General"

        return "General"

    def set_format_code(self, code: str) -> None:
        self._current_format = code
        self._select_category_for_code(code)
        self.update_sample()

    def update_sample(self) -> None:
        code = self.get_format_code()
        try:
            res = format_value(self.sample_value, code)
            self.sample_label.setText(res.text)
            color = res.color if res.color else "#000000"
            self.sample_label.setStyleSheet(
                f"font-size: 13px; font-weight: bold; padding: 4px; color: {color};"
            )
        except Exception:
            self.sample_label.setText(str(self.sample_value))
            self.sample_label.setStyleSheet(
                "font-size: 13px; font-weight: bold; padding: 4px; color: #000000;"
            )

    def retranslate_ui(self) -> None:
        self.lbl_category.setText(safe_tr("分类(&C):"))
        self.sample_group.setTitle(safe_tr("示例"))
        self.lbl_decimals.setText(safe_tr("小数位数(&D):"))
        self.sep_check.setText(safe_tr("使用千位分隔符 (,) (&U)"))
        self.lbl_neg.setText(safe_tr("负数(&N):"))
        self.lbl_symbol.setText(safe_tr("货币符号(&S):"))
        self.lbl_curr_neg.setText(safe_tr("负数(&N):"))
        self.lbl_date_type.setText(safe_tr("类型(&T):"))
        self.lbl_time_type.setText(safe_tr("类型(&T):"))
        self.lbl_fraction.setText(safe_tr("类型(&T):"))
        self.lbl_special.setText(safe_tr("类型(&T):"))
        self._on_category_changed(self.cat_list.currentRow())
