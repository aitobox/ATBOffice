"""Protection tab for FormatCellsDialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("ProtectionTab", text)


class ProtectionTab(QWidget):
    """Tab 6: Cell locking and formula hiding."""

    def __init__(
        self,
        locked: bool = True,
        hidden: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.check_locked = QCheckBox(safe_tr("锁定(&L)"))
        self.check_locked.setChecked(locked)
        layout.addWidget(self.check_locked)

        self.check_hidden = QCheckBox(safe_tr("隐藏(&H)"))
        self.check_hidden.setChecked(hidden)
        layout.addWidget(self.check_hidden)

        self.hint_label = QLabel(
            safe_tr(
                "锁定单元格或隐藏公式只有在工作表受保护时才有效。"
                "若要保护工作表，请在“工具”菜单中指向“保护”，然后单击“保护工作表”。密码为可选项。"
            )
        )
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #666666; padding-top: 8px;")
        layout.addWidget(self.hint_label)

        layout.addStretch(1)

    def get_protection(self) -> dict[str, Any]:
        return {
            "locked": self.check_locked.isChecked(),
            "hidden": self.check_hidden.isChecked(),
        }

    def set_protection(self, locked: bool, hidden: bool) -> None:
        self.check_locked.setChecked(locked)
        self.check_hidden.setChecked(hidden)

    def retranslate_ui(self) -> None:
        self.check_locked.setText(safe_tr("锁定(&L)"))
        self.check_hidden.setText(safe_tr("隐藏(&H)"))
        self.hint_label.setText(
            safe_tr(
                "锁定单元格或隐藏公式只有在工作表受保护时才有效。"
                "若要保护工作表，请在“工具”菜单中指向“保护”，然后单击“保护工作表”。密码为可选项。"
            )
        )
