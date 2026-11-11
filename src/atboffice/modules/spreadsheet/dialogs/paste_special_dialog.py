"""Excel 2003 Paste Special dialog for Ledger."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for PasteSpecialDialog."""
    return QCoreApplication.translate("PasteSpecialDialog", text)


class PasteSpecialDialog(QDialog):
    """Excel 2003 / VibeOffice Paste Special dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("选择性粘贴"))
        self.resize(380, 360)

        self._paste_link_clicked = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Upper row: Paste group & Operation group
        groups_layout = QHBoxLayout()
        groups_layout.setSpacing(10)

        # --- Paste Group ---
        self.grp_paste = QGroupBox(safe_tr("粘贴"), self)
        paste_layout = QVBoxLayout(self.grp_paste)
        paste_layout.setSpacing(4)
        paste_layout.setContentsMargins(8, 8, 8, 8)

        self.btn_group_paste = QButtonGroup(self)

        self.rb_all = QRadioButton(safe_tr("全部(&A)"), self.grp_paste)
        self.rb_formulas = QRadioButton(safe_tr("公式(&F)"), self.grp_paste)
        self.rb_values = QRadioButton(safe_tr("数值(&V)"), self.grp_paste)
        self.rb_formats = QRadioButton(safe_tr("格式(&T)"), self.grp_paste)
        self.rb_comments = QRadioButton(safe_tr("批注(&C)"), self.grp_paste)
        self.rb_validation = QRadioButton(safe_tr("有效性验证(&N)"), self.grp_paste)
        self.rb_all_theme = QRadioButton(safe_tr("所有使用源主题的单元(&H)"), self.grp_paste)
        self.rb_no_borders = QRadioButton(safe_tr("除边框外的所有内容(&X)"), self.grp_paste)
        self.rb_col_widths = QRadioButton(safe_tr("列宽(&W)"), self.grp_paste)
        self.rb_formulas_nf = QRadioButton(safe_tr("公式和数字格式(&R)"), self.grp_paste)
        self.rb_values_nf = QRadioButton(safe_tr("值和数字格式(&U)"), self.grp_paste)

        self.rb_all.setChecked(True)

        paste_radios = [
            (self.rb_all, "all"),
            (self.rb_formulas, "formulas"),
            (self.rb_values, "values"),
            (self.rb_formats, "formats"),
            (self.rb_comments, "comments"),
            (self.rb_validation, "validation"),
            (self.rb_all_theme, "allTheme"),
            (self.rb_no_borders, "noBorders"),
            (self.rb_col_widths, "colWidths"),
            (self.rb_formulas_nf, "formulasNF"),
            (self.rb_values_nf, "valuesNF"),
        ]
        self._paste_map: dict[QRadioButton, str] = {}
        for idx, (rb, key) in enumerate(paste_radios):
            self.btn_group_paste.addButton(rb, idx)
            paste_layout.addWidget(rb)
            self._paste_map[rb] = key

        groups_layout.addWidget(self.grp_paste)

        # --- Operation Group ---
        self.grp_op = QGroupBox(safe_tr("运算"), self)
        op_layout = QVBoxLayout(self.grp_op)
        op_layout.setSpacing(4)
        op_layout.setContentsMargins(8, 8, 8, 8)

        self.btn_group_op = QButtonGroup(self)

        self.rb_op_none = QRadioButton(safe_tr("无(&O)"), self.grp_op)
        self.rb_op_add = QRadioButton(safe_tr("加(&D)"), self.grp_op)
        self.rb_op_sub = QRadioButton(safe_tr("减(&S)"), self.grp_op)
        self.rb_op_mul = QRadioButton(safe_tr("乘(&M)"), self.grp_op)
        self.rb_op_div = QRadioButton(safe_tr("除(&I)"), self.grp_op)

        self.rb_op_none.setChecked(True)

        op_radios = [
            (self.rb_op_none, "none"),
            (self.rb_op_add, "add"),
            (self.rb_op_sub, "sub"),
            (self.rb_op_mul, "mul"),
            (self.rb_op_div, "div"),
        ]
        self._op_map: dict[QRadioButton, str] = {}
        for idx, (rb, key) in enumerate(op_radios):
            self.btn_group_op.addButton(rb, idx)
            op_layout.addWidget(rb)
            self._op_map[rb] = key
        op_layout.addStretch()

        groups_layout.addWidget(self.grp_op)
        main_layout.addLayout(groups_layout)

        # --- Checkboxes row ---
        chk_layout = QHBoxLayout()
        chk_layout.setSpacing(20)
        self.chk_skip_blanks = QCheckBox(safe_tr("跳过空单元(&B)"), self)
        self.chk_transpose = QCheckBox(safe_tr("转置(&E)"), self)
        chk_layout.addWidget(self.chk_skip_blanks)
        chk_layout.addWidget(self.chk_transpose)
        chk_layout.addStretch()
        main_layout.addLayout(chk_layout)

        # --- Action Buttons ---
        btn_layout = QHBoxLayout()
        self.btn_paste_link = QPushButton(safe_tr("粘贴链接(&L)"), self)
        self.btn_paste_link.clicked.connect(self._on_paste_link)
        btn_layout.addWidget(self.btn_paste_link)

        btn_layout.addStretch()

        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_layout)

    def _on_paste_link(self) -> None:
        self._paste_link_clicked = True
        self.accept()

    @property
    def selected_what(self) -> str:
        """Selected paste mode string."""
        btn = self.btn_group_paste.checkedButton()
        if btn is not None and btn in self._paste_map:
            return self._paste_map[btn]
        return "all"

    @property
    def selected_operation(self) -> str:
        """Selected arithmetic operation string."""
        btn = self.btn_group_op.checkedButton()
        if btn is not None and btn in self._op_map:
            return self._op_map[btn]
        return "none"

    def set_selected_what(self, what: str) -> None:
        """Programmatically select paste mode."""
        for rb, key in self._paste_map.items():
            if key == what or (what in ("allExceptBorders", "no_borders") and key == "noBorders"):
                rb.setChecked(True)
                break

    def set_selected_operation(self, op: str) -> None:
        """Programmatically select operation mode."""
        norm_op = {"subtract": "sub", "multiply": "mul", "divide": "div"}.get(op, op)
        for rb, key in self._op_map.items():
            if key == norm_op:
                rb.setChecked(True)
                break

    @property
    def is_skip_blanks(self) -> bool:
        """Whether skip blanks is checked."""
        return self.chk_skip_blanks.isChecked()

    @property
    def is_transpose(self) -> bool:
        """Whether transpose is checked."""
        return self.chk_transpose.isChecked()

    @property
    def is_paste_link(self) -> bool:
        """Whether Paste Link was clicked."""
        return self._paste_link_clicked

    @property
    def options(self) -> dict[str, Any]:
        """Consolidated options dictionary."""
        return {
            "what": self.selected_what,
            "type": self.selected_what,
            "op": self.selected_operation,
            "operation": self.selected_operation,
            "skip_blanks": self.is_skip_blanks,
            "transpose": self.is_transpose,
            "link": self.is_paste_link,
        }

    def retranslate_ui(self) -> None:
        """Retranslate dialog text for i18n."""
        self.setWindowTitle(safe_tr("选择性粘贴"))
        self.grp_paste.setTitle(safe_tr("粘贴"))
        self.rb_all.setText(safe_tr("全部(&A)"))
        self.rb_formulas.setText(safe_tr("公式(&F)"))
        self.rb_values.setText(safe_tr("数值(&V)"))
        self.rb_formats.setText(safe_tr("格式(&T)"))
        self.rb_comments.setText(safe_tr("批注(&C)"))
        self.rb_validation.setText(safe_tr("有效性验证(&N)"))
        self.rb_all_theme.setText(safe_tr("所有使用源主题的单元(&H)"))
        self.rb_no_borders.setText(safe_tr("除边框外的所有内容(&X)"))
        self.rb_col_widths.setText(safe_tr("列宽(&W)"))
        self.rb_formulas_nf.setText(safe_tr("公式和数字格式(&R)"))
        self.rb_values_nf.setText(safe_tr("值和数字格式(&U)"))

        self.grp_op.setTitle(safe_tr("运算"))
        self.rb_op_none.setText(safe_tr("无(&O)"))
        self.rb_op_add.setText(safe_tr("加(&D)"))
        self.rb_op_sub.setText(safe_tr("减(&S)"))
        self.rb_op_mul.setText(safe_tr("乘(&M)"))
        self.rb_op_div.setText(safe_tr("除(&I)"))

        self.chk_skip_blanks.setText(safe_tr("跳过空单元(&B)"))
        self.chk_transpose.setText(safe_tr("转置(&E)"))
        self.btn_paste_link.setText(safe_tr("粘贴链接(&L)"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_cancel.setText(safe_tr("取消"))
