"""Word 2003 Built-in styles and cascade resolution engine for Quire document model."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.writer.models.properties import (
    IndentProperties,
    NumberingRef,
    ParagraphProperties,
    RunProperties,
    SpacingProperties,
    TabStop,
)


@dataclass
class Style:
    """Style definition (paragraph, character, table, or numbering)."""

    id: str
    name: str
    style_type: str = "paragraph"  # "paragraph", "character", "table", "numbering"
    based_on: str | None = None
    next_style: str | None = None
    p_pr: ParagraphProperties = field(default_factory=ParagraphProperties)
    r_pr: RunProperties = field(default_factory=RunProperties)
    tbl_pr: dict[str, Any] = field(default_factory=dict)
    tc_pr: dict[str, Any] = field(default_factory=dict)
    builtin: bool = True
    is_default: bool = False


def builtin_styles() -> dict[str, Style]:
    """Return dictionary of standard built-in Word 2003 styles."""
    styles: dict[str, Style] = {}

    def add(
        s_id: str,
        name: str,
        s_type: str = "paragraph",
        based_on: str | None = None,
        next_s: str | None = None,
        p_pr: ParagraphProperties | None = None,
        r_pr: RunProperties | None = None,
        is_default: bool = False,
    ) -> Style:
        if s_type == "paragraph" and based_on is None and s_id != "Normal":
            based_on = "Normal"
        st = Style(
            id=s_id,
            name=name,
            style_type=s_type,
            based_on=based_on,
            next_style=next_s,
            p_pr=p_pr or ParagraphProperties(),
            r_pr=r_pr or RunProperties(),
            builtin=True,
            is_default=is_default,
        )
        styles[s_id] = st
        return st

    # Paragraph Styles
    add("Normal", "Normal", "paragraph", based_on=None, is_default=True)
    add(
        "Heading1",
        "heading 1",
        "paragraph",
        based_on="Normal",
        next_s="Normal",
        p_pr=ParagraphProperties(
            keep_next=True,
            sp=SpacingProperties(before=12.0, after=3.0),
            outline_level=0,
        ),
        r_pr=RunProperties(font="Arial", b=True, sz=16.0, kern=16.0),
    )
    add(
        "Heading2",
        "heading 2",
        "paragraph",
        based_on="Normal",
        next_s="Normal",
        p_pr=ParagraphProperties(
            keep_next=True,
            sp=SpacingProperties(before=12.0, after=3.0),
            outline_level=1,
        ),
        r_pr=RunProperties(font="Arial", b=True, i=True, sz=14.0),
    )
    add(
        "Heading3",
        "heading 3",
        "paragraph",
        based_on="Normal",
        next_s="Normal",
        p_pr=ParagraphProperties(
            keep_next=True,
            sp=SpacingProperties(before=12.0, after=3.0),
            outline_level=2,
        ),
        r_pr=RunProperties(font="Arial", b=True, sz=13.0),
    )
    for i in range(4, 10):
        add(
            f"Heading{i}",
            f"heading {i}",
            "paragraph",
            based_on="Normal",
            next_s="Normal",
            p_pr=ParagraphProperties(
                keep_next=True,
                sp=SpacingProperties(before=12.0, after=3.0),
                outline_level=i - 1,
            ),
            r_pr=RunProperties(font="Arial", b=True, sz=12.0),
        )

    add(
        "Title",
        "Title",
        "paragraph",
        based_on="Normal",
        next_s="Normal",
        p_pr=ParagraphProperties(
            jc="center",
            sp=SpacingProperties(before=12.0, after=3.0),
            outline_level=0,
        ),
        r_pr=RunProperties(font="Arial", b=True, sz=16.0, kern=14.0),
    )
    add(
        "Subtitle",
        "Subtitle",
        "paragraph",
        based_on="Normal",
        next_s="Normal",
        p_pr=ParagraphProperties(jc="center", sp=SpacingProperties(after=3.0), outline_level=1),
        r_pr=RunProperties(font="Arial"),
    )
    add("BodyText", "Body Text", "paragraph", p_pr=ParagraphProperties(sp=SpacingProperties(after=6.0)))
    add(
        "Quote",
        "Quote",
        "paragraph",
        p_pr=ParagraphProperties(ind=IndentProperties(left=36.0, right=36.0), sp=SpacingProperties(after=6.0)),
        r_pr=RunProperties(i=True),
    )
    add("PlainText", "Plain Text", "paragraph", r_pr=RunProperties(font="Courier New", sz=10.0))

    # Lists
    add("ListBullet", "List Bullet", "paragraph", p_pr=ParagraphProperties(num=NumberingRef(id="__bul", lvl=0)))
    add("ListNumber", "List Number", "paragraph", p_pr=ParagraphProperties(num=NumberingRef(id="__num", lvl=0)))

    # Character Styles
    add("DefaultParagraphFont", "Default Paragraph Font", "character", based_on=None, is_default=True)
    add("Hyperlink", "Hyperlink", "character", based_on=None, r_pr=RunProperties(color="0000FF", u="single"))
    add("Strong", "Strong", "character", based_on=None, r_pr=RunProperties(b=True))
    add("Emphasis", "Emphasis", "character", based_on=None, r_pr=RunProperties(i=True))

    # Table Styles
    add("TableNormal", "Normal Table", "table", based_on=None, is_default=True)
    add("TableGrid", "Table Grid", "table", based_on="TableNormal")

    return styles


def style_chain(doc: Any, style_id: str) -> list[Style]:
    """Ascend based_on hierarchy and return style list from root ancestor to target style."""
    chain: list[Style] = []
    seen: set[str] = set()
    styles = getattr(doc, "styles", {})
    cur_id: str | None = style_id
    while cur_id and cur_id in styles and cur_id not in seen:
        s = styles[cur_id]
        chain.insert(0, s)
        seen.add(cur_id)
        cur_id = s.based_on
    return chain


def merge_p_props(base: ParagraphProperties, over: ParagraphProperties | None) -> ParagraphProperties:
    """Merge override paragraph properties on top of base properties."""
    if not over:
        return copy.deepcopy(base)
    res = copy.deepcopy(base)

    if over.style != "Normal":
        res.style = over.style
    if over.jc != "left":
        res.jc = over.jc
    if over.keep_next:
        res.keep_next = True
    if over.keep_lines:
        res.keep_lines = True
    if over.page_break_before:
        res.page_break_before = True
    if not over.widow_control:
        res.widow_control = False
    if over.outline_level is not None:
        res.outline_level = over.outline_level

    # Indent
    if over.ind.left != 0.0:
        res.ind.left = over.ind.left
    if over.ind.right != 0.0:
        res.ind.right = over.ind.right
    if over.ind.first_line != 0.0:
        res.ind.first_line = over.ind.first_line

    # Spacing
    if over.sp.before != 0.0:
        res.sp.before = over.sp.before
    if over.sp.after != 0.0:
        res.sp.after = over.sp.after
    if over.sp.line != 1.0:
        res.sp.line = over.sp.line
    if over.sp.line_rule != "auto":
        res.sp.line_rule = over.sp.line_rule

    # Tabs
    if over.tabs:
        # Merge tabs by position
        tab_map = {t.pos: t for t in res.tabs}
        for t in over.tabs:
            tab_map[t.pos] = t
        res.tabs = sorted(tab_map.values(), key=lambda x: x.pos)

    # Numbering
    if over.num is not None:
        res.num = copy.deepcopy(over.num)

    return res


def merge_r_props(base: RunProperties, over: RunProperties | None) -> RunProperties:
    """Merge override run properties on top of base properties."""
    if not over:
        return copy.deepcopy(base)
    res = copy.deepcopy(base)

    if over.style:
        res.style = over.style
    if over.font != "Times New Roman":
        res.font = over.font
    if over.font_ea != "SimSun":
        res.font_ea = over.font_ea
    if over.sz != 12.0:
        res.sz = over.sz
    if over.sz_ea is not None:
        res.sz_ea = over.sz_ea
    if over.b:
        res.b = True
    if over.i:
        res.i = True
    if over.u != "none":
        res.u = over.u
    if over.color != "auto":
        res.color = over.color
    if over.vert != "baseline":
        res.vert = over.vert
    if over.highlight is not None:
        res.highlight = over.highlight
    if over.strike:
        res.strike = True
    if over.dstrike:
        res.dstrike = True
    if over.caps:
        res.caps = True
    if over.small_caps:
        res.small_caps = True
    if over.kern is not None:
        res.kern = over.kern
    if over.spacing != 0.0:
        res.spacing = over.spacing

    return res


def resolve_p_props(doc: Any, para: Any, context: Any = None) -> ParagraphProperties:
    """Resolve full cascading paragraph properties for a paragraph."""
    defaults = getattr(doc, "defaults", {})
    base = copy.deepcopy(defaults.get("p_pr", ParagraphProperties()))

    # Apply style chain
    sid = getattr(para.p_pr, "style", "Normal") or "Normal"
    for s in style_chain(doc, sid):
        base = merge_p_props(base, s.p_pr)

    # Direct paragraph formatting
    base = merge_p_props(base, getattr(para, "p_pr", None))
    return base


def resolve_r_props(doc: Any, para: Any, item: Any = None, context: Any = None) -> RunProperties:
    """Resolve full cascading run properties for an inline item or paragraph mark."""
    defaults = getattr(doc, "defaults", {})
    base = copy.deepcopy(defaults.get("r_pr", RunProperties()))

    # Apply paragraph style chain run properties
    sid = getattr(para.p_pr, "style", "Normal") or "Normal"
    for s in style_chain(doc, sid):
        base = merge_r_props(base, s.r_pr)

    rp = item.r_pr if item and hasattr(item, "r_pr") else getattr(para, "r_pr", None)

    # Apply character style chain if specified
    if rp and getattr(rp, "style", None):
        for cs in style_chain(doc, rp.style):
            if cs.style_type == "character":
                base = merge_r_props(base, cs.r_pr)

    # Direct run formatting
    if rp:
        base = merge_r_props(base, rp)

    return base
