"""Base helper functions for constructing Lectern presentation templates."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide, Transition, create_slide
from atboffice.modules.presentation.models.text import Paragraph, Run, TextBody
from atboffice.modules.presentation.smartart.engine import SmartArtEngine, relayout


def make_title_text(title: str) -> TextBody:
    """Construct a centered title TextBody model with a single paragraph."""
    run = Run(text=title)
    para = Paragraph(level=0, runs=[run])
    return TextBody(paragraphs=[para], anchor="ctr", wrap=True)


def make_body_text(lines: list[str]) -> TextBody:
    """Construct a bulleted body TextBody model handling tab-indented sub-items."""
    paragraphs: list[Paragraph] = []
    for line in lines:
        lvl = 0
        txt = line
        while txt.startswith("\t"):
            lvl += 1
            txt = txt[1:]
        paragraphs.append(Paragraph(level=lvl, runs=[Run(text=txt)]))
    return TextBody(paragraphs=paragraphs, anchor="t", wrap=True)


def add_template_slide(
    pres: Presentation,
    layout: str,
    title: str,
    *cols: list[str],
) -> Slide:
    """Append a new slide to the presentation populated with title and column body texts."""
    design = pres.get_design_for_slide(None)
    slide = create_slide(layout=layout, design=design)
    pres.slides.append(slide)

    # Locate title placeholder (ctrTitle or title)
    title_ph = next(
        (
            sh
            for sh in slide.shapes
            if sh.placeholder and sh.placeholder.type in ("ctrTitle", "title")
        ),
        None,
    )
    if title_ph:
        title_ph.text = make_title_text(title)

    if layout == "title":
        sub_ph = next(
            (
                sh
                for sh in slide.shapes
                if sh.placeholder and sh.placeholder.type == "subTitle"
            ),
            None,
        )
        if sub_ph and cols and cols[0]:
            sub_ph.text = make_body_text(cols[0])
    else:
        body_phs = [
            sh
            for sh in slide.shapes
            if sh.placeholder and sh.placeholder.type in ("body", "obj")
        ]
        for i, b_ph in enumerate(body_phs):
            if i < len(cols) and cols[i]:
                b_ph.text = make_body_text(cols[i])

    slide.transition = Transition(type="fade", speed="med", click=True, after=None)
    return slide


def insert_diagram_placeholder(
    pres: Presentation,
    slide: Slide,
    layout: str,
    lines: list[str],
    colors: str = "ocean",
    style: str = "moderate",
) -> Shape:
    """Replace a slide's body placeholder with an IntelliArt/SmartArt diagram group."""
    at = next(
        (
            sh
            for sh in slide.shapes
            if sh.placeholder and sh.placeholder.type in ("body", "obj")
        ),
        None,
    )
    box_x = at.x if at else pres.w * 0.15
    box_y = at.y if at else pres.h * 0.22
    box_w = at.w if at else pres.w * 0.7
    box_h = at.h if at else pres.h * 0.66

    eng = SmartArtEngine()
    items = eng.items_from_outline(lines)
    shape_id = f"s_sa_{uuid.uuid4().hex[:8]}"
    name = f"{layout.capitalize()} {len(slide.shapes) + 1}"

    g = Shape(
        id=shape_id,
        type="group",
        name=name,
        x=box_x,
        y=box_y,
        w=box_w,
        h=box_h,
        sa={
            "layout": layout,
            "colors": colors,
            "style": style,
            "items": [it.to_dict() for it in items],
        },
        kids=[],
    )
    design = pres.get_design_for_slide(slide)
    relayout(g, design)

    if at and at in slide.shapes:
        idx = slide.shapes.index(at)
        slide.shapes[idx] = g
    else:
        slide.shapes.append(g)

    return g


def insert_table_placeholder(
    pres: Presentation,
    slide: Slide,
    rows: list[list[str]],
    widths: list[float],
) -> Shape:
    """Replace a slide's table placeholder with a styled Table shape."""
    tp = next(
        (
            sh
            for sh in slide.shapes
            if sh.placeholder and sh.placeholder.type in ("tbl", "obj")
        ),
        None,
    )
    bx = tp.x if tp else pres.w * 0.1
    by = tp.y if tp else pres.h * 0.25
    bw = tp.w if tp else pres.w * 0.8
    bh = tp.h if tp else pres.h * 0.55

    rh = min(44.0, bh / max(1, len(rows)))
    tot_h = rh * len(rows)
    cols = [bw * f for f in widths]

    tbl_rows: list[dict[str, Any]] = []
    for ri, row in enumerate(rows):
        cells: list[dict[str, Any]] = []
        for ci, val in enumerate(row):
            fill = (
                {"t": "solid", "c": "accent1", "a": 1.0}
                if ri == 0
                else {"t": "solid", "c": "#F2F5FA" if ri % 2 else "#FFFFFF", "a": 1.0}
            )
            font_sz = 18.0 if ri == 0 else 16.0
            bold = True if ri == 0 else False
            color = "lt1" if ri == 0 else "dk1"
            run = Run(text=val, size=font_sz, bold=bold, color=color)
            para = Paragraph(level=0, runs=[run])
            tx = TextBody(paragraphs=[para], anchor="ctr", wrap=True)

            cell = {
                "fill": fill,
                "text": val,
                "tx": tx,
                "bd": {
                    k: {"c": "#B4C3DC", "w": 1.0, "dash": "solid"}
                    for k in ("l", "r", "t", "b")
                },
            }
            cells.append(cell)
        tbl_rows.append({"h": rh, "cells": cells})

    tbl_data = {"cols": cols, "rows": tbl_rows}
    shape_id = f"s_tbl_{uuid.uuid4().hex[:8]}"
    name = f"Table {len(slide.shapes) + 1}"

    t = Shape(
        id=shape_id,
        type="table",
        name=name,
        x=bx,
        y=by,
        w=bw,
        h=tot_h,
        tbl=tbl_data,
        placeholder=copy.deepcopy(tp.placeholder) if tp else None,
    )

    if tp and tp in slide.shapes:
        idx = slide.shapes.index(tp)
        slide.shapes[idx] = t
    else:
        slide.shapes.append(t)

    return t
