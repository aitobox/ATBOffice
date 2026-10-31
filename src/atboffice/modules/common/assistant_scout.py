"""Scout the Beagle desktop companion assistant for ATBOffice.

Features procedural vector rendering, idle breathing/tail-wagging/blinking animations,
drag-and-drop repositioning, comic speech balloons, and quick contextual actions.
"""

from __future__ import annotations

import datetime
import math
from typing import Any

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text with fallback to original string."""
    app = QApplication.instance()
    if app:
        translated = app.translate("AssistantScout", text)
        if translated and translated != text:
            return translated
    return text


def get_greeting() -> str:
    """Generate time-aware greeting message."""
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return safe_tr("早上好！我是 Scout，您的桌面伴侣助手。有什么我可以帮您的吗？")
    elif 12 <= hour < 18:
        return safe_tr("下午好！我是 Scout，保持专注，工作更高效哦！")
    else:
        return safe_tr("晚上好！我是 Scout，工作辛苦了，别忘了适时保存文档。")


class ScoutBalloon(QWidget):
    """Comic speech bubble displaying tips, greetings, and shortcut options."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(220, 110)
        self.setMaximumWidth(320)

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 26)  # extra bottom margin for bubble pointer
        main_layout.setSpacing(8)

        # Header with title and close button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.label_title = QLabel(safe_tr("🐶 Scout 助手"), self)
        font_title = QFont()
        font_title.setBold(True)
        self.label_title.setFont(font_title)
        self.label_title.setStyleSheet("color: #2e6bc6;")
        header_layout.addWidget(self.label_title)

        header_layout.addStretch()

        self.btn_close = QPushButton("×", self)
        self.btn_close.setFixedSize(18, 18)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(
            "QPushButton { border: none; font-size: 14px; color: #888; font-weight: bold; }"
            "QPushButton:hover { color: #d64541; }"
        )
        self.btn_close.clicked.connect(self.hide)
        header_layout.addWidget(self.btn_close)

        main_layout.addLayout(header_layout)

        # Speech body
        self.label_text = QLabel(self)
        self.label_text.setWordWrap(True)
        self.label_text.setStyleSheet("color: #222; font-size: 13px; line-height: 1.3;")
        main_layout.addWidget(self.label_text, stretch=1)

    def set_text(self, text: str) -> None:
        """Set speech text and adjust size to fit."""
        self.label_text.setText(text)
        self.adjustSize()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        pointer_h = 16.0
        bubble_h = h - pointer_h

        # Rounded bubble background
        path = QPainterPath()
        path.addRoundedRect(QRectF(2, 2, w - 4, bubble_h - 4), 12.0, 12.0)

        # Downward speech pointer towards bottom-right (Scout's head)
        tip_x = w * 0.75
        pointer = QPolygonF(
            [
                QPoint(int(tip_x - 12), int(bubble_h - 4)),
                QPoint(int(tip_x + 12), int(bubble_h - 4)),
                QPoint(int(tip_x + 4), int(h - 2)),
            ]
        )
        path.addPolygon(pointer)

        # Fill bubble
        painter.fillPath(path, QBrush(QColor(255, 255, 255, 245)))

        # Border
        pen = QPen(QColor(160, 185, 215), 1.6)
        painter.strokePath(path, pen)
        painter.end()


class ScoutWidget(QWidget):
    """Floating desktop companion Scout the Beagle."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(154, 140)

        self.balloon = ScoutBalloon()
        self.is_animating = False

        # Animation states
        self._breath_phase = 0.0
        self._tail_phase = 0.0
        self._blink_counter = 0
        self._is_blinking = False
        self._trick_angle = 0.0
        self._drag_start_pos: QPoint | None = None
        self._drag_mouse_offset: QPoint | None = None

        # Timers
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(40)  # ~25 fps
        self._idle_timer.timeout.connect(self._on_idle_tick)
        self._idle_timer.start()

        self._trick_timer = QTimer(self)
        self._trick_timer.setInterval(30)
        self._trick_timer.timeout.connect(self._on_trick_tick)

        self._init_position()

    def _init_position(self) -> None:
        """Position Scout near the bottom right of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            self.move(geom.right() - self.width() - 40, geom.bottom() - self.height() - 60)

    def speak(self, text: str) -> None:
        """Display speech balloon with provided text."""
        self.balloon.set_text(text)
        self._position_balloon()
        self.balloon.show()
        self.balloon.raise_()

    def _position_balloon(self) -> None:
        """Position speech balloon right above Scout."""
        bx = self.x() + (self.width() // 2) - int(self.balloon.width() * 0.75)
        by = self.y() - self.balloon.height() + 10
        self.balloon.move(max(10, bx), max(10, by))

    def play_trick(self) -> None:
        """Trigger enthusiastic acrobatic animation."""
        if self.is_animating:
            return
        self.is_animating = True
        self._trick_angle = 0.0
        self._trick_timer.start()

    def _on_trick_tick(self) -> None:
        self._trick_angle += 18.0
        if self._trick_angle >= 360.0:
            self._trick_angle = 0.0
            self.is_animating = False
            self._trick_timer.stop()
            self.speak(safe_tr("汪！表演完毕，喜欢吗？"))
        self.update()

    def _on_idle_tick(self) -> None:
        """Advance idle animation phases."""
        self._breath_phase += 0.06
        if self._breath_phase > math.tau:
            self._breath_phase -= math.tau

        self._tail_phase += 0.12
        if self._tail_phase > math.tau:
            self._tail_phase -= math.tau

        self._blink_counter += 1
        if self._blink_counter > 75:  # blink roughly every 3 seconds
            self._is_blinking = True
            if self._blink_counter > 80:
                self._is_blinking = False
                self._blink_counter = 0

        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_mouse_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_mouse_offset:
            new_pos = event.globalPosition().toPoint() - self._drag_mouse_offset
            self.move(new_pos)
            if self.balloon.isVisible():
                self._position_balloon()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            dist = (event.globalPosition().toPoint() - self._drag_start_pos).manhattanLength()
            if dist < 5:  # Click without drag
                if self.balloon.isVisible():
                    self.balloon.hide()
                else:
                    self.speak(get_greeting())
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: Any) -> None:
        """Show context menu for Scout."""
        menu = QMenu(self)

        act_trick = menu.addAction(safe_tr("动一动! (&A)"))
        act_trick.triggered.connect(self.play_trick)

        menu.addSeparator()

        act_search = menu.addAction(safe_tr("搜索命令 (&S)..."))
        act_search.setShortcut("Alt+Q")
        act_search.triggered.connect(self._on_search_commands)

        act_help = menu.addAction(safe_tr("ATBOffice 帮助 (&H)"))
        act_help.setShortcut("F1")
        act_help.triggered.connect(self._on_open_help)

        act_update = menu.addAction(safe_tr("检查软件更新 (&U)..."))
        act_update.triggered.connect(self._on_check_update)

        menu.addSeparator()

        act_hide = menu.addAction(safe_tr("隐藏伴侣助手 (&Hide)"))
        act_hide.triggered.connect(self.hide)

        menu.exec(QCursor.pos())

    def _on_search_commands(self) -> None:
        self.speak(safe_tr("提示：按 Alt+Q 或点击菜单栏可直接检索所有 Office 功能。"))

    def _on_open_help(self) -> None:
        self.speak(safe_tr("您可以点击菜单栏【帮助 -> 帮助文档】查阅详细使用手册。"))

    def _on_check_update(self) -> None:
        from atboffice.core.updater import check_for_updates

        check_for_updates(parent=self, manual=True)

    def moveEvent(self, event: Any) -> None:
        super().moveEvent(event)
        if self.balloon and self.balloon.isVisible():
            self._position_balloon()

    def hideEvent(self, event: Any) -> None:
        super().hideEvent(event)
        if self.balloon:
            self.balloon.hide()

    def closeEvent(self, event: Any) -> None:
        if self._idle_timer.isActive():
            self._idle_timer.stop()
        if self._trick_timer.isActive():
            self._trick_timer.stop()
        if self.balloon:
            self.balloon.close()
        super().closeEvent(event)

    def paintEvent(self, event: Any) -> None:
        """Procedurally render Scout the Beagle on his blue oval mat with QPainter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Center reference point
        cx = self.width() / 2.0
        cy = self.height() / 2.0 + 8.0

        if self.is_animating and self._trick_angle != 0.0:
            painter.translate(cx, cy)
            painter.rotate(self._trick_angle)
            painter.translate(-cx, -cy)

        # Breathing oscillation
        breath = math.sin(self._breath_phase) * 1.5
        tail_rot = math.sin(self._tail_phase) * 16.0

        # 1. Blue Oval Mat (Sleeping pad)
        mat_rect = QRectF(cx - 62, cy + 22, 124, 34)
        painter.setPen(QPen(QColor("#1f4e79"), 2.0))
        painter.setBrush(QBrush(QColor("#2f6fb3")))
        painter.drawEllipse(mat_rect)

        # Inner stitch line on mat
        inner_mat = QRectF(cx - 54, cy + 26, 108, 26)
        stitch_pen = QPen(QColor("#7fb0e6"), 1.2, Qt.PenStyle.DashLine)
        painter.setPen(stitch_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(inner_mat)

        # 2. Tail (behind body)
        tail_base_x = cx + 32
        tail_base_y = cy + 18
        painter.save()
        painter.translate(tail_base_x, tail_base_y)
        painter.rotate(tail_rot)

        tail_path = QPainterPath()
        tail_path.moveTo(0, 0)
        tail_path.quadTo(18, -12, 26, -26)
        tail_path.quadTo(20, -18, 0, 8)
        tail_path.closeSubpath()

        painter.setPen(QPen(QColor("#4a3426"), 1.8))
        painter.setBrush(QBrush(QColor("#c97a3c")))
        painter.drawPath(tail_path)

        # White tip of tail
        painter.setBrush(QBrush(QColor("#fbf8f2")))
        painter.drawEllipse(QPoint(24, -24), 5, 5)
        painter.restore()

        # 3. Body (Tan beagle body)
        body_rect = QRectF(cx - 36, cy - 14 - breath, 72, 48 + breath)
        painter.setPen(QPen(QColor("#4a3426"), 2.0))
        painter.setBrush(QBrush(QColor("#c97a3c")))
        painter.drawEllipse(body_rect)

        # White chest patch
        chest_rect = QRectF(cx - 20, cy - 2 - breath, 40, 34 + breath)
        painter.setBrush(QBrush(QColor("#fbf8f2")))
        painter.drawEllipse(chest_rect)

        # 4. Front Paws
        painter.setPen(QPen(QColor("#4a3426"), 1.8))
        painter.setBrush(QBrush(QColor("#fbf8f2")))
        # Left paw
        painter.drawRoundedRect(QRectF(cx - 24, cy + 28, 18, 12), 6, 6)
        # Right paw
        painter.drawRoundedRect(QRectF(cx + 6, cy + 28, 18, 12), 6, 6)

        # 5. Red Collar and Golden Tag
        collar_rect = QRectF(cx - 25, cy - 18 - (breath * 0.6), 50, 11)
        painter.setPen(QPen(QColor("#4a3426"), 1.5))
        painter.setBrush(QBrush(QColor("#d64541")))
        painter.drawRoundedRect(collar_rect, 4, 4)

        # Golden tag
        tag_pos = QPoint(int(cx), int(cy - 10 - (breath * 0.6)))
        painter.setPen(QPen(QColor("#a67c1e"), 1.2))
        painter.setBrush(QBrush(QColor("#f0bf45")))
        painter.drawEllipse(tag_pos, 5, 5)

        # 6. Head
        head_cy = cy - 36 - (breath * 0.4)
        head_rect = QRectF(cx - 30, head_cy - 22, 60, 48)
        painter.setPen(QPen(QColor("#4a3426"), 2.0))
        painter.setBrush(QBrush(QColor("#c97a3c")))
        painter.drawEllipse(head_rect)

        # White muzzle
        muzzle_rect = QRectF(cx - 18, head_cy - 4, 36, 26)
        painter.setBrush(QBrush(QColor("#fbf8f2")))
        painter.drawEllipse(muzzle_rect)

        # Black nose
        nose_rect = QRectF(cx - 7, head_cy - 3, 14, 9)
        painter.setBrush(QBrush(QColor("#231d1a")))
        painter.drawEllipse(nose_rect)

        # Mouth line
        painter.setPen(QPen(QColor("#4a3426"), 1.5))
        painter.drawLine(QPoint(int(cx), int(head_cy + 6)), QPoint(int(cx), int(head_cy + 13)))
        painter.drawLine(QPoint(int(cx - 6), int(head_cy + 15)), QPoint(int(cx), int(head_cy + 13)))
        painter.drawLine(QPoint(int(cx + 6), int(head_cy + 15)), QPoint(int(cx), int(head_cy + 13)))

        # Eyes
        eye_y = head_cy - 8
        if self._is_blinking:
            # Closed eye curves
            painter.drawLine(QPoint(int(cx - 15), int(eye_y)), QPoint(int(cx - 7), int(eye_y)))
            painter.drawLine(QPoint(int(cx + 7), int(eye_y)), QPoint(int(cx + 15), int(eye_y)))
        else:
            # Left eye
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#5a3218")))
            painter.drawEllipse(QRectF(cx - 16, eye_y - 5, 9, 10))
            painter.setBrush(QBrush(QColor("#140c08")))
            painter.drawEllipse(QRectF(cx - 14, eye_y - 3, 6, 7))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(QRectF(cx - 13, eye_y - 4, 3, 3))

            # Right eye
            painter.setBrush(QBrush(QColor("#5a3218")))
            painter.drawEllipse(QRectF(cx + 7, eye_y - 5, 9, 10))
            painter.setBrush(QBrush(QColor("#140c08")))
            painter.drawEllipse(QRectF(cx + 8, eye_y - 3, 6, 7))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(QRectF(cx + 9, eye_y - 4, 3, 3))

        # 7. Floppy Brown Ears
        painter.setPen(QPen(QColor("#4a3426"), 2.0))
        painter.setBrush(QBrush(QColor("#8c4c22")))

        # Left ear
        left_ear = QPainterPath()
        left_ear.moveTo(cx - 24, head_cy - 12)
        left_ear.cubicTo(cx - 42, head_cy - 6, cx - 44, head_cy + 22, cx - 26, head_cy + 18)
        left_ear.closeSubpath()
        painter.drawPath(left_ear)

        # Right ear
        right_ear = QPainterPath()
        right_ear.moveTo(cx + 24, head_cy - 12)
        right_ear.cubicTo(cx + 42, head_cy - 6, cx + 44, head_cy + 22, cx + 26, head_cy + 18)
        right_ear.closeSubpath()
        painter.drawPath(right_ear)

        painter.end()


# Module-level singleton
_global_scout: ScoutWidget | None = None


def get_scout_assistant() -> ScoutWidget:
    """Return the global Scout companion assistant singleton."""
    global _global_scout
    if _global_scout is None:
        _global_scout = ScoutWidget()
    return _global_scout


def toggle_assistant() -> None:
    """Toggle visibility of global Scout assistant."""
    scout = get_scout_assistant()
    if scout.isVisible():
        scout.hide()
    else:
        scout.show()
        scout.speak(get_greeting())
