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
    add(
        "BodyText",
        "Body Text",
        "paragraph",
        p_pr=ParagraphProperties(sp=SpacingProperties(after=6.0)),
    )
    add(
        "Quote",
        "Quote",
        "paragraph",
        p_pr=ParagraphProperties(
            ind=IndentProperties(left=36.0, right=36.0),
            sp=SpacingProperties(after=6.0),
        ),
        r_pr=RunProperties(i=True),
    )
    add("PlainText", "Plain Text", "paragraph", r_pr=RunProperties(font="Courier New", sz=10.0))

    # TOC Styles
    for i in range(1, 10):
        add(
            f"TOC{i}",
            f"toc {i}",
            "paragraph",
            based_on="Normal",
            next_s="Normal",
            p_pr=ParagraphProperties(
                ind=IndentProperties(left=(i - 1) * 11.0),
                sp=SpacingProperties(after=2.0),
            ),
        )

    # Lists
    add(
        "ListBullet",
        "List Bullet",
        "paragraph",
        p_pr=ParagraphProperties(num=NumberingRef(id="__bul", lvl=0)),
    )
    add(
        "ListNumber",
        "List Number",
        "paragraph",
        p_pr=ParagraphProperties(num=NumberingRef(id="__num", lvl=0)),
    )

    # Character Styles
    add(
        "DefaultParagraphFont",
        "Default Paragraph Font",
        "character",
        based_on=None,
        is_default=True,
    )
    add(
        "Hyperlink",
        "Hyperlink",
        "character",
        based_on=None,
        r_pr=RunProperties(color="0000FF", u="single"),
    )
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


def merge_p_props(
    base: ParagraphProperties, over: ParagraphProperties | None
) -> ParagraphProperties:
    """Merge override paragraph properties on top of base properties."""
    if not over:
        return copy.deepcopy(base)
    res = copy.deepcopy(base)

    if over.style != "Normal":
        res.style = over.style
    if over.jc != "left" or getattr(over, "jc_explicit", False):
        res.jc = over.jc
        res.jc_explicit = True
    if getattr(over, "bidi", None) is not None:
        res.bidi = over.bidi
    if getattr(over, "contextual", None) is not None:
        res.contextual = over.contextual
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
    if over.ind.left != 0.0 or over.ind.left_explicit:
        res.ind.left = over.ind.left
        res.ind.left_explicit = True
    if over.ind.right != 0.0 or over.ind.right_explicit:
        res.ind.right = over.ind.right
        res.ind.right_explicit = True
    if over.ind.first_line != 0.0 or over.ind.first_line_explicit:
        res.ind.first_line = over.ind.first_line
        res.ind.first_line_explicit = True

    # Spacing
    if over.sp.before != 0.0 or getattr(over.sp, "before_explicit", False):
        res.sp.before = over.sp.before
        res.sp.before_explicit = True
    if over.sp.after != 0.0 or getattr(over.sp, "after_explicit", False):
        res.sp.after = over.sp.after
        res.sp.after_explicit = True
    if over.sp.line != 1.0 or getattr(over.sp, "line_explicit", False):
        res.sp.line = over.sp.line
        res.sp.line_explicit = True
    if over.sp.line_rule != "auto" or getattr(over.sp, "line_rule_explicit", False):
        res.sp.line_rule = over.sp.line_rule
        res.sp.line_rule_explicit = True
    if over.sp.before_auto or getattr(over.sp, "before_auto_explicit", False):
        res.sp.before_auto = over.sp.before_auto
        res.sp.before_auto_explicit = True
    if over.sp.after_auto or getattr(over.sp, "after_auto_explicit", False):
        res.sp.after_auto = over.sp.after_auto
        res.sp.after_auto_explicit = True

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

    # Frame properties (framePr)
    if over.frame_pr is not None:
        if res.frame_pr is None:
            res.frame_pr = copy.deepcopy(over.frame_pr)
        else:
            res.frame_pr.update(copy.deepcopy(over.frame_pr))

    return res


def merge_r_props(base: RunProperties, over: RunProperties | None) -> RunProperties:
    """Merge override run properties on top of base properties."""
    if not over:
        return copy.deepcopy(base)
    res = copy.deepcopy(base)

    if over.style:
        res.style = over.style
    if over.font != "Times New Roman" or over.font_explicit:
        res.font = over.font
    if over.font_ea != "SimSun" or over.font_ea_explicit:
        res.font_ea = over.font_ea
    if over.font_cs != "Times New Roman" or over.font_cs_explicit:
        res.font_cs = over.font_cs
    if over.sz != 12.0 or over.sz_explicit:
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
        res.strike_off = False
    elif over.strike_off:
        res.strike = False
        res.strike_off = True
    if over.dstrike:
        res.dstrike = True
        res.dstrike_off = False
    elif over.dstrike_off:
        res.dstrike = False
        res.dstrike_off = True
    if over.caps:
        res.caps = True
    if over.small_caps:
        res.small_caps = True
    if over.kern is not None:
        res.kern = over.kern
    if over.spacing != 0.0:
        res.spacing = over.spacing
    if getattr(over, "rtl", False):
        res.rtl = True

    return res


def _default_style_id(doc: Any, style_type: str) -> str:
    """Return the document's default style ID for a given style type."""
    styles = getattr(doc, "styles", {}) or {}
    defaults = [
        s
        for s in styles.values()
        if getattr(s, "style_type", "") == style_type and getattr(s, "is_default", False)
    ]
    defaults.sort(key=lambda s: bool(getattr(s, "builtin", True)))
    if defaults:
        return defaults[0].id
    return "Normal" if style_type == "paragraph" else "TableNormal"


def _is_default_para_style(doc: Any, sid: str) -> bool:
    """Return True if sid is absent or matches the document's default paragraph style."""
    styles = getattr(doc, "styles", {}) or {}
    return sid not in styles or sid == _default_style_id(doc, "paragraph")


def _extract_tbl_context(
    context: Any,
) -> tuple[ParagraphProperties | None, RunProperties | None]:
    """Extract optional table-style (p_pr, r_pr) from a layout/style context."""
    if not context:
        return None, None
    if isinstance(context, dict):
        return context.get("tbl_p_pr"), context.get("tbl_r_pr")
    return getattr(context, "tbl_p_pr", None), getattr(context, "tbl_r_pr", None)


def _apply_numbering_indent(
    doc: Any, para: Any, chain: list[Style], base: ParagraphProperties
) -> ParagraphProperties:
    """Merge the list level's w:ind over the styles (the original's dmodel.js D.pProps).

    When the numbering comes from the paragraph style, indents set in the style that brings
    the numbering (or in styles derived from it) still win over the level's.
    """
    direct = getattr(para, "p_pr", None)
    direct_num = getattr(direct, "num", None) if direct is not None else None
    num = direct_num if direct_num is not None else base.num
    if (
        num is None
        or str(getattr(num, "id", "0")) in ("0", "")
        or not getattr(doc, "numbering", None)
    ):
        return base
    from atboffice.modules.writer.layout.portions import num_level_def

    lvl = num_level_def(doc, num.id, num.lvl if num.lvl is not None else 0)
    lvl_ind = lvl.get("ind") if isinstance(lvl, dict) else None
    if not lvl_ind:
        return base
    res = copy.deepcopy(base)
    if lvl_ind.get("l") is not None:
        res.ind.left = float(lvl_ind["l"])
        res.ind.left_explicit = True
    if lvl_ind.get("fl") is not None:
        res.ind.first_line = float(lvl_ind["fl"])
        res.ind.first_line_explicit = True
    if direct_num is None:
        k = max((i for i, s in enumerate(chain) if s.p_pr.num is not None), default=-1)
        if k >= 0:
            style_ind = ParagraphProperties()
            for s in chain[k:]:
                style_ind = merge_p_props(style_ind, ParagraphProperties(ind=s.p_pr.ind))
            res = merge_p_props(res, style_ind)
    return res


def resolve_p_props(doc: Any, para: Any, context: Any = None) -> ParagraphProperties:
    """Resolve full cascading paragraph properties for a paragraph."""
    defaults = getattr(doc, "defaults", {})
    base = copy.deepcopy(defaults.get("p_pr", ParagraphProperties()))

    # Apply style chain with Word / LibreOffice table-style precedence:
    # docDefaults < table style < non-default paragraph style < direct.
    # For the default paragraph style (e.g. Normal), its own properties sit
    # below the table style while inherited ancestor properties still win.
    sid = getattr(para.p_pr, "style", "Normal") or "Normal"
    chain = style_chain(doc, sid)
    tbl_p_pr, _ = _extract_tbl_context(context)
    if tbl_p_pr is not None:
        if _is_default_para_style(doc, sid):
            own = chain[-1].p_pr if chain else None
            if own is not None:
                base = merge_p_props(base, own)
            base = merge_p_props(base, tbl_p_pr)
            if len(chain) > 1:
                anc_merged = ParagraphProperties()
                for anc in chain[:-1]:
                    anc_merged = merge_p_props(anc_merged, anc.p_pr)
                # Only ancestor properties NOT overridden by own still inherit over tbl_p_pr.
                if own is not None:
                    if own.sp.before != 0.0 or getattr(own.sp, "before_explicit", False):
                        anc_merged.sp.before = 0.0
                        anc_merged.sp.before_explicit = False
                    if own.sp.after != 0.0 or getattr(own.sp, "after_explicit", False):
                        anc_merged.sp.after = 0.0
                        anc_merged.sp.after_explicit = False
                    if own.sp.line != 1.0 or getattr(own.sp, "line_explicit", False):
                        anc_merged.sp.line = 1.0
                        anc_merged.sp.line_explicit = False
                    if own.sp.line_rule != "auto" or getattr(own.sp, "line_rule_explicit", False):
                        anc_merged.sp.line_rule = "auto"
                        anc_merged.sp.line_rule_explicit = False
                base = merge_p_props(base, anc_merged)
        else:
            base = merge_p_props(base, tbl_p_pr)
            for s in chain:
                base = merge_p_props(base, s.p_pr)
    else:
        for s in chain:
            base = merge_p_props(base, s.p_pr)

    # Numbering level indents sit between the styles and direct formatting
    base = _apply_numbering_indent(doc, para, chain, base)

    # Direct paragraph formatting
    base = merge_p_props(base, getattr(para, "p_pr", None))
    if getattr(base, "bidi", False) and not getattr(base, "jc_explicit", False):
        base.jc = "right"
    return base


def resolve_r_props(doc: Any, para: Any, item: Any = None, context: Any = None) -> RunProperties:
    """Resolve full cascading run properties for an inline item or paragraph mark."""
    defaults = getattr(doc, "defaults", {})
    base = copy.deepcopy(defaults.get("r_pr", RunProperties()))

    # Apply table style and paragraph style chain run properties
    sid = getattr(para.p_pr, "style", "Normal") or "Normal"
    chain = style_chain(doc, sid)
    _, tbl_r_pr = _extract_tbl_context(context)
    if tbl_r_pr is not None:
        base = merge_r_props(base, tbl_r_pr)
        for s in chain:
            base = merge_r_props(base, s.r_pr)
        if _is_default_para_style(doc, sid) and (tbl_r_pr.sz != 12.0 or tbl_r_pr.sz_explicit):
            base.sz = tbl_r_pr.sz
    else:
        for s in chain:
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
