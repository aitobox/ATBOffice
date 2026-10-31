"""WordArt (LettersArt) gallery, 30 classic styles, and curved bezier text deformations."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text with fallback to Chinese native text for ATBOffice."""
    app = QApplication.instance()
    if app:
        translated = app.translate("WordArtGallery", text)
        if translated and translated != text:
            return translated
    return text


class WarpMode(StrEnum):
    """10 classic WordArt warp modes."""

    PLAIN = "textPlain"
    ARCH_UP = "textArchUp"
    ARCH_DOWN = "textArchDown"
    CIRCLE = "textCircle"
    WAVE = "textWave1"
    SLANT_UP = "textSlantUp"
    SLANT_DOWN = "textSlantDown"
    TRIANGLE = "textTriangle"
    CHEVRON = "textChevron"
    CAN_UP = "textCanUp"


@dataclass
class WordArtStyle:
    """Definition for a classic 2003 WordArt preset style."""

    id: int
    name: str
    fill_type: str = "solid"  # "solid" | "gradient"
    fill_colors: list[str] = field(default_factory=lambda: ["#000000"])
    gradient_angle: float = 90.0  # 0.0 (horizontal) or 90.0 (vertical)
    line_color: str | None = None
    line_width: float = 1.0
    shadow: bool = False
    shadow_color: str = "#000000"
    shadow_alpha: float = 0.35
    shadow_dx: float = 3.0
    shadow_dy: float = 3.0
    shadow_blur: float = 0.0
    warp: str = "textPlain"
    bold: bool = True
    italic: bool = False
    font_family: str = "Arial Black"


def _build_30_styles() -> list[WordArtStyle]:
    """Build the exact 30 WordArt styles defined in Office 2003 / VibeOffice."""
    # (fill_type, fill_colors, angle, line_col, line_w, shadow_tuple, warp, font)
    # shadow_tuple: (color, alpha, dx, dy, blur) or None
    s0 = ("#000000", 0.35, 3.0, 3.0, 0.0)
    s1 = ("#000000", 0.60, 4.0, 4.0, 2.0)

    raw_defs = [
        # Row 1 (0..5)
        ("solid", ["#000000"], 90.0, None, 1.0, None, "textPlain", "Arial Black"),
        ("solid", ["#FFFFFF"], 90.0, "#000000", 1.0, None, "textPlain", "Impact"),
        ("gradient", ["#3366FF", "#99CCFF"], 90.0, None, 1.0, None, "textPlain", "Arial"),
        ("solid", ["#C0C0C0"], 90.0, "#404040", 1.0, s0, "textPlain", "Times New Roman"),
        ("gradient", ["#FF6600", "#FFCC00"], 90.0, "#993300", 1.0, None, "textArchUp", "Georgia"),
        ("solid", ["#3366CC"], 90.0, None, 1.0, s0, "textWave1", "Trebuchet MS"),
        # Row 2 (6..11)
        (
            "gradient",
            ["#FFFFFF", "#808080"],
            90.0,
            "#000000",
            1.0,
            s0,
            "textPlain",
            "Arial Black",
        ),
        ("solid", ["#CC0000"], 90.0, "#660000", 1.0, None, "textSlantUp", "Impact"),
        ("gradient", ["#00CC99", "#006666"], 90.0, None, 1.0, s0, "textPlain", "Arial"),
        ("solid", ["#FFFF00"], 90.0, "#FF6600", 1.5, s0, "textPlain", "Times New Roman"),
        ("gradient", ["#CC99FF", "#660099"], 90.0, None, 1.0, None, "textArchDown", "Georgia"),
        ("solid", ["#006600"], 90.0, "#003300", 1.0, None, "textTriangle", "Trebuchet MS"),
        # Row 3 (12..17)
        (
            "gradient",
            ["#FFCC00", "#CC6600"],
            0.0,
            "#663300",
            1.0,
            s0,
            "textPlain",
            "Arial Black",
        ),
        ("solid", ["#000080"], 90.0, None, 1.0, s0, "textChevron", "Impact"),
        ("gradient", ["#E6E6E6", "#333333"], 90.0, "#000000", 1.0, None, "textPlain", "Arial"),
        ("solid", ["#FF99CC"], 90.0, "#CC0066", 1.0, s0, "textWave1", "Times New Roman"),
        ("gradient", ["#66CCFF", "#003399"], 0.0, None, 1.0, s0, "textCanUp", "Georgia"),
        ("solid", ["#996633"], 90.0, "#663300", 1.0, None, "textSlantDown", "Trebuchet MS"),
        # Row 4 (18..23)
        ("gradient", ["#FFFF99", "#FF9900"], 90.0, "#996600", 1.0, s0, "textArchUp", "Arial Black"),
        ("solid", ["#00CCFF"], 90.0, "#006699", 1.0, None, "textPlain", "Impact"),
        ("gradient", ["#FF0000", "#660000"], 90.0, None, 1.0, s0, "textPlain", "Arial"),
        ("solid", ["#808080"], 90.0, None, 1.0, s1, "textPlain", "Times New Roman"),
        ("gradient", ["#99FF99", "#009900"], 90.0, "#006600", 1.0, None, "textCircle", "Georgia"),
        ("solid", ["#FF6600"], 90.0, None, 1.0, s0, "textTriangle", "Trebuchet MS"),
        # Row 5 (24..29)
        ("gradient", ["#000000", "#808080"], 90.0, None, 1.0, s0, "textPlain", "Arial Black"),
        ("solid", ["#FFFFFF"], 90.0, "#3366CC", 1.5, s0, "textArchUp", "Impact"),
        ("gradient", ["#CC66FF", "#3399FF"], 0.0, None, 1.0, None, "textWave1", "Arial"),
        ("solid", ["#003366"], 90.0, "#99CCFF", 1.0, s0, "textSlantUp", "Times New Roman"),
        ("gradient", ["#FFCCCC", "#FF3366"], 90.0, "#990033", 1.0, None, "textChevron", "Georgia"),
        ("solid", ["#669900"], 90.0, None, 1.0, s0, "textCanUp", "Trebuchet MS"),
    ]

    styles: list[WordArtStyle] = []
    for i, (ft, fc, ang, lc, lw, shd, warp, font) in enumerate(raw_defs):
        s = WordArtStyle(
            id=i,
            name=f"WordArt Style {i + 1}",
            fill_type=ft,
            fill_colors=fc,
            gradient_angle=ang,
            line_color=lc,
            line_width=lw,
            shadow=shd is not None,
            shadow_color=shd[0] if shd else "#000000",
            shadow_alpha=shd[1] if shd else 0.35,
            shadow_dx=shd[2] if shd else 3.0,
            shadow_dy=shd[3] if shd else 3.0,
            shadow_blur=shd[4] if shd else 0.0,
            warp=warp,
            bold=(i % 3 != 1),
            italic=False,
            font_family=font,
        )
        styles.append(s)
    return styles


WA_STYLES: list[WordArtStyle] = _build_30_styles()


def warp_points(
    warp: str, w: float, h: float, fs: float, num_points: int = 64
) -> list[tuple[float, float]]:
    """Compute parametric baseline points (x, y) along the deformation curve."""
    pts: list[tuple[float, float]] = []
    n = max(2, num_points)
    m = fs * 0.15
    w_eff = max(1.0, w)
    h_eff = max(1.0, h)

    for i in range(n + 1):
        t = i / float(n)
        if warp == WarpMode.ARCH_UP:
            a = math.pi - t * math.pi
            rx = max(1.0, w_eff / 2.0 - m)
            ry = max(1.0, h_eff - fs - m)
            x = w_eff / 2.0 + math.cos(a) * rx
            y = h_eff - m - math.sin(a) * ry
        elif warp == WarpMode.ARCH_DOWN:
            a = math.pi + t * math.pi
            rx = max(1.0, w_eff / 2.0 - m)
            ry = max(1.0, h_eff - fs - m * 2.0)
            x = w_eff / 2.0 + math.cos(a) * rx
            y = fs + m - math.sin(a) * ry
        elif warp == WarpMode.CIRCLE:
            a = math.pi + t * math.pi * 2.0 * 0.98
            rx = max(1.0, w_eff / 2.0 - fs)
            ry = max(1.0, h_eff / 2.0 - fs)
            x = w_eff / 2.0 + math.cos(a) * rx
            y = h_eff / 2.0 + math.sin(a) * ry
        elif warp == WarpMode.WAVE:
            x = m + t * (w_eff - 2.0 * m)
            amp = max(1.0, h_eff / 2.0 - fs * 0.8)
            y = h_eff / 2.0 + fs / 3.0 + math.sin(t * math.pi * 2.0) * amp
        elif warp == WarpMode.SLANT_UP:
            x = m + t * (w_eff - 2.0 * m)
            y = h_eff - m - t * max(1.0, h_eff - fs - m)
        elif warp == WarpMode.SLANT_DOWN:
            x = m + t * (w_eff - 2.0 * m)
            y = fs + t * max(1.0, h_eff - fs - m)
        elif warp == WarpMode.TRIANGLE:
            x = m + t * (w_eff - 2.0 * m)
            span = max(1.0, h_eff - fs - m)
            if t < 0.5:
                y = h_eff - m - t * 2.0 * span
            else:
                y = fs + (t - 0.5) * 2.0 * span
        elif warp == WarpMode.CHEVRON:
            x = m + t * (w_eff - 2.0 * m)
            if t < 0.5:
                y = h_eff * 0.75 - t * 2.0 * h_eff * 0.35
            else:
                y = h_eff * 0.4 + (t - 0.5) * 2.0 * h_eff * 0.35
        elif warp == WarpMode.CAN_UP:
            x = m + t * (w_eff - 2.0 * m)
            y = h_eff * 0.85 - math.sin(t * math.pi) * h_eff * 0.25
        else:  # textPlain
            x = t * w_eff
            y = h_eff / 2.0 + fs * 0.35
        pts.append((x, y))
    return pts


def create_wordart_composite_path(
    text: str, style: WordArtStyle, rect: QRectF
) -> QPainterPath:
    """Generate a combined vector QPainterPath of deformed glyphs for WordArt."""
    composite_path = QPainterPath()
    cleaned = text.strip()
    if not cleaned or rect.width() <= 0 or rect.height() <= 0:
        return composite_path

    w = max(1.0, rect.width())
    h = max(1.0, rect.height())
    warp = style.warp or WarpMode.PLAIN

    # Plain text layout
    if warp == WarpMode.PLAIN or "\n" in cleaned:
        lines = cleaned.split("\n")
        lh = h / max(1, len(lines))
        fs = lh * 0.82
        font = QFont(style.font_family, int(max(6.0, fs)))
        font.setBold(style.bold)
        font.setItalic(style.italic)

        for i, line in enumerate(lines):
            line_path = QPainterPath()
            y_baseline = rect.top() + (i + 1) * lh - lh * 0.2
            # Add line text stretched to fit width
            line_path.addText(QPointF(rect.left(), y_baseline), font, line)
            # Scale horizontally to match target width if needed
            b = line_path.boundingRect()
            if b.width() > 0:
                sx = w / b.width()
                t = QTransform()
                t.translate(rect.left(), 0.0)
                t.scale(sx, 1.0)
                t.translate(-rect.left(), 0.0)
                line_path = t.map(line_path)
            composite_path.addPath(line_path)
        return composite_path

    # Warped single-line curve layout
    chars = list(cleaned)
    n = len(chars)
    if n == 0:
        return composite_path

    fs = min(h * (0.22 if warp == WarpMode.CIRCLE else 0.45), (w / max(n, 1)) * 1.35)
    fs = max(8.0, fs)
    font = QFont(style.font_family, int(fs))
    font.setBold(style.bold)
    font.setItalic(style.italic)

    num_samples = max(64, n * 8)
    pts = warp_points(warp, w, h, fs, num_points=num_samples)

    # Compute cumulative arc length of path
    cum_lens = [0.0]
    total_len = 0.0
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dy = pts[i][1] - pts[i - 1][1]
        dist = math.hypot(dx, dy)
        total_len += dist
        cum_lens.append(total_len)

    if total_len <= 0.0:
        return composite_path

    for i, ch in enumerate(chars):
        # Character progress along arc
        t_target = (i + 0.5) / float(n) * total_len
        # Binary search or scan for corresponding point
        idx = 0
        for k in range(len(cum_lens) - 1):
            if cum_lens[k] <= t_target <= cum_lens[k + 1]:
                idx = k
                break

        p0 = pts[idx]
        p1 = pts[min(idx + 1, len(pts) - 1)]
        seg_len = max(0.0001, cum_lens[min(idx + 1, len(cum_lens) - 1)] - cum_lens[idx])
        sub_t = (t_target - cum_lens[idx]) / seg_len
        cur_x = rect.left() + p0[0] + sub_t * (p1[0] - p0[0])
        cur_y = rect.top() + p0[1] + sub_t * (p1[1] - p0[1])

        # Angle of tangent
        tangent_dx = p1[0] - p0[0]
        tangent_dy = p1[1] - p0[1]
        angle_rad = math.atan2(tangent_dy, tangent_dx)
        angle_deg = math.degrees(angle_rad)

        # Create single character path centered at origin
        char_path = QPainterPath()
        char_path.addText(QPointF(0.0, 0.0), font, ch)
        cb = char_path.boundingRect()

        # Transform: center char, rotate along tangent, translate to curve point
        xf = QTransform()
        xf.translate(cur_x, cur_y)
        xf.rotate(angle_deg)
        xf.translate(-cb.center().x(), -cb.center().y())

        deformed_char = xf.map(char_path)
        composite_path.addPath(deformed_char)

    return composite_path


def render_wordart(
    painter: QPainter, text: str, style: WordArtStyle, rect: QRectF
) -> None:
    """Render WordArt onto a QPainter surface with fills, outlines, and shadows."""
    path = create_wordart_composite_path(text, style, rect)
    if path.isEmpty():
        return

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # 1. Shadow
    if style.shadow:
        painter.save()
        painter.translate(style.shadow_dx, style.shadow_dy)
        sc = QColor(style.shadow_color)
        sc.setAlphaF(style.shadow_alpha)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(sc))
        painter.drawPath(path)
        painter.restore()

    # 2. Fill brush
    if style.fill_type == "gradient" and len(style.fill_colors) >= 2:
        c1 = QColor(style.fill_colors[0])
        c2 = QColor(style.fill_colors[1])
        b_rect = path.boundingRect()
        if style.gradient_angle == 0.0:  # Horizontal
            grad = QLinearGradient(b_rect.left(), 0.0, b_rect.right(), 0.0)
        else:  # Vertical (90 deg)
            grad = QLinearGradient(0.0, b_rect.top(), 0.0, b_rect.bottom())
        grad.setColorAt(0.0, c1)
        grad.setColorAt(1.0, c2)
        fill_brush = QBrush(grad)
    else:
        fill_brush = QBrush(QColor(style.fill_colors[0]))

    # 3. Outline Pen
    if style.line_color:
        pen = QPen(
            QColor(style.line_color),
            max(0.5, style.line_width),
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    else:
        pen = QPen(Qt.PenStyle.NoPen)

    painter.setBrush(fill_brush)
    painter.setPen(pen)
    painter.drawPath(path)

    painter.restore()


class WordArtThumbnailWidget(QWidget):
    """Selectable thumbnail preview widget for a WordArt style."""

    clicked = Signal(int)
    double_clicked = Signal(int)

    def __init__(
        self, style: WordArtStyle, is_selected: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.style = style
        self.is_selected = is_selected
        self.setFixedSize(70, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(safe_tr(f"艺术字样式 {style.id + 1}"))

    def sizeHint(self) -> QSize:
        return QSize(70, 48)

    def set_selected(self, selected: bool) -> None:
        if self.is_selected != selected:
            self.is_selected = selected
            self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(1, 1, -1, -1)

        # Background & selection state
        if self.is_selected:
            painter.setPen(QPen(QColor(49, 106, 197), 2.0))
            painter.setBrush(QBrush(QColor(221, 235, 247)))
        else:
            painter.setPen(QPen(QColor(180, 180, 180), 1.0))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawRoundedRect(r, 2.0, 2.0)

        # Render WordArt preview
        preview_rect = QRectF(4.0, 4.0, self.width() - 8.0, self.height() - 8.0)
        render_wordart(painter, "LettersArt", self.style, preview_rect)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.style.id)
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.style.id)
            super().mouseDoubleClickEvent(event)


class WordArtGalleryDialog(QDialog):
    """WordArt Gallery dialog presenting 30 classic styles in a 5x6 matrix."""

    def __init__(self, current_style_id: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selected_style_index = max(0, min(29, current_style_id))
        self.thumbnail_widgets: list[WordArtThumbnailWidget] = []
        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        self.setFixedSize(500, 360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.label_prompt = QLabel(self)
        layout.addWidget(self.label_prompt)

        # Grid of 30 styles (5 rows x 6 columns)
        grid_frame = QFrame(self)
        grid_frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setContentsMargins(6, 6, 6, 6)
        grid_layout.setSpacing(4)

        for i, style in enumerate(WA_STYLES):
            thumb = WordArtThumbnailWidget(style, is_selected=(i == self.selected_style_index))
            thumb.clicked.connect(self.set_selected_style_index)
            thumb.double_clicked.connect(self._on_thumbnail_double_click)
            self.thumbnail_widgets.append(thumb)
            row = i // 6
            col = i % 6
            grid_layout.addWidget(thumb, row, col)

        layout.addWidget(grid_frame)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("艺术字样式库"))
        self.label_prompt.setText(safe_tr("请选择一种艺术字样式(&S):"))
        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("取消"))

    def set_selected_style_index(self, index: int) -> None:
        if 0 <= index < len(self.thumbnail_widgets):
            self.selected_style_index = index
            for i, w in enumerate(self.thumbnail_widgets):
                w.set_selected(i == index)

    @property
    def selected_style(self) -> WordArtStyle:
        return WA_STYLES[self.selected_style_index]

    def _on_thumbnail_double_click(self, index: int) -> None:
        self.set_selected_style_index(index)
        self.accept()

    def keyPressEvent(self, event: Any) -> None:
        key = event.key()
        cur = self.selected_style_index
        row = cur // 6
        col = cur % 6

        if key == Qt.Key.Key_Left and col > 0:
            self.set_selected_style_index(cur - 1)
        elif key == Qt.Key.Key_Right and col < 5:
            self.set_selected_style_index(cur + 1)
        elif key == Qt.Key.Key_Up and row > 0:
            self.set_selected_style_index(cur - 6)
        elif key == Qt.Key.Key_Down and row < 4:
            self.set_selected_style_index(cur + 6)
        else:
            super().keyPressEvent(event)


class WordArtTextDialog(QDialog):
    """Dialog for editing WordArt text, font family, font size, bold, and italic."""

    def __init__(
        self,
        initial_text: str = "Your Text Here",
        initial_font: str = "Arial Black",
        initial_size: int = 36,
        initial_bold: bool = True,
        initial_italic: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._initial_text = initial_text or "Your Text Here"
        self._initial_font = initial_font or "Arial Black"
        self._initial_size = initial_size or 36
        self._initial_bold = initial_bold
        self._initial_italic = initial_italic
        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        self.setFixedSize(460, 280)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Top controls row: Font, Size, Bold, Italic
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.lbl_font = QLabel(self)
        self.font_combo = QComboBox(self)
        fonts = [
            "Arial Black",
            "Impact",
            "Arial",
            "Times New Roman",
            "Georgia",
            "Trebuchet MS",
            "SimHei",
            "Microsoft YaHei",
            "Courier New",
            "Comic Sans MS",
        ]
        # Append available system font families
        sys_fonts = QFontDatabase.families()
        for f in sys_fonts:
            if f not in fonts:
                fonts.append(f)
        self.font_combo.addItems(fonts[:30])
        idx = self.font_combo.findText(self._initial_font)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)

        top_row.addWidget(self.lbl_font)
        top_row.addWidget(self.font_combo, 2)

        self.lbl_size = QLabel(self)
        self.size_combo = QComboBox(self)
        sizes = [
            "12", "14", "16", "18", "20", "24", "28", "32", "36",
            "40", "44", "48", "54", "60", "66", "72", "80", "96",
        ]
        self.size_combo.addItems(sizes)
        s_idx = self.size_combo.findText(str(self._initial_size))
        if s_idx >= 0:
            self.size_combo.setCurrentIndex(s_idx)
        else:
            self.size_combo.setCurrentText(str(self._initial_size))

        top_row.addWidget(self.lbl_size)
        top_row.addWidget(self.size_combo, 1)

        self.bold_btn = QPushButton("B", self)
        self.bold_btn.setCheckable(True)
        self.bold_btn.setChecked(self._initial_bold)
        self.bold_btn.setFixedWidth(28)
        font_b = self.bold_btn.font()
        font_b.setBold(True)
        self.bold_btn.setFont(font_b)
        top_row.addWidget(self.bold_btn)

        self.italic_btn = QPushButton("I", self)
        self.italic_btn.setCheckable(True)
        self.italic_btn.setChecked(self._initial_italic)
        self.italic_btn.setFixedWidth(28)
        font_i = self.italic_btn.font()
        font_i.setItalic(True)
        self.italic_btn.setFont(font_i)
        top_row.addWidget(self.italic_btn)

        layout.addLayout(top_row)

        # Text input area
        self.lbl_text = QLabel(self)
        layout.addWidget(self.lbl_text)

        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setPlainText(self._initial_text)
        layout.addWidget(self.text_edit)

        # Dynamic font preview sync
        self.font_combo.currentTextChanged.connect(self._sync_preview_font)
        self.bold_btn.toggled.connect(self._sync_preview_font)
        self.italic_btn.toggled.connect(self._sync_preview_font)
        self._sync_preview_font()

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _sync_preview_font(self) -> None:
        font = QFont(self.font_combo.currentText(), 14)
        font.setBold(self.bold_btn.isChecked())
        font.setItalic(self.italic_btn.isChecked())
        self.text_edit.setFont(font)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("编辑艺术字文字"))
        self.lbl_font.setText(safe_tr("字体(&F):"))
        self.lbl_size.setText(safe_tr("字号(&S):"))
        self.lbl_text.setText(safe_tr("文字(&T):"))
        self.bold_btn.setToolTip(safe_tr("加粗(&B)"))
        self.italic_btn.setToolTip(safe_tr("倾斜(&I)"))
        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("取消"))

    def get_result(self) -> dict[str, Any]:
        """Return the user-configured text and font specifications."""
        try:
            sz = int(self.size_combo.currentText())
        except ValueError:
            sz = 36

        return {
            "text": self.text_edit.toPlainText().strip() or "WordArt",
            "font": self.font_combo.currentText(),
            "size": sz,
            "bold": self.bold_btn.isChecked(),
            "italic": self.italic_btn.isChecked(),
        }


def prompt_insert_wordart(parent: QWidget | None = None) -> dict[str, Any] | None:
    """Execute complete workflow: pick WordArt style preset, edit text, and return WordArt data."""
    gallery_dlg = WordArtGalleryDialog(parent=parent)
    if gallery_dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    style = gallery_dlg.selected_style

    text_dlg = WordArtTextDialog(
        initial_text=safe_tr("在这里输入文字"),
        initial_font=style.font_family,
        initial_size=36,
        initial_bold=style.bold,
        initial_italic=style.italic,
        parent=parent,
    )
    if text_dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    res = text_dlg.get_result()
    res["style"] = style
    res["style_id"] = style.id

    # If parent window supports inserting drawing object, delegate insertion directly
    if parent:
        _try_insert_into_window(parent, res)

    return res


def _try_insert_into_window(window: QWidget, data: dict[str, Any]) -> None:
    """Inject the generated WordArt object into the active window (Quire, Lectern, or Ledger)."""
    # 1. Lectern (Presentation)
    if hasattr(window, "add_shape") or hasattr(window, "current_slide"):
        from atboffice.modules.presentation.models.shape import Fill, Line, Shadow, Shape

        style: WordArtStyle = data["style"]
        text: str = data["text"]

        fill = Fill.solid(style.fill_colors[0])
        if style.fill_type == "gradient" and len(style.fill_colors) >= 2:
            stops = [{"p": 0.0, "c": style.fill_colors[0]}, {"p": 1.0, "c": style.fill_colors[1]}]
            fill = Fill.gradient(stops, angle=style.gradient_angle)

        line = Line.none()
        if style.line_color:
            line = Line(color=style.line_color, width=style.line_width)

        shadow = None
        if style.shadow:
            shadow = Shadow(
                color=style.shadow_color,
                alpha=style.shadow_alpha,
                dist=math.hypot(style.shadow_dx, style.shadow_dy),
            )

        shape = Shape(
            id=f"wordart_{id(data)}",
            type="shape",
            name=f"WordArt: {text[:10]}",
            geom="custom",
            x=100.0,
            y=100.0,
            w=240.0,
            h=90.0,
            fill=fill,
            line=line,
            shadow=shadow,
        )
        if hasattr(window, "add_shape"):
            window.add_shape(shape)
        elif hasattr(window, "current_slide") and window.current_slide:
            window.current_slide.shapes.append(shape)
            if hasattr(window, "update_view"):
                window.update_view()

    # 2. Quire (Writer)
    elif hasattr(window, "writer_view") and hasattr(window.writer_view, "insert_drawing_object"):
        from atboffice.modules.writer.models.drawing import TextBoxItem

        tb_item = TextBoxItem(
            name=f"WordArt: {data['text'][:10]}",
            width=240.0,
            height=90.0,
        )
        window.writer_view.insert_drawing_object(tb_item)

    # 3. Generic window method fallback
    elif hasattr(window, "insert_wordart_object"):
        window.insert_wordart_object(data)
