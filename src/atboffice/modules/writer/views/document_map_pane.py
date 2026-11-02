"""Document Map (文档结构图) navigation pane for Quire (Word 2003 port)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.layout.toc import get_paragraph_heading_level
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    all_paragraphs,
    plain_text,
)

if TYPE_CHECKING:
    from atboffice.modules.writer.views.caret_controller import CaretController


def safe_tr(text: str) -> str:
    """Translate UI text safely for DocumentMapPane."""
    return QCoreApplication.translate("DocumentMapPane", text)


class DocumentMapPane(QWidget):
    """Left sidebar tree pane displaying hierarchical document headings for rapid navigation."""

    heading_selected = Signal(int)  # para_id

    def __init__(
        self,
        doc: Document | None = None,
        controller: CaretController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc: Document = doc or Document()
        self.controller = controller
        self._updating: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        self.refresh_headings()
        self.retranslate_ui()

    def set_document(self, doc: Document) -> None:
        """Update active document and rebuild headings tree."""
        self.doc = doc
        self.refresh_headings()

    def refresh_headings(self) -> None:
        """Scan document headings and reconstruct the QTreeWidget hierarchy."""
        self._updating = True
        self.tree.clear()

        paras = list(all_paragraphs(self.doc))
        headings: list[tuple[Paragraph, int, str]] = []

        for p in paras:
            lvl = get_paragraph_heading_level(self.doc, p)
            if lvl is not None and 1 <= lvl <= 9:
                text = plain_text(p).strip()
                if not text:
                    text = safe_tr("(空白标题)")
                headings.append((p, lvl, text))

        if not headings:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, safe_tr("(无标题)"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            font = item.font(0)
            font.setItalic(True)
            item.setFont(0, font)
            item.setForeground(0, QColor(130, 130, 130))
            self._updating = False
            return

        # Stack of (level, QTreeWidgetItem)
        stack: list[tuple[int, QTreeWidgetItem]] = []

        for p, lvl, text in headings:
            while stack and stack[-1][0] >= lvl:
                stack.pop()

            if stack:
                item = QTreeWidgetItem(stack[-1][1])
            else:
                item = QTreeWidgetItem(self.tree)

            item.setText(0, text)
            item.setData(0, Qt.ItemDataRole.UserRole, p.id)
            item.setToolTip(0, text)

            # Style font
            font = item.font(0)
            if lvl == 1:
                font.setBold(True)
                font.setPointSize(10)
            else:
                font.setPointSize(9)
            item.setFont(0, font)

            stack.append((lvl, item))

        self.tree.expandAll()
        self._updating = False

    def sync_caret_para(self, p: Paragraph | None) -> None:
        """Synchronize active tree item with current caret paragraph."""
        if not p or self._updating:
            return

        target_id = p.id
        # Check if p is a heading or locate closest preceding heading
        paras = list(all_paragraphs(self.doc))
        if p in paras:
            idx = paras.index(p)
            for i in range(idx, -1, -1):
                cand = paras[i]
                if get_paragraph_heading_level(self.doc, cand) is not None:
                    target_id = cand.id
                    break

        # Find matching item in tree
        def _find_item(parent_item: QTreeWidgetItem | QTreeWidget) -> QTreeWidgetItem | None:
            is_tw = isinstance(parent_item, QTreeWidget)
            count = parent_item.topLevelItemCount() if is_tw else parent_item.childCount()
            for idx in range(count):
                child = parent_item.topLevelItem(idx) if is_tw else parent_item.child(idx)
                if child.data(0, Qt.ItemDataRole.UserRole) == target_id:
                    return child
                found = _find_item(child)
                if found:
                    return found
            return None

        match = _find_item(self.tree)
        if match:
            self._updating = True
            self.tree.setCurrentItem(match)
            self._updating = False

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating:
            return
        para_id = item.data(0, Qt.ItemDataRole.UserRole)
        if para_id is not None:
            self.heading_selected.emit(para_id)
            if self.controller:
                self.controller.set_caret(para_id, 0)

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.setWindowTitle(safe_tr("文档结构图"))
        if (
            self.tree.topLevelItemCount() == 1
            and self.tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole) is None
        ):
            self.tree.topLevelItem(0).setText(0, safe_tr("(无标题)"))
