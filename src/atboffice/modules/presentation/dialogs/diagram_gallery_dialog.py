"""Office 2003 Diagram Gallery: the six classic diagram types."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("DiagramGalleryDialog", text)


# (SmartArt layout id, label, description)
DIAGRAM_TYPES: list[tuple[str, str, str]] = [
    ("orgChart", "组织结构图", "用于显示层次关系"),
    ("cycle", "循环图", "用于显示持续循环的过程"),
    ("radial", "射线图", "用于显示核心元素的关系"),
    ("pyramid", "棱锥图", "用于显示基于基础的关系"),
    ("venn", "维恩图", "用于显示元素间的重叠区域"),
    ("target", "目标图", "用于显示实现目标的步骤"),
]


class DiagramGalleryDialog(QDialog):
    """Pick a diagram type; ``selected_layout()`` returns the SmartArt layout id."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.resize(360, 320)
        layout = QVBoxLayout(self)
        self.lbl_prompt = QLabel(self)
        self.list_types = QListWidget(self)
        self.list_types.itemDoubleClicked.connect(lambda _item: self.accept())
        self.list_types.currentRowChanged.connect(self._on_row_changed)
        self.lbl_desc = QLabel(self)
        self.lbl_desc.setWordWrap(True)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.lbl_prompt)
        layout.addWidget(self.list_types, 1)
        layout.addWidget(self.lbl_desc)
        layout.addWidget(self.buttons)
        for layout_id, _label, _desc in DIAGRAM_TYPES:
            item = QListWidgetItem(self.list_types)
            item.setData(Qt.ItemDataRole.UserRole, layout_id)
        self.retranslate_ui()
        self.list_types.setCurrentRow(0)

    def selected_layout(self) -> str:
        item = self.list_types.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else DIAGRAM_TYPES[0][0]

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(DIAGRAM_TYPES):
            self.lbl_desc.setText(safe_tr(DIAGRAM_TYPES[row][2]))

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("图示库"))
        self.lbl_prompt.setText(safe_tr("选择图示类型(&S):"))
        for row, (_lid, label, _desc) in enumerate(DIAGRAM_TYPES):
            item = self.list_types.item(row)
            if item is not None:
                item.setText(safe_tr(label))
        self._on_row_changed(self.list_types.currentRow())
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok is not None:
            ok.setText(safe_tr("确定"))
        if cancel is not None:
            cancel.setText(safe_tr("取消"))
