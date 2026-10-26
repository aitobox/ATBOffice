"""Text wrapping, floating positioning, and linked text box layout engine for Quire.

Implements Word 2003 wrapping modes (inline, square, tight, behind, inFront, topBottom),
line obstacle avoidance, and story chaining across linked text boxes.
"""

from __future__ import annotations

import copy
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


@dataclass
class TextBoxFlowResult:
    """Result of flowing a story across linked text boxes."""

    placed_blocks: dict[int, list[Paragraph]] = field(default_factory=dict)
    overflow_story: Story | None = None
    is_complete: bool = True


def flow_linked_text_boxes(
    boxes: list[TextBoxItem],
    story: Story,
    line_layout_fn: Callable[[Paragraph, float], Any] | None = None,
) -> TextBoxFlowResult:
    """Flow a story through a sequence of linked text boxes.

    Args:
        boxes: List of TextBoxItem instances belonging to the chain.
        story: The source Story containing paragraphs to place.
        line_layout_fn: Optional layout function (default: layout_paragraph).

    Returns:
        TextBoxFlowResult with placed paragraphs per box ID and any overflow story.
    """
    if line_layout_fn is None:
        from atboffice.modules.writer.layout.portions import layout_paragraph

        line_layout_fn = layout_paragraph

    # Sort boxes by chain sequence: seq 0, 1, 2, ...
    sorted_boxes = sorted(boxes, key=lambda b: (b.chain.seq if b.chain else 0))

    placed_blocks: dict[int, list[Paragraph]] = {b.id: [] for b in sorted_boxes}
    remaining_paras: list[Paragraph] = [copy.deepcopy(p) for p in story.paras]

    for box in sorted_boxes:
        if not remaining_paras:
            break

        ins_l, ins_t, ins_r, ins_b = box.internal_margins
        usable_w = max(10.0, box.width - ins_l - ins_r)
        usable_h = max(0.0, box.height - ins_t - ins_b)
        used_h = 0.0

        box_paras: list[Paragraph] = []

        while remaining_paras:
            cur_p = remaining_paras[0]
            layout = line_layout_fn(cur_p, usable_w)
            lines = layout.lines

            if not lines:
                # Empty paragraph, minimal height
                p_h = 14.0
                if used_h + p_h <= usable_h or not box_paras:
                    box_paras.append(remaining_paras.pop(0))
                    used_h += p_h
                else:
                    break
                continue

            # Check how many lines fit in remaining height
            accum_h = 0.0
            fitted_line_count = 0
            for line in lines:
                l_h = max(10.0, line.height)
                if used_h + accum_h + l_h <= usable_h:
                    accum_h += l_h
                    fitted_line_count += 1
                else:
                    break

            if fitted_line_count == len(lines):
                # Entire paragraph fits
                box_paras.append(remaining_paras.pop(0))
                used_h += accum_h
            elif fitted_line_count > 0:
                # Partial paragraph fits: split at the end of fitted lines
                last_line = lines[fitted_line_count - 1]
                split_char_offset = 0
                for portion in last_line.portions:
                    split_char_offset = max(
                        split_char_offset, portion.char_offset + portion.length
                    )

                from atboffice.modules.writer.models.document import _next_nid, split_at

                cur_p = remaining_paras.pop(0)
                split_idx = split_at(cur_p, split_char_offset)

                p1_runs = cur_p.runs[:split_idx]
                p2_runs = cur_p.runs[split_idx:]

                p1 = Paragraph(id=cur_p.id, p_pr=copy.deepcopy(cur_p.p_pr), runs=p1_runs)
                p2 = Paragraph(id=_next_nid(), p_pr=copy.deepcopy(cur_p.p_pr), runs=p2_runs)

                box_paras.append(p1)
                used_h += accum_h
                if p2.runs:
                    remaining_paras.insert(0, p2)
                break  # Current box is full
            else:
                # 0 lines fit in this box
                if not box_paras:
                    # If box was completely empty, at least place 1 line to avoid infinite loop
                    last_line = lines[0]
                    split_char_offset = 0
                    for portion in last_line.portions:
                        split_char_offset = max(
                            split_char_offset, portion.char_offset + portion.length
                        )

                    from atboffice.modules.writer.models.document import _next_nid, split_at

                    cur_p = remaining_paras.pop(0)
                    split_idx = split_at(cur_p, split_char_offset)
                    p1 = Paragraph(id=cur_p.id, p_pr=copy.deepcopy(cur_p.p_pr), runs=cur_p.runs[:split_idx])
                    p2 = Paragraph(id=_next_nid(), p_pr=copy.deepcopy(cur_p.p_pr), runs=cur_p.runs[split_idx:])
                    box_paras.append(p1)
                    if p2.runs:
                        remaining_paras.insert(0, p2)
                break

        placed_blocks[box.id] = box_paras
        box.story.paras = box_paras

    is_complete = len(remaining_paras) == 0
    overflow_story = Story(paras=remaining_paras) if remaining_paras else None

    return TextBoxFlowResult(
        placed_blocks=placed_blocks,
        overflow_story=overflow_story,
        is_complete=is_complete,
    )
