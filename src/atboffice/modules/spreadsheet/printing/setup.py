"""Excel 2003 Page Setup settings for one worksheet (``sheet.extra["print_setup"]``)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# name -> (width, height) in points, portrait; xlsx paperSize code
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A4": (595.276, 841.89),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "A3": (841.89, 1190.55),
    "A5": (419.53, 595.276),
    "B5": (515.91, 728.5),
}
PAPER_CODES: dict[str, int] = {"Letter": 1, "Legal": 5, "A3": 8, "A4": 9, "A5": 11, "B5": 13}

Range = tuple[int, int, int, int]


def _default_margins() -> dict[str, float]:
    # Excel 2003 defaults, in points: 1" top/bottom, 0.75" left/right, 0.5" header/footer
    return {"top": 72.0, "bottom": 72.0, "left": 54.0, "right": 54.0,
            "header": 36.0, "footer": 36.0}


@dataclass
class SheetPrintSetup:
    orientation: str = "portrait"  # "portrait" | "landscape"
    paper: str = "A4"
    scale: int = 100  # percent, 10..400
    fit_to: bool = False
    fit_width: int = 1  # pages wide (0 = automatic)
    fit_height: int = 1  # pages tall (0 = automatic)
    first_page_number: int | None = None
    margins: dict[str, float] = field(default_factory=_default_margins)
    center_h: bool = False
    center_v: bool = False
    header: str = ""  # Excel codes: "&L…&C…&R…" with &P &N &D &T &F &A
    footer: str = ""
    print_area: Range | None = None
    title_rows: tuple[int, int] | None = None
    title_cols: tuple[int, int] | None = None
    gridlines: bool = False
    headings: bool = False
    black_white: bool = False
    page_order: str = "down_then_over"  # or "over_then_down"

    def paper_size(self) -> tuple[float, float]:
        """Paper (width, height) in points with orientation applied."""
        w, h = PAPER_SIZES.get(self.paper, PAPER_SIZES["A4"])
        return (h, w) if self.orientation == "landscape" else (w, h)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for key in ("print_area", "title_rows", "title_cols"):
            if d[key] is not None:
                d[key] = list(d[key])
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SheetPrintSetup:
        if not data:
            return cls()
        kwargs: dict[str, Any] = {}
        for name in cls.__dataclass_fields__:
            if name not in data:
                continue
            val = data[name]
            if name in ("print_area", "title_rows", "title_cols") and val is not None:
                val = tuple(int(v) for v in val)
            if name == "margins":
                merged = _default_margins()
                merged.update({k: float(v) for k, v in dict(val).items()})
                val = merged
            kwargs[name] = val
        setup = cls(**kwargs)
        setup.scale = max(10, min(400, int(setup.scale or 100)))
        if setup.orientation not in ("portrait", "landscape"):
            setup.orientation = "portrait"
        if setup.paper not in PAPER_SIZES:
            setup.paper = "A4"
        return setup


def get_print_setup(sheet: Any) -> SheetPrintSetup:
    extra = getattr(sheet, "extra", None)
    raw = extra.get("print_setup") if isinstance(extra, dict) else None
    if isinstance(raw, SheetPrintSetup):
        return raw
    return SheetPrintSetup.from_dict(raw)


def set_print_setup(sheet: Any, setup: SheetPrintSetup) -> None:
    sheet.extra["print_setup"] = setup.to_dict()
    sheet.dirty = True
