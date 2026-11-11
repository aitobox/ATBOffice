"""Office 24-Item Clipboard Task Pane for ATBOffice suite.

Collects cut/copied items across Quire, Ledger, Lectern, and external apps.
Displays snippet previews, type icons, item counters, and provides Paste All,
Clear All, and single-item click-to-paste actions.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QCoreApplication, QMimeData, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.ui.icons import get_office_icon


def safe_tr(text: str) -> str:
    """Translate UI text safely for ClipboardTaskPane."""
    return QCoreApplication.translate("ClipboardTaskPane", text)


@dataclass
class ClipItem:
    """Represents a single captured clipboard clipping."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    html: str = ""
    item_type: str = "text"  # "text", "table", "cells", "image"
    mime_data: QMimeData | None = None
    created_at: float = field(default_factory=time.time)


class ClipItemWidget(QFrame):
    """Clickable card representing one clipboard item in the task pane."""

    clicked = Signal(object)
    delete_requested = Signal(str)

    def __init__(self, item: ClipItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self._init_ui()

    def _init_ui(self) -> None:
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            ClipItemWidget {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 2px;
                margin-bottom: 2px;
            }
            ClipItemWidget:hover {
                background-color: #F2F5FB;
                border: 1px solid #316AC5;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 4, 4)
        layout.setSpacing(6)

        # Icon
        self.icon_lbl = QLabel(self)
        self.icon_lbl.setFixedSize(16, 16)
        self._update_icon()
        layout.addWidget(self.icon_lbl)

        # Snippet text
        preview_text = self._format_snippet(self.item.text)
        self.text_lbl = QLabel(preview_text, self)
        self.text_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setStyleSheet("color: #000000; font-size: 11px;")
        if self.item.text:
            self.text_lbl.setToolTip(self.item.text[:500])
        layout.addWidget(self.text_lbl, stretch=1)

        # Quick delete button
        self.btn_del = QToolButton(self)
        self.btn_del.setText("✕")
        self.btn_del.setToolTip(safe_tr("删除"))
        self.btn_del.setFixedSize(18, 18)
        self.btn_del.setStyleSheet(
            """
            QToolButton {
                border: none;
                background: transparent;
                color: #888888;
                font-size: 10px;
                border-radius: 2px;
            }
            QToolButton:hover {
                background-color: #E0E0E0;
                color: #C00000;
            }
            """
        )
        self.btn_del.clicked.connect(lambda: self.delete_requested.emit(self.item.id))
        layout.addWidget(self.btn_del)

    def _format_snippet(self, raw_text: str) -> str:
        text = raw_text.replace("\t", "    ").strip()
        if not text:
            if self.item.item_type == "image":
                return safe_tr("[图片]")
            elif self.item.item_type == "table":
                return safe_tr("[表格]")
            elif self.item.item_type == "cells":
                return safe_tr("[单元格数据]")
            return safe_tr("[对象]")
        lines = text.splitlines()
        first_lines = " ".join(line.strip() for line in lines[:3] if line.strip())
        if len(first_lines) > 120:
            return first_lines[:120] + "..."
        return first_lines

    def _update_icon(self) -> None:
        icon_key = "font"
        if self.item.item_type == "table":
            icon_key = "table"
        elif self.item.item_type == "cells":
            icon_key = "tablesBorders"
        elif self.item.item_type == "image":
            icon_key = "picture"
        pix = get_office_icon(icon_key).pixmap(16, 16)
        self.icon_lbl.setPixmap(pix)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked inside delete button
            if not self.btn_del.geometry().contains(event.pos()):
                self.clicked.emit(self.item)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: Any) -> None:
        menu = QMenu(self)
        act_paste = menu.addAction(safe_tr("粘贴 (&P)"))
        act_del = menu.addAction(safe_tr("删除 (&D)"))
        chosen = menu.exec(event.globalPos())
        if chosen == act_paste:
            self.clicked.emit(self.item)
        elif chosen == act_del:
            self.delete_requested.emit(self.item.id)


class ClipboardTaskPane(QWidget):
    """Office 2003 24-item Clipboard Task Pane component."""

    item_clicked = Signal(object)  # Emits ClipItem when single item clicked
    paste_all_requested = Signal(list)  # Emits list[ClipItem]
    cleared = Signal()

    MAX_CAPACITY = 24

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[ClipItem] = []
        self._inhibited: bool = False
        self._monitoring: bool = False
        self._init_ui()
        self.start_monitoring()
        self.destroyed.connect(lambda: self.stop_monitoring())

    def closeEvent(self, event: Any) -> None:
        self.stop_monitoring()
        super().closeEvent(event)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(6)

        # Top Button Bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(6)

        self.btn_paste_all = QPushButton(safe_tr("全部粘贴"), self)
        self.btn_paste_all.setFixedHeight(24)
        self.btn_paste_all.setStyleSheet(
            """
            QPushButton {
                background-color: #ECE9D8;
                border: 1px solid #7B9EBD;
                border-radius: 2px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QPushButton:hover:enabled {
                background-color: #B6BDD2;
                border: 1px solid #0A246A;
            }
            QPushButton:disabled {
                color: #A0A0A0;
            }
            """
        )
        self.btn_paste_all.clicked.connect(self.paste_all)
        btn_bar.addWidget(self.btn_paste_all)

        self.btn_clear_all = QPushButton(safe_tr("全部清空"), self)
        self.btn_clear_all.setFixedHeight(24)
        self.btn_clear_all.setStyleSheet(self.btn_paste_all.styleSheet())
        self.btn_clear_all.clicked.connect(self.clear_all)
        btn_bar.addWidget(self.btn_clear_all)

        btn_bar.addStretch(1)
        main_layout.addLayout(btn_bar)

        # Counter / Instructions note
        self.lbl_note = QLabel(self)
        self.lbl_note.setWordWrap(True)
        self.lbl_note.setStyleSheet("color: #444444; font-size: 11px; margin-top: 2px;")
        main_layout.addWidget(self.lbl_note)

        # Scroll Area for Clippings
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.list_container = QWidget(self.scroll_area)
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(3)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.list_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # Empty state prompt
        self.lbl_empty = QLabel(safe_tr("剪贴板为空。复制或剪切内容将在此处收集。"), self)
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("color: #888888; font-size: 11px; padding: 20px;")
        self.list_layout.addWidget(self.lbl_empty)

        self._refresh_ui()

    def start_monitoring(self) -> None:
        """Start listening to system QClipboard dataChanged signals."""
        if self._monitoring:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            self._monitoring = True
            clipboard.dataChanged.connect(self._on_clipboard_data_changed)

    def stop_monitoring(self) -> None:
        """Stop listening to system QClipboard changes."""
        if not self._monitoring:
            return
        self._monitoring = False
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            try:
                clipboard.dataChanged.disconnect(self._on_clipboard_data_changed)
            except Exception:
                pass

    def _on_clipboard_data_changed(self) -> None:
        """Handle incoming system clipboard change."""
        if not self._monitoring or self._inhibited:
            return

        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return

        mime = clipboard.mimeData()
        if mime is None:
            return

        text = mime.text() if mime.hasText() else ""
        html = mime.html() if mime.hasHtml() else ""
        has_image = mime.hasImage()

        if not text and not html and not has_image:
            return

        # Duplicate check against the most recent item
        if self._items:
            latest = self._items[0]
            if text and latest.text == text:
                return
            if not text and html and latest.html == html:
                return

        # Determine item type
        item_type = "text"
        html_lower = html.lower()
        if "<table" in html_lower or "<tr" in html_lower:
            item_type = "table"
        elif "\t" in text or "csv" in "".join(mime.formats()).lower():
            item_type = "cells"
        elif has_image:
            item_type = "image"

        # Clone QMimeData snapshot
        snapshot = QMimeData()
        if text:
            snapshot.setText(text)
        if html:
            snapshot.setHtml(html)
        if has_image:
            img = clipboard.image()
            if not img.isNull():
                snapshot.setImageData(img)

        item = ClipItem(
            text=text,
            html=html,
            item_type=item_type,
            mime_data=snapshot,
            created_at=time.time(),
        )

        self.add_clip_item(item)

    def add_clip_item(self, item: ClipItem) -> None:
        """Insert a new clipping into the top of the collection."""
        self._items.insert(0, item)
        if len(self._items) > self.MAX_CAPACITY:
            self._items.pop()
        self._refresh_ui()

    def paste_item(self, item: ClipItem) -> None:
        """Put item onto system clipboard (with inhibit guard) and emit item_clicked."""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            self._inhibited = True
            try:
                if item.text:
                    clipboard.setText(item.text)
                elif item.html:
                    cloned = QMimeData()
                    cloned.setHtml(item.html)
                    clipboard.setMimeData(cloned)
            finally:
                self._inhibited = False

        self.item_clicked.emit(item)

    def paste_all(self) -> None:
        """Emit paste_all_requested with items in reverse order (oldest to newest)."""
        if not self._items:
            return
        # Standard Office 2003 pastes all items starting from oldest
        items_to_paste = list(reversed(self._items))
        self.paste_all_requested.emit(items_to_paste)

    def clear_all(self) -> None:
        """Clear all clippings and update UI."""
        self._items.clear()
        self._refresh_ui()
        self.cleared.emit()

    def remove_item(self, item_id: str) -> None:
        """Remove a single item by ID."""
        self._items = [it for it in self._items if it.id != item_id]
        self._refresh_ui()

    def items(self) -> list[ClipItem]:
        """Return the current list of clippings."""
        return list(self._items)

    def count(self) -> int:
        """Return total number of captured clippings."""
        return len(self._items)

    def _refresh_ui(self) -> None:
        """Rebuild item cards and update button / label states."""
        # Clear existing item widgets
        while self.list_layout.count() > 0:
            child = self.list_layout.takeAt(0)
            w = child.widget()
            if w:
                w.deleteLater()

        count = len(self._items)
        has_items = count > 0

        self.btn_paste_all.setEnabled(has_items)
        self.btn_clear_all.setEnabled(has_items)

        note_tmpl = safe_tr("剪贴板：{0}/24。单击项目可粘贴。")
        self.lbl_note.setText(note_tmpl.format(count))

        if not has_items:
            self.lbl_empty = QLabel(safe_tr("剪贴板为空。复制或剪切内容将在此处收集。"), self)
            self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_empty.setStyleSheet("color: #888888; font-size: 11px; padding: 20px;")
            self.list_layout.addWidget(self.lbl_empty)
        else:
            for item in self._items:
                w = ClipItemWidget(item, self.list_container)
                w.clicked.connect(self.paste_item)
                w.delete_requested.connect(self.remove_item)
                self.list_layout.addWidget(w)

    def retranslate_ui(self) -> None:
        """Update localized UI strings."""
        self.btn_paste_all.setText(safe_tr("全部粘贴"))
        self.btn_clear_all.setText(safe_tr("全部清空"))
        count = len(self._items)
        note_tmpl = safe_tr("剪贴板：{0}/24。单击项目可粘贴。")
        self.lbl_note.setText(note_tmpl.format(count))
        if len(self._items) == 0 and hasattr(self, "lbl_empty") and self.lbl_empty is not None:
            self.lbl_empty.setText(safe_tr("剪贴板为空。复制或剪切内容将在此处收集。"))
