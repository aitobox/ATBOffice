"""Undoable floating object commands for Quire canvas (wrap, picture, drawing, format)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QDialog, QWidget

from atboffice.core.i18n import safe_tr
from atboffice.drawing.dml import DmlFill
from atboffice.drawing.shape_style import DmlLine
from atboffice.modules.writer.models.drawing import (
    ChartItem,
    Crop,
    FloatProperties,
    PositionH,
    PositionV,
    WrapMode,
)

OBJECT_HINT = "请先在文档中选择图片或图形对象"

_DEFAULT_ARROW_TAIL: dict[str, str] = {"type": "triangle", "w": "med", "len": "med"}
_DEFAULT_SHADOW: dict[str, Any] = {
    "blur": 2.0,
    "dist": 4.0,
    "alpha": 0.35,
    "color": "#000000",
    "angle": 45.0,
}


def _show_hint(
    canvas: Any,
    text: str,
    status_cb: Callable[[str], None] | None = None,
) -> None:
    if status_cb is not None:
        status_cb(text)
        return
    win = canvas.window() if hasattr(canvas, "window") else None
    sb = win.statusBar() if win is not None and hasattr(win, "statusBar") else None
    if sb is not None:
        sb.showMessage(text, 3000)


def selected_float_or_hint(
    canvas: Any,
    status_cb: Callable[[str], None] | None = None,
) -> Any | None:
    """Return ``canvas.selected_float()``, or emit a localized hint and return ``None``."""
    item = canvas.selected_float() if hasattr(canvas, "selected_float") else None
    if item is None:
        _show_hint(canvas, safe_tr(OBJECT_HINT), status_cb=status_cb)
        return None
    return item


def _clear_stale_raw_xml(item: Any) -> None:
    """Drop cached verbatim DrawingML XML on edited shapes/pictures so saves reflect edits."""
    if isinstance(item, ChartItem) or getattr(item, "children", None):
        return
    if hasattr(item, "raw_xml"):
        item.raw_xml = None


def _ensure_line(item: Any) -> DmlLine:
    line = getattr(item, "line", None)
    if line is None:
        line = DmlLine(visible=True, color="#000000", width=0.75, dash="solid")
        item.line = line
    return line


def _set_shadow(item: Any, enabled: bool) -> None:
    item.shadow = bool(enabled)
    raw = getattr(item, "raw_data", None)
    if not isinstance(raw, dict):
        raw = {}
        item.raw_data = raw
    if enabled:
        raw["shadow"] = dict(_DEFAULT_SHADOW)
    else:
        raw.pop("shadow", None)


def _apply_wrap_to_item(item: Any, mode: str | WrapMode) -> None:
    target_mode = mode if isinstance(mode, WrapMode) else WrapMode(str(mode))
    if target_mode == WrapMode.INLINE:
        item.float_pr = None
        _clear_stale_raw_xml(item)
        return

    fp = getattr(item, "float_pr", None)
    if fp is None:
        fp = FloatProperties(
            wrap=target_mode,
            pos_h=PositionH(rel="margin", offset=72.0),
            pos_v=PositionV(rel="paragraph", offset=12.0),
        )
        item.float_pr = fp
    fp.wrap = target_mode
    fp.behind = target_mode == WrapMode.BEHIND
    _clear_stale_raw_xml(item)


def set_wrap_mode(
    canvas: Any,
    mode: str | WrapMode,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Set text wrapping mode on the selected floating object undoably."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    target_mode = mode if isinstance(mode, WrapMode) else WrapMode(str(mode))

    def mutate() -> bool:
        _apply_wrap_to_item(item, target_mode)
        return True

    ok = bool(canvas.run_undoable(mutate, label=safe_tr("文字环绕")))
    if ok and target_mode == WrapMode.INLINE and hasattr(canvas, "select_float"):
        canvas.select_float(None, None)
    return ok


def wrap_inline(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Convert the selected floating object to inline layout."""
    return set_wrap_mode(canvas, WrapMode.INLINE, status_cb=status_cb)


def wrap_square(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Set square text wrapping on the selected floating object."""
    return set_wrap_mode(canvas, WrapMode.SQUARE, status_cb=status_cb)


def wrap_tight(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Set tight text wrapping on the selected floating object."""
    return set_wrap_mode(canvas, WrapMode.TIGHT, status_cb=status_cb)


def wrap_behind(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Send the selected floating object behind text."""
    return set_wrap_mode(canvas, WrapMode.BEHIND, status_cb=status_cb)


def wrap_front(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Bring the selected floating object in front of text."""
    return set_wrap_mode(canvas, WrapMode.IN_FRONT, status_cb=status_cb)


def pic_rotate(
    canvas: Any,
    delta: float = 90.0,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Rotate the selected floating object by +90 degrees mod 360 undoably."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    def mutate() -> bool:
        cur_rot = float(getattr(item, "rotation", 0.0) or 0.0)
        item.rotation = round((cur_rot + float(delta)) % 360.0, 1)
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=safe_tr("旋转对象")))


def pic_reset(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Reset rotation, brightness, contrast, color mode, crop and natural size."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    def mutate() -> bool:
        item.rotation = 0.0
        if hasattr(item, "brightness"):
            item.brightness = 0.0
        if hasattr(item, "contrast"):
            item.contrast = 0.0
        if hasattr(item, "grayscale"):
            item.grayscale = False
        if hasattr(item, "washout"):
            item.washout = False
        if hasattr(item, "bw"):
            item.bw = False
        item.color_mode = "auto"
        raw = getattr(item, "raw_data", None)
        if isinstance(raw, dict):
            raw["color_mode"] = "auto"
        if hasattr(item, "crop") and item.crop is not None:
            item.crop = Crop()
        nat_w = float(getattr(item, "natural_width", 0.0) or 0.0)
        nat_h = float(getattr(item, "natural_height", 0.0) or 0.0)
        if nat_w > 0.0 and nat_h > 0.0:
            item.width = nat_w
            item.height = nat_h
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=safe_tr("重设图片")))


def pic_adjust_brightness(
    canvas: Any,
    delta: float,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Adjust brightness of the selected floating object in [-1.0, 1.0]."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    label = safe_tr("增加亮度") if delta >= 0 else safe_tr("降低亮度")

    def mutate() -> bool:
        cur = float(getattr(item, "brightness", 0.0) or 0.0)
        item.brightness = round(max(-1.0, min(1.0, cur + float(delta))), 2)
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=label))


def pic_adjust_contrast(
    canvas: Any,
    delta: float,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Adjust contrast of the selected floating object in [-1.0, 1.0]."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    label = safe_tr("增加对比度") if delta >= 0 else safe_tr("降低对比度")

    def mutate() -> bool:
        cur = float(getattr(item, "contrast", 0.0) or 0.0)
        item.contrast = round(max(-1.0, min(1.0, cur + float(delta))), 2)
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=label))


def pic_set_color_mode(
    canvas: Any,
    mode: str,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Set picture color mode ('auto', 'gray', 'bw', 'washout') undoably."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    normalized = "washout" if mode in ("wash", "washout") else mode

    def mutate() -> bool:
        item.grayscale = normalized == "gray"
        item.washout = normalized == "washout"
        item.bw = normalized == "bw"
        item.color_mode = normalized
        raw = getattr(item, "raw_data", None)
        if not isinstance(raw, dict):
            raw = {}
            item.raw_data = raw
        raw["color_mode"] = normalized
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=safe_tr("图片颜色")))


def draw_line_weight(
    canvas: Any,
    width_pt: float = 0.75,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Set stroke width on the selected floating shape/object undoably."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    def mutate() -> bool:
        line = _ensure_line(item)
        line.visible = True
        line.width = float(width_pt)
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=safe_tr("线型")))


def draw_dash_style(
    canvas: Any,
    dash: str = "dash",
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Set stroke dash style on the selected floating shape/object undoably."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    def mutate() -> bool:
        line = _ensure_line(item)
        line.visible = True
        line.dash = str(dash)
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=safe_tr("虚线线型")))


def draw_arrow_style(
    canvas: Any,
    style: str = "style1",
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Set arrow head preset on the selected floating shape/object undoably."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    def mutate() -> bool:
        line = _ensure_line(item)
        line.visible = True
        line.head = None
        line.tail = dict(_DEFAULT_ARROW_TAIL)
        raw = getattr(item, "raw_data", None)
        if not isinstance(raw, dict):
            raw = {}
            item.raw_data = raw
        raw["arrow"] = str(style)
        item.arrow = str(style)
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=safe_tr("箭头样式")))


def draw_shadow_style(
    canvas: Any,
    enabled: bool = True,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Set shadow preset on the selected floating shape/object undoably."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    def mutate() -> bool:
        _set_shadow(item, bool(enabled))
        _clear_stale_raw_xml(item)
        return True

    return bool(canvas.run_undoable(mutate, label=safe_tr("阴影样式")))


def draw_weight_075(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Apply 0.75 pt line weight to the selected floating object."""
    return draw_line_weight(canvas, 0.75, status_cb=status_cb)


def draw_dash_dash(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Apply dashed stroke style to the selected floating object."""
    return draw_dash_style(canvas, "dash", status_cb=status_cb)


def draw_arrow_1(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Apply arrow style 1 to the selected floating object."""
    return draw_arrow_style(canvas, "style1", status_cb=status_cb)


def draw_shadow_1(canvas: Any, status_cb: Callable[[str], None] | None = None) -> bool:
    """Apply shadow style 1 to the selected floating object."""
    return draw_shadow_style(canvas, True, status_cb=status_cb)


def apply_format_object_settings(target: Any, settings: dict[str, Any]) -> bool:
    """Apply FormatObjectDialog settings dictionary onto ``target``."""
    target.width = max(1.0, float(settings["width"]))
    target.height = max(1.0, float(settings["height"]))
    target.rotation = round(float(settings["rotation"]) % 360.0, 1)

    _apply_wrap_to_item(target, settings["wrap_mode"])

    if settings.get("line_visible"):
        line = _ensure_line(target)
        line.visible = True
        line.color = str(settings.get("line_color") or "#000000")
        line.width = max(0.25, float(settings.get("line_width", 0.75)))
    elif getattr(target, "line", None) is not None:
        target.line.visible = False
        target.line.width = 0.0

    if settings.get("fill_enabled"):
        fill_color = str(settings.get("fill_color") or "#FFFFFF")
        fill = getattr(target, "fill", None)
        if fill is None:
            target.fill = DmlFill(kind="solid", color=fill_color)
        else:
            fill.kind = "solid"
            fill.color = fill_color
    elif getattr(target, "fill", None) is not None:
        target.fill.kind = "none"

    _set_shadow(target, bool(settings.get("shadow", False)))
    _clear_stale_raw_xml(target)
    return True


def format_object(
    canvas: Any,
    parent: QWidget | None = None,
    status_cb: Callable[[str], None] | None = None,
) -> bool:
    """Open FormatObjectDialog for the selected floating object and commit undoably."""
    item = selected_float_or_hint(canvas, status_cb=status_cb)
    if item is None:
        return False

    from atboffice.modules.writer.dialogs.format_object_dialog import FormatObjectDialog

    dlg = FormatObjectDialog(item, parent=parent)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return False

    settings = dlg.get_settings()
    ok = bool(
        canvas.run_undoable(
            lambda: apply_format_object_settings(item, settings),
            label=safe_tr("设置对象格式"),
        )
    )
    if (
        ok
        and settings.get("wrap_mode") == WrapMode.INLINE.value
        and hasattr(canvas, "select_float")
    ):
        canvas.select_float(None, None)
    return ok
