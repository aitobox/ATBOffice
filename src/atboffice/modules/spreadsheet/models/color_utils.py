"""Color and font geometry utilities for SpreadsheetML.

Implements ECMA-376 Part 1 §18.8.3 tint transformations in HSL color space,
and default row height calculation matching Microsoft Excel and LibreOffice.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from typing import Any

# SpreadsheetML theme index order (ECMA-376 Part 1 §18.8.3 / §20.1.6.2)
THEME_COLOR_ORDER: tuple[str, ...] = (
    "lt1",
    "dk1",
    "lt2",
    "dk2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
)

# Default Office theme colors in SpreadsheetML index order (0..11)
DEFAULT_THEME_COLORS: list[str] = [
    "#FFFFFF",  # 0: lt1 (window)
    "#000000",  # 1: dk1 (windowText)
    "#EEECE1",  # 2: lt2
    "#1F497D",  # 3: dk2
    "#4F81BD",  # 4: accent1
    "#C0504D",  # 5: accent2
    "#9BBB59",  # 6: accent3
    "#8064A2",  # 7: accent4
    "#4BACC6",  # 8: accent5
    "#F79646",  # 9: accent6
    "#0000FF",  # 10: hlink
    "#800080",  # 11: folHlink
]

# ECMA-376 Part 1 §18.8.27 default 64-entry indexed color palette (0..63)
DEFAULT_INDEXED_PALETTE: list[str] = [
    "#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF",
    "#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF",
    "#800000", "#008000", "#000080", "#808000", "#800080", "#008080", "#C0C0C0", "#808080",
    "#9999FF", "#993366", "#FFFFCC", "#CCFFFF", "#660066", "#FF8080", "#0066CC", "#CCCCFF",
    "#000080", "#FF00FF", "#FFFF00", "#00FFFF", "#800080", "#800000", "#008080", "#0000FF",
    "#00CCFF", "#CCFFFF", "#CCFFCC", "#FFFF99", "#99CCFF", "#FF99CC", "#CC99FF", "#FFCC99",
    "#3366FF", "#33CCCC", "#99CC00", "#FFCC00", "#FF9900", "#FF6600", "#666699", "#969696",
    "#003366", "#339966", "#003300", "#333300", "#993300", "#993366", "#333399", "#333333",
]


def _local_tag(tag: str) -> str:
    """Strip XML namespace URI from an ElementTree tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _local_attr(el: ET.Element | None, name: str, default: str | None = None) -> str | None:
    """Retrieve attribute value matching local name, ignoring XML namespaces."""
    if el is None:
        return default
    target = name.lower()
    for k, v in el.attrib.items():
        local_k = k.split("}", 1)[1] if "}" in k else k
        if ":" in local_k:
            local_k = local_k.split(":", 1)[1]
        if local_k.lower() == target:
            return v
    return default


def _find_local_child(el: ET.Element | None, name: str) -> ET.Element | None:
    """Find first direct child matching local tag name (case-insensitive)."""
    if el is None:
        return None
    target = name.lower()
    for child in el:
        if _local_tag(child.tag).lower() == target:
            return child
    return None


def normalize_hex_color(col: str | None) -> str | None:
    """Normalize an RGB or ARGB color string to canonical '#RRGGBB' (or '#AARRGGBB')."""
    if not col:
        return None
    clean = str(col).strip().lstrip("#").upper()
    if not clean:
        return None
    if len(clean) == 8:
        if clean.startswith("FF"):
            return f"#{clean[2:]}"
        return f"#{clean}"
    if len(clean) == 6:
        return f"#{clean}"
    if len(clean) == 3:
        return f"#{clean[0] * 2}{clean[1] * 2}{clean[2] * 2}"
    if len(clean) > 6:
        return f"#{clean[-6:]}"
    return f"#{clean.zfill(6)}"


def parse_theme_xml(xml_bytes: bytes) -> dict[str, Any]:
    """Parse DrawingML xl/theme/theme1.xml into theme colors and fonts.

    Returns a dictionary with keys:
      - name: Theme name string
      - colors: 12-entry list of '#RRGGBB' strings in THEME_COLOR_ORDER
      - scheme: Dict mapping slot name -> '#RRGGBB'
      - major: Major Latin font typeface
      - minor: Minor Latin font typeface
    """
    colors = list(DEFAULT_THEME_COLORS)
    scheme = dict(zip(THEME_COLOR_ORDER, colors))
    result: dict[str, Any] = {
        "name": "Office",
        "colors": colors,
        "scheme": scheme,
        "major": "Cambria",
        "minor": "Calibri",
    }
    if not xml_bytes:
        return result

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return result

    theme_name = _local_attr(root, "name")
    if theme_name:
        result["name"] = theme_name

    elems = _find_local_child(root, "themeElements")
    if elems is None:
        return result

    clr_scheme = _find_local_child(elems, "clrScheme")
    if clr_scheme is not None:
        for idx, slot_name in enumerate(THEME_COLOR_ORDER):
            slot_el = _find_local_child(clr_scheme, slot_name)
            if slot_el is None or len(slot_el) == 0:
                continue
            color_node = slot_el[0]
            node_tag = _local_tag(color_node.tag).lower()
            resolved: str | None = None
            if node_tag == "srgbclr":
                val = _local_attr(color_node, "val")
                if val:
                    resolved = normalize_hex_color(val)
            elif node_tag == "sysclr":
                last_clr = _local_attr(color_node, "lastClr")
                if last_clr:
                    resolved = normalize_hex_color(last_clr)
                else:
                    sys_val = (_local_attr(color_node, "val") or "").lower()
                    resolved = "#FFFFFF" if sys_val == "window" else "#000000"
            if resolved:
                colors[idx] = resolved
                scheme[slot_name] = resolved

    font_scheme = _find_local_child(elems, "fontScheme")
    if font_scheme is not None:
        major_el = _find_local_child(font_scheme, "majorFont")
        minor_el = _find_local_child(font_scheme, "minorFont")
        if major_el is not None:
            latin_mj = _find_local_child(major_el, "latin")
            tp = _local_attr(latin_mj, "typeface")
            if tp:
                result["major"] = tp
        if minor_el is not None:
            latin_mn = _find_local_child(minor_el, "latin")
            tp = _local_attr(latin_mn, "typeface")
            if tp:
                result["minor"] = tp

    return result


def parse_color_element(el: ET.Element | None) -> dict[str, Any] | None:
    """Parse an OOXML SpreadsheetML color element into a structured color spec dict.

    Priority matches Excel / Ledger: auto -> theme > rgb > indexed, plus optional tint.
    """
    if el is None:
        return None

    auto_attr = _local_attr(el, "auto")
    if auto_attr is not None and auto_attr.strip().lower() in ("1", "true"):
        return {"auto": True}

    spec: dict[str, Any] | None = None

    theme_attr = _local_attr(el, "theme")
    rgb_attr = _local_attr(el, "rgb")
    indexed_attr = _local_attr(el, "indexed")

    if theme_attr is not None and theme_attr.strip() != "":
        try:
            spec = {"theme": int(float(theme_attr.strip()))}
        except ValueError:
            spec = None
    elif rgb_attr is not None and rgb_attr.strip() != "":
        clean = rgb_attr.strip().lstrip("#").upper()
        if len(clean) == 6:
            clean = "FF" + clean
        spec = {"rgb": clean}
    elif indexed_attr is not None and indexed_attr.strip() != "":
        try:
            spec = {"indexed": int(float(indexed_attr.strip()))}
        except ValueError:
            spec = None

    if spec is None:
        return None

    tint_attr = _local_attr(el, "tint")
    if tint_attr is not None and tint_attr.strip() != "":
        try:
            tint_val = float(tint_attr.strip())
            if math.isfinite(tint_val) and tint_val != 0.0:
                spec["tint"] = tint_val
        except ValueError:
            pass

    return spec


def resolve_color_spec(
    spec: dict[str, Any] | str | None,
    theme_colors: Sequence[str] | None = None,
    palette: Sequence[str] | None = None,
    auto: str | None = None,
) -> str | None:
    """Resolve a structured OOXML color spec (or hex string) to '#RRGGBB'.

    Handles:
      - auto=True -> returns `auto`
      - theme=N -> looks up `theme_colors[N]` (or DEFAULT_THEME_COLORS)
      - rgb=... -> normalizes to '#RRGGBB'
      - indexed=64 -> system foreground (`auto` if provided else '#000000')
      - indexed=65 -> system background ('#FFFFFF')
      - indexed=N -> looks up `palette[N]` (or DEFAULT_INDEXED_PALETTE)
      - tint -> applies HSL luminance tint via `apply_tint`
    """
    if spec is None:
        return None
    if isinstance(spec, str):
        return normalize_hex_color(spec)

    if spec.get("auto"):
        return auto

    hex_val: str | None = None
    if "theme" in spec and spec["theme"] is not None:
        th = theme_colors if theme_colors else DEFAULT_THEME_COLORS
        idx = int(spec["theme"])
        if 0 <= idx < len(th):
            hex_val = normalize_hex_color(th[idx])
        elif 0 <= idx < len(DEFAULT_THEME_COLORS):
            hex_val = DEFAULT_THEME_COLORS[idx]
        else:
            hex_val = "#000000"
    elif spec.get("rgb"):
        hex_val = normalize_hex_color(str(spec["rgb"]))
    elif "indexed" in spec and spec["indexed"] is not None:
        idx = int(spec["indexed"])
        if idx == 64:
            return auto if auto is not None else "#000000"
        if idx == 65:
            return "#FFFFFF"
        pal = palette if palette else DEFAULT_INDEXED_PALETTE
        if 0 <= idx < len(pal):
            hex_val = normalize_hex_color(pal[idx])
        elif 0 <= idx < len(DEFAULT_INDEXED_PALETTE):
            hex_val = DEFAULT_INDEXED_PALETTE[idx]
        else:
            hex_val = "#000000"

    if hex_val and spec.get("tint"):
        hex_val = apply_tint(hex_val, float(spec["tint"]))

    return hex_val


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
