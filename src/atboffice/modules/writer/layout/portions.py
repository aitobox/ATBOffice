"""Quire line portions layout engine and line height calculation.

Derived from Apache OpenOffice Writer main/sw/source/core/text/porlay.cxx
(SwLineLayout::CalcLine, lcl_HasOnlyBlanks), porrst.cxx (SwBreakPortion,
SwTxtFrm::EmptyHeight) and porfly.cxx (SwFlyCntPortion::SetBase) (Apache License 2.0).

This module implements:
1. Fine-grained paragraph decomposition into line portions (Text, Blank, Tab, Break, Graphic).
2. OpenOffice Writer #i3952: blanks and tabs do not raise a line's height.
3. Microsoft Word paragraph spacing collapse: max(p1.sp.after, p2.sp.before).
4. East Asian document line grid snapping (15.6pt, 18pt pitch) matching Word behavior.
5. Justified text (jc == 'both') with up to 20% inter-word spacing micro-compression.
6. Kinsoku Shori (避头尾规则) for East Asian line breaking.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from atboffice.modules.writer.layout.wrap import FloatBox, calculate_line_segments
from atboffice.modules.writer.models.document import (
    BreakItem,
    Document,
    NoteRefItem,
    Paragraph,
    SymbolItem,
    TabItem,
    TextItem,
)
from atboffice.modules.writer.models.drawing import PictureItem, WrapMode
from atboffice.modules.writer.models.omml import OfficeMathItem
from atboffice.modules.writer.models.properties import (
    SectionProperties,
)
from atboffice.modules.writer.models.styles import resolve_p_props, resolve_r_props

# ---------------------------------------------------------------------------
# Font Line Factors (Single-space line height as multiple of font size)
# Matched to Word / Quire metrics table
# ---------------------------------------------------------------------------

FONT_LINE_FACTORS: dict[str, float] = {
    "calibri": 1.2207,
    "calibri light": 1.2207,
    "cambria": 1.1724,
    "times new roman": 1.149,
    "arial": 1.149,
    "courier new": 1.1328,
    "verdana": 1.2153,
    "georgia": 1.1362,
    "tahoma": 1.2069,
    "trebuchet ms": 1.1611,
    "segoe ui": 1.3301,
    "garamond": 1.1235,
    "comic sans ms": 1.3936,
    "book antiqua": 1.1704,
    "bookman old style": 1.1636,
    "century gothic": 1.2251,
    "palatino linotype": 1.1353,
    "lucida console": 1.0,
    "impact": 1.2197,
    "arial black": 1.41,
    "arial narrow": 1.149,
    "franklin gothic medium": 1.1338,
    "symbol": 1.2275,
    "wingdings": 1.1,
    "aptos": 1.2,
    "helvetica": 1.149,
    # East Asian fonts
    "simsun": 1.17,
    "nsimsun": 1.17,
    "simhei": 1.17,
    "kaiti": 1.17,
    "fangsong": 1.17,
    "microsoft yahei": 1.33,
    "dengxian": 1.25,
    "ms mincho": 1.0,
    "ms pmincho": 1.0,
    "ms gothic": 1.0,
    "ms pgothic": 1.0,
    "ms ui gothic": 1.0,
    "yu mincho": 1.73,
    "yu gothic": 1.73,
    "yu gothic light": 1.73,
    "meiryo": 1.5,
    "malgun gothic": 1.33,
    "batang": 1.15,
    "gulim": 1.15,
    "dotum": 1.15,
}

# Average character width ratios relative to font size for Latin fonts
LATIN_SPACE_EM: dict[str, float] = {
    "times new roman": 0.25,
    "arial": 0.2778,
    "calibri": 0.2261,
    "calibri light": 0.2261,
    "cambria": 0.2197,
    "georgia": 0.2412,
    "verdana": 0.3516,
    "tahoma": 0.3125,
    "courier new": 0.6,
    "garamond": 0.25,
    "book antiqua": 0.25,
    "palatino linotype": 0.25,
    "segoe ui": 0.2744,
    "trebuchet ms": 0.3013,
    "century gothic": 0.2773,
    "helvetica": 0.2778,
    "aptos": 0.2,
}

# East Asian CJK Kinsoku Shori (避头尾规则)
FORBIDDEN_LINE_STARTS: frozenset[str] = frozenset(
    "，。！？、；：）》」』’”·…—～〉】｝］,.!?):;]}>\"'”’»›"
)

FORBIDDEN_LINE_ENDS: frozenset[str] = frozenset('（《「『‘“【〈｛［([{"“‘«‹')

# CJK character detection regex
CJK_REGEX = re.compile(
    r"[\u1100-\u11ff\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef]"
)


def is_cjk_char(ch: str) -> bool:
    """Return True if character belongs to East Asian CJK Unicode blocks."""
    return bool(CJK_REGEX.match(ch))


def get_font_key(name: str) -> str:
    """Normalize font family name to lowercase key."""
    n = str(name or "").replace('"', "").replace("'", "").strip().lower()
    # Chinese aliases
    aliases = {
        "宋体": "simsun",
        "新宋体": "nsimsun",
        "黑体": "simhei",
        "楷体": "kaiti",
        "仿宋": "fangsong",
        "微软雅黑": "microsoft yahei",
        "等线": "dengxian",
        "ｍｓ 明朝": "ms mincho",
        "游明朝": "yu mincho",
        "游ゴシック": "yu gothic",
        "メイリオ": "meiryo",
        "맑은 고딕": "malgun gothic",
    }
    return aliases.get(n, n)


def get_line_factor(font_family: str) -> float:
    """Return line height factor for a given font family."""
    key = get_font_key(font_family)
    return FONT_LINE_FACTORS.get(key, 1.17)


def get_space_em(font_family: str) -> float:
    """Return standard space width as a fraction of font size (em)."""
    key = get_font_key(font_family)
    return LATIN_SPACE_EM.get(key, 0.25)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class PortionType(Enum):
    """Classification of an atomic layout portion."""

    TEXT = "text"
    BLANK = "blank"
    TAB = "tab"
    BREAK = "break"
    GRAPHIC = "graphic"
    MARK = "mark"


@dataclass
class Portion:
    """An atomic inline fragment of content with font metrics and dimensions."""

    type: PortionType
    text: str = ""
    width: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0
    font_size: float = 12.0
    font_family: str = "Times New Roman"
    bold: bool = False
    italic: bool = False
    color: str | None = None
    underline: str = "none"
    highlight: str | None = None
    rtl: bool = False
    counts_for_height: bool = True
    char_offset: int = 0
    length: int = 0
    data: Any = None

    @property
    def height(self) -> float:
        """Return raw physical height of the portion."""
        return self.ascent + self.descent


@dataclass
class LayoutLine:
    """A single wrapped or formatted line in a paragraph."""

    portions: list[Portion] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0
    baseline: float = 0.0
    top: float = 0.0
    bottom: float = 0.0
    is_last_line: bool = False
    is_hard_break: bool = False
    indent_left: float = 0.0
    indent_right: float = 0.0
    extra_space_per_blank: float = 0.0
    is_rtl: bool = False
    jc: str = "left"

    @property
    def baseline_offset(self) -> float:
        """Return baseline vertical offset relative to line.top."""
        return self.baseline - self.top


@dataclass
class ParagraphLayout:
    """Complete layout result for a single paragraph."""

    lines: list[LayoutLine] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    effective_space_before: float = 0.0
    effective_space_after: float = 0.0


# ---------------------------------------------------------------------------
# Measurement & Metric Functions
# ---------------------------------------------------------------------------

_fm_cache: dict[tuple[str, float, bool, bool], Any] = {}


def _get_font_metrics(
    font_family: str, font_size: float, bold: bool = False, italic: bool = False
) -> Any:
    """Retrieve cached QFontMetricsF if a GUI application instance is active."""
    try:
        from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication

        if QGuiApplication.instance() is None:
            return None
        key = (get_font_key(font_family), float(font_size), bool(bold), bool(italic))
        if key in _fm_cache:
            return _fm_cache[key]
        f = QFont(font_family)
        f.setPointSizeF(font_size)
        if bold:
            f.setBold(True)
        if italic:
            f.setItalic(True)
        fm = QFontMetricsF(f)
        _fm_cache[key] = fm
        return fm
    except Exception:
        return None


def measure_char_width(
    ch: str, font_size: float, font_family: str, bold: bool = False, italic: bool = False
) -> float:
    """Deterministic, high-precision character width calculation in points."""
    if is_cjk_char(ch):
        # East Asian CJK full-width glyph is 1.0 em
        return font_size
    if ch in (" ", "\u00a0"):
        return font_size * get_space_em(font_family)
    if ch == "\t":
        # Tabs are handled by tab-stop calculation
        return 0.0
    # Proportional Latin widths
    key = get_font_key(font_family)
    if "courier" in key or "console" in key:
        return font_size * 0.60
    # Standard variable-width Latin approximations
    if ch in "ijlI!|;:'.,":
        return font_size * 0.28
    if ch in "mwMW@#%&":
        return font_size * 0.85
    if ch.isupper() or ch in "0123456789":
        return font_size * 0.58
    return font_size * 0.50


def measure_text_width(
    text: str, font_size: float, font_family: str, bold: bool = False, italic: bool = False
) -> float:
    """Calculate the total layout width of a string in points."""
    if not text:
        return 0.0
    return sum(
        measure_char_width(c, font_size, font_family, bold=bold, italic=italic) for c in text
    )


def compute_font_metrics(
    font_size: float, font_family: str, bold: bool = False, italic: bool = False
) -> tuple[float, float]:
    """Calculate (ascent, descent) in points according to standard typographic ratios."""
    # Standard typographic baseline: ascent ~ 80%, descent ~ 20%
    ascent = round(font_size * 0.80, 2)
    descent = round(font_size * 0.20, 2)
    return ascent, descent


# ---------------------------------------------------------------------------
# Word Spacing Collapse & Line Grid Calculations
# ---------------------------------------------------------------------------


def collapse_paragraph_spacing(
    sp_after_prev: float,
    sp_before_curr: float,
    is_page_top: bool = False,
) -> float:
    """Strict Microsoft Word paragraph spacing collapse rule.

    1. Between adjacent paragraphs, spacing collapses to max(p1.sp.after, p2.sp.before).
    2. At the top of a page or column (or after a page break), space before is dropped to 0.
    """
    if is_page_top:
        return 0.0
    return max(float(sp_after_prev), float(sp_before_curr))


def compute_grid_line_height(
    pitch: float,
    mult: float,
    font_size: float,
    font_family: str,
) -> float:
    """Calculate the line height on an East Asian document line grid (e.g., 15.6pt, 18pt).

    Formula (matches Quire R.gridLine / Word for Mac / Windows):
      natural_line = font_size * line_factor(font)
      needed_pitches = ceil(natural_line / pitch - 0.02)
      effective_pitches = max(1.0, mult, needed_pitches)
      line_height = pitch * effective_pitches
    """
    factor = get_line_factor(font_family)
    natural_line = font_size * factor
    needed = math.ceil((natural_line / pitch) - 0.02)
    effective_pitches = max(1.0, float(mult), float(needed))
    return round(pitch * effective_pitches, 4)


# ---------------------------------------------------------------------------
# Portion Decomposition
# ---------------------------------------------------------------------------


def decompose_paragraph_to_portions(
    p: Paragraph,
    doc: Document | None = None,
) -> list[Portion]:
    """Decompose a Paragraph into atomic portions (Text, Blank, Tab, Break, Graphic)."""
    portions: list[Portion] = []
    d = doc or Document()
    p_pr = resolve_p_props(d, p)
    char_offset = 0

    # Numbering & Bullet Portion Synthesis
    num = getattr(p_pr, "num", None)
    if num is not None and getattr(d, "numbering", None):
        nums_map = d.numbering.get("nums", {})
        num_entry = nums_map.get(str(num.id))
        if num_entry:
            abs_id = num_entry.get("abs")
            abs_entry = d.numbering.get("abs", {}).get(str(abs_id), {})
            levels = abs_entry.get("levels", [])
            lvl_idx = num.lvl if num.lvl is not None else 0
            if 0 <= lvl_idx < len(levels):
                lvl = levels[lvl_idx]
                fmt = lvl.get("fmt", "bullet")
                txt = lvl.get("text", "")
                r_pr = lvl.get("r_pr")
                font_f = r_pr.font if (r_pr and r_pr.font) else "Wingdings"
                font_s = r_pr.sz if (r_pr and r_pr.sz) else 10.0
                color = r_pr.color if (r_pr and r_pr.color) else "#000000"

                if fmt == "bullet":
                    glyph = txt if txt else "•"
                elif fmt == "decimal":
                    start_val = lvl.get("start", 1)
                    glyph = (
                        txt.replace(f"%{lvl_idx + 1}", str(start_val))
                        if txt
                        else f"{start_val}."
                    )
                elif fmt == "lowerLetter":
                    glyph = txt.replace(f"%{lvl_idx+1}", "a") if txt else "a."
                elif fmt == "upperLetter":
                    glyph = txt.replace(f"%{lvl_idx+1}", "A") if txt else "A."
                elif fmt == "lowerRoman":
                    glyph = txt.replace(f"%{lvl_idx+1}", "i") if txt else "i."
                elif fmt == "upperRoman":
                    glyph = txt.replace(f"%{lvl_idx+1}", "I") if txt else "I."
                else:
                    glyph = txt if txt else "•"

                w_glyph = measure_text_width(glyph, font_s, font_f)
                b_ascent, b_descent = compute_font_metrics(font_s, font_f)
                portions.append(
                    Portion(
                        type=PortionType.TEXT,
                        text=glyph,
                        width=w_glyph,
                        ascent=b_ascent,
                        descent=b_descent,
                        font_size=font_s,
                        font_family=font_f,
                        color=color,
                        counts_for_height=True,
                        char_offset=0,
                        length=len(glyph),
                    )
                )
                char_offset += len(glyph)
                suff = lvl.get("suff", "tab")
                if suff == "tab":
                    portions.append(
                        Portion(
                            type=PortionType.TAB,
                            text="\t",
                            width=0.0,
                            ascent=0.0,
                            descent=0.0,
                            font_size=font_s,
                            font_family=font_f,
                            counts_for_height=False,
                            char_offset=char_offset,
                            length=1,
                        )
                    )
                    char_offset += 1
                elif suff == "space":
                    sp_w = measure_text_width(" ", font_s, font_f)
                    portions.append(
                        Portion(
                            type=PortionType.BLANK,
                            text=" ",
                            width=sp_w,
                            ascent=b_ascent,
                            descent=b_descent,
                            font_size=font_s,
                            font_family=font_f,
                            counts_for_height=False,
                            char_offset=char_offset,
                            length=1,
                        )
                    )
                    char_offset += 1

    for item in p.runs:
        r_pr = resolve_r_props(d, p, item)
        font_sz = r_pr.sz
        font_family = r_pr.font

        if isinstance(item, TextItem):
            text = item.text or ""
            if not text:
                continue

            # Split text by newlines and spaces/words/CJK
            lines = text.split("\n")
            for line_idx, line_str in enumerate(lines):
                if line_idx > 0:
                    # Explicit line break within text item
                    portions.append(
                        Portion(
                            type=PortionType.BREAK,
                            text="\n",
                            width=0.0,
                            ascent=0.0,
                            descent=0.0,
                            font_size=font_sz,
                            font_family=font_family,
                            counts_for_height=False,
                            char_offset=char_offset,
                            length=1,
                        )
                    )
                    char_offset += 1

                # Tokenize line_str into words, blanks, and CJK characters
                pos = 0
                while pos < len(line_str):
                    ch = line_str[pos]
                    if ch in (" ", "\u00a0"):
                        # Accumulate consecutive blanks
                        start = pos
                        while pos < len(line_str) and line_str[pos] in (" ", "\u00a0"):
                            pos += 1
                        blanks = line_str[start:pos]
                        w = measure_text_width(
                            blanks, font_sz, font_family, bold=bool(r_pr.b), italic=bool(r_pr.i)
                        )
                        # OpenOffice #i3952: blanks do not count for raising line height
                        portions.append(
                            Portion(
                                type=PortionType.BLANK,
                                text=blanks,
                                width=w,
                                ascent=0.0,
                                descent=0.0,
                                font_size=font_sz,
                                font_family=font_family,
                                bold=bool(r_pr.b),
                                italic=bool(r_pr.i),
                                color=r_pr.color,
                                underline=getattr(r_pr, "u", "none"),
                                highlight=getattr(r_pr, "highlight", None),
                                rtl=bool(getattr(r_pr, "rtl", False)),
                                counts_for_height=False,
                                char_offset=char_offset + start,
                                length=len(blanks),
                            )
                        )
                    elif is_cjk_char(ch):
                        # CJK characters can break individually
                        ascent, descent = compute_font_metrics(
                            font_sz,
                            r_pr.font_ea or font_family,
                            bold=bool(r_pr.b),
                            italic=bool(r_pr.i),
                        )
                        w = font_sz
                        portions.append(
                            Portion(
                                type=PortionType.TEXT,
                                text=ch,
                                width=w,
                                ascent=ascent,
                                descent=descent,
                                font_size=font_sz,
                                font_family=r_pr.font_ea or font_family,
                                bold=bool(r_pr.b),
                                italic=bool(r_pr.i),
                                color=r_pr.color,
                                underline=getattr(r_pr, "u", "none"),
                                highlight=getattr(r_pr, "highlight", None),
                                rtl=bool(getattr(r_pr, "rtl", False)),
                                counts_for_height=True,
                                char_offset=char_offset + pos,
                                length=1,
                            )
                        )
                        pos += 1
                    else:
                        # Latin / non-CJK word
                        start = pos
                        while (
                            pos < len(line_str)
                            and line_str[pos] not in (" ", "\u00a0", "\t")
                            and not is_cjk_char(line_str[pos])
                        ):
                            pos += 1
                        word = line_str[start:pos]
                        w = measure_text_width(
                            word, font_sz, font_family, bold=bool(r_pr.b), italic=bool(r_pr.i)
                        )
                        ascent, descent = compute_font_metrics(
                            font_sz, font_family, bold=bool(r_pr.b), italic=bool(r_pr.i)
                        )
                        portions.append(
                            Portion(
                                type=PortionType.TEXT,
                                text=word,
                                width=w,
                                ascent=ascent,
                                descent=descent,
                                font_size=font_sz,
                                font_family=font_family,
                                bold=bool(r_pr.b),
                                italic=bool(r_pr.i),
                                color=r_pr.color,
                                underline=getattr(r_pr, "u", "none"),
                                highlight=getattr(r_pr, "highlight", None),
                                rtl=bool(getattr(r_pr, "rtl", False)),
                                counts_for_height=True,
                                char_offset=char_offset + start,
                                length=len(word),
                            )
                        )
                char_offset += len(line_str)

        elif isinstance(item, TabItem):
            # Tab portion: does not count for raising line height
            portions.append(
                Portion(
                    type=PortionType.TAB,
                    text="\t",
                    width=0.0,  # Computed during layout based on tab stops
                    ascent=0.0,
                    descent=0.0,
                    font_size=font_sz,
                    font_family=font_family,
                    counts_for_height=False,
                    char_offset=char_offset,
                    length=1,
                )
            )
            char_offset += 1

        elif isinstance(item, BreakItem):
            # Manual line or page break
            portions.append(
                Portion(
                    type=PortionType.BREAK,
                    text="\n",
                    width=0.0,
                    ascent=0.0,
                    descent=0.0,
                    font_size=font_sz,
                    font_family=font_family,
                    counts_for_height=False,
                    char_offset=char_offset,
                    length=1,
                    data=item.break_type,
                )
            )
            char_offset += 1

        elif isinstance(item, SymbolItem):
            char = getattr(item, "char", "") or ""
            sym_font = getattr(item, "font", "") or font_family
            w = measure_char_width(char, font_sz, sym_font)
            ascent, descent = compute_font_metrics(font_sz, sym_font)
            portions.append(
                Portion(
                    type=PortionType.TEXT,
                    text=char,
                    width=w,
                    ascent=ascent,
                    descent=descent,
                    font_size=font_sz,
                    font_family=sym_font,
                    counts_for_height=True,
                    char_offset=char_offset,
                    length=len(char),
                    data=item,
                )
            )
            char_offset += len(char)

        elif isinstance(item, OfficeMathItem):
            from atboffice.modules.writer.layout.math_layout import layout_math_item

            layout_math_item(item, font_sz, font_family)
            portions.append(
                Portion(
                    type=PortionType.GRAPHIC,
                    text="",
                    width=item.width,
                    ascent=item.ascent,
                    descent=item.descent,
                    font_size=font_sz,
                    font_family=font_family,
                    counts_for_height=True,
                    char_offset=char_offset,
                    length=1,
                    data=item,
                )
            )
            char_offset += 1

        elif isinstance(item, PictureItem) or getattr(item, "t", "") in ("picture", "img"):
            float_pr = getattr(item, "float_pr", None)
            is_floating = float_pr is not None and getattr(float_pr, "wrap", None) not in (
                WrapMode.INLINE,
                "inline",
                None,
            )
            if is_floating:
                # Floating anchor: zero width in inline text stream
                portions.append(
                    Portion(
                        type=PortionType.GRAPHIC,
                        text="",
                        width=0.0,
                        ascent=0.0,
                        descent=0.0,
                        font_size=font_sz,
                        font_family=font_family,
                        counts_for_height=False,
                        char_offset=char_offset,
                        length=1,
                        data=item,
                    )
                )
                char_offset += 1
            else:
                w = float(getattr(item, "width", 0.0) or getattr(item, "w", 0.0) or 72.0)
                h = float(getattr(item, "height", 0.0) or getattr(item, "h", 0.0) or 72.0)
                portions.append(
                    Portion(
                        type=PortionType.GRAPHIC,
                        text="",
                        width=w,
                        ascent=h,
                        descent=0.0,
                        font_size=font_sz,
                        font_family=font_family,
                        counts_for_height=True,
                        char_offset=char_offset,
                        length=1,
                        data=item,
                    )
                )
                char_offset += 1

        elif isinstance(item, NoteRefItem):
            ref_str = item.custom_mark or str(item.note_id or "")
            if not ref_str:
                ref_str = "*"
            fn_font_sz = max(6.0, round(font_sz * 0.65, 2))
            w = measure_text_width(
                ref_str, fn_font_sz, font_family, bold=bool(r_pr.b), italic=bool(r_pr.i)
            )
            ascent, descent = compute_font_metrics(
                fn_font_sz, font_family, bold=bool(r_pr.b), italic=bool(r_pr.i)
            )
            shift = round(font_sz * 0.35, 2)
            portions.append(
                Portion(
                    type=PortionType.TEXT,
                    text=ref_str,
                    width=w,
                    ascent=ascent + shift,
                    descent=0.0,
                    font_size=fn_font_sz,
                    font_family=font_family,
                    bold=bool(r_pr.b),
                    italic=bool(r_pr.i),
                    counts_for_height=True,
                    char_offset=char_offset,
                    length=len(ref_str),
                    data=item,
                )
            )
            char_offset += len(ref_str)

        else:
            # Inline graphic, shape, or custom object
            float_pr = getattr(item, "float_pr", None)
            is_floating = float_pr is not None and getattr(float_pr, "wrap", None) not in (
                WrapMode.INLINE,
                "inline",
                None,
            )
            if is_floating:
                # Floating anchor: zero width in inline text stream
                portions.append(
                    Portion(
                        type=PortionType.GRAPHIC,
                        text="",
                        width=0.0,
                        ascent=0.0,
                        descent=0.0,
                        font_size=font_sz,
                        font_family=font_family,
                        counts_for_height=False,
                        char_offset=char_offset,
                        length=1,
                        data=item,
                    )
                )
                char_offset += 1
            else:
                w = getattr(item, "w", 0.0) or getattr(item, "width", 0.0) or 0.0
                h = getattr(item, "h", 0.0) or getattr(item, "height", 0.0) or 0.0
                if w > 0.0 or h > 0.0:
                    portions.append(
                        Portion(
                            type=PortionType.GRAPHIC,
                            text="",
                            width=float(w),
                            ascent=float(h),
                            descent=0.0,
                            font_size=font_sz,
                            font_family=font_family,
                            counts_for_height=True,
                            char_offset=char_offset,
                            length=1,
                            data=item,
                        )
                    )
                    char_offset += 1

    # Empty paragraph or paragraph with no text: provide a Mark portion
    if not portions:
        mark_r_pr = getattr(p, "mark", None) or getattr(p, "r_pr", None)
        mark_sz = getattr(mark_r_pr, "sz", 12.0) if mark_r_pr else 12.0
        mark_font = (
            getattr(mark_r_pr, "font", "Times New Roman") if mark_r_pr else "Times New Roman"
        )
        ascent, descent = compute_font_metrics(mark_sz, mark_font)
        portions.append(
            Portion(
                type=PortionType.MARK,
                text="",
                width=0.0,
                ascent=ascent,
                descent=descent,
                font_size=mark_sz,
                font_family=mark_font,
                counts_for_height=True,
                char_offset=0,
                length=0,
            )
        )

    return portions


# ---------------------------------------------------------------------------
# Paragraph Layout Engine
# ---------------------------------------------------------------------------


def find_next_tab_stop(
    current_x: float,
    left_margin: float,
    tabs: list[Any],
    default_tab_pitch: float = 36.0,
) -> tuple[float, Any]:
    """Find the next tab stop position in points and the tab stop object if any."""
    rel_x = current_x - left_margin
    # Check explicit paragraph tab stops
    for tab in tabs:
        pos = getattr(tab, "pos", None)
        if pos is not None and pos > rel_x + 0.1:
            return left_margin + pos, tab

    # Fall back to default regular tab stops (e.g. 0.5 in = 36 pt)
    next_tab = (math.floor(rel_x / default_tab_pitch) + 1.0) * default_tab_pitch
    return left_margin + next_tab, None


def compute_next_tab_stop(
    current_x: float,
    left_margin: float,
    tabs: list[Any],
    default_tab_pitch: float = 36.0,
) -> float:
    """Find the next tab stop position in points."""
    pos, _ = find_next_tab_stop(current_x, left_margin, tabs, default_tab_pitch)
    return pos


def layout_paragraph(
    p: Paragraph,
    container_width: float,
    section_props: SectionProperties | None = None,
    doc: Document | None = None,
    prev_paragraph: Paragraph | None = None,
    is_page_top: bool = False,
    float_boxes: list[FloatBox] | None = None,
    y_offset: float = 0.0,
    col_left: float = 0.0,
) -> ParagraphLayout:
    """Layout a paragraph into lines with OpenOffice portions and Word typography rules."""
    d = doc or Document()
    p_pr = resolve_p_props(d, p)
    sect = section_props or SectionProperties()
    portions = decompose_paragraph_to_portions(p, d)

    # Indentations
    ind_left = p_pr.ind.left
    ind_right = p_pr.ind.right
    ind_first = p_pr.ind.first_line

    # Inherit indents from numbering level if not explicitly defined
    num = getattr(p_pr, "num", None)
    if num is not None and getattr(d, "numbering", None):
        nums_map = d.numbering.get("nums", {})
        num_entry = nums_map.get(str(num.id))
        if num_entry:
            abs_id = num_entry.get("abs")
            abs_entry = d.numbering.get("abs", {}).get(str(abs_id), {})
            levels = abs_entry.get("levels", [])
            lvl_idx = num.lvl if num.lvl is not None else 0
            if 0 <= lvl_idx < len(levels):
                lvl = levels[lvl_idx]
                lvl_ind = lvl.get("ind", {})
                if ind_left == 0.0 and lvl_ind.get("l") is not None:
                    ind_left = float(lvl_ind["l"])
                if ind_first == 0.0 and lvl_ind.get("fl") is not None:
                    ind_first = float(lvl_ind["fl"])

    first_line_available = max(10.0, container_width - ind_left - ind_right - ind_first)
    subsequent_line_available = max(10.0, container_width - ind_left - ind_right)

    lines: list[LayoutLine] = []
    current_portions: list[Portion] = []
    current_width = 0.0
    line_idx = 0
    cur_line_top = 0.0

    # Paragraph mark metrics for empty lines & picture minimum heights
    mark_r_pr = getattr(p, "mark", None) or getattr(p, "r_pr", None)
    mark_sz = getattr(mark_r_pr, "sz", 12.0) if mark_r_pr else 12.0
    mark_font = getattr(mark_r_pr, "font", "Times New Roman") if mark_r_pr else "Times New Roman"
    mark_ascent, mark_descent = compute_font_metrics(mark_sz, mark_font)
    mark_line_factor = get_line_factor(mark_font)
    mark_natural_height = mark_sz * mark_line_factor

    def get_line_constraints() -> tuple[float, float]:
        nonlocal cur_line_top
        base_avail = first_line_available if line_idx == 0 else subsequent_line_available
        base_indent = ind_left + (ind_first if line_idx == 0 else 0.0)

        if not float_boxes:
            return base_avail, base_indent

        est_h = mark_natural_height or 14.0
        for _ in range(10):
            line_abs_y = y_offset + cur_line_top
            segs = calculate_line_segments(
                col_left=col_left,
                col_right=col_left + container_width,
                y=line_abs_y,
                line_height=est_h,
                float_boxes=float_boxes,
            )
            if not segs:
                overlapping_bottoms = [
                    (fb.y + fb.h + fb.dist.bottom) - y_offset
                    for fb in float_boxes
                    if fb.wrap_mode == WrapMode.TOP_BOTTOM
                    and (
                        line_abs_y + est_h > fb.y - fb.dist.top
                        and line_abs_y < fb.y + fb.h + fb.dist.bottom
                    )
                ]
                if overlapping_bottoms:
                    cur_line_top = max(cur_line_top, max(overlapping_bottoms))
                else:
                    cur_line_top += est_h
            else:
                chosen_seg = max(segs, key=lambda s: s[1] - s[0])
                seg_w = max(10.0, chosen_seg[1] - chosen_seg[0])
                seg_indent = max(0.0, chosen_seg[0] - col_left)
                avail_w = max(10.0, min(base_avail, seg_w))
                indent_l = seg_indent + base_indent
                return avail_w, indent_l

        return base_avail, base_indent

    def target_available_width() -> float:
        w, _ = get_line_constraints()
        return w

    def target_indent_left() -> float:
        _, ind = get_line_constraints()
        return ind

    def finalize_line(is_last: bool, is_hard: bool) -> LayoutLine:
        nonlocal line_idx, cur_line_top
        avail_w, indent_l = get_line_constraints()

        # Trim trailing blank portions from line width calculation
        trimmed_portions = list(current_portions)
        while trimmed_portions and trimmed_portions[-1].type == PortionType.BLANK:
            trimmed_portions.pop()

        actual_content_width = sum(p.width for p in trimmed_portions)

        # Handle Justification (jc == 'both') and Horizontal Alignment (center / right)
        slack = max(0.0, avail_w - actual_content_width)
        extra_per_blank = 0.0
        is_bidi = bool(getattr(p_pr, "bidi", False))
        resolved_jc = "left"
        if p_pr.jc in ("both", "distribute") and not is_last and trimmed_portions:
            resolved_jc = "both"
            blank_portions = [pt for pt in trimmed_portions if pt.type == PortionType.BLANK]
            if blank_portions:
                extra_per_blank = slack / float(len(blank_portions))
                for pt in blank_portions:
                    pt.width += extra_per_blank
                actual_content_width = avail_w
        elif p_pr.jc == "center":
            resolved_jc = "center"
            indent_l += slack / 2.0
        elif p_pr.jc == "right" or (p_pr.jc in ("both", "distribute") and is_last and is_bidi):
            resolved_jc = "right"
            indent_l += slack

        # Line height & baseline calculations
        counting = [pt for pt in trimmed_portions if pt.counts_for_height]
        if not counting:
            # Empty paragraph or only blanks/tabs -> OpenOffice EmptyHeight
            ascent = mark_ascent
            descent = mark_descent
            has_only_pictures = False
        else:
            ascent = max(pt.ascent for pt in counting)
            descent = max(pt.descent for pt in counting)
            has_only_pictures = all(pt.type == PortionType.GRAPHIC for pt in counting)

        # Baseline & line height by line rule
        sp = p_pr.sp
        line_rule = sp.line_rule
        line_mult = sp.line

        if line_rule == "exact":
            height = line_mult
            baseline = ascent
        elif line_rule == "atLeast":
            natural = ascent + descent
            if has_only_pictures:
                natural = max(natural, mark_natural_height)
            height = max(line_mult, natural)
            baseline = ascent
        else:
            # Auto line spacing
            if sect.doc_grid.type in ("lines", "linesAndChars"):
                # East Asian line grid snapping
                dominant_font = counting[0].font_family if counting else mark_font
                max_sz = max((pt.font_size for pt in counting), default=mark_sz)
                pitch = sect.doc_grid.line_pitch
                height = compute_grid_line_height(pitch, line_mult, max_sz, dominant_font)
                natural_content = ascent + descent
                if natural_content > height:
                    grid_steps = max(1, int(math.ceil(natural_content / pitch - 0.02)))
                    height = max(height, grid_steps * pitch)
                natural_line = max_sz * get_line_factor(dominant_font)
                top_padding = max(0.0, (height - natural_line) / 2.0)
                baseline = top_padding + ascent
            else:
                natural = (ascent + descent) * line_mult
                if has_only_pictures:
                    natural = max(natural, mark_natural_height)
                height = natural
                baseline = height if (has_only_pictures and height > ascent) else ascent

        line = LayoutLine(
            portions=current_portions,
            width=actual_content_width,
            height=round(height, 4),
            ascent=ascent,
            descent=descent,
            baseline=round(baseline, 4),
            top=round(cur_line_top, 4),
            bottom=round(cur_line_top + height, 4),
            is_last_line=is_last,
            is_hard_break=is_hard,
            indent_left=indent_l,
            indent_right=ind_right,
            extra_space_per_blank=extra_per_blank,
            is_rtl=bool(getattr(p_pr, "bidi", False)),
            jc=resolved_jc,
        )
        cur_line_top += height
        line_idx += 1
        return line

    # Word wrap & portion packing loop
    idx = 0
    while idx < len(portions):
        pt = portions[idx]

        if pt.type == PortionType.BREAK:
            # Explicit break ends line immediately
            lines.append(finalize_line(is_last=False, is_hard=True))
            current_portions = []
            current_width = 0.0
            idx += 1
            continue

        if pt.type == PortionType.TAB:
            # Tab advance
            cur_x = target_indent_left() + current_width
            if line_idx == 0 and ind_first < 0.0 and cur_x < ind_left:
                next_x = ind_left
                tab_obj = None
            else:
                next_x, tab_obj = find_next_tab_stop(cur_x, target_indent_left(), p_pr.tabs)
            pt.data = tab_obj
            align = getattr(tab_obj, "align", "left") if tab_obj else "left"
            if align == "right":
                rem_w = 0.0
                for look_idx in range(idx + 1, len(portions)):
                    look_pt = portions[look_idx]
                    if look_pt.type in (PortionType.TAB, PortionType.BREAK):
                        break
                    rem_w += look_pt.width
                pt.width = max(0.0, next_x - cur_x - rem_w)
            elif align == "center":
                rem_w = 0.0
                for look_idx in range(idx + 1, len(portions)):
                    look_pt = portions[look_idx]
                    if look_pt.type in (PortionType.TAB, PortionType.BREAK):
                        break
                    rem_w += look_pt.width
                pt.width = max(0.0, next_x - cur_x - (rem_w / 2.0))
            else:
                pt.width = max(0.0, next_x - cur_x)

        avail_w = target_available_width()

        # Check if adding pt overflows the line
        if current_portions and (current_width + pt.width > avail_w):
            # Kinsoku Shori: check if pt starts with forbidden character
            if pt.text and pt.text[0] in FORBIDDEN_LINE_STARTS:
                # Keep on current line with preceding portion to avoid forbidden line start
                current_portions.append(pt)
                current_width += pt.width
                idx += 1
                lines.append(finalize_line(is_last=False, is_hard=False))
                current_portions = []
                current_width = 0.0
                continue

            # Check for up to 20% justification micro-compression
            if p_pr.jc in ("both", "distribute"):
                blank_portions = [
                    p_item for p_item in current_portions if p_item.type == PortionType.BLANK
                ]
                if blank_portions:
                    overflow = (current_width + pt.width) - avail_w
                    total_space_width = sum(b.width for b in blank_portions)
                    max_compression = total_space_width * 0.20
                    if 0.0 < overflow <= max_compression:
                        # Compress spaces and fit onto current line
                        compress_ratio = 1.0 - (overflow / total_space_width)
                        for b in blank_portions:
                            b.width *= compress_ratio
                        current_portions.append(pt)
                        current_width = avail_w
                        idx += 1
                        lines.append(finalize_line(is_last=False, is_hard=False))
                        current_portions = []
                        current_width = 0.0
                        continue

            # Trailing whitespace over margin per Word rules
            if pt.type == PortionType.BLANK:
                all_remaining_blank = all(
                    rem_pt.type == PortionType.BLANK
                    for rem_pt in portions[idx:]
                    if rem_pt.type != PortionType.BREAK
                )
                if all_remaining_blank:
                    # Retain trailing blanks hanging over margin without forcing line wrap
                    current_portions.append(pt)
                    current_width += pt.width
                    idx += 1
                    continue
                else:
                    # Space before wrapped word stays on current line
                    current_portions.append(pt)
                    lines.append(finalize_line(is_last=False, is_hard=False))
                    current_portions = []
                    current_width = 0.0
                    idx += 1
                    continue

            # Keep contiguous non-CJK word portions atomic across run style changes
            roll_back = 0
            if pt.type == PortionType.TEXT and pt.text and not is_cjk_char(pt.text[0]):
                for prev in reversed(current_portions):
                    if (
                        prev.type == PortionType.TEXT
                        and prev.text
                        and not is_cjk_char(prev.text[-1])
                    ):
                        roll_back += 1
                    else:
                        break
            if 0 < roll_back < len(current_portions):
                current_portions = current_portions[:-roll_back]
                lines.append(finalize_line(is_last=False, is_hard=False))
                current_portions = []
                current_width = 0.0
                idx -= roll_back
                continue

            # Wrap to next line
            lines.append(finalize_line(is_last=False, is_hard=False))
            current_portions = []
            current_width = 0.0

            # If wrapped to new line and this portion is just a leading space, drop it
            if pt.type == PortionType.BLANK:
                idx += 1
                continue

        # If a single word on an empty line exceeds available width, break it character-by-character
        if (
            not current_portions
            and pt.width > avail_w
            and len(pt.text) > 1
            and pt.type == PortionType.TEXT
        ):
            sub_chars: list[str] = []
            sub_w = 0.0
            for c in pt.text:
                cw = measure_text_width(
                    c, pt.font_size, pt.font_family, bold=pt.bold, italic=pt.italic
                )
                if sub_chars and (sub_w + cw > avail_w):
                    break
                sub_chars.append(c)
                sub_w += cw
            if not sub_chars:
                sub_chars = [pt.text[0]]
                sub_w = measure_text_width(
                    pt.text[0], pt.font_size, pt.font_family, bold=pt.bold, italic=pt.italic
                )

            head_text = "".join(sub_chars)
            tail_text = pt.text[len(sub_chars) :]

            head_pt = Portion(
                type=pt.type,
                text=head_text,
                width=sub_w,
                ascent=pt.ascent,
                descent=pt.descent,
                font_size=pt.font_size,
                font_family=pt.font_family,
                bold=pt.bold,
                italic=pt.italic,
                color=pt.color,
                underline=pt.underline,
                highlight=pt.highlight,
                rtl=pt.rtl,
                counts_for_height=pt.counts_for_height,
                char_offset=pt.char_offset,
                length=len(head_text),
            )
            tail_pt = Portion(
                type=pt.type,
                text=tail_text,
                width=measure_text_width(
                    tail_text, pt.font_size, pt.font_family, bold=pt.bold, italic=pt.italic
                ),
                ascent=pt.ascent,
                descent=pt.descent,
                font_size=pt.font_size,
                font_family=pt.font_family,
                bold=pt.bold,
                italic=pt.italic,
                color=pt.color,
                underline=pt.underline,
                highlight=pt.highlight,
                rtl=pt.rtl,
                counts_for_height=pt.counts_for_height,
                char_offset=pt.char_offset + len(head_text),
                length=len(tail_text),
            )
            current_portions.append(head_pt)
            current_width += sub_w
            lines.append(finalize_line(is_last=False, is_hard=False))
            current_portions = []
            current_width = 0.0
            portions[idx] = tail_pt
            continue

        # Add portion to current line
        current_portions.append(pt)
        current_width += pt.width
        idx += 1

    # Finalize trailing line
    if current_portions or not lines:
        lines.append(finalize_line(is_last=True, is_hard=False))

    # Calculate vertical positions of lines
    for line in lines:
        line.baseline = line.top + line.baseline

    total_height = max((line.bottom for line in lines), default=0.0)
    total_width = max((line.width for line in lines), default=0.0)

    # Word Spacing Collapse
    prev_after = prev_paragraph.p_pr.sp.after if prev_paragraph else 0.0
    eff_before = collapse_paragraph_spacing(prev_after, p_pr.sp.before, is_page_top=is_page_top)
    eff_after = p_pr.sp.after

    return ParagraphLayout(
        lines=lines,
        width=total_width,
        height=total_height,
        space_before=p_pr.sp.before,
        space_after=p_pr.sp.after,
        effective_space_before=eff_before,
        effective_space_after=eff_after,
    )
