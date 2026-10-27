"""PowerPoint 2003 Classic Slide Layout Selection Dialog for Lectern."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.layouts import LAYOUTS


def safe_tr(text: str) -> str:
    """Translate UI text safely for SlideLayoutDialog."""
    return QCoreApplication.translate("SlideLayoutDialog", text)


class SlideLayoutDialog(QDialog):
    """Slide Layout Picker Dialog showcasing PowerPoint 2003 slide layouts."""

    def __init__(
        self,
        current_layout: str = "title",
        on_select: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.current_layout = current_layout
        self.on_select = on_select
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("Slide Layout"))
        self.resize(480, 420)

        layout = QVBoxLayout(self)

        self.instruction_lbl = QLabel(safe_tr("Apply slide layout:"))
        layout.addWidget(self.instruction_lbl)

        self.layout_list = QListWidget()
        self.layout_list.setIconSize(QSize(48, 36))
        self.layout_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._populate_layouts()
        layout.addWidget(self.layout_list)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText(safe_tr("&Apply"))
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_layouts(self) -> None:
        self.layout_list.clear()
        for l_info in LAYOUTS:
            item = QListWidgetItem(f"{l_info.name} ({safe_tr(l_info.group)})")
            item.setData(Qt.ItemDataRole.UserRole, l_info.key)
            self.layout_list.addItem(item)
            if l_info.key == self.current_layout:
                self.layout_list.setCurrentItem(item)

        if not self.layout_list.currentItem() and self.layout_list.count() > 0:
            self.layout_list.setCurrentRow(0)

    def select_layout(self, layout_key: str) -> None:
        for idx in range(self.layout_list.count()):
            item = self.layout_list.item(idx)
            if item.data(Qt.ItemDataRole.UserRole) == layout_key:
                self.layout_list.setCurrentItem(item)
                break

    def get_selected_layout(self) -> str:
        item = self.layout_list.currentItem()
        if item:
            return str(item.data(Qt.ItemDataRole.UserRole))
        return self.current_layout

    def apply_layout(self) -> None:
        selected = self.get_selected_layout()
        if self.on_select:
            self.on_select(selected)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._on_accept()

    def _on_accept(self) -> None:
        self.apply_layout()
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("Slide Layout"))
        self.instruction_lbl.setText(safe_tr("Apply slide layout:"))
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText(safe_tr("&Apply"))
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(safe_tr("Cancel"))
        self._populate_layouts()
