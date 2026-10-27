"""Slide and transition models for Lectern presentations."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.presentation.models.comment import Comment
from atboffice.modules.presentation.models.designs import DesignTemplate
from atboffice.modules.presentation.models.layouts import layout_frames, make_placeholder
from atboffice.modules.presentation.models.shape import Shape


@dataclass
class Transition:
    """Slide transition animation and advance timing."""

    type: str = "none"  # "none", "fade", "wipe", "push", "split", etc.
    speed: str = "fast"  # "fast", "med", "slow"
    click: bool = True  # Advance on mouse click
    after: float | None = None  # Advance automatically after N seconds
    dir: str | None = None
    thruBlk: bool = False
    spokes: int | None = None
    orient: str | None = None
    dur: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.type,
            "spd": self.speed,
            "click": self.click,
            "after": self.after,
        }
        if self.dir is not None:
            d["dir"] = self.dir
        if self.thruBlk:
            d["thruBlk"] = True
        if self.spokes is not None:
            d["spokes"] = self.spokes
        if self.orient is not None:
            d["orient"] = self.orient
        if self.dur is not None:
            d["dur"] = self.dur
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Transition:
        if not data:
            return cls()
        return cls(
            type=str(data.get("type", "none")),
            speed=str(data.get("spd", data.get("speed", "fast"))),
            click=bool(data.get("click", True)),
            after=float(data["after"]) if data.get("after") is not None else None,
            dir=str(data["dir"]) if data.get("dir") is not None else None,
            thruBlk=bool(data.get("thruBlk", False)),
            spokes=int(data["spokes"]) if data.get("spokes") is not None else None,
            orient=str(data["orient"]) if data.get("orient") is not None else None,
            dur=int(data["dur"]) if data.get("dur") is not None else None,
        )


@dataclass
class Animation:
    """Shape entry/exit/emphasis/motion-path animation on a slide."""

    id: str
    sid: str  # Target shape id
    cls: str = "entr"  # "entr", "emph", "exit", "path"
    eff: str = "appear"  # Effect name (e.g. flyIn, zoom, spin, right)
    dir: str | None = None
    start: str = "click"  # "click", "with", "after"
    dur: int = 500  # duration in milliseconds
    delay: int = 0  # delay in milliseconds
    by: str = "all"  # "all" or "para" (by paragraph)
    repeat: int = 1  # for emphasis (e.g. spin, teeter)
    amount: float = 360.0  # for spin degrees or zoom scale percentage
    pts: list[list[float]] = field(default_factory=list)  # for motion paths
    para: int | None = None  # specific paragraph index when expanded

    # Backwards compatibility properties
    @property
    def type(self) -> str:
        return self.eff

    @type.setter
    def type(self, val: str) -> None:
        self.eff = val

    @property
    def trigger(self) -> str:
        return self.start

    @trigger.setter
    def trigger(self, val: str) -> None:
        self.start = val

    @property
    def duration(self) -> float:
        return self.dur / 1000.0

    @duration.setter
    def duration(self, val: float) -> None:
        self.dur = int(val * 1000)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "sid": self.sid,
            "cls": self.cls,
            "eff": self.eff,
            "type": self.eff,
            "dir": self.dir,
            "start": self.start,
            "trigger": self.start,
            "dur": self.dur,
            "duration": self.dur / 1000.0,
            "delay": self.delay,
            "by": self.by,
            "repeat": self.repeat,
            "amount": self.amount,
        }
        if self.pts:
            d["pts"] = self.pts
        if self.para is not None:
            d["para"] = self.para
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Animation:
        eff = str(data.get("eff", data.get("type", "appear")))
        cls_val = str(data.get("cls", "entr"))
        start = str(data.get("start", data.get("trigger", "click")))
        dur = int(data.get("dur", int(float(data.get("duration", 0.5)) * 1000)))
        return cls(
            id=str(data.get("id", f"a_{uuid.uuid4().hex[:6]}")),
            sid=str(data.get("sid", "")),
            cls=cls_val,
            eff=eff,
            dir=str(data["dir"]) if data.get("dir") is not None else None,
            start=start,
            dur=dur,
            delay=int(data.get("delay", 0)),
            by=str(data.get("by", "all")),
            repeat=int(data.get("repeat", 1)),
            amount=float(data.get("amount", 360.0)),
            pts=[list(p) for p in data.get("pts", [])] if "pts" in data else [],
            para=int(data["para"]) if data.get("para") is not None else None,
        )


@dataclass
class Slide:
    """Individual slide holding shapes, layout type, and speaker notes."""

    id: str
    layout: str = "text"
    design_id: str = ""
    shapes: list[Shape] = field(default_factory=list)
    notes: str = ""
    transition: Transition = field(default_factory=Transition)
    animations: list[Animation] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    hidden: bool = False

    def add_shape(self, shape: Shape) -> None:
        self.shapes.append(shape)

    def remove_shape(self, shape_id: str) -> bool:
        for i, s in enumerate(self.shapes):
            if s.id == shape_id:
                del self.shapes[i]
                return True
            if s.type == "group" and s.kids:
                for j, k in enumerate(s.kids):
                    if k.id == shape_id:
                        del s.kids[j]
                        return True
        return False

    def find_shape(self, shape_id: str) -> Shape | None:
        for s in self.shapes:
            if s.id == shape_id:
                return s
            if s.type == "group":
                for k in s.kids:
                    if k.id == shape_id:
                        return k
        return None

    def get_title(self) -> str:
        for s in self.shapes:
            if s.placeholder and s.placeholder.type in ("title", "ctrTitle") and s.text:
                return s.text.plain_text.strip().replace("\n", " ")
        return ""

    def all_text(self) -> str:
        out: list[str] = []
        for s in self.shapes:
            if s.text:
                out.append(s.text.plain_text)
            if s.kids:
                for k in s.kids:
                    if k.text:
                        out.append(k.text.plain_text)
        return "\n".join(out)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "layout": self.layout,
            "design": self.design_id,
            "shapes": [s.to_dict() for s in self.shapes],
            "notes": self.notes,
            "trans": self.transition.to_dict(),
            "anims": [a.to_dict() for a in self.animations],
            "comments": [c.to_dict() for c in self.comments],
            "hidden": self.hidden,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Slide:
        return cls(
            id=str(data.get("id", f"sl_{uuid.uuid4().hex[:8]}")),
            layout=str(data.get("layout", "text")),
            design_id=str(data.get("design", "")),
            shapes=[Shape.from_dict(s) for s in data.get("shapes", [])],
            notes=str(data.get("notes", "")),
            transition=Transition.from_dict(data.get("trans")),
            animations=[Animation.from_dict(a) for a in data.get("anims", [])],
            comments=[Comment.from_dict(c) for c in data.get("comments", [])],
            hidden=bool(data.get("hidden", False)),
        )


def create_slide(
    layout: str,
    design: DesignTemplate,
    slide_id: str | None = None,
) -> Slide:
    """Create a new slide with placeholders built for the requested layout and design."""
    s = Slide(
        id=slide_id or f"sl_{uuid.uuid4().hex[:8]}",
        layout=layout,
        design_id=design.id,
    )
    for fr in layout_frames(layout, design):
        s.shapes.append(make_placeholder(fr, design))
    return s


def dup_slide(slide: Slide) -> Slide:
    """Deep clone a slide with brand new shape IDs and re-mapped animation targets."""
    new_slide_id = f"sl_{uuid.uuid4().hex[:8]}"
    id_map: dict[str, str] = {}

    def clone_shape_with_new_id(sh: Shape) -> Shape:
        new_sh = copy.deepcopy(sh)
        nid = f"s_{uuid.uuid4().hex[:8]}"
        id_map[sh.id] = nid
        new_sh.id = nid
        # If it's a non-special placeholder, strip placeholder link in duplicated user shapes
        if new_sh.placeholder and new_sh.placeholder.type not in ("dt", "ftr", "sldNum"):
            # keep placeholder info
            pass
        if new_sh.kids:
            new_sh.kids = [clone_shape_with_new_id(k) for k in new_sh.kids]
        return new_sh

    new_shapes = [clone_shape_with_new_id(s) for s in slide.shapes]

    new_anims: list[Animation] = []
    for a in slide.animations:
        new_anims.append(
            Animation(
                id=f"a_{uuid.uuid4().hex[:6]}",
                sid=id_map.get(a.sid, a.sid),
                type=a.type,
                trigger=a.trigger,
                duration=a.duration,
            )
        )

    new_comments: list[Comment] = []
    for cm in slide.comments:
        new_cm = copy.deepcopy(cm)
        new_cm.id = f"cm_{uuid.uuid4().hex[:8]}"
        if new_cm.shape_id:
            new_cm.shape_id = id_map.get(new_cm.shape_id, new_cm.shape_id)
        for rep in new_cm.replies:
            rep.id = f"rep_{uuid.uuid4().hex[:8]}"
        new_comments.append(new_cm)

    return Slide(
        id=new_slide_id,
        layout=slide.layout,
        design_id=slide.design_id,
        shapes=new_shapes,
        notes=slide.notes,
        transition=copy.deepcopy(slide.transition),
        animations=new_anims,
        comments=new_comments,
        hidden=slide.hidden,
    )
