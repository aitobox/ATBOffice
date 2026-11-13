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
from atboffice.utils.font_metrics import (
    compute_font_metrics as calibrated_font_metrics,
)
from atboffice.utils.font_metrics import (
    get_line_factor as calibrated_line_factor,
)
from atboffice.utils.font_metrics import (
    get_space_em as calibrated_space_em,
)
from atboffice.utils.font_metrics import (
    normalize_font_key,
)

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
    return normalize_font_key(name)


def get_line_factor(font_family: str) -> float:
    """Return line height factor for a given font family."""
    return calibrated_line_factor(font_family)


def get_space_em(font_family: str) -> float:
    """Return standard space width as a fraction of font size (em)."""
    return calibrated_space_em(font_family)


def map_symbol_char(ch: str, font: str = "") -> str:
    """Map Symbol, Wingdings, and private-use bullet glyphs to standard Unicode characters."""
    if not ch:
        return ""
    f = str(font or "").lower()
    code = ord(ch[0]) & 0xFF

    # Wingdings 2
    if "wingdings" in f and "2" in f:
        if 0x96 <= code <= 0x9D:
            return "●"
        if 0x9E <= code <= 0xA5:
            return "■"
        if 0xA6 <= code <= 0xAD:
            return "◆"
        w2_map = {0x50: "✓", 0x4F: "✗", 0x51: "☒", 0x52: "☑", 0xE9: "★", 0xEA: "★"}
        return w2_map.get(code, "•")

    # Wingdings 3
    if "wingdings" in f and "3" in f:
        w3_map = {
            0x7D: "►", 0x84: "►", 0x75: "►", 0x71: "◄",
            0x70: "▲", 0x72: "▼", 0xC6: "➔", 0xC7: "⬅",
        }
        return w3_map.get(code, "▸")

    # Wingdings (standard)
    if f.startswith("wingdings"):
        w_map = {
            "l": "●", "n": "■", "q": "❑", "u": "◆", "v": "❖", "Ø": "➢", "ü": "✓", "§": "▪",
            "o": "❍", "p": "□", "w": "⬥", "Ü": "➢", "à": "➔", "è": "➜", "Þ": "➝", "ð": "⇨",
            "ª": "✦", "¨": "◻",
            "\uF06E": "■", "\uF06C": "●", "\uF075": "◆",
            "\uF0FC": "✓", "\uF0D8": "➢", "\uF0A7": "▪",
            "\uF04A": "☺", "\uF049": "☹", "\uF0B2": "❖",
        }
        if ch in w_map:
            return w_map[ch]
        c_ascii = chr(code)
        if c_ascii in w_map:
            return w_map[c_ascii]
        return "•"

    # Symbol
    if "symbol" in f:
        sym_map = {"·": "•", "\uF0B7": "•", "Þ": "⇒", "®": "→", "¾": "—"}
        if ch in sym_map:
            return sym_map[ch]
        c_ascii = chr(code)
        if c_ascii in sym_map:
            return sym_map[c_ascii]
        if 0xF000 <= ord(ch[0]) <= 0xF0FF:
            return "•"
        return ch

    # General private-use area characters often used for bullets
    if ch in ("", ""):
        return "•"
    if 0xF000 <= ord(ch[0]) <= 0xF0FF:
        p_map = {
            "\uF06E": "■", "\uF06C": "●", "\uF075": "◆",
            "\uF0FC": "✓", "\uF0D8": "➢", "\uF0A7": "▪",
            "\uF0B7": "•", "\uF04A": "☺", "\uF049": "☹", "\uF0B2": "❖",
        }
        return p_map.get(ch, "•")

    return ch


def num_def(doc: Any, num_id: str | int) -> dict[str, Any] | None:
    """Lookup concrete num and abstractNum definitions."""
    numbering = getattr(doc, "numbering", {}) or {}
    nums = numbering.get("nums", {})
    entry = nums.get(str(num_id))
    if not entry:
        return None
    abs_id = entry.get("abs")
    abs_entry = numbering.get("abs", {}).get(str(abs_id))
    if not abs_entry:
        return None
    return {"num": entry, "abs": abs_entry}


def num_level_def(doc: Any, num_id: str | int, lvl: int) -> dict[str, Any]:
    """Retrieve level definition, applying overrides if present."""
    d = num_def(doc, num_id)
    if not d:
        return {}
    ov_map = d["num"].get("ov", {}) or {}
    ov = ov_map.get(lvl) if lvl in ov_map else ov_map.get(str(lvl))
    levels = d["abs"].get("levels", [])
    base = levels[lvl] if (0 <= lvl < len(levels)) else (levels[-1] if levels else {})
    if not isinstance(base, dict):
        base = {}
    if ov and isinstance(ov, dict) and "lvl" in ov:
        return ov["lvl"]
    if ov and isinstance(ov, dict):
        merged = dict(base)
        for k in ("start", "fmt", "text"):
            if k in ov and ov[k] is not None:
                merged[k] = ov[k]
        return merged
    return base


def compute_lists(doc: Any, stories: list[Any] | None = None) -> dict[int, dict[str, Any]]:
    """Walk paragraphs in reading order and compute list labels and counters.

    Matches the reference implementation in Quire (dmodel.js:562-616).
    Updates each paragraph's `label` attribute and returns a dict mapping
    paragraph.id to label metadata.
    """
    from atboffice.modules.writer.layout.pagination import format_number
    from atboffice.modules.writer.models.document import Paragraph, plen
    from atboffice.modules.writer.models.styles import resolve_p_props

    labels: dict[int, dict[str, Any]] = {}
    counters: dict[str, list[int | None]] = {}  # absId -> int[9]
    seen_num: set[str] = set()

    def visit(p: Paragraph) -> None:
        p_pr = resolve_p_props(doc, p)
        num = getattr(p_pr, "num", None)
        if num is None or getattr(num, "id", None) is None or str(num.id) in ("0", ""):
            p.label = ""
            return

        # Word neither shows nor counts a number on an empty paragraph that only
        # carries a section break
        if getattr(p, "sect", None) is not None and plen(p) == 0:
            p.label = ""
            return

        definition = num_def(doc, num.id)
        if not definition or not definition.get("abs"):
            p.label = ""
            return

        raw_lvl = getattr(num, "lvl", 0)
        lvl = max(0, min(int(raw_lvl if raw_lvl is not None else 0), 8))
        abs_id = str(definition["num"].get("abs", ""))

        if abs_id not in counters:
            counters[abs_id] = [None] * 9
        c = counters[abs_id]

        if str(num.id) not in seen_num:
            seen_num.add(str(num.id))
            ov = definition["num"].get("ov", {}) or {}
            for k, val in ov.items():
                if val and isinstance(val, dict) and val.get("start") is not None:
                    try:
                        k_int = int(k)
                        if 0 <= k_int < 9:
                            c[k_int] = None
                            for j in range(k_int + 1, 9):
                                c[j] = None
                    except (ValueError, TypeError):
                        pass

        lv_def = num_level_def(doc, num.id, lvl)

        def start_of(l_idx: int) -> int:
            ov = definition["num"].get("ov", {}) or {}
            ov_val = ov.get(l_idx) or ov.get(str(l_idx))
            if ov_val and isinstance(ov_val, dict) and ov_val.get("start") is not None:
                return int(ov_val["start"])
            d_l = num_level_def(doc, num.id, l_idx)
            if d_l and d_l.get("start") is not None:
                return int(d_l["start"])
            return 1

        for j in range(lvl):
            if c[j] is None:
                c[j] = start_of(j)

        c[lvl] = start_of(lvl) if c[lvl] is None else (c[lvl] + 1)

        for j in range(lvl + 1, 9):
            d_j = num_level_def(doc, num.id, j)
            restart = d_j.get("restart") if d_j else None
            if not d_j or restart is None or restart > lvl:
                c[j] = None

        pic_bullet = lv_def.get("pic_bullet")
        fmt = lv_def.get("fmt", "decimal")
        r_pr = lv_def.get("r_pr")
        font_name = getattr(r_pr, "font", None) if r_pr else None

        if pic_bullet:
            text = ""
        elif fmt == "bullet":
            raw_text = lv_def.get("text", "•") or "•"
            text = map_symbol_char(raw_text, font_name or "Symbol")
        else:
            raw_pattern = str(
                lv_def.get("text") if lv_def.get("text") is not None else f"%{lvl + 1}."
            )

            def repl(m: re.Match[str]) -> str:
                digit = int(m.group(1))
                k = digit - 1
                if k > lvl or k < 0:
                    return ""
                ld = lv_def if k == lvl else num_level_def(doc, num.id, k)
                is_lgl = bool(lv_def.get("is_lgl"))
                sub_fmt = "decimal" if (is_lgl and k < lvl) else ld.get("fmt", "decimal")
                val = c[k] if c[k] is not None else start_of(k)
                return format_number(val, sub_fmt)

            text = re.sub(r"%(\d)", repl, raw_pattern)
            # Remove any trailing unmatched percent tokens
            text = re.sub(r"%\d+", "", text)
            text = text.replace("%", "")

        p.label = text
        labels[p.id] = {
            "text": text,
            "lv": lv_def,
            "num_id": str(num.id),
            "lvl": lvl,
            "value": c[lvl],
            "pic_bullet": pic_bullet,
        }

    def walk_blocks(blocks: list[Any]) -> None:
        for b in blocks:
            if isinstance(b, Paragraph):
                visit(b)
            elif hasattr(b, "rows"):
                for r in getattr(b, "rows", []):
                    for cell in getattr(r, "cells", []):
                        walk_blocks(getattr(cell, "blocks", []))

    walk_blocks(getattr(getattr(doc, "main", None), "blocks", []))
    if stories:
        for s in stories:
            walk_blocks(getattr(s, "blocks", []))

    return labels


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
    underline: str | None = None
    highlight: str | None = None
    strikethrough: bool = False
    dstrike: bool = False
    caps: bool = False
    small_caps: bool = False
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
    """Calculate (ascent, descent) in points using calibrated font parameters."""
    return calibrated_font_metrics(font_size, font_family, bold=bold, italic=italic)


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


def _norm_underline(r_pr: Any) -> str | None:
    """Return normalised underline style string or None when no underline."""
    u = getattr(r_pr, "u", None)
    if not u or u == "none":
        return None
    return u


def decompose_paragraph_to_portions(
    p: Paragraph,
    doc: Document | None = None,
) -> list[Portion]:
    """Decompose a Paragraph into atomic portions (Text, Blank, Tab, Break, Graphic)."""
    portions: list[Portion] = []
    d = doc or Document()
    p_pr = resolve_p_props(d, p)
    char_offset = 0
    # Sequential fallback counter for footnote/endnote references whose note_id is "0"
    _fn_seq: list[int] = [0]

    # Numbering & Bullet Portion Synthesis
    num = getattr(p_pr, "num", None)
    if (
        num is not None
        and getattr(d, "numbering", None)
        and str(getattr(num, "id", "0")) not in ("0", "")
    ):
        if not getattr(p, "label", "") and not getattr(p, "_lists_checked", False):
            compute_lists(d)
            p._lists_checked = True

        definition = num_def(d, num.id)
        if definition:
            lvl_idx = num.lvl if num.lvl is not None else 0
            lvl = num_level_def(d, num.id, lvl_idx)
            pic_bullet = lvl.get("pic_bullet")
            r_pr = lvl.get("r_pr")
            font_f = (
                r_pr.font
                if (r_pr and getattr(r_pr, "font", None))
                else ("Symbol" if lvl.get("fmt") == "bullet" else "Times New Roman")
            )
            font_s = r_pr.sz if (r_pr and getattr(r_pr, "sz", None)) else 10.0
            color = r_pr.color if (r_pr and getattr(r_pr, "color", None)) else "#000000"

            # 1. Picture Bullet
            if pic_bullet and pic_bullet.get("image_part"):
                w_pt = float(pic_bullet.get("width", 11.25))
                h_pt = float(pic_bullet.get("height", 11.25))
                pic_item = PictureItem(
                    width=w_pt,
                    height=h_pt,
                    image_part=pic_bullet["image_part"],
                )
                portions.append(
                    Portion(
                        type=PortionType.GRAPHIC,
                        text="",
                        width=w_pt,
                        ascent=h_pt,
                        descent=0.0,
                        font_size=font_s,
                        font_family=font_f,
                        color=color,
                        counts_for_height=True,
                        char_offset=0,
                        length=1,
                        data=pic_item,
                    )
                )
                char_offset += 1
            elif p.label:
                glyph = p.label
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

            # Suffix tab or space
            if pic_bullet or p.label:
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
                    b_ascent, b_descent = compute_font_metrics(font_s, font_f)
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
                                underline=_norm_underline(r_pr),
                                strikethrough=bool(getattr(r_pr, "strike", False)),
                                dstrike=bool(getattr(r_pr, "dstrike", False)),
                                caps=bool(getattr(r_pr, "caps", False)),
                                small_caps=bool(getattr(r_pr, "small_caps", False)),
                                highlight=getattr(r_pr, "highlight", None),
                                rtl=bool(getattr(r_pr, "rtl", False)),
                                counts_for_height=False,
                                char_offset=char_offset + start,
                                length=len(blanks),
                            )
                        )
                    elif is_cjk_char(ch):
                        # CJK characters can break individually
                        _cjk_font_sz = font_sz
                        if getattr(r_pr, "small_caps", False):
                            _cjk_font_sz = round(font_sz * 0.8, 2)
                        ascent, descent = compute_font_metrics(
                            _cjk_font_sz,
                            r_pr.font_ea or font_family,
                            bold=bool(r_pr.b),
                            italic=bool(r_pr.i),
                        )
                        w = _cjk_font_sz
                        _is_upper = getattr(r_pr, "caps", False) or getattr(
                            r_pr, "small_caps", False
                        )
                        _cjk_ch = ch.upper() if _is_upper else ch
                        portions.append(
                            Portion(
                                type=PortionType.TEXT,
                                text=_cjk_ch,
                                width=w,
                                ascent=ascent,
                                descent=descent,
                                font_size=_cjk_font_sz,
                                font_family=r_pr.font_ea or font_family,
                                bold=bool(r_pr.b),
                                italic=bool(r_pr.i),
                                color=r_pr.color,
                                underline=_norm_underline(r_pr),
                                strikethrough=bool(getattr(r_pr, "strike", False)),
                                dstrike=bool(getattr(r_pr, "dstrike", False)),
                                caps=bool(getattr(r_pr, "caps", False)),
                                small_caps=bool(getattr(r_pr, "small_caps", False)),
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
                        # Apply caps / small_caps: uppercase the display text only
                        _latin_caps = bool(getattr(r_pr, "caps", False))
                        _latin_small_caps = bool(getattr(r_pr, "small_caps", False))
                        _latin_font_sz = font_sz
                        display_word = word
                        if _latin_caps or _latin_small_caps:
                            display_word = word.upper()
                        if _latin_small_caps:
                            _latin_font_sz = round(font_sz * 0.8, 2)
                        w = measure_text_width(
                            display_word,
                            _latin_font_sz,
                            font_family,
                            bold=bool(r_pr.b),
                            italic=bool(r_pr.i),
                        )
                        ascent, descent = compute_font_metrics(
                            _latin_font_sz, font_family, bold=bool(r_pr.b), italic=bool(r_pr.i)
                        )
                        portions.append(
                            Portion(
                                type=PortionType.TEXT,
                                text=display_word,
                                width=w,
                                ascent=ascent,
                                descent=descent,
                                font_size=_latin_font_sz,
                                font_family=font_family,
                                bold=bool(r_pr.b),
                                italic=bool(r_pr.i),
                                color=r_pr.color,
                                underline=_norm_underline(r_pr),
                                strikethrough=bool(getattr(r_pr, "strike", False)),
                                dstrike=bool(getattr(r_pr, "dstrike", False)),
                                caps=_latin_caps,
                                small_caps=_latin_small_caps,
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
            # Determine display text for the footnote/endnote reference mark.
            # Priority: custom_mark > valid non-zero note_id > sequential counter
            if item.custom_mark:
                ref_str = item.custom_mark
            elif item.note_id and str(item.note_id) not in ("0", ""):
                ref_str = str(item.note_id)
            else:
                # Fallback: use a sequential counter tracked across this paragraph
                _fn_seq[0] += 1
                ref_str = str(_fn_seq[0])
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
    if (
        num is not None
        and getattr(d, "numbering", None)
        and str(getattr(num, "id", "0")) not in ("0", "")
    ):
        lvl_idx = num.lvl if num.lvl is not None else 0
        lvl = num_level_def(d, num.id, lvl_idx)
        lvl_ind = lvl.get("ind", {}) if isinstance(lvl, dict) else {}
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
            half_leading = max(0.0, (height - (ascent + descent)) / 2.0)
            baseline = ascent + half_leading
        else:
            # Auto line spacing
            if (
                sect.doc_grid.type in ("lines", "linesAndChars", "snapToChars")
                and sect.doc_grid.line_pitch > 0
            ):
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
                dominant_font = counting[0].font_family if counting else mark_font
                dominant_sz = counting[0].font_size if counting else mark_sz
                factor = get_line_factor(dominant_font)
                natural_font_line = dominant_sz * factor
                content_h = ascent + descent
                single_h = max(content_h, natural_font_line)
                natural = single_h * line_mult
                if has_only_pictures:
                    natural = max(natural, mark_natural_height)
                height = natural
                half_leading = max(0.0, (height - (ascent + descent)) / 2.0)
                baseline = (
                    height if (has_only_pictures and height > ascent) else (ascent + half_leading)
                )

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
                strikethrough=pt.strikethrough,
                dstrike=pt.dstrike,
                caps=pt.caps,
                small_caps=pt.small_caps,
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
                strikethrough=pt.strikethrough,
                dstrike=pt.dstrike,
                caps=pt.caps,
                small_caps=pt.small_caps,
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
