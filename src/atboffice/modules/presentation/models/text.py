"""Text and typography models for Lectern presentations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BulletInfo:
    """Bullet formatting for paragraphs."""

    type: str = "none"  # "none", "char", "auto"
    char: str = "•"
    color: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"t": self.type}
        if self.type == "char":
            d["ch"] = self.char
        if self.color:
            d["c"] = self.color
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BulletInfo:
        if not data:
            return cls(type="none")
        t = data.get("t", "none")
        ch = data.get("ch", "•")
        c = data.get("c")
        return cls(type=t, char=ch, color=c)


@dataclass
class TextStyleLevel:
    """Paragraph and character formatting defaults for an outline level."""

    algn: str = "l"  # "l", "ctr", "r", "just"
    mar_l: float = 0.0
    indent: float = 0.0
    ln_spc: float = 1.0  # Percentage or multiple
    spc_bef: float = 0.0
    spc_aft: float = 0.0
    bullet: BulletInfo = field(default_factory=BulletInfo)
    r_pr: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "algn": self.algn,
            "marL": self.mar_l,
            "indent": self.indent,
            "lnSpc": {"pct": int(self.ln_spc * 100)},
            "spcBef": {"pct": int(self.spc_bef * 100)},
            "spcAft": {"pct": int(self.spc_aft * 100)},
            "bu": self.bullet.to_dict(),
            "rPr": dict(self.r_pr),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TextStyleLevel:
        if not data:
            return cls()
        ln_pct = data.get("lnSpc", {}).get("pct", 100) if isinstance(data.get("lnSpc"), dict) else 100
        bef_pct = data.get("spcBef", {}).get("pct", 0) if isinstance(data.get("spcBef"), dict) else 0
        aft_pct = data.get("spcAft", {}).get("pct", 0) if isinstance(data.get("spcAft"), dict) else 0
        return cls(
            algn=data.get("algn", "l"),
            mar_l=float(data.get("marL", 0.0)),
            indent=float(data.get("indent", 0.0)),
            ln_spc=ln_pct / 100.0,
            spc_bef=bef_pct / 100.0,
            spc_aft=aft_pct / 100.0,
            bullet=BulletInfo.from_dict(data.get("bu")),
            r_pr=dict(data.get("rPr", {})),
        )


# Default text formatting for PowerPoint 2003 master
BODY_BULLETS = ["•", "–", "•", "–", "»", "•", "•", "•", "•"]
BODY_SIZES = [32.0, 28.0, 24.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0]
BODY_MARL = [27.0, 58.5, 90.0, 126.0, 162.0, 198.0, 234.0, 270.0, 306.0]
BODY_INDENT = [-27.0, -22.5, -18.0, -18.0, -18.0, -18.0, -18.0, -18.0, -18.0]


def get_default_title_style() -> list[TextStyleLevel]:
    return [
        TextStyleLevel(
            algn="ctr",
            mar_l=0.0,
            indent=0.0,
            ln_spc=1.0,
            spc_bef=0.0,
            spc_aft=0.0,
            bullet=BulletInfo(type="none"),
            r_pr={"font": "+mj", "sz": 44.0, "color": "tx2"},
        )
    ]


def get_default_body_styles() -> list[TextStyleLevel]:
    styles: list[TextStyleLevel] = []
    for i in range(9):
        styles.append(
            TextStyleLevel(
                algn="l",
                mar_l=BODY_MARL[i],
                indent=BODY_INDENT[i],
                ln_spc=1.0,
                spc_bef=0.2,
                spc_aft=0.0,
                bullet=BulletInfo(type="char", char=BODY_BULLETS[i]),
                r_pr={"font": "+mn", "sz": BODY_SIZES[i], "color": "tx1"},
            )
        )
    return styles


def get_default_other_styles() -> list[TextStyleLevel]:
    styles: list[TextStyleLevel] = []
    for i in range(9):
        styles.append(
            TextStyleLevel(
                algn="l",
                mar_l=float(i * 36),
                indent=0.0,
                ln_spc=1.0,
                spc_bef=0.0,
                spc_aft=0.0,
                bullet=BulletInfo(type="none"),
                r_pr={"font": "+mn", "sz": 18.0, "color": "tx1"},
            )
        )
    return styles


@dataclass
class TextRun:
    """Individual formatted span of text within a paragraph."""

    text: str = ""
    font: str | None = None
    font_ea: str | None = None
    size: float | None = None
    color: str | None = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    field: str | None = None  # "dt", "sldNum", "ftr"
    link: str | None = None
    baseline: int = 0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"t": self.text}
        if self.font:
            d["font"] = self.font
        if self.font_ea:
            d["fontEA"] = self.font_ea
        if self.size is not None:
            d["sz"] = self.size
        if self.color:
            d["color"] = self.color
        if self.bold:
            d["b"] = True
        if self.italic:
            d["i"] = True
        if self.underline:
            d["u"] = True
        if self.strike:
            d["strike"] = True
        if self.field:
            d["fld"] = self.field
        if self.link:
            d["link"] = self.link
        if self.baseline != 0:
            d["base"] = self.baseline
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TextRun:
        if not data:
            return cls()
        return cls(
            text=str(data.get("t", "")),
            font=data.get("font"),
            font_ea=data.get("fontEA"),
            size=float(data["sz"]) if "sz" in data and data["sz"] is not None else None,
            color=data.get("color"),
            bold=bool(data.get("b", False)),
            italic=bool(data.get("i", False)),
            underline=bool(data.get("u", False)),
            strike=bool(data.get("strike", False)),
            field=data.get("fld"),
            link=data.get("link"),
            baseline=int(data.get("base", 0)),
        )


@dataclass
class Paragraph:
    """Paragraph with an outline level (0-8), properties, and runs."""

    level: int = 0
    props: dict[str, Any] = field(default_factory=dict)
    runs: list[TextRun] = field(default_factory=list)
    end_props: dict[str, Any] = field(default_factory=dict)

    @property
    def plain_text(self) -> str:
        return "".join(r.text for r in self.runs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lvl": self.level,
            "pp": dict(self.props),
            "rs": [r.to_dict() for r in self.runs],
            "end": dict(self.end_props),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Paragraph:
        if not data:
            return cls()
        return cls(
            level=int(data.get("lvl", 0)),
            props=dict(data.get("pp", {})),
            runs=[TextRun.from_dict(r) for r in data.get("rs", [])],
            end_props=dict(data.get("end", {})),
        )


@dataclass
class TextBody:
    """Text container for shapes and placeholders."""

    anchor: str = "t"  # "t", "ctr", "b"
    wrap: bool = True
    autofit: str = "none"  # "none", "norm", "shape"
    insets: tuple[float, float, float, float] = (7.2, 3.6, 7.2, 3.6)  # left, top, right, bottom pt
    paragraphs: list[Paragraph] = field(default_factory=list)
    vert: str | None = None  # None or "vert"

    @property
    def plain_text(self) -> str:
        return "\n".join(p.plain_text for p in self.paragraphs)

    def is_empty(self) -> bool:
        return not self.paragraphs or all(len(p.plain_text) == 0 for p in self.paragraphs)

    def set_plain_text(self, text: str) -> None:
        lines = str(text).split("\n")
        self.paragraphs = [
            Paragraph(level=0, runs=[TextRun(text=line)] if line else [])
            for line in lines
        ]

    @classmethod
    def create_empty(cls) -> TextBody:
        return cls(paragraphs=[Paragraph(level=0, runs=[])])

    @classmethod
    def from_plain_text(cls, text: str, anchor: str = "t", wrap: bool = True) -> TextBody:
        tb = cls(anchor=anchor, wrap=wrap)
        tb.set_plain_text(text)
        return tb

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "anchor": self.anchor,
            "wrap": self.wrap,
            "autofit": self.autofit,
            "ins": list(self.insets),
            "ps": [p.to_dict() for p in self.paragraphs],
        }
        if self.vert:
            d["vert"] = self.vert
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TextBody:
        if not data:
            return cls.create_empty()
        ins = tuple(data.get("ins", [7.2, 3.6, 7.2, 3.6]))
        return cls(
            anchor=data.get("anchor", "t"),
            wrap=bool(data.get("wrap", True)),
            autofit=data.get("autofit", "none"),
            insets=(float(ins[0]), float(ins[1]), float(ins[2]), float(ins[3])),
            paragraphs=[Paragraph.from_dict(p) for p in data.get("ps", [])],
            vert=data.get("vert"),
        )
