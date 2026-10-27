"""Slide comments bubble markers and card overlay widgets for Lectern."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.comment import (
    Comment,
    format_relative_time,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


def safe_tr(text: str) -> str:
    """Translate UI text with fallbacks."""
    app = QApplication.instance()
    if app:
        translated = app.translate("CommentOverlay", text)
        if translated and translated != text:
            return translated
    # Default to Chinese native text for ATBOffice
    return text


class CommentMarkerItem(QGraphicsItem):
    """Interactive sticky-note speech bubble marker drawn on the slide canvas."""

    def __init__(
        self,
        comment: Comment,
        presentation: Presentation | None = None,
        on_click: Callable[[CommentMarkerItem], None] | None = None,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.comment = comment
        self.presentation = presentation
        self.on_click = on_click
        self._is_hovered = False

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(1000.0)
        self.setPos(self.comment.x, self.comment.y)
        self.update_tooltip()

    def update_tooltip(self) -> None:
        """Update tooltip text with author and comment snippet."""
        author_name = safe_tr("审阅人")
        if self.presentation:
            author = self.presentation.find_author(self.comment.author_id)
            if author:
                author_name = author.name

        time_str = format_relative_time(self.comment.created)
        status_str = (
            safe_tr("已解决") if self.comment.status == "resolved" else safe_tr("未解决")
        )
        preview = self.comment.text.strip().replace("\n", " ")
        if len(preview) > 60:
            preview = preview[:57] + "..."

        tip = f"{author_name} ({status_str} · {time_str})\n{preview}"
        self.setToolTip(tip)

    def boundingRect(self) -> QRectF:
        """Bounding box including the bubble and bottom indicator tail."""
        return QRectF(-2.0, -2.0, 36.0, 38.0)

    def paint(
        self,
        painter: QPainter,
        option: Any,
        widget: QWidget | None = None,
    ) -> None:
        """Render iconic speech bubble badge with author initials."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        is_resolved = self.comment.status == "resolved"
        is_selected = self.isSelected()

        # Color palette
        if is_resolved:
            bg_color = QColor("#DEE2E6") if not self._is_hovered else QColor("#CED4DA")
            border_color = QColor("#ADB5BD")
            text_color = QColor("#6C757D")
        else:
            bg_color = QColor("#FFE066") if not self._is_hovered else QColor("#FFD43B")
            border_color = QColor("#F59F00")
            text_color = QColor("#212529")

        if is_selected:
            border_color = QColor("#1D76DB")

        pen = QPen(border_color, 1.8 if is_selected else 1.2)
        painter.setPen(pen)
        painter.setBrush(QBrush(bg_color))

        # Bubble geometry with small downward pointer tail
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.0, 0.0, 30.0, 24.0), 5.0, 5.0)
        # Pointer tail at bottom left
        tail = QPainterPath()
        tail.moveTo(5.0, 23.0)
        tail.lineTo(1.0, 32.0)
        tail.lineTo(13.0, 23.0)
        path = path.united(tail)

        painter.drawPath(path)

        # Draw author initials centered
        initials = "A"
        if self.presentation:
            author = self.presentation.find_author(self.comment.author_id)
            if author and author.initials:
                initials = author.initials[:2].upper()

        font = QFont("Helvetica", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(QRectF(0.0, 0.0, 30.0, 24.0), Qt.AlignmentFlag.AlignCenter, initials)

        painter.restore()

    def hoverEnterEvent(self, event: Any) -> None:
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: Any) -> None:
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mousePressEvent(event)
        if self.on_click:
            self.on_click(self)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = self.pos()
            self.comment.x = round(pos.x(), 2)
            self.comment.y = round(pos.y(), 2)
        return super().itemChange(change, value)


class CommentCardWidget(QFrame):
    """Rich card overlay displaying comment conversation thread, editor and replies."""

    commentUpdated = Signal(object)
    commentDeleted = Signal(object)
    closed = Signal()

    def __init__(
        self,
        comment: Comment,
        presentation: Presentation,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.comment = comment
        self.presentation = presentation

        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setStyleSheet(
            """
            QFrame#CommentCard {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 8px;
            }
            QLabel {
                color: #212529;
            }
            """
        )
        self.setObjectName("CommentCard")
        self.setFixedWidth(310)

        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 1. Header (Avatar, Name, Date, Status, Close)
        header = QHBoxLayout()
        header.setSpacing(6)

        author = self.presentation.find_author(self.comment.author_id)
        author_name = author.name if author else safe_tr("审阅人")
        initials = author.initials if author else "A"

        self.avatar_lbl = QLabel(initials)
        self.avatar_lbl.setFixedSize(26, 26)
        self.avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_lbl.setStyleSheet(
            """
            background-color: #FFE066;
            color: #212529;
            font-weight: bold;
            font-size: 11px;
            border-radius: 13px;
            border: 1px solid #F59F00;
            """
        )
        header.addWidget(self.avatar_lbl)

        info_box = QVBoxLayout()
        info_box.setSpacing(1)
        self.name_lbl = QLabel(author_name)
        self.name_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.date_lbl = QLabel(format_relative_time(self.comment.created))
        self.date_lbl.setStyleSheet("color: #868E96; font-size: 10px;")
        info_box.addWidget(self.name_lbl)
        info_box.addWidget(self.date_lbl)
        header.addLayout(info_box, 1)

        # Status toggle button
        self.status_btn = QToolButton()
        self.status_btn.setStyleSheet(
            """
            QToolButton {
                font-size: 11px;
                padding: 2px 6px;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                background-color: #F8F9FA;
            }
            QToolButton:hover {
                background-color: #E9ECEF;
            }
            """
        )
        self.status_btn.clicked.connect(self._toggle_status)
        header.addWidget(self.status_btn)

        # Delete button
        self.del_btn = QToolButton()
        self.del_btn.setText("🗑")
        self.del_btn.setToolTip(safe_tr("删除批注"))
        self.del_btn.setStyleSheet("QToolButton { border: none; font-size: 12px; }")
        self.del_btn.clicked.connect(self._on_delete)
        header.addWidget(self.del_btn)

        # Close button
        self.close_btn = QToolButton()
        self.close_btn.setText("✕")
        self.close_btn.setStyleSheet(
            "QToolButton { border: none; font-size: 12px; color: #868E96; }"
        )
        self.close_btn.clicked.connect(self._on_close)
        header.addWidget(self.close_btn)

        main_layout.addLayout(header)

        # 2. Main Comment Text Body
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(self.comment.text)
        self.text_edit.setMaximumHeight(75)
        self.text_edit.setStyleSheet(
            """
            QTextEdit {
                border: 1px solid #E9ECEF;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                background-color: #FAFAFA;
            }
            QTextEdit:focus {
                border-color: #1D76DB;
                background-color: #FFFFFF;
            }
            """
        )
        self.text_edit.textChanged.connect(self._on_text_changed)
        main_layout.addWidget(self.text_edit)

        # 3. Replies list container
        self.replies_area = QScrollArea()
        self.replies_area.setWidgetResizable(True)
        self.replies_area.setMaximumHeight(140)
        self.replies_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.replies_widget = QWidget()
        self.replies_layout = QVBoxLayout(self.replies_widget)
        self.replies_layout.setContentsMargins(0, 4, 0, 4)
        self.replies_layout.setSpacing(6)
        self.replies_area.setWidget(self.replies_widget)
        main_layout.addWidget(self.replies_area)
        self._refresh_replies()

        # 4. Reply input
        reply_box = QHBoxLayout()
        reply_box.setSpacing(4)
        self.reply_input = QLineEdit()
        self.reply_input.setPlaceholderText(safe_tr("添加答复..."))
        self.reply_input.setStyleSheet(
            """
            QLineEdit {
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #1D76DB;
            }
            """
        )
        self.reply_input.returnPressed.connect(self._submit_reply)
        reply_box.addWidget(self.reply_input, 1)

        self.reply_btn = QPushButton(safe_tr("答复"))
        self.reply_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #1D76DB;
                color: #FFFFFF;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #155CB0;
            }
            """
        )
        self.reply_btn.clicked.connect(self._submit_reply)
        reply_box.addWidget(self.reply_btn)
        main_layout.addLayout(reply_box)

    def _refresh_replies(self) -> None:
        """Repopulate replies list widgets."""
        # Clear previous layout children
        while self.replies_layout.count():
            item = self.replies_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.comment.replies:
            self.replies_area.setVisible(False)
            return

        self.replies_area.setVisible(True)
        for rep in self.comment.replies:
            rep_card = QFrame()
            rep_card.setStyleSheet(
                """
                QFrame {
                    background-color: #F8F9FA;
                    border: 1px solid #E9ECEF;
                    border-radius: 4px;
                }
                """
            )
            r_lay = QVBoxLayout(rep_card)
            r_lay.setContentsMargins(6, 4, 6, 4)
            r_lay.setSpacing(2)

            r_auth = self.presentation.find_author(rep.author_id)
            r_name = r_auth.name if r_auth else safe_tr("协作者")
            r_time = format_relative_time(rep.created)

            top_lbl = QLabel(f"{r_name} · {r_time}")
            top_lbl.setStyleSheet("color: #868E96; font-size: 10px; font-weight: bold;")
            msg_lbl = QLabel(rep.text)
            msg_lbl.setStyleSheet("font-size: 11px; color: #212529;")
            msg_lbl.setWordWrap(True)

            r_lay.addWidget(top_lbl)
            r_lay.addWidget(msg_lbl)
            self.replies_layout.addWidget(rep_card)

    def _toggle_status(self) -> None:
        """Toggle resolved vs active state."""
        if self.comment.status == "resolved":
            self.comment.status = "active"
        else:
            self.comment.status = "resolved"
        self.retranslate_ui()
        self.commentUpdated.emit(self.comment)

    def _on_text_changed(self) -> None:
        self.comment.text = self.text_edit.toPlainText()
        self.commentUpdated.emit(self.comment)

    def _submit_reply(self) -> None:
        text = self.reply_input.text().strip()
        if not text:
            return
        user_author = self.presentation.get_or_create_author(safe_tr("当前用户"))
        self.comment.add_reply(author_id=user_author.id, text=text)
        self.reply_input.clear()
        self._refresh_replies()
        self.commentUpdated.emit(self.comment)

    def _on_delete(self) -> None:
        self.commentDeleted.emit(self.comment)
        self.close()

    def _on_close(self) -> None:
        self.closed.emit()
        self.close()

    def retranslate_ui(self) -> None:
        """Update all localizable labels."""
        if self.comment.status == "resolved":
            self.status_btn.setText(safe_tr("重新打开"))
            self.status_btn.setToolTip(safe_tr("将此批注重新标记为未解决"))
        else:
            self.status_btn.setText(safe_tr("解决"))
            self.status_btn.setToolTip(safe_tr("将此批注标记为已解决"))

        self.del_btn.setToolTip(safe_tr("删除批注"))
        self.reply_input.setPlaceholderText(safe_tr("添加答复..."))
        self.reply_btn.setText(safe_tr("答复"))
