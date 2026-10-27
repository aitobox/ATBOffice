"""Custom Animation Engine and catalogue for Lectern presentations.

Ported from PowerPoint 2003 and .vibeoffice/public/lectern/js/slideshow.js.
Supports 50+ object animations across Entrance, Emphasis, Exit, and Motion Paths,
60 FPS frame calculation, and sequential step compilation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRectF, QTimer, Signal
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.models.slide import Animation, Slide

if TYPE_CHECKING:
    pass


def safe_tr(text: str) -> str:
    """Translate animation UI string with Chinese/English fallback."""
    app = QApplication.instance()
    if app:
        translated = app.translate("Animations", text)
        if translated and translated != text:
            return translated
    # Common translation dictionary fallback
    _DICT: dict[str, str] = {
        # Classes
        "Entrance": "进入",
        "Emphasis": "强调",
        "Exit": "退出",
        "Motion Paths": "动作路径",
        # Entrance effects
        "Appear": "出现",
        "Blinds": "百叶窗",
        "Box": "盒状",
        "Checkerboard": "棋盘",
        "Circle": "圆环",
        "Diamond": "菱形",
        "Dissolve In": "溶解",
        "Fade": "淡出/淡入",
        "Fly In": "飞入",
        "Peek In": "切入",
        "Plus": "十字扩展",
        "Random Bars": "随机线条",
        "Split": "分割",
        "Strips": "阶梯",
        "Wedge": "楔形",
        "Wheel": "轮子",
        "Wipe": "擦除",
        "Zoom": "缩放",
        "Ascend": "浮入",
        "Descend": "浮出",
        "Expand": "展开",
        "Spinner": "回旋",
        # Emphasis effects
        "Grow/Shrink": "放大/缩小",
        "Spin": "陀螺旋",
        "Transparency": "透明度",
        "Teeter": "跷跷板",
        "Blink": "闪烁",
        # Exit effects
        "Disappear": "消失",
        "Dissolve Out": "向外溶解",
        "Fly Out": "飞出",
        "Peek Out": "切出",
        "Sink Down": "下沉",
        # Paths
        "Right": "向右",
        "Left": "向左",
        "Up": "向上",
        "Down": "向下",
        "Diagonal Down Right": "向右下",
        "Diagonal Up Right": "向右上",
        "Bounce Right": "弹跳",
        # Directions
        "From Bottom": "自底部",
        "From Left": "自左侧",
        "From Right": "自右侧",
        "From Top": "自顶部",
        "From Bottom-Left": "自左下",
        "From Bottom-Right": "自右下",
        "From Top-Left": "自左上",
        "From Top-Right": "自右上",
        "Horizontal": "水平",
        "Vertical": "垂直",
        "In": "放大/向内",
        "Out": "缩小/向外",
        "Across": "横向",
        "Horizontal In": "水平向内",
        "Horizontal Out": "水平向外",
        "Vertical In": "垂直向内",
        "Vertical Out": "垂直向外",
        "Left Down": "向左下",
        "Left Up": "向左上",
        "Right Down": "向右下",
        "Right Up": "向右上",
        "1 Spoke": "1 根辐条",
        "2 Spokes": "2 根辐条",
        "3 Spokes": "3 根辐条",
        "4 Spokes": "4 根辐条",
        "8 Spokes": "8 根辐条",
        # Triggers
        "On Click": "单击时",
        "With Previous": "之前",
        "After Previous": "之后",
        "Start On Click": "单击时开始",
        "Start With Previous": "从上一项开始",
        "Start After Previous": "从上一项之后开始",
        # Speeds
        "Very Slow": "非常慢 (5秒)",
        "Slow": "慢速 (3秒)",
        "Medium": "中速 (2秒)",
        "Fast": "快速 (1秒)",
        "Very Fast": "非常快 (0.5秒)",
        # Buttons & headers
        "Add Effect": "添加效果",
        "Remove": "删除",
        "Modify effect": "修改效果",
        "Start:": "开始:",
        "Direction:": "方向:",
        "Speed:": "速度:",
        "Re-Order": "重新排序",
        "Play": "播放",
        "Slide Show": "放映幻灯片",
        "AutoPreview": "自动预览",
    }
    return _DICT.get(text, text)


# ==============================================================================
# Directions Catalogue
# ==============================================================================

DIR8 = [
    ("b", "From Bottom", 4),
    ("l", "From Left", 8),
    ("r", "From Right", 2),
    ("t", "From Top", 1),
    ("bl", "From Bottom-Left", 12),
    ("br", "From Bottom-Right", 6),
    ("tl", "From Top-Left", 9),
    ("tr", "From Top-Right", 3),
]

DIR4 = [
    ("b", "From Bottom", 4),
    ("l", "From Left", 8),
    ("r", "From Right", 2),
    ("t", "From Top", 1),
]

HV = [("horz", "Horizontal", 10), ("vert", "Vertical", 5)]
INOUT = [("in", "In", 16), ("out", "Out", 32)]
ACROSS = [("across", "Across", 10), ("down", "Down", 5)]
SPLIT = [
    ("horzIn", "Horizontal In", 26),
    ("horzOut", "Horizontal Out", 42),
    ("vertIn", "Vertical In", 21),
    ("vertOut", "Vertical Out", 37),
]
DIAG = [
    ("dl", "Left Down", 12),
    ("ul", "Left Up", 9),
    ("dr", "Right Down", 6),
    ("ur", "Right Up", 3),
]
SPOKES = [
    ("1", "1 Spoke", 1),
    ("2", "2 Spokes", 2),
    ("3", "3 Spokes", 3),
    ("4", "4 Spokes", 4),
    ("8", "8 Spokes", 8),
]


# ==============================================================================
# 50+ Effects Catalogue (Entrance, Emphasis, Exit, Motion Paths)
# ==============================================================================


@dataclass(frozen=True)
class EffectDef:
    key: str
    name: str
    id: int
    dirs: list[tuple[str, str, int]] | None = None


# Entrance Effects (22)
E_ENTR: list[EffectDef] = [
    EffectDef("appear", "Appear", 1),
    EffectDef("blinds", "Blinds", 3, HV),
    EffectDef("box", "Box", 4, INOUT),
    EffectDef("checkerboard", "Checkerboard", 5, ACROSS),
    EffectDef("circle", "Circle", 6, INOUT),
    EffectDef("diamond", "Diamond", 8, INOUT),
    EffectDef("dissolve", "Dissolve In", 9),
    EffectDef("fade", "Fade", 10),
    EffectDef("flyIn", "Fly In", 2, DIR8),
    EffectDef("peekIn", "Peek In", 12, DIR4),
    EffectDef("plus", "Plus", 13, INOUT),
    EffectDef("randomBars", "Random Bars", 14, HV),
    EffectDef("split", "Split", 16, SPLIT),
    EffectDef("strips", "Strips", 18, DIAG),
    EffectDef("wedge", "Wedge", 20),
    EffectDef("wheel", "Wheel", 21, SPOKES),
    EffectDef("wipe", "Wipe", 22, DIR4),
    EffectDef("zoom", "Zoom", 23),
    EffectDef("ascend", "Ascend", 42),
    EffectDef("descend", "Descend", 47),
    EffectDef("expand", "Expand", 55),
    EffectDef("spinner", "Spinner", 49),
]

# Emphasis Effects (5)
E_EMPH: list[EffectDef] = [
    EffectDef("growShrink", "Grow/Shrink", 6),
    EffectDef("spin", "Spin", 8),
    EffectDef("transparency", "Transparency", 9),
    EffectDef("teeter", "Teeter", 32),
    EffectDef("blink", "Blink", 35),
]

# Exit Effects (19)
E_EXIT: list[EffectDef] = [
    EffectDef("disappear", "Disappear", 1),
    EffectDef("blinds", "Blinds", 3, HV),
    EffectDef("box", "Box", 4, INOUT),
    EffectDef("checkerboard", "Checkerboard", 5, ACROSS),
    EffectDef("circle", "Circle", 6, INOUT),
    EffectDef("diamond", "Diamond", 8, INOUT),
    EffectDef("dissolve", "Dissolve Out", 9),
    EffectDef("fade", "Fade", 10),
    EffectDef("flyOut", "Fly Out", 2, DIR8),
    EffectDef("peekIn", "Peek Out", 12, DIR4),
    EffectDef("plus", "Plus", 13, INOUT),
    EffectDef("randomBars", "Random Bars", 14, HV),
    EffectDef("split", "Split", 16, SPLIT),
    EffectDef("strips", "Strips", 18, DIAG),
    EffectDef("wedge", "Wedge", 20),
    EffectDef("wheel", "Wheel", 21, SPOKES),
    EffectDef("wipe", "Wipe", 22, DIR4),
    EffectDef("zoom", "Zoom", 23),
    EffectDef("descend", "Sink Down", 47),
]

# Motion Paths (8)
E_PATH: list[EffectDef] = [
    EffectDef("right", "Right", 0),
    EffectDef("left", "Left", 0),
    EffectDef("up", "Up", 0),
    EffectDef("down", "Down", 0),
    EffectDef("diagDR", "Diagonal Down Right", 0),
    EffectDef("diagUR", "Diagonal Up Right", 0),
    EffectDef("circle", "Circle", 0),
    EffectDef("bounce", "Bounce Right", 0),
]

# Speed Presets
SPEEDS: list[tuple[str, int]] = [
    ("Very Slow", 5000),
    ("Slow", 3000),
    ("Medium", 2000),
    ("Fast", 1000),
    ("Very Fast", 500),
]


def list_effects(cls: str) -> list[EffectDef]:
    """Retrieve effect catalogue by category ('entr', 'emph', 'exit', 'path')."""
    return {
        "entr": E_ENTR,
        "emph": E_EMPH,
        "exit": E_EXIT,
        "path": E_PATH,
    }.get(cls, E_ENTR)


def find_effect(cls: str, eff: str) -> EffectDef | None:
    """Find effect metadata by category and effect key."""
    for e in list_effects(cls):
        if e.key == eff:
            return e
    return None


def default_dir(cls: str, eff: str) -> str | None:
    """Get the default direction for an effect if applicable."""
    e = find_effect(cls, eff)
    if e and e.dirs and len(e.dirs) > 0:
        return e.dirs[0][0]
    return None


def effect_display_name(cls: str, eff: str) -> str:
    """Get human-readable (and localized) name of an effect."""
    e = find_effect(cls, eff)
    if e:
        return safe_tr(e.name)
    return eff


# ==============================================================================
# Easing & Math
# ==============================================================================


def clamp(val: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, val))


def ease_out(t: float) -> float:
    """Cubic ease-out curve."""
    return 1.0 - math.pow(1.0 - clamp(t, 0.0, 1.0), 3)


def ease_in_out(t: float) -> float:
    """Quadratic ease-in-out curve."""
    t = clamp(t, 0.0, 1.0)
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - math.pow(-2.0 * t + 2.0, 2) / 2.0


def path_points(anim: Animation) -> list[list[float]]:
    """Generate normalized relative 2D path points [[dx, dy], ...]."""
    if anim.pts and len(anim.pts) > 0:
        return anim.pts
    k = anim.eff
    if k == "circle":
        pts = []
        for i in range(25):
            angle = (i / 24.0) * math.pi * 2.0
            pts.append([0.12 * math.sin(angle), -0.12 * (1.0 - math.cos(angle)) * 1.333])
        return pts
    if k == "bounce":
        pts = []
        for i in range(21):
            t = i / 20.0
            pts.append([t * 0.3, -abs(math.sin(t * math.pi * 2.0)) * 0.15 * (1.0 - t * 0.5)])
        return pts
    vectors = {
        "right": [0.25, 0.0],
        "left": [-0.25, 0.0],
        "up": [0.0, -0.25],
        "down": [0.0, 0.25],
        "diagDR": [0.2, 0.2],
        "diagUR": [0.2, -0.2],
    }
    target = vectors.get(k, [0.25, 0.0])
    return [[0.0, 0.0], target]


# ==============================================================================
# Frame State Calculation
# ==============================================================================


@dataclass
class FrameState:
    """Visual properties of a shape at a specific animation frame."""

    opacity: float = 1.0
    visible: bool = True
    translate_x: float = 0.0
    translate_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: float = 0.0
    reveal_type: str | None = None
    reveal_progress: float = 1.0
    reveal_dir: str | None = None


def compute_frame(
    anim: Animation,
    t: float,
    bounds: QRectF,
    slide_w: float = 960.0,
    slide_h: float = 540.0,
) -> FrameState:
    """Compute visual transformation state for a single animation item at progress t in [0, 1]."""
    t = clamp(t, 0.0, 1.0)
    state = FrameState()

    # Motion Path
    if anim.cls == "path":
        pts = path_points(anim)
        total = len(pts) - 1
        if total <= 0:
            return state
        f = ease_in_out(t) * total
        i = min(total - 1, int(math.floor(f)))
        k = f - i
        p0 = pts[max(0, i)]
        p1 = pts[min(total, i + 1)]
        x = (p0[0] + (p1[0] - p0[0]) * k) * slide_w
        y = (p0[1] + (p1[1] - p0[1]) * k) * slide_h
        state.translate_x = x
        state.translate_y = y
        return state

    # Emphasis Effects
    if anim.cls == "emph":
        rep = max(1, anim.repeat)
        tt = 1.0 if t >= 1.0 else (t * rep) % 1.0
        eff = anim.eff
        if eff == "spin":
            deg = (1.0 if t >= 1.0 else tt) * anim.amount
            state.rotation = deg
        elif eff == "transparency":
            state.opacity = 0.5 if t >= 1.0 else (1.0 - 0.5 * min(1.0, tt * 4.0))
        elif eff == "teeter":
            state.rotation = math.sin(tt * math.pi * 4.0) * 6.0 * (1.0 - tt)
        elif eff == "blink":
            state.visible = True if t >= 1.0 else not ((tt % 0.5) < 0.25)
        elif eff == "growShrink":
            target_scale = anim.amount / 100.0 if anim.amount else 1.5
            s = 1.0 + (target_scale - 1.0) * (1.0 if t >= 1.0 else ease_in_out(tt))
            state.scale_x = s
            state.scale_y = s
        return state

    # Entrance and Exit Effects
    entering = anim.cls == "entr"
    p = t if entering else (1.0 - t)
    eff = anim.eff
    if eff == "flyOut":
        eff = "flyIn"
    elif eff == "disappear":
        eff = "appear"

    if eff == "appear":
        state.visible = (t >= 1.0) if entering else (t < 1.0)
        return state

    if eff == "fade":
        state.opacity = ease_out(p) if entering else p
        state.visible = state.opacity > 0.001
        return state

    if eff == "flyIn":
        d = anim.dir or "b"
        k = (1.0 - ease_out(t)) if entering else (t * t)
        dx, dy = 0.0, 0.0
        if "l" in d:
            dx = -(bounds.x() + bounds.width())
        elif "r" in d:
            dx = slide_w - bounds.x()
        if "t" in d:
            dy = -(bounds.y() + bounds.height())
        elif "b" in d:
            dy = slide_h - bounds.y()
        state.translate_x = dx * k
        state.translate_y = dy * k
        state.visible = True
        return state

    if eff == "peekIn":
        d = anim.dir or "b"
        off = 1.0 - (ease_out(t) if entering else (1.0 - t))
        dx = -bounds.width() if d == "l" else (bounds.width() if d == "r" else 0.0)
        dy = -bounds.height() if d == "t" else (bounds.height() if d == "b" else 0.0)
        state.translate_x = dx * off
        state.translate_y = dy * off
        state.reveal_type = "wipe"
        state.reveal_dir = d
        state.reveal_progress = 1.0
        return state

    if eff == "zoom":
        scale = max(0.0001, ease_out(p) if entering else p)
        state.scale_x = scale
        state.scale_y = scale
        state.opacity = min(1.0, p * 2.0)
        state.visible = state.opacity > 0.01
        return state

    if eff == "ascend":
        offset_y = (1.0 - ease_out(p)) * min(bounds.height(), 60.0) * 0.8
        state.translate_y = offset_y
        state.opacity = p
        state.visible = p > 0.01
        return state

    if eff == "descend":
        mult = 1.0 if entering else -1.0
        offset_y = -(1.0 - ease_out(p)) * min(bounds.height(), 60.0) * 0.8 * mult
        state.translate_y = offset_y
        state.opacity = p
        state.visible = p > 0.01
        return state

    if eff == "expand":
        state.scale_x = 0.7 + 0.3 * ease_out(p)
        state.opacity = p
        state.visible = p > 0.01
        return state

    if eff == "spinner":
        state.rotation = (1.0 - ease_out(p)) * 360.0
        scale = max(0.0001, ease_out(p))
        state.scale_x = scale
        state.scale_y = scale
        state.opacity = p
        state.visible = p > 0.01
        return state

    # Fallback to wipe/reveal types (blinds, box, checkerboard, wipe, wheel, etc.)
    state.reveal_type = eff
    state.reveal_progress = p
    state.reveal_dir = anim.dir or default_dir(anim.cls, eff)
    state.visible = p > 0.001
    return state


# ==============================================================================
# Step Compiler & Sequencing
# ==============================================================================


@dataclass
class AnimationItem:
    """Compiled runtime animation target item."""

    anim: Animation
    start: int  # ms relative to step
    end: int  # ms relative to step
    dur: int  # ms
    shape_id: str
    para_index: int | None = None
    done: bool = False


@dataclass
class AnimationStep:
    """A build step containing one or more simultaneous or sequenced animations."""

    items: list[AnimationItem] = field(default_factory=list)
    total_duration: int = 0  # ms
    is_auto: bool = False  # True if starts automatically without user click
    last_start: int = 0
    last_end: int = 0


def compile_steps(
    slide: Slide,
    slide_w: float = 960.0,
    slide_h: float = 540.0,
    no_anim: bool = False,
) -> list[AnimationStep]:
    """Compile slide animations into sequential build steps according to trigger rules."""
    if no_anim or not slide.animations:
        return []

    # Filter animations that reference existing shapes
    valid_shape_ids = {s.id for s in slide.shapes}
    for s in slide.shapes:
        if s.type == "group" and s.kids:
            valid_shape_ids.update(k.id for k in s.kids)

    anims = [a for a in slide.animations if a.sid in valid_shape_ids]
    if not anims:
        return []

    # Expand paragraph builds
    expanded_items: list[Animation] = []
    for a in anims:
        sh = slide.find_shape(a.sid)
        if a.by == "para" and sh and sh.text and len(sh.text.paragraphs) > 1 and a.cls != "path":
            prior = False
            for idx, p in enumerate(sh.text.paragraphs):
                p_text = p.plain_text.strip()
                if not p_text:
                    continue
                start_trigger = (
                    a.start if not prior else ("with" if (p.level or 0) > 0 else a.start)
                )
                delay_val = 0 if (prior and (p.level or 0) > 0) else a.delay
                clone = Animation(
                    id=f"{a.id}_p{idx}",
                    sid=a.sid,
                    cls=a.cls,
                    eff=a.eff,
                    dir=a.dir,
                    start=start_trigger,
                    dur=a.dur,
                    delay=delay_val,
                    by=a.by,
                    repeat=a.repeat,
                    amount=a.amount,
                    pts=a.pts,
                    para=idx,
                )
                expanded_items.append(clone)
                prior = True
        else:
            expanded_items.append(a)

    steps: list[AnimationStep] = []
    cur_step: AnimationStep | None = None

    for a in expanded_items:
        # 'click' starts a new step; first item always creates a step
        if cur_step is None or a.start == "click":
            cur_step = AnimationStep(
                items=[],
                total_duration=0,
                is_auto=(a.start != "click"),
                last_start=0,
                last_end=0,
            )
            steps.append(cur_step)

        dur = a.dur
        if a.cls == "emph":
            dur = a.dur * max(1, a.repeat)

        if a.start == "after":
            start_time = cur_step.last_end + a.delay
        elif a.start == "with":
            start_time = cur_step.last_start + a.delay
        else:
            start_time = a.delay

        # Instant appear/disappear have duration 0
        is_instant = (a.cls == "entr" and a.eff == "appear") or (
            a.cls == "exit" and a.eff == "disappear"
        )
        end_time = start_time + (0 if is_instant else dur)

        item = AnimationItem(
            anim=a,
            start=start_time,
            end=end_time,
            dur=dur,
            shape_id=a.sid,
            para_index=a.para,
        )
        cur_step.items.append(item)
        cur_step.last_start = start_time
        cur_step.last_end = max(cur_step.last_end, end_time)

    for s in steps:
        s.total_duration = max((it.end for it in s.items), default=0)

    return steps


def apply_initial_state(steps: list[AnimationStep]) -> dict[str, FrameState]:
    """Calculate the initial appearance before any animations have been triggered.

    Shapes with entrance animations are hidden initially; other shapes are visible.
    """
    states: dict[str, FrameState] = {}
    seen: set[str] = set()

    for step in steps:
        for it in step.items:
            key = f"{it.shape_id}_{it.para_index}" if it.para_index is not None else it.shape_id
            if key not in seen:
                seen.add(key)
                if it.anim.cls == "entr":
                    states[key] = FrameState(visible=False, opacity=0.0)
                else:
                    states[key] = FrameState(visible=True, opacity=1.0)
    return states


def apply_step_state(
    steps: list[AnimationStep],
    completed_steps_count: int,
    shapes_bounds: dict[str, QRectF] | None = None,
    slide_w: float = 960.0,
    slide_h: float = 540.0,
) -> dict[str, FrameState]:
    """Calculate final state after completed_steps_count steps have finished completely."""
    states = apply_initial_state(steps)
    bounds_map = shapes_bounds or {}

    for s_idx in range(min(completed_steps_count, len(steps))):
        step = steps[s_idx]
        for it in step.items:
            key = f"{it.shape_id}_{it.para_index}" if it.para_index is not None else it.shape_id
            b = bounds_map.get(it.shape_id, QRectF(0, 0, 100, 100))
            final_frame = compute_frame(it.anim, 1.0, b, slide_w, slide_h)
            if it.anim.cls == "entr":
                final_frame.visible = True
                final_frame.opacity = 1.0
                final_frame.translate_x = 0.0
                final_frame.translate_y = 0.0
                final_frame.scale_x = 1.0
                final_frame.scale_y = 1.0
                final_frame.rotation = 0.0
            elif it.anim.cls == "exit":
                final_frame.visible = False
                final_frame.opacity = 0.0
            states[key] = final_frame
    return states


# ==============================================================================
# 60 FPS Animation Step Player
# ==============================================================================


class AnimationStepPlayer(QObject):
    """High-precision 60 FPS step animator for presentation slideshows."""

    frameChanged = Signal(dict)  # dict[str, FrameState]
    stepFinished = Signal(int)  # step_idx

    def __init__(
        self,
        slide_w: float = 960.0,
        slide_h: float = 540.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.slide_w = slide_w
        self.slide_h = slide_h
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 FPS
        self._timer.timeout.connect(self._on_tick)

        self._active_step: AnimationStep | None = None
        self._active_step_idx: int = -1
        self._start_time_ms: float = 0.0
        self._base_states: dict[str, FrameState] = {}
        self._bounds_map: dict[str, QRectF] = {}
        self._path_accum: dict[str, tuple[float, float]] = {}

    @property
    def is_playing(self) -> bool:
        return self._timer.isActive()

    def play(
        self,
        step: AnimationStep,
        step_idx: int,
        base_states: dict[str, FrameState],
        bounds_map: dict[str, QRectF],
    ) -> None:
        """Start playing a build step."""
        self.stop()
        self._active_step = step
        self._active_step_idx = step_idx
        self._base_states = dict(base_states)
        self._bounds_map = bounds_map

        for it in step.items:
            it.done = False

        import time

        self._start_time_ms = time.perf_counter() * 1000.0
        self._timer.start()
        self._on_tick()

    def finish_now(self) -> None:
        """Immediately skip the current step to completion."""
        if not self._active_step or not self.is_playing:
            return
        self._timer.stop()
        final_states = dict(self._base_states)
        for it in self._active_step.items:
            key = f"{it.shape_id}_{it.para_index}" if it.para_index is not None else it.shape_id
            b = self._bounds_map.get(it.shape_id, QRectF(0, 0, 100, 100))
            frame = compute_frame(it.anim, 1.0, b, self.slide_w, self.slide_h)
            if it.anim.cls == "entr":
                frame.visible = True
                frame.opacity = 1.0
            elif it.anim.cls == "exit":
                frame.visible = False
                frame.opacity = 0.0
            elif it.anim.cls == "path":
                prev_x, prev_y = self._path_accum.get(key, (0.0, 0.0))
                self._path_accum[key] = (prev_x + frame.translate_x, prev_y + frame.translate_y)
                frame.translate_x = self._path_accum[key][0]
                frame.translate_y = self._path_accum[key][1]
            final_states[key] = frame
            it.done = True

        self.frameChanged.emit(final_states)
        finished_idx = self._active_step_idx
        self._active_step = None
        self.stepFinished.emit(finished_idx)

    def stop(self) -> None:
        """Cancel current animation."""
        if self._timer.isActive():
            self._timer.stop()
        self._active_step = None

    def _on_tick(self) -> None:
        if not self._active_step:
            self._timer.stop()
            return

        import time

        elapsed = (time.perf_counter() * 1000.0) - self._start_time_ms
        all_done = True
        current_states = dict(self._base_states)

        for it in self._active_step.items:
            key = f"{it.shape_id}_{it.para_index}" if it.para_index is not None else it.shape_id
            b = self._bounds_map.get(it.shape_id, QRectF(0, 0, 100, 100))

            if elapsed < it.start:
                all_done = False
                continue

            dur = it.end - it.start
            progress = 1.0 if dur <= 0 else clamp((elapsed - it.start) / float(dur), 0.0, 1.0)

            if progress < 1.0:
                all_done = False

            frame = compute_frame(it.anim, progress, b, self.slide_w, self.slide_h)
            if it.anim.cls == "entr":
                frame.visible = True
            elif it.anim.cls == "path":
                prev_x, prev_y = self._path_accum.get(key, (0.0, 0.0))
                frame.translate_x += prev_x
                frame.translate_y += prev_y

            current_states[key] = frame

        self.frameChanged.emit(current_states)

        if all_done:
            self.finish_now()
