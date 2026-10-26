"""Design templates, color schemes, and palette resolution for Lectern presentations."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.text import (
    get_default_body_styles,
    get_default_other_styles,
    get_default_title_style,
)


def safe_tr(text: str) -> str:
    """Safe translation fallback when Qt QCoreApplication is not instantiated."""
    try:
        from PySide6.QtCore import QCoreApplication

        return QCoreApplication.translate("LecternDesigns", text)
    except Exception:
        return text


def color_mix(c1: str, c2: str, weight: float) -> str:
    """Mix two hex colors #RRGGBB with a given weight (0.0 to 1.0)."""
    if not c1.startswith("#") or not c2.startswith("#"):
        return c1
    try:
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        w = max(0.0, min(1.0, weight))
        r = int(r1 * (1 - w) + r2 * w)
        g = int(g1 * (1 - w) + g2 * w)
        b = int(b1 * (1 - w) + b2 * w)
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return c1


@dataclass
class ColorScheme:
    """PowerPoint 2003 12-slot color scheme."""

    lt1: str = "#FFFFFF"  # Background
    dk1: str = "#000000"  # Text and lines
    lt2: str = "#808080"  # Shadows
    dk2: str = "#000000"  # Title text
    accent1: str = "#BBE0E3"  # Fills
    accent2: str = "#333399"  # Accent
    hlink: str = "#009999"  # Hyperlink
    folHlink: str = "#99CC00"  # Followed hyperlink
    accent3: str = "#FFFFFF"
    accent4: str = "#000000"
    accent5: str = "#ADADD6"
    accent6: str = "#008A8A"

    def to_dict(self) -> dict[str, str]:
        return {
            "lt1": self.lt1,
            "dk1": self.dk1,
            "lt2": self.lt2,
            "dk2": self.dk2,
            "accent1": self.accent1,
            "accent2": self.accent2,
            "hlink": self.hlink,
            "folHlink": self.folHlink,
            "accent3": self.accent3,
            "accent4": self.accent4,
            "accent5": self.accent5,
            "accent6": self.accent6,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ColorScheme:
        if not data:
            return cls()
        return cls(
            lt1=str(data.get("lt1", "#FFFFFF")),
            dk1=str(data.get("dk1", "#000000")),
            lt2=str(data.get("lt2", "#808080")),
            dk2=str(data.get("dk2", "#000000")),
            accent1=str(data.get("accent1", "#BBE0E3")),
            accent2=str(data.get("accent2", "#333399")),
            hlink=str(data.get("hlink", "#009999")),
            folHlink=str(data.get("folHlink", "#99CC00")),
            accent3=str(data.get("accent3", "#FFFFFF")),
            accent4=str(data.get("accent4", "#000000")),
            accent5=str(data.get("accent5", "#ADADD6")),
            accent6=str(data.get("accent6", "#008A8A")),
        )


def make_scheme(
    lt1: str,
    dk1: str,
    lt2: str,
    dk2: str,
    a1: str,
    a2: str,
    hl: str,
    fh: str,
    a3: str | None = None,
    a4: str | None = None,
    a5: str | None = None,
    a6: str | None = None,
) -> ColorScheme:
    return ColorScheme(
        lt1=lt1,
        dk1=dk1,
        lt2=lt2,
        dk2=dk2,
        accent1=a1,
        accent2=a2,
        hlink=hl,
        folHlink=fh,
        accent3=a3 or color_mix(a1, lt1, 0.35),
        accent4=a4 or color_mix(dk1, lt1, 0.3),
        accent5=a5 or color_mix(a2, lt1, 0.3),
        accent6=a6 or color_mix(hl, dk1, 0.2),
    )


# Color resolution mapping aliases
COLOR_SLOT_MAP = {
    "tx1": "dk1",
    "bg1": "lt1",
    "tx2": "dk2",
    "bg2": "lt2",
}

PRESET_COLORS = {
    "white": "#FFFFFF",
    "black": "#000000",
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "gray": "#808080",
}


def resolve_color(
    c: str | None,
    design: DesignTemplate | None = None,
    fallback: str = "#000000",
) -> str:
    """Resolve a color token or scheme slot to an actual hex color #RRGGBB."""
    if not c:
        return fallback
    if c.startswith("#"):
        return c
    cols = design.colors if design else ColorScheme()
    slot = COLOR_SLOT_MAP.get(c, c)
    if hasattr(cols, slot):
        return getattr(cols, slot)
    if c in PRESET_COLORS:
        return PRESET_COLORS[c]
    return fallback


# Default placeholder bounding box fractions of slide W and H (PowerPoint 2003 master)
DEFAULT_PH_FRACTIONS: dict[str, tuple[float, float, float, float]] = {
    "title": (0.05, 0.04, 0.9, 0.1667),
    "body": (0.05, 0.2333, 0.9, 0.66),
    "ctrTitle": (0.075, 0.3106, 0.85, 0.2144),
    "subTitle": (0.15, 0.5667, 0.7, 0.2556),
    "dt": (0.05, 0.9104, 0.2333, 0.0694),
    "ftr": (0.3417, 0.9104, 0.3167, 0.0694),
    "sldNum": (0.7167, 0.9104, 0.2333, 0.0694),
}


@dataclass
class DesignDefinition:
    """Blueprint definition for a design template."""

    key: str
    name: str
    colors: ColorScheme
    fonts: dict[str, str]
    bg: Fill
    deco_fn: Callable[[float, float], list[Shape]] | None = None
    title_deco_fn: Callable[[float, float], list[Shape]] | None = None
    title_bg: Fill | None = None
    ph_fractions: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    tx_overrides: dict[str, Any] = field(default_factory=dict)
    ctr_title_algn: str = "ctr"
    sub_title_algn: str = "ctr"


@dataclass
class DesignTemplate:
    """Instantiated design template with resolved decoration shapes and frames."""

    id: str
    key: str
    name: str
    colors: ColorScheme
    fonts: dict[str, str]
    bg: Fill
    decorations: list[Shape] = field(default_factory=list)
    title_decorations: list[Shape] | None = None
    title_bg: Fill | None = None
    placeholder_frames: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    text_styles: dict[str, Any] = field(default_factory=dict)
    footer_style: dict[str, Any] = field(default_factory=dict)
    ctr_title_algn: str = "ctr"
    sub_title_algn: str = "ctr"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "key": self.key,
            "name": self.name,
            "colors": self.colors.to_dict(),
            "fonts": dict(self.fonts),
            "bg": self.bg.to_dict(),
            "deco": [s.to_dict() for s in self.decorations],
            "ph": {k: list(v) for k, v in self.placeholder_frames.items()},
            "ctrTitleAlgn": self.ctr_title_algn,
            "subTitleAlgn": self.sub_title_algn,
        }
        if self.title_decorations is not None:
            d["titleDeco"] = [s.to_dict() for s in self.title_decorations]
        if self.title_bg:
            d["titleBg"] = self.title_bg.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DesignTemplate:
        ph_frames = {
            k: (float(v[0]), float(v[1]), float(v[2]), float(v[3]))
            for k, v in data.get("ph", {}).items()
        }
        title_decos = (
            [Shape.from_dict(s) for s in data["titleDeco"]] if "titleDeco" in data else None
        )
        title_bg = Fill.from_dict(data.get("titleBg")) if "titleBg" in data else None
        return cls(
            id=str(data.get("id", f"dsn_{uuid.uuid4().hex[:8]}")),
            key=str(data.get("key", "default")),
            name=str(data.get("name", "Default Design")),
            colors=ColorScheme.from_dict(data.get("colors")),
            fonts=dict(data.get("fonts", {"major": "Arial", "minor": "Arial"})),
            bg=Fill.from_dict(data.get("bg")),
            decorations=[Shape.from_dict(s) for s in data.get("deco", [])],
            title_decorations=title_decos,
            title_bg=title_bg,
            placeholder_frames=ph_frames,
            ctr_title_algn=str(data.get("ctrTitleAlgn", "ctr")),
            sub_title_algn=str(data.get("subTitleAlgn", "ctr")),
        )


def _make_deco(
    geom: str,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: Fill,
    line: Line | None = None,
    rot: float = 0.0,
    adj: dict[str, Any] | None = None,
) -> Shape:
    return Shape(
        id=f"d_{uuid.uuid4().hex[:6]}",
        type="shape",
        name="Decoration",
        geom=geom,
        x=x,
        y=y,
        w=w,
        h=h,
        rot=rot,
        fill=fill,
        line=line or Line.none(),
        adj=adj,
    )


# Helper deco lambdas
def _azure_deco(w: float, h: float) -> list[Shape]:
    grad1 = Fill.gradient([{"p": 0.0, "c": "#2A4E8F"}, {"p": 1.0, "c": "#1F3A6E"}], angle=90.0)
    return [
        _make_deco("rect", 0.0, 0.0, w, h * 0.2, grad1),
        _make_deco("rect", 0.0, h * 0.2, w, h * 0.008, Fill.solid("accent2")),
    ]


def _azure_title_deco(w: float, h: float) -> list[Shape]:
    grad1 = Fill.gradient([{"p": 0.0, "c": "#2A4E8F"}, {"p": 1.0, "c": "#1F3A6E"}], angle=90.0)
    return [
        _make_deco("rect", 0.0, h * 0.3, w, h * 0.26, grad1),
        _make_deco("rect", 0.0, h * 0.56, w, h * 0.008, Fill.solid("accent2")),
    ]


def _night_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("star4", w * 0.82, h * 0.06, w * 0.035, w * 0.035, Fill.solid("#FFF2CC", 0.9)),
        _make_deco("star4", w * 0.90, h * 0.14, w * 0.022, w * 0.022, Fill.solid("#FFF2CC", 0.9)),
        _make_deco("ellipse", w * 0.62, h * 0.88, w * 0.7, h * 0.5, Fill.solid("#FFFFFF", 0.04)),
    ]


def _meadow_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("rect", 0.0, h * 0.88, w, h * 0.12, Fill.solid("#9CCB5E", 0.55)),
        _make_deco("rect", 0.0, h * 0.92, w, h * 0.08, Fill.solid("#5E9E3A", 0.65)),
    ]


def _ember_deco(w: float, h: float) -> list[Shape]:
    g = Fill.gradient([{"p": 0.0, "c": "#C1272D"}, {"p": 1.0, "c": "#F39C12"}], angle=0.0)
    return [
        _make_deco("rect", 0.0, h * 0.94, w, h * 0.06, g),
        _make_deco("rect", 0.0, h * 0.925, w, h * 0.008, Fill.solid("accent1", 0.7)),
        _make_deco("rect", w * 0.05, h * 0.205, w * 0.9, h * 0.004, Fill.solid("accent1")),
    ]


def _ember_title_deco(w: float, h: float) -> list[Shape]:
    g0 = Fill.gradient([{"p": 0.0, "c": "#C1272D"}, {"p": 1.0, "c": "#F39C12"}], angle=0.0)
    g90 = Fill.gradient([{"p": 0.0, "c": "#F39C12"}, {"p": 1.0, "c": "#C1272D"}], angle=90.0)
    return [
        _make_deco("rect", 0.0, h * 0.94, w, h * 0.06, g0),
        _make_deco("rect", 0.0, 0.0, w * 0.035, h * 0.94, g90),
    ]


def _graphite_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco(
            "parallelogram",
            -w * 0.04,
            h * 0.03,
            w * 0.24,
            h * 0.022,
            Fill.solid("accent1"),
            adj={"adj": 60000},
        ),
        _make_deco("rect", w * 0.05, h * 0.215, w * 0.9, h * 0.0025, Fill.solid("#FFFFFF", 0.25)),
    ]


def _blueprint_deco(w: float, h: float) -> list[Shape]:
    line = Line(color="#B3D4F5", width=1.0, dash="solid")
    return [
        _make_deco("rect", 0.0, 0.0, w, h, Fill.pattern_fill("smGrid", fg="#3D6FA8", bg="#1D4E89")),
        _make_deco("rect", w * 0.03, h * 0.04, w * 0.94, h * 0.92, Fill.none(), line),
    ]


def _capsule_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco(
            "roundRect",
            w * 0.68,
            h * 0.035,
            w * 0.2,
            h * 0.05,
            Fill.solid("accent1"),
            adj={"adj": 50000},
        ),
        _make_deco(
            "roundRect",
            w * 0.84,
            h * 0.035,
            w * 0.12,
            h * 0.05,
            Fill.solid("accent2"),
            adj={"adj": 50000},
        ),
        _make_deco("rect", 0.0, h * 0.965, w, h * 0.035, Fill.solid("accent1")),
    ]


def _ocean_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("rect", 0.0, h * 0.88, w, h * 0.12, Fill.solid("#2A9D8F", 0.45)),
        _make_deco("rect", 0.0, h * 0.93, w, h * 0.07, Fill.solid("#1D7C99", 0.60)),
    ]


def _parchment_deco(w: float, h: float) -> list[Shape]:
    line = Line(color="#8C5A2B", width=0.75, dash="solid")
    return [
        _make_deco("rect", w * 0.05, h * 0.205, w * 0.9, h * 0.0035, Fill.solid("accent2")),
        _make_deco("rect", w * 0.02, h * 0.027, w * 0.96, h * 0.946, Fill.none(), line),
    ]


def _pixel_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("rect", w * 0.88, h * 0.03, w * 0.025, w * 0.025, Fill.solid("accent1", 0.9)),
        _make_deco("rect", w * 0.92, h * 0.03, w * 0.025, w * 0.025, Fill.solid("accent2", 0.9)),
        _make_deco("rect", w * 0.88, h * 0.07, w * 0.025, w * 0.025, Fill.solid("accent3", 0.9)),
        _make_deco("rect", w * 0.05, h * 0.21, w * 0.62, h * 0.004, Fill.solid("accent1")),
    ]


def _crimson_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("rect", 0.0, 0.0, w * 0.03, h, Fill.solid("accent1")),
        _make_deco("rect", w * 0.08, h * 0.205, w * 0.87, h * 0.0025, Fill.solid("accent1")),
    ]


def _crimson_title_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("rect", 0.0, 0.0, w * 0.03, h, Fill.solid("accent1")),
        _make_deco("rect", w * 0.03, h * 0.6, w * 0.97, h * 0.006, Fill.solid("accent1")),
    ]


def _glass_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco(
            "rect", w * 0.55, -h * 0.1, w * 0.6, h * 0.7, Fill.solid("#FFFFFF", 0.08), rot=18.0
        ),
        _make_deco(
            "rect", w * 0.70, h * 0.40, w * 0.5, h * 0.8, Fill.solid("#FFFFFF", 0.06), rot=-12.0
        ),
    ]


def _radial_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("ellipse", w * 0.3, h * 0.95, w * 0.4, h * 0.012, Fill.solid("#7FB3FF", 0.35)),
    ]


def _evergreen_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("rect", w * 0.05, h * 0.07, w * 0.05, h * 0.008, Fill.solid("accent2")),
        _make_deco("rect", w * 0.05, h * 0.905, w * 0.9, h * 0.002, Fill.solid("lt2")),
    ]


def _evergreen_title_deco(w: float, h: float) -> list[Shape]:
    return [
        _make_deco("rect", w * 0.6, 0.0, w * 0.4, h, Fill.solid("tx2")),
        _make_deco("rect", w * 0.6, 0.0, w * 0.006, h, Fill.solid("accent2")),
    ]


# Definition table for all 15 built-in designs
DESIGNS: list[DesignDefinition] = [
    # 1. Default Design
    DesignDefinition(
        key="default",
        name="Default Design",
        colors=make_scheme(
            "#FFFFFF",
            "#000000",
            "#808080",
            "#000000",
            "#BBE0E3",
            "#339999",
            "#009999",
            "#99CC00",
        ),
        fonts={"major": "Arial", "minor": "Arial"},
        bg=Fill.solid("bg1"),
    ),
    # 2. Azure Horizon
    DesignDefinition(
        key="azure",
        name="Azure Horizon",
        colors=make_scheme(
            "#FFFFFF",
            "#1B2A41",
            "#7F93B2",
            "#FFFFFF",
            "#4A7BC8",
            "#E0A526",
            "#2D6BB5",
            "#8E7CC3",
        ),
        fonts={"major": "Trebuchet MS", "minor": "Verdana"},
        bg=Fill.gradient([{"p": 0.0, "c": "#FFFFFF"}, {"p": 1.0, "c": "#DCE8F7"}], angle=90.0),
        deco_fn=_azure_deco,
        title_deco_fn=_azure_title_deco,
        ph_fractions={
            "title": (0.05, 0.025, 0.9, 0.15),
            "body": (0.07, 0.26, 0.86, 0.63),
            "ctrTitle": (0.075, 0.31, 0.85, 0.24),
            "subTitle": (0.15, 0.6, 0.7, 0.2),
        },
        tx_overrides={"title": {"color": "lt1", "b": True}, "body_bu": "accent2"},
    ),
    # 3. Night Sky
    DesignDefinition(
        key="night",
        name="Night Sky",
        colors=make_scheme(
            "#0B1633",
            "#FFFFFF",
            "#06102A",
            "#FFE599",
            "#3D6CB3",
            "#FFD966",
            "#9FC5F8",
            "#C9DAF8",
        ),
        fonts={"major": "Georgia", "minor": "Verdana"},
        bg=Fill.gradient([{"p": 0.0, "c": "#0B1633"}, {"p": 1.0, "c": "#22427A"}], angle=90.0),
        deco_fn=_night_deco,
        tx_overrides={"title_algn": "l", "body_bu_char": "✦", "body_bu_color": "accent2"},
    ),
    # 4. Meadow
    DesignDefinition(
        key="meadow",
        name="Meadow",
        colors=make_scheme(
            "#F7FBEF",
            "#22331A",
            "#A7C08F",
            "#2F5E1E",
            "#7DB04B",
            "#E7A93B",
            "#3B7D2A",
            "#8A9A5B",
        ),
        fonts={"major": "Century Gothic", "minor": "Century Gothic"},
        bg=Fill.solid("bg1"),
        deco_fn=_meadow_deco,
        ph_fractions={"body": (0.05, 0.2333, 0.9, 0.56)},
        tx_overrides={"title_algn": "l", "body_bu_char": "●", "body_bu_color": "accent1"},
    ),
    # 5. Ember
    DesignDefinition(
        key="ember",
        name="Ember",
        colors=make_scheme(
            "#FFF8F0",
            "#3A2414",
            "#C9A88C",
            "#8C2D04",
            "#E8641C",
            "#C1272D",
            "#B5651D",
            "#8E6C4F",
        ),
        fonts={"major": "Franklin Gothic Medium", "minor": "Arial"},
        bg=Fill.solid("bg1"),
        deco_fn=_ember_deco,
        title_deco_fn=_ember_title_deco,
        ph_fractions={"body": (0.05, 0.24, 0.9, 0.64)},
        tx_overrides={"title_algn": "l", "body_bu_char": "■", "body_bu_color": "accent1"},
    ),
    # 6. Graphite
    DesignDefinition(
        key="graphite",
        name="Graphite",
        colors=make_scheme(
            "#2B2D31",
            "#E8EAED",
            "#17181B",
            "#FFFFFF",
            "#F28C28",
            "#58A6FF",
            "#79C0FF",
            "#B1BAC4",
        ),
        fonts={"major": "Arial", "minor": "Arial"},
        bg=Fill.gradient([{"p": 0.0, "c": "#34373D"}, {"p": 1.0, "c": "#232428"}], angle=90.0),
        deco_fn=_graphite_deco,
        tx_overrides={
            "title_algn": "l",
            "title_b": True,
            "body_bu_char": "▸",
            "body_bu_color": "accent1",
        },
    ),
    # 7. Blueprint
    DesignDefinition(
        key="blueprint",
        name="Blueprint",
        colors=make_scheme(
            "#1D4E89",
            "#E8F1FB",
            "#123359",
            "#FFFFFF",
            "#7FB3E6",
            "#FFD24D",
            "#B3D4F5",
            "#9DBCE0",
        ),
        fonts={"major": "Courier New", "minor": "Arial"},
        bg=Fill.solid("bg1"),
        deco_fn=_blueprint_deco,
        tx_overrides={
            "title_algn": "l",
            "title_b": True,
            "body_bu_char": "–",
            "body_bu_color": "accent2",
        },
    ),
    # 8. Capsule
    DesignDefinition(
        key="capsule",
        name="Capsule",
        colors=make_scheme(
            "#FFFFFF",
            "#1E2D33",
            "#9FB4BA",
            "#21545F",
            "#2BA6A0",
            "#9BC53D",
            "#1F7A8C",
            "#7E9C9F",
        ),
        fonts={"major": "Trebuchet MS", "minor": "Trebuchet MS"},
        bg=Fill.solid("bg1"),
        deco_fn=_capsule_deco,
        ph_fractions={"title": (0.05, 0.06, 0.62, 0.15)},
        tx_overrides={"title_algn": "l", "body_bu_char": "●", "body_bu_color": "accent1"},
    ),
    # 9. Ocean Wave
    DesignDefinition(
        key="ocean",
        name="Ocean Wave",
        colors=make_scheme(
            "#EEF8FB",
            "#0E2F3A",
            "#8FB9C4",
            "#0E4C5C",
            "#2A9D8F",
            "#F4A261",
            "#1D7C99",
            "#7A9EA8",
        ),
        fonts={"major": "Tahoma", "minor": "Tahoma"},
        bg=Fill.gradient([{"p": 0.0, "c": "#F4FBFD"}, {"p": 1.0, "c": "#C7E6EE"}], angle=90.0),
        deco_fn=_ocean_deco,
        ph_fractions={"body": (0.05, 0.2333, 0.9, 0.58)},
        tx_overrides={"body_bu_char": "•", "body_bu_color": "accent1"},
    ),
    # 10. Parchment
    DesignDefinition(
        key="parchment",
        name="Parchment",
        colors=make_scheme(
            "#F4ECD8",
            "#3B2A1A",
            "#B8A27F",
            "#5A3A1A",
            "#C8A96B",
            "#8C5A2B",
            "#7B3F00",
            "#8A7A60",
        ),
        fonts={"major": "Book Antiqua", "minor": "Georgia"},
        bg=Fill.gradient(
            [{"p": 0.0, "c": "#F7F0DE"}, {"p": 1.0, "c": "#E6D7B5"}], angle=0.0, path="circle"
        ),
        deco_fn=_parchment_deco,
        tx_overrides={"body_bu_char": "❧", "body_bu_color": "accent2"},
    ),
    # 11. Pixel Mosaic
    DesignDefinition(
        key="pixel",
        name="Pixel Mosaic",
        colors=make_scheme(
            "#FFFFFF",
            "#1A2733",
            "#A0AEBB",
            "#1F4E79",
            "#2E86C1",
            "#28B463",
            "#1B4F72",
            "#7F8C8D",
        ),
        fonts={"major": "Verdana", "minor": "Verdana"},
        bg=Fill.solid("bg1"),
        deco_fn=_pixel_deco,
        ph_fractions={"title": (0.05, 0.04, 0.78, 0.1667)},
        tx_overrides={"title_algn": "l", "body_bu_char": "■", "body_bu_color": "accent2"},
    ),
    # 12. Crimson Edge
    DesignDefinition(
        key="crimson",
        name="Crimson Edge",
        colors=make_scheme(
            "#FFFFFF",
            "#262626",
            "#A6A6A6",
            "#A4161A",
            "#A4161A",
            "#495057",
            "#0B6E99",
            "#6C757D",
        ),
        fonts={"major": "Georgia", "minor": "Arial"},
        bg=Fill.solid("bg1"),
        deco_fn=_crimson_deco,
        title_deco_fn=_crimson_title_deco,
        ph_fractions={
            "title": (0.08, 0.04, 0.87, 0.1667),
            "body": (0.08, 0.2333, 0.87, 0.66),
            "ctrTitle": (0.08, 0.34, 0.84, 0.24),
            "subTitle": (0.08, 0.63, 0.84, 0.2),
            "dt": (0.08, 0.9104, 0.2, 0.0694),
        },
        tx_overrides={"title_algn": "l", "body_bu_char": "▪", "body_bu_color": "accent1"},
        ctr_title_algn="l",
        sub_title_algn="l",
    ),
    # 13. Layered Glass
    DesignDefinition(
        key="glass",
        name="Layered Glass",
        colors=make_scheme(
            "#3A6EA5",
            "#FFFFFF",
            "#244A73",
            "#FFFFFF",
            "#9CC3EB",
            "#FFD166",
            "#CFE4FA",
            "#B8D0EA",
        ),
        fonts={"major": "Tahoma", "minor": "Tahoma"},
        bg=Fill.gradient([{"p": 0.0, "c": "#2F5F94"}, {"p": 1.0, "c": "#6A9FD4"}], angle=45.0),
        deco_fn=_glass_deco,
        tx_overrides={"body_bu_color": "accent2"},
    ),
    # 14. Radial Glow
    DesignDefinition(
        key="radial",
        name="Radial Glow",
        colors=make_scheme(
            "#0D1F3C",
            "#DCE6F2",
            "#081428",
            "#FFFFFF",
            "#7FB3FF",
            "#FFC857",
            "#A9CBFF",
            "#8FA3BF",
        ),
        fonts={"major": "Arial", "minor": "Arial"},
        bg=Fill.gradient(
            [{"p": 0.0, "c": "#2E5C9A"}, {"p": 1.0, "c": "#0D1F3C"}], angle=0.0, path="circle"
        ),
        deco_fn=_radial_deco,
        tx_overrides={"body_bu_color": "accent1"},
    ),
    # 15. Evergreen
    DesignDefinition(
        key="evergreen",
        name="Evergreen",
        colors=make_scheme(
            "#FBF8F3",
            "#2B2622",
            "#E9E2D7",
            "#1F4038",
            "#2F6B5B",
            "#C9803A",
            "#3F6E8C",
            "#8C7A66",
        ),
        fonts={"major": "Georgia", "minor": "Calibri"},
        bg=Fill.solid("bg1"),
        deco_fn=_evergreen_deco,
        title_deco_fn=_evergreen_title_deco,
        ph_fractions={
            "title": (0.05, 0.09, 0.9, 0.13),
            "body": (0.05, 0.26, 0.9, 0.61),
            "ctrTitle": (0.06, 0.25, 0.48, 0.3),
            "subTitle": (0.06, 0.57, 0.48, 0.16),
        },
        tx_overrides={"title_algn": "l", "body_bu_color": "accent2"},
        ctr_title_algn="l",
        sub_title_algn="l",
    ),
]


def build_design(key: str, w: float, h: float) -> DesignTemplate:
    """Build a concrete DesignTemplate scaled for a specific slide size (W, H)."""
    defn = next((d for d in DESIGNS if d.key == key), DESIGNS[0])
    ph_dict = dict(DEFAULT_PH_FRACTIONS)
    ph_dict.update(defn.ph_fractions)

    concrete_ph: dict[str, tuple[float, float, float, float]] = {}
    for ph_key, (fx, fy, fw, fh) in ph_dict.items():
        concrete_ph[ph_key] = (
            round(w * fx, 2),
            round(h * fy, 2),
            round(w * fw, 2),
            round(h * fh, 2),
        )

    decos = defn.deco_fn(w, h) if defn.deco_fn else []
    title_decos = defn.title_deco_fn(w, h) if defn.title_deco_fn else None

    # Title & Body text levels with possible template overrides
    title_styles = get_default_title_style()
    body_styles = get_default_body_styles()
    other_styles = get_default_other_styles()

    if defn.tx_overrides:
        if "title_algn" in defn.tx_overrides:
            title_styles[0].algn = defn.tx_overrides["title_algn"]
        if "title_b" in defn.tx_overrides:
            title_styles[0].r_pr["b"] = defn.tx_overrides["title_b"]
        for bs in body_styles:
            if "body_bu_color" in defn.tx_overrides:
                bs.bullet.color = defn.tx_overrides["body_bu_color"]
            if "body_bu_char" in defn.tx_overrides:
                bs.bullet.char = defn.tx_overrides["body_bu_char"]

    # Scale fonts if slide is smaller than 720x540
    tk = min(1.0, w / 720.0, h / 540.0)
    if tk < 0.999:
        for st in title_styles + body_styles + other_styles:
            if "sz" in st.r_pr:
                st.r_pr["sz"] = round(st.r_pr["sz"] * tk, 1)
            st.mar_l = round(st.mar_l * tk, 2)
            st.indent = round(st.indent * tk, 2)

    return DesignTemplate(
        id=f"dsn_{uuid.uuid4().hex[:8]}",
        key=defn.key,
        name=defn.name,
        colors=copy.deepcopy(defn.colors),
        fonts=copy.deepcopy(defn.fonts),
        bg=copy.deepcopy(defn.bg),
        decorations=decos,
        title_decorations=title_decos,
        title_bg=copy.deepcopy(defn.title_bg),
        placeholder_frames=concrete_ph,
        text_styles={
            "title": [s.to_dict() for s in title_styles],
            "body": [s.to_dict() for s in body_styles],
            "other": [s.to_dict() for s in other_styles],
        },
        footer_style={"algn": "l", "rPr": {"sz": round(14.0 * tk, 1), "color": "tx1"}},
        ctr_title_algn=defn.ctr_title_algn,
        sub_title_algn=defn.sub_title_algn,
    )
