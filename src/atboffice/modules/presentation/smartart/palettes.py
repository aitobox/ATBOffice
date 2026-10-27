"""Color palettes, texture styles, and shape painting for SmartArt."""

from __future__ import annotations

from typing import Any

# 13 Built-in Palettes: [Name, Colors, Method ('span' | 'cycle'), TextColor, BaseColor]
PALETTES: dict[str, list[Any]] = {
    "ocean": ["Ocean", ["#0891B2", "#4F46E5"], "span", "#FFFFFF", "#0891B2"],
    "aurora": ["Aurora", ["#059669", "#2563EB"], "span", "#FFFFFF", "#059669"],
    "lagoon": ["Lagoon", ["#0F766E", "#0284C7"], "span", "#FFFFFF", "#0F766E"],
    "midnight": ["Midnight", ["#1E3A8A", "#7C3AED"], "span", "#FFFFFF", "#1E3A8A"],
    "berry": ["Berry", ["#7C3AED", "#DB2777"], "span", "#FFFFFF", "#7C3AED"],
    "sunset": ["Sunset", ["#EA580C", "#DB2777"], "span", "#FFFFFF", "#EA580C"],
    "fire": ["Fire", ["#B91C1C", "#EA580C"], "span", "#FFFFFF", "#B91C1C"],
    "amber": ["Amber", ["#B45309", "#CA8A04"], "span", "#FFFFFF", "#B45309"],
    "forest": ["Forest", ["#166534", "#65A30D"], "span", "#FFFFFF", "#166534"],
    "slate": ["Slate", ["#1E293B", "#64748B"], "span", "#FFFFFF", "#1E293B"],
    "vivid": ["Vivid", ["#E03131", "#E8590C", "#2F9E44", "#1971C2", "#7048E8"], "cycle", "#FFFFFF", "#E03131"],
    "jewel": ["Jewel", ["#0E7490", "#7E22CE", "#BE123C", "#15803D", "#1D4ED8"], "cycle", "#FFFFFF", "#0E7490"],
    "pastel": ["Pastel", ["#FBCFE8", "#BFDBFE", "#BBF7D0", "#FDE68A", "#DDD6FE"], "cycle", "#1F2937", "#64748B"],
}

# 13 Built-in Quick Styles: [ID, Name, [LineRef, FillRef, EffectRef], Language ('fill' | 'outline' | 'tint')]
STYLES: list[list[Any]] = [
    ["simple", "Simple Fill", [2, 1, 0], "fill"],
    ["flat", "Flat", [0, 1, 0], "fill"],
    ["white", "White Outline", [3, 1, 0], "fill"],
    ["subtle", "Subtle Effect", [2, 1, 1], "fill"],
    ["soft", "Soft Gradient", [0, 2, 0], "fill"],
    ["moderate", "Moderate Effect", [0, 2, 2], "fill"],
    ["intense", "Intense Effect", [0, 3, 3], "fill"],
    ["lifted", "Lifted", [2, 2, 3], "fill"],
    ["gloss", "Gloss", [1, 3, 2], "fill"],
    ["outline", "Outline", [2, 1, 0], "outline"],
    ["card", "Outline Card", [1, 1, 2], "outline"],
    ["tint", "Tinted", [0, 1, 0], "tint"],
    ["tintLine", "Tinted Outline", [2, 1, 0], "tint"],
]

DEFAULT_COLORS: str = "ocean"
DEFAULT_STYLE: str = "moderate"


def mix_hex(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex color codes."""
    t_clamped = max(0.0, min(1.0, float(t)))
    c1_clean = c1.lstrip("#")
    c2_clean = c2.lstrip("#")
    r1, g1, b1 = int(c1_clean[0:2], 16), int(c1_clean[2:4], 16), int(c1_clean[4:6], 16)
    r2, g2, b2 = int(c2_clean[0:2], 16), int(c2_clean[2:4], 16), int(c2_clean[4:6], 16)
    r = round(r1 + (r2 - r1) * t_clamped)
    g = round(g1 + (g2 - g1) * t_clamped)
    b = round(b1 + (b2 - b1) * t_clamped)
    return f"#{r:02X}{g:02X}{b:02X}"


def style_info(style_id: str) -> list[Any]:
    """Retrieve style definition entry by style id."""
    for s in STYLES:
        if s[0] == style_id:
            return s
    return STYLES[0]


def style_lang(style_id: str) -> str:
    """Retrieve style language ('fill', 'outline', or 'tint')."""
    info = style_info(style_id)
    return str(info[3]) if len(info) > 3 else "fill"


def style_refs(style_id: str) -> list[int]:
    """Retrieve style refs [line, fill, effect]."""
    return list(style_info(style_id)[2])


def color_spec(colors_id: str, pal: Any = None) -> dict[str, Any]:
    """Resolve color specification: colors, method, base color, and text colors."""
    p = PALETTES.get(colors_id) or PALETTES[DEFAULT_COLORS]
    name, cols, meth = p[0], list(p[1]), p[2]
    text_color = p[3] if len(p) > 3 else "#FFFFFF"
    base_color = p[4] if len(p) > 4 else cols[0]
    return {
        "name": name,
        "cols": cols,
        "meth": meth,
        "base": base_color,
        "texts": [text_color],
    }


def paint_shape(s: dict[str, Any], sa: dict[str, Any], pal: Any = None) -> dict[str, Any]:
    """Calculate fill, line, shadow, and text formatting for a laid-out SmartArt shape."""
    colors_id = sa.get("colors") or DEFAULT_COLORS
    style_id = sa.get("style") or DEFAULT_STYLE
    spec = color_spec(colors_id, pal)

    cols = spec["cols"]
    n_cols = len(cols)
    meth = spec["meth"]
    base = spec["base"]
    texts = spec["texts"]

    idx = s.get("colorIdx", 0)
    cnt = s.get("colorCnt", 1)
    alpha = s.get("alpha", 1.0)
    role = s.get("role", "node")
    lang = style_lang(style_id)
    venn = s.get("styleLbl") == "vennNode1"

    # Step in span or item in cycle
    if meth == "cycle" and role != "conn":
        c = cols[idx % n_cols]
    elif meth == "span":
        if cnt > 1:
            t = (idx / (cnt - 1)) * (n_cols - 1)
            k = min(n_cols - 2, int(t))
            c = mix_hex(cols[k], cols[k + 1], t - k)
        else:
            c = cols[0]
    else:
        c = base

    # Sub-item bullets / cards
    if role == "child" and s.get("tint") and not s.get("noFill"):
        return {
            "fill": {"t": "solid", "c": c, "a": 0.18},
            "line": {"c": c, "w": 1.0, "dash": "solid"} if s.get("line") else {"t": "none"},
            "shadow": None,
            "text": "#1F2937",
        }
    if role == "child" or s.get("noFill"):
        return {
            "fill": {"t": "none"},
            "line": {"t": "none"},
            "shadow": None,
            "text": "#1F2937",
        }
    if role == "conn":
        return {
            "fill": {"t": "none"},
            "line": {"c": c, "w": 1.5, "dash": "solid"},
            "shadow": None,
            "text": None,
        }
    if role == "ring":
        return {
            "fill": {"t": "none"},
            "line": {"c": c, "a": 0.4, "w": 8.0, "dash": "solid"},
            "shadow": None,
            "text": None,
        }
    if role == "bg":
        return {
            "fill": {"t": "solid", "c": c, "a": 0.25},
            "line": {"t": "none"},
            "shadow": None,
            "text": None,
        }
    if role == "arrow":
        return {
            "fill": {"t": "solid", "c": c, "a": alpha * (0.3 if s.get("big") else 0.6)},
            "line": {"t": "none"},
            "shadow": None,
            "text": None,
        }

    # Style effects & shadows
    refs = style_refs(style_id)
    fx = refs[2]
    shadow = {"c": "#000000", "a": 0.25, "dx": 0.0, "dy": float(fx), "blur": float(fx) * 2.0} if fx > 0 and not venn else None

    # Text color
    default_text = "#1F2937" if venn else texts[idx % len(texts)]

    if lang == "outline":
        return {
            "fill": {"t": "solid", "c": "#FFFFFF", "a": alpha},
            "line": {"c": c, "w": 1.5, "dash": "solid"},
            "shadow": shadow,
            "text": "#1F2937" if venn else c,
        }
    if lang == "tint":
        tint_c = mix_hex(c, "#FFFFFF", 0.75)
        return {
            "fill": {"t": "solid", "c": tint_c, "a": 0.7 if venn else alpha},
            "line": {"c": c, "w": 1.0, "dash": "solid"},
            "shadow": shadow,
            "text": "#1F2937" if venn else c,
        }

    # Standard fill
    return {
        "fill": {"t": "solid", "c": c, "a": alpha},
        "line": {"t": "none"},
        "shadow": shadow,
        "text": default_text,
    }
