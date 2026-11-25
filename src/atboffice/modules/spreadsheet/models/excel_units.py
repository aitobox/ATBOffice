"""Excel's column-width and row-height units.

Port of the original's ``ledger/js/model.js`` (``M.mdw``, ``M.widthToPx``, ``M.defaultColPx``,
``M.fontRowPt``). Column widths in SpreadsheetML count characters of the workbook default
font's maximum digit width (MDW); default row heights follow the default font.
"""

from __future__ import annotations

import math

# Maximum digit width per point of font size, for the faces Excel workbooks commonly use
_MDW_PER_PT: dict[str, float] = {
    # Calibri 11 measures 8px per digit in the reference renderer (ledger/js layout
    # L.measureDigit); 7px made every custom-width Calibri column ~12% too narrow.
    "calibri": 8.0 / 11.0,
    "arial": 7.0 / 10.0,
    "aptos narrow": 7.0 / 11.0,
    "aptos": 7.5 / 11.0,
    "cambria": 7.0 / 11.0,
    "times new roman": 7.0 / 12.0,
    "verdana": 8.0 / 10.0,
    "tahoma": 7.0 / 10.0,
    "courier new": 8.0 / 10.0,
    "segoe ui": 7.0 / 10.0,
    "ms pgothic": 8.0 / 11.0,
    # Century Gothic is a wide face: its digits are ~0.55em, 8px at 11pt, as are those of the
    # faces the reference draws it with when it is missing (TeX Gyre Adventor, URW Gothic,
    # Futura, Arial). The 7px fallback left every column of a Century Gothic workbook ~12%
    # too narrow, so its tables ended well short of the reference's.
    "century gothic": 8.0 / 11.0,
}

# Row height (pt) Excel gives the default font at common sizes
_ROW_PT: dict[str, dict[int, float]] = {
    "arial": {
        8: 11.25,
        9: 12,
        10: 12.75,
        11: 14.25,
        12: 15,
        14: 18,
        16: 20.25,
        18: 23.25,
        20: 25.5,
        24: 30,
    },
    "calibri": {
        8: 11.25,
        9: 12,
        10: 12.75,
        11: 15,
        12: 15.75,
        14: 18.75,
        16: 21,
        18: 23.25,
        20: 26.25,
        24: 31.5,
    },
}
# East Asian faces, from their row height at 11pt in localized Excel workbooks
_EA_ROW_PT_AT_11: dict[str, float] = {
    "ms pgothic": 13.5,
    "ms gothic": 13.5,
    "yu gothic": 18.75,
    "malgun gothic": 16.5,
    "simsun": 13.5,
    "pmingliu": 14.25,
}

DEFAULT_MDW = 7


def excel_mdw(font_family: str | None, font_size: float | None) -> int:
    """Maximum digit width in pixels for a font."""
    name = (font_family or "Arial").strip().lower()
    sz = font_size or 11
    k = _MDW_PER_PT.get(name, 7.0 / 11.0)
    return max(5, int(round(k * sz)))


def width_to_px(width: float, mdw: int) -> int:
    """Column width in characters (``<col width>``, ``defaultColWidth``) to pixels."""
    return math.trunc(((256 * width + math.trunc(128 / mdw)) / 256) * mdw)


def px_to_width(px: float, mdw: int) -> float:
    """Pixels to the column width in characters that ``width_to_px`` maps back to ``px``."""
    return math.trunc((px / mdw) * 256) / 256


def default_col_px(mdw: int, default_col_width: float | None, base_col_width: float | None) -> int:
    """Default column width in pixels from ``<sheetFormatPr>``."""
    if default_col_width is not None:
        return width_to_px(default_col_width, mdw)
    base = 8.0 if base_col_width is None else base_col_width
    return math.ceil((base * mdw + 5) / 8) * 8


def font_row_pt(font_family: str | None, font_size: float | None) -> float:
    """Default row height in points for a workbook default font."""
    name = (font_family or "Arial").strip().lower()
    sz = font_size or 11
    table = _ROW_PT.get(name)
    if table is None and any(k in name for k in ("calibri", "aptos", "segoe")):
        table = _ROW_PT["calibri"]
    if table is not None and float(sz).is_integer() and int(sz) in table:
        return float(table[int(sz)])
    ea = _EA_ROW_PT_AT_11.get(name)
    return round(sz * (ea / 11 if ea else 1.275) * 4) / 4
