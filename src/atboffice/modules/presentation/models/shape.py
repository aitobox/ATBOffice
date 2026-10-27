"""Shape, line, fill, shadow and geometry models for Lectern."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.presentation.models.text import TextBody


@dataclass
class Fill:
    """Shape fill style."""

    type: str = "solid"  # "none", "solid", "grad", "patt"
    color: str = "accent1"
    alpha: float = 1.0
    stops: list[dict[str, Any]] = field(default_factory=list)  # [{"p": 0.0, "c": "#FFF", "a": 1.0}]
    angle: float = 90.0
    path: str = "lin"  # "lin", "circle"
    pattern: str = ""
    fg: str = ""
    bg: str = ""

    @classmethod
    def none(cls) -> Fill:
        return cls(type="none", color="")

    @classmethod
    def solid(cls, color: str, alpha: float = 1.0) -> Fill:
        return cls(type="solid", color=color, alpha=alpha)

    @classmethod
    def gradient(cls, stops: list[dict[str, Any]], angle: float = 90.0, path: str = "lin") -> Fill:
        return cls(type="grad", stops=stops, angle=angle, path=path)

    @classmethod
    def pattern_fill(cls, prst: str, fg: str, bg: str) -> Fill:
        return cls(type="patt", pattern=prst, fg=fg, bg=bg)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"t": self.type}
        if self.type == "solid":
            d["c"] = self.color
            if self.alpha != 1.0:
                d["a"] = self.alpha
        elif self.type == "grad":
            d["stops"] = copy.deepcopy(self.stops)
            d["ang"] = self.angle
            d["path"] = self.path
        elif self.type == "patt":
            d["prst"] = self.pattern
            d["fg"] = self.fg
            d["bg"] = self.bg
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Fill:
        if not data:
            return cls.none()
        t = data.get("t", "solid")
        if t == "none":
            return cls.none()
        if t == "grad":
            return cls(
                type="grad",
                stops=data.get("stops", []),
                angle=float(data.get("ang", 90.0)),
                path=data.get("path", "lin"),
            )
        if t == "patt":
            return cls(
                type="patt",
                pattern=data.get("prst", ""),
                fg=data.get("fg", ""),
                bg=data.get("bg", ""),
            )
        return cls(
            type="solid",
            color=data.get("c", "accent1"),
            alpha=float(data.get("a", 1.0)),
        )


@dataclass
class Line:
    """Shape outline / line style."""

    type: str = "solid"  # "none", "solid"
    color: str = "tx1"
    width: float = 0.75  # in points
    dash: str = "solid"  # "solid", "dash", "dot"
    tail: dict[str, Any] | None = None
    head: dict[str, Any] | None = None

    @classmethod
    def none(cls) -> Line:
        return cls(type="none", color="")

    def to_dict(self) -> dict[str, Any]:
        if self.type == "none":
            return {"t": "none"}
        d: dict[str, Any] = {"c": self.color, "w": self.width, "dash": self.dash}
        if self.tail:
            d["tail"] = dict(self.tail)
        if self.head:
            d["head"] = dict(self.head)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Line:
        if not data or data.get("t") == "none":
            return cls.none()
        return cls(
            type="solid",
            color=data.get("c", "tx1"),
            width=float(data.get("w", 0.75)),
            dash=data.get("dash", "solid"),
            tail=dict(data.get("tail")) if data.get("tail") else None,
            head=dict(data.get("head")) if data.get("head") else None,
        )


@dataclass
class Shadow:
    """Drop shadow effect."""

    blur: float = 3.0
    dist: float = 1.0
    alpha: float = 0.28
    color: str = "#000000"
    angle: float = 90.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "blur": self.blur,
            "dist": self.dist,
            "a": self.alpha,
            "c": self.color,
            "ang": self.angle,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Shadow | None:
        if not data:
            return None
        return cls(
            blur=float(data.get("blur", 3.0)),
            dist=float(data.get("dist", 1.0)),
            alpha=float(data.get("a", 0.28)),
            color=data.get("c", "#000000"),
            angle=float(data.get("ang", 90.0)),
        )


@dataclass
class PlaceholderInfo:
    """Master placeholder descriptor."""

    # "title", "ctrTitle", "subTitle", "body", "obj", "tbl", "chart", "dt", "ftr", "sldNum"
    type: str
    idx: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "idx": self.idx}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PlaceholderInfo | None:
        if not data or "type" not in data:
            return None
        return cls(type=str(data["type"]), idx=int(data.get("idx", 0)))


@dataclass
class Shape:
    """Universal shape model representing rectangles, text boxes, lines, images, tables, etc."""

    id: str
    type: str = "shape"  # "shape", "text", "line", "image", "table", "group"
    name: str = "Shape"
    geom: str = "rect"
    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 100.0
    rot: float = 0.0
    fill: Fill = field(default_factory=Fill)
    line: Line = field(default_factory=Line)
    shadow: Shadow | None = None
    placeholder: PlaceholderInfo | None = None
    text: TextBody | None = None
    adj: dict[str, Any] | None = None
    kids: list[Shape] = field(default_factory=list)
    media: str | None = None
    crop: dict[str, float] | None = None
    tbl: dict[str, Any] | None = None
    link: dict[str, Any] | None = None
    sa: dict[str, Any] | None = None
    poly: list[list[float]] | None = None
    custom_path: dict[str, Any] | None = None

    def translate(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy
        for kid in self.kids:
            kid.translate(dx, dy)

    def scale(self, sx: float, sy: float) -> None:
        self.x *= sx
        self.y *= sy
        self.w *= sx
        self.h *= sy
        if self.text:
            # Scale text insets
            ins = self.text.insets
            self.text.insets = (ins[0] * sx, ins[1] * sy, ins[2] * sx, ins[3] * sy)
            # Scale run font sizes if needed
            k = min(sx, sy)
            if abs(k - 1.0) > 0.01:
                for p in self.text.paragraphs:
                    for r in p.runs:
                        if r.size is not None:
                            r.size = round(r.size * k, 1)
        for kid in self.kids:
            kid.scale(sx, sy)

    def clone(self) -> Shape:
        return copy.deepcopy(self)

    @property
    def is_diagram(self) -> bool:
        return self.type == "group" and bool(self.sa)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "geom": self.geom,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "w": round(self.w, 2),
            "h": round(self.h, 2),
            "rot": self.rot,
            "fill": self.fill.to_dict(),
            "line": self.line.to_dict(),
        }
        if self.shadow:
            d["shadow"] = self.shadow.to_dict()
        if self.placeholder:
            d["ph"] = self.placeholder.to_dict()
        if self.text:
            d["tx"] = self.text.to_dict()
        if self.adj:
            d["adj"] = dict(self.adj)
        if self.kids:
            d["kids"] = [k.to_dict() for k in self.kids]
        if self.media:
            d["media"] = self.media
        if self.crop:
            d["crop"] = dict(self.crop)
        if self.tbl:
            d["tbl"] = copy.deepcopy(self.tbl)
        if self.link:
            d["link"] = copy.deepcopy(self.link)
        if self.sa:
            d["sa"] = copy.deepcopy(self.sa)
        if self.poly:
            d["poly"] = [list(pt) for pt in self.poly]
        if self.custom_path:
            d["custom_path"] = copy.deepcopy(self.custom_path)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Shape:
        return cls(
            id=str(data.get("id", "")),
            type=data.get("type", "shape"),
            name=data.get("name", "Shape"),
            geom=data.get("geom", "rect"),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            w=float(data.get("w", 100.0)),
            h=float(data.get("h", 100.0)),
            rot=float(data.get("rot", 0.0)),
            fill=Fill.from_dict(data.get("fill")),
            line=Line.from_dict(data.get("line")),
            shadow=Shadow.from_dict(data.get("shadow")),
            placeholder=PlaceholderInfo.from_dict(data.get("ph")),
            text=TextBody.from_dict(data.get("tx")) if "tx" in data else None,
            adj=dict(data.get("adj")) if data.get("adj") else None,
            kids=[cls.from_dict(k) for k in data.get("kids", [])],
            media=data.get("media"),
            crop=dict(data.get("crop")) if data.get("crop") else None,
            tbl=copy.deepcopy(data.get("tbl")),
            link=copy.deepcopy(data.get("link")),
            sa=copy.deepcopy(data.get("sa")),
            poly=[list(pt) for pt in data["poly"]] if "poly" in data and data["poly"] else None,
            custom_path=copy.deepcopy(data.get("custom_path")),
        )
