"""Outline view and Outline toolbar for Quire (Word 2003 parity).

Provides heading level hierarchy (Levels 1-9), promote, demote, move up/down,
expand, collapse, and outline toolbar interactions.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.layout.toc import get_paragraph_heading_level
from atboffice.modules.writer.models.document import (
    Document,
    Paragraph,
    all_paragraphs,
    plain_text,
    reindex,
)
from atboffice.modules.writer.models.styles import builtin_styles

if TYPE_CHECKING:
    from atboffice.modules.writer.views.caret_controller import CaretController


def safe_tr(text: str) -> str:
    """Translate UI text safely for Outline components."""
    return QCoreApplication.translate("OutlineView", text)


def heading_level(doc: Document, p: Paragraph) -> int:
    """Return heading level 1-9, or 0 if body text."""
    lvl = get_paragraph_heading_level(doc, p)
    return lvl if lvl is not None else 0


def ensure_heading_style(doc: Document, level: int) -> str:
    """Ensure style for heading level exists in document styles dictionary."""
    style_id = f"Heading{level}"
    if style_id not in doc.styles:
        b_styles = builtin_styles()
        if style_id in b_styles:
            doc.styles[style_id] = b_styles[style_id]
    return style_id


def promote_paragraph(doc: Document, p: Paragraph) -> int:
    """Promote heading level (e.g. 2 -> 1, or body text -> Heading 1/above)."""
    curr = heading_level(doc, p)
    if curr == 0:
        # Body text: find preceding heading level
        paras = list(all_paragraphs(doc))
        idx = paras.index(p) if p in paras else -1
        above = 0
        for i in range(idx - 1, -1, -1):
            alvl = heading_level(doc, paras[i])
            if alvl:
                above = alvl
                break
        new_lvl = min(9, above or 1)
    else:
        new_lvl = max(1, curr - 1)

    style_id = ensure_heading_style(doc, new_lvl)
    p.p_pr.style = style_id
    p.p_pr.outline_level = new_lvl - 1
    return new_lvl


def demote_paragraph(doc: Document, p: Paragraph) -> int:
    """Demote heading level (e.g. 1 -> 2, up to 9)."""
    curr = heading_level(doc, p)
    if curr == 0:
        return 0
    new_lvl = min(9, curr + 1)
    style_id = ensure_heading_style(doc, new_lvl)
    p.p_pr.style = style_id
    p.p_pr.outline_level = new_lvl - 1
    return new_lvl


def promote_to_heading_1(doc: Document, p: Paragraph) -> int:
    """Promote paragraph directly to Heading 1."""
    style_id = ensure_heading_style(doc, 1)
    p.p_pr.style = style_id
    p.p_pr.outline_level = 0
    return 1


def demote_to_body_text(doc: Document, p: Paragraph) -> int:
    """Demote paragraph to body text (Normal)."""
    p.p_pr.style = "Normal"
    p.p_pr.outline_level = None
    return 0


def get_collapsed_extent(
    doc: Document, idx: int, collapsed_ids: set[int] | None = None
) -> int:
    """Return ending index of collapsed heading subtree, or idx if not collapsed."""
    blocks = doc.main.blocks
    if not (0 <= idx < len(blocks)):
        return idx
    b = blocks[idx]
    if not isinstance(b, Paragraph):
        return idx
    lv = heading_level(doc, b)
    if not lv or not collapsed_ids or b.id not in collapsed_ids:
        return idx
    k = idx + 1
    while k < len(blocks):
        sub = blocks[k]
        if isinstance(sub, Paragraph):
            sub_lv = heading_level(doc, sub)
            if sub_lv != 0 and sub_lv <= lv:
                break
        k += 1
    return k - 1


def move_paragraph(
    doc: Document,
    p: Paragraph,
    delta: int,
    collapsed_ids: set[int] | None = None,
) -> bool:
    """Move paragraph (and subordinate children if collapsed) up (-1) or down (+1)."""
    blocks = doc.main.blocks
    if p not in blocks:
        return False

    i0 = blocks.index(p)
    i1 = get_collapsed_extent(doc, i0, collapsed_ids)

    if delta < 0:
        if i0 == 0:
            return False
        j = i0 - 1
        chunk = blocks[i0 : i1 + 1]
        del blocks[i0 : i1 + 1]
        blocks[j:j] = chunk
        reindex(doc)
        return True

    elif delta > 0:
        if i1 >= len(blocks) - 1:
            return False
        j = get_collapsed_extent(doc, i1 + 1, collapsed_ids)
        chunk = blocks[i0 : i1 + 1]
        after = blocks[i1 + 1 : j + 1]
        blocks[i0 : j + 1] = after + chunk
        reindex(doc)
        return True

    return False


class OutlineToolbar(QToolBar):
    """Word 2003 styled Outline Toolbar."""

    promote_requested = Signal()
    demote_requested = Signal()
    promote_h1_requested = Signal()
    demote_body_requested = Signal()
    move_up_requested = Signal()
    move_down_requested = Signal()
    expand_requested = Signal()
    collapse_requested = Signal()
    show_level_changed = Signal(int)
    first_line_toggled = Signal(bool)
    show_formatting_toggled = Signal(bool)
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tb_outline")
        self.setWindowTitle(safe_tr("大纲工具栏"))
        self.setMovable(True)

        self._btn_promote_h1 = QToolButton(self)
        self._btn_promote_h1.setText("<<")
        self._btn_promote_h1.setToolTip(safe_tr("升级到 1 级 (Alt+Shift+1)"))
        self._btn_promote_h1.clicked.connect(self.promote_h1_requested.emit)
        self.addWidget(self._btn_promote_h1)

        self._btn_promote = QToolButton(self)
        self._btn_promote.setText("<")
        self._btn_promote.setToolTip(safe_tr("升级 (Alt+Shift+左箭头)"))
        self._btn_promote.clicked.connect(self.promote_requested.emit)
        self.addWidget(self._btn_promote)

        self._combo_outline_level = QComboBox(self)
        self._combo_outline_level.setToolTip(safe_tr("大纲级别"))
        self._combo_outline_level.currentIndexChanged.connect(self._on_outline_level_changed)
        self.addWidget(self._combo_outline_level)

        self._btn_demote = QToolButton(self)
        self._btn_demote.setText(">")
        self._btn_demote.setToolTip(safe_tr("降级 (Alt+Shift+右箭头)"))
        self._btn_demote.clicked.connect(self.demote_requested.emit)
        self.addWidget(self._btn_demote)

        self._btn_demote_body = QToolButton(self)
        self._btn_demote_body.setText(">>")
        self._btn_demote_body.setToolTip(safe_tr("降级为正文 (Ctrl+Shift+N)"))
        self._btn_demote_body.clicked.connect(self.demote_body_requested.emit)
        self.addWidget(self._btn_demote_body)

        self.addSeparator()

        self._btn_move_up = QToolButton(self)
        self._btn_move_up.setText("▲")
        self._btn_move_up.setToolTip(safe_tr("上移 (Alt+Shift+上箭头)"))
        self._btn_move_up.clicked.connect(self.move_up_requested.emit)
        self.addWidget(self._btn_move_up)

        self._btn_move_down = QToolButton(self)
        self._btn_move_down.setText("▼")
        self._btn_move_down.setToolTip(safe_tr("下移 (Alt+Shift+下箭头)"))
        self._btn_move_down.clicked.connect(self.move_down_requested.emit)
        self.addWidget(self._btn_move_down)

        self.addSeparator()

        self._btn_expand = QToolButton(self)
        self._btn_expand.setText("+")
        self._btn_expand.setToolTip(safe_tr("展开 (Alt+Shift+加号)"))
        self._btn_expand.clicked.connect(self.expand_requested.emit)
        self.addWidget(self._btn_expand)

        self._btn_collapse = QToolButton(self)
        self._btn_collapse.setText("−")
        self._btn_collapse.setToolTip(safe_tr("折叠 (Alt+Shift+减号)"))
        self._btn_collapse.clicked.connect(self.collapse_requested.emit)
        self.addWidget(self._btn_collapse)

        self.addSeparator()

        self._combo_show_level = QComboBox(self)
        self._combo_show_level.setToolTip(safe_tr("显示级别"))
        self._combo_show_level.currentIndexChanged.connect(self._on_show_level_changed)
        self.addWidget(self._combo_show_level)

        self._btn_first_line = QToolButton(self)
        self._btn_first_line.setCheckable(True)
        self._btn_first_line.setText("===")
        self._btn_first_line.setToolTip(safe_tr("只显示首行"))
        self._btn_first_line.toggled.connect(self.first_line_toggled.emit)
        self.addWidget(self._btn_first_line)

        self._btn_show_formatting = QToolButton(self)
        self._btn_show_formatting.setCheckable(True)
        self._btn_show_formatting.setChecked(True)
        self._btn_show_formatting.setText("A")
        self._btn_show_formatting.setToolTip(safe_tr("显示格式"))
        self._btn_show_formatting.toggled.connect(self.show_formatting_toggled.emit)
        self.addWidget(self._btn_show_formatting)

        self.addSeparator()

        self._btn_close = QToolButton(self)
        self._btn_close.setText(safe_tr("关闭大纲视图"))
        self._btn_close.setToolTip(safe_tr("关闭大纲视图返回页面视图"))
        self._btn_close.clicked.connect(self.close_requested.emit)
        self.addWidget(self._btn_close)

        self.retranslate_ui()

    def _on_outline_level_changed(self, idx: int) -> None:
        pass

    def _on_show_level_changed(self, idx: int) -> None:
        # idx 0: All Levels (0), idx 1..9: Level 1..9
        self.show_level_changed.emit(idx)

    def set_current_level(self, level: int) -> None:
        """Update outline level combo to reflect currently active heading level (0..9)."""
        if 0 <= level <= 9:
            self._combo_outline_level.blockSignals(True)
            self._combo_outline_level.setCurrentIndex(level)
            self._combo_outline_level.blockSignals(False)

    def retranslate_ui(self) -> None:
        """Update localized UI strings."""
        self.setWindowTitle(safe_tr("大纲工具栏"))
        self._btn_promote_h1.setToolTip(safe_tr("升级到 1 级 (Alt+Shift+1)"))
        self._btn_promote.setToolTip(safe_tr("升级 (Alt+Shift+左箭头)"))
        self._btn_demote.setToolTip(safe_tr("降级 (Alt+Shift+右箭头)"))
        self._btn_demote_body.setToolTip(safe_tr("降级为正文 (Ctrl+Shift+N)"))
        self._btn_move_up.setToolTip(safe_tr("上移 (Alt+Shift+上箭头)"))
        self._btn_move_down.setToolTip(safe_tr("下移 (Alt+Shift+下箭头)"))
        self._btn_expand.setToolTip(safe_tr("展开 (Alt+Shift+加号)"))
        self._btn_collapse.setToolTip(safe_tr("折叠 (Alt+Shift+减号)"))
        self._btn_first_line.setToolTip(safe_tr("只显示首行"))
        self._btn_show_formatting.setToolTip(safe_tr("显示格式"))
        self._btn_close.setText(safe_tr("关闭大纲视图"))
        self._btn_close.setToolTip(safe_tr("关闭大纲视图返回页面视图"))

        # Re-populate outline level combo
        cur_ol = self._combo_outline_level.currentIndex()
        self._combo_outline_level.blockSignals(True)
        self._combo_outline_level.clear()
        self._combo_outline_level.addItem(safe_tr("正文文本"))
        for i in range(1, 10):
            self._combo_outline_level.addItem(safe_tr(f"{i} 级"))
        if cur_ol >= 0:
            self._combo_outline_level.setCurrentIndex(cur_ol)
        self._combo_outline_level.blockSignals(False)

        # Re-populate show level combo
        cur_sl = self._combo_show_level.currentIndex()
        self._combo_show_level.blockSignals(True)
        self._combo_show_level.clear()
        self._combo_show_level.addItem(safe_tr("所有级别"))
        for i in range(1, 10):
            self._combo_show_level.addItem(safe_tr(f"显示至 {i} 级"))
        if cur_sl >= 0:
            self._combo_show_level.setCurrentIndex(cur_sl)
        self._combo_show_level.blockSignals(False)


class OutlineViewWidget(QWidget):
    """Word 2003 styled Outline View document display and interaction canvas."""

    paragraph_clicked = Signal(Paragraph)
    paragraph_double_clicked = Signal(Paragraph)
    structure_changed = Signal()

    def __init__(
        self,
        doc: Document | None = None,
        controller: CaretController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc: Document = doc or Document()
        self.controller = controller
        self.collapsed_ids: set[int] = set()
        self.show_level: int = 0  # 0: all levels, 1..9: show up to level
        self.first_line_only: bool = False
        self.show_formatting: bool = True
        self.selected_para: Paragraph | None = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Track row bounding rects for mouse hit-testing
        self._item_rects: list[tuple[QRect, Paragraph, bool]] = []  # (rect, para, is_symbol)

    def set_document(self, doc: Document) -> None:
        self.doc = doc
        self.collapsed_ids.clear()
        self.update()

    def set_show_level(self, level: int) -> None:
        self.show_level = level
        self.update()

    def set_first_line_only(self, first_line: bool) -> None:
        self.first_line_only = first_line
        self.update()

    def set_show_formatting(self, show_formatting: bool) -> None:
        self.show_formatting = show_formatting
        self.update()

    def toggle_collapse(self, p: Paragraph) -> None:
        if p.id in self.collapsed_ids:
            self.collapsed_ids.remove(p.id)
        else:
            self.collapsed_ids.add(p.id)
        self.update()
        self.structure_changed.emit()

    def promote_selected(self) -> None:
        p = self.selected_para or (self.controller.caret_para if self.controller else None)
        if p:
            promote_paragraph(self.doc, p)
            self.update()
            self.structure_changed.emit()

    def demote_selected(self) -> None:
        p = self.selected_para or (self.controller.caret_para if self.controller else None)
        if p:
            demote_paragraph(self.doc, p)
            self.update()
            self.structure_changed.emit()

    def promote_selected_h1(self) -> None:
        p = self.selected_para or (self.controller.caret_para if self.controller else None)
        if p:
            promote_to_heading_1(self.doc, p)
            self.update()
            self.structure_changed.emit()

    def demote_selected_body(self) -> None:
        p = self.selected_para or (self.controller.caret_para if self.controller else None)
        if p:
            demote_to_body_text(self.doc, p)
            self.update()
            self.structure_changed.emit()

    def move_selected_up(self) -> None:
        p = self.selected_para or (self.controller.caret_para if self.controller else None)
        if p and move_paragraph(self.doc, p, -1, self.collapsed_ids):
            self.update()
            self.structure_changed.emit()

    def move_selected_down(self) -> None:
        p = self.selected_para or (self.controller.caret_para if self.controller else None)
        if p and move_paragraph(self.doc, p, 1, self.collapsed_ids):
            self.update()
            self.structure_changed.emit()

    def expand_selected(self) -> None:
        p = self.selected_para or (self.controller.caret_para if self.controller else None)
        if p and p.id in self.collapsed_ids:
            self.collapsed_ids.remove(p.id)
            self.update()
            self.structure_changed.emit()

    def collapse_selected(self) -> None:
        p = self.selected_para or (self.controller.caret_para if self.controller else None)
        if p and heading_level(self.doc, p) > 0:
            self.collapsed_ids.add(p.id)
            self.update()
            self.structure_changed.emit()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Background
        painter.fillRect(self.rect(), QColor(255, 255, 255))

        self._item_rects.clear()

        paras = list(all_paragraphs(self.doc))
        y = 16
        line_height = 24
        hide_under_level = 0

        for p in paras:
            lvl = heading_level(self.doc, p)

            # Check if this heading unlocks a previous collapse
            if lvl > 0:
                if hide_under_level and lvl <= hide_under_level:
                    hide_under_level = 0

            # Filter by show_level
            if self.show_level > 0:
                effective = lvl if lvl > 0 else 10
                if effective > self.show_level:
                    continue

            # Hidden by a collapsed parent heading
            if hide_under_level > 0 and (lvl == 0 or lvl > hide_under_level):
                continue

            # Render paragraph row
            indent = (lvl - 1) * 24 + 20 if lvl > 0 else 40
            row_rect = QRect(indent, y, self.width() - indent - 20, line_height)
            sym_rect = QRect(indent - 18, y + 4, 16, 16)

            is_selected = (self.selected_para and self.selected_para.id == p.id) or (
                self.controller and self.controller.caret_para and self.controller.caret_para.id == p.id
            )

            if is_selected:
                painter.fillRect(QRect(0, y, self.width(), line_height), QColor(210, 230, 255))

            # Draw symbol
            painter.setPen(QPen(QColor(80, 80, 80), 1))
            if lvl > 0:
                is_coll = p.id in self.collapsed_ids
                painter.drawRect(sym_rect)
                painter.drawText(
                    sym_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    "+" if is_coll else "−",
                )
            else:
                # Body bullet
                painter.setBrush(QColor(100, 100, 100))
                painter.drawEllipse(sym_rect.center(), 2, 2)
                painter.setBrush(Qt.BrushStyle.NoBrush)

            # Draw text
            text = plain_text(p)
            if self.first_line_only and "\n" in text:
                text = text.split("\n", 1)[0]
            if not text.strip():
                text = safe_tr("(空白段落)") if lvl == 0 else safe_tr("(无标题文本)")

            font = painter.font()
            if self.show_formatting and lvl > 0:
                font.setBold(True)
                font.setPointSize(max(9, 14 - lvl))
            else:
                font.setBold(False)
                font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(QColor(0, 0, 0) if is_selected else QColor(40, 40, 40))

            painter.drawText(
                row_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

            self._item_rects.append((row_rect, p, False))
            self._item_rects.append((sym_rect, p, True))

            if lvl > 0 and p.id in self.collapsed_ids and not hide_under_level:
                hide_under_level = lvl

            y += line_height

        self.setMinimumHeight(max(300, y + 20))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pt = event.position().toPoint()
        for rect, p, is_sym in self._item_rects:
            if rect.contains(pt):
                if is_sym and heading_level(self.doc, p) > 0:
                    self.toggle_collapse(p)
                    return
                self.selected_para = p
                if self.controller:
                    self.controller.set_caret(p.id, 0)
                self.paragraph_clicked.emit(p)
                self.update()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        pt = event.position().toPoint()
        for rect, p, is_sym in self._item_rects:
            if rect.contains(pt):
                if heading_level(self.doc, p) > 0:
                    self.toggle_collapse(p)
                self.paragraph_double_clicked.emit(p)
                return
        super().mouseDoubleClickEvent(event)
