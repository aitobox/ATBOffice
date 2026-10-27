"""Lectern dual-screen presenter console (Speaker View).

Full-featured presenter console providing real-time presentation timer,
speaker notes with zooming, next slide preview, slide thumbnail drawer,
ink annotations, and laser pointer synchronized with audience SlideShowView.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.slideshow.transitions import (
    render_slide_to_image,
    safe_tr,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation
    from atboffice.modules.presentation.slideshow.slideshow_view import SlideShowView


@dataclass
class InkPoint:
    """Individual point in an ink stroke."""

    x: float
    y: float


@dataclass
class InkStroke:
    """Freehand ink annotation stroke."""

    points: list[tuple[float, float]] = field(default_factory=list)
    color: str = "#FF0000"
    width: float = 2.0
    alpha: float = 1.0
    is_highlighter: bool = False


class InteractiveSlideCanvas(QWidget):
    """Interactive canvas widget displaying current slide with ink and laser overlays."""

    slideAdvanced = Signal()
    strokeAdded = Signal(int, object)  # slide_index, stroke
    strokeErased = Signal(int, int)  # slide_index, stroke_index
    laserMoved = Signal(object)  # laser position tuple

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode: str = "arrow"  # "arrow", "pen", "highlighter", "laser", "eraser"
        self.slide_image: QImage | None = None
        self.slide_w: float = 960.0
        self.slide_h: float = 540.0
        self.slide_index: int = 0
        self.strokes: list[InkStroke] = []
        self.current_stroke: InkStroke | None = None
        self.laser_pos: tuple[float, float] | None = None
        self.blank_color: QColor | None = None
        self.pen_color: str = "#FF0000"
        self.pen_width: float = 3.0
        self._press_pos: QPointF | None = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(240, 135)

    def set_mode(self, mode: str) -> None:
        """Switch drawing / interaction tool mode."""
        self.mode = mode
        if mode != "laser":
            self.laser_pos = None
        if mode == "arrow":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode in ("pen", "highlighter"):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "laser":
            self.setCursor(Qt.CursorShape.BlankCursor)
        elif mode == "eraser":
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def set_slide_data(
        self,
        img: QImage | None,
        w: float,
        h: float,
        slide_index: int,
        strokes: list[InkStroke],
    ) -> None:
        """Update active slide image and annotations."""
        self.slide_image = img
        self.slide_w = max(1.0, w)
        self.slide_h = max(1.0, h)
        self.slide_index = slide_index
        self.strokes = strokes
        self.current_stroke = None
        self.update()

    def _get_stage_geometry(self) -> tuple[float, float, float, float, float]:
        """Compute aspect-ratio preserving display rectangle: ox, oy, sw, sh, scale."""
        vw = float(self.width())
        vh = float(self.height())
        pw = max(1.0, self.slide_w)
        ph = max(1.0, self.slide_h)
        scale = min(vw / pw, vh / ph)
        sw = pw * scale
        sh = ph * scale
        ox = (vw - sw) / 2.0
        oy = (vh - sh) / 2.0
        return ox, oy, sw, sh, scale

    def to_slide_pt(self, pt: QPointF) -> tuple[float, float]:
        """Convert widget coordinate to slide coordinate."""
        ox, oy, sw, sh, scale = self._get_stage_geometry()
        scale_x = sw / max(1.0, self.slide_w)
        scale_y = sh / max(1.0, self.slide_h)
        if scale_x <= 0 or scale_y <= 0:
            return pt.x(), pt.y()
        sx = (pt.x() - ox) / scale_x
        sy = (pt.y() - oy) / scale_y
        return sx, sy

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        sp = self.to_slide_pt(pos)

        if self.mode == "arrow":
            if event.button() == Qt.MouseButton.LeftButton:
                self._press_pos = pos
        elif self.mode in ("pen", "highlighter"):
            if event.button() == Qt.MouseButton.LeftButton:
                color = self.pen_color if self.mode == "pen" else "#FFFF00"
                width = self.pen_width if self.mode == "pen" else 14.0
                alpha = 1.0 if self.mode == "pen" else 0.4
                self.current_stroke = InkStroke(
                    points=[sp],
                    color=color,
                    width=width,
                    alpha=alpha,
                    is_highlighter=(self.mode == "highlighter"),
                )
                self.update()
        elif self.mode == "laser":
            self.laser_pos = sp
            self.laserMoved.emit(self.laser_pos)
            self.update()
        elif self.mode == "eraser":
            if event.button() == Qt.MouseButton.LeftButton:
                self._erase_at(sp)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        sp = self.to_slide_pt(pos)

        if self.mode in ("pen", "highlighter") and self.current_stroke is not None:
            self.current_stroke.points.append(sp)
            self.update()
        elif self.mode == "laser":
            self.laser_pos = sp
            self.laserMoved.emit(self.laser_pos)
            self.update()
        elif self.mode == "eraser":
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._erase_at(sp)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.mode == "arrow":
            if event.button() == Qt.MouseButton.LeftButton and self._press_pos is not None:
                diff = (event.position() - self._press_pos).manhattanLength()
                self._press_pos = None
                if diff < 10:
                    self.slideAdvanced.emit()
        elif self.mode in ("pen", "highlighter") and self.current_stroke is not None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.strokes.append(self.current_stroke)
                self.strokeAdded.emit(self.slide_index, self.current_stroke)
                self.current_stroke = None
                self.update()

        super().mouseReleaseEvent(event)

    def _erase_at(self, pt: tuple[float, float], threshold: float = 30.0) -> None:
        """Hit-test and delete strokes near pt."""
        px, py = pt
        for idx in range(len(self.strokes) - 1, -1, -1):
            stroke = self.strokes[idx]
            hit = False
            for p in stroke.points:
                if math.hypot(p[0] - px, p[1] - py) <= threshold:
                    hit = True
                    break
            if hit:
                self.strokes.pop(idx)
                self.strokeErased.emit(self.slide_index, idx)
                self.update()
                break

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Background
        painter.fillRect(self.rect(), QColor("#1E1E1E"))

        ox, oy, sw, sh, scale = self._get_stage_geometry()
        stage_rect = QRectF(ox, oy, sw, sh)

        # Blank screen
        if self.blank_color is not None:
            painter.fillRect(stage_rect, self.blank_color)
            return

        # Slide snapshot
        if self.slide_image:
            painter.drawImage(stage_rect, self.slide_image)
        else:
            painter.fillRect(stage_rect, QColor("#FFFFFF"))

        # Ink strokes
        scale_x = sw / max(1.0, self.slide_w)
        scale_y = sh / max(1.0, self.slide_h)

        all_strokes = list(self.strokes)
        if self.current_stroke:
            all_strokes.append(self.current_stroke)

        for stroke in all_strokes:
            pts = stroke.points
            if len(pts) < 1:
                continue
            qcolor = QColor(stroke.color)
            qcolor.setAlphaF(min(1.0, max(0.0, stroke.alpha)))
            pen = QPen(qcolor, max(1.0, stroke.width * scale))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            if len(pts) == 1:
                sx = ox + pts[0][0] * scale_x
                sy = oy + pts[0][1] * scale_y
                painter.drawPoint(QPointF(sx, sy))
            else:
                path = QPainterPath()
                path.moveTo(ox + pts[0][0] * scale_x, oy + pts[0][1] * scale_y)
                for p in pts[1:]:
                    path.lineTo(ox + p[0] * scale_x, oy + p[1] * scale_y)
                painter.drawPath(path)

        # Laser pointer
        if self.laser_pos is not None:
            lx, ly = self.laser_pos
            sx = ox + lx * scale_x
            sy = oy + ly * scale_y
            halo_rad = 16.0 * scale
            gradient = QRadialGradient(sx, sy, halo_rad)
            gradient.setColorAt(0.0, QColor(255, 30, 30, 220))
            gradient.setColorAt(0.4, QColor(255, 50, 50, 140))
            gradient.setColorAt(1.0, QColor(255, 50, 50, 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(sx, sy), halo_rad, halo_rad)

            core_rad = 4.0 * scale
            painter.setBrush(QColor(255, 255, 255, 240))
            painter.drawEllipse(QPointF(sx, sy), core_rad, core_rad)


class PresenterConsole(QMainWindow):
    """PowerPoint 2003 dual-screen speaker console."""

    def __init__(
        self,
        presentation: Presentation,
        start_slide_index: int = 0,
        audience_view: SlideShowView | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.current_slide_index: int = max(0, min(start_slide_index, len(presentation.slides) - 1)) if presentation.slides else 0
        self.audience_view: SlideShowView | None = audience_view
        self.elapsed_seconds: int = 0
        self.is_timer_running: bool = True
        self.notes_font_size: int = 18
        self.ink_strokes: dict[int, list[InkStroke]] = {}

        self.setWindowTitle(safe_tr("演讲者控制台 - Lectern"))
        self.resize(1100, 720)
        self.setStyleSheet(
            """
            QMainWindow { background-color: #212121; color: #FFFFFF; }
            QLabel { color: #DDDDDD; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #444444; border-color: #777777; }
            QPushButton:pressed { background-color: #222222; }
            QTextEdit {
                background-color: #2D2D2D;
                color: #F0F0F0;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 8px;
            }
            QSplitter::handle { background-color: #383838; }
            """
        )

        self._init_ui()
        self._init_timers()
        self._bind_audience_view()
        self._load_current_slide()
        self._load_next_slide_preview()
        self.show()

    def _init_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # 1. Top Header Bar
        header = QHBoxLayout()
        header.setSpacing(10)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #00E676; min-width: 90px;")
        header.addWidget(self.timer_label)

        self.btn_pause_timer = QPushButton("❚❚")
        self.btn_pause_timer.setToolTip(safe_tr("暂停计时"))
        self.btn_pause_timer.setFixedWidth(40)
        self.btn_pause_timer.clicked.connect(self.toggle_timer)
        header.addWidget(self.btn_pause_timer)

        self.btn_reset_timer = QPushButton("↺")
        self.btn_reset_timer.setToolTip(safe_tr("重置计时"))
        self.btn_reset_timer.setFixedWidth(40)
        self.btn_reset_timer.clicked.connect(self.reset_timer)
        header.addWidget(self.btn_reset_timer)

        header.addSpacing(20)

        lbl_clock_prefix = QLabel(safe_tr("当前时间:"))
        lbl_clock_prefix.setStyleSheet("color: #888888; font-size: 13px;")
        header.addWidget(lbl_clock_prefix)

        self.clock_label = QLabel(time.strftime("%H:%M:%S"))
        self.clock_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #CCCCCC;")
        header.addWidget(self.clock_label)

        header.addStretch()

        self.btn_swap_screens = QPushButton(safe_tr("交换显示器"))
        self.btn_swap_screens.clicked.connect(self._swap_screens)
        header.addWidget(self.btn_swap_screens)

        self.btn_end_show = QPushButton(safe_tr("结束放映"))
        self.btn_end_show.setStyleSheet("background-color: #D32F2F; color: #FFFFFF; font-weight: bold;")
        self.btn_end_show.clicked.connect(self.end_show)
        header.addWidget(self.btn_end_show)

        root_layout.addLayout(header)

        # 2. Main Middle Splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Canvas + Navigation Toolbar
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.canvas = InteractiveSlideCanvas()
        self.canvas.slideAdvanced.connect(self.next_slide)
        self.canvas.strokeAdded.connect(self._on_canvas_stroke_added)
        self.canvas.strokeErased.connect(self._on_canvas_stroke_erased)
        self.canvas.laserMoved.connect(self._on_canvas_laser_moved)
        left_layout.addWidget(self.canvas, stretch=1)

        # Bottom nav bar under canvas
        nav_bar = QHBoxLayout()
        nav_bar.setSpacing(6)

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setToolTip(safe_tr("上一页"))
        self.btn_prev.setFixedWidth(40)
        self.btn_prev.clicked.connect(self.prev_slide)
        nav_bar.addWidget(self.btn_prev)

        self.btn_next = QPushButton("▶")
        self.btn_next.setToolTip(safe_tr("下一页"))
        self.btn_next.setFixedWidth(40)
        self.btn_next.clicked.connect(self.next_slide)
        nav_bar.addWidget(self.btn_next)

        self.slide_counter_label = QLabel(f"1 / {max(1, len(self.presentation.slides))}")
        self.slide_counter_label.setStyleSheet("font-weight: 600; padding: 0 8px;")
        nav_bar.addWidget(self.slide_counter_label)

        nav_bar.addSpacing(10)

        self.btn_arrow = QPushButton("↗")
        self.btn_arrow.setToolTip(safe_tr("普通箭头"))
        self.btn_arrow.setFixedWidth(36)
        self.btn_arrow.clicked.connect(lambda: self.canvas.set_mode("arrow"))
        nav_bar.addWidget(self.btn_arrow)

        self.btn_pen = QPushButton("✎")
        self.btn_pen.setToolTip(safe_tr("画笔"))
        self.btn_pen.setFixedWidth(36)
        self.btn_pen.clicked.connect(lambda: self.canvas.set_mode("pen"))
        nav_bar.addWidget(self.btn_pen)

        self.btn_laser = QPushButton("◉")
        self.btn_laser.setToolTip(safe_tr("激光笔"))
        self.btn_laser.setFixedWidth(36)
        self.btn_laser.clicked.connect(lambda: self.canvas.set_mode("laser"))
        nav_bar.addWidget(self.btn_laser)

        self.btn_eraser = QPushButton("⌫")
        self.btn_eraser.setToolTip(safe_tr("橡皮擦"))
        self.btn_eraser.setFixedWidth(36)
        self.btn_eraser.clicked.connect(lambda: self.canvas.set_mode("eraser"))
        nav_bar.addWidget(self.btn_eraser)

        nav_bar.addSpacing(10)

        self.btn_black = QPushButton(safe_tr("黑屏"))
        self.btn_black.clicked.connect(self.toggle_black)
        nav_bar.addWidget(self.btn_black)

        self.btn_white = QPushButton(safe_tr("白屏"))
        self.btn_white.clicked.connect(self.toggle_white)
        nav_bar.addWidget(self.btn_white)

        nav_bar.addStretch()

        self.btn_drawer = QPushButton(safe_tr("幻灯片导航"))
        self.btn_drawer.clicked.connect(self.toggle_drawer)
        nav_bar.addWidget(self.btn_drawer)

        left_layout.addLayout(nav_bar)
        main_splitter.addWidget(left_widget)

        # Right Column: Next Preview & Notes
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Next slide preview section
        next_box = QFrame()
        next_box.setStyleSheet("background-color: #282828; border-radius: 6px; padding: 6px;")
        next_box_layout = QVBoxLayout(next_box)
        next_box_layout.setContentsMargins(6, 6, 6, 6)

        self.next_preview_title = QLabel(safe_tr("下一张: 幻灯片 2"))
        self.next_preview_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #4FC3F7;")
        next_box_layout.addWidget(self.next_preview_title)

        self.next_preview_label = QLabel()
        self.next_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_preview_label.setMinimumSize(220, 125)
        self.next_preview_label.setStyleSheet("background-color: #000000; border-radius: 4px;")
        next_box_layout.addWidget(self.next_preview_label, stretch=1)
        right_layout.addWidget(next_box, stretch=2)

        # Notes section
        notes_box = QFrame()
        notes_box.setStyleSheet("background-color: #282828; border-radius: 6px; padding: 6px;")
        notes_box_layout = QVBoxLayout(notes_box)
        notes_box_layout.setContentsMargins(6, 6, 6, 6)

        notes_header = QHBoxLayout()
        lbl_notes = QLabel(safe_tr("演讲者备注"))
        lbl_notes.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFF;")
        notes_header.addWidget(lbl_notes)
        notes_header.addStretch()

        self.btn_zoom_in = QPushButton("A+")
        self.btn_zoom_in.setFixedWidth(36)
        self.btn_zoom_in.clicked.connect(self.zoom_in_notes)
        notes_header.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("A-")
        self.btn_zoom_out.setFixedWidth(36)
        self.btn_zoom_out.clicked.connect(self.zoom_out_notes)
        notes_header.addWidget(self.btn_zoom_out)
        notes_box_layout.addLayout(notes_header)

        self.notes_placeholder = QLabel(safe_tr("无演讲者备注"))
        self.notes_placeholder.setStyleSheet("color: #777777; font-style: italic; padding: 4px;")
        self.notes_placeholder.setVisible(False)
        notes_box_layout.addWidget(self.notes_placeholder)

        self.notes_edit = QTextEdit()
        self.notes_edit.setReadOnly(True)
        self._update_notes_font()
        notes_box_layout.addWidget(self.notes_edit, stretch=1)
        right_layout.addWidget(notes_box, stretch=3)

        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)
        root_layout.addWidget(main_splitter, stretch=1)

        # 3. Bottom Slide Drawer Widget
        self.drawer_widget = QWidget()
        drawer_layout = QVBoxLayout(self.drawer_widget)
        drawer_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(120)

        drawer_content = QWidget()
        self.drawer_thumbs_layout = QHBoxLayout(drawer_content)
        self.drawer_thumbs_layout.setContentsMargins(4, 4, 4, 4)
        self.drawer_thumbs_layout.setSpacing(8)

        self._populate_drawer_thumbnails()
        scroll.setWidget(drawer_content)
        drawer_layout.addWidget(scroll)

        self.drawer_widget.setVisible(False)
        root_layout.addWidget(self.drawer_widget)

    def _populate_drawer_thumbnails(self) -> None:
        """Populate thumbnail buttons in bottom drawer."""
        for i, slide in enumerate(self.presentation.slides):
            btn = QPushButton(f"{i + 1}")
            btn.setFixedSize(140, 80)
            btn.setStyleSheet("font-size: 13px; font-weight: bold; background-color: #333333; border: 1px solid #666;")
            btn.clicked.connect(lambda checked=False, target=i: self.select_slide_from_drawer(target))
            self.drawer_thumbs_layout.addWidget(btn)
        self.drawer_thumbs_layout.addStretch()

    def _init_timers(self) -> None:
        self._timer_1s = QTimer(self)
        self._timer_1s.setInterval(1000)
        self._timer_1s.timeout.connect(self._on_timer_tick)
        self._timer_1s.start()

    def _on_timer_tick(self) -> None:
        self.clock_label.setText(time.strftime("%H:%M:%S"))
        if self.is_timer_running:
            self.elapsed_seconds += 1
            self._update_timer_display()

    def _update_timer_display(self) -> None:
        hours = self.elapsed_seconds // 3600
        minutes = (self.elapsed_seconds % 3600) // 60
        seconds = self.elapsed_seconds % 60
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def toggle_timer(self) -> None:
        """Pause or resume elapsed presentation timer."""
        self.is_timer_running = not self.is_timer_running
        if self.is_timer_running:
            self.btn_pause_timer.setText("❚❚")
            self.btn_pause_timer.setToolTip(safe_tr("暂停计时"))
        else:
            self.btn_pause_timer.setText("▶")
            self.btn_pause_timer.setToolTip(safe_tr("继续计时"))

    def reset_timer(self) -> None:
        """Reset elapsed presentation timer to zero."""
        self.elapsed_seconds = 0
        self._update_timer_display()

    def next_slide(self) -> None:
        """Navigate to next slide."""
        if self.current_slide_index < len(self.presentation.slides) - 1:
            self.goto_slide(self.current_slide_index + 1)

    def prev_slide(self) -> None:
        """Navigate to previous slide."""
        if self.current_slide_index > 0:
            self.goto_slide(self.current_slide_index - 1)

    def goto_slide(self, index: int, sync_audience: bool = True) -> None:
        """Navigate directly to slide by index."""
        if not (0 <= index < len(self.presentation.slides)):
            return
        self.current_slide_index = index
        self._load_current_slide()
        self._load_next_slide_preview()

        if sync_audience and self.audience_view is not None:
            if self.audience_view.current_slide_index != index:
                self.audience_view.goto_slide(index)
                if getattr(self.audience_view, "in_transition", False):
                    self.audience_view.finish_transition_now()

    def _load_current_slide(self) -> None:
        if not self.presentation.slides:
            return
        slide = self.presentation.slides[self.current_slide_index]
        img = render_slide_to_image(slide, self.presentation)

        if self.current_slide_index not in self.ink_strokes:
            self.ink_strokes[self.current_slide_index] = []

        self.canvas.set_slide_data(
            img,
            self.presentation.w,
            self.presentation.h,
            self.current_slide_index,
            self.ink_strokes[self.current_slide_index],
        )

        notes = getattr(slide, "notes", "") or ""
        self.notes_edit.setPlainText(notes)
        if not notes.strip():
            self.notes_placeholder.setText(safe_tr("无演讲者备注"))
            self.notes_placeholder.setVisible(True)
        else:
            self.notes_placeholder.setVisible(False)

        self.slide_counter_label.setText(
            f"{self.current_slide_index + 1} / {len(self.presentation.slides)}"
        )

    def _load_next_slide_preview(self) -> None:
        next_idx = self.current_slide_index + 1
        if next_idx < len(self.presentation.slides):
            next_slide = self.presentation.slides[next_idx]
            self.next_preview_title.setText(f"{safe_tr('下一张')}: {safe_tr('幻灯片')} {next_idx + 1}")
            img = render_slide_to_image(next_slide, self.presentation, width=320, height=180)
            self.next_preview_label.setPixmap(QPixmap.fromImage(img))
        else:
            self.next_preview_title.setText(safe_tr("放映结束"))
            pix = QPixmap(320, 180)
            pix.fill(QColor("#000000"))
            self.next_preview_label.setPixmap(pix)

    def zoom_in_notes(self) -> None:
        """Increase speaker notes font size."""
        self.notes_font_size += 2
        self._update_notes_font()

    def zoom_out_notes(self) -> None:
        """Decrease speaker notes font size with lower bound."""
        self.notes_font_size = max(8, self.notes_font_size - 2)
        self._update_notes_font()

    def _update_notes_font(self) -> None:
        font = QFont("Arial", self.notes_font_size)
        self.notes_edit.setFont(font)

    def toggle_drawer(self) -> None:
        """Toggle bottom slide drawer visibility."""
        self.drawer_widget.setVisible(not self.drawer_widget.isVisible())

    def select_slide_from_drawer(self, index: int) -> None:
        """Select slide from drawer and jump to it."""
        self.goto_slide(index)

    def toggle_black(self) -> None:
        """Toggle black screen blanking."""
        target = QColor(0, 0, 0)
        if self.canvas.blank_color == target:
            self.canvas.blank_color = None
        else:
            self.canvas.blank_color = target
        self.canvas.update()
        if self.audience_view is not None:
            self.audience_view.toggle_blank(target)

    def toggle_white(self) -> None:
        """Toggle white screen blanking."""
        target = QColor(255, 255, 255)
        if self.canvas.blank_color == target:
            self.canvas.blank_color = None
        else:
            self.canvas.blank_color = target
        self.canvas.update()
        if self.audience_view is not None:
            self.audience_view.toggle_blank(target)

    def _on_canvas_stroke_added(self, slide_idx: int, stroke: InkStroke) -> None:
        if slide_idx not in self.ink_strokes:
            self.ink_strokes[slide_idx] = []
        if stroke not in self.ink_strokes[slide_idx]:
            self.ink_strokes[slide_idx].append(stroke)
        if self.audience_view is not None:
            if slide_idx not in self.audience_view.ink_strokes:
                self.audience_view.ink_strokes[slide_idx] = []
            if stroke not in self.audience_view.ink_strokes[slide_idx]:
                self.audience_view.ink_strokes[slide_idx].append(stroke)
            self.audience_view.update()

    def _on_canvas_stroke_erased(self, slide_idx: int, stroke_idx: int) -> None:
        if slide_idx in self.ink_strokes and 0 <= stroke_idx < len(self.ink_strokes[slide_idx]):
            self.ink_strokes[slide_idx].pop(stroke_idx)
        if self.audience_view is not None and slide_idx in self.audience_view.ink_strokes:
            if 0 <= stroke_idx < len(self.audience_view.ink_strokes[slide_idx]):
                self.audience_view.ink_strokes[slide_idx].pop(stroke_idx)
            self.audience_view.update()

    def _on_canvas_laser_moved(self, pos: Any) -> None:
        if self.audience_view is not None:
            if isinstance(pos, (tuple, list)):
                self.audience_view.laser_pos = (float(pos[0]), float(pos[1]))
            elif isinstance(pos, QPointF):
                self.audience_view.laser_pos = (pos.x(), pos.y())
            elif pos is None:
                self.audience_view.laser_pos = None
            self.audience_view.update()

    def _bind_audience_view(self) -> None:
        if self.audience_view is not None:
            self.audience_view.slideChanged.connect(self._on_audience_slide_changed)
            self.audience_view.showEnded.connect(self.close)

    def _on_audience_slide_changed(self, new_idx: int) -> None:
        if self.current_slide_index != new_idx:
            self.goto_slide(new_idx, sync_audience=False)

    def _swap_screens(self) -> None:
        """Swap displays between presenter console and audience window."""
        screens = QApplication.screens()
        if len(screens) >= 2 and self.audience_view is not None:
            s0 = screens[0].geometry()
            s1 = screens[1].geometry()
            if self.geometry().intersects(s0):
                self.setGeometry(s1)
                self.audience_view.setGeometry(s0)
            else:
                self.setGeometry(s0)
                self.audience_view.setGeometry(s1)

    def end_show(self, prompt_ink: bool = True, keep_ink: bool = False) -> None:
        """End presentation with optional ink annotation retention."""
        has_ink = any(len(strokes) > 0 for strokes in self.ink_strokes.values())
        if prompt_ink and has_ink:
            res = QMessageBox.question(
                self,
                safe_tr("保留墨迹批注"),
                safe_tr("是否保留墨迹批注？"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            keep_ink = res == QMessageBox.StandardButton.Yes

        if keep_ink:
            for s_idx, strokes in self.ink_strokes.items():
                if 0 <= s_idx < len(self.presentation.slides):
                    slide = self.presentation.slides[s_idx]
                    for stroke in strokes:
                        if stroke.points:
                            poly_pts = [list(pt) for pt in stroke.points]
                            line_style = Line(color=stroke.color, width=stroke.width)
                            ink_shape = Shape(
                                id=f"ink_{s_idx}_{len(slide.shapes)}",
                                type="shape",
                                name="Ink Annotation",
                                geom="freeform",
                                poly=poly_pts,
                                line=line_style,
                                fill=Fill.none(),
                            )
                            slide.shapes.append(ink_shape)

        if self.audience_view is not None:
            self.audience_view.end_show()
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        k = event.key()
        mod = event.modifiers()

        if mod & Qt.KeyboardModifier.ControlModifier:
            if k in (Qt.Key.Key_P,):
                self.canvas.set_mode("pen")
                return
            elif k in (Qt.Key.Key_L,):
                self.canvas.set_mode("laser")
                return
            elif k in (Qt.Key.Key_E,):
                self.canvas.set_mode("eraser")
                return
            elif k in (Qt.Key.Key_A,):
                self.canvas.set_mode("arrow")
                return

        if k in (
            Qt.Key.Key_Space,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_Right,
            Qt.Key.Key_Down,
            Qt.Key.Key_N,
            Qt.Key.Key_Return,
        ):
            self.next_slide()
        elif k in (
            Qt.Key.Key_Backspace,
            Qt.Key.Key_PageUp,
            Qt.Key.Key_Left,
            Qt.Key.Key_Up,
            Qt.Key.Key_P,
        ):
            self.prev_slide()
        elif k in (Qt.Key.Key_B, Qt.Key.Key_Period):
            self.toggle_black()
        elif k in (Qt.Key.Key_W, Qt.Key.Key_Comma):
            self.toggle_white()
        elif k in (Qt.Key.Key_Escape,):
            self.end_show()
        else:
            super().keyPressEvent(event)

    def retranslate_ui(self) -> None:
        """Dynamically re-translate all UI text."""
        self.setWindowTitle(safe_tr("演讲者控制台 - Lectern"))
        self.btn_pause_timer.setToolTip(safe_tr("暂停计时") if self.is_timer_running else safe_tr("继续计时"))
        self.btn_reset_timer.setToolTip(safe_tr("重置计时"))
        self.btn_swap_screens.setText(safe_tr("交换显示器"))
        self.btn_end_show.setText(safe_tr("结束放映"))
        self.notes_placeholder.setText(safe_tr("无演讲者备注"))
        self.btn_black.setText(safe_tr("黑屏"))
        self.btn_white.setText(safe_tr("白屏"))
        self.btn_drawer.setText(safe_tr("幻灯片导航"))
        self._load_next_slide_preview()


PresenterView = PresenterConsole

__all__ = [
    "InkPoint",
    "InkStroke",
    "InteractiveSlideCanvas",
    "PresenterConsole",
    "PresenterView",
]
