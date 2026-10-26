"""Standard slide layouts and placeholder frame geometry calculator for Lectern."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from atboffice.modules.presentation.models.designs import DesignTemplate
from atboffice.modules.presentation.models.shape import Fill, Line, PlaceholderInfo, Shape
from atboffice.modules.presentation.models.text import Paragraph, TextBody


def safe_tr(text: str) -> str:
    """Safe translation fallback when Qt QCoreApplication is not instantiated."""
    try:
        from PySide6.QtCore import QCoreApplication

        return QCoreApplication.translate("LecternLayouts", text)
    except Exception:
        return text


@dataclass(frozen=True)
class LayoutInfo:
    """Definition metadata for a slide layout."""

    key: str
    name: str
    group: str
    ox: str


# 21 standard layouts matching PowerPoint 2003
LAYOUTS: list[LayoutInfo] = [
    LayoutInfo(key="title", name="Title Slide", group="Text Layouts", ox="title"),
    LayoutInfo(key="titleOnly", name="Title Only", group="Text Layouts", ox="titleOnly"),
    LayoutInfo(key="text", name="Title and Text", group="Text Layouts", ox="tx"),
    LayoutInfo(
        key="twoText", name="Title and 2-Column Text", group="Text Layouts", ox="twoColTx"
    ),
    LayoutInfo(key="blank", name="Blank", group="Content Layouts", ox="blank"),
    LayoutInfo(key="contentOnly", name="Content", group="Content Layouts", ox="objOnly"),
    LayoutInfo(key="content", name="Title and Content", group="Content Layouts", ox="obj"),
    LayoutInfo(key="twoContent", name="Title and 2 Content", group="Content Layouts", ox="twoObj"),
    LayoutInfo(
        key="contentTwoContent",
        name="Title, Content and 2 Content",
        group="Content Layouts",
        ox="objAndTwoObj",
    ),
    LayoutInfo(
        key="twoContentContent",
        name="Title, 2 Content and Content",
        group="Content Layouts",
        ox="twoObjAndObj",
    ),
    LayoutInfo(
        key="fourContent", name="Title and 4 Content", group="Content Layouts", ox="fourObj"
    ),
    LayoutInfo(
        key="textContent",
        name="Title, Text, and Content",
        group="Text and Content Layouts",
        ox="txAndObj",
    ),
    LayoutInfo(
        key="contentText",
        name="Title, Content and Text",
        group="Text and Content Layouts",
        ox="objAndTx",
    ),
    LayoutInfo(
        key="textTwoContent",
        name="Title, Text, and 2 Content",
        group="Text and Content Layouts",
        ox="txAndTwoObj",
    ),
    LayoutInfo(
        key="twoContentText",
        name="Title, 2 Content and Text",
        group="Text and Content Layouts",
        ox="twoObjAndTx",
    ),
    LayoutInfo(key="table", name="Title and Table", group="Other Layouts", ox="tbl"),
    LayoutInfo(key="chart", name="Title and Chart", group="Other Layouts", ox="chart"),
    LayoutInfo(
        key="textOverContent",
        name="Title and Text over Content",
        group="Other Layouts",
        ox="txOverObj",
    ),
    LayoutInfo(
        key="contentOverText",
        name="Title and Content over Text",
        group="Other Layouts",
        ox="objOverTx",
    ),
    LayoutInfo(key="vertText", name="Title and Vertical Text", group="Other Layouts", ox="vertTx"),
    LayoutInfo(
        key="vertTitleText",
        name="Vertical Title and Text",
        group="Other Layouts",
        ox="vertTitleAndTx",
    ),
]

LAYOUT_MAP: dict[str, LayoutInfo] = {item.key: item for item in LAYOUTS}


def get_layout_info(key: str) -> LayoutInfo:
    return LAYOUT_MAP.get(key, LAYOUT_MAP["text"])


# User prompt hints for empty placeholders
PROMPTS = {
    "title": "Click to add title",
    "ctrTitle": "Click to add title",
    "subTitle": "Click to add subtitle",
    "body": "Click to add text",
    "obj": "Click to add text",
    "tbl": "Double click to add table",
    "chart": "Double click to add chart",
    "pic": "Click icon to add picture",
    "dt": "",
    "ftr": "",
    "sldNum": "",
}


def _ph_name(ph_type: str, idx: int = 0) -> str:
    names = {
        "title": "Title",
        "ctrTitle": "Title",
        "subTitle": "Subtitle",
        "body": "Text Placeholder",
        "obj": "Content Placeholder",
        "tbl": "Table Placeholder",
        "chart": "Chart Placeholder",
        "dt": "Date Placeholder",
        "ftr": "Footer Placeholder",
        "sldNum": "Slide Number Placeholder",
    }
    base = names.get(ph_type, "Placeholder")
    return f"{base} {idx + 1}"


def layout_frames(key: str, design: DesignTemplate) -> list[dict[str, Any]]:
    """Calculate the concrete placeholder frame bounding boxes for a given layout and design."""
    ph = design.placeholder_frames
    t_box = ph.get("title", (48.0, 21.6, 864.0, 90.0))
    b_box = ph.get("body", (48.0, 126.0, 864.0, 356.4))

    bx, by, bw, bh = b_box
    tx, ty, tw, th = t_box

    gap = round(bw * 0.0185, 2)
    half = (bw - gap) / 2.0
    vh = (bh - gap) / 2.0

    l1 = {"x": bx, "y": by, "w": half, "h": bh}
    r1 = {"x": bx + half + gap, "y": by, "w": half, "h": bh}

    lt = {"x": bx, "y": by, "w": half, "h": vh}
    lb = {"x": bx, "y": by + vh + gap, "w": half, "h": vh}
    rt = {"x": bx + half + gap, "y": by, "w": half, "h": vh}
    rb = {"x": bx + half + gap, "y": by + vh + gap, "w": half, "h": vh}

    top = {"x": bx, "y": by, "w": bw, "h": vh}
    bot = {"x": bx, "y": by + vh + gap, "w": bw, "h": vh}

    ttl = {"type": "title", "idx": 0, "x": tx, "y": ty, "w": tw, "h": th}

    def frame(
        ph_type: str, idx: int, r: dict[str, float], extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        d = {"type": ph_type, "idx": idx, "x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"]}
        if extra:
            d.update(extra)
        return d

    if key == "title":
        ctr = ph.get("ctrTitle", (72.0, 167.7, 816.0, 115.8))
        sub = ph.get("subTitle", (144.0, 306.0, 672.0, 138.0))
        return [
            {"type": "ctrTitle", "idx": 0, "x": ctr[0], "y": ctr[1], "w": ctr[2], "h": ctr[3]},
            {"type": "subTitle", "idx": 1, "x": sub[0], "y": sub[1], "w": sub[2], "h": sub[3]},
        ]
    if key == "titleOnly":
        return [ttl]
    if key == "text":
        return [ttl, frame("body", 1, {"x": bx, "y": by, "w": bw, "h": bh})]
    if key == "twoText":
        return [ttl, frame("body", 1, l1), frame("body", 2, r1)]
    if key == "blank":
        return []
    if key == "contentOnly":
        return [frame("obj", 1, {"x": bx, "y": ty, "w": bw, "h": by + bh - ty})]
    if key == "content":
        return [ttl, frame("obj", 1, {"x": bx, "y": by, "w": bw, "h": bh})]
    if key == "twoContent":
        return [ttl, frame("obj", 1, l1), frame("obj", 2, r1)]
    if key == "contentTwoContent":
        return [ttl, frame("obj", 1, l1), frame("obj", 2, rt), frame("obj", 3, rb)]
    if key == "twoContentContent":
        return [ttl, frame("obj", 1, lt), frame("obj", 2, lb), frame("obj", 3, r1)]
    if key == "fourContent":
        return [
            ttl,
            frame("obj", 1, lt),
            frame("obj", 2, rt),
            frame("obj", 3, lb),
            frame("obj", 4, rb),
        ]
    if key == "textContent":
        return [ttl, frame("body", 1, l1), frame("obj", 2, r1)]
    if key == "contentText":
        return [ttl, frame("obj", 1, l1), frame("body", 2, r1)]
    if key == "textTwoContent":
        return [ttl, frame("body", 1, l1), frame("obj", 2, rt), frame("obj", 3, rb)]
    if key == "twoContentText":
        return [ttl, frame("obj", 1, lt), frame("obj", 2, lb), frame("body", 3, r1)]
    if key == "table":
        return [ttl, frame("tbl", 1, {"x": bx, "y": by, "w": bw, "h": bh})]
    if key == "chart":
        return [ttl, frame("chart", 1, {"x": bx, "y": by, "w": bw, "h": bh})]
    if key == "textOverContent":
        return [ttl, frame("body", 1, top), frame("obj", 2, bot)]
    if key == "contentOverText":
        return [ttl, frame("obj", 1, top), frame("body", 2, bot)]
    if key == "vertText":
        return [ttl, frame("body", 1, {"x": bx, "y": by, "w": bw, "h": bh}, extra={"vert": "vert"})]
    if key == "vertTitleText":
        tw_col = bw * 0.22
        return [
            {
                "type": "title",
                "idx": 0,
                "vert": "vert",
                "x": bx + bw - tw_col,
                "y": ty,
                "w": tw_col,
                "h": by + bh - ty,
            },
            frame(
                "body",
                1,
                {"x": bx, "y": ty, "w": bw - tw_col - gap, "h": by + bh - ty},
                extra={"vert": "vert"},
            ),
        ]

    # Default fallback
    return [ttl, frame("body", 1, {"x": bx, "y": by, "w": bw, "h": bh})]


def make_placeholder(fr: dict[str, Any], design: DesignTemplate) -> Shape:
    """Create a Shape instance configured as a placeholder for the given frame and design."""
    ph_type = fr["type"]
    idx = fr.get("idx", 0)
    is_title = ph_type in ("title", "ctrTitle")

    tb = TextBody(
        anchor="ctr" if is_title else "t",
        wrap=True,
        autofit="none" if is_title else "norm",
        paragraphs=[Paragraph(level=0, runs=[])],
        vert=fr.get("vert"),
    )

    return Shape(
        id=f"s_{uuid.uuid4().hex[:8]}",
        type="text",
        name=_ph_name(ph_type, idx),
        geom="rect",
        x=float(fr["x"]),
        y=float(fr["y"]),
        w=float(fr["w"]),
        h=float(fr["h"]),
        rot=0.0,
        fill=Fill.none(),
        line=Line.none(),
        placeholder=PlaceholderInfo(type=ph_type, idx=idx),
        text=tb,
    )
