"""Classic Excel 2003 Multi-tab Ledger Options Dialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Safely translate OptionsDialog UI string."""
    return QCoreApplication.translate("LedgerOptionsDialog", text)


BUILTIN_CUSTOM_LISTS = [
    [
        "Sun, Mon, Tue, Wed, Thu, Fri, Sat",
        "Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday",
    ],
    [
        "Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec",
        (
            "January, February, March, April, May, June, July, "
            "August, September, October, November, December"
        ),
    ],
    ["日, 一, 二, 三, 四, 五, 六", "星期日, 星期一, 星期二, 星期三, 星期四, 星期五, 星期六"],
    ["一月, 二月, 三月, 四月, 五月, 六月, 七月, 八月, 九月, 十月, 十一月, 十二月"],
]


class LedgerOptionsDialog(QDialog):
    """Excel 2003 classic 8-tab Ledger Options Dialog."""

    options_saved = Signal(dict)

    def __init__(
        self,
        initial_options: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.options: dict[str, Any] = initial_options or {}
        self.custom_lists: list[list[str]] = list(self.options.get("custom_lists", []))

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("选项"))
        self.resize(540, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_view_tab(), safe_tr("视图"))
        self.tabs.addTab(self._build_calc_tab(), safe_tr("计算"))
        self.tabs.addTab(self._build_edit_tab(), safe_tr("编辑"))
        self.tabs.addTab(self._build_general_tab(), safe_tr("常规"))
        self.tabs.addTab(self._build_custom_lists_tab(), safe_tr("自定义序列"))
        self.tabs.addTab(self._build_error_checking_tab(), safe_tr("错误检查"))
        self.tabs.addTab(self._build_spelling_tab(), safe_tr("拼写检查"))
        self.tabs.addTab(self._build_security_tab(), safe_tr("安全性"))
        main_layout.addWidget(self.tabs, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)

    # -------------------------------------------------------------
    # Tab 1: View
    # -------------------------------------------------------------
    def _build_view_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        # Show group
        grp_show = QGroupBox(safe_tr("显示"), w)
        g_show = QGridLayout(grp_show)
        self.chk_formula_bar = QCheckBox(safe_tr("编辑栏(&F)"), grp_show)
        self.chk_status_bar = QCheckBox(safe_tr("状态栏(&S)"), grp_show)
        self.chk_show_screentips = QCheckBox(safe_tr("显示屏幕提示(&T)"), grp_show)
        self.chk_formula_bar.setChecked(True)
        self.chk_status_bar.setChecked(True)
        self.chk_show_screentips.setChecked(True)
        g_show.addWidget(self.chk_formula_bar, 0, 0)
        g_show.addWidget(self.chk_status_bar, 0, 1)
        g_show.addWidget(self.chk_show_screentips, 1, 0)
        v.addWidget(grp_show)

        # Window options group
        grp_win = QGroupBox(safe_tr("窗口选项"), w)
        g_win = QGridLayout(grp_win)
        self.chk_page_breaks = QCheckBox(safe_tr("分页符(&B)"), grp_win)
        self.chk_formulas = QCheckBox(safe_tr("公式(&R)"), grp_win)
        self.chk_gridlines = QCheckBox(safe_tr("网格线(&G)"), grp_win)
        self.chk_gridlines.setChecked(True)
        self.chk_row_col_headers = QCheckBox(safe_tr("行号列标(&H)"), grp_win)
        self.chk_row_col_headers.setChecked(True)
        self.chk_zero_values = QCheckBox(safe_tr("零值(&Z)"), grp_win)
        self.chk_zero_values.setChecked(True)
        self.chk_sheet_tabs = QCheckBox(safe_tr("工作表标签(&T)"), grp_win)
        self.chk_sheet_tabs.setChecked(True)

        g_win.addWidget(self.chk_page_breaks, 0, 0)
        g_win.addWidget(self.chk_formulas, 0, 1)
        g_win.addWidget(self.chk_gridlines, 1, 0)
        g_win.addWidget(self.chk_row_col_headers, 1, 1)
        g_win.addWidget(self.chk_zero_values, 2, 0)
        g_win.addWidget(self.chk_sheet_tabs, 2, 1)
        v.addWidget(grp_win)

        v.addStretch(1)
        return w

    # -------------------------------------------------------------
    # Tab 2: Calculation
    # -------------------------------------------------------------
    def _build_calc_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        grp_calc = QGroupBox(safe_tr("计算"), w)
        v_c = QVBoxLayout(grp_calc)
        self.radio_calc_auto = QRadioButton(safe_tr("自动重算(&A)"), grp_calc)
        self.radio_calc_auto.setChecked(True)
        self.radio_calc_table = QRadioButton(safe_tr("除模拟运算表外均自动重算(&T)"), grp_calc)
        self.radio_calc_manual = QRadioButton(safe_tr("手动重算(&M)"), grp_calc)
        self.chk_recalc_before_save = QCheckBox(safe_tr("保存前重新计算(&S)"), grp_calc)
        self.chk_recalc_before_save.setChecked(True)

        v_c.addWidget(self.radio_calc_auto)
        v_c.addWidget(self.radio_calc_table)
        v_c.addWidget(self.radio_calc_manual)
        v_c.addWidget(self.chk_recalc_before_save)
        v.addWidget(grp_calc)

        grp_iter = QGroupBox(safe_tr("迭代计算"), w)
        g_iter = QGridLayout(grp_iter)
        self.chk_iteration = QCheckBox(safe_tr("迭代计算(&I)"), grp_iter)
        g_iter.addWidget(self.chk_iteration, 0, 0, 1, 2)

        g_iter.addWidget(QLabel(safe_tr("最多迭代次数(&X):")), 1, 0)
        self.spin_max_iter = QSpinBox(grp_iter)
        self.spin_max_iter.setRange(1, 32767)
        self.spin_max_iter.setValue(100)
        g_iter.addWidget(self.spin_max_iter, 1, 1)

        g_iter.addWidget(QLabel(safe_tr("最大变化值(&C):")), 2, 0)
        self.spin_max_change = QDoubleSpinBox(grp_iter)
        self.spin_max_change.setDecimals(5)
        self.spin_max_change.setValue(0.001)
        g_iter.addWidget(self.spin_max_change, 2, 1)
        v.addWidget(grp_iter)

        v.addStretch(1)
        return w

    # -------------------------------------------------------------
    # Tab 3: Edit
    # -------------------------------------------------------------
    def _build_edit_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)

        self.chk_edit_in_cell = QCheckBox(safe_tr("直接在单元格内编辑(&E)"), w)
        self.chk_edit_in_cell.setChecked(True)
        self.chk_drag_drop = QCheckBox(safe_tr("允许单元格拖放(&D)"), w)
        self.chk_drag_drop.setChecked(True)
        self.chk_alert_overwrite = QCheckBox(safe_tr("覆盖单元格前发出警告(&W)"), w)
        self.chk_alert_overwrite.setChecked(True)
        self.chk_autocomplete = QCheckBox(safe_tr("记忆式键入(&A)"), w)
        self.chk_autocomplete.setChecked(True)

        v.addWidget(self.chk_edit_in_cell)
        v.addWidget(self.chk_drag_drop)
        v.addWidget(self.chk_alert_overwrite)
        v.addWidget(self.chk_autocomplete)

        h_enter = QHBoxLayout()
        self.chk_move_on_enter = QCheckBox(safe_tr("按 Enter 键后移动所选单元格(&M)"), w)
        self.chk_move_on_enter.setChecked(True)
        self.combo_enter_dir = QComboBox(w)
        self.combo_enter_dir.addItems(
            [safe_tr("向下"), safe_tr("向右"), safe_tr("向上"), safe_tr("向左")]
        )
        h_enter.addWidget(self.chk_move_on_enter)
        h_enter.addWidget(self.combo_enter_dir)
        h_enter.addStretch(1)
        v.addLayout(h_enter)

        v.addStretch(1)
        return w

    # -------------------------------------------------------------
    # Tab 4: General
    # -------------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        grid = QGridLayout(w)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel(safe_tr("新工作簿中的工作表数(&S):")), 0, 0)
        self.spin_sheets_count = QSpinBox(w)
        self.spin_sheets_count.setRange(1, 255)
        self.spin_sheets_count.setValue(3)
        grid.addWidget(self.spin_sheets_count, 0, 1)

        grid.addWidget(QLabel(safe_tr("标准字体(&F):")), 1, 0)
        self.combo_std_font = QComboBox(w)
        self.combo_std_font.addItems(["宋体", "Calibri", "Arial", "Times New Roman"])
        grid.addWidget(self.combo_std_font, 1, 1)

        grid.addWidget(QLabel(safe_tr("字号(&Z):")), 2, 0)
        self.combo_std_size = QComboBox(w)
        self.combo_std_size.addItems(["9", "10", "11", "12", "14", "16"])
        self.combo_std_size.setCurrentText("11")
        grid.addWidget(self.combo_std_size, 2, 1)

        grid.addWidget(QLabel(safe_tr("默认文件位置(&D):")), 3, 0)
        self.edit_default_dir = QLineEdit("~/Documents", w)
        grid.addWidget(self.edit_default_dir, 3, 1)

        grid.addWidget(QLabel(safe_tr("用户名(&U):")), 4, 0)
        self.edit_username = QLineEdit("User", w)
        grid.addWidget(self.edit_username, 4, 1)

        grid.setRowStretch(5, 1)
        return w

    # -------------------------------------------------------------
    # Tab 5: Custom Lists
    # -------------------------------------------------------------
    def _build_custom_lists_tab(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setSpacing(10)

        # Left: list names
        v_left = QVBoxLayout()
        v_left.addWidget(QLabel(safe_tr("自定义序列(&C):")))
        self.list_custom_lists = QListWidget(w)
        self.list_custom_lists.addItem(safe_tr("新序列"))
        for item in BUILTIN_CUSTOM_LISTS:
            self.list_custom_lists.addItem(item[0])
        for cl in self.custom_lists:
            self.list_custom_lists.addItem(", ".join(cl[:3]) + ("..." if len(cl) > 3 else ""))
        self.list_custom_lists.setCurrentRow(0)
        self.list_custom_lists.currentRowChanged.connect(self._on_custom_list_selected)
        v_left.addWidget(self.list_custom_lists, 1)
        h.addLayout(v_left, 1)

        # Right: entries editor
        v_right = QVBoxLayout()
        v_right.addWidget(QLabel(safe_tr("输入序列(&L):")))
        self.edit_list_entries = QPlainTextEdit(w)
        v_right.addWidget(self.edit_list_entries, 1)

        h_btns = QHBoxLayout()
        self.btn_add_list = QPushButton(safe_tr("添加(&A)"), w)
        self.btn_del_list = QPushButton(safe_tr("删除(&D)"), w)
        self.btn_del_list.setEnabled(False)
        self.btn_add_list.clicked.connect(self._on_add_custom_list)
        self.btn_del_list.clicked.connect(self._on_del_custom_list)
        h_btns.addWidget(self.btn_add_list)
        h_btns.addWidget(self.btn_del_list)
        v_right.addLayout(h_btns)

        h.addLayout(v_right, 1)
        return w

    def _on_custom_list_selected(self, row: int) -> None:
        if row <= 0:
            self.edit_list_entries.clear()
            self.btn_del_list.setEnabled(False)
            self.btn_add_list.setEnabled(True)
        elif 1 <= row <= len(BUILTIN_CUSTOM_LISTS):
            b_list = BUILTIN_CUSTOM_LISTS[row - 1]
            self.edit_list_entries.setPlainText("\n".join(b_list))
            self.btn_del_list.setEnabled(False)
            self.btn_add_list.setEnabled(False)
        else:
            u_idx = row - len(BUILTIN_CUSTOM_LISTS) - 1
            if 0 <= u_idx < len(self.custom_lists):
                self.edit_list_entries.setPlainText("\n".join(self.custom_lists[u_idx]))
                self.btn_del_list.setEnabled(True)
                self.btn_add_list.setEnabled(False)

    def _on_add_custom_list(self) -> None:
        raw_text = self.edit_list_entries.toPlainText().strip()
        if not raw_text:
            return
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not lines:
            return
        items: list[str] = []
        for line in lines:
            if "," in line:
                items.extend([part.strip() for part in line.split(",") if part.strip()])
            else:
                items.append(line)
        if not items:
            return
        self.custom_lists.append(items)
        display_label = ", ".join(items[:3]) + ("..." if len(items) > 3 else "")
        self.list_custom_lists.addItem(display_label)
        self.list_custom_lists.setCurrentRow(self.list_custom_lists.count() - 1)

    def _on_del_custom_list(self) -> None:
        row = self.list_custom_lists.currentRow()
        if row > len(BUILTIN_CUSTOM_LISTS):
            u_idx = row - len(BUILTIN_CUSTOM_LISTS) - 1
            if 0 <= u_idx < len(self.custom_lists):
                del self.custom_lists[u_idx]
                self.list_custom_lists.takeItem(row)
                self.list_custom_lists.setCurrentRow(0)

    # -------------------------------------------------------------
    # Tab 6: Error Checking
    # -------------------------------------------------------------
    def _build_error_checking_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        self.chk_bg_error_check = QCheckBox(safe_tr("启用后台错误检查(&E)"), w)
        self.chk_bg_error_check.setChecked(True)
        v.addWidget(self.chk_bg_error_check)

        grp_rules = QGroupBox(safe_tr("错误检查规则"), w)
        v_r = QVBoxLayout(grp_rules)
        self.chk_rule_eval = QCheckBox(safe_tr("求值出错的单元格(&V)"), grp_rules)
        self.chk_rule_eval.setChecked(True)
        self.chk_rule_number_text = QCheckBox(safe_tr("以文本形式存储的数字(&N)"), grp_rules)
        self.chk_rule_number_text.setChecked(True)
        self.chk_rule_inconsistent_formula = QCheckBox(
            safe_tr("公式与区域中其他公式不一致(&F)"), grp_rules
        )
        self.chk_rule_inconsistent_formula.setChecked(True)
        v_r.addWidget(self.chk_rule_eval)
        v_r.addWidget(self.chk_rule_number_text)
        v_r.addWidget(self.chk_rule_inconsistent_formula)
        v.addWidget(grp_rules)

        v.addStretch(1)
        return w

    # -------------------------------------------------------------
    # Tab 7: Spelling
    # -------------------------------------------------------------
    def _build_spelling_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        grp_spell = QGroupBox(safe_tr("拼写检查选项"), w)
        v_s = QVBoxLayout(grp_spell)
        self.chk_ignore_upper = QCheckBox(safe_tr("忽略全部大写的单词(&U)"), grp_spell)
        self.chk_ignore_upper.setChecked(True)
        self.chk_ignore_numbers = QCheckBox(safe_tr("忽略包含数字的单词(&N)"), grp_spell)
        self.chk_ignore_numbers.setChecked(True)
        self.chk_ignore_urls = QCheckBox(safe_tr("忽略 Internet 和文件地址(&I)"), grp_spell)
        self.chk_ignore_urls.setChecked(True)
        v_s.addWidget(self.chk_ignore_upper)
        v_s.addWidget(self.chk_ignore_numbers)
        v_s.addWidget(self.chk_ignore_urls)
        v.addWidget(grp_spell)

        v.addStretch(1)
        return w

    # -------------------------------------------------------------
    # Tab 8: Security
    # -------------------------------------------------------------
    def _build_security_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        grp_enc = QGroupBox(safe_tr("此工作簿的文件加密选项"), w)
        g_enc = QGridLayout(grp_enc)
        g_enc.addWidget(QLabel(safe_tr("打开权限密码(&P):")), 0, 0)
        self.edit_pwd_open = QLineEdit(grp_enc)
        self.edit_pwd_open.setEchoMode(QLineEdit.EchoMode.Password)
        g_enc.addWidget(self.edit_pwd_open, 0, 1)
        v.addWidget(grp_enc)

        grp_share = QGroupBox(safe_tr("此工作簿的文件共享选项"), w)
        g_share = QGridLayout(grp_share)
        g_share.addWidget(QLabel(safe_tr("修改权限密码(&M):")), 0, 0)
        self.edit_pwd_modify = QLineEdit(grp_share)
        self.edit_pwd_modify.setEchoMode(QLineEdit.EchoMode.Password)
        g_share.addWidget(self.edit_pwd_modify, 0, 1)

        self.chk_read_only_rec = QCheckBox(safe_tr("建议只读(&R)"), grp_share)
        g_share.addWidget(self.chk_read_only_rec, 1, 0, 1, 2)
        v.addWidget(grp_share)

        v.addStretch(1)
        return w

    # -------------------------------------------------------------
    # Options export & handler
    # -------------------------------------------------------------
    def get_options(self) -> dict[str, Any]:
        return {
            "show_formula_bar": self.chk_formula_bar.isChecked(),
            "show_status_bar": self.chk_status_bar.isChecked(),
            "show_page_breaks": self.chk_page_breaks.isChecked(),
            "show_formulas": self.chk_formulas.isChecked(),
            "show_gridlines": self.chk_gridlines.isChecked(),
            "show_headers": self.chk_row_col_headers.isChecked(),
            "show_zeros": self.chk_zero_values.isChecked(),
            "show_tabs": self.chk_sheet_tabs.isChecked(),
            "calc_mode": "manual" if self.radio_calc_manual.isChecked() else "auto",
            "iteration": self.chk_iteration.isChecked(),
            "max_iterations": self.spin_max_iter.value(),
            "max_change": self.spin_max_change.value(),
            "edit_in_cell": self.chk_edit_in_cell.isChecked(),
            "drag_and_drop": self.chk_drag_drop.isChecked(),
            "sheets_count": self.spin_sheets_count.value(),
            "default_font": self.combo_std_font.currentText(),
            "default_size": self.combo_std_size.currentText(),
            "username": self.edit_username.text().strip(),
            "bg_error_checking": self.chk_bg_error_check.isChecked(),
            "read_only_recommended": self.chk_read_only_rec.isChecked(),
            "show_screentips": self.chk_show_screentips.isChecked(),
            "custom_lists": [list(cl) for cl in self.custom_lists],
        }

    def _on_ok(self) -> None:
        opts = self.get_options()
        self.options_saved.emit(opts)
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("选项"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_cancel.setText(safe_tr("取消"))
        if hasattr(self, "btn_add_list"):
            self.btn_add_list.setText(safe_tr("添加(&A)"))
        if hasattr(self, "btn_del_list"):
            self.btn_del_list.setText(safe_tr("删除(&D)"))
        if hasattr(self, "chk_show_screentips"):
            self.chk_show_screentips.setText(safe_tr("显示屏幕提示(&T)"))
