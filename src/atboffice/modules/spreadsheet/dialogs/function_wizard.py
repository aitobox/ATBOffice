"""Insert Function (fx) Wizard and Function Arguments Dialog.

Excel 2003-style two-step formula authoring wizard:
1. InsertFunctionDialog: Category filter, fuzzy search, syntax/description preview, MRU list.
2. FunctionArgumentsDialog: Dedicated per-parameter editing, argument help, dynamic repeating
   parameters ('...'), live evaluation preview, cell range coordinate picker, and formula injection.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QSettings, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.evaluator import evaluate
from atboffice.modules.spreadsheet.calc.fn_info import (
    ALL_FUNCTIONS_CATALOG,
    FunctionInfo,
    get_function_info,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
    from atboffice.modules.spreadsheet.views.editor_controller import EditorController


def safe_tr(text: str) -> str:
    """Translate UI text safely for the function wizard dialogs."""
    return QCoreApplication.translate("FunctionWizard", text)


DEFAULT_MRU: list[str] = [
    "SUM",
    "AVERAGE",
    "IF",
    "HYPERLINK",
    "COUNT",
    "MAX",
    "SIN",
    "SUMIF",
    "PMT",
    "STDEV",
]

# Canonical category names as defined in fn_info / fninfo.js
STANDARD_CATEGORIES: list[str] = [
    "Most Recently Used",
    "All",
    "Financial",
    "Date & Time",
    "Math & Trig",
    "Statistical",
    "Lookup & Reference",
    "Database",
    "Text",
    "Logical",
    "Information",
    "Engineering",
    "Cube",
    "Web",
]

CATEGORY_TRANSLATIONS: dict[str, str] = {
    "Most Recently Used": "常用函数",
    "All": "全部",
    "Financial": "财务",
    "Date & Time": "日期与时间",
    "Math & Trig": "数学与三角函数",
    "Statistical": "统计",
    "Lookup & Reference": "查找与引用",
    "Database": "数据库",
    "Text": "文本",
    "Logical": "逻辑",
    "Information": "信息",
    "Engineering": "工程",
    "Cube": "多维数据集",
    "Web": "Web",
    "Recommended": "搜索建议",
}

ARG_HELP_DATA: dict[str, str] = {
    "number": "为数字，或包含数字的单元格引用。",
    "number1": "number1, number2, ... 为 1 到 255 个需要计算的数值或单元格引用。",
    "value1": "value1, value2, ... 为 1 到 255 个数值、文本或单元格区域。",
    "logical1": "logical1, logical2, ... 为 1 到 255 个计算结果为 TRUE 或 FALSE 的条件。",
    "logical_test": "为计算结果为 TRUE 或 FALSE 的任意值或表达式。",
    "value_if_true": "为 Logical_test 结果为 TRUE 时的返回值。如果省略，则返回 TRUE。",
    "value_if_false": "为 Logical_test 结果为 FALSE 时的返回值。如果省略，则返回 FALSE。",
    "lookup_value": "为在表格第一列（或行）中查找的数值，可以是数值、引用或文本字符串。",
    "table_array": "为要在其中检索数据的数据表。可以是单元格区域引用或区域名称。",
    "col_index_num": "为 table_array 中待返回匹配值的列序号。第一列为 1。",
    "row_index_num": "为 table_array 中待返回匹配值的行序号。第一行为 1。",
    "range_lookup": (
        "为逻辑值：指明是要寻找精确匹配还是近似匹配。"
        "TRUE 或省略表示近似匹配；FALSE 表示精确匹配。"
    ),
    "range": "为需要计算或评估的单元格区域。",
    "criteria": "为定义哪些单元格将被计入的条件，可以是数字、表达式或文本。",
    "sum_range": "为实际求和的单元格。如果省略，则计算 range 中的单元格。",
    "text": "为需要处理的文本字符串。",
    "num_chars": "指定要提取的字符数。",
    "rate": "为各期利率。例如，如果按 6% 年利率每季度付款，请使用 6%/4。",
    "nper": "为总付款期数。",
    "pv": "为现值：未来各期付款现在的总价值。",
    "fv": "为未来值，或在最后一次付款后希望达到的现金余额。",
    "type": "为逻辑值：期初付款 = 1；期末付款 = 0 或省略。",
    "num_digits": "指定进行四舍五入的位数。负数舍入到小数点左侧；0 舍入到最接近的整数。",
    "serial_number": "为 Ledger 日期时间代码中的数字序列号。",
    "array": "为单元格区域或数组常量。",
    "k": "为需要返回的数据在数组或单元格区域中的位置（从最大或最小算起）。",
    "reference": "为单元格或单元格区域引用。",
    "database": "为构成列表或数据库的单元格区域。数据库是包含相关数据的列表。",
    "field": "为带双引号的列标签，或者是代表该列在列表中位置的数字。",
    "criteria_range1": "为特定条件下需要评估的单元格区域。",
}


class FunctionCatalogService:
    """Service providing function catalog searching, category filtering, and MRU caching."""

    MRU_SETTINGS_KEY = "spreadsheet/function_mru"

    @classmethod
    def get_mru_list(cls) -> list[str]:
        """Retrieve most recently used function names from QSettings with fallback."""
        settings = QSettings("ATBOffice", "ATBOffice")
        raw = settings.value(cls.MRU_SETTINGS_KEY)
        if isinstance(raw, list) and raw:
            return [str(x).upper() for x in raw if str(x).upper() in ALL_FUNCTIONS_CATALOG]
        if isinstance(raw, str) and raw:
            items = [x.strip().upper() for x in raw.split(",") if x.strip()]
            return [x for x in items if x in ALL_FUNCTIONS_CATALOG]
        return list(DEFAULT_MRU)

    @classmethod
    def record_mru(cls, name: str) -> None:
        """Record function usage and persist to MRU list (max 10 items)."""
        upper = name.strip().upper()
        if upper not in ALL_FUNCTIONS_CATALOG:
            return
        mru = cls.get_mru_list()
        if upper in mru:
            mru.remove(upper)
        mru.insert(0, upper)
        mru = mru[:10]
        settings = QSettings("ATBOffice", "ATBOffice")
        settings.setValue(cls.MRU_SETTINGS_KEY, mru)

    @classmethod
    def get_functions_by_category(cls, category: str) -> list[str]:
        """Return sorted function names matching a category."""
        if category == "Most Recently Used":
            return cls.get_mru_list()
        if category == "All":
            return sorted(ALL_FUNCTIONS_CATALOG.keys())
        return sorted(
            name
            for name, info in ALL_FUNCTIONS_CATALOG.items()
            if info.category.lower() == category.lower()
        )

    @classmethod
    def search(cls, query: str) -> list[str]:
        """Fuzzy search catalog by query keywords, scoring name and description matches."""
        words = [w.lower() for w in re.split(r"[^\w]+", query) if len(w) > 1]
        if not words:
            return []

        scored: list[tuple[str, int]] = []
        for name, info in ALL_FUNCTIONS_CATALOG.items():
            name_lower = name.lower()
            desc_lower = info.desc.lower()
            score = 0
            for w in words:
                if name_lower == w:
                    score += 20
                elif name_lower.startswith(w):
                    score += 10
                elif w in name_lower:
                    score += 5
                if w in desc_lower:
                    score += 2
            if score > 0:
                scored.append((name, score))

        scored.sort(key=lambda item: (-item[1], item[0]))
        return [item[0] for item in scored[:35]]

    @classmethod
    def format_syntax(cls, info: FunctionInfo) -> str:
        """Format syntax signature: NAME(arg1, [arg2], ...)."""
        return f"{info.name}({', '.join(info.args)})"

    @classmethod
    def get_arg_help(cls, arg_name: str) -> str:
        """Get localized description for a function argument."""
        clean_name = re.sub(r"[\[\]\.]", "", arg_name).lower()
        if clean_name in ARG_HELP_DATA:
            return safe_tr(ARG_HELP_DATA[clean_name])
        # Strip trailing numbers (e.g. number2 -> number1)
        base_name = re.sub(r"\d+$", "", clean_name)
        if base_name in ARG_HELP_DATA:
            return safe_tr(ARG_HELP_DATA[base_name])
        if clean_name + "1" in ARG_HELP_DATA:
            return safe_tr(ARG_HELP_DATA[clean_name + "1"])
        return safe_tr("为函数的输入参数。")


# ==============================================================================
# Step 1: Insert Function Dialog
# ==============================================================================


class InsertFunctionDialog(QDialog):
    """Step 1 dialog: Filter and search worksheet functions, preview syntax & description."""

    def __init__(self, parent: QWidget | None = None, initial_fn: str | None = None) -> None:
        super().__init__(parent)
        self.selected_function: str = initial_fn.upper() if initial_fn else "SUM"
        self._current_category: str = "Most Recently Used"

        self.setWindowTitle(safe_tr("插入函数"))
        self.resize(460, 430)
        self.setMinimumSize(400, 360)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 1. Search Box
        self.lbl_search = QLabel(safe_tr("搜索函数(&S):"), self)
        main_layout.addWidget(self.lbl_search)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.edit_search = QLineEdit(self)
        self.edit_search.setPlaceholderText(safe_tr("键入需要执行操作的简短描述，然后单击“转到”"))
        self.edit_search.returnPressed.connect(self._on_search_clicked)
        search_row.addWidget(self.edit_search)

        self.btn_go = QPushButton(safe_tr("转到(&G)"), self)
        self.btn_go.setFixedWidth(70)
        self.btn_go.clicked.connect(self._on_search_clicked)
        search_row.addWidget(self.btn_go)
        main_layout.addLayout(search_row)

        # 2. Category Selection
        cat_layout = QHBoxLayout()
        self.lbl_category = QLabel(safe_tr("或选择类别(&C):"), self)
        cat_layout.addWidget(self.lbl_category)

        self.combo_category = QComboBox(self)
        for cat in STANDARD_CATEGORIES:
            label = safe_tr(CATEGORY_TRANSLATIONS.get(cat, cat))
            self.combo_category.addItem(label, cat)
        self.combo_category.currentIndexChanged.connect(self._on_category_changed)
        cat_layout.addWidget(self.combo_category, 1)
        main_layout.addLayout(cat_layout)

        # 3. Function List
        self.lbl_select = QLabel(safe_tr("选择函数(&N):"), self)
        main_layout.addWidget(self.lbl_select)

        self.list_functions = QListWidget(self)
        list_font = QFont("Courier New", 10)
        self.list_functions.setFont(list_font)
        self.list_functions.currentItemChanged.connect(self._on_item_changed)
        self.list_functions.itemDoubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.list_functions, 1)

        # 4. Syntax & Description Preview Box
        preview_frame = QFrame(self)
        preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        preview_frame.setFrameShadow(QFrame.Shadow.Sunken)
        preview_frame.setStyleSheet("background-color: #fcfcfc; padding: 4px; border-radius: 3px;")
        prev_layout = QVBoxLayout(preview_frame)
        prev_layout.setContentsMargins(6, 6, 6, 6)
        prev_layout.setSpacing(4)

        self.lbl_syntax = QLabel(self)
        syntax_font = QFont()
        syntax_font.setBold(True)
        self.lbl_syntax.setFont(syntax_font)
        self.lbl_syntax.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        prev_layout.addWidget(self.lbl_syntax)

        self.lbl_desc = QLabel(self)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        prev_layout.addWidget(self.lbl_desc)
        main_layout.addWidget(preview_frame)

        # 5. Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Initial populate
        self._populate_list(self._current_category, select_fn=self.selected_function)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.setWindowTitle(safe_tr("插入函数"))
        self.lbl_search.setText(safe_tr("搜索函数(&S):"))
        self.btn_go.setText(safe_tr("转到(&G)"))
        self.lbl_category.setText(safe_tr("或选择类别(&C):"))
        self.lbl_select.setText(safe_tr("选择函数(&N):"))
        btn_ok = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if btn_ok:
            btn_ok.setText(safe_tr("确定"))
        btn_cancel = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if btn_cancel:
            btn_cancel.setText(safe_tr("取消"))

    def _populate_list(self, category: str, select_fn: str | None = None) -> None:
        """Populate the function list widget with items for category."""
        self.list_functions.blockSignals(True)
        self.list_functions.clear()
        names = FunctionCatalogService.get_functions_by_category(category)

        target_row = 0
        for i, name in enumerate(names):
            QListWidgetItem(name, self.list_functions)
            if select_fn and name == select_fn:
                target_row = i

        self.list_functions.blockSignals(False)
        if names:
            self.list_functions.setCurrentRow(target_row)
            self._update_preview(names[target_row])
        else:
            self.lbl_syntax.setText("")
            self.lbl_desc.setText(safe_tr("未找到符合条件的函数。"))

    def _on_category_changed(self, index: int) -> None:
        cat_data = self.combo_category.currentData()
        if cat_data:
            self._current_category = str(cat_data)
            self._populate_list(self._current_category)

    def _on_search_clicked(self) -> None:
        text = self.edit_search.text().strip()
        if not text:
            return
        results = FunctionCatalogService.search(text)

        # Block combo signals to prevent overwriting search results
        self.combo_category.blockSignals(True)
        rec_idx = self.combo_category.findData("Recommended")
        if rec_idx >= 0:
            self.combo_category.setCurrentIndex(rec_idx)
        else:
            self.combo_category.addItem(safe_tr("搜索结果"), "Recommended")
            self.combo_category.setCurrentIndex(self.combo_category.count() - 1)
        self.combo_category.blockSignals(False)

        self.list_functions.blockSignals(True)
        self.list_functions.clear()
        for name in results:
            QListWidgetItem(name, self.list_functions)
        self.list_functions.blockSignals(False)

        if results:
            self.list_functions.setCurrentRow(0)
            self._update_preview(results[0])
        else:
            self.lbl_syntax.setText("")
            self.lbl_desc.setText(safe_tr("未找到匹配“{0}”的函数。").format(text))

    def _on_item_changed(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        if current is not None:
            name = current.text()
            self.selected_function = name
            self._update_preview(name)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self.selected_function = item.text()
        self._on_accept()

    def _update_preview(self, name: str) -> None:
        info = get_function_info(name)
        if info:
            self.lbl_syntax.setText(FunctionCatalogService.format_syntax(info))
            self.lbl_desc.setText(safe_tr(info.desc))
        else:
            self.lbl_syntax.setText(f"{name}()")
            self.lbl_desc.setText("")

    def _on_accept(self) -> None:
        current = self.list_functions.currentItem()
        if current:
            self.selected_function = current.text()
            FunctionCatalogService.record_mru(self.selected_function)
        self.accept()


# ==============================================================================
# Step 2: Function Arguments Dialog
# ==============================================================================


class FunctionArgumentsDialog(QDialog):
    """Step 2 dialog: Dedicated parameter input, argument hints, live preview."""

    formula_confirmed = Signal(str)

    def __init__(
        self,
        func_name: str,
        workbook: WorkbookModel | None = None,
        sheet: SheetDataModel | None = None,
        active_r: int = 0,
        active_c: int = 0,
        preset_args: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.func_name: str = func_name.upper()
        self.workbook: WorkbookModel | None = workbook
        self.sheet: SheetDataModel | None = sheet
        self.active_r: int = active_r
        self.active_c: int = active_c
        self.preset_args: list[str] = list(preset_args) if preset_args else []

        self.func_info: FunctionInfo = get_function_info(self.func_name) or FunctionInfo(
            name=self.func_name,
            category="User Defined",
            args=("arg1", "[arg2]", "..."),
            desc=safe_tr("计算自定义函数值。"),
        )

        self.setWindowTitle(safe_tr("函数参数"))
        self.resize(540, 480)
        self.setMinimumSize(480, 400)

        # Base arguments without the repeating ellipsis
        self.base_args: list[str] = [a for a in self.func_info.args if a != "..."]
        self.is_repeating: bool = "..." in self.func_info.args

        # Argument input widgets tracker: list of (arg_name, line_edit, preview_label)
        self.arg_rows: list[tuple[str, QLineEdit, QLabel]] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 1. Header: Function Name
        self.lbl_func_header = QLabel(f"<b>{self.func_name}</b>", self)
        header_font = QFont()
        header_font.setPointSize(header_font.pointSize() + 2)
        self.lbl_func_header.setFont(header_font)
        main_layout.addWidget(self.lbl_func_header)

        # 2. Scrollable Argument Input Area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.StyledPanel)

        self.args_container = QWidget(self.scroll_area)
        self.args_layout = QFormLayout(self.args_container)
        self.args_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.args_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.args_layout.setContentsMargins(8, 8, 8, 8)
        self.args_layout.setSpacing(6)
        self.scroll_area.setWidget(self.args_container)
        main_layout.addWidget(self.scroll_area, 1)

        # 3. Real-time Calculation Result Preview
        calc_box = QHBoxLayout()
        calc_box.setSpacing(6)
        self.lbl_result_tag = QLabel(safe_tr("计算结果 = "), self)
        bold_font = QFont()
        bold_font.setBold(True)
        self.lbl_result_tag.setFont(bold_font)
        self.lbl_result_val = QLabel("", self)
        self.lbl_result_val.setFont(bold_font)
        calc_box.addWidget(self.lbl_result_tag)
        calc_box.addWidget(self.lbl_result_val, 1)
        main_layout.addLayout(calc_box)

        # 4. Parameter & Function Help Box
        self.help_frame = QFrame(self)
        self.help_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.help_frame.setFrameShadow(QFrame.Shadow.Sunken)
        self.help_frame.setStyleSheet(
            "background-color: #fafafa; border-radius: 3px; padding: 4px;"
        )
        help_layout = QVBoxLayout(self.help_frame)
        help_layout.setContentsMargins(8, 8, 8, 8)
        help_layout.setSpacing(4)

        self.lbl_func_desc = QLabel(safe_tr(self.func_info.desc), self.help_frame)
        self.lbl_func_desc.setWordWrap(True)
        help_layout.addWidget(self.lbl_func_desc)

        self.lbl_arg_help = QLabel("", self.help_frame)
        self.lbl_arg_help.setWordWrap(True)
        self.lbl_arg_help.setStyleSheet("color: #333333;")
        help_layout.addWidget(self.lbl_arg_help)
        main_layout.addWidget(self.help_frame)

        # 5. Bottom Total / Dialog Button Box
        bottom_row = QHBoxLayout()
        self.lbl_formula_result_summary = QLabel(safe_tr("公式结果 = "), self)
        bottom_row.addWidget(self.lbl_formula_result_summary, 1)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        bottom_row.addWidget(self.button_box)
        main_layout.addLayout(bottom_row)

        # Build initial argument rows
        self._build_initial_rows()
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.setWindowTitle(safe_tr("函数参数"))
        self.lbl_result_tag.setText(safe_tr("计算结果 = "))
        btn_ok = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if btn_ok:
            btn_ok.setText(safe_tr("确定"))
        btn_cancel = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if btn_cancel:
            btn_cancel.setText(safe_tr("取消"))

    def _arg_name_for_index(self, index: int) -> str:
        """Resolve argument name for a given index, supporting repeating ... suffix."""
        if index < len(self.base_args):
            return self.base_args[index]
        last = self.base_args[-1] if self.base_args else "number1"
        match = re.match(r"^(\[?)([a-zA-Z_]+?)(\d+)(\]?)$", last)
        if match:
            prefix, name, num_str, suffix = match.groups()
            next_num = int(num_str) + index - len(self.base_args) + 1
            return f"{prefix}{name}{next_num}{suffix}"
        return last

    def _build_initial_rows(self) -> None:
        """Create argument rows matching base arguments or preset args."""
        initial_count = max(len(self.base_args), len(self.preset_args), 1)
        for i in range(initial_count):
            val = self.preset_args[i] if i < len(self.preset_args) else ""
            self._add_argument_row(i, val)
        self._update_evaluation()

    def _add_argument_row(self, index: int, initial_val: str = "") -> None:
        """Add a single parameter input row."""
        arg_name = self._arg_name_for_index(index)
        is_optional = arg_name.startswith("[") and arg_name.endswith("]")
        display_name = re.sub(r"[\[\]]", "", arg_name)
        display_name = display_name[:1].upper() + display_name[1:]

        label = QLabel(display_name + ":", self.args_container)
        label_font = QFont()
        if not is_optional:
            label_font.setBold(True)
        label.setFont(label_font)

        field_widget = QWidget(self.args_container)
        field_layout = QHBoxLayout(field_widget)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)

        edit = QLineEdit(initial_val, field_widget)
        edit.textChanged.connect(self._on_arg_text_changed)
        field_layout.addWidget(edit, 1)

        # Coordinate selection button
        btn_pick = QToolButton(field_widget)
        btn_pick.setText("⊞")
        btn_pick.setToolTip(safe_tr("在工作表中选取坐标或单元格"))
        btn_pick.setFixedSize(22, 22)
        btn_pick.clicked.connect(lambda: self._on_pick_coordinate(edit))
        field_layout.addWidget(btn_pick)

        # Value preview label
        lbl_val = QLabel("", field_widget)
        lbl_val.setMinimumWidth(80)
        lbl_val.setStyleSheet("color: #666666;")
        field_layout.addWidget(lbl_val)

        # Focus hook to display focused argument description and dynamic expansion
        row_idx = len(self.arg_rows)
        edit.installEventFilter(self)
        edit.setProperty("arg_row_index", row_idx)
        edit.setProperty("arg_raw_name", arg_name)

        self.args_layout.addRow(label, field_widget)
        self.arg_rows.append((arg_name, edit, lbl_val))

    def eventFilter(self, watched: Any, event: Any) -> bool:
        """Listen to FocusIn events to update help text and expand repeating arguments."""
        if event.type() == event.Type.FocusIn and isinstance(watched, QLineEdit):
            idx = watched.property("arg_row_index")
            raw_name = watched.property("arg_raw_name") or ""
            self._update_focused_help(raw_name)

            # If this is the last argument and function has repeating '...', add next row
            if self.is_repeating and idx == len(self.arg_rows) - 1:
                self._add_argument_row(len(self.arg_rows), "")
        return super().eventFilter(watched, event)

    def _update_focused_help(self, raw_name: str) -> None:
        """Display help description for currently focused argument."""
        display_name = re.sub(r"[\[\]]", "", raw_name)
        display_name = display_name[:1].upper() + display_name[1:]
        help_text = FunctionCatalogService.get_arg_help(raw_name)
        self.lbl_arg_help.setText(f"<b>{display_name}</b>: {help_text}")

    def _on_arg_text_changed(self) -> None:
        """Re-evaluate formula and update preview when arguments change."""
        self._update_evaluation()

    def _on_pick_coordinate(self, edit: QLineEdit) -> None:
        """Handle coordinate picking from spreadsheet selection."""
        if self.sheet is not None and hasattr(self.sheet, "current_selection_address"):
            addr = self.sheet.current_selection_address()
            if addr:
                edit.setText(addr)
                return

        # Fallback to parent window's active selection
        parent_win = self.window()
        if hasattr(parent_win, "spreadsheet_view"):
            sel = getattr(parent_win.spreadsheet_view, "grid", None)
            if sel and hasattr(sel, "selection"):
                pr = sel.selection.primary_range
                from atboffice.modules.spreadsheet.calc.references import range_name

                edit.setText(range_name(pr.min_r, pr.min_c, pr.max_r, pr.max_c))

    def build_call_string(self) -> str:
        """Construct function call string, trimming trailing optional blank arguments."""
        args_values = [edit.text().strip() for _, edit, _ in self.arg_rows]

        # Calculate minimum required arguments count (non-optional)
        min_required = sum(1 for a in self.base_args if not a.startswith("["))

        # Trim trailing empty optional arguments
        while len(args_values) > min_required and args_values and not args_values[-1]:
            args_values.pop()

        return f"{self.func_name}({', '.join(args_values)})"

    def _update_evaluation(self) -> None:
        """Run real-time formula evaluation on the active workbook and update UI."""
        # 1. Update individual argument previews
        sheet_name = getattr(self.sheet, "name", "Sheet1") if self.sheet else "Sheet1"
        ctx = EvalContext(
            workbook=self.workbook,
            current_sheet=sheet_name,
            current_row=self.active_r,
            current_col=self.active_c,
        )

        for _, edit, lbl_val in self.arg_rows:
            text = edit.text().strip()
            if not text:
                lbl_val.setText("")
                continue
            try:
                val = evaluate(text, ctx=ctx, workbook=self.workbook)
                lbl_val.setText(f"= {val}")
            except Exception:
                lbl_val.setText("= ")

        # 2. Evaluate full formula
        call_str = self.build_call_string()
        try:
            res = evaluate(call_str, ctx=ctx, workbook=self.workbook)
            res_str = str(res)
            self.lbl_result_val.setText(res_str)
            self.lbl_formula_result_summary.setText(safe_tr("公式结果 = {0}").format(res_str))
        except Exception:
            self.lbl_result_val.setText(safe_tr("(等待有效参数)"))
            self.lbl_formula_result_summary.setText(safe_tr("公式结果 = "))

    def _on_accept(self) -> None:
        call_str = self.build_call_string()
        self.formula_confirmed.emit(call_str)
        self.accept()


# ==============================================================================
# Wizard Launcher & Coordinator
# ==============================================================================


def launch_function_wizard(
    parent: QWidget | None = None,
    workbook: WorkbookModel | None = None,
    sheet: SheetDataModel | None = None,
    active_r: int = 0,
    active_c: int = 0,
    editor_controller: EditorController | None = None,
    default_fn: str | None = None,
) -> str | None:
    """Orchestrate the 2-step function wizard and inject formula into cell or editor."""
    chosen_fn = default_fn

    # Step 1: If no default function specified, show InsertFunctionDialog
    if not chosen_fn:
        step1 = InsertFunctionDialog(parent=parent)
        if step1.exec() != QDialog.DialogCode.Accepted:
            return None
        chosen_fn = step1.selected_function

    if not chosen_fn:
        return None

    # Step 2: Show FunctionArgumentsDialog
    step2 = FunctionArgumentsDialog(
        func_name=chosen_fn,
        workbook=workbook,
        sheet=sheet,
        active_r=active_r,
        active_c=active_c,
        parent=parent,
    )
    if step2.exec() != QDialog.DialogCode.Accepted:
        return None

    constructed_call = step2.build_call_string()
    full_formula = f"={constructed_call}"

    # Commit formula into editor_controller if available
    if editor_controller is not None:
        if editor_controller.is_active:
            current_text = editor_controller.in_cell_editor.text()
            # If current text ends with fx name, replace it; otherwise insert
            m = re.search(
                r"(?:_xlfn\.)?" + re.escape(chosen_fn) + r"\($", current_text, re.IGNORECASE
            )
            if m:
                before = current_text[: m.start()]
                after = current_text[m.end() :]
                editor_controller._sync_text(before + constructed_call + after)
            else:
                editor_controller.insert_text(constructed_call)
        else:
            editor_controller.begin_edit(active_r, active_c, initial_text=full_formula)
            editor_controller.commit()
    elif sheet is not None:
        # Fallback to direct cell assignment
        cell = sheet.get_cell(active_r, active_c)
        if cell is None:
            from atboffice.modules.spreadsheet.models.sheet_model import CellData

            cell = CellData()
            sheet.set_cell(active_r, active_c, cell)
        cell.formula = constructed_call

    return full_formula
