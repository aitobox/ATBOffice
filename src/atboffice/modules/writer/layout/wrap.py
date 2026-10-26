"""Text wrapping, floating positioning, and linked text box layout engine for Quire.

Implements Word 2003 wrapping modes (inline, square, tight, behind, inFront, topBottom),
line obstacle avoidance, and story chaining across linked text boxes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from atboffice.modules.writer.models.document import (
    Paragraph,
    RunItem,
    Story,
    TextItem,
    ilen,
    split_at,
)
from atboffice.modules.writer.models.drawing import (
    DrawingObject,
    FloatProperties,
    PictureItem,
    TextBoxItem,
    WrapDist,
    WrapMode,
    WrapSide,
)


@dataclass
class FloatBox:
    """Bounding box of an anchored floating drawing on the physical page."""

    x: float
    y: float
    w: float
    h: float
    wrap_mode: WrapMode
    side: WrapSide
    dist: WrapDist
    z_index: int = 0
    behind: bool = False
    item: DrawingObject | None = None


def resolve_float_box(
    item: DrawingObject,
    page_dims: tuple[float, float],
    margin_dims: tuple[float, float, float, float],
    col_dims: tuple[float, float],
    para_top: float,
    anchor_x: float = 0.0,
    anchor_y: float = 0.0,
) -> FloatBox:
    """Calculate absolute page coordinates for a floating drawing object.

    Args:
        item: The floating DrawingObject.
        page_dims: (page_width, page_height)
        margin_dims: (margin_left, margin_right, margin_top, margin_bottom)
        col_dims: (col_left, col_width)
        para_top: Top y-coordinate of anchor paragraph.
        anchor_x: X-coordinate of inline anchor.
        anchor_y: Y-coordinate of inline anchor.

    Returns:
        FloatBox with resolved x, y, width, height.
    """
    pw, ph = page_dims
    ml, mr, mt, mb = margin_dims
    cl, cw = col_dims

    f_pr = item.float_pr or FloatProperties()
    ow, oh = item.width, item.height

    # Horizontal placement
    pos_h = f_pr.pos_h
    if pos_h.rel == "page":
        x0 = 0.0
        aw = pw
    elif pos_h.rel == "margin":
        x0 = ml
        aw = pw - ml - mr
    elif pos_h.rel == "leftMargin":
        x0 = 0.0
        aw = ml
    elif pos_h.rel == "rightMargin":
        x0 = pw - mr
        aw = mr
    elif pos_h.rel == "character":
        x0 = anchor_x
        aw = 0.0
    else:  # "column"
        x0 = cl
        aw = cw

    if pos_h.align == "center":
        x = x0 + (aw - ow) / 2.0
    elif pos_h.align in ("right", "outside"):
        x = x0 + aw - ow
    elif pos_h.align in ("left", "inside"):
        x = x0
    elif pos_h.percent is not None:
        x = x0 + aw * (pos_h.percent / 100.0)
    else:
        x = x0 + pos_h.offset

    # Vertical placement
    pos_v = f_pr.pos_v
    if pos_v.rel == "page":
        y0 = 0.0
        ah = ph
    elif pos_v.rel == "margin":
        y0 = mt
        ah = ph - mt - mb
    elif pos_v.rel == "topMargin":
        y0 = 0.0
        ah = mt
    elif pos_v.rel == "bottomMargin":
        y0 = ph - mb
        ah = mb
    elif pos_v.rel == "line":
        y0 = anchor_y
        ah = 0.0
    else:  # "paragraph"
        y0 = para_top
        ah = 0.0

    if pos_v.align == "center":
        y = y0 + (ah - oh) / 2.0
    elif pos_v.align in ("bottom", "outside"):
        y = y0 + ah - oh
    elif pos_v.align in ("top", "inside"):
        y = y0
    elif pos_v.percent is not None:
        y = y0 + ah * (pos_v.percent / 100.0)
    else:
        y = y0 + pos_v.offset

    return FloatBox(
        x=round(x, 2),
        y=round(y, 2),
        w=round(ow, 2),
        h=round(oh, 2),
        wrap_mode=f_pr.wrap,
        side=f_pr.side,
        dist=f_pr.dist,
        z_index=f_pr.z_index,
        behind=f_pr.behind or (f_pr.wrap == WrapMode.BEHIND),
        item=item,
    )


def calculate_line_segments(
    col_left: float,
    col_right: float,
    y: float,
    line_height: float,
    float_boxes: list[FloatBox],
    min_segment_width: float = 18.0,
) -> list[tuple[float, float]]:
    """Calculate available horizontal text spans on a line given floating obstacles.

    Args:
        col_left: Left boundary of the column/margin.
        col_right: Right boundary of the column/margin.
        y: Baseline/top y-coordinate of the candidate text line.
        line_height: Height of the line.
        float_boxes: List of active FloatBoxes on the page.
        min_segment_width: Minimum width to consider a span valid for text.

    Returns:
        List of (start_x, end_x) tuples where text can be placed.
        Empty list indicates line cannot be placed at this vertical position (e.g. topBottom wrap).
    """
    segments: list[tuple[float, float]] = [(col_left, col_right)]

    # Filter obstacles that overlap line vertically
    for fb in float_boxes:
        if fb.wrap_mode in (WrapMode.BEHIND, WrapMode.IN_FRONT, WrapMode.INLINE):
            continue

        obs_t = fb.y - fb.dist.top
        obs_b = fb.y + fb.h + fb.dist.bottom

        # Check vertical overlap with line interval [y, y + line_height]
        if not (y + line_height > obs_t and y < obs_b):
            continue

        # TopBottom wrap rejects any text on the obstacle's vertical range
        if fb.wrap_mode == WrapMode.TOP_BOTTOM:
            return []

        # Square / Tight wrap exclusions
        obs_l = fb.x - fb.dist.left
        obs_r = fb.x + fb.w + fb.dist.right

        # Apply side constraint
        if fb.side == WrapSide.LEFT:
            obs_r = max(obs_r, col_right)
        elif fb.side == WrapSide.RIGHT:
            obs_l = min(obs_l, col_left)

        new_segs: list[tuple[float, float]] = []
        for s_start, s_end in segments:
            # Check if obstacle overlaps segment horizontally
            if obs_r <= s_start or obs_l >= s_end:
                new_segs.append((s_start, s_end))
            else:
                # Left side of obstacle
                if s_start < obs_l:
                    seg_w = obs_l - s_start
                    if seg_w >= min_segment_width:
                        new_segs.append((s_start, obs_l))
                # Right side of obstacle
                if obs_r < s_end:
                    seg_w = s_end - obs_r
                    if seg_w >= min_segment_width:
                        new_segs.append((obs_r, s_end))

        if fb.side == WrapSide.LARGEST and len(new_segs) > 1:
            widest = max(new_segs, key=lambda s: s[1] - s[0])
            new_segs = [widest]

        segments = new_segs
        if not segments:
            break

    return segments
