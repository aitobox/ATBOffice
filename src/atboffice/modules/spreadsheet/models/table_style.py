"""Excel table (ListObject) styles.

Port of ``ledger/js/styles.js``: the built-in Light / Medium / Dark table styles
derived from the theme colours, custom dxf-based ``<tableStyle>`` definitions from
``xl/styles.xml``, and the per-cell resolution ``table_style_at(sheet, r, c)``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from atboffice.modules.spreadsheet.models.color_utils import DEFAULT_THEME_COLORS, apply_tint
from atboffice.modules.spreadsheet.models.conditional_format import CFResult
from atboffice.modules.spreadsheet.models.sheet_model import BorderStyle, SheetDataModel, Table

_WHITE = "#FFFFFF"
_BLACK = "#000000"
_SIDES = ("t", "b", "l", "r")


@dataclass
class TableStylePart:
    """Formatting contributed by one table style element (header row, stripe, ...)."""

    fill: str | None = None
    font_color: str | None = None
    bold: bool | None = None
    borders: dict[str, BorderStyle] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return (
            self.fill is None
            and self.font_color is None
            and self.bold is None
            and not self.borders
        )


# The per-cell result has the same shape as a style element.
TableCellStyle = TableStylePart


@dataclass
class TableStyleSpec:
    """A resolved table style: one optional part per ``tableStyleElement`` type."""

    whole: TableStylePart | None = None
    header: TableStylePart | None = None
    total: TableStylePart | None = None
    band1: TableStylePart | None = None
    band2: TableStylePart | None = None
    col_band1: TableStylePart | None = None
    col_band2: TableStylePart | None = None
    first_col: TableStylePart | None = None
    last_col: TableStylePart | None = None
    inner_h: BorderStyle | None = None
    inner_v: BorderStyle | None = None


BUILTIN_TABLE_STYLE_NAMES: list[str] = (
    [f"TableStyleLight{i}" for i in range(1, 22)]
    + [f"TableStyleMedium{i}" for i in range(1, 29)]
    + [f"TableStyleDark{i}" for i in range(1, 12)]
)

_BUILTIN_RE = re.compile(r"^TableStyle(Light|Medium|Dark)(\d+)$")


def _line(color: str, style: str = "thin") -> BorderStyle:
    return BorderStyle(style=style, color=color)


def _part(
    fill: str | None = None,
    font_color: str | None = None,
    bold: bool | None = None,
    **borders: BorderStyle,
) -> TableStylePart:
    return TableStylePart(fill=fill, font_color=font_color, bold=bold, borders=dict(borders))


def _accent(theme: Sequence[str], k: int) -> str:
    """Theme colour for accent index ``k`` (0 = the dark text colour dk1)."""
    if k == 0:
        return theme[1] if len(theme) > 1 and theme[1] else _BLACK
    idx = 3 + k
    return theme[idx] if idx < len(theme) and theme[idx] else DEFAULT_THEME_COLORS[idx]


def builtin_table_style(
    name: str, theme_colors: Sequence[str] | None = None
) -> TableStyleSpec | None:
    """Spec of a built-in ``TableStyle{Light,Medium,Dark}N`` style, or None if not built-in."""
    m = _BUILTIN_RE.match(name or "")
    if not m:
        return None
    kind, n = m.group(1), int(m.group(2))
    theme = list(theme_colors) if theme_colors else list(DEFAULT_THEME_COLORS)
    k = (n - 1) % 7
    a = _accent(theme, k)
    gray = k == 0
    pale = "#D9D9D9" if gray else apply_tint(a, 0.8)
    pale2 = "#BFBFBF" if gray else apply_tint(a, 0.6)
    mid = "#808080" if gray else apply_tint(a, 0.4)
    bold = _part(bold=True)

    if kind == "Light":
        if n <= 7:
            dark_text = None if gray else apply_tint(a, -0.25)
            return TableStyleSpec(
                whole=_part(t=_line(a), b=_line(a)),
                header=_part(font_color=dark_text, bold=True, b=_line(a)),
                total=_part(bold=True, t=_line(a)),
                band1=_part(fill=pale, font_color=dark_text),
                band2=_part(font_color=dark_text),
                first_col=bold,
                last_col=bold,
            )
        if n <= 14:
            return TableStyleSpec(
                whole=_part(t=_line(a), b=_line(a), l=_line(a), r=_line(a)),
                header=_part(fill=a, font_color=_WHITE, bold=True),
                total=_part(bold=True, t=_line(a, "double")),
                band1=_part(t=_line(a), b=_line(a)),
                first_col=bold,
                last_col=bold,
            )
        return TableStyleSpec(
            whole=_part(t=_line(a), b=_line(a), l=_line(a), r=_line(a)),
            inner_h=_line(a),
            inner_v=_line(a),
            header=_part(bold=True, b=_line(a, "medium")),
            total=_part(bold=True, t=_line(a, "double")),
            band1=_part(fill=pale),
            first_col=bold,
            last_col=bold,
        )

    if kind == "Medium":
        if n <= 7:
            return TableStyleSpec(
                whole=_part(t=_line(mid), b=_line(mid), l=_line(mid), r=_line(mid)),
                inner_h=_line(mid),
                header=_part(fill=a, font_color=_WHITE, bold=True),
                total=_part(bold=True, t=_line(a, "double")),
                band1=_part(fill=pale),
                first_col=bold,
                last_col=bold,
            )
        if n <= 14:
            accent_col = _part(fill=a, font_color=_WHITE, bold=True)
            return TableStyleSpec(
                whole=_part(fill=pale),
                inner_h=_line(_WHITE),
                inner_v=_line(_WHITE),
                header=_part(fill=a, font_color=_WHITE, bold=True, b=_line(_WHITE, "medium")),
                total=_part(fill=a, font_color=_WHITE, bold=True, t=_line(_WHITE, "medium")),
                band1=_part(fill=pale2),
                first_col=accent_col,
                last_col=accent_col,
            )
        if n <= 21:
            return TableStyleSpec(
                whole=_part(t=_line(_BLACK, "medium"), b=_line(_BLACK, "medium")),
                header=_part(fill=a, font_color=_WHITE, bold=True, b=_line(_BLACK, "medium")),
                total=_part(bold=True, t=_line(_BLACK, "double")),
                band1=_part(fill=pale2),
                first_col=bold,
                last_col=bold,
            )
        return TableStyleSpec(
            whole=_part(fill=pale, t=_line(mid), b=_line(mid), l=_line(mid), r=_line(mid)),
            inner_h=_line(mid),
            inner_v=_line(mid),
            header=bold,
            total=_part(bold=True, t=_line(a, "double")),
            band1=_part(fill=pale2),
            first_col=bold,
            last_col=bold,
        )

    # Dark
    if n <= 7:
        dark = "#404040" if gray else apply_tint(a, -0.25)
        dark_col = _part(fill=dark, font_color=_WHITE, bold=True)
        return TableStyleSpec(
            whole=_part(fill=a, font_color=_WHITE),
            header=_part(fill=_BLACK, font_color=_WHITE, bold=True, b=_line(_WHITE, "medium")),
            total=_part(
                fill=apply_tint(a, -0.5), font_color=_WHITE, bold=True, t=_line(_WHITE, "double")
            ),
            band1=_part(fill=dark),
            first_col=dark_col,
            last_col=dark_col,
        )
    pairs = [(0, 1), (1, 2), (3, 4), (5, 6)]
    i1, i2 = pairs[(n - 8) % 4]
    p1, p2 = _accent(theme, i1), _accent(theme, i2)
    return TableStyleSpec(
        whole=_part(fill=apply_tint(p2, 0.8)),
        header=_part(fill=p1, font_color=_WHITE, bold=True),
        total=_part(fill=apply_tint(p2, 0.8), bold=True, t=_line(_BLACK, "double")),
        band1=_part(fill=apply_tint(p2, 0.6)),
        first_col=bold,
        last_col=bold,
    )


_ELEMENT_KEYS = {
    "wholeTable": "whole",
    "headerRow": "header",
    "totalRow": "total",
    "firstRowStripe": "band1",
    "secondRowStripe": "band2",
    "firstColumn": "first_col",
    "lastColumn": "last_col",
    "firstColumnStripe": "col_band1",
    "secondColumnStripe": "col_band2",
}
_DXF_SIDES = {"top": "t", "bottom": "b", "left": "l", "right": "r"}


def custom_table_style(
    name: str,
    custom_styles: Sequence[dict[str, Any]] | None,
    dxfs: Sequence[dict[str, Any]] | None,
) -> TableStyleSpec | None:
    """Spec of a workbook-defined ``<tableStyle>`` built from its dxf records."""
    style = next((s for s in custom_styles or () if s.get("name") == name), None)
    if style is None:
        return None
    dxfs = dxfs or []
    spec = TableStyleSpec()
    for el in style.get("elements", []):
        key = _ELEMENT_KEYS.get(el.get("type", ""))
        dxf_id = el.get("dxf_id", -1)
        if key is None or not 0 <= dxf_id < len(dxfs):
            continue
        d = dxfs[dxf_id]
        part = TableStylePart()
        if d.get("bg_color") and d.get("pattern_type") != "none":
            part.fill = d["bg_color"]
        if d.get("fg_color"):
            part.font_color = d["fg_color"]
        if d.get("bold") is not None:
            part.bold = d["bold"]
        borders: dict[str, BorderStyle] = d.get("borders") or {}
        for side, short in _DXF_SIDES.items():
            if side in borders:
                part.borders[short] = borders[side]
        if key == "whole":
            spec.inner_h = borders.get("horizontal")
            spec.inner_v = borders.get("vertical")
        setattr(spec, key, part)
    return spec


def resolve_table_style(
    name: str | None,
    theme_colors: Sequence[str] | None = None,
    custom_styles: Sequence[dict[str, Any]] | None = None,
    dxfs: Sequence[dict[str, Any]] | None = None,
) -> TableStyleSpec | None:
    """Custom workbook styles shadow built-ins of the same name (as in Excel)."""
    if not name:
        return None
    return custom_table_style(name, custom_styles, dxfs) or builtin_table_style(name, theme_colors)


def _merge(out: TableStylePart, part: TableStylePart | None) -> None:
    if part is None:
        return
    if part.fill is not None:
        out.fill = part.fill
    if part.font_color is not None:
        out.font_color = part.font_color
    if part.bold is not None:
        out.bold = part.bold
    out.borders.update(part.borders)


def table_cell_style(table: Table, r: int, c: int) -> TableCellStyle | None:
    """Formatting the table style gives cell (r, c); precedence follows ``TS.at``."""
    spec: TableStyleSpec | None = table.spec
    if spec is None or not table.contains(r, c):
        return None
    header = table.has_header and r == table.r1
    total = table.has_totals and r == table.r2
    out = TableStylePart()

    if spec.whole is not None:
        w = spec.whole
        out.fill = w.fill
        out.font_color = w.font_color
        out.bold = w.bold
        edges = {"t": r == table.r1, "b": r == table.r2, "l": c == table.c1, "r": c == table.c2}
        for side in _SIDES:
            if edges[side] and side in w.borders:
                out.borders[side] = w.borders[side]
        ih, iv = spec.inner_h, spec.inner_v
        if ih is not None:
            if r < table.r2:
                out.borders.setdefault("b", ih)
            if r > table.r1:
                out.borders.setdefault("t", ih)
        if iv is not None:
            if c < table.c2:
                out.borders.setdefault("r", iv)
            if c > table.c1:
                out.borders.setdefault("l", iv)

    if not header and not total:
        si = table.style_info
        if si is not None:
            data_idx = r - table.r1 - (1 if table.has_header else 0)
            if si.show_row_stripes:
                _merge(out, spec.band1 if data_idx % 2 == 0 else spec.band2)
            if si.show_column_stripes:
                _merge(out, spec.col_band1 if (c - table.c1) % 2 == 0 else spec.col_band2)
            if si.show_first_column and c == table.c1:
                _merge(out, spec.first_col)
            if si.show_last_column and c == table.c2:
                _merge(out, spec.last_col)
    if header:
        _merge(out, spec.header)
    if total:
        _merge(out, spec.total)
    return None if out.is_empty() else out


def table_style_at(sheet: SheetDataModel, r: int, c: int) -> TableCellStyle | None:
    """Table-style formatting for cell (r, c) of ``sheet`` (None outside any styled table)."""
    tables = getattr(sheet, "tables", None)
    if not tables:
        return None
    table = sheet.table_at(r, c)
    return table_cell_style(table, r, c) if table is not None else None


def overlay_table_style(
    cf_res: CFResult | None,
    ts: TableCellStyle | None,
    cell: Any,
    default_font_color: str | None = None,
) -> CFResult | None:
    """Fold a table style under direct cell formatting and conditional formatting.

    Precedence (``ledger/js/render.js``): conditional format > direct cell format > table
    style. The table fill is used only when the cell has no fill of its own, the table
    font colour only when the cell has none (a colour equal to the workbook default font,
    ``default_font_color``, counts as none), and table bold never clears cell bold.
    """
    if ts is None:
        return cf_res
    out = replace(cf_res) if cf_res is not None else CFResult()
    has_own_fill = cell is not None and (cell.bg_color or cell.pattern)
    if out.bg_color is None and ts.fill and not has_own_fill:
        out.bg_color = ts.fill
    own_color = cell.fg_color if cell is not None else None
    has_own_color = bool(own_color) and (
        default_font_color is None or own_color.upper() != default_font_color.upper()
    )
    if out.fg_color is None and ts.font_color and not has_own_color:
        out.fg_color = ts.font_color
    if out.bold is None and ts.bold:
        out.bold = True
    return out
