"""Color and font geometry utilities for SpreadsheetML.

Implements ECMA-376 Part 1 §18.8.3 tint transformations in HSL color space,
and default row height calculation matching Microsoft Excel and LibreOffice.
"""

from __future__ import annotations


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB (0-255) to HSL (0.0-1.0)."""
    R, G, B = r / 255.0, g / 255.0, b / 255.0
    top, bottom = max(R, G, B), min(R, G, B)
    lum = (top + bottom) / 2.0
    if top == bottom:
        return 0.0, 0.0, lum
    span = top - bottom
    s = span / (2.0 - top - bottom) if lum > 0.5 else span / (top + bottom)
    if top == R:
        h = (G - B) / span + (6.0 if G < B else 0.0)
    elif top == G:
        h = 2.0 + (B - R) / span
    else:
        h = 4.0 + (R - G) / span
    return h / 6.0, s, lum


def hsl_to_rgb(h: float, s: float, lum: float) -> tuple[int, int, int]:
    """Convert HSL (0.0-1.0) to RGB (0-255).

    Follows CSS Color Level 3 / ECMA-376 standard hue conversion.
    """
    if s == 0:
        val = int(round(lum * 255.0))
        return val, val, val

    m2 = lum * (s + 1.0) if lum < 0.5 else lum + s - lum * s
    m1 = lum * 2.0 - m2

    def hue_to_rgb(x: float) -> float:
        if x < 0.0:
            x += 1.0
        if x > 1.0:
            x -= 1.0
        if x < 1.0 / 6.0:
            return m1 + (m2 - m1) * 6.0 * x
        if x < 0.5:
            return m2
        if x < 2.0 / 3.0:
            return m1 + (m2 - m1) * (2.0 / 3.0 - x) * 6.0
        return m1

    r = int(round(hue_to_rgb(h + 1.0 / 3.0) * 255.0))
    g = int(round(hue_to_rgb(h) * 255.0))
    b = int(round(hue_to_rgb(h - 1.0 / 3.0) * 255.0))
    return (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b)),
    )


def apply_tint(hex_str: str, tint: float) -> str:
    """Apply SpreadsheetML tint (lighten if tint > 0, darken if tint < 0) in HSL luminance.

    ECMA-376 Part 1 §18.8.3:
      If tint < 0: Lum' = Lum * (1.0 + tint)
      If tint > 0: Lum' = Lum * (1.0 - tint) + (1.0 - (1.0 - tint)) = Lum * (1.0 - tint) + tint
    """
    if not tint:
        clean = hex_str.lstrip("#")
        return f"#{clean[-6:].upper()}" if len(clean) >= 6 else hex_str.upper()

    clean = hex_str.lstrip("#")
    if len(clean) == 8:
        clean = clean[2:]
    if len(clean) < 6:
        clean = clean.zfill(6)

    r = int(clean[0:2], 16)
    g = int(clean[2:4], 16)
    b = int(clean[4:6], 16)

    h, s, lum = rgb_to_hsl(r, g, b)
    if tint < 0:
        l2 = lum * (1.0 + tint)
    else:
        l2 = lum * (1.0 - tint) + tint

    l2 = max(0.0, min(1.0, l2))
    nr, ng, nb = hsl_to_rgb(h, s, l2)
    return f"#{nr:02X}{ng:02X}{nb:02X}"


def normalize_font_key(name: str) -> str:
    """Normalize font name across English and East Asian localized names."""
    n = (name or "").strip().lower()
    mapping = {
        "ｍｓ ｐゴシック": "ms pgothic",
        "ms pgothic": "ms pgothic",
        "ｍｓ 明朝": "ms mincho",
        "ms mincho": "ms mincho",
        "ｍｓ ゴシック": "ms gothic",
        "ms gothic": "ms gothic",
        "游ゴシック": "yu gothic",
        "yu gothic": "yu gothic",
        "맑은 고딕": "malgun gothic",
        "malgun gothic": "malgun gothic",
        "宋体": "simsun",
        "simsun": "simsun",
        "新細明體": "pmingliu",
        "pmingliu": "pmingliu",
    }
    return mapping.get(n, n)


def font_row_pt(font_name: str, sz: float = 11.0) -> float:
    """Calculate default row height in points for the given default font and point size."""
    name = normalize_font_key(font_name or "Arial")
    size = float(sz or 11.0)

    arial_table: dict[int, float] = {
        8: 11.25,
        9: 12.0,
        10: 12.75,
        11: 14.25,
        12: 15.0,
        14: 18.0,
        16: 20.25,
        18: 23.25,
        20: 25.5,
        24: 30.0,
    }
    calibri_table: dict[int, float] = {
        8: 11.25,
        9: 12.0,
        10: 12.75,
        11: 15.0,
        12: 15.75,
        14: 18.75,
        16: 21.0,
        18: 23.25,
        20: 26.25,
        24: 31.5,
    }

    if name == "arial" and int(size) in arial_table and size == int(size):
        return arial_table[int(size)]
    has_calibri_family = any(k in name for k in ["calibri", "aptos", "segoe"])
    if has_calibri_family and int(size) in calibri_table and size == int(size):
        return calibri_table[int(size)]

    # Localized East Asian default sizes for 11pt
    ea_rates: dict[str, float] = {
        "ms pgothic": 13.5,
        "ms gothic": 13.5,
        "yu gothic": 18.75,
        "malgun gothic": 16.5,
        "simsun": 13.5,
        "pmingliu": 14.25,
    }
    if name in ea_rates:
        rate = ea_rates[name] / 11.0
    else:
        rate = 1.275

    return round(size * rate * 4.0) / 4.0


def pt_to_px(pt: float) -> int:
    """Convert typography points (pt) to screen pixels (96 DPI)."""
    return int(round((pt * 96.0) / 72.0))
