"""Centralized Font Metrics Calibration and Typography Measurement.

Provides metric-compatible font parameters matching Word 2003 / Chromium stand-in
fonts (Carlito, Caladea, Gelasio, Liberation / Tinos / Arimo) as specified in
.vibeoffice/docs/quire.md and .vibeoffice/tools/fonts.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FontMetricData:
    """Typographic metric parameters calibrated for a specific font family."""

    ascent_ratio: float
    descent_ratio: float
    line_factor: float
    space_em: float
    substitute_family: str = ""
    is_cjk: bool = False

    @property
    def total_height_ratio(self) -> float:
        """Physical font bounding height ratio."""
        return self.ascent_ratio + self.descent_ratio


# Default typographic parameters for unlisted fonts
DEFAULT_FONT_METRIC = FontMetricData(
    ascent_ratio=0.80,
    descent_ratio=0.20,
    line_factor=1.17,
    space_em=0.25,
    substitute_family="",
    is_cjk=False,
)

# ---------------------------------------------------------------------------
# Calibration Dictionary
# ---------------------------------------------------------------------------

FONT_METRICS_CALIBRATION: dict[str, FontMetricData] = {
    # Calibri stand-in (Carlito, OFL google/fonts 51303ca, unitsPerEm=2048, hhea: 1950/-550)
    "calibri": FontMetricData(
        ascent_ratio=0.9521,
        descent_ratio=0.2686,
        line_factor=1.2207,
        space_em=0.2261,
        substitute_family="Carlito",
    ),
    "calibri light": FontMetricData(
        ascent_ratio=0.9521,
        descent_ratio=0.2686,
        line_factor=1.2207,
        space_em=0.2261,
        substitute_family="Carlito",
    ),
    "carlito": FontMetricData(
        ascent_ratio=0.9521,
        descent_ratio=0.2686,
        line_factor=1.2207,
        space_em=0.2261,
        substitute_family="Carlito",
    ),
    "aptos": FontMetricData(
        ascent_ratio=0.9521,
        descent_ratio=0.2686,
        line_factor=1.2000,
        space_em=0.2000,
        substitute_family="Carlito",
    ),
    "aptos display": FontMetricData(
        ascent_ratio=0.9521,
        descent_ratio=0.2686,
        line_factor=1.2000,
        space_em=0.2000,
        substitute_family="Carlito",
    ),
    "aptos narrow": FontMetricData(
        ascent_ratio=0.9521,
        descent_ratio=0.2686,
        line_factor=1.2000,
        space_em=0.2000,
        substitute_family="Carlito",
    ),
    # Cambria stand-in (Caladea, unitsPerEm=1000, hhea: 900/-250)
    "cambria": FontMetricData(
        ascent_ratio=0.9000,
        descent_ratio=0.2500,
        line_factor=1.1724,
        space_em=0.2197,
        substitute_family="Caladea",
    ),
    "caladea": FontMetricData(
        ascent_ratio=0.9000,
        descent_ratio=0.2500,
        line_factor=1.1724,
        space_em=0.2197,
        substitute_family="Caladea",
    ),
    # Georgia stand-in (Gelasio, unitsPerEm=2048, hhea: 1900/-700)
    "georgia": FontMetricData(
        ascent_ratio=0.9277,
        descent_ratio=0.3418,
        line_factor=1.1362,
        space_em=0.2412,
        substitute_family="Gelasio",
    ),
    "gelasio": FontMetricData(
        ascent_ratio=0.9277,
        descent_ratio=0.3418,
        line_factor=1.1362,
        space_em=0.2412,
        substitute_family="Gelasio",
    ),
    # Times New Roman (Tinos / Liberation Serif)
    "times new roman": FontMetricData(
        ascent_ratio=0.8916,
        descent_ratio=0.2163,
        line_factor=1.1490,
        space_em=0.2500,
        substitute_family="Tinos",
    ),
    "times": FontMetricData(
        ascent_ratio=0.8916,
        descent_ratio=0.2163,
        line_factor=1.1490,
        space_em=0.2500,
        substitute_family="Tinos",
    ),
    "tinos": FontMetricData(
        ascent_ratio=0.8916,
        descent_ratio=0.2163,
        line_factor=1.1490,
        space_em=0.2500,
        substitute_family="Tinos",
    ),
    "liberation serif": FontMetricData(
        ascent_ratio=0.8916,
        descent_ratio=0.2163,
        line_factor=1.1490,
        space_em=0.2500,
        substitute_family="Liberation Serif",
    ),
    # Arial (Arimo / Liberation Sans / Helvetica)
    "arial": FontMetricData(
        ascent_ratio=0.9053,
        descent_ratio=0.2119,
        line_factor=1.1490,
        space_em=0.2778,
        substitute_family="Arimo",
    ),
    "arimo": FontMetricData(
        ascent_ratio=0.9053,
        descent_ratio=0.2119,
        line_factor=1.1490,
        space_em=0.2778,
        substitute_family="Arimo",
    ),
    "liberation sans": FontMetricData(
        ascent_ratio=0.9053,
        descent_ratio=0.2119,
        line_factor=1.1490,
        space_em=0.2778,
        substitute_family="Liberation Sans",
    ),
    "helvetica": FontMetricData(
        ascent_ratio=0.9053,
        descent_ratio=0.2119,
        line_factor=1.1490,
        space_em=0.2778,
        substitute_family="Helvetica",
    ),
    "arial narrow": FontMetricData(
        ascent_ratio=0.9053,
        descent_ratio=0.2119,
        line_factor=1.1490,
        space_em=0.2278,
        substitute_family="Arimo",
    ),
    "arial black": FontMetricData(
        ascent_ratio=1.0500,
        descent_ratio=0.3600,
        line_factor=1.4100,
        space_em=0.2778,
    ),
    # Courier New (Cousine / Liberation Mono)
    "courier new": FontMetricData(
        ascent_ratio=0.8328,
        descent_ratio=0.3000,
        line_factor=1.1328,
        space_em=0.6000,
        substitute_family="Cousine",
    ),
    "courier": FontMetricData(
        ascent_ratio=0.8328,
        descent_ratio=0.3000,
        line_factor=1.1328,
        space_em=0.6000,
        substitute_family="Cousine",
    ),
    "cousine": FontMetricData(
        ascent_ratio=0.8328,
        descent_ratio=0.3000,
        line_factor=1.1328,
        space_em=0.6000,
        substitute_family="Cousine",
    ),
    "liberation mono": FontMetricData(
        ascent_ratio=0.8328,
        descent_ratio=0.3000,
        line_factor=1.1328,
        space_em=0.6000,
        substitute_family="Liberation Mono",
    ),
    # Other Common Office Fonts
    "verdana": FontMetricData(
        ascent_ratio=0.9500,
        descent_ratio=0.2653,
        line_factor=1.2153,
        space_em=0.3516,
    ),
    "tahoma": FontMetricData(
        ascent_ratio=0.9500,
        descent_ratio=0.2569,
        line_factor=1.2069,
        space_em=0.3125,
    ),
    "trebuchet ms": FontMetricData(
        ascent_ratio=0.9000,
        descent_ratio=0.2611,
        line_factor=1.1611,
        space_em=0.3013,
    ),
    "segoe ui": FontMetricData(
        ascent_ratio=1.0500,
        descent_ratio=0.2801,
        line_factor=1.3301,
        space_em=0.2744,
    ),
    "garamond": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.2435,
        line_factor=1.1235,
        space_em=0.2500,
    ),
    "comic sans ms": FontMetricData(
        ascent_ratio=1.0800,
        descent_ratio=0.3136,
        line_factor=1.3936,
        space_em=0.3000,
    ),
    "book antiqua": FontMetricData(
        ascent_ratio=0.9100,
        descent_ratio=0.2604,
        line_factor=1.1704,
        space_em=0.2500,
    ),
    "bookman old style": FontMetricData(
        ascent_ratio=0.9100,
        descent_ratio=0.2536,
        line_factor=1.1636,
        space_em=0.2500,
    ),
    "century gothic": FontMetricData(
        ascent_ratio=0.9600,
        descent_ratio=0.2651,
        line_factor=1.2251,
        space_em=0.2773,
    ),
    "palatino linotype": FontMetricData(
        ascent_ratio=0.8900,
        descent_ratio=0.2453,
        line_factor=1.1353,
        space_em=0.2500,
    ),
    "lucida console": FontMetricData(
        ascent_ratio=0.8000,
        descent_ratio=0.2000,
        line_factor=1.0000,
        space_em=0.6000,
    ),
    "impact": FontMetricData(
        ascent_ratio=0.9800,
        descent_ratio=0.2397,
        line_factor=1.2197,
        space_em=0.2500,
    ),
    "franklin gothic medium": FontMetricData(
        ascent_ratio=0.8900,
        descent_ratio=0.2438,
        line_factor=1.1338,
        space_em=0.2800,
    ),
    "symbol": FontMetricData(
        ascent_ratio=0.9600,
        descent_ratio=0.2675,
        line_factor=1.2275,
        space_em=0.2500,
    ),
    "wingdings": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.2200,
        line_factor=1.1000,
        space_em=0.2500,
    ),
    # -----------------------------------------------------------------------
    # East Asian CJK Fonts (Chinese, Japanese, Korean)
    # -----------------------------------------------------------------------
    "simsun": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.1400,
        line_factor=1.1700,
        space_em=0.5000,
        is_cjk=True,
    ),
    "nsimsun": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.1400,
        line_factor=1.1700,
        space_em=0.5000,
        is_cjk=True,
    ),
    "simhei": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.1400,
        line_factor=1.1700,
        space_em=0.5000,
        is_cjk=True,
    ),
    "kaiti": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.1400,
        line_factor=1.1700,
        space_em=0.5000,
        is_cjk=True,
    ),
    "fangsong": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.1400,
        line_factor=1.1700,
        space_em=0.5000,
        is_cjk=True,
    ),
    "microsoft yahei": FontMetricData(
        ascent_ratio=1.0500,
        descent_ratio=0.2800,
        line_factor=1.3300,
        space_em=0.5000,
        is_cjk=True,
    ),
    "dengxian": FontMetricData(
        ascent_ratio=0.9800,
        descent_ratio=0.2700,
        line_factor=1.2500,
        space_em=0.5000,
        is_cjk=True,
    ),
    "pingfang sc": FontMetricData(
        ascent_ratio=1.0500,
        descent_ratio=0.2800,
        line_factor=1.3300,
        space_em=0.5000,
        is_cjk=True,
    ),
    "pingfang": FontMetricData(
        ascent_ratio=1.0500,
        descent_ratio=0.2800,
        line_factor=1.3300,
        space_em=0.5000,
        is_cjk=True,
    ),
    "ms mincho": FontMetricData(
        ascent_ratio=0.8500,
        descent_ratio=0.1500,
        line_factor=1.0000,
        space_em=0.5000,
        is_cjk=True,
    ),
    "ms pmincho": FontMetricData(
        ascent_ratio=0.8500,
        descent_ratio=0.1500,
        line_factor=1.0000,
        space_em=0.5000,
        is_cjk=True,
    ),
    "ms gothic": FontMetricData(
        ascent_ratio=0.8500,
        descent_ratio=0.1500,
        line_factor=1.0000,
        space_em=0.5000,
        is_cjk=True,
    ),
    "ms pgothic": FontMetricData(
        ascent_ratio=0.8500,
        descent_ratio=0.1500,
        line_factor=1.0000,
        space_em=0.5000,
        is_cjk=True,
    ),
    "ms ui gothic": FontMetricData(
        ascent_ratio=0.8500,
        descent_ratio=0.1500,
        line_factor=1.0000,
        space_em=0.5000,
        is_cjk=True,
    ),
    "yu mincho": FontMetricData(
        ascent_ratio=1.3500,
        descent_ratio=0.3800,
        line_factor=1.7300,
        space_em=0.5000,
        is_cjk=True,
    ),
    "yu gothic": FontMetricData(
        ascent_ratio=1.3500,
        descent_ratio=0.3800,
        line_factor=1.7300,
        space_em=0.5000,
        is_cjk=True,
    ),
    "yu gothic light": FontMetricData(
        ascent_ratio=1.3500,
        descent_ratio=0.3800,
        line_factor=1.7300,
        space_em=0.5000,
        is_cjk=True,
    ),
    "meiryo": FontMetricData(
        ascent_ratio=1.2000,
        descent_ratio=0.3000,
        line_factor=1.5000,
        space_em=0.5000,
        is_cjk=True,
    ),
    "malgun gothic": FontMetricData(
        ascent_ratio=1.0500,
        descent_ratio=0.2800,
        line_factor=1.3300,
        space_em=0.5000,
        is_cjk=True,
    ),
    "batang": FontMetricData(
        ascent_ratio=0.9000,
        descent_ratio=0.2500,
        line_factor=1.1500,
        space_em=0.5000,
        is_cjk=True,
    ),
    "gulim": FontMetricData(
        ascent_ratio=0.9000,
        descent_ratio=0.2500,
        line_factor=1.1500,
        space_em=0.5000,
        is_cjk=True,
    ),
    "dotum": FontMetricData(
        ascent_ratio=0.9000,
        descent_ratio=0.2500,
        line_factor=1.1500,
        space_em=0.5000,
        is_cjk=True,
    ),
    "pmingliu": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.1400,
        line_factor=1.1700,
        space_em=0.5000,
        is_cjk=True,
    ),
    "mingliu": FontMetricData(
        ascent_ratio=0.8800,
        descent_ratio=0.1400,
        line_factor=1.1700,
        space_em=0.5000,
        is_cjk=True,
    ),
}

# Localized font aliases
FONT_ALIASES: dict[str, str] = {
    "宋体": "simsun",
    "新宋体": "nsimsun",
    "黑体": "simhei",
    "楷体": "kaiti",
    "仿宋": "fangsong",
    "微软雅黑": "microsoft yahei",
    "等线": "dengxian",
    "苹方": "pingfang sc",
    "苹方-简": "pingfang sc",
    "pingfang": "pingfang sc",
    "ｍｓ 明朝": "ms mincho",
    "ｍｓ ｐ明朝": "ms pmincho",
    "ｍｓ ゴシック": "ms gothic",
    "ｍｓ ｐゴシック": "ms pgothic",
    "游明朝": "yu mincho",
    "游ゴシック": "yu gothic",
    "メイリオ": "meiryo",
    "맑은 고딕": "malgun gothic",
    "바탕": "batang",
    "굴림": "gulim",
    "돋움": "dotum",
    "新細明體": "pmingliu",
    "細明體": "mingliu",
}


def normalize_font_key(name: str | None) -> str:
    """Normalize font family name to canonical lowercase lookup key."""
    if not name:
        return "times new roman"
    clean = str(name).replace('"', "").replace("'", "").strip().lower()
    return FONT_ALIASES.get(clean, clean)


def get_font_metric(font_family: str | None) -> FontMetricData:
    """Retrieve calibrated FontMetricData for a given font family."""
    key = normalize_font_key(font_family)
    return FONT_METRICS_CALIBRATION.get(key, DEFAULT_FONT_METRIC)


def get_line_factor(font_family: str | None) -> float:
    """Return single-space line height factor for a font family."""
    return get_font_metric(font_family).line_factor


def get_space_em(font_family: str | None) -> float:
    """Return standard space character width as fraction of em."""
    return get_font_metric(font_family).space_em


def is_cjk_font(font_family: str | None) -> bool:
    """Check if font is classified as East Asian CJK."""
    return get_font_metric(font_family).is_cjk


def compute_font_metrics(
    font_size: float,
    font_family: str | None,
    bold: bool = False,
    italic: bool = False,
) -> tuple[float, float]:
    """Calculate calibrated (ascent, descent) in points.

    Uses precision ratios calibrated to Carlito/Caladea/Gelasio and standard
    OpenOffice/Word typographic models.
    """
    metric = get_font_metric(font_family)
    ascent = round(float(font_size) * metric.ascent_ratio, 2)
    descent = round(float(font_size) * metric.descent_ratio, 2)
    return ascent, descent


# ---------------------------------------------------------------------------
# Unhinted Advance Width Tables (Headless / Cross-Platform Fallback)
# ---------------------------------------------------------------------------
# Exact unhinted hmtx advances (unitsPerEm = 2048) extracted from the bundled
# SIL OFL Tinos TrueType fonts (metric-compatible stand-in for Times New Roman).
# Keeps headless layout (QGuiApplication.instance() is None) identical to GUI
# unhinted QFontMetricsF measurement across macOS, Linux, and Windows.

_TINOS_UPEM = 2048.0
_TINOS_FAMILIES: frozenset[str] = frozenset(
    {"times new roman", "times", "tinos", "liberation serif"}
)

# Printable ASCII 0x20 (' ') through 0x7E ('~') keyed by (bold, italic)
_TINOS_ASCII_ADVANCES: dict[tuple[bool, bool], tuple[int, ...]] = {
    (False, False): (
        512, 682, 836, 1024, 1024, 1706, 1593, 369, 682, 682, 1024, 1155, 512,
        682, 512, 569, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024,
        1024, 569, 569, 1155, 1155, 1155, 909, 1886, 1479, 1366, 1366, 1479,
        1251, 1139, 1479, 1479, 682, 797, 1479, 1251, 1821, 1479, 1479, 1139,
        1479, 1366, 1139, 1251, 1479, 1479, 1933, 1479, 1479, 1251, 682, 569,
        682, 961, 1024, 682, 909, 1024, 909, 1024, 909, 682, 1024, 1024, 569,
        569, 1024, 569, 1593, 1024, 1024, 1024, 1024, 682, 797, 569, 1024,
        1024, 1479, 1024, 1024, 909, 983, 410, 983, 1108,
    ),
    (True, False): (
        512, 682, 1137, 1024, 1024, 2048, 1706, 569, 682, 682, 1024, 1167, 512,
        682, 512, 569, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024,
        1024, 682, 682, 1167, 1167, 1167, 1024, 1905, 1479, 1366, 1479, 1479,
        1366, 1251, 1593, 1593, 797, 1024, 1593, 1366, 1933, 1479, 1593, 1251,
        1593, 1479, 1139, 1366, 1479, 1479, 2048, 1479, 1479, 1366, 682, 569,
        682, 1190, 1024, 682, 1024, 1139, 909, 1139, 909, 682, 1024, 1139,
        569, 682, 1139, 569, 1706, 1139, 1024, 1139, 1139, 909, 797, 682, 1139,
        1024, 1479, 1024, 1024, 909, 807, 451, 807, 1065,
    ),
    (False, True): (
        512, 682, 860, 1024, 1024, 1706, 1593, 438, 682, 682, 1024, 1382, 512,
        682, 512, 569, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024,
        1024, 682, 682, 1382, 1382, 1382, 1024, 1884, 1251, 1251, 1366, 1479,
        1251, 1251, 1479, 1479, 682, 909, 1366, 1139, 1706, 1366, 1479, 1251,
        1479, 1251, 1024, 1139, 1479, 1251, 1706, 1251, 1139, 1139, 797, 569,
        797, 864, 1024, 682, 1024, 1024, 909, 1024, 909, 569, 1024, 1024, 569,
        569, 909, 569, 1479, 1024, 1024, 1024, 1024, 797, 797, 569, 1024, 909,
        1366, 909, 909, 797, 819, 563, 819, 1108,
    ),
    (True, True): (
        512, 797, 1137, 1024, 1024, 1706, 1593, 569, 682, 682, 1024, 1167, 512,
        682, 512, 569, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024,
        1024, 682, 682, 1167, 1167, 1167, 1024, 1704, 1366, 1366, 1366, 1479,
        1366, 1366, 1479, 1593, 797, 1024, 1366, 1251, 1821, 1479, 1479, 1251,
        1479, 1366, 1139, 1251, 1479, 1366, 1821, 1366, 1251, 1251, 682, 569,
        682, 1167, 1024, 682, 1024, 1024, 909, 1024, 909, 682, 1024, 1139,
        569, 569, 1024, 569, 1593, 1139, 1024, 1024, 1024, 797, 797, 569, 1139,
        909, 1366, 1024, 909, 797, 713, 451, 713, 1167,
    ),
}

_TINOS_EXTRA_ADVANCES: dict[tuple[bool, bool], dict[str, int]] = {
    (False, False): {
        "\u00a0": 512, "\u2013": 1024, "\u2014": 2048, "\u2018": 682,
        "\u2019": 682, "\u201c": 909, "\u201d": 909, "\u2026": 2048,
    },
    (True, False): {
        "\u00a0": 512, "\u2013": 1024, "\u2014": 2048, "\u2018": 682,
        "\u2019": 682, "\u201c": 1024, "\u201d": 1024, "\u2026": 2048,
    },
    (False, True): {
        "\u00a0": 512, "\u2013": 1024, "\u2014": 1821, "\u2018": 682,
        "\u2019": 682, "\u201c": 1139, "\u201d": 1139, "\u2026": 1821,
    },
    (True, True): {
        "\u00a0": 512, "\u2013": 1024, "\u2014": 2048, "\u2018": 682,
        "\u2019": 682, "\u201c": 1024, "\u201d": 1024, "\u2026": 2048,
    },
}


def get_calibrated_char_em(
    ch: str,
    font_family: str | None,
    bold: bool = False,
    italic: bool = False,
) -> float | None:
    """Return exact unhinted em advance for calibrated faces, or None."""
    if not ch:
        return None
    key = normalize_font_key(font_family)
    if key not in _TINOS_FAMILIES:
        return None
    style = (bool(bold), bool(italic))
    code = ord(ch)
    if 0x20 <= code <= 0x7E:
        return _TINOS_ASCII_ADVANCES[style][code - 0x20] / _TINOS_UPEM
    extra = _TINOS_EXTRA_ADVANCES[style].get(ch)
    if extra is not None:
        return extra / _TINOS_UPEM
    return None
