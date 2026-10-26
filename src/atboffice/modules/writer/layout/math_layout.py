"""Mathematical layout and vector typography engine for Quire word processor.

Calculates bounding boxes, ascents, descents, and baselines for Office Math (OMML)
AST nodes, and performs high-fidelity vector rendering using PySide6 QPainter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen

from atboffice.modules.writer.layout.portions import (
    compute_font_metrics,
    measure_text_width,
)
from atboffice.modules.writer.models.omml import (
    MathAccent,
    MathBar,
    MathBorderBoxNode,
    MathBoxNode,
    MathDelimiter,
    MathEqArray,
    MathFraction,
    MathFunction,
    MathGroupChar,
    MathLimitLower,
    MathLimitUpper,
    MathMatrix,
    MathNary,
    MathNode,
    MathPhantomNode,
    MathPre,
    MathRadical,
    MathRun,
    MathSub,
    MathSubSup,
    MathSup,
    OfficeMathItem,
)


@dataclass
class RenderText:
    """Render operation for a text string."""

    x: float
    y: float  # Baseline position
    text: str
    font_size: float
    font_family: str
    bold: bool = False
    italic: bool = False


@dataclass
class RenderLine:
    """Render operation for a vector line (e.g. fraction bar)."""

    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 1.0
    color: str = "#000000"


@dataclass
class RenderPath:
    """Render operation for a vector path (e.g. radical tick, brackets)."""

    path: QPainterPath
    pen: QPen
    brush: QBrush | None = None


@dataclass
class MathLayoutBox:
    """Bounding box, metrics, and vector operations for a laid-out formula element."""

    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0
    baseline: float = 0.0
    render_ops: list[Any] = field(default_factory=list)
    children: list[MathLayoutBox] = field(default_factory=list)

    def offset(self, dx: float, dy: float) -> None:
        """Offset box and all its nested render operations."""
        self.x += dx
        self.y += dy
        new_ops: list[Any] = []
        for op in self.render_ops:
            if isinstance(op, RenderText):
                new_ops.append(
                    RenderText(
                        x=op.x + dx,
                        y=op.y + dy,
                        text=op.text,
                        font_size=op.font_size,
                        font_family=op.font_family,
                        bold=op.bold,
                        italic=op.italic,
                    )
                )
            elif isinstance(op, RenderLine):
                new_ops.append(
                    RenderLine(
                        x1=op.x1 + dx,
                        y1=op.y1 + dy,
                        x2=op.x2 + dx,
                        y2=op.y2 + dy,
                        width=op.width,
                        color=op.color,
                    )
                )
            elif isinstance(op, RenderPath):
                p = QPainterPath(op.path)
                p.translate(dx, dy)
                new_ops.append(RenderPath(path=p, pen=op.pen, brush=op.brush))
            else:
                new_ops.append(op)
        self.render_ops = new_ops
        for c in self.children:
            c.offset(dx, dy)


# ---------------------------------------------------------------------------
# Node Layout Functions
# ---------------------------------------------------------------------------


def layout_run(run: MathRun, font_sz: float, font_fam: str) -> MathLayoutBox:
    """Layout a MathRun with text metrics."""
    text = run.text or ""
    if not text:
        ascent, descent = compute_font_metrics(font_sz, font_fam)
        return MathLayoutBox(
            width=0.0,
            height=ascent + descent,
            ascent=ascent,
            descent=descent,
            baseline=ascent,
        )

    w = measure_text_width(text, font_sz, font_fam)
    ascent, descent = compute_font_metrics(font_sz, font_fam)
    h = ascent + descent
    bold = run.style in ("b", "bi")
    italic = not run.normal and (run.style in ("i", "bi") or not run.style)

    box = MathLayoutBox(
        width=w,
        height=h,
        ascent=ascent,
        descent=descent,
        baseline=ascent,
    )
    box.render_ops.append(
        RenderText(
            x=0.0,
            y=ascent,
            text=text,
            font_size=font_sz,
            font_family=font_fam,
            bold=bold,
            italic=italic,
        )
    )
    return box


def layout_sequence(
    nodes: list[MathNode], font_sz: float, font_fam: str
) -> MathLayoutBox:
    """Layout a sequence of math nodes horizontally along a shared baseline."""
    if not nodes:
        ascent, descent = compute_font_metrics(font_sz, font_fam)
        return MathLayoutBox(
            width=0.0,
            height=ascent + descent,
            ascent=ascent,
            descent=descent,
            baseline=ascent,
        )

    child_boxes: list[MathLayoutBox] = []
    for node in nodes:
        b = layout_node(node, font_sz, font_fam)
        child_boxes.append(b)

    # Determine shared baseline (maximum ascent across children)
    max_ascent = max((cb.ascent for cb in child_boxes), default=font_sz * 0.8)
    max_descent = max((cb.descent for cb in child_boxes), default=font_sz * 0.2)
    total_height = max_ascent + max_descent

    res_box = MathLayoutBox(
        width=0.0,
        height=total_height,
        ascent=max_ascent,
        descent=max_descent,
        baseline=max_ascent,
    )

    cur_x = 0.0
    for cb in child_boxes:
        # Align child baseline to max_ascent
        dy = max_ascent - cb.baseline
        cb.offset(cur_x, dy)
        res_box.render_ops.extend(cb.render_ops)
        res_box.children.append(cb)
        cur_x += cb.width

    res_box.width = cur_x
    return res_box


def layout_fraction(frac: MathFraction, font_sz: float, font_fam: str) -> MathLayoutBox:
    """Layout a fraction m:f."""
    sub_font_sz = max(6.0, font_sz * 0.85)
    num_box = layout_sequence(frac.num, sub_font_sz, font_fam)
    den_box = layout_sequence(frac.den, sub_font_sz, font_fam)

    pad = 3.0
    content_w = max(num_box.width, den_box.width)
    total_w = content_w + pad * 2

    # Math axis line height (fraction bar baseline)
    bar_thickness = max(1.0, font_sz * 0.06)
    axis_y = font_sz * 0.25  # Height above formula baseline

    # Numerator placed above bar with small gap
    gap = 2.0
    num_y = -gap - num_box.height
    den_y = gap

    # Center children horizontally
    num_box.offset((total_w - num_box.width) / 2.0, num_y)
    den_box.offset((total_w - den_box.width) / 2.0, den_y)

    # Calculate overall metrics relative to axis
    ascent = abs(num_y) + axis_y
    descent = den_y + den_box.height - axis_y
    total_h = ascent + descent
    baseline = ascent

    box = MathLayoutBox(
        width=total_w,
        height=total_h,
        ascent=ascent,
        descent=descent,
        baseline=baseline,
    )

    # Shift children so baseline matches
    num_box.offset(0.0, baseline - axis_y)
    den_box.offset(0.0, baseline - axis_y)

    box.render_ops.extend(num_box.render_ops)
    box.render_ops.extend(den_box.render_ops)
    box.children.extend([num_box, den_box])

    if frac.type != "noBar":
        bar_y = baseline - axis_y
        box.render_ops.append(
            RenderLine(
                x1=1.0,
                y1=bar_y,
                x2=total_w - 1.0,
                y2=bar_y,
                width=bar_thickness,
                color="#000000",
            )
        )

    return box


def layout_scripts(
    node: MathSup | MathSub | MathSubSup | MathPre, font_sz: float, font_fam: str
) -> MathLayoutBox:
    """Layout superscript, subscript, or combined scripts."""
    base_box = layout_sequence(node.base, font_sz, font_fam)
    script_sz = max(6.0, font_sz * 0.7)

    sup_box: MathLayoutBox | None = None
    sub_box: MathLayoutBox | None = None

    if hasattr(node, "sup") and node.sup:
        sup_box = layout_sequence(node.sup, script_sz, font_fam)
    if hasattr(node, "sub") and node.sub:
        sub_box = layout_sequence(node.sub, script_sz, font_fam)

    is_pre = isinstance(node, MathPre)
    scripts_w = max(
        sup_box.width if sup_box else 0.0,
        sub_box.width if sub_box else 0.0,
    )
    total_w = base_box.width + scripts_w + (1.0 if scripts_w > 0 else 0.0)

    # Superscript shifted up, subscript shifted down
    sup_dy = -base_box.ascent * 0.45
    sub_dy = base_box.descent * 0.45

    max_ascent = max(
        base_box.ascent,
        (abs(sup_dy) + sup_box.ascent) if sup_box else 0.0,
    )
    max_descent = max(
        base_box.descent,
        (sub_dy + sub_box.descent) if sub_box else 0.0,
    )
    total_h = max_ascent + max_descent
    baseline = max_ascent

    res = MathLayoutBox(
        width=total_w,
        height=total_h,
        ascent=max_ascent,
        descent=max_descent,
        baseline=baseline,
    )

    base_x = scripts_w + 1.0 if is_pre else 0.0
    scripts_x = 0.0 if is_pre else base_box.width + 1.0

    base_box.offset(base_x, baseline - base_box.baseline)
    res.render_ops.extend(base_box.render_ops)
    res.children.append(base_box)

    if sup_box:
        sup_box.offset(scripts_x, baseline - sup_box.baseline + sup_dy)
        res.render_ops.extend(sup_box.render_ops)
        res.children.append(sup_box)

    if sub_box:
        sub_box.offset(scripts_x, baseline - sub_box.baseline + sub_dy)
        res.render_ops.extend(sub_box.render_ops)
        res.children.append(sub_box)

    return res


def layout_radical(rad: MathRadical, font_sz: float, font_fam: str) -> MathLayoutBox:
    """Layout radical element m:rad."""
    base_box = layout_sequence(rad.base, font_sz, font_fam)
    deg_box: MathLayoutBox | None = None
    if not rad.deg_hide and rad.deg:
        deg_box = layout_sequence(rad.deg, max(5.0, font_sz * 0.6), font_fam)

    tick_w = 9.0
    deg_w = deg_box.width if deg_box else 0.0
    total_w = deg_w + tick_w + base_box.width + 3.0

    vinculum_pad = 2.0
    ascent = base_box.ascent + vinculum_pad + 2.0
    descent = base_box.descent + 1.0
    total_h = ascent + descent
    baseline = ascent

    res = MathLayoutBox(
        width=total_w,
        height=total_h,
        ascent=ascent,
        descent=descent,
        baseline=baseline,
    )

    # Position radicand
    rad_x = deg_w + tick_w
    base_box.offset(rad_x, baseline - base_box.baseline)
    res.render_ops.extend(base_box.render_ops)
    res.children.append(base_box)

    # Vector path for radical symbol √
    top_y = 1.0
    bottom_y = total_h - 1.0
    mid_y = bottom_y - (total_h * 0.35)

    path = QPainterPath()
    # Left hook
    path.moveTo(deg_w + 1.0, mid_y)
    path.lineTo(deg_w + 3.5, mid_y)
    # Down to bottom notch
    path.lineTo(deg_w + 6.0, bottom_y)
    # Up to top corner
    path.lineTo(deg_w + tick_w, top_y)
    # Horizontal vinculum bar across radicand
    path.lineTo(total_w - 1.0, top_y)

    pen = QPen(QColor(0, 0, 0), max(1.0, font_sz * 0.07))
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    res.render_ops.append(RenderPath(path=path, pen=pen))

    if deg_box:
        deg_box.offset(0.0, top_y + 1.0)
        res.render_ops.extend(deg_box.render_ops)
        res.children.append(deg_box)

    return res


def layout_delimiter(delm: MathDelimiter, font_sz: float, font_fam: str) -> MathLayoutBox:
    """Layout delimiter brackets element m:d."""
    inner_boxes: list[MathLayoutBox] = []
    for item in delm.items:
        ib = layout_sequence(item, font_sz, font_fam)
        inner_boxes.append(ib)

    max_ascent = max((ib.ascent for ib in inner_boxes), default=font_sz * 0.8)
    max_descent = max((ib.descent for ib in inner_boxes), default=font_sz * 0.2)
    baseline = max_ascent
    total_h = max_ascent + max_descent

    # Bracket width
    b_w = max(5.0, font_sz * 0.35)
    sep_w = max(4.0, font_sz * 0.25)

    cur_x = b_w + 1.0
    res = MathLayoutBox(
        height=total_h,
        ascent=max_ascent,
        descent=max_descent,
        baseline=baseline,
    )

    for i, ib in enumerate(inner_boxes):
        if i > 0 and delm.sep_chr:
            res.render_ops.append(
                RenderText(
                    x=cur_x,
                    y=baseline,
                    text=delm.sep_chr,
                    font_size=font_sz,
                    font_family=font_fam,
                )
            )
            cur_x += sep_w
        ib.offset(cur_x, baseline - ib.baseline)
        res.render_ops.extend(ib.render_ops)
        res.children.append(ib)
        cur_x += ib.width

    cur_x += 1.0
    total_w = cur_x + b_w
    res.width = total_w

    # Draw left delimiter
    if delm.beg_chr:
        res.render_ops.append(
            _make_bracket_op(
                delm.beg_chr, 0.0, total_h, baseline, font_sz, font_fam, is_left=True
            )
        )
    # Draw right delimiter
    if delm.end_chr:
        res.render_ops.append(
            _make_bracket_op(
                delm.end_chr,
                total_w - b_w,
                total_h,
                baseline,
                font_sz,
                font_fam,
                is_left=False,
            )
        )

    return res


def _make_bracket_op(
    chr_str: str,
    x: float,
    height: float,
    baseline: float,
    font_sz: float,
    font_fam: str,
    is_left: bool,
) -> Any:
    """Create stretched bracket path or text op."""
    if height <= font_sz * 1.3:
        return RenderText(
            x=x,
            y=baseline,
            text=chr_str,
            font_size=font_sz,
            font_family=font_fam,
        )

    # Vector stretched brackets for tall equations
    path = QPainterPath()
    w = max(5.0, font_sz * 0.35)
    top = 1.0
    bot = height - 1.0

    if chr_str in ("(", ")"):
        ctrl_x = x + w if is_left else x
        edge_x = x if is_left else x + w
        path.moveTo(edge_x, top)
        path.quadTo(ctrl_x, (top + bot) / 2.0, edge_x, bot)
    elif chr_str in ("[", "]"):
        path.moveTo(x + w if is_left else x, top)
        path.lineTo(x if is_left else x + w, top)
        path.lineTo(x if is_left else x + w, bot)
        path.lineTo(x + w if is_left else x, bot)
    elif chr_str in ("{", "}"):
        mid = (top + bot) / 2.0
        edge_x = x if is_left else x + w
        ctrl_x = x + w if is_left else x
        path.moveTo(ctrl_x, top)
        path.quadTo(edge_x, (top + mid) / 2.0, edge_x, mid)
        path.quadTo(edge_x, (mid + bot) / 2.0, ctrl_x, bot)
    else:
        return RenderText(
            x=x,
            y=baseline,
            text=chr_str,
            font_size=font_sz,
            font_family=font_fam,
        )

    pen = QPen(QColor(0, 0, 0), max(1.0, font_sz * 0.06))
    return RenderPath(path=path, pen=pen)


def layout_nary(nary: MathNary, font_sz: float, font_fam: str) -> MathLayoutBox:
    """Layout n-ary operator (e.g. integral, summation)."""
    op_sz = font_sz * 1.3
    op_w = measure_text_width(nary.op, op_sz, font_fam)
    ascent, descent = compute_font_metrics(op_sz, font_fam)

    sub_font_sz = max(6.0, font_sz * 0.7)
    sub_box = (
        layout_sequence(nary.sub, sub_font_sz, font_fam)
        if not nary.sub_hide and nary.sub
        else None
    )
    sup_box = (
        layout_sequence(nary.sup, sub_font_sz, font_fam)
        if not nary.sup_hide and nary.sup
        else None
    )
    base_box = layout_sequence(nary.base, font_sz, font_fam)

    under = nary.lim_loc == "undOvr"
    if under:
        limits_w = max(
            op_w,
            sub_box.width if sub_box else 0.0,
            sup_box.width if sup_box else 0.0,
        )
        total_w = limits_w + 3.0 + base_box.width
        top_h = (sup_box.height + 2.0) if sup_box else 0.0
        bot_h = (sub_box.height + 2.0) if sub_box else 0.0
        tot_ascent = ascent + top_h
        tot_descent = descent + bot_h
        baseline = tot_ascent

        res = MathLayoutBox(
            width=total_w,
            height=tot_ascent + tot_descent,
            ascent=tot_ascent,
            descent=tot_descent,
            baseline=baseline,
        )

        op_x = (limits_w - op_w) / 2.0
        res.render_ops.append(
            RenderText(
                x=op_x,
                y=baseline,
                text=nary.op,
                font_size=op_sz,
                font_family=font_fam,
            )
        )
        if sup_box:
            sup_box.offset((limits_w - sup_box.width) / 2.0, 0.0)
            res.render_ops.extend(sup_box.render_ops)
            res.children.append(sup_box)
        if sub_box:
            sub_box.offset((limits_w - sub_box.width) / 2.0, baseline + descent + 2.0)
            res.render_ops.extend(sub_box.render_ops)
            res.children.append(sub_box)

        base_box.offset(limits_w + 3.0, baseline - base_box.baseline)
        res.render_ops.extend(base_box.render_ops)
        res.children.append(base_box)
        return res

    # Side-by-side subSup limits
    limits_w = max(
        sub_box.width if sub_box else 0.0,
        sup_box.width if sup_box else 0.0,
    )
    total_w = op_w + limits_w + 3.0 + base_box.width
    baseline = max(ascent, base_box.ascent)
    total_h = baseline + max(descent, base_box.descent)

    res = MathLayoutBox(
        width=total_w,
        height=total_h,
        ascent=baseline,
        descent=total_h - baseline,
        baseline=baseline,
    )
    res.render_ops.append(
        RenderText(
            x=0.0,
            y=baseline,
            text=nary.op,
            font_size=op_sz,
            font_family=font_fam,
        )
    )
    if sup_box:
        sup_box.offset(op_w + 1.0, baseline - sup_box.baseline - font_sz * 0.4)
        res.render_ops.extend(sup_box.render_ops)
        res.children.append(sup_box)
    if sub_box:
        sub_box.offset(op_w + 1.0, baseline - sub_box.baseline + font_sz * 0.3)
        res.render_ops.extend(sub_box.render_ops)
        res.children.append(sub_box)

    base_box.offset(op_w + limits_w + 3.0, baseline - base_box.baseline)
    res.render_ops.extend(base_box.render_ops)
    res.children.append(base_box)
    return res


def layout_matrix(mat: MathMatrix, font_sz: float, font_fam: str) -> MathLayoutBox:
    """Layout a 2D matrix element m:m."""
    if not mat.rows:
        return MathLayoutBox()

    row_boxes: list[list[MathLayoutBox]] = []
    num_cols = max(len(r) for r in mat.rows)

    col_widths = [0.0] * num_cols
    row_heights = [0.0] * len(mat.rows)
    row_ascents = [0.0] * len(mat.rows)

    for r_idx, r in enumerate(mat.rows):
        r_list: list[MathLayoutBox] = []
        for c_idx in range(num_cols):
            cell_nodes = r[c_idx] if c_idx < len(r) else []
            cb = layout_sequence(cell_nodes, font_sz, font_fam)
            r_list.append(cb)
            col_widths[c_idx] = max(col_widths[c_idx], cb.width)
            row_heights[r_idx] = max(row_heights[r_idx], cb.height)
            row_ascents[r_idx] = max(row_ascents[r_idx], cb.ascent)
        row_boxes.append(r_list)

    h_pad = 6.0
    v_pad = 4.0
    total_w = sum(col_widths) + (num_cols - 1) * h_pad
    total_h = sum(row_heights) + (len(mat.rows) - 1) * v_pad
    baseline = total_h / 2.0  # Matrix baseline typically centered vertically

    res = MathLayoutBox(
        width=total_w,
        height=total_h,
        ascent=baseline,
        descent=total_h - baseline,
        baseline=baseline,
    )

    cur_y = 0.0
    for r_idx, r_list in enumerate(row_boxes):
        cur_x = 0.0
        for c_idx, cb in enumerate(r_list):
            cell_w = col_widths[c_idx]
            # Center content horizontally within cell
            ox = cur_x + (cell_w - cb.width) / 2.0
            oy = cur_y + (row_heights[r_idx] - cb.height) / 2.0
            cb.offset(ox, oy)
            res.render_ops.extend(cb.render_ops)
            res.children.append(cb)
            cur_x += cell_w + h_pad
        cur_y += row_heights[r_idx] + v_pad

    return res


def layout_node(node: MathNode, font_sz: float, font_fam: str) -> MathLayoutBox:
    """Dispatch layout for any MathNode subtype."""
    if isinstance(node, MathRun):
        return layout_run(node, font_sz, font_fam)
    elif isinstance(node, MathFraction):
        return layout_fraction(node, font_sz, font_fam)
    elif isinstance(node, (MathSup, MathSub, MathSubSup, MathPre)):
        return layout_scripts(node, font_sz, font_fam)
    elif isinstance(node, MathRadical):
        return layout_radical(node, font_sz, font_fam)
    elif isinstance(node, MathDelimiter):
        return layout_delimiter(node, font_sz, font_fam)
    elif isinstance(node, MathNary):
        return layout_nary(node, font_sz, font_fam)
    elif isinstance(node, MathMatrix):
        return layout_matrix(node, font_sz, font_fam)
    elif isinstance(node, MathFunction):
        name_box = layout_sequence(node.name, font_sz, font_fam)
        base_box = layout_sequence(node.base, font_sz, font_fam)
        return layout_sequence([node.name, node.base], font_sz, font_fam)  # type: ignore[list-item]
    elif isinstance(node, (MathBoxNode, MathBorderBoxNode, MathPhantomNode)):
        inner = layout_sequence(node.base, font_sz, font_fam)
        if isinstance(node, MathPhantomNode) and not node.show:
            inner.render_ops.clear()
        elif isinstance(node, MathBorderBoxNode):
            pen = QPen(QColor(0, 0, 0), 1.0)
            inner.render_ops.append(
                RenderLine(0, 0, inner.width, 0, 1.0)
            )
            inner.render_ops.append(
                RenderLine(inner.width, 0, inner.width, inner.height, 1.0)
            )
            inner.render_ops.append(
                RenderLine(inner.width, inner.height, 0, inner.height, 1.0)
            )
            inner.render_ops.append(
                RenderLine(0, inner.height, 0, 0, 1.0)
            )
        return inner
    return MathLayoutBox()


# ---------------------------------------------------------------------------
# Top-level Item Layout and Vector Drawing
# ---------------------------------------------------------------------------


def layout_math_item(
    item: OfficeMathItem,
    font_size: float = 12.0,
    font_family: str = "Cambria Math",
) -> MathLayoutBox:
    """Calculate bounding box and vector render operations for OfficeMathItem."""
    sz = item.font_size or font_size
    box = layout_sequence(item.nodes, sz, font_family)

    item.width = box.width
    item.height = box.height
    item.ascent = box.ascent
    item.descent = box.descent
    item.layout_box = box
    return box


def paint_math(
    painter: QPainter,
    item: OfficeMathItem,
    origin_x: float,
    baseline_y: float,
    zoom: float = 1.0,
) -> None:
    """Render the mathematical formula onto a PySide6 QPainter at origin_x, baseline_y."""
    box = getattr(item, "layout_box", None)
    if box is None:
        box = layout_math_item(item, item.font_size)

    # Calculate top-left based on formula baseline
    top_y = baseline_y - (box.baseline * zoom)
    left_x = origin_x

    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        for op in box.render_ops:
            if isinstance(op, RenderText):
                font = QFont(op.font_family)
                font.setPointSizeF(op.font_size * zoom)
                if op.bold:
                    font.setBold(True)
                if op.italic:
                    font.setItalic(True)
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 0, 0)))

                pt = QPointF(left_x + op.x * zoom, top_y + op.y * zoom)
                painter.drawText(pt, op.text)

            elif isinstance(op, RenderLine):
                pen = QPen(QColor(op.color), max(1.0, op.width * zoom))
                painter.setPen(pen)
                p1 = QPointF(left_x + op.x1 * zoom, top_y + op.y1 * zoom)
                p2 = QPointF(left_x + op.x2 * zoom, top_y + op.y2 * zoom)
                painter.drawLine(p1, p2)

            elif isinstance(op, RenderPath):
                scaled_pen = QPen(op.pen)
                scaled_pen.setWidthF(max(1.0, op.pen.widthF() * zoom))
                painter.setPen(scaled_pen)
                if op.brush:
                    painter.setBrush(op.brush)
                else:
                    painter.setBrush(Qt.BrushStyle.NoBrush)

                t_path = QPainterPath(op.path)
                # Translate path to viewport origin
                t_path.translate(left_x / zoom, top_y / zoom)
                # We can draw the scaled path
                painter.scale(zoom, zoom)
                painter.drawPath(t_path)
                painter.scale(1.0 / zoom, 1.0 / zoom)

    finally:
        painter.restore()
