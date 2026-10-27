"""Slide Sorter View (幻灯片浏览视图) for Lectern presentations.

Provides:
- Multi-column responsive grid card layout adapting to viewport width.
- Slide thumbnails with sequence numbering, transition effect badges, advance timing, and hidden slide indicators.
- Multi-selection support (single-click, Ctrl/Cmd+click, Shift+click).
- Visual drag-and-drop slide reordering with insertion line indicator.
- Double-click navigation into Normal view.
- Context menu for batch slide operations (duplicate, delete, toggle hide, transitions).
- Full i18n support.
"""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.workspace import render_slide_thumbnail


def safe_tr(text: str) -> str:
    """Safe translation for Slide Sorter UI."""
    app = QApplication.instance()
    if app:
        translated = app.translate("SlideSorter", text)
        if translated and translated != text:
            return translated
    return text


def fmt_duration(seconds: float | None) -> str:
    """Format duration in seconds into mm:ss (e.g. 5.0 -> '00:05')."""
    if seconds is None or seconds < 0:
        return ""
    total_secs = int(round(seconds))
    mins = total_secs // 60
    secs = total_secs % 60
    return f"{mins:02d}:{secs:02d}"


class SlideSorterCard(QFrame):
    """Card representing a single slide in the Slide Sorter View."""

    clicked = Signal(int, Qt.KeyboardModifiers)
    double_clicked = Signal(int)
    drag_started = Signal(int, QPoint)
    context_menu_requested = Signal(int, QPoint)

    def __init__(
        self,
        slide: Slide,
        index: int,
        presentation: Presentation,
        card_width: int = 180,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slide = slide
        self.index = index
        self.presentation = presentation
        self.card_width = card_width
        self.is_selected = False
        self._press_pos: QPoint | None = None
        self._is_dragging = False

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self._init_ui()
        self.update_style()

    @property
    def is_hidden_slide(self) -> bool:
        return bool(self.slide.hidden)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 1. Slide Thumbnail Preview
        self.thumb_label = QLabel(self)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.thumb_label)

        # 2. Footer container (star icon, time, slide number, hidden badge)
        self.footer = QWidget(self)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(2, 0, 2, 0)
        footer_layout.setSpacing(4)

        # Transition icon (Star)
        self.star_label: QLabel | None = None
        trans = getattr(self.slide, "transition", None)
        if trans and trans.type and trans.type != "none":
            self.star_label = QLabel("★", self.footer)
            self.star_label.setFont(QFont("Arial", 11))
            self.star_label.setStyleSheet("color: #444444;")
            tip = f"{safe_tr('转场效果')}: {trans.type}"
            if trans.speed:
                tip += f" ({trans.speed})"
            self.star_label.setToolTip(tip)
            footer_layout.addWidget(self.star_label)

        # Advance duration timing
        self.time_label: QLabel | None = None
        if trans and trans.after is not None:
            formatted_time = fmt_duration(trans.after)
            self.time_label = QLabel(formatted_time, self.footer)
            self.time_label.setFont(QFont("Arial", 8))
            self.time_label.setStyleSheet("color: #666666;")
            footer_layout.addWidget(self.time_label)

        footer_layout.addStretch()

        # Hidden slide indicator
        self.hidden_badge: QLabel | None = None
        if self.is_hidden_slide:
            self.hidden_badge = QLabel(safe_tr("[隐藏]"), self.footer)
            self.hidden_badge.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            self.hidden_badge.setStyleSheet("color: #999999;")
            footer_layout.addWidget(self.hidden_badge)

        # Slide Number
        first_num = getattr(self.presentation, "first_num", 1)
        slide_num_str = str(self.index + first_num)
        self.number_label = QLabel(slide_num_str, self.footer)
        self.number_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.number_label.setStyleSheet("color: #333333;")
        footer_layout.addWidget(self.number_label)

        layout.addWidget(self.footer)

        self.refresh_thumbnail()

    def refresh_thumbnail(self) -> None:
        """Render and set the slide thumbnail pixmap."""
        thumb_w = max(80, self.card_width - 12)
        pixmap = render_slide_thumbnail(self.slide, self.presentation, width=thumb_w)
        if self.is_hidden_slide:
            # Dim the thumbnail preview for hidden slides
            dimmed = QPixmap(pixmap.size())
            dimmed.fill(Qt.GlobalColor.transparent)
            painter = QPainter(dimmed)
            painter.setOpacity(0.5)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            pixmap = dimmed

        self.thumb_label.setPixmap(pixmap)
        self.thumb_label.setFixedSize(pixmap.size())
        self.setFixedSize(self.card_width, pixmap.height() + 38)

    def set_card_width(self, width: int) -> None:
        if self.card_width != width:
            self.card_width = width
            self.refresh_thumbnail()

    def set_selected(self, selected: bool) -> None:
        if self.is_selected != selected:
            self.is_selected = selected
            self.update_style()

    def update_style(self) -> None:
        if self.is_selected:
            self.setStyleSheet(
                """
                SlideSorterCard {
                    background-color: #DCE6F1;
                    border: 2px solid #2B579A;
                    border-radius: 4px;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                SlideSorterCard {
                    background-color: #FFFFFF;
                    border: 1px solid #D0D0D0;
                    border-radius: 4px;
                }
                SlideSorterCard:hover {
                    border: 1px solid #707070;
                    background-color: #F8F9FA;
                }
                """
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self._is_dragging = False
            self.clicked.emit(self.index, event.modifiers())
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(self.index, event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            delta = (event.position().toPoint() - self._press_pos).manhattanLength()
            if delta > QApplication.startDragDistance() and not self._is_dragging:
                self._is_dragging = True
                self.drag_started.emit(self.index, self.mapToParent(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._press_pos = None
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.index)
        super().mouseDoubleClickEvent(event)


class SlideSorterGridWidget(QWidget):
    """Grid container holding sorter cards and drawing insertion indicator."""

    def __init__(self, sorter_view: SlideSorterView) -> None:
        super().__init__(sorter_view)
        self.sorter_view = sorter_view
        self.setMouseTracking(True)
        self.drop_marker_x: int | None = None
        self.drop_marker_y: int | None = None
        self.drop_marker_h: int = 120

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self.drop_marker_x is not None and self.drop_marker_y is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor("#2B579A"), 3.0)
            painter.setPen(pen)
            x = self.drop_marker_x
            y = self.drop_marker_y
            h = self.drop_marker_h
            painter.drawLine(x, y, x, y + h)
            # Arrow heads on top and bottom of insertion marker
            painter.setBrush(QColor("#2B579A"))
            painter.drawPolygon([QPoint(x - 5, y), QPoint(x + 5, y), QPoint(x, y + 6)])
            painter.drawPolygon([QPoint(x - 5, y + h), QPoint(x + 5, y + h), QPoint(x, y + h - 6)])
            painter.end()


class SlideSorterView(QScrollArea):
    """Scrollable multi-column Slide Sorter View."""

    slide_selected = Signal(int)
    slide_double_clicked = Signal(int)
    slides_reordered = Signal(list, int)

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
        self.cards: list[SlideSorterCard] = []
        self._selected_indices: set[int] = set()
        self.card_width: int = 180
        self.spacing: int = 16
        self.padding: int = 16
        self.zoom: float = 0.25

        # Drag state
        self._dragging_indices: list[int] = []
        self._drop_target_index: int | None = None

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QScrollArea { background-color: #E8E8E8; }")

        self.grid_widget = SlideSorterGridWidget(self)
        self.setWidget(self.grid_widget)

        self.empty_label = QLabel(safe_tr("暂无幻灯片"), self.grid_widget)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setFont(QFont("Arial", 12))
        self.empty_label.setStyleSheet("color: #888888; padding: 40px;")
        self.empty_label.hide()

        self.load_presentation(self.presentation)

    def load_presentation(self, presentation: Presentation) -> None:
        """Load presentation slides and construct cards."""
        self.presentation = presentation
        self._selected_indices.clear()

        # Clear existing cards
        for card in self.cards:
            card.deleteLater()
        self.cards.clear()

        slides = getattr(presentation, "slides", [])
        if not slides:
            self.empty_label.show()
            self._reflow_cards()
            return

        self.empty_label.hide()
        for idx, slide in enumerate(slides):
            card = SlideSorterCard(
                slide=slide,
                index=idx,
                presentation=presentation,
                card_width=self.card_width,
                parent=self.grid_widget,
            )
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.drag_started.connect(self._on_card_drag_started)
            card.context_menu_requested.connect(self._on_card_context_menu)
            card.show()
            self.cards.append(card)

        # Select first slide by default if available
        if self.cards:
            self._selected_indices.add(0)
            self.cards[0].set_selected(True)

        self._reflow_cards()

    def get_selected_indices(self) -> set[int]:
        """Return the set of currently selected slide indices."""
        return set(self._selected_indices)

    def select_slide(self, index: int) -> None:
        """Set a single slide as selected."""
        if not (0 <= index < len(self.cards)):
            return
        self._selected_indices.clear()
        self._selected_indices.add(index)
        self._sync_card_selection()
        self.slide_selected.emit(index)

    def select_range(self, from_idx: int, to_idx: int) -> None:
        """Select a contiguous range of slides (Shift+Click)."""
        start = max(0, min(from_idx, to_idx))
        end = min(len(self.cards) - 1, max(from_idx, to_idx))
        self._selected_indices = set(range(start, end + 1))
        self._sync_card_selection()
        if self.cards:
            self.slide_selected.emit(to_idx)

    def toggle_slide_selection(self, index: int) -> None:
        """Toggle slide selection state (Ctrl/Cmd+Click)."""
        if not (0 <= index < len(self.cards)):
            return
        if index in self._selected_indices and len(self._selected_indices) > 1:
            self._selected_indices.remove(index)
        else:
            self._selected_indices.add(index)
        self._sync_card_selection()
        self.slide_selected.emit(index)

    def _sync_card_selection(self) -> None:
        for idx, card in enumerate(self.cards):
            card.set_selected(idx in self._selected_indices)

    def set_zoom(self, zoom: float) -> None:
        """Set zoom scale (e.g. 0.2 to 1.0)."""
        clamped = max(0.15, min(1.0, zoom))
        if abs(self.zoom - clamped) > 0.01:
            self.zoom = clamped
            base_w = int(240 * self.zoom / 0.25)
            self.card_width = max(120, min(480, base_w))
            for card in self.cards:
                card.set_card_width(self.card_width)
            self._reflow_cards()

    def _reflow_cards(self) -> None:
        """Arrange cards in a responsive flow grid based on current viewport width."""
        avail_w = self.viewport().width()
        if avail_w <= 0:
            avail_w = 800

        if not self.cards:
            self.empty_label.setGeometry(0, 0, avail_w, 200)
            self.grid_widget.resize(avail_w, 200)
            return

        card_w = self.card_width
        card_h = self.cards[0].height() if self.cards else 140
        num_cols = max(1, (avail_w - self.padding * 2 + self.spacing) // (card_w + self.spacing))

        col = 0
        row = 0
        total_w = num_cols * card_w + (num_cols - 1) * self.spacing
        start_x = max(self.padding, (avail_w - total_w) // 2)

        for card in self.cards:
            x = start_x + col * (card_w + self.spacing)
            y = self.padding + row * (card_h + self.spacing)
            card.move(x, y)

            col += 1
            if col >= num_cols:
                col = 0
                row += 1

        total_rows = (len(self.cards) + num_cols - 1) // num_cols
        total_h = self.padding * 2 + total_rows * card_h + max(0, total_rows - 1) * self.spacing
        self.grid_widget.resize(avail_w, max(total_h, self.viewport().height()))
        self.grid_widget.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._reflow_cards()

    def _on_card_clicked(self, index: int, modifiers: Qt.KeyboardModifiers) -> None:
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            anchor = min(self._selected_indices) if self._selected_indices else 0
            self.select_range(anchor, index)
        elif modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            self.toggle_slide_selection(index)
        else:
            self.select_slide(index)

    def _on_card_double_clicked(self, index: int) -> None:
        self.slide_double_clicked.emit(index)

    def _on_card_drag_started(self, index: int, global_pos: QPoint) -> None:
        if index not in self._selected_indices:
            self.select_slide(index)
        self._dragging_indices = sorted(self._selected_indices)
        self._drop_target_index = None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging_indices:
            pos = self.grid_widget.mapFrom(self, event.position().toPoint())
            self._update_drop_marker(pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging_indices and self._drop_target_index is not None:
            self.move_slides(self._dragging_indices, self._drop_target_index)
        self._dragging_indices = []
        self._drop_target_index = None
        self.grid_widget.drop_marker_x = None
        self.grid_widget.drop_marker_y = None
        self.grid_widget.update()
        super().mouseReleaseEvent(event)

    def _update_drop_marker(self, pos: QPoint) -> None:
        """Find closest card gap to position the drop indicator line."""
        if not self.cards:
            return

        target_idx = len(self.cards)
        best_ref: SlideSorterCard | None = None
        before = True

        for k, card in enumerate(self.cards):
            geo = card.geometry()
            margin = 12
            if (geo.top() - margin <= pos.y() <= geo.bottom() + margin) and (
                pos.x() < geo.left() + geo.width() / 2
            ):
                target_idx = k
                best_ref = card
                before = True
                break
            if geo.top() - margin <= pos.y() <= geo.bottom() + margin:
                best_ref = card
                before = False
                target_idx = k + 1

        if best_ref:
            self._drop_target_index = target_idx
            geo = best_ref.geometry()
            marker_x = (geo.left() - self.spacing // 2) if before else (geo.right() + self.spacing // 2)
            self.grid_widget.drop_marker_x = marker_x
            self.grid_widget.drop_marker_y = geo.top()
            self.grid_widget.drop_marker_h = geo.height()
            self.grid_widget.update()

    def move_slides(self, indices: list[int], target_index: int) -> None:
        """Move one or more slides to a target insertion position."""
        if not indices or not self.presentation.slides:
            return

        sorted_indices = sorted(set(indices))
        slides_to_move = [self.presentation.slides[i] for i in sorted_indices]

        # Remove from high index to low index to keep remaining indices valid
        for i in reversed(sorted_indices):
            del self.presentation.slides[i]

        # Adjust target index for items removed before target
        offset = sum(1 for i in sorted_indices if i < target_index)
        adj_target = max(0, min(len(self.presentation.slides), target_index - offset))

        # Insert slides
        for k, s in enumerate(slides_to_move):
            self.presentation.slides.insert(adj_target + k, s)

        new_selected = set(range(adj_target, adj_target + len(slides_to_move)))
        self.load_presentation(self.presentation)
        self._selected_indices = new_selected
        self._sync_card_selection()
        self.slides_reordered.emit(sorted_indices, target_index)

    def duplicate_selected_slides(self) -> None:
        """Duplicate all currently selected slides."""
        if not self._selected_indices or not self.presentation.slides:
            return
        sorted_indices = sorted(self._selected_indices)
        insert_pos = sorted_indices[-1] + 1
        new_indices: list[int] = []

        for offset, idx in enumerate(sorted_indices):
            orig_slide = self.presentation.slides[idx]
            new_slide = copy.deepcopy(orig_slide)
            new_slide.id = f"slide_{id(new_slide)}"
            pos = insert_pos + offset
            self.presentation.slides.insert(pos, new_slide)
            new_indices.append(pos)

        self.load_presentation(self.presentation)
        self._selected_indices = set(new_indices)
        self._sync_card_selection()

    def delete_selected_slides(self) -> None:
        """Delete all currently selected slides."""
        if not self._selected_indices or not self.presentation.slides:
            return
        for idx in sorted(self._selected_indices, reverse=True):
            if 0 <= idx < len(self.presentation.slides):
                del self.presentation.slides[idx]

        self.load_presentation(self.presentation)

    def toggle_hide_selected_slides(self) -> None:
        """Toggle hidden state for selected slides."""
        if not self._selected_indices or not self.presentation.slides:
            return
        for idx in self._selected_indices:
            if 0 <= idx < len(self.presentation.slides):
                s = self.presentation.slides[idx]
                s.hidden = not s.hidden

        self.load_presentation(self.presentation)

    def _on_card_context_menu(self, index: int, global_pos: QPoint) -> None:
        """Pop up context menu for card operations."""
        if index not in self._selected_indices:
            self.select_slide(index)

        menu = QMenu(self)
        act_dup = menu.addAction(safe_tr("复制幻灯片"))
        act_del = menu.addAction(safe_tr("删除幻灯片"))
        act_hide = menu.addAction(safe_tr("隐藏幻灯片") if not self.presentation.slides[index].hidden else safe_tr("取消隐藏"))

        action = menu.exec(global_pos)
        if action == act_dup:
            self.duplicate_selected_slides()
        elif action == act_del:
            self.delete_selected_slides()
        elif action == act_hide:
            self.toggle_hide_selected_slides()

    def retranslate_ui(self) -> None:
        """Retranslate all sorter view components."""
        self.empty_label.setText(safe_tr("暂无幻灯片"))
        for card in self.cards:
            if card.star_label and card.slide.transition:
                tip = f"{safe_tr('转场效果')}: {card.slide.transition.type}"
                if card.slide.transition.speed:
                    tip += f" ({card.slide.transition.speed})"
                card.star_label.setToolTip(tip)
            if card.hidden_badge:
                card.hidden_badge.setText(safe_tr("[隐藏]"))
