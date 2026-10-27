"""58 Slide Transitions catalogue and high-performance QPainter rendering algorithms."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.slide import Slide, Transition
from atboffice.modules.presentation.views.geometry_helper import create_shape_path

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


def safe_tr(text: str) -> str:
    """Translate UI text with fallbacks."""
    app = QApplication.instance()
    if app:
        translated = app.translate("Transitions", text)
        if translated and translated != text:
            return translated
    return text


@dataclass(frozen=True)
class TransitionEffect:
    """Metadata container for a slide transition effect."""

    key: str
    name: str
    cn_name: str
    type: str
    category: str = "subtle"  # "subtle", "moderate", "exciting"
    dir: str | None = None
    thruBlk: bool = False
    spokes: int | None = None
    orient: str | None = None
    dur: int | None = None
    spd: str = "fast"


# ==============================================================================
# Complete 58 Transitions Catalogue (matching PowerPoint 2003 & vibeoffice)
# ==============================================================================

TRANSITION_CATALOGUE: list[TransitionEffect] = [
    TransitionEffect("none", "No Transition", "无切换", "none"),
    # Blinds (2)
    TransitionEffect("blinds_horz", "Blinds Horizontal", "百叶窗 (水平)", "blinds", dir="horz"),
    TransitionEffect("blinds_vert", "Blinds Vertical", "百叶窗 (垂直)", "blinds", dir="vert"),
    # Box / Zoom (2)
    TransitionEffect("box_in", "Box In", "盒状收缩", "zoom", dir="in"),
    TransitionEffect("box_out", "Box Out", "盒状展开", "zoom", dir="out"),
    # Checkerboard (2)
    TransitionEffect("checker_horz", "Checkerboard Across", "棋盘 (横向)", "checker", dir="horz"),
    TransitionEffect("checker_vert", "Checkerboard Down", "棋盘 (纵向)", "checker", dir="vert"),
    # Comb (2)
    TransitionEffect("comb_horz", "Comb Horizontal", "梳理 (水平)", "comb", dir="horz"),
    TransitionEffect("comb_vert", "Comb Vertical", "梳理 (垂直)", "comb", dir="vert"),
    # Cover (8)
    TransitionEffect("cover_d", "Cover Down", "向下覆盖", "cover", dir="d"),
    TransitionEffect("cover_l", "Cover Left", "向左覆盖", "cover", dir="l"),
    TransitionEffect("cover_r", "Cover Right", "向右覆盖", "cover", dir="r"),
    TransitionEffect("cover_u", "Cover Up", "向上覆盖", "cover", dir="u"),
    TransitionEffect("cover_ld", "Cover Left-Down", "向左下覆盖", "cover", dir="ld"),
    TransitionEffect("cover_lu", "Cover Left-Up", "向左上覆盖", "cover", dir="lu"),
    TransitionEffect("cover_rd", "Cover Right-Down", "向右下覆盖", "cover", dir="rd"),
    TransitionEffect("cover_ru", "Cover Right-Up", "向右上覆盖", "cover", dir="ru"),
    # Cut (2)
    TransitionEffect("cut", "Cut", "快速切入", "cut"),
    TransitionEffect("cut_blk", "Cut Through Black", "黑屏切入", "cut", thruBlk=True),
    # Dissolve (1)
    TransitionEffect("dissolve", "Dissolve", "溶解", "dissolve"),
    # Fade (2)
    TransitionEffect("fade", "Fade Smoothly", "平滑淡出", "fade"),
    TransitionEffect("fade_blk", "Fade Through Black", "黑屏淡出", "fade", thruBlk=True),
    # Newsflash (1)
    TransitionEffect("newsflash", "Newsflash", "旋转飞入", "newsflash", category="exciting"),
    # Push (4)
    TransitionEffect("push_d", "Push Down", "向下推移", "push", dir="d"),
    TransitionEffect("push_l", "Push Left", "向左推移", "push", dir="l"),
    TransitionEffect("push_r", "Push Right", "向右推移", "push", dir="r"),
    TransitionEffect("push_u", "Push Up", "向上推移", "push", dir="u"),
    # Random Bars (2)
    TransitionEffect(
        "random_bar_horz", "Random Bars Horizontal", "水平随机线条", "randomBar", dir="horz"
    ),
    TransitionEffect(
        "random_bar_vert", "Random Bars Vertical", "垂直随机线条", "randomBar", dir="vert"
    ),
    # Shape (3)
    TransitionEffect("shape_circle", "Shape Circle", "圆形扩展", "circle"),
    TransitionEffect("shape_diamond", "Shape Diamond", "菱形扩展", "diamond"),
    TransitionEffect("shape_plus", "Shape Plus", "十字扩展", "plus"),
    # Split (4)
    TransitionEffect(
        "split_horz_in", "Split Horizontal In", "水平向内分割", "split", orient="horz", dir="in"
    ),
    TransitionEffect(
        "split_horz_out", "Split Horizontal Out", "水平向外分割", "split", orient="horz", dir="out"
    ),
    TransitionEffect(
        "split_vert_in", "Split Vertical In", "垂直向内分割", "split", orient="vert", dir="in"
    ),
    TransitionEffect(
        "split_vert_out", "Split Vertical Out", "垂直向外分割", "split", orient="vert", dir="out"
    ),
    # Strips (4)
    TransitionEffect("strips_ld", "Strips Left-Down", "阶梯状向左下", "strips", dir="ld"),
    TransitionEffect("strips_lu", "Strips Left-Up", "阶梯状向左上", "strips", dir="lu"),
    TransitionEffect("strips_rd", "Strips Right-Down", "阶梯状向右下", "strips", dir="rd"),
    TransitionEffect("strips_ru", "Strips Right-Up", "阶梯状向右上", "strips", dir="ru"),
    # Uncover / Pull (8)
    TransitionEffect("uncover_d", "Uncover Down", "向下揭开", "pull", dir="d"),
    TransitionEffect("uncover_l", "Uncover Left", "向左揭开", "pull", dir="l"),
    TransitionEffect("uncover_r", "Uncover Right", "向右揭开", "pull", dir="r"),
    TransitionEffect("uncover_u", "Uncover Up", "向上揭开", "pull", dir="u"),
    TransitionEffect("uncover_ld", "Uncover Left-Down", "向左下揭开", "pull", dir="ld"),
    TransitionEffect("uncover_lu", "Uncover Left-Up", "向左上揭开", "pull", dir="lu"),
    TransitionEffect("uncover_rd", "Uncover Right-Down", "向右下揭开", "pull", dir="rd"),
    TransitionEffect("uncover_ru", "Uncover Right-Up", "向右上揭开", "pull", dir="ru"),
    # Wedge (1)
    TransitionEffect("wedge", "Wedge", "扇形展开", "wedge"),
    # Wheel (5)
    TransitionEffect(
        "wheel_1", "Wheel Clockwise, 1 Spoke", "顺时针轮子 (1 辐条)", "wheel", spokes=1
    ),
    TransitionEffect(
        "wheel_2", "Wheel Clockwise, 2 Spokes", "顺时针轮子 (2 辐条)", "wheel", spokes=2
    ),
    TransitionEffect(
        "wheel_3", "Wheel Clockwise, 3 Spokes", "顺时针轮子 (3 辐条)", "wheel", spokes=3
    ),
    TransitionEffect(
        "wheel_4", "Wheel Clockwise, 4 Spokes", "顺时针轮子 (4 辐条)", "wheel", spokes=4
    ),
    TransitionEffect(
        "wheel_8", "Wheel Clockwise, 8 Spokes", "顺时针轮子 (8 辐条)", "wheel", spokes=8
    ),
    # Wipe (4)
    TransitionEffect("wipe_d", "Wipe Down", "向下擦除", "wipe", dir="d"),
    TransitionEffect("wipe_l", "Wipe Left", "向左擦除", "wipe", dir="l"),
    TransitionEffect("wipe_r", "Wipe Right", "向右擦除", "wipe", dir="r"),
    TransitionEffect("wipe_u", "Wipe Up", "向上擦除", "wipe", dir="u"),
    # Random (1)
    TransitionEffect("random", "Random Transition", "随机切换", "random"),
]


def list_transitions() -> list[TransitionEffect]:
    """Return all available transition effects."""
    return list(TRANSITION_CATALOGUE)


def get_transition_name(trans: Transition | None) -> str:
    """Get localized display name of a transition."""
    if not trans or trans.type == "none":
        return safe_tr("无切换")

    for eff in TRANSITION_CATALOGUE:
        if eff.type == trans.type:
            if trans.dir is not None and eff.dir != trans.dir:
                continue
            if trans.thruBlk != eff.thruBlk:
                continue
            if trans.spokes is not None and eff.spokes != trans.spokes:
                continue
            if trans.orient is not None and eff.orient != trans.orient:
                continue
            return safe_tr(eff.cn_name)

    # Fallback by type
    for eff in TRANSITION_CATALOGUE:
        if eff.type == trans.type:
            return safe_tr(eff.cn_name)

    return safe_tr(trans.type)


def get_transition_duration(trans: Transition | None) -> int:
    """Get transition duration in milliseconds (fast=500, med=750, slow=1000)."""
    if not trans or trans.type == "none":
        return 0
    if trans.dur is not None:
        return max(1, trans.dur)
    if trans.type == "cut" and not trans.thruBlk:
        return 0
    speeds = {"fast": 500, "med": 750, "slow": 1000}
    return speeds.get(trans.speed, 500)


def _ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - math.pow(-2.0 * t + 2.0, 2) / 2.0


def _direction_vector(d: str | None) -> tuple[float, float]:
    vectors: dict[str, tuple[float, float]] = {
        "l": (-1.0, 0.0),
        "r": (1.0, 0.0),
        "u": (0.0, -1.0),
        "d": (0.0, 1.0),
        "lu": (-1.0, -1.0),
        "ru": (1.0, -1.0),
        "ld": (-1.0, 1.0),
        "rd": (1.0, 1.0),
    }
    return vectors.get(d or "l", (-1.0, 0.0))


# ==============================================================================
# Slide Snapshot Rendering
# ==============================================================================


def render_slide_to_image(
    slide: Slide,
    presentation: Presentation,
    width: int = 960,
    height: int = 540,
    frame_states: dict[str, Any] | None = None,
) -> QImage:
    """Render a slide with background and shapes onto a QImage with animation frame support."""
    w = max(100.0, presentation.w)
    h = max(100.0, presentation.h)

    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor("#FFFFFF"))

    painter = QPainter(img)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        sx = float(width) / w
        sy = float(height) / h

        # 1. Background fill from design template
        design = presentation.get_design_for_slide(slide)
        bg_hex = design.colors.lt1 if design else "#FFFFFF"
        painter.fillRect(0, 0, width, height, QColor(bg_hex))

        # 2. Draw slide shapes
        for sh in slide.shapes:
            if sh.w <= 0 or sh.h <= 0:
                continue

            state = frame_states.get(sh.id) if frame_states else None
            if state is not None:
                if not getattr(state, "visible", True) or getattr(state, "opacity", 1.0) <= 0.001:
                    continue

            rect = QRectF(sh.x * sx, sh.y * sy, sh.w * sx, sh.h * sy)

            # Geometry path if available
            path = create_shape_path(
                getattr(sh, "geom", "rect"), rect.width(), rect.height(), sh.adj
            )
            painter.save()
            if state is not None:
                op = getattr(state, "opacity", 1.0)
                if op < 1.0:
                    painter.setOpacity(max(0.0, min(1.0, op)))
                tx = getattr(state, "translate_x", 0.0) * sx
                ty = getattr(state, "translate_y", 0.0) * sy
                rot = getattr(state, "rotation", 0.0)
                scale_x = getattr(state, "scale_x", 1.0)
                scale_y = getattr(state, "scale_y", 1.0)
                center = rect.center()
                painter.translate(center.x() + tx, center.y() + ty)
                if rot != 0.0:
                    painter.rotate(rot)
                if scale_x != 1.0 or scale_y != 1.0:
                    painter.scale(scale_x, scale_y)
                painter.translate(-rect.width() / 2.0, -rect.height() / 2.0)
            else:
                painter.translate(rect.topLeft())

            # Fill
            if sh.fill and sh.fill.type == "solid":
                painter.fillPath(path, QColor(sh.fill.color))
            elif sh.placeholder and sh.placeholder.type in ("title", "ctrTitle"):
                # Subtle title hint
                pass

            # Line / Border
            if sh.line and sh.line.width > 0:
                pen = QPen(QColor(sh.line.color), max(1.0, sh.line.width * sx))
                painter.setPen(pen)
                painter.drawPath(path)

            # Text
            if sh.text and not sh.text.is_empty():
                painter.setPen(QColor(design.colors.dk1 if design else "#000000"))
                font_size = max(8, int(14 * sy))
                font = QFont("Arial", font_size)
                if sh.placeholder and sh.placeholder.type in ("title", "ctrTitle"):
                    font.setBold(True)
                    font.setPointSize(max(10, int(20 * sy)))
                painter.setFont(font)
                inner_rect = QRectF(4, 4, rect.width() - 8, rect.height() - 8)
                painter.drawText(
                    inner_rect,
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap,
                    sh.text.plain_text,
                )

            painter.restore()
    finally:
        painter.end()

    return img


# ==============================================================================
# Transition Frame Rendering (58 Transition Algorithms)
# ==============================================================================


def render_transition_frame(
    painter: QPainter,
    img_from: QImage,
    img_to: QImage,
    trans: Transition | None,
    progress: float,
    width: int,
    height: int,
) -> None:
    """Render a single transition frame between img_from and img_to onto painter."""
    p = max(0.0, min(1.0, progress))
    w, h = float(width), float(height)
    t_type = trans.type if trans else "none"

    if t_type == "none" or p >= 1.0:
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        return
    if p <= 0.0 and t_type != "cut":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        return

    # Handle random transition selection
    if t_type == "random":
        pool = [t for t in TRANSITION_CATALOGUE if t.type not in ("none", "random")]
        chosen = pool[hash(str(trans.dir or "r")) % len(pool)]
        t_type = chosen.type
        trans = Transition(
            type=chosen.type,
            dir=chosen.dir,
            thruBlk=chosen.thruBlk,
            spokes=chosen.spokes,
            orient=chosen.orient,
        )

    # Cut transition
    if t_type == "cut":
        if trans and trans.thruBlk:
            if p < 0.5:
                painter.fillRect(QRectF(0, 0, w, h), QColor("#000000"))
            else:
                painter.drawImage(QRectF(0, 0, w, h), img_to)
        else:
            painter.drawImage(QRectF(0, 0, w, h), img_to if p >= 0.5 else img_from)
        return

    # Fade transition
    if t_type == "fade":
        if trans and trans.thruBlk:
            painter.fillRect(QRectF(0, 0, w, h), QColor("#000000"))
            if p < 0.5:
                alpha = max(0.0, 1.0 - p * 2.0)
                painter.setOpacity(alpha)
                painter.drawImage(QRectF(0, 0, w, h), img_from)
                painter.setOpacity(1.0)
            else:
                alpha = max(0.0, p * 2.0 - 1.0)
                painter.setOpacity(alpha)
                painter.drawImage(QRectF(0, 0, w, h), img_to)
                painter.setOpacity(1.0)
        else:
            painter.drawImage(QRectF(0, 0, w, h), img_from)
            painter.setOpacity(p)
            painter.drawImage(QRectF(0, 0, w, h), img_to)
            painter.setOpacity(1.0)
        return

    # Push transition
    if t_type == "push":
        e = _ease_in_out(p)
        vx, vy = _direction_vector(trans.dir if trans else "d")
        painter.drawImage(QRectF(vx * w * e, vy * h * e, w, h), img_from)
        painter.drawImage(QRectF(-vx * w * (1.0 - e), -vy * h * (1.0 - e), w, h), img_to)
        return

    # Cover transition
    if t_type == "cover":
        e = _ease_in_out(p)
        vx, vy = _direction_vector(trans.dir if trans else "d")
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        painter.drawImage(QRectF(-vx * w * (1.0 - e), -vy * h * (1.0 - e), w, h), img_to)
        return

    # Pull / Uncover transition
    if t_type == "pull":
        e = _ease_in_out(p)
        vx, vy = _direction_vector(trans.dir if trans else "d")
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.drawImage(QRectF(vx * w * e, vy * h * e, w, h), img_from)
        return

    # Wipe transition
    if t_type == "wipe":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        d = trans.dir if trans else "d"
        clip_rect = QRectF(0, 0, w, h)
        if d == "d":
            clip_rect = QRectF(0, 0, w, h * p)
        elif d == "u":
            clip_rect = QRectF(0, h * (1.0 - p), w, h * p)
        elif d == "r":
            clip_rect = QRectF(0, 0, w * p, h)
        elif d == "l":
            clip_rect = QRectF(w * (1.0 - p), 0, w * p, h)

        painter.save()
        painter.setClipRect(clip_rect)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Split transition
    if t_type == "split":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        orient = trans.orient if trans else "vert"
        direction = trans.dir if trans else "in"

        painter.save()
        clip_path = QPainterPath()
        if orient == "horz":
            if direction == "out":
                clip_path.addRect(QRectF(0, h / 2.0 - p * h / 2.0, w, p * h))
            else:
                k = (1.0 - p) * h / 2.0
                clip_path.addRect(QRectF(0, 0, w, p * h / 2.0))
                clip_path.addRect(QRectF(0, h - p * h / 2.0, w, p * h / 2.0))
        else:
            if direction == "out":
                clip_path.addRect(QRectF(w / 2.0 - p * w / 2.0, 0, p * w, h))
            else:
                clip_path.addRect(QRectF(0, 0, p * w / 2.0, h))
                clip_path.addRect(QRectF(w - p * w / 2.0, 0, p * w / 2.0, h))

        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Blinds transition (6 slats)
    if t_type == "blinds":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        d = trans.dir if trans else "horz"
        slats = 6
        painter.save()
        clip_path = QPainterPath()
        if d == "vert":
            slat_w = w / slats
            for i in range(slats):
                clip_path.addRect(QRectF(i * slat_w, 0, slat_w * p, h))
        else:
            slat_h = h / slats
            for i in range(slats):
                clip_path.addRect(QRectF(0, i * slat_h, w, slat_h * p))

        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Comb transition (8 interleaved sliding strips)
    if t_type == "comb":
        e = _ease_in_out(p)
        bands = 8
        d = trans.dir if trans else "horz"
        painter.drawImage(QRectF(0, 0, w, h), img_from)

        painter.save()
        if d == "vert":
            band_w = w / bands
            for i in range(bands):
                painter.save()
                clip = QRectF(i * band_w, 0, band_w, h)
                painter.setClipRect(clip)
                shift = -h * (1.0 - e) if i % 2 == 0 else h * (1.0 - e)
                painter.drawImage(QRectF(0, shift, w, h), img_to)
                painter.restore()
        else:
            band_h = h / bands
            for i in range(bands):
                painter.save()
                clip = QRectF(0, i * band_h, w, band_h)
                painter.setClipRect(clip)
                shift = -w * (1.0 - e) if i % 2 == 0 else w * (1.0 - e)
                painter.drawImage(QRectF(shift, 0, w, h), img_to)
                painter.restore()
        painter.restore()
        return

    # Checkerboard transition
    if t_type == "checker":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        cols, rows = 8, 6
        cw, ch = w / cols, h / rows
        d = trans.dir if trans else "horz"

        painter.save()
        clip_path = QPainterPath()
        for j in range(rows):
            for i in range(cols):
                stagger = 0.5 if (i + j) % 2 == 1 else 0.0
                tt = max(0.0, min(1.0, p * 1.5 - stagger))
                if tt > 0:
                    if d == "vert":
                        clip_path.addRect(QRectF(i * cw, j * ch, cw, ch * tt))
                    else:
                        clip_path.addRect(QRectF(i * cw, j * ch, cw * tt, ch))

        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Shape transitions (Circle, Diamond, Plus)
    if t_type in ("circle", "diamond", "plus"):
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        cx, cy = w / 2.0, h / 2.0
        max_r = math.hypot(w, h) / 2.0

        painter.save()
        clip_path = QPainterPath()
        if t_type == "circle":
            r = max_r * p
            clip_path.addEllipse(QPointF(cx, cy), r, r)
        elif t_type == "diamond":
            poly = QPolygonF(
                [
                    QPointF(cx, cy - p * h),
                    QPointF(cx + p * w, cy),
                    QPointF(cx, cy + p * h),
                    QPointF(cx - p * w, cy),
                ]
            )
            clip_path.addPolygon(poly)
        elif t_type == "plus":
            pw, ph = p * w / 2.0, p * h / 2.0
            clip_path.addRect(QRectF(cx - pw, 0, pw * 2.0, h))
            clip_path.addRect(QRectF(0, cy - ph, w, ph * 2.0))

        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Zoom / Box transition
    if t_type == "zoom":
        direction = trans.dir if trans else "out"
        if direction == "in":
            # Shrinking box reveals img_to
            painter.drawImage(QRectF(0, 0, w, h), img_to)
            k = 1.0 - p
            painter.save()
            painter.setClipRect(QRectF(w / 2.0 - k * w / 2.0, h / 2.0 - k * h / 2.0, k * w, k * h))
            painter.drawImage(QRectF(0, 0, w, h), img_from)
            painter.restore()
        else:
            # Expanding box from center
            painter.drawImage(QRectF(0, 0, w, h), img_from)
            painter.save()
            painter.setClipRect(QRectF(w / 2.0 - p * w / 2.0, h / 2.0 - p * h / 2.0, p * w, p * h))
            painter.drawImage(QRectF(0, 0, w, h), img_to)
            painter.restore()
        return

    # Wedge transition
    if t_type == "wedge":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        diag = math.hypot(w, h)
        angle = p * 180.0

        painter.save()
        clip_path = QPainterPath()
        clip_path.moveTo(w / 2.0, h / 2.0)
        clip_path.arcTo(
            QRectF(w / 2.0 - diag, h / 2.0 - diag, diag * 2.0, diag * 2.0),
            90.0 - angle,
            angle * 2.0,
        )
        clip_path.closeSubpath()
        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Wheel transition (1, 2, 3, 4, 8 spokes)
    if t_type == "wheel":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        spokes = max(1, trans.spokes if trans and trans.spokes else 4)
        diag = math.hypot(w, h)
        seg = 360.0 / spokes
        sweep = p * seg

        painter.save()
        clip_path = QPainterPath()
        for i in range(spokes):
            start = 90.0 - i * seg
            sub_path = QPainterPath()
            sub_path.moveTo(w / 2.0, h / 2.0)
            sub_path.arcTo(
                QRectF(w / 2.0 - diag, h / 2.0 - diag, diag * 2.0, diag * 2.0),
                start - sweep,
                sweep,
            )
            sub_path.closeSubpath()
            clip_path.addPath(sub_path)

        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Random Bars transition
    if t_type == "randomBar":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        d = trans.dir if trans else "horz"
        bars = 40
        painter.save()
        clip_path = QPainterPath()
        if d == "vert":
            bw = w / bars
            for i in range(bars):
                # Deterministic pseudo-random permutation
                h_val = (i * 17 + 7) % bars
                if h_val / float(bars) < p:
                    clip_path.addRect(QRectF(i * bw, 0, bw, h))
        else:
            bh = h / bars
            for i in range(bars):
                h_val = (i * 23 + 11) % bars
                if h_val / float(bars) < p:
                    clip_path.addRect(QRectF(0, i * bh, w, bh))

        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Strips transition (4 diagonal directions: ld, lu, rd, ru)
    if t_type == "strips":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        d = trans.dir if trans else "ld"
        steps = 16
        step_w = w / steps
        step_h = h / steps

        painter.save()
        clip_path = QPainterPath()
        for i in range(steps):
            for j in range(steps):
                if d == "rd":
                    dist = (i + j) / float(steps * 2)
                elif d == "lu":
                    dist = ((steps - 1 - i) + (steps - 1 - j)) / float(steps * 2)
                elif d == "ld":
                    dist = ((steps - 1 - i) + j) / float(steps * 2)
                else:  # ru
                    dist = (i + (steps - 1 - j)) / float(steps * 2)

                if dist < p:
                    clip_path.addRect(QRectF(i * step_w, j * step_h, step_w, step_h))

        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Dissolve transition (36x27 block dissolve)
    if t_type == "dissolve":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        cols, rows = 36, 27
        bw, bh = w / cols, h / rows

        painter.save()
        clip_path = QPainterPath()
        total = cols * rows
        for j in range(rows):
            for i in range(cols):
                idx = (i * 73 + j * 179 + 31) % total
                if idx / float(total) < p:
                    clip_path.addRect(QRectF(i * bw, j * bh, bw + 0.5, bh + 0.5))

        painter.setClipPath(clip_path)
        painter.drawImage(QRectF(0, 0, w, h), img_to)
        painter.restore()
        return

    # Newsflash transition (spin + scale)
    if t_type == "newsflash":
        painter.drawImage(QRectF(0, 0, w, h), img_from)
        painter.save()
        painter.translate(w / 2.0, h / 2.0)
        angle = (1.0 - p) * 720.0
        scale = max(0.001, p)
        painter.rotate(angle)
        painter.scale(scale, scale)
        painter.drawImage(QRectF(-w / 2.0, -h / 2.0, w, h), img_to)
        painter.restore()
        return

    # Default fallback: smooth fade
    painter.drawImage(QRectF(0, 0, w, h), img_from)
    painter.setOpacity(p)
    painter.drawImage(QRectF(0, 0, w, h), img_to)
    painter.setOpacity(1.0)
