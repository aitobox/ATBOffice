"""Office 2007-style Compatibility Checker shown before a lossy save."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.compat import Loss


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("CompatibilityDialog", text)


class CompatibilityDialog(QDialog):
    """Lists the features the chosen format cannot keep; Continue saves, Cancel aborts."""

    def __init__(self, losses: list[Loss], target_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.losses = losses
        self.target_name = target_name
        self.resize(560, 320)
        layout = QVBoxLayout(self)
        self.lbl_summary = QLabel(self)
        self.lbl_summary.setWordWrap(True)
        layout.addWidget(self.lbl_summary)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(3)
        self.tree.setRootIsDecorated(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for loss in losses:
            item = QTreeWidgetItem([loss.feature, loss.where, str(loss.count)])
            if loss.detail:
                item.setToolTip(0, loss.detail)
            self.tree.addTopLevelItem(item)
        layout.addWidget(self.tree, 1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("兼容性检查器"))
        self.lbl_summary.setText(safe_tr(
            "“{0}”所用的格式不支持文档中的以下功能。继续保存，这些内容将会丢失或被更改。"
        ).format(self.target_name))
        self.tree.setHeaderLabels([safe_tr("功能"), safe_tr("位置"), safe_tr("出现次数")])
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok is not None:
            ok.setText(safe_tr("继续(&C)"))
        if cancel is not None:
            cancel.setText(safe_tr("取消"))
