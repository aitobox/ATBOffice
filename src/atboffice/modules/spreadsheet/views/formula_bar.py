"""Formula Bar component for spreadsheet formula editing and cell reference navigation."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.references import parse_cell, parse_range


def safe_tr(text: str) -> str:
    """Translate UI text safely for FormulaBar."""
    return QCoreApplication.translate("FormulaBar", text)


class FormulaBar(QWidget):
    """Top formula bar widget containing NameBox, action buttons, and formula editor."""

    navigate_requested = Signal(int, int)
    range_navigate_requested = Signal(int, int, int, int)
    text_changed = Signal(str)
    editing_started = Signal()
    commit_requested = Signal()
    cancel_requested = Signal()
    fx_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_editing: bool = False
        self._internal_change: bool = False

        self.setFixedHeight(26)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # 1. Name Box (Address / Defined name indicator and jumper)
        self.name_box = QLineEdit(self)
        self.name_box.setFixedWidth(80)
        self.name_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_box.returnPressed.connect(self._on_name_box_return)
        layout.addWidget(self.name_box)

        # 2. Cancel Button ('✕')
        self.btn_cancel = QToolButton(self)
        self.btn_cancel.setFixedSize(20, 20)
        self.btn_cancel.setText("✕")
        self.btn_cancel.setStyleSheet(
            "QToolButton { color: #c0281a; font-weight: bold; font-size: 11px; "
            "border: 1px solid transparent; border-radius: 2px; } "
            "QToolButton:hover { border: 1px solid #c0281a; background-color: #fde8e8; } "
            "QToolButton:disabled { color: #aaaaaa; }"
        )
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.btn_cancel)

        # 3. Commit Button ('✓')
        self.btn_commit = QToolButton(self)
        self.btn_commit.setFixedSize(20, 20)
        self.btn_commit.setText("✓")
        self.btn_commit.setStyleSheet(
            "QToolButton { color: #1b8a2a; font-weight: bold; font-size: 12px; "
            "border: 1px solid transparent; border-radius: 2px; } "
            "QToolButton:hover { border: 1px solid #1b8a2a; background-color: #e8f5e9; } "
            "QToolButton:disabled { color: #aaaaaa; }"
        )
        self.btn_commit.setEnabled(False)
        self.btn_commit.clicked.connect(self._on_commit_clicked)
        layout.addWidget(self.btn_commit)

        # 4. Insert Function Button ('fx')
        self.btn_fx = QToolButton(self)
        self.btn_fx.setFixedSize(22, 20)
        self.btn_fx.setText("fx")
        fx_font = QFont("Times New Roman", 10)
        fx_font.setItalic(True)
        self.btn_fx.setFont(fx_font)
        self.btn_fx.setStyleSheet(
            "QToolButton { color: #1a3f8a; font-weight: bold; "
            "border: 1px solid transparent; border-radius: 2px; } "
            "QToolButton:hover { border: 1px solid #1a3f8a; background-color: #e8eef8; }"
        )
        self.btn_fx.clicked.connect(self._on_fx_clicked)
        layout.addWidget(self.btn_fx)

        # 5. Formula / Value Input
        self.formula_input = QLineEdit(self)
        self.formula_input.textChanged.connect(self._on_formula_text_changed)
        self.formula_input.returnPressed.connect(self._on_commit_clicked)
        layout.addWidget(self.formula_input)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Update localized UI text and tooltips."""
        self.name_box.setToolTip(safe_tr("名称框：跳转至指定单元格或区域"))
        self.btn_cancel.setToolTip(safe_tr("取消 (Esc)"))
        self.btn_commit.setToolTip(safe_tr("输入 (Enter)"))
        self.btn_fx.setToolTip(safe_tr("插入函数"))
        self.formula_input.setPlaceholderText(safe_tr("在此处输入公式或内容..."))

    def set_address(self, address: str) -> None:
        """Update the displayed cell address or selection dimension in the NameBox."""
        if not self.name_box.hasFocus():
            self.name_box.setText(address)

    def set_cell_text(self, text: str) -> None:
        """Update the text shown in the formula bar without triggering recursive edit events."""
        if self._is_editing and self.formula_input.hasFocus():
            return
        self._internal_change = True
        self.formula_input.setText(text)
        self._internal_change = False

    def text(self) -> str:
        """Return the current formula input string."""
        return self.formula_input.text()

    def set_text(self, text: str) -> None:
        """Directly set text in the formula input."""
        self._internal_change = True
        self.formula_input.setText(text)
        self._internal_change = False

    def set_editing_state(self, is_editing: bool) -> None:
        """Update visual state and enable/disable cancel and commit buttons."""
        self._is_editing = is_editing
        self.btn_cancel.setEnabled(is_editing)
        self.btn_commit.setEnabled(is_editing)

    def _on_name_box_return(self) -> None:
        text = self.name_box.text().strip().upper()
        if not text:
            return

        # Check for range: e.g. A1:B10
        if ":" in text:
            rng = parse_range(text)
            if rng is not None:
                self.range_navigate_requested.emit(
                    rng["r1"], rng["c1"], rng["r2"], rng["c2"]
                )
                return

        # Check for single cell: e.g. B5
        cell_info = parse_cell(text)
        if cell_info is not None:
            self.navigate_requested.emit(cell_info["r"], cell_info["c"])

    def _on_formula_text_changed(self, text: str) -> None:
        if self._internal_change:
            return
        if not self._is_editing:
            self.set_editing_state(True)
            self.editing_started.emit()
        self.text_changed.emit(text)

    def _on_cancel_clicked(self) -> None:
        self.cancel_requested.emit()

    def _on_commit_clicked(self) -> None:
        self.commit_requested.emit()

    def _on_fx_clicked(self) -> None:
        self.fx_requested.emit()
