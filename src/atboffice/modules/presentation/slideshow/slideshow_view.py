"""Fullscreen interactive presentation slideshow viewport for Lectern."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QWidget,
)

from atboffice.modules.presentation.models.slide import Slide, Transition
from atboffice.modules.presentation.slideshow.transitions import (
    get_transition_duration,
    render_slide_to_image,
    render_transition_frame,
    safe_tr,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


class SlideShowView(QWidget):
    """High-performance double-buffered slide show presentation viewport."""

    slideChanged = Signal(int)
    showEnded = Signal()

    def __init__(
        self,
        presentation: Presentation,
        start_slide_index: int = 0,
        fullscreen: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.is_active = True
        self.in_transition = False
        self.is_ended = False
        self.blank_color: str | None = None
        self.goto_buf: str = ""
        self._mouse_down = False
        self._cursor_visible = True

        # Build slide display order (all slide indices)
        self.order: list[int] = list(range(len(presentation.slides)))
        if not self.order:
            self.order = [0]

        # Starting position in order
        if 0 <= start_slide_index < len(self.order):
            self.pos = start_slide_index
        else:
            self.pos = 0

        # Pre-render cache
        self._cache: dict[int, QImage] = {}

        # Transition animation state
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)  # ~60 FPS
        self._anim_timer.timeout.connect(self._on_anim_frame)
        self._anim_t0: float = 0.0
        self._anim_dur: int = 500
        self._img_prev: QImage | None = None
        self._img_curr: QImage | None = None
        self._active_transition: Transition | None = None

        # Auto-advance timing
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._on_auto_advance)

        # Idle cursor timer (auto-hide cursor after 3s)
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(3000)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_cursor_idle)

        # Window properties
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        if fullscreen:
            self.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.FramelessWindowHint
            )
            self.showFullScreen()
        else:
            self.setWindowFlags(Qt.WindowType.Window)
            self.resize(960, 540)

        # Render first slide immediately
        self._load_current_slide_image()
        self._schedule_auto_advance()
        self._idle_timer.start()

    @property
    def current_slide_index(self) -> int:
        if 0 <= self.pos < len(self.order):
            return self.order[self.pos]
        return 0

    @property
    def current_slide(self) -> Slide | None:
        idx = self.current_slide_index
        if 0 <= idx < len(self.presentation.slides):
            return self.presentation.slides[idx]
        return None

    # --------------------------------------------------------------------------
    # Image Caching & Slide Loading
    # --------------------------------------------------------------------------

    def _get_slide_image(self, slide_idx: int) -> QImage:
        if slide_idx in self._cache:
            return self._cache[slide_idx]
        if 0 <= slide_idx < len(self.presentation.slides):
            slide = self.presentation.slides[slide_idx]
            img = render_slide_to_image(
                slide,
                self.presentation,
                int(self.presentation.w),
                int(self.presentation.h),
            )
            self._cache[slide_idx] = img
            return img

        # Fallback empty image
        img = QImage(int(self.presentation.w), int(self.presentation.h), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor("#FFFFFF"))
        return img

    def _load_current_slide_image(self) -> None:
        self._img_curr = self._get_slide_image(self.current_slide_index)

    # --------------------------------------------------------------------------
    # Navigation Methods
    # --------------------------------------------------------------------------

    def next_slide(self) -> None:
        """Advance to next slide, complete transition, unblank, or exit."""
        if not self.is_active:
            return

        # 1. If screen is blanked, restore it
        if self.blank_color is not None:
            self.blank_color = None
            self.update()
            return

        # 2. If already at end-screen, exit show
        if self.is_ended:
            self.end_show()
            return

        # 3. If transition currently playing, finish it immediately
        if self.in_transition:
            self.finish_transition_now()
            return

        # 4. Find next non-hidden slide
        next_pos = self.pos + 1
        while next_pos < len(self.order):
            s_idx = self.order[next_pos]
            if 0 <= s_idx < len(self.presentation.slides):
                if not self.presentation.slides[s_idx].hidden:
                    break
            next_pos += 1

        # 5. Check if past end
        if next_pos >= len(self.order):
            if self.presentation.show.loop:
                # Wrap to beginning
                loop_pos = 0
                while loop_pos < len(self.order) - 1:
                    s_idx = self.order[loop_pos]
                    if 0 <= s_idx < len(self.presentation.slides) and not self.presentation.slides[s_idx].hidden:
                        break
                    loop_pos += 1
                self._transition_to_pos(loop_pos)
            else:
                self.is_ended = True
                self._auto_timer.stop()
                self.update()
            return

        self._transition_to_pos(next_pos)

    def prev_slide(self) -> None:
        """Return to previous slide or unblank."""
        if not self.is_active:
            return

        if self.blank_color is not None:
            self.blank_color = None
            self.update()
            return

        if self.is_ended:
            self.is_ended = False
            self.update()
            return

        if self.in_transition:
            self.finish_transition_now()

        prev_pos = self.pos - 1
        while prev_pos >= 0:
            s_idx = self.order[prev_pos]
            if 0 <= s_idx < len(self.presentation.slides):
                if not self.presentation.slides[s_idx].hidden:
                    break
            prev_pos -= 1

        if prev_pos < 0:
            return

        self._transition_to_pos(prev_pos)

    def goto_slide(self, slide_index: int) -> None:
        """Directly jump to a specified slide index."""
        if not self.is_active:
            return
        if slide_index in self.order:
            pos = self.order.index(slide_index)
            self._transition_to_pos(pos)

    def first_slide(self) -> None:
        """Jump to the very first slide."""
        if self.order:
            self._transition_to_pos(0)

    def last_slide(self) -> None:
        """Jump to the very last slide."""
        if self.order:
            self._transition_to_pos(len(self.order) - 1)

    def _transition_to_pos(self, new_pos: int) -> None:
        """Transition from current slide to new_pos."""
        self._auto_timer.stop()
        old_idx = self.current_slide_index
        self.pos = new_pos
        new_idx = self.current_slide_index
        self.is_ended = False

        self._img_prev = self._img_curr or self._get_slide_image(old_idx)
        self._img_curr = self._get_slide_image(new_idx)

        # Get transition definition
        slide = self.current_slide
        trans = slide.transition if slide else Transition()
        dur = get_transition_duration(trans)

        if trans.type != "none" and dur > 0:
            self.in_transition = True
            self._active_transition = trans
            self._anim_dur = dur
            self._anim_t0 = time.monotonic()
            self._anim_timer.start()
        else:
            self.in_transition = False
            self._img_prev = None
            self.update()
            self._schedule_auto_advance()

        self.slideChanged.emit(new_idx)

    def finish_transition_now(self) -> None:
        """Instantly complete the active transition animation."""
        self._anim_timer.stop()
        self.in_transition = False
        self._img_prev = None
        self.update()
        self._schedule_auto_advance()

    def _on_anim_frame(self) -> None:
        """Advance transition animation frame."""
        if not self.in_transition:
            self._anim_timer.stop()
            return

        elapsed_ms = (time.monotonic() - self._anim_t0) * 1000.0
        if elapsed_ms >= self._anim_dur:
            self.finish_transition_now()
        else:
            self.update()

    def _schedule_auto_advance(self) -> None:
        """Schedule automatic slide transition if configured."""
        slide = self.current_slide
        if slide and slide.transition and slide.transition.after is not None:
            if slide.transition.after > 0:
                self._auto_timer.start(int(slide.transition.after * 1000.0))

    def _on_auto_advance(self) -> None:
        """Triggered when auto advance timer expires."""
        if self.is_active and not self.is_ended and not self.in_transition:
            self.next_slide()

    def toggle_blank(self, color: str) -> None:
        """Toggle blank screen (e.g. '#000000' or '#FFFFFF')."""
        if self.blank_color == color:
            self.blank_color = None
        else:
            self.blank_color = color
        self.update()

    def end_show(self) -> None:
        """Close slide show view and exit presentation mode."""
        if not self.is_active:
            return
        self._anim_timer.stop()
        self._auto_timer.stop()
        self._idle_timer.stop()
        self.is_active = False
        self.showEnded.emit()
        self.close()

    # --------------------------------------------------------------------------
    # Mouse & Keyboard Event Handlers
    # --------------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        text = event.text()

        # Direct number navigation
        if text.isdigit():
            self.goto_buf += text
            self.update()
            event.accept()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.goto_buf:
                target_slide_1based = int(self.goto_buf)
                self.goto_buf = ""
                # Convert 1-based slide number to 0-based index
                self.goto_slide(target_slide_1based - 1)
                event.accept()
                return

        if self.goto_buf and key not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.goto_buf = ""
            self.update()

        # Navigation shortcuts
        if key in (
            Qt.Key.Key_Right,
            Qt.Key.Key_Down,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_Space,
            Qt.Key.Key_N,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            event.accept()
            self.next_slide()
            return

        if key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Up,
            Qt.Key.Key_PageUp,
            Qt.Key.Key_Backspace,
            Qt.Key.Key_P,
        ):
            event.accept()
            self.prev_slide()
            return

        if key == Qt.Key.Key_Home:
            event.accept()
            self.first_slide()
            return

        if key == Qt.Key.Key_End:
            event.accept()
            self.last_slide()
            return

        if key in (Qt.Key.Key_B, Qt.Key.Key_Period):
            event.accept()
            self.toggle_blank("#000000")
            return

        if key in (Qt.Key.Key_W, Qt.Key.Key_Comma):
            event.accept()
            self.toggle_blank("#FFFFFF")
            return

        if key == Qt.Key.Key_Escape:
            event.accept()
            self.end_show()
            return

        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._reset_cursor_idle()
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_down = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._mouse_down and event.button() == Qt.MouseButton.LeftButton:
            self._mouse_down = False
            event.accept()
            self.next_slide()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._reset_cursor_idle()
        delta = event.angleDelta().y()
        if delta < 0:
            self.next_slide()
        elif delta > 0:
            self.prev_slide()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._reset_cursor_idle()
        super().mouseMoveEvent(event)

    def _reset_cursor_idle(self) -> None:
        if not self._cursor_visible:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self._cursor_visible = True
            self.update()
        self._idle_timer.start()

    def _on_cursor_idle(self) -> None:
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._cursor_visible = False
        self.update()

    # --------------------------------------------------------------------------
    # Right-Click Context Menu
    # --------------------------------------------------------------------------

    def create_context_menu(self) -> QMenu:
        """Construct the standard PowerPoint slide show context menu."""
        menu = QMenu(self)

        act_next = menu.addAction(safe_tr("下一页 (&N)"))
        act_next.triggered.connect(self.next_slide)

        act_prev = menu.addAction(safe_tr("上一页 (&P)"))
        act_prev.triggered.connect(self.prev_slide)

        menu.addSeparator()

        # Go to slide submenu
        menu_goto = menu.addMenu(safe_tr("定位到幻灯片 (&G)"))
        for idx in self.order:
            if idx < len(self.presentation.slides):
                s = self.presentation.slides[idx]
                title = f"{idx + 1}. {safe_tr('幻灯片')} {idx + 1}"
                if s.shapes and s.shapes[0].text and not s.shapes[0].text.is_empty():
                    first_line = s.shapes[0].text.plain_text.splitlines()[0][:30]
                    title = f"{idx + 1}. {first_line}"
                act_s = menu_goto.addAction(title)
                act_s.triggered.connect(lambda checked=False, target=idx: self.goto_slide(target))

        # Screen submenu
        menu_screen = menu.addMenu(safe_tr("屏幕 (&S)"))
        act_black = menu_screen.addAction(safe_tr("黑屏 (&B)"))
        act_black.triggered.connect(lambda: self.toggle_blank("#000000"))

        act_white = menu_screen.addAction(safe_tr("白屏 (&W)"))
        act_white.triggered.connect(lambda: self.toggle_blank("#FFFFFF"))

        menu.addSeparator()

        act_end = menu.addAction(safe_tr("结束放映 (&E)"))
        act_end.triggered.connect(self.end_show)

        return menu

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.create_context_menu()
        menu.exec_(event.globalPos())
        event.accept()

    # --------------------------------------------------------------------------
    # Painting & Double-Buffered Blit
    # --------------------------------------------------------------------------

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

            vw, vh = float(self.width()), float(self.height())
            pw = max(100.0, float(self.presentation.w))
            ph = max(100.0, float(self.presentation.h))

            # 1. Fill entire window background with black letterbox
            painter.fillRect(QRectF(0, 0, vw, vh), QColor("#000000"))

            # 2. Aspect-ratio letterbox calculation
            scale = min(vw / pw, vh / ph)
            sw, sh = pw * scale, ph * scale
            ox = (vw - sw) / 2.0
            oy = (vh - sh) / 2.0
            stage_rect = QRectF(ox, oy, sw, sh)

            # 3. Check special display states
            if self.is_ended:
                painter.fillRect(stage_rect, QColor("#111111"))
                painter.setPen(QColor("#FFFFFF"))
                font = QFont("Arial", max(12, int(20 * scale)))
                painter.setFont(font)
                painter.drawText(
                    stage_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    safe_tr("放映结束，单击鼠标退出。"),
                )
                return

            if self.blank_color is not None:
                painter.fillRect(stage_rect, QColor(self.blank_color))
                return

            # 4. Render transition frame or current slide
            if self.in_transition and self._img_prev and self._img_curr:
                elapsed_ms = (time.monotonic() - self._anim_t0) * 1000.0
                progress = min(1.0, elapsed_ms / float(self._anim_dur))

                # Render transition onto an offscreen buffer at stage size
                frame_img = QImage(int(sw), int(sh), QImage.Format.Format_ARGB32_Premultiplied)
                frame_img.fill(QColor("#000000"))
                p_trans = QPainter(frame_img)
                try:
                    p_trans.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    p_trans.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    render_transition_frame(
                        p_trans,
                        self._img_prev,
                        self._img_curr,
                        self._active_transition,
                        progress,
                        int(sw),
                        int(sh),
                    )
                finally:
                    p_trans.end()

                painter.drawImage(stage_rect, frame_img)
            elif self._img_curr:
                painter.drawImage(stage_rect, self._img_curr)

            # 5. On-screen Goto Overlay ("定位到幻灯片: 2")
            if self.goto_buf:
                overlay_text = f"{safe_tr('定位到幻灯片:')} {self.goto_buf}"
                box_w = max(200.0, 150.0 * scale)
                box_h = max(40.0, 36.0 * scale)
                overlay_rect = QRectF((vw - box_w) / 2.0, vh - box_h - 40.0, box_w, box_h)
                painter.fillRect(overlay_rect, QColor(0, 0, 0, 180))
                painter.setPen(QPen(QColor("#FFFFFF"), 1.0))
                painter.drawRect(overlay_rect)
                font = QFont("Arial", max(10, int(14 * scale)))
                painter.setFont(font)
                painter.drawText(overlay_rect, Qt.AlignmentFlag.AlignCenter, overlay_text)

            # 6. Floating Navigation Popbar at bottom-left
            if self._cursor_visible and not self.is_ended:
                self._draw_popbar(painter, ox, oy + sh - 40.0 * scale, scale)

        finally:
            painter.end()

    def _draw_popbar(self, painter: QPainter, x: float, y: float, scale: float) -> None:
        """Draw minimalist floating on-screen buttons (Prev / Menu / Next) at bottom-left."""
        w = 120.0 * scale
        h = 30.0 * scale
        r = QRectF(x + 10.0, y - h - 10.0, w, h)
        painter.fillRect(r, QColor(40, 40, 40, 160))
        painter.setPen(QPen(QColor(180, 180, 180, 200), 1.0))
        painter.drawRoundedRect(r, 4.0, 4.0)

        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Arial", max(8, int(11 * scale)))
        painter.setFont(font)

        # Draw symbols: <  ≡  >
        b_w = w / 3.0
        painter.drawText(QRectF(r.left(), r.top(), b_w, h), Qt.AlignmentFlag.AlignCenter, "◄")
        painter.drawText(QRectF(r.left() + b_w, r.top(), b_w, h), Qt.AlignmentFlag.AlignCenter, "≡")
        painter.drawText(QRectF(r.left() + b_w * 2.0, r.top(), b_w, h), Qt.AlignmentFlag.AlignCenter, "►")

    def retranslate_ui(self) -> None:
        """Update window title and UI strings."""
        self.setWindowTitle(safe_tr("幻灯片放映"))
        self.update()
