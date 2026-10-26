"""Typography, dimensions, and formatting property models for Quire document model."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Standard Paper Sizes in Points (width, height)
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "Executive": (522.0, 756.0),
    "A4": (595.3, 841.9),
    "A5": (419.55, 595.3),
    "A3": (841.9, 1190.55),
    "B5": (515.9, 728.5),
    "Tabloid": (792.0, 1224.0),
    "Statement": (396.0, 612.0),
    "Envelope #10": (684.0, 297.0),
    "Envelope DL": (623.6, 311.8),
    "Envelope C5": (649.15, 459.2),
    "Envelope Monarch": (540.0, 279.0),
}


def pt_to_dxa(pt: float | int) -> int:
    """Convert points to twips (1/20th of a point)."""
    return round(float(pt) * 20.0)


def dxa_to_pt(dxa: float | int) -> float:
    """Convert twips to points."""
    return float(dxa) / 20.0


def parse_length(s: str | float | int, default_unit: str = "in") -> float | None:
    """Parse a length string (e.g., '72pt', '1in', '2.54cm', '25.4mm') into points."""
    if isinstance(s, (int, float)):
        return float(s)
    match = re.search(
        r"(-?\d*\.?\d+)\s*(cm|mm|pt|pi|in|\"|li|line|lines)?",
        str(s).strip(),
        re.IGNORECASE,
    )
    if not match:
        return None
    val = float(match.group(1))
    unit = (match.group(2) or default_unit).lower()
    factors = {
        "cm": 28.3465,
        "mm": 2.83465,
        "pt": 1.0,
        "pi": 12.0,
        "in": 72.0,
        '"': 72.0,
        "li": 12.0,
        "line": 12.0,
        "lines": 12.0,
    }
    return val * factors.get(unit, 72.0)


def format_length(pt: float | int, unit: str = "in") -> str:
    """Format points into a readable string with unit."""
    val = float(pt)
    unit = unit.lower()
    if unit == "cm":
        return f"{round(val / 28.3465, 2)} cm"
    if unit == "mm":
        return f"{round(val / 2.83465, 1)} mm"
    if unit == "pt":
        return f"{round(val, 1):g} pt"
    if unit == "pi":
        return f"{round(val / 12.0, 2)} pi"
    return f'{round(val / 72.0, 2):g}"'


@dataclass
class DocGridProperties:
    """East Asian document line grid properties."""

    type: str = "lines"  # "lines", "linesAndChars", "none"
    line_pitch: float = 15.6  # Default 15.6 pt (or 18 pt)
    char_space: float = 0.0


@dataclass
class ColumnsProperties:
    """Section columns layout configuration."""

    num: int = 1
    space: float = 36.0  # 0.5 in
    sep: bool = False
    equal_width: bool = True
    widths: list[float] = field(default_factory=list)


@dataclass
class PageNumberProperties:
    """Section page numbering settings."""

    fmt: str = "decimal"  # "decimal", "upperRoman", "lowerRoman", etc.
    start: int | None = None


@dataclass
class SectionProperties:
    """Section page layout and paper geometry."""

    pg_w: float = 612.0  # Letter default
    pg_h: float = 792.0
    orient: str = "portrait"  # "portrait", "landscape"
    mt: float = 72.0  # 1 in
    mb: float = 72.0
    ml: float = 90.0  # 1.25 in
    mr: float = 90.0
    gutter: float = 0.0
    hdr: float = 36.0  # 0.5 in
    ftr: float = 36.0
    cols: ColumnsProperties = field(default_factory=ColumnsProperties)
    doc_grid: DocGridProperties = field(default_factory=DocGridProperties)
    title_pg: bool = False
    v_align: str = "top"  # "top", "center", "both", "bottom"
    pg_num: PageNumberProperties = field(default_factory=PageNumberProperties)
    refs: dict[str, dict[str, str]] = field(default_factory=lambda: {"hdr": {}, "ftr": {}})
    sect_type: str = "nextPage"  # "nextPage", "continuous", "oddPage", "evenPage"


@dataclass
class IndentProperties:
    """Paragraph indentation in points."""

    left: float = 0.0
    right: float = 0.0
    first_line: float = 0.0  # Positive: first line indent; Negative: hanging indent


@dataclass
class SpacingProperties:
    """Paragraph spacing before/after and line spacing."""

    before: float = 0.0
    after: float = 0.0
    line: float = 1.0  # Multiplier or exact points
    line_rule: str = "auto"  # "auto", "exact", "atLeast"
    before_auto: bool = False
    after_auto: bool = False


@dataclass
class TabStop:
    """Paragraph tab stop position and alignment."""

    pos: float = 0.0
    align: str = "left"  # "left", "center", "right", "decimal", "bar"
    leader: str = "none"  # "none", "dot", "hyphen", "underscore"


@dataclass
class NumberingRef:
    """Reference to a list numbering definition."""

    id: str = "0"
    lvl: int = 0


@dataclass
class RevisionStamp:
    """Track Changes revision author and timestamp record."""

    author: str = "Author"
    date: str = ""  # ISO 8601 string, e.g. "2026-10-26T12:00:00Z"
    id: int = 0
    old: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParagraphProperties:
    """Paragraph formatting and layout properties."""

    style: str = "Normal"
    jc: str = "left"  # "left", "center", "right", "both", "distribute"
    ind: IndentProperties = field(default_factory=IndentProperties)
    sp: SpacingProperties = field(default_factory=SpacingProperties)
    keep_next: bool = False
    keep_lines: bool = False
    page_break_before: bool = False
    widow_control: bool = True
    outline_level: int | None = None
    tabs: list[TabStop] = field(default_factory=list)
    num: NumberingRef | None = None
    chg: RevisionStamp | None = None


@dataclass
class RunProperties:
    """Character and inline run formatting properties."""

    style: str | None = None
    font: str = "Times New Roman"
    font_ea: str = "SimSun"
    font_cs: str = "Times New Roman"
    sz: float = 12.0  # pt
    sz_ea: float | None = None
    sz_cs: float | None = None
    b: bool = False
    i: bool = False
    u: str = "none"  # "none", "single", "double", "dotted", "dashed", "wave"
    color: str = "auto"  # "RRGGBB" or "auto"
    vert: str = "baseline"  # "baseline", "superscript", "subscript"
    highlight: str | None = None
    strike: bool = False
    dstrike: bool = False
    caps: bool = False
    small_caps: bool = False
    kern: float | None = None
    spacing: float = 0.0
    lang: str = "en-US"
    lang_ea: str = "zh-CN"
    link: dict[str, Any] | None = None
    ins: RevisionStamp | None = None
    del_rev: RevisionStamp | None = None
    chg: RevisionStamp | None = None


@dataclass
class BorderProperties:
    """Table / Cell border properties."""

    val: str = "none"  # "none", "single", "double", etc.
    sz: float = 0.5  # pt
    color: str = "auto"


@dataclass
class ShadingProperties:
    """Table / Cell background shading properties."""

    val: str = "clear"
    color: str = "auto"
    fill: str = "auto"


@dataclass
class TableProperties:
    """Table layout and formatting properties."""

    style: str = "TableNormal"
    jc: str = "left"  # "left", "center", "right"
    w: float = 0.0
    w_type: str = "auto"  # "auto", "dxa", "pct"
    borders: dict[str, BorderProperties] = field(default_factory=dict)
    cell_mar: dict[str, float] = field(
        default_factory=lambda: {"t": 0.0, "b": 0.0, "l": 5.4, "r": 5.4}
    )


@dataclass
class RowProperties:
    """Table row formatting properties."""

    h: float | None = None
    h_rule: str = "auto"  # "auto", "exact", "atLeast"
    tbl_header: bool = False
    cant_split: bool = False


@dataclass
class CellProperties:
    """Table cell formatting properties."""

    w: float = 0.0
    w_type: str = "dxa"
    grid_span: int = 1
    v_merge: str | None = None  # "restart", "continue", None
    v_align: str = "top"  # "top", "center", "bottom"
    borders: dict[str, BorderProperties] = field(default_factory=dict)
    shd: ShadingProperties = field(default_factory=ShadingProperties)
