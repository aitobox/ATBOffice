"""DrawingML chart data models, type definitions, and default palettes."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

CH_PALETTE = [
    "#4472C4",
    "#ED7D31",
    "#A5A5A5",
    "#FFC000",
    "#5B9BD5",
    "#70AD47",
    "#264478",
    "#9E480E",
    "#636363",
    "#997300",
    "#255E91",
    "#43682B",
]

# 17 DrawingML chart types
CH_KINDS: list[tuple[str, str]] = [
    ("col", "Clustered Column"),
    ("colStacked", "Stacked Column"),
    ("colPct", "100% Stacked Column"),
    ("bar", "Clustered Bar"),
    ("barStacked", "Stacked Bar"),
    ("barPct", "100% Stacked Bar"),
    ("line", "Line"),
    ("lineMarkers", "Line with Markers"),
    ("area", "Area"),
    ("areaStacked", "Stacked Area"),
    ("areaPct", "100% Stacked Area"),
    ("pie", "Pie"),
    ("doughnut", "Doughnut"),
    ("scatter", "XY (Scatter)"),
    ("bubble", "Bubble"),
    ("radar", "Radar"),
    ("radarFilled", "Filled Radar"),
]


@dataclass
class SeriesData:
    """Represents a single data series in a chart."""

    name: str = ""
    vals: list[float] = field(default_factory=list)
    color: str = ""
    xs: list[float] = field(default_factory=list)
    sizes: list[float] = field(default_factory=list)
    fill: dict[str, Any] | None = None
    line: dict[str, Any] | None = None
    marker: dict[str, Any] | None = None
    lbl: dict[str, Any] | None = None
    smooth: bool = False
    overlay: bool = False
    expl: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "vals": list(self.vals),
        }
        if self.color:
            d["color"] = self.color
        if self.xs:
            d["xs"] = list(self.xs)
        if self.sizes:
            d["sizes"] = list(self.sizes)
        if self.fill:
            d["fill"] = copy.deepcopy(self.fill)
        if self.line:
            d["line"] = copy.deepcopy(self.line)
        if self.marker:
            d["marker"] = copy.deepcopy(self.marker)
        if self.lbl:
            d["lbl"] = copy.deepcopy(self.lbl)
        if self.smooth:
            d["smooth"] = True
        if self.overlay:
            d["overlay"] = True
        if self.expl:
            d["expl"] = self.expl
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SeriesData:
        return cls(
            name=str(data.get("name", "")),
            vals=[float(v) for v in data.get("vals", []) if v is not None],
            color=str(data.get("color", "")),
            xs=[float(x) for x in data.get("xs", []) if x is not None],
            sizes=[float(s) for s in data.get("sizes", []) if s is not None],
            fill=copy.deepcopy(data.get("fill")),
            line=copy.deepcopy(data.get("line")),
            marker=copy.deepcopy(data.get("marker")),
            lbl=copy.deepcopy(data.get("lbl")),
            smooth=bool(data.get("smooth", False)),
            overlay=bool(data.get("overlay", False)),
            expl=float(data.get("expl", 0.0)),
        )


@dataclass
class ChartData:
    """Universal DrawingML chart model."""

    v: int = 2
    kind: str = "col"
    title: str = ""
    title_tx: dict[str, Any] = field(default_factory=dict)
    legend: str = "r"  # "r", "b", "t", "l", "none"
    grid_y: bool = True
    labels: bool = False
    cats: list[str] = field(default_factory=list)
    series: list[SeriesData] = field(default_factory=list)
    ax: dict[str, Any] = field(default_factory=dict)
    fsz: float = 10.0
    bg: dict[str, Any] | None = None
    border: dict[str, Any] | None = None
    pie_colors: list[str] = field(default_factory=list)
    embedded_workbook: bytes | None = None

    @classmethod
    def create_sample(cls, kind: str = "col") -> ChartData:
        """Create a standard default chart with 4 categories and 3 series."""
        cats = ["1st Qtr", "2nd Qtr", "3rd Qtr", "4th Qtr"]
        series = [
            SeriesData(name="East", vals=[20.4, 27.4, 90.0, 20.4], color=CH_PALETTE[0]),
            SeriesData(name="West", vals=[30.6, 38.6, 34.6, 31.6], color=CH_PALETTE[1]),
            SeriesData(name="North", vals=[45.9, 46.9, 45.0, 43.9], color=CH_PALETTE[2]),
        ]
        return cls(
            v=2,
            kind=kind,
            title="",
            legend="r",
            grid_y=True,
            labels=False,
            cats=cats,
            series=series,
            ax={
                "c": {"tick": "out", "rev": False},
                "v": {"grid": {"c": "#D9D9D9", "w": 0.75}},
            },
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "v": self.v,
            "kind": self.kind,
            "title": self.title,
            "legend": self.legend,
            "gridY": self.grid_y,
            "labels": self.labels,
            "cats": list(self.cats),
            "series": [s.to_dict() for s in self.series],
            "fsz": self.fsz,
        }
        if self.title_tx:
            d["titleTx"] = copy.deepcopy(self.title_tx)
        if self.ax:
            d["ax"] = copy.deepcopy(self.ax)
        if self.bg:
            d["bg"] = copy.deepcopy(self.bg)
        if self.border:
            d["border"] = copy.deepcopy(self.border)
        if self.pie_colors:
            d["pieColors"] = list(self.pie_colors)
        if self.embedded_workbook:
            d["embedded_workbook"] = self.embedded_workbook
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ChartData:
        if not data:
            return cls.create_sample()
        raw_series = data.get("series", [])
        series = [SeriesData.from_dict(s) for s in raw_series]
        return cls(
            v=int(data.get("v", 2)),
            kind=str(data.get("kind", "col")),
            title=str(data.get("title", "")),
            title_tx=dict(data.get("titleTx", {})),
            legend=str(data.get("legend", "r")),
            grid_y=bool(data.get("gridY", True)),
            labels=bool(data.get("labels", False)),
            cats=[str(c) for c in data.get("cats", [])],
            series=series,
            ax=dict(data.get("ax", {})),
            fsz=float(data.get("fsz", 10.0)),
            bg=copy.deepcopy(data.get("bg")),
            border=copy.deepcopy(data.get("border")),
            pie_colors=list(data.get("pieColors", [])),
            embedded_workbook=data.get("embedded_workbook"),
        )
