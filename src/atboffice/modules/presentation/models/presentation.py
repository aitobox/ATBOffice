"""Presentation container, slide sizing, layout application and aspect ratio adaptation for Lectern."""

from __future__ import annotations

import copy
import datetime
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.presentation.models.designs import DesignTemplate, build_design
from atboffice.modules.presentation.models.layouts import layout_frames, make_placeholder
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide, create_slide


@dataclass(frozen=True)
class SlideSize:
    """Pre-configured slide size option."""

    key: str
    name: str
    w: float
    h: float


STANDARD_SLIDE_SIZES: list[SlideSize] = [
    SlideSize(key="screen", name="On-screen Show (4:3)", w=720.0, h=540.0),
    SlideSize(key="widescreen", name="Widescreen (16:9), 13.33 x 7.5 in", w=960.0, h=540.0),
    SlideSize(key="wide", name="On-screen Show (16:9), 10 x 5.63 in", w=720.0, h=405.0),
    SlideSize(key="wide10", name="On-screen Show (16:10)", w=720.0, h=450.0),
    SlideSize(key="letter", name="Letter Paper (8.5x11 in)", w=720.0, h=540.0),
    SlideSize(key="a4", name="A4 Paper (210x297 mm)", w=780.0, h=540.0),
    SlideSize(key="custom", name="Custom", w=720.0, h=540.0),
]


@dataclass
class HeaderFooterSettings:
    """Master header and footer display settings."""

    dt: bool = False
    dt_auto: bool = True
    dt_fmt: str = "datetime1"
    dt_text: str = ""
    num: bool = False
    ftr: bool = False
    ftr_text: str = ""
    not_on_title: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "dt": self.dt,
            "dtAuto": self.dt_auto,
            "dtFmt": self.dt_fmt,
            "dtText": self.dt_text,
            "num": self.num,
            "ftr": self.ftr,
            "ftrText": self.ftr_text,
            "notOnTitle": self.not_on_title,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> HeaderFooterSettings:
        if not data:
            return cls()
        return cls(
            dt=bool(data.get("dt", False)),
            dt_auto=bool(data.get("dtAuto", True)),
            dt_fmt=str(data.get("dtFmt", "datetime1")),
            dt_text=str(data.get("dtText", "")),
            num=bool(data.get("num", False)),
            ftr=bool(data.get("ftr", False)),
            ftr_text=str(data.get("ftrText", "")),
            not_on_title=bool(data.get("notOnTitle", False)),
        )


@dataclass
class SlideShowSettings:
    """Slide show presentation options."""

    loop: bool = False
    no_anim: bool = False
    use_timings: bool = True
    from_slide: int = 0
    to_slide: int = 0
    pen_color: str = "#FF0000"
    kiosk: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop": self.loop,
            "noAnim": self.no_anim,
            "useTimings": self.use_timings,
            "from": self.from_slide,
            "to": self.to_slide,
            "penColor": self.pen_color,
            "kiosk": self.kiosk,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SlideShowSettings:
        if not data:
            return cls()
        return cls(
            loop=bool(data.get("loop", False)),
            no_anim=bool(data.get("noAnim", False)),
            use_timings=bool(data.get("useTimings", True)),
            from_slide=int(data.get("from", 0)),
            to_slide=int(data.get("to", 0)),
            pen_color=str(data.get("penColor", "#FF0000")),
            kiosk=bool(data.get("kiosk", False)),
        )


@dataclass
class Presentation:
    """Root container representing an entire presentation document."""

    w: float = 960.0
    h: float = 540.0
    title: str = ""
    first_num: int = 1
    designs: dict[str, DesignTemplate] = field(default_factory=dict)
    slides: list[Slide] = field(default_factory=list)
    show: SlideShowSettings = field(default_factory=SlideShowSettings)
    hf: HeaderFooterSettings = field(default_factory=HeaderFooterSettings)
    props: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create_new(
        cls,
        title: str = "",
        design_key: str = "default",
        w: float = 960.0,
        h: float = 540.0,
        empty: bool = False,
    ) -> Presentation:
        """Create a fresh presentation initialized with a design and first title slide."""
        d = build_design(design_key, w, h)
        pres = cls(
            w=w,
            h=h,
            title=title,
            designs={d.id: d},
            props={
                "author": "",
                "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        )
        if not empty:
            slide = create_slide(layout="title", design=d)
            pres.slides.append(slide)
        return pres

    def get_design_for_slide(self, slide: Slide | None) -> DesignTemplate:
        """Retrieve the design assigned to a slide, falling back to the primary design."""
        if slide and slide.design_id in self.designs:
            return self.designs[slide.design_id]
        if self.designs:
            return next(iter(self.designs.values()))
        # Fallback default
        d = build_design("default", self.w, self.h)
        self.designs[d.id] = d
        return d

    def add_slide(self, layout: str = "text", design_id: str | None = None) -> Slide:
        """Append a new slide to the presentation."""
        target_design = self.designs.get(design_id) if design_id else self.get_design_for_slide(None)
        slide = create_slide(layout=layout, design=target_design)
        self.slides.append(slide)
        return slide

    def insert_slide(self, index: int, slide: Slide) -> None:
        """Insert a slide at the specified index."""
        self.slides.insert(index, slide)

    def remove_slide(self, slide_or_id: Slide | str) -> bool:
        """Remove a slide by reference or id."""
        sid = slide_or_id.id if isinstance(slide_or_id, Slide) else slide_or_id
        for i, s in enumerate(self.slides):
            if s.id == sid:
                del self.slides[i]
                return True
        return False

    def move_slide(self, from_idx: int, to_idx: int) -> None:
        """Reorder slides."""
        if 0 <= from_idx < len(self.slides) and 0 <= to_idx < len(self.slides):
            s = self.slides.pop(from_idx)
            self.slides.insert(to_idx, s)

    def apply_layout(self, slide: Slide, key: str) -> None:
        """Re-apply a layout to an existing slide, preserving existing text and content."""
        design = self.get_design_for_slide(slide)
        frames = layout_frames(key, design)
        old_shapes = slide.shapes
        used_shapes: set[str] = set()

        def take_matching(pred: Any) -> Shape | None:
            for s in old_shapes:
                if s.id not in used_shapes and pred(s):
                    used_shapes.add(s.id)
                    return s
            return None

        new_shapes: list[Shape] = []
        for fr in frames:
            is_title = fr["type"] in ("title", "ctrTitle")
            matched = (
                take_matching(lambda s: s.placeholder and s.placeholder.type in ("title", "ctrTitle"))
                if is_title
                else take_matching(
                    lambda s: s.placeholder and s.placeholder.type not in ("title", "ctrTitle", "dt", "ftr", "sldNum")
                )
            )

            if matched and matched.type == "text":
                fresh = make_placeholder(fr, design)
                # Keep text paragraphs
                if matched.text:
                    fresh.text.paragraphs = copy.deepcopy(matched.text.paragraphs)
                new_shapes.append(fresh)
            elif matched:
                matched.placeholder = copy.deepcopy(PlaceholderInfo(type=fr["type"], idx=fr.get("idx", 0)))
                matched.x = float(fr["x"])
                matched.y = float(fr["y"])
                matched.w = float(fr["w"])
                if matched.type != "table":
                    matched.h = float(fr["h"])
                new_shapes.append(matched)
            else:
                new_shapes.append(make_placeholder(fr, design))

        # Preserve unmapped user shapes (non-empty text, images, drawings)
        for s in old_shapes:
            if s.id in used_shapes:
                continue
            # Drop empty placeholders
            if s.placeholder and s.text and s.text.is_empty() and s.placeholder.type not in ("dt", "ftr", "sldNum"):
                continue
            # Strip placeholder designation for orphaned text so it becomes a free text box
            if s.placeholder and s.placeholder.type not in ("dt", "ftr", "sldNum"):
                s.placeholder = None
            new_shapes.append(s)

        slide.layout = key
        slide.shapes = new_shapes

    def apply_design(
        self,
        design_key: str,
        slides: list[Slide] | None = None,
        keep_colors: Any | None = None,
    ) -> str:
        """Apply a new design template to target slides (or all). Returns new design id."""
        d = build_design(design_key, self.w, self.h)
        if keep_colors:
            d.colors = copy.deepcopy(keep_colors)
        self.designs[d.id] = d

        target_slides = slides if slides is not None else self.slides
        for s in target_slides:
            old_design = self.designs.get(s.design_id)
            s.design_id = d.id

            # Move untouched placeholders to new design frames
            new_frames = layout_frames(s.layout, d)
            old_frames = layout_frames(s.layout, old_design) if old_design else []

            for sh in s.shapes:
                if not sh.placeholder:
                    continue
                of = next(
                    (f for f in old_frames if f["type"] == sh.placeholder.type and f.get("idx", 0) == sh.placeholder.idx),
                    None,
                )
                nf = next(
                    (f for f in new_frames if f["type"] == sh.placeholder.type and f.get("idx", 0) == sh.placeholder.idx),
                    None,
                )
                if nf and (not of or (abs(of["x"] - sh.x) < 2 and abs(of["y"] - sh.y) < 2 and abs(of["w"] - sh.w) < 2)):
                    sh.x = float(nf["x"])
                    sh.y = float(nf["y"])
                    sh.w = float(nf["w"])
                    if sh.type != "table":
                        sh.h = float(nf["h"])

        # Garbage collect unused designs
        used_ids = {s.design_id for s in self.slides}
        for did in list(self.designs.keys()):
            if did not in used_ids and len(self.designs) > 1:
                del self.designs[did]

        return d.id

    def change_size(self, new_w: float, new_h: float, scale_content: bool = True) -> None:
        """Change slide aspect ratio / dimensions and adapt layouts and shapes."""
        old_w, old_h = self.w, self.h
        if abs(old_w - new_w) < 0.1 and abs(old_h - new_h) < 0.1:
            return

        self.w = new_w
        self.h = new_h
        sx = new_w / old_w if old_w else 1.0
        sy = new_h / old_h if old_h else 1.0

        # Rebuild all design templates for the new dimensions
        for d_id, d in list(self.designs.items()):
            rebuilt = build_design(d.key, new_w, new_h)
            rebuilt.id = d_id
            self.designs[d_id] = rebuilt

        if scale_content:
            for s in self.slides:
                d = self.get_design_for_slide(s)
                frames = layout_frames(s.layout, d)

                for sh in s.shapes:
                    if sh.placeholder:
                        # Find matching frame in newly calculated frames
                        nf = next(
                            (
                                f
                                for f in frames
                                if f["type"] == sh.placeholder.type and f.get("idx", 0) == sh.placeholder.idx
                            ),
                            None,
                        )
                        if nf:
                            sh.x = float(nf["x"])
                            sh.y = float(nf["y"])
                            sh.w = float(nf["w"])
                            sh.h = float(nf["h"])
                        else:
                            sh.scale(sx, sy)
                    else:
                        sh.scale(sx, sy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "W": round(self.w, 2),
            "H": round(self.h, 2),
            "title": self.title,
            "firstNum": self.first_num,
            "designs": {did: d.to_dict() for did, d in self.designs.items()},
            "slides": [s.to_dict() for s in self.slides],
            "show": self.show.to_dict(),
            "hf": self.hf.to_dict(),
            "props": copy.deepcopy(self.props),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Presentation:
        w = float(data.get("W", data.get("w", 960.0)))
        h = float(data.get("H", data.get("h", 540.0)))
        designs = {
            did: DesignTemplate.from_dict(d_data)
            for did, d_data in data.get("designs", {}).items()
        }
        slides = [Slide.from_dict(s) for s in data.get("slides", [])]
        return cls(
            w=w,
            h=h,
            title=str(data.get("title", "")),
            first_num=int(data.get("firstNum", 1)),
            designs=designs,
            slides=slides,
            show=SlideShowSettings.from_dict(data.get("show")),
            hf=HeaderFooterSettings.from_dict(data.get("hf")),
            props=dict(data.get("props", {})),
        )
