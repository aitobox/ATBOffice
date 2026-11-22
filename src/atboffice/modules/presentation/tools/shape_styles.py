"""Drawing-toolbar presets: dash style, arrow style, shadow style and line weight."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from atboffice.modules.presentation.models.shape import Line, Shadow

# toolbar id suffix -> DrawingML prstDash value (rendered by DASH_PATTERNS)
DASH_STYLES: dict[str, str] = {
    "solid": "solid",
    "round_dot": "sysDot",
    "short_dash": "sysDash",
    "long_dash": "lgDash",
    "dash_dot": "dashDot",
}

# head = line start, tail = line end (DrawingML headEnd / tailEnd)
ARROW_STYLES: dict[str, tuple[dict[str, Any] | None, dict[str, Any] | None]] = {
    "none": (None, None),
    "style1": (None, {"type": "triangle", "w": "med", "len": "med"}),
    "style2": (None, {"type": "stealth", "w": "med", "len": "med"}),
    "double": (
        {"type": "triangle", "w": "med", "len": "med"},
        {"type": "triangle", "w": "med", "len": "med"},
    ),
}

SHADOW_STYLES: dict[str, Shadow | None] = {
    "none": None,
    "style1": Shadow(blur=2.0, dist=4.0, alpha=0.35, color="#000000", angle=45.0),
    "style2": Shadow(blur=2.0, dist=4.0, alpha=0.35, color="#000000", angle=135.0),
    "style3": Shadow(blur=8.0, dist=6.0, alpha=0.30, color="#000000", angle=90.0),
}


def _line_of(shape: Any) -> Line:
    if getattr(shape, "line", None) is None:
        shape.line = Line()
    return shape.line


def apply_dash(shapes: Iterable[Any], key: str) -> int:
    dash = DASH_STYLES[key]
    n = 0
    for sh in shapes:
        ln = _line_of(sh)
        ln.dash = dash
        ln.custom_dash = None
        if ln.type == "none":
            ln.type = "solid"
        n += 1
    return n


def apply_arrows(shapes: Iterable[Any], key: str) -> int:
    """Arrowheads only make sense on open paths (lines / connectors)."""
    head, tail = ARROW_STYLES[key]
    n = 0
    for sh in shapes:
        if not getattr(sh, "is_connector", False):
            continue
        ln = _line_of(sh)
        ln.head = dict(head) if head else None
        ln.tail = dict(tail) if tail else None
        n += 1
    return n


def apply_shadow(shapes: Iterable[Any], key: str) -> int:
    import copy

    preset = SHADOW_STYLES[key]
    n = 0
    for sh in shapes:
        sh.shadow = copy.deepcopy(preset)
        n += 1
    return n


def apply_line_weight(shapes: Iterable[Any], points: float) -> int:
    n = 0
    for sh in shapes:
        ln = _line_of(sh)
        ln.width = float(points)
        if ln.type == "none":
            ln.type = "solid"
            if not ln.color:
                ln.color = "tx1"
        n += 1
    return n
